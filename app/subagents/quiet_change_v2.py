"""Quiet Change Agent v2 — meeting-spec rebuild (2026-05-21).

Classifies a Japanese ticker into positive / negative / neutral based on
the QUICK "quiet change" use case: companies whose revenue is rising but
whose stock price has fallen.

Per the PM spec (2026-05-21 meeting): the agent takes ONLY a securities
code and looks up everything — stock movement, recent earnings, and the
reason for any price change — by consulting ANALYST REPORTS AND NEWS.
No raw financial data feed.

Architecture (SerpAPI variant, 2026-05-22):
  1. Python calls SerpAPI to run a Google.co.jp search for the ticker.
     - Returns organic results (kabutan, minkabu, IRバンク, etc.)
     - If Google AI Overview is shown, fetch its text via a 2nd SerpAPI call
  2. Python builds a single SEARCH RESULTS block with AI Overview text +
     organic snippets.
  3. ONE Claude Haiku 4.5 call with tool_choice forcing submit_classification.
     No iterative tool-use loop, no token rebilling.
  4. Python composes derived fields (in_scope, in_scope_reason, as_of)
     from the LLM's structured output.

Taxonomy:
  in_scope = (revenue YoY up AND stock recently down)

  positive — analyst reports surface a POSITIVE reason; stock fell only
             due to post-earnings profit-taking. Fundamentals are fine.
  negative — analyst reports surface a NEGATIVE reason (cost pressure, no
             growth outlook, theme-ending, guided-down, weakening forward
             orders).
  neutral  — TARGET CLASS. No identifiable reason in analyst reports or
             news. The market likely hasn't noticed the fundamental
             improvement yet.

Public surface:
    analyze_ticker(code: str, model: str = ..., api_key: str | None = None) -> dict

Required env vars:
    ANTHROPIC_API_KEY — for Claude Haiku 4.5
    SERP_API_KEY      — for SerpAPI (sign up at serpapi.com, free tier =
                        100 searches/month, no card required)
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import anthropic
from serpapi import GoogleSearch

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:
    pass

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def _resolve_use_bedrock() -> bool:
    """Decide which API path the analyzer uses.

    Priority:
      1. USE_BEDROCK=true|false in env  -> explicit override always wins
      2. ANTHROPIC_API_KEY present      -> direct Anthropic API
      3. otherwise                      -> Bedrock (assumes AWS creds set)

    Prior default was "Bedrock unless explicitly disabled," which silently
    routed past ANTHROPIC_API_KEY and produced the 2026-05-22 Bedrock
    charges. The new default prefers direct API when a key is set so the
    user's intended billing path wins without needing an extra env var.
    """
    explicit = os.environ.get("USE_BEDROCK")
    if explicit is not None:
        return explicit.lower() == "true"
    return not bool(os.environ.get("ANTHROPIC_API_KEY"))


USE_BEDROCK = _resolve_use_bedrock()
MAX_TOKENS = 800  # runaway guardrail; not a cost lever (you pay for tokens
# actually generated, not the cap). Lowered from 2500 to bound worst-case
# blowups. If a rationale ever needs more than ~600 tokens, raise it.
SERPAPI_ORGANIC_RESULTS = 7
SERPAPI_NEWS_RESULTS = 10
LOW_ATTENTION_CONFIRM_THRESHOLD = 8.0  # below this, run confirmation search
# Raised from 4.0 after adding the retail-chatter channel (which added ~3-5
# points of typical attention to every name). The "thin" cutoff has to shift
# up to match the new score distribution; otherwise post-retail "thin"
# becomes much rarer than intended and the strict gate stops firing on
# genuinely overlooked names.

SYSTEM_PROMPT = """You are a Japanese equity analyst working with QUICK, a Japanese financial-services company. QUICK's analysts write growth reports for individual companies but cannot cover the entire market by hand. Your job is to triage a Japanese listed company so a human analyst can decide whether to investigate further.

THE QUICK USE CASE — what we are looking for
A "quiet change" company is one whose REVENUE IS INCREASING but whose STOCK PRICE HAS RECENTLY FALLEN. The market hasn't priced in the fundamental improvement, and our analysts want to surface these BEFORE the market does. But not every "revenue up, stock down" company is a target — when there is a clear reason for the drop (positive OR negative), we want to filter it out.

OUTPUT — TWO LAYERS

LAYER 1: PRE-FILTER (`in_scope`)
- `true` iff the latest reported period's revenue is up YoY AND the stock price has fallen over the last ~3 months.
- `false` otherwise (revenue flat/down OR stock flat/up).
- Always emit a one-sentence `in_scope_reason` citing the actual numbers you found.

LAYER 2: CLASSIFICATION (`classification` — exactly one of three)

`positive` — There IS a POSITIVE reason in the filing or recent news, but the stock still fell, ONLY because early holders sold to lock in gains (post-earnings profit-taking). The company itself is fine; the drop is a market-mechanic, not a fundamentals signal.
Example pattern: "Q3 beat consensus, stock spiked briefly, then drifted down over the following week as buy-and-hold positions were unwound."

`negative` — There IS a NEGATIVE reason in the filing or recent news that explains the drop:
  - Cost pressure (semiconductors, raw materials, content production)
  - No forward growth visible (no new businesses, market saturating)
  - A tailwind ending (COVID demand, supply-shortage premium gone)
  - The company itself guided lower for the next period (大幅な減益予想 / downward profit revision)
  - Forward orders / 受注見込み weakening even though current numbers are fine
The market saw the reason and priced it in.

`neutral` — NO identifiable reason in any filing, news, or analyst commentary explains why the stock fell. Fundamentals are improving but the market hasn't noticed. THIS IS THE QUICK TARGET.

CRITICAL: Reserve `neutral` for genuine information vacuums. If web_search surfaces ANY plausible driver — positive (profit-taking) or negative (cost / outlook / theme-ending / guided-down / weakening orders) — DO NOT classify as `neutral`. Over-classifying as `neutral` defeats the purpose of this agent.

CONFIDENCE (`confidence` — exactly one of three)
- `high` — Multiple sources corroborate the SAME named driver (for positive/negative), OR exhaustive search turned up no driver at all (for neutral).
- `medium` — One source, or sources hint at a driver without specifics.
- `low` — Sparse / conflicting sources, or data is missing.

INPUT FORMAT
The user message contains:
  1. The 4-digit ticker
  2. Today's date (YYYY-MM-DD reference)
  3. A SEARCH RESULTS block — Google AI Overview text (when Google shows one) plus the top organic search results from Google.co.jp for this ticker. Sources are typically Japanese-domestic analyst sites (kabutan, minkabu, 株予報Pro, IRバンク, note.com) plus news.

This is your ONLY source of data. You do NOT have any search tool — everything you need is already in the SEARCH RESULTS block.

WHAT TO EXTRACT
- `company_name_ja` / `company_name_en` — from search results
- `earnings_summary` — latest reported period (annual or quarterly, whichever the analyst reports cite), revenue / op income / net income YoY %, direction (up/flat/down)
- `stock_summary` — the price window the analyst reports cite, move %, direction
- `classification` (positive/negative/neutral) and `confidence`
- `rationale_en` / `rationale_ja` — the specific reason the analyst reports cite

**EXTRACTING `revenue_yoy_pct` AND `direction` — critical for QUICK in_scope filter**:

`direction` is ONLY about REVENUE in the latest reported period. It is NOT about:
  - Net income / 純利益 / 営業利益 direction (those are separate fields)
  - Forward guidance for the next year
  - Analyst forecasts
  - Stock price direction
  - "Earnings downward revision" (下方修正) — these are almost always profit revisions, not revenue

Scan search snippets for revenue YoY %. Common Japanese phrasings:
  - `売上高 X億円 (前期比+Y%)` — revenue ¥XB (YoY +Y%)
  - `売上 +Y%増収` — revenue +Y% increase
  - `売上高は前年同期比Y%増` — revenue increased Y% YoY
  - `増収` alone implies revenue up
  - `減収` alone implies revenue down
  - English: "revenue grew Y%", "FY2026 revenue ¥4,974B (+14.1% YoY)"

**HARD RULE**: If ANY snippet cites a positive revenue YoY %, OR mentions "増収" / "record revenue" / "revenue up" for the latest period, set `revenue_yoy_pct` to that number (or a representative positive number) AND set `direction` to "up". A profit/net-income downward revision (下方修正) does NOT override this — that's profit, not revenue.

If you genuinely find NO revenue figure or 増収/減収 indicator in any snippet, use null for `revenue_yoy_pct` and pick `direction` from whatever wording does appear (e.g., "record revenue" → up; "revenue decline" → down). Do NOT fabricate numbers.

If you cannot identify the company at all, set `confidence: "low"` and explain in `rationale_en`.

RULES
- `rationale_en` MUST name a specific driver (event, number, forward-looking concern from the analyst report). Generic phrases like "market sentiment weakened" or "broader sell-off" are NOT acceptable.
- `rationale_ja` is the same reasoning in natural Japanese, naming the same driver.
- **STOCK WINDOW SELECTION**: When analyst reports cite multiple stock windows, PREFER 1-3 month or "since-earnings-release" windows. AVOID 1-day / intraday / "earnings-day" windows — they're noise, not signal. If only short-term windows are cited, use them but set `confidence: "low"`.
- **FORWARD GUIDANCE OVERRIDE — CRITICAL**: When you find current results, ALWAYS look for the company's OWN guidance for the NEXT reporting period (来期業績予想 / 業績見通し / 次期予想 / forward guidance / FY+1 outlook). If the company itself has guided revenue OR operating income OR net income DOWN for the next period — even modestly — classify as `negative` regardless of how strong the trailing beat was. The market prices forward guidance, not trailing beats. Patterns to catch:
    * "大幅な減益予想" (significant earnings decline forecast)
    * "業績下方修正" / "下方修正" (downward revision)
    * "受注見込み減少" / "受注の減少" (orders forecast to decline)
    * "FY27 guidance" lower than FY26 actuals
    * Analyst's consensus EPS for next year below current year
  Examples: 4751 CyberAgent (company guided FY27 profit down → negative); 7974 Nintendo (FY27 unit guidance -17%, FY27 revenue -11% → negative); 7011 Mitsubishi Heavy (next-period orders -11% → negative). The "positive" class is ONLY for tickers where a profit-taking drop occurred AND there is no bearish forward signal.
- Call submit_classification when you have enough information — don't narrate or summarize in text first."""


CLASSIFICATION_TOOL = {
    "name": "submit_classification",
    "description": (
        "Submit the structured interpretation for this ticker. Extract every "
        "field from the analyst reports and news in the SEARCH RESULTS block. "
        "Python composes derived fields (in_scope, in_scope_reason, as_of) "
        "from your structured output. Call this tool exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "company_name_ja": {"type": "string", "description": "Japanese company name."},
            "company_name_en": {"type": "string", "description": "English company name."},
            "classification": {
                "type": "string",
                "enum": ["positive", "negative", "neutral"],
                "description": (
                    "positive = good news, profit-taking drop; "
                    "negative = bad news explains drop; "
                    "neutral = no identifiable reason (TARGET)."
                ),
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "earnings_summary": {
                "type": "object",
                "properties": {
                    "latest_period": {
                        "type": "string",
                        "description": "The most recently REPORTED period in the search results (e.g. 'Q2 FY2026/9' or 'FY2026/3 full year'). NOT next year's guidance/forecast period.",
                    },
                    "revenue_yoy_pct": {
                        "type": ["number", "null"],
                        "description": "Revenue YoY % growth for the LATEST REPORTED PERIOD. Populate this whenever the search results mention any YoY revenue figure for the most recent quarter or fiscal year. Use null ONLY when no YoY % appears anywhere.",
                    },
                    "operating_income_yoy_pct": {"type": ["number", "null"]},
                    "net_income_yoy_pct": {"type": ["number", "null"]},
                    "direction": {
                        "type": "string",
                        "enum": ["up", "flat", "down"],
                        "description": "Revenue YoY direction in the LATEST REPORTED PERIOD ONLY. Do NOT use forward guidance / next-year forecast / FY+1 outlook here — that goes into the classification, not direction. If the most recently reported revenue grew, direction is 'up' EVEN IF the company guided down for next year.",
                    },
                },
                "required": ["latest_period", "direction"],
            },
            "stock_summary": {
                "type": "object",
                "properties": {
                    "window": {
                        "type": "string",
                        "description": (
                            "Window the analyst report references — e.g. "
                            "'last_3_months', 'YTD_2026', 'last_6_months', "
                            "'since_FY26_earnings'."
                        ),
                    },
                    "move_pct": {
                        "type": "number",
                        "description": "Percent move; negative for drops.",
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["up", "flat", "down"],
                    },
                },
                "required": ["window", "move_pct", "direction"],
            },
            "rationale_en": {
                "type": "string",
                "description": (
                    "Two short English sentences naming the SPECIFIC driver "
                    "(event, number, forward-looking concern). NOT generic."
                ),
            },
            "rationale_ja": {
                "type": "string",
                "description": "Same reasoning in natural Japanese, same driver named.",
            },
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                    },
                    "required": ["title", "url"],
                },
            },
        },
        "required": [
            "company_name_ja",
            "company_name_en",
            "classification",
            "confidence",
            "earnings_summary",
            "stock_summary",
            "rationale_en",
            "rationale_ja",
        ],
    },
}


# ---------------------------------------------------------------------------
# Attention scoring (v2 — anomaly-targeted)
# ---------------------------------------------------------------------------

# Source classification — URLs mapped to attention signal categories.
# Aggregator stubs (auto-generated pages that exist for every TSE ticker)
# are SUBTRACTED to avoid the size-confound bug Claude's review flagged.
_EDITORIAL_DOMAINS = {
    "nikkei.com", "jp.reuters.com", "bloomberg.co.jp", "zaikei.co.jp",
    "asahi.com", "mainichi.jp", "sankei.com", "jiji.com",
    "diamond.jp", "toyokeizai.net", "newspicks.com",
    "itmedia.co.jp", "businessinsider.jp", "forbesjapan.com",
    "news.yahoo.co.jp",
}
_BROKERAGE_DOMAINS = {
    "daiwa-am.co.jp", "smbcnikko.co.jp", "sbisec.co.jp", "rakuten-sec.co.jp",
    "marusan-sec.co.jp", "monex.co.jp", "simplywall.st",
}
_AGGREGATOR_DOMAINS = {
    "kabutan.jp", "minkabu.jp", "irbank.net", "kabuyoho.jp",
    "stockanalysis.com", "tradingview.com", "investing.com",
    "morningstar.com", "stockopedia.com", "quartr.com",
    "finance.yahoo.co.jp", "finance.yahoo.com",
}
_FORUM_DOMAINS = {"5ch.net", "reddit.com"}


def _classify_source(url: str, snippet: str = "") -> str:
    """Classify a SerpAPI result URL into an attention-signal category.

    Returns one of: editorial | brokerage | aggregator_article | aggregator_stub
    | forum | ir_official | other. Aggregator URLs that look like article
    pages (path contains /news/ or a date) are upgraded to aggregator_article.
    """
    if not url:
        return "other"
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc.lower()
        path = urlparse(url).path.lower()
    except Exception:
        return "other"
    # Strip leading "www."
    netloc = netloc.removeprefix("www.")

    if any(d in netloc for d in _EDITORIAL_DOMAINS):
        return "editorial"
    if any(d in netloc for d in _BROKERAGE_DOMAINS):
        return "brokerage"
    if any(d in netloc for d in _FORUM_DOMAINS):
        return "forum"
    if any(d in netloc for d in _AGGREGATOR_DOMAINS):
        # Distinguish news-article subpaths from data stubs
        if "/news/" in path or "/article/" in path or "/articles/" in path:
            return "aggregator_article"
        return "aggregator_stub"
    if "note.com" in netloc:
        # note.com is a mix — treat as editorial if path contains /n/ (article)
        return "editorial" if "/n/" in path else "other"
    # Company IR pages — domain looks like company official
    if any(s in netloc for s in (".co.jp", ".jp")) and "ir" in path:
        return "ir_official"
    return "other"


def _is_recent_2026(snippet: str, title: str) -> bool:
    """Crude heuristic: does the snippet/title cite a 2026 date?"""
    text = (snippet or "") + " " + (title or "")
    return any(token in text for token in ("2026", "26年", "令和8"))


# Weight for retail/social chatter hits (5ch / Yahoo boards / note.com)
# from a dedicated targeted probe. Set to 1.0 — same as aggregator_article:
# "real but anonymous evidence of attention, and you went looking for it"
# (stronger than incidental forum=0.3, weaker than brokerage=2.0).
# Err-high rationale: retail-loud names are often *hyped*, not "overlooked,"
# so the cost of weighting too high (occasional false demotion) is much smaller
# than weighting too low (Base-Food-style false-positive lead).
RETAIL_CHATTER_WEIGHT = 1.0
RETAIL_CHATTER_DOMAINS = ("5ch.net", "note.com", "yahoo.co.jp")


def _retail_chatter_hits(retail_results: list[dict[str, Any]]) -> int:
    """Count retail/social hits in a dedicated retail-chatter SerpAPI payload."""
    from urllib.parse import urlparse
    n = 0
    seen = set()
    for r in retail_results or []:
        url = (r.get("link") or r.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            netloc = urlparse(url).netloc.lower().removeprefix("www.")
        except Exception:
            continue
        if any(d in netloc for d in RETAIL_CHATTER_DOMAINS):
            n += 1
    return n


def _compute_attention_score(
    anomaly_results: list[dict[str, Any]],
    confirmation_results: list[dict[str, Any]] | None = None,
    retail_chatter_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute multi-channel attention score.

    Channels (each contributing additively):
      - editorial         (×2.5) — strong: financial press / named analysts
      - brokerage         (×2.0) — strong: brokerage initiations / reports
      - aggregator_article(×1.0) — real-but-anonymous: dated kabutan/minkabu
      - retail_chatter    (×1.0) — real-but-anonymous: 5ch / Yahoo / note.com,
                                   only counted from a TARGETED probe, since
                                   the brokerage-weighted general search is
                                   structurally blind to this channel
      - forum             (×0.3) — incidental forum mentions from general
                                   search (kept for back-compat / low weight)
      - aggregator_stub   (×−0.5)— auto-generated stub-page noise (subtract)
      - recent_2026       (×0.5) — recency bonus

    A name is "overlooked" only if it's quiet across ALL the channels above —
    the multi-channel model. Earlier single-channel-only failures: Nissin (high
    fame, missed by anomaly search) and Base Food (heavy retail, missed by
    brokerage-weighted score). The retail-chatter channel directly addresses
    the latter; the fame guard (market-cap heuristic in the aggregator)
    addresses the former.
    """
    all_results = list(anomaly_results) + list(confirmation_results or [])
    if not all_results and not retail_chatter_results:
        return {
            "score": 0.0,
            "editorial": 0, "brokerage": 0, "aggregator_article": 0,
            "aggregator_stub": 0, "forum": 0, "ir_official": 0, "other": 0,
            "retail_chatter": 0, "recent_2026": 0,
            "rationale": "no search results returned",
        }

    counts = {
        "editorial": 0, "brokerage": 0, "aggregator_article": 0,
        "aggregator_stub": 0, "forum": 0, "ir_official": 0, "other": 0,
    }
    recent_count = 0
    seen_urls: set[str] = set()
    seen_domains: set[str] = set()

    for r in all_results:
        url = (r.get("link") or r.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            from urllib.parse import urlparse
            seen_domains.add(urlparse(url).netloc.lower().removeprefix("www."))
        except Exception:
            pass
        snippet = r.get("snippet", "")
        title = r.get("title", "")
        category = _classify_source(url, snippet)
        counts[category] = counts.get(category, 0) + 1
        if _is_recent_2026(snippet, title):
            recent_count += 1

    # Dedicated retail-chatter channel (counted separately so the weight is explicit)
    retail_chatter = _retail_chatter_hits(retail_chatter_results or [])

    # Weights (subject to calibration; see module-level constants)
    score = (
        counts["editorial"]            * 2.5
        + counts["brokerage"]          * 2.0
        + counts["aggregator_article"] * 1.0
        + retail_chatter               * RETAIL_CHATTER_WEIGHT
        + counts["forum"]              * 0.3
        - counts["aggregator_stub"]    * 0.5
        + recent_count                 * 0.5
    )

    return {
        "score": round(score, 2),
        **counts,
        "retail_chatter": retail_chatter,
        "recent_2026": recent_count,
        "unique_domains": len(seen_domains),
        "rationale": (
            f"editorial={counts['editorial']} brokerage={counts['brokerage']} "
            f"agg_article={counts['aggregator_article']} retail={retail_chatter} "
            f"agg_stub={counts['aggregator_stub']} recent_2026={recent_count}"
        ),
    }


def _run_retail_chatter_search(ticker: str, serp_key: str) -> dict:
    """Targeted SerpAPI search for retail/social chatter on this ticker.

    Promoted from scripts/run_dash_experiment.py to be a standard pipeline
    component. Queries Japanese retail-trader spaces (5ch, Yahoo boards,
    note.com) that the brokerage-weighted general search misses by design.
    """
    if GoogleSearch is None:
        return {}
    params = {
        "q": f"{ticker} 株価 (5ch OR 掲示板 OR note.com)",
        "engine": "google",
        "google_domain": "google.co.jp",
        "gl": "jp",
        "hl": "ja",
        "num": "10",
        "api_key": serp_key,
    }
    return GoogleSearch(params).get_dict()


def _make_anthropic_client(api_key: str | None):
    """Return an Anthropic or AnthropicBedrock client based on USE_BEDROCK env."""
    if USE_BEDROCK:
        return anthropic.AnthropicBedrock(
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
            aws_access_key=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN") or None,
        )
    return anthropic.Anthropic(api_key=api_key)


def _resolve_model_id(model: str) -> str:
    """Pick the right model ID format for the active backend."""
    if USE_BEDROCK:
        # If caller passed a direct-API ID, swap to the Bedrock inference profile
        if model.startswith("claude-haiku-4-5"):
            return DEFAULT_BEDROCK_MODEL
        if model.startswith("us.anthropic.") or model.startswith("anthropic."):
            return model
        # Fallback: use the env-configured Bedrock model if any
        return os.environ.get("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL)
    return model


# ---------------------------------------------------------------------------
# SerpAPI search helpers
# ---------------------------------------------------------------------------

def _run_anomaly_news_search(code: str, serp_key: str) -> dict[str, Any]:
    """News-tab Google search for THIS DECLINE — the anomaly-attention signal.

    Uses Google News engine to restrict to news articles only. If multiple
    recent JP news articles surface, the decline is being noticed. If empty
    or sparse, likely unnoticed (subject to confirmation guard).
    """
    resp = GoogleSearch({
        "engine": "google_news",
        "q": f"{code} 株価 下落 理由 2026",
        "hl": "ja",
        "gl": "jp",
        "google_domain": "google.co.jp",
        "num": SERPAPI_NEWS_RESULTS,
        "api_key": serp_key,
    }).get_dict()
    # Normalize so callers see results under "news_results" with link/title/snippet
    raw = resp.get("news_results") or []
    normalized: list[dict[str, Any]] = []
    for item in raw:
        # Some google_news results are grouped under "stories" — flatten
        if isinstance(item, dict) and "stories" in item and isinstance(item["stories"], list):
            for s in item["stories"]:
                normalized.append({
                    "title": s.get("title", ""),
                    "link": s.get("link", ""),
                    "snippet": s.get("snippet", "") or s.get("source", {}).get("name", ""),
                })
        else:
            normalized.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", "") or item.get("source", {}).get("name", ""),
            })
    return {"news_results": normalized}


def _run_confirmation_search(code: str, serp_key: str) -> dict[str, Any]:
    """Low-side guard: a different angle search to confirm low attention.

    Run only when anomaly search returns sparse results. If this also
    comes back thin, we have positive evidence of low coverage. If it
    finds rich content the first query missed, that's a retrieval failure,
    not a quiet stock.
    """
    resp = GoogleSearch({
        "q": f"{code} なぜ下落 株価 業績 説明 2026",
        "hl": "ja",
        "gl": "jp",
        "google_domain": "google.co.jp",
        "num": SERPAPI_ORGANIC_RESULTS,
        "api_key": serp_key,
    }).get_dict()
    return {"organic_results": resp.get("organic_results") or []}


def _run_serpapi_search(code: str, serp_key: str) -> tuple[dict[str, Any], int]:
    """Run Google.co.jp search via SerpAPI. Returns (response_dict, search_count).

    Uses the organic results — Japanese-domestic analyst sites (kabutan,
    minkabu, 株予報Pro, IRバンク, note.com) with rich snippets. Google's AI
    Overview is currently NOT retrievable separately via SerpAPI's
    google_ai_overview engine (returns "no results" for finance queries),
    so we skip that call. If text_blocks are inlined into the primary
    response, we use them; otherwise organic snippets carry the load.
    """
    # Query balanced for the QUICK universe (rev↑ + stock↓): it needs to surface
    # BOTH the latest reported numbers (売上 / 営業利益 / 純利益 keywords pull
    # the most recent quarterly/annual results) AND the why-decline angle
    # (下落理由 / 下方修正 / 業績見通し). Without the income-statement terms,
    # the search returns only decline articles and the model can't ground
    # the latest-period revenue direction.
    query = (
        f"{code} 株価 売上 営業利益 純利益 決算 業績 "
        f"アナリスト 業績予想 下方修正 下落理由 来期業績 2026"
    )
    primary = GoogleSearch({
        "q": query,
        "hl": "ja",
        "gl": "jp",
        "google_domain": "google.co.jp",
        "num": SERPAPI_ORGANIC_RESULTS,
        "api_key": serp_key,
    }).get_dict()

    ai_overview = primary.get("ai_overview") or {}
    ai_text = ""
    if ai_overview.get("text_blocks"):
        ai_text = "\n".join(
            b.get("snippet", "") for b in ai_overview["text_blocks"] if b.get("snippet")
        )

    return {
        "ai_overview_text": ai_text,
        "organic_results": primary.get("organic_results") or [],
    }, 1


def _format_serpapi_for_prompt(resp: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    """Build the SEARCH RESULTS block + a sources list from a SerpAPI response."""
    sources: list[dict[str, str]] = []
    lines: list[str] = []

    ai_text = (resp.get("ai_overview_text") or "").strip()
    if ai_text:
        lines.append("GOOGLE AI OVERVIEW (Gemini-generated summary):")
        lines.append(ai_text)
        lines.append("")

    organic = resp.get("organic_results") or []
    if organic:
        lines.append("TOP GOOGLE.CO.JP SEARCH RESULTS:")
        for i, r in enumerate(organic[:SERPAPI_ORGANIC_RESULTS], start=1):
            title = (r.get("title") or "").strip()
            url = (r.get("link") or "").strip()
            snippet = (r.get("snippet") or "").strip()
            if not title and not snippet:
                continue
            lines.append(f"[{i}] {title}")
            if snippet:
                lines.append(f"    {snippet[:500]}")
            if url:
                lines.append(f"    url: {url}")
            if title and url:
                sources.append({"title": title, "url": url})

    return "\n".join(lines), sources


def analyze_ticker(
    code: str,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    serp_api_key: str | None = None,
) -> dict[str, Any]:
    """Classify a Japanese ticker per the meeting-spec taxonomy.

    Uses SerpAPI to fetch Google.co.jp search results + Google AI Overview text,
    then calls Claude Haiku once with the search content baked into the prompt.

    Args:
        code: 4-digit Japanese stock ticker (e.g. "7974" for Nintendo).
        model: Anthropic model ID. Defaults to Haiku 4.5.
        api_key: Optional Anthropic override; else reads ANTHROPIC_API_KEY.
        serp_api_key: Optional SerpAPI override; else reads SERP_API_KEY.

    Returns:
        A dict matching the submit_classification schema, plus model + usage.
        On API failure, returns {"ticker": code, "error": "..."} instead.
    """
    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in env and not passed")

    if serp_api_key is None:
        serp_api_key = os.environ.get("SERP_API_KEY") or os.environ.get("SERPAPI_API_KEY")
    if not serp_api_key:
        raise RuntimeError(
            "SERP_API_KEY not set. Sign up at https://serpapi.com (free tier = "
            "100 searches/month, no card) and add SERP_API_KEY=... to .env."
        )

    today = date.today().isoformat()

    # === PASS 1A: driver search — for sentiment/driver extraction ===
    try:
        serp_resp, search_count = _run_serpapi_search(code, serp_api_key)
    except Exception as e:
        return {"ticker": code, "error": f"SerpAPI error: {e}", "model": model}

    # === PASS 1B: anomaly news search — measures attention on the DECLINE ===
    try:
        anomaly = _run_anomaly_news_search(code, serp_api_key)
        search_count += 1
    except Exception:
        anomaly = {"news_results": []}

    confirmation_results: list[dict[str, Any]] = []
    attention = _compute_attention_score(anomaly.get("news_results", []))

    # === PASS 1C: low-side confirmation guard (only when attention is sparse) ===
    if attention["score"] < LOW_ATTENTION_CONFIRM_THRESHOLD:
        try:
            confirm = _run_confirmation_search(code, serp_api_key)
            confirmation_results = confirm.get("organic_results", [])
            search_count += 1
            attention = _compute_attention_score(
                anomaly.get("news_results", []), confirmation_results
            )
        except Exception:
            pass

    search_block, sources = _format_serpapi_for_prompt(serp_resp)

    user_message = (
        f"Analyze Japanese ticker: {code}\n"
        f"Today's date: {today}\n\n"
        f"--- SEARCH RESULTS (Google.co.jp) ---\n{search_block}\n"
        f"--- END SEARCH RESULTS ---\n\n"
        "Extract everything from the analyst reports and news above and call "
        "submit_classification with the structured result."
    )

    client = _make_anthropic_client(api_key)
    resolved_model = _resolve_model_id(model)

    try:
        response = client.messages.create(
            model=resolved_model,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[{**CLASSIFICATION_TOOL, "cache_control": {"type": "ephemeral"}}],
            tool_choice={"type": "tool", "name": "submit_classification"},
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as e:
        return {"ticker": code, "error": f"Anthropic API error: {e}", "model": resolved_model}

    submission: dict[str, Any] | None = None
    for block in response.content:
        if (
            getattr(block, "type", None) == "tool_use"
            and getattr(block, "name", None) == "submit_classification"
        ):
            submission = block.input
            break

    if submission is None:
        return {
            "ticker": code,
            "error": "model did not call submit_classification",
            "model": model,
            "stop_reason": getattr(response, "stop_reason", None),
            "search_count": search_count,
        }

    result: dict[str, Any] = {
        "ticker": code,
        "as_of": today,
        **submission,
    }

    earnings = dict(result.get("earnings_summary") or {})
    stock = dict(result.get("stock_summary") or {})

    # Normalize earnings.direction from revenue_yoy_pct when a number exists.
    # The LLM sometimes conflates forward outlook with current direction;
    # the numeric value is the ground truth for the latest reported period.
    rev_pct = earnings.get("revenue_yoy_pct")
    if isinstance(rev_pct, (int, float)):
        if rev_pct > 1.0:
            earnings["direction"] = "up"
        elif rev_pct < -1.0:
            earnings["direction"] = "down"
        else:
            earnings["direction"] = "flat"
    result["earnings_summary"] = earnings

    earnings_dir = earnings.get("direction")
    stock_dir = stock.get("direction")
    in_scope = earnings_dir == "up" and stock_dir == "down"
    result["in_scope"] = in_scope
    result["in_scope_reason"] = _build_in_scope_reason(earnings, stock)

    # === ATTENTION GATE (v2): override classification based on coverage ===
    # If attention is LOW, this is a potential quiet-change target — emit
    # neutral with positive evidence of low coverage, NOT just because LLM
    # didn't find a reason. This is the Rakuten guard from Claude's review.
    NOTICED_HIGH = 8.0
    NOTICED_LOW = LOW_ATTENTION_CONFIRM_THRESHOLD  # 4.0
    attention_score = attention["score"]
    llm_class = result.get("classification")

    if attention_score >= NOTICED_HIGH:
        noticed = True
        # Heavy attention exists — if LLM said neutral, it's a retrieval failure
        # (driver search missed the story everyone is discussing). Flag it.
        if llm_class == "neutral":
            result["classification"] = "noticed_retrieval_failure"
            result["confidence"] = "low"
            result["needs_manual_review"] = True
    elif attention_score <= NOTICED_LOW:
        noticed = False
        # Override LLM — this IS a quiet-change candidate per attention signal.
        # Positive evidence of low coverage > "search didn't find a reason."
        result["classification"] = "neutral"
        if result.get("confidence") in (None, "low"):
            result["confidence"] = "medium"  # backed by positive low-coverage evidence
    else:
        # ambiguous band — leave LLM's classification but flag uncertainty
        noticed = None
        if llm_class == "neutral":
            result["confidence"] = "low"

    result["noticed"] = noticed
    result["attention"] = attention

    result["model"] = resolved_model
    result["search_provider"] = "serpapi"
    result["search_count"] = search_count
    result["ai_overview_used"] = bool(serp_resp.get("ai_overview_text"))

    if not result.get("sources"):
        result["sources"] = sources[:10]

    usage = getattr(response, "usage", None)
    if usage is not None:
        result["usage"] = {
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        }

    return result


def _build_in_scope_reason(
    earnings: dict[str, Any],
    stock: dict[str, Any],
) -> str:
    """Build a one-sentence in_scope_reason from LLM-extracted summaries."""
    rev_dir = earnings.get("direction")
    rev_pct = earnings.get("revenue_yoy_pct")
    period = earnings.get("latest_period") or "latest period"
    if rev_dir is None:
        rev_text = "revenue direction unknown"
    elif rev_pct is not None:
        rev_text = f"revenue {rev_dir} {rev_pct:+.1f}% YoY ({period})"
    else:
        rev_text = f"revenue {rev_dir} YoY ({period})"

    stock_dir = stock.get("direction")
    stock_pct = stock.get("move_pct")
    stock_window = stock.get("window") or "recent window"
    if stock_dir is None:
        stock_text = "stock direction unknown"
    elif stock_pct is not None:
        stock_text = f"stock {stock_dir} {stock_pct:+.1f}% over {stock_window}"
    else:
        stock_text = f"stock {stock_dir} over {stock_window}"
    return f"{rev_text}; {stock_text}."
