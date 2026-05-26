"""TempestAI Finance API loader — drop-in replacement for edinet_loader.

Reads cached JSON from ``data/tempest/{ticker}/`` (populated by
``fetch_tempest.py``) and exposes the same public API as
``app/ingest/edinet_loader.py``, ``app/ingest/segment_extract.py``, and
``app/ingest/bs_extract.py`` — so the subagents can swap their imports
without touching downstream logic.

SCOPE & LIMITATIONS
-------------------
The Tempest staging API only parses XBRL text/segments for **TOPIX 100**.
Outside that pool, financials/segments/indicators come back empty (per
the API docs §5). This loader therefore restricts the universe to TOPIX
100 — non-TOPIX-100 tickers in the Tempest cache are silently dropped
from ``build_universe``. The user opted into this trade-off when wiring
the agents to Tempest as the sole data source.

Synthetic ZIP paths
-------------------
The downstream agents call ``extract_*_from_zip_path(path)`` with the
``zip_path`` field returned by ``load_asr_series``. For Tempest there is
no zip — but to keep call signatures stable, this loader returns
synthetic paths of the form ``tempest://{ticker}/{doc_id}`` and dispatches
to the per-ticker JSON cache when its ``extract_*`` functions get one.
"""
from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import Any

from app.config import ROOT
from app.tools.jpx_industries import lookup as jpx_lookup

log = logging.getLogger(__name__)

DATA_DIR = ROOT / "data" / "tempest"
META_DIR = DATA_DIR / "_meta"

# Section keys used by Tempest's parsed XBRL text payload (see
# /disclosures/{doc_id}). Mapped to the agent-side field names.
SECTION_BUSINESS_DESCRIPTION = "business_overview"   # 事業の内容
SECTION_QUALITATIVE = "md_and_a"                     # 経営者による経営成績等の検討及び分析
SECTION_BUSINESS_RISKS = "business_risks"            # 事業等のリスク (Phase 5)
SECTION_CORPORATE_GOVERNANCE = "corporate_governance"# コーポレート・ガバナンス (Phase 5)

# How much qualitative narrative to keep. The original edinet_loader
# truncated to 8000 chars for the LLM prompt + kept an un-truncated copy
# for the regex post-check. Same conventions here.
QUALITATIVE_PROMPT_BUDGET = 8000


# ----------------------------------------------------------------------------
# Path helpers
# ----------------------------------------------------------------------------
# Match BOTH the raw URL form (`tempest://9432/SXXX`) AND the Windows
# Path()-mangled form (`tempest:\9432\SXXX`). When `analyze_company` wraps a
# zip_path with `pathlib.Path(...)` on Windows, the URL collapses to a
# single-colon backslash form — the regex must accept both so the loader
# survives the round-trip. Linux/Mac never need the backslash branch but
# accepting it is harmless.
TEMPEST_PATH_RE = re.compile(
    r"^tempest:[\\/]{1,2}(?P<ticker>\d{4}[A-Za-z0-9]?)[\\/](?P<doc_id>S\d{3}[A-Za-z0-9]+)$"
)


def _make_synthetic_path(ticker: str, doc_id: str) -> str:
    return f"tempest://{ticker}/{doc_id}"


def _parse_synthetic_path(path: Any) -> tuple[str, str] | None:
    """Decode tempest://{ticker}/{doc_id} → (ticker, doc_id), else None."""
    m = TEMPEST_PATH_RE.match(str(path))
    if not m:
        return None
    return m.group("ticker"), m.group("doc_id")


def _ticker_dir(ticker: str) -> Path:
    return DATA_DIR / ticker


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _ticker_from_folder(folder) -> str:
    """Accept either a 4-digit ticker string or a Path whose name is one.

    Existing edinet code passes ``Path("data/edinet/<code>")``. We honor
    that shape for back-compat — only the folder name matters.
    """
    if isinstance(folder, (str, int)):
        return str(folder)
    return Path(folder).name


# ----------------------------------------------------------------------------
# Disclosure / ASR helpers
# ----------------------------------------------------------------------------
def _get_asrs(ticker: str) -> list[dict]:
    """All ASRs (有価証券報告書, doc_type_code=120) for ticker, newest first."""
    disc = _load_json(_ticker_dir(ticker) / "disclosures.json")
    if not disc:
        return []
    rows = [r for r in disc.get("data", []) if r.get("doc_type_code") == "120"]
    rows.sort(key=lambda r: r.get("submit_datetime") or "", reverse=True)
    return rows


def _get_asr_text(ticker: str, doc_id: str) -> dict | None:
    """Cached /disclosures/{doc_id} payload (or None if not fetched)."""
    return _load_json(_ticker_dir(ticker) / "asr_texts" / f"{doc_id}.json")


def _section_text(asr_text: dict | None, section_key: str) -> str:
    if not asr_text:
        return ""
    for t in asr_text.get("texts", []):
        if t.get("section_key") == section_key:
            return t.get("content") or ""
    return ""


def _get_financials(ticker: str) -> list[dict]:
    """Annual financials (net_sales, op_profit, total_assets...) sorted by fiscal_year asc."""
    fin = _load_json(_ticker_dir(ticker) / "financials.json")
    if not fin:
        return []
    rows = [r for r in fin.get("data", []) if r.get("fiscal_year") is not None]
    rows.sort(key=lambda r: r["fiscal_year"])
    return rows


def _get_line_items(ticker: str) -> list[dict]:
    li = _load_json(_ticker_dir(ticker) / "financials_line_items.json")
    return li.get("data", []) if li else []


def _get_segments(ticker: str) -> list[dict]:
    s = _load_json(_ticker_dir(ticker) / "segments.json")
    return s.get("data", []) if s else []


# ----------------------------------------------------------------------------
# load_asr_series — drop-in replacement
# ----------------------------------------------------------------------------
def load_asr_series(folder) -> list[dict[str, Any]]:
    """Same shape as ``edinet_loader.load_asr_series`` — sorted by filing_date asc.

    Each entry::
        {
          "filing_date": "YYYY-MM-DD",
          "period_end":  "YYYY-MM-DD",
          "fiscal_period": "FY",
          "zip_path": "tempest://{ticker}/{doc_id}",
          "revenue": float,
          "qualitative_text": str (truncated, prompt budget),
          "qualitative_text_full": str (un-truncated, for regex post-checks),
          # Bonus fields used directly by Tempest-aware callers:
          "ticker": str, "doc_id": str, "fiscal_year": int,
          "operating_profit": float | None,
          "business_description": str,
        }
    """
    ticker = _ticker_from_folder(folder)
    fins = _get_financials(ticker)
    if not fins:
        return []
    fin_by_fy = {r["fiscal_year"]: r for r in fins}

    asrs = list(reversed(_get_asrs(ticker)))   # oldest → newest
    out: list[dict[str, Any]] = []
    for asr in asrs:
        submitted = asr.get("submit_datetime") or ""
        if len(submitted) < 10:
            continue
        filing_date = submitted[:10]
        period_end = (asr.get("period_end") or "")[:10]
        if not period_end:
            # Fall back to financials.period_end matched by year of submit
            try:
                fy_guess = int(filing_date[:4]) - 1
            except ValueError:
                continue
            fin = fin_by_fy.get(fy_guess)
            period_end = (fin or {}).get("period_end", "")[:10]
        if not period_end:
            continue

        try:
            fy = int(period_end[:4]) - (0 if int(period_end[5:7]) >= 4 else 1)
        except ValueError:
            continue
        fin = fin_by_fy.get(fy)
        if fin is None:
            # Some ASRs reference a fiscal_year not in the financials cache
            # (e.g. very old filings). Skip — the agents care about the
            # window where both filing + financials co-exist.
            continue

        net_sales = fin.get("net_sales")
        try:
            revenue = float(net_sales) if net_sales is not None else None
        except (TypeError, ValueError):
            revenue = None
        if revenue is None:
            continue

        op = fin.get("operating_profit")
        try:
            op_val = float(op) if op is not None else None
        except (TypeError, ValueError):
            op_val = None

        asr_text = _get_asr_text(ticker, asr["doc_id"])
        qual = _section_text(asr_text, SECTION_QUALITATIVE)
        bus_desc = _section_text(asr_text, SECTION_BUSINESS_DESCRIPTION)

        out.append({
            "filing_date": filing_date,
            "period_end": period_end,
            "fiscal_period": "FY",
            "zip_path": _make_synthetic_path(ticker, asr["doc_id"]),
            "revenue": revenue,
            "qualitative_text": qual[:QUALITATIVE_PROMPT_BUDGET],
            "qualitative_text_full": qual,
            # Bonus context for tempest-aware code paths:
            "ticker": ticker,
            "doc_id": asr["doc_id"],
            "fiscal_year": fy,
            "operating_profit": op_val,
            "business_description": bus_desc,
        })
    out.sort(key=lambda r: r["filing_date"])
    return out


# ----------------------------------------------------------------------------
# Drop-in extract_*_from_zip_path implementations
# ----------------------------------------------------------------------------
def extract_business_description_from_zip_path(zip_path) -> str:
    parsed = _parse_synthetic_path(zip_path)
    if parsed is None:
        return ""
    ticker, doc_id = parsed
    return _section_text(_get_asr_text(ticker, doc_id), SECTION_BUSINESS_DESCRIPTION)


def extract_text_section_from_zip_path(zip_path, section_key: str) -> str:
    """Generic ASR text-section extractor (Phase 5, 2026-05-15).

    `section_key` is one of the SECTION_* constants. Returns the raw text
    (possibly large — risk-factor sections run 5k-30k chars in this universe).
    Empty string when the ZIP path doesn't resolve or the section isn't
    present in the cached ASR text payload.
    """
    parsed = _parse_synthetic_path(zip_path)
    if parsed is None:
        return ""
    ticker, doc_id = parsed
    return _section_text(_get_asr_text(ticker, doc_id), section_key)


def extract_revenue_from_zip_path(zip_path) -> float | None:
    parsed = _parse_synthetic_path(zip_path)
    if parsed is None:
        return None
    ticker, doc_id = parsed
    asr = next((r for r in _get_asrs(ticker) if r["doc_id"] == doc_id), None)
    if asr is None:
        return None
    period_end = (asr.get("period_end") or "")[:10]
    if not period_end:
        return None
    try:
        fy = int(period_end[:4]) - (0 if int(period_end[5:7]) >= 4 else 1)
    except ValueError:
        return None
    fin = next((r for r in _get_financials(ticker) if r["fiscal_year"] == fy), None)
    if fin is None or fin.get("net_sales") is None:
        return None
    try:
        return float(fin["net_sales"])
    except (TypeError, ValueError):
        return None


def extract_operating_profit_from_zip_path(zip_path) -> float | None:
    parsed = _parse_synthetic_path(zip_path)
    if parsed is None:
        return None
    ticker, doc_id = parsed
    asr = next((r for r in _get_asrs(ticker) if r["doc_id"] == doc_id), None)
    if asr is None:
        return None
    period_end = (asr.get("period_end") or "")[:10]
    if not period_end:
        return None
    try:
        fy = int(period_end[:4]) - (0 if int(period_end[5:7]) >= 4 else 1)
    except ValueError:
        return None
    fin = next((r for r in _get_financials(ticker) if r["fiscal_year"] == fy), None)
    if fin is None or fin.get("operating_profit") is None:
        return None
    try:
        return float(fin["operating_profit"])
    except (TypeError, ValueError):
        return None


def extract_revenue_history_from_zip_path(zip_path) -> list[dict]:
    """Multi-year {fiscal_year, period_end, revenue} from cached financials.

    The original EDINET version walked the 5-year-history XBRL block in
    the latest annual report. Tempest already exposes the same series via
    the financials endpoint, so we just reshape it.
    """
    parsed = _parse_synthetic_path(zip_path)
    if parsed is None:
        return []
    ticker, _doc_id = parsed
    out: list[dict] = []
    for fin in _get_financials(ticker):
        ns = fin.get("net_sales")
        if ns is None:
            continue
        try:
            rev = float(ns)
        except (TypeError, ValueError):
            continue
        if rev <= 0:
            continue
        out.append({
            "fiscal_year": fin["fiscal_year"],
            "period_end": (fin.get("period_end") or "")[:10],
            "revenue": rev,
        })
    return out


def detect_revenue_scope(zip_path, picked_value: float) -> dict | None:
    """Tempest doesn't expose alternative-scope candidates — return None.

    The XBRL ambiguity-detection logic relied on scanning every
    revenue-shaped tag in the filing. Tempest's API gives a single
    pre-resolved ``net_sales`` per fiscal year, so there is nothing to
    triangulate. The agent treats None as "no ambiguity to flag."
    """
    return None


# ----------------------------------------------------------------------------
# Balance-sheet extractor — replaces bs_extract.extract_balance_sheet_from_zip_path
# ----------------------------------------------------------------------------
# Map agent-side bs_extract keys → Tempest line_item_key (in priority order).
# The first key that yields a numeric value wins. None marker means "sum all
# matching line_item_keys" (used for interest_bearing_debt).
BS_LINE_ITEM_MAP: dict[str, tuple[str, ...] | None] = {
    "total_assets":              ("total_assets",),
    "tangible_fixed_assets":     ("property_plant_and_equipment_net", "property_plant_and_equipment"),
    "intangible_assets":         ("intangible_assets",),
    "goodwill":                  ("goodwill",),
    "inventory":                 ("inventories", "total_inventories", "merchandise_and_finished_goods"),
    "trade_receivables":         ("notes_and_accounts_receivable_trade", "trade_and_other_receivables"),
    "cash_and_equivalents":      ("cash_and_deposits", "cash_and_cash_equivalents"),
    "equity":                    ("total_equity", "equity_attributable_to_owners_of_parent", "equity", "net_assets"),
    "impairment_loss":           ("impairment_loss", "impairment_losses"),
    "extraordinary_loss_total":  ("extraordinary_loss", "total_extraordinary_losses"),
}
# Special: interest_bearing_debt sums the matching line items. Tempest splits
# IFRS filers' debt into current/non-current; JGAAP filers expose individual
# borrowings/bonds tags. Cover both.
DEBT_KEYS = (
    "interest_bearing_liabilities_current",
    "interest_bearing_liabilities_non_current",
    "short_term_borrowings",
    "current_portion_of_long_term_borrowings",
    "long_term_borrowings",
    "bonds_payable",
    "current_portion_of_bonds",
)


def _value_for_period(line_items: list[dict], fiscal_year: int,
                      candidates: tuple[str, ...]) -> float | None:
    """First matching line-item value for the given fiscal year.

    Filters to consolidated, non-quarterly rows.
    """
    for key in candidates:
        for li in line_items:
            if li.get("line_item_key") != key:
                continue
            if li.get("fiscal_year") != fiscal_year:
                continue
            if li.get("fiscal_quarter") not in (None, 0):
                continue
            if li.get("is_consolidated") is False:
                continue
            try:
                return float(li["value"])
            except (TypeError, ValueError):
                continue
    return None


def _sum_for_period(line_items: list[dict], fiscal_year: int,
                    candidates: tuple[str, ...]) -> float | None:
    """Sum of all matching line items for the given fiscal year, or None if none matched."""
    total = 0.0
    matched = False
    for key in candidates:
        for li in line_items:
            if li.get("line_item_key") != key:
                continue
            if li.get("fiscal_year") != fiscal_year:
                continue
            if li.get("fiscal_quarter") not in (None, 0):
                continue
            if li.get("is_consolidated") is False:
                continue
            try:
                total += float(li["value"])
                matched = True
            except (TypeError, ValueError):
                continue
    return total if matched else None


def extract_balance_sheet_from_zip_path(zip_path) -> dict:
    """Same shape as ``bs_extract.extract_balance_sheet_from_zip_path``.

    Returns ``{items: {key: float}, missing: [...], framework: 'IFRS'|'JGAAP'}``.
    """
    out = {"items": {}, "missing": [], "framework": "JGAAP"}
    parsed = _parse_synthetic_path(zip_path)
    if parsed is None:
        out["missing"] = list(BS_LINE_ITEM_MAP) + ["interest_bearing_debt"]
        return out
    ticker, doc_id = parsed
    asr = next((r for r in _get_asrs(ticker) if r["doc_id"] == doc_id), None)
    if asr is None:
        out["missing"] = list(BS_LINE_ITEM_MAP) + ["interest_bearing_debt"]
        return out
    period_end = (asr.get("period_end") or "")[:10]
    if not period_end:
        out["missing"] = list(BS_LINE_ITEM_MAP) + ["interest_bearing_debt"]
        return out
    try:
        fy = int(period_end[:4]) - (0 if int(period_end[5:7]) >= 4 else 1)
    except ValueError:
        out["missing"] = list(BS_LINE_ITEM_MAP) + ["interest_bearing_debt"]
        return out

    line_items = _get_line_items(ticker)
    fin = next((r for r in _get_financials(ticker) if r["fiscal_year"] == fy), None)

    # Framework hint: IFRS if the matching financials row says so.
    if fin and fin.get("accounting_standard") == "IFRS":
        out["framework"] = "IFRS"

    # Per-item resolution.
    for key, candidates in BS_LINE_ITEM_MAP.items():
        val = _value_for_period(line_items, fy, candidates) if candidates else None
        # Fall back to top-level financials row for the items it exposes
        # (Tempest's /financials has total_assets + equity even when
        # /financials/line-items is sparse — preserve those).
        if val is None and fin:
            if key == "total_assets" and fin.get("total_assets") is not None:
                try:
                    val = float(fin["total_assets"])
                except (TypeError, ValueError):
                    val = None
            elif key == "equity" and fin.get("equity") is not None:
                try:
                    val = float(fin["equity"])
                except (TypeError, ValueError):
                    val = None
        if val is None:
            out["missing"].append(key)
        else:
            out["items"][key] = val

    debt = _sum_for_period(line_items, fy, DEBT_KEYS)
    if debt is None:
        out["missing"].append("interest_bearing_debt")
    else:
        out["items"]["interest_bearing_debt"] = debt
    return out


# ----------------------------------------------------------------------------
# P/L extractor — fronted by app/ingest/pl_extract.py
# ----------------------------------------------------------------------------
# Per-item priority list of Tempest line_item_keys. First match wins. The
# order here mirrors how a Japanese filer's損益計算書 reads top-to-bottom:
# revenue → operating → ordinary/pretax → tax → net income → per-share.
# Margins are derived (not extracted) once revenue + the corresponding
# numerator have both landed.
PL_LINE_ITEM_MAP: dict[str, tuple[str, ...]] = {
    "revenue":                       ("net_sales", "revenue", "total_revenues"),
    # Cost-of-sales + gross profit are exposed for many TOPIX 100 filers and
    # let the agent compute / cite gross-margin compression — one of the
    # strongest forward-outlook signals (per senior 2026-05-10).
    "cost_of_sales":                 ("cost_of_sales", "cost_of_revenue"),
    "gross_profit":                  ("gross_profit",),
    "sga_expenses":                  ("sga_expenses",
                                      "selling_general_and_administrative_expenses"),
    "operating_income":              ("operating_income", "operating_profit"),
    "ordinary_income":               ("income_before_taxes", "ordinary_income", "cf_profit_before_tax"),
    "income_taxes":                  ("income_taxes_total",),
    "net_income":                    ("profit_attributable_to_owners_of_parent",
                                      "profit_loss",
                                      "net_income"),
    "comprehensive_income":          ("comprehensive_income_attributable_to_owners",
                                      "comprehensive_income"),
    "basic_eps":                     ("basic_eps", "earnings_per_share_basic"),
    "rd_expense":                    ("research_and_development_activities_expenses",
                                      "research_and_development_expenses"),
    "depreciation_amortization":     ("depreciation_and_amortization",),
}


def _get_quarterly_financials(ticker: str) -> list[dict]:
    """Cached /financials/quarterly payload (or empty list)."""
    fq = _load_json(_ticker_dir(ticker) / "financials_quarterly.json")
    return fq.get("data", []) if fq else []


def load_quarterly_series(ticker: str) -> list[dict]:
    """Sorted quarterly snapshots usable for YoY comparison.

    Returns one entry per (fiscal_year, fiscal_quarter), sorted by period_end
    ascending. Filters out incomplete rows (missing net_sales OR period_end).
    Keeps the most recent row when duplicates exist for the same (fy, fq) —
    Tempest sometimes carries both 四半期報告書 and its 訂正 (revised) version,
    and the revised numbers are authoritative.

    Each entry includes the fields the agent needs to call the LLM:
      fiscal_year, fiscal_quarter, period_start, period_end,
      filing_date (= disclosed_date), revenue (net_sales), operating_profit,
      net_income (profit), eps (earnings_per_share), total_assets, equity,
      document_type, accounting_standard.
    """
    rows = _get_quarterly_financials(ticker)
    if not rows:
        return []

    # Dedup by (fy, fq) keeping the latest disclosed_date so corrections win.
    by_key: dict[tuple[int, int], dict] = {}
    for r in rows:
        fy = r.get("fiscal_year")
        fq = r.get("fiscal_quarter")
        ns = r.get("net_sales")
        pe = r.get("period_end")
        if fy is None or fq is None or ns is None or not pe:
            continue
        key = (fy, fq)
        existing = by_key.get(key)
        # Prefer revised (訂正) over original — they have the same period_end
        # but different document_type and (sometimes) different numbers.
        if existing is None:
            by_key[key] = r
        else:
            existing_dd = existing.get("disclosed_date") or ""
            new_dd = r.get("disclosed_date") or ""
            if new_dd > existing_dd:
                by_key[key] = r

    out: list[dict] = []
    for r in by_key.values():
        try:
            revenue = float(r["net_sales"])
        except (TypeError, ValueError):
            continue
        op = r.get("operating_profit")
        try:
            op_val = float(op) if op is not None else None
        except (TypeError, ValueError):
            op_val = None
        ni = r.get("profit")
        try:
            ni_val = float(ni) if ni is not None else None
        except (TypeError, ValueError):
            ni_val = None
        eps = r.get("earnings_per_share")
        try:
            eps_val = float(eps) if eps is not None else None
        except (TypeError, ValueError):
            eps_val = None
        ta = r.get("total_assets")
        try:
            ta_val = float(ta) if ta is not None else None
        except (TypeError, ValueError):
            ta_val = None
        eq = r.get("equity")
        try:
            eq_val = float(eq) if eq is not None else None
        except (TypeError, ValueError):
            eq_val = None
        out.append({
            "fiscal_year":      r["fiscal_year"],
            "fiscal_quarter":   r["fiscal_quarter"],
            "period_start":     (r.get("period_start") or "")[:10],
            "period_end":       (r.get("period_end") or "")[:10],
            "filing_date":      (r.get("disclosed_date") or r.get("period_end") or "")[:10],
            "revenue":          revenue,
            "operating_profit": op_val,
            "net_income":       ni_val,
            "eps":              eps_val,
            "total_assets":     ta_val,
            "equity":           eq_val,
            "document_type":    r.get("document_type", ""),
            "accounting_standard": r.get("accounting_standard", ""),
        })
    out.sort(key=lambda r: r["period_end"])
    return out


def make_quarterly_yoy_pairs(series: list[dict]) -> list[tuple[dict, dict]]:
    """Pair each quarter with the same quarter from one year earlier.

    Returns [(prev_quarter, curr_quarter), ...] where prev.fiscal_year ==
    curr.fiscal_year - 1 AND prev.fiscal_quarter == curr.fiscal_quarter.
    Skips quarters with no matching prior-year quarter (e.g., Q3 in 2024+
    after Japan abolished quarterly reports — only annual + semi-annual remain).
    Sorted by curr.period_end ascending.
    """
    by_key = {(r["fiscal_year"], r["fiscal_quarter"]): r for r in series}
    pairs: list[tuple[dict, dict]] = []
    for curr in series:
        prior_key = (curr["fiscal_year"] - 1, curr["fiscal_quarter"])
        prev = by_key.get(prior_key)
        if prev is None:
            continue
        pairs.append((prev, curr))
    pairs.sort(key=lambda p: p[1]["period_end"])
    return pairs


def extract_pl_from_zip_path(zip_path) -> dict:
    """Profit-and-loss panel for a single ASR period.

    Returns ``{items: {key: float}, derived: {margin_key: float}, missing: [...]}``
    where ``items`` carries the raw P/L tags and ``derived`` carries the
    margin ratios computed from them (op_margin_pct, ordinary_margin_pct,
    net_margin_pct). Margins are reported as PERCENT not fraction (i.e.
    12.3 means 12.3 %).

    Empty / missing values are reported in ``missing`` rather than as None,
    so the prompt builder can branch on presence the same way it does for
    the BS panel.
    """
    out: dict = {"items": {}, "derived": {}, "missing": []}
    parsed = _parse_synthetic_path(zip_path)
    if parsed is None:
        out["missing"] = list(PL_LINE_ITEM_MAP)
        return out
    ticker, doc_id = parsed
    asr = next((r for r in _get_asrs(ticker) if r["doc_id"] == doc_id), None)
    if asr is None:
        out["missing"] = list(PL_LINE_ITEM_MAP)
        return out
    period_end = (asr.get("period_end") or "")[:10]
    if not period_end:
        out["missing"] = list(PL_LINE_ITEM_MAP)
        return out
    try:
        fy = int(period_end[:4]) - (0 if int(period_end[5:7]) >= 4 else 1)
    except ValueError:
        out["missing"] = list(PL_LINE_ITEM_MAP)
        return out

    line_items = _get_line_items(ticker)
    fin = next((r for r in _get_financials(ticker) if r["fiscal_year"] == fy), None)

    for key, candidates in PL_LINE_ITEM_MAP.items():
        val = _value_for_period(line_items, fy, candidates)
        # Fall back to /financials top-level row for items it exposes
        # directly. This is the same pattern bs_extract uses for total_assets.
        if val is None and fin:
            if key == "revenue" and fin.get("net_sales") is not None:
                try: val = float(fin["net_sales"])
                except (TypeError, ValueError): val = None
            elif key == "operating_income" and fin.get("operating_profit") is not None:
                try: val = float(fin["operating_profit"])
                except (TypeError, ValueError): val = None
        if val is None:
            out["missing"].append(key)
        else:
            out["items"][key] = val

    # Derived margin ratios — only emit when both numerator and revenue landed
    # AND revenue is positive. Margins on negative or zero revenue are
    # meaningless (some shell-company filings have rev=0 transitions).
    rev = out["items"].get("revenue")
    if rev and rev > 0:
        for num_key, margin_key in (
            ("gross_profit",         "gross_margin_pct"),
            ("operating_income",     "op_margin_pct"),
            ("ordinary_income",      "ordinary_margin_pct"),
            ("net_income",           "net_margin_pct"),
        ):
            num = out["items"].get(num_key)
            if num is not None:
                out["derived"][margin_key] = num / rev * 100.0
    return out


# ----------------------------------------------------------------------------
# Cash-flow extractor — Phase 1 addition (2026-05-15)
# ----------------------------------------------------------------------------
# Mirror of PL_LINE_ITEM_MAP but for cash-flow-statement rows. Tempest's
# /financials/line-items emits these with statement_type == 'CF'. Capex is
# typically reported as a NEGATIVE number in the CF statement (an outflow);
# the FCF derivation below uses (CFO + capex) on that signed convention.
CF_LINE_ITEM_MAP: dict[str, tuple[str, ...]] = {
    "cfo":               ("cash_flows_from_operating",),
    "cfi":               ("cash_flows_from_investing",),
    "cff":               ("cash_flows_from_financing",),
    "capex":             ("capital_expenditures",),
    "net_change_in_cash":("net_change_in_cash",),
}


def extract_cashflow_from_zip_path(zip_path) -> dict:
    """Cash-flow panel for a single ASR period.

    Returns ``{items: {key: float}, derived: {fcf, cfo_to_ni_ratio,
    cfo_positive_despite_loss?}, missing: [...]}`` with the same shape as
    ``extract_pl_from_zip_path``.

    Items: cfo, cfi, cff, capex, net_change_in_cash (absolute values, JPY).
    Derived:
        fcf = cfo - capex
        cfo_to_ni_ratio = cfo / net_income — only when net_income > 0.
            (Ratio's "<0.8 for 2 yrs = bad earnings quality" interpretation
            only makes sense for profitable years; the existing detector
            depends on this convention.)
        cfo_positive_despite_loss = True — when NI < 0 AND CFO > 0.
            STRONG POSITIVE earnings-quality signal: paper losses (likely
            non-cash writedowns / impairments / one-time charges) but the
            business is generating real operating cash. Caught Phase 1
            audit (2026-05-16): this signal was previously dropped because
            the ratio code required ni > 0.

    Pure function. Bad ZIPs return empty items + a missing list of all keys.
    """
    out: dict = {"items": {}, "derived": {}, "missing": []}
    parsed = _parse_synthetic_path(zip_path)
    if parsed is None:
        out["missing"] = list(CF_LINE_ITEM_MAP)
        return out
    ticker, doc_id = parsed
    asr = next((r for r in _get_asrs(ticker) if r["doc_id"] == doc_id), None)
    if asr is None:
        out["missing"] = list(CF_LINE_ITEM_MAP)
        return out
    period_end = (asr.get("period_end") or "")[:10]
    if not period_end:
        out["missing"] = list(CF_LINE_ITEM_MAP)
        return out
    try:
        fy = int(period_end[:4]) - (0 if int(period_end[5:7]) >= 4 else 1)
    except ValueError:
        out["missing"] = list(CF_LINE_ITEM_MAP)
        return out

    line_items = _get_line_items(ticker)

    for key, candidates in CF_LINE_ITEM_MAP.items():
        val = _value_for_period(line_items, fy, candidates)
        if val is None:
            out["missing"].append(key)
        else:
            out["items"][key] = val

    cfo = out["items"].get("cfo")
    capex = out["items"].get("capex")
    if cfo is not None and capex is not None:
        # Tempest normalises both CFO and capex to positive magnitudes
        # (unlike the raw XBRL where capex is typically signed-negative as
        # an outflow). FCF = CFO − capex on this convention.
        out["derived"]["fcf"] = cfo - capex

    # CFO-to-NI ratio — earnings-quality signal. Read NI from the same
    # fiscal_year's /financials top-level row. Tempest exposes parent-
    # attributable profit under the field `profit` (verified 2026-05-15
    # against NTT, fields seen: net_sales, operating_profit, ordinary_profit,
    # profit). Fall back to the line-items extractor for filers that don't
    # populate the top-level row.
    fin = next((r for r in _get_financials(ticker) if r["fiscal_year"] == fy), None)
    ni: float | None = None
    if fin is not None:
        ni_raw = fin.get("profit")
        try:
            ni = float(ni_raw) if ni_raw is not None else None
        except (TypeError, ValueError):
            ni = None
    if ni is None:
        ni = _value_for_period(
            line_items, fy,
            ("profit_attributable_to_owners_of_parent", "profit_loss", "net_income"),
        )
    if cfo is not None and ni is not None:
        out["items"]["net_income_for_ratio"] = ni
        if ni > 0:
            # Standard earnings-quality ratio (well-defined when profitable)
            out["derived"]["cfo_to_ni_ratio"] = cfo / ni
        elif ni < 0 and cfo > 0:
            # Loss-making but positive operating cash flow — strong positive
            # signal (paper loss likely non-cash; business generates cash).
            # Surfaced as a structured boolean rather than a numeric ratio
            # because the ratio's normal "<0.8 = bad" interpretation flips
            # when NI is negative and would corrupt the existing detector.
            out["derived"]["cfo_positive_despite_loss"] = True
    return out


# ----------------------------------------------------------------------------
# Segment extractor — replaces segment_extract.extract_segments
# ----------------------------------------------------------------------------
# XBRL segment-name fragments that flag a meta / reconciling / totals row
# rather than a real reportable segment. Matched as substrings on the raw
# segment_name returned by the API (case-sensitive — these are XBRL local-
# names, not display labels).
SEGMENT_META_FRAGMENTS = (
    "Reconciling",
    "TotalOfReportableSegments",
    "OperatingSegmentsNotIncludedInReportableSegments",
    "Elimination",
    "Adjustment",
    "CorporateExpense",
)


def _is_meta_segment(name: str) -> bool:
    if not name:
        return True
    return any(frag in name for frag in SEGMENT_META_FRAGMENTS)


def _segments_for_period(ticker: str, fiscal_year: int,
                         dimension: str = "business",
                         line_item_key: str = "net_sales") -> list[dict]:
    """Return [{segment_name, value}] for the requested fy/dimension.

    Filters out XBRL meta-segments (Reconciling, Eliminations, totals, etc.)
    so the agent only sees real reportable segments.
    """
    rows = _get_segments(ticker)
    out: list[dict] = []
    seen = set()
    for r in rows:
        if r.get("fiscal_year") != fiscal_year:
            continue
        if r.get("segment_dimension") != dimension:
            continue
        if r.get("line_item_key") != line_item_key:
            continue
        if r.get("fiscal_quarter") not in (None, 0):
            continue
        name = r.get("segment_name")
        if _is_meta_segment(name) or name in seen:
            continue
        try:
            val = float(r["value"])
        except (TypeError, ValueError):
            continue
        out.append({"segment_name": name, "value": val})
        seen.add(name)
    return out


def extract_segments(zip_path, period: str | None = None):
    """Same shape as ``segment_extract.extract_segments``.

    Returns a pandas DataFrame with columns ``[segment_name, segment_name_ja,
    revenue, ratio]`` — column names match the original
    ``app.ingest.segment_extract.extract_segments`` contract that
    ``quiet_change._segment_yoy`` reads (it expects a `revenue` column, not
    `value`). Bug fix 2026-05-10: the post-switch column was named `value`
    and crashed downstream with KeyError 'revenue' on the first ticker that
    actually had segment rows.

    Parameters
    ----------
    period : ``"prior"`` (read the restated prior-year comparatives that the
        current filing republishes) is not directly supported by the Tempest
        API in the same form — when called with period="prior", we resolve
        the prior fiscal year from the current ASR's period_end and pull
        that year's segment rows directly from /segments. This is a
        slightly weaker analogue of "as restated by the filer" but is
        accurate as long as no major restatement has occurred.
    """
    import pandas as pd
    cols = ["segment_name", "segment_name_ja", "revenue", "ratio"]
    parsed = _parse_synthetic_path(zip_path)
    if parsed is None:
        return pd.DataFrame(columns=cols)
    ticker, doc_id = parsed
    asr = next((r for r in _get_asrs(ticker) if r["doc_id"] == doc_id), None)
    if asr is None:
        return pd.DataFrame(columns=cols)
    pe = (asr.get("period_end") or "")[:10]
    if not pe:
        return pd.DataFrame(columns=cols)
    try:
        fy = int(pe[:4]) - (0 if int(pe[5:7]) >= 4 else 1)
    except ValueError:
        return pd.DataFrame(columns=cols)
    if period == "prior":
        fy -= 1
    rows = _segments_for_period(ticker, fy, dimension="business",
                                line_item_key="net_sales")
    if not rows:
        return pd.DataFrame(columns=cols)
    # Map Tempest's raw `value` field onto the `revenue` column the consumer
    # expects, and add an empty `segment_name_ja` placeholder (Tempest
    # doesn't expose a JA label per segment; the agent's UI tolerates an
    # empty string here).
    out_rows = [
        {"segment_name": r["segment_name"],
         "segment_name_ja": "",
         "revenue": r["value"]}
        for r in rows
    ]
    df = pd.DataFrame(out_rows)
    total = float(df["revenue"].sum()) if len(df) else 0.0
    df["ratio"] = (df["revenue"] / total) if total > 0 else 0.0
    return df


# ----------------------------------------------------------------------------
# Universe builder — replaces similar_company.build_universe
# ----------------------------------------------------------------------------
def _scan_universe_from_disk() -> list[dict]:
    """Fallback: derive the universe by scanning data/tempest/<ticker>/company.json.

    Used when ``_meta/universe.json`` is missing (e.g. fetcher was run with
    --tickers only). Less authoritative than the meta file because it
    re-derives is_topix100 from each company.json, but produces a usable
    universe for testing.
    """
    if not DATA_DIR.is_dir():
        return []
    rows: list[dict] = []
    for sub in DATA_DIR.iterdir():
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        comp = _load_json(sub / "company.json")
        if not comp:
            continue
        comp = dict(comp)   # shallow copy so we don't mutate cached file
        comp.setdefault("ticker", sub.name)
        comp["is_topix100"] = comp.get("scale_category") in ("TOPIX Core30", "TOPIX Large70")
        rows.append(comp)
    return rows


def build_universe(min_year: int = 2020,
                   sector_code: str = "5250") -> list[dict[str, Any]]:
    """Drop-in replacement for ``similar_company.build_universe``.

    Walks ``data/tempest/_meta/universe.json`` (populated by
    fetch_tempest.py), keeps tickers whose JPX 33業種 code matches
    ``sector_code`` AND that have parsed text (TOPIX 100 only, per
    Tempest staging). Each entry has the same fields the agent expects.
    """
    universe = _load_json(META_DIR / "universe.json")
    if universe and universe.get("rows"):
        rows = universe["rows"]
    else:
        log.info("tempest universe meta missing — scanning disk")
        rows = _scan_universe_from_disk()
    if not rows:
        log.warning("tempest universe not found — run fetch_tempest.py first")
        return []

    out: list[dict] = []
    for row in rows:
        ticker = row["ticker"]
        # Tempest restriction: only TOPIX 100 has parsed text/segments.
        if not row.get("is_topix100"):
            continue
        # Sector match — fall back to API-provided code, then jpx_lookup.
        api_code = row.get("sector_33_code")
        if api_code != sector_code:
            rec = jpx_lookup(ticker)
            if rec is None or rec.code33 != sector_code:
                continue
        series = [s for s in load_asr_series(ticker)
                  if int(s["period_end"][:4]) >= min_year]
        if not series:
            continue
        latest = series[-1]
        desc = latest.get("business_description") or ""
        if not desc or len(desc) < 100:
            log.warning("similar_company (tempest): %s has no usable 事業の内容 — skipping", ticker)
            continue
        revenue_history = [
            {"fiscal_year": int(s["period_end"][:4]),
             "period_end": s["period_end"],
             "revenue": s["revenue"]}
            for s in series
        ]
        out.append({
            "code": ticker,
            "name": row.get("company_name") or ticker,
            "latest_revenue": latest["revenue"],
            "latest_period_end": latest["period_end"],
            "latest_filing_date": latest["filing_date"],
            "latest_zip_path": latest["zip_path"],
            "business_description": desc,
            "revenue_history": revenue_history,
        })
    return out


def count_per_sector(min_year: int = 2020) -> dict[str, int]:
    """Per-sector universe counts for the UI dropdown — Tempest universe view.

    The agent uses this to populate the sector picker. Counts only TOPIX
    100 tickers since those are the only ones the Tempest text/segment
    pipeline supports.
    """
    universe = _load_json(META_DIR / "universe.json")
    rows = universe["rows"] if (universe and universe.get("rows")) else _scan_universe_from_disk()
    if not rows:
        return {}
    counts: dict[str, int] = {}
    min_year_str = str(min_year)
    for row in rows:
        if not row.get("is_topix100"):
            continue
        ticker = row["ticker"]
        # Only count if we have usable financials covering min_year+.
        fins = _get_financials(ticker)
        if not any(str(f.get("fiscal_year", "")) >= min_year_str for f in fins):
            continue
        sec = row.get("sector_33_code")
        if not sec:
            rec = jpx_lookup(ticker)
            sec = rec.code33 if rec else None
        if sec:
            counts[sec] = counts.get(sec, 0) + 1
    return counts


# ----------------------------------------------------------------------------
# YoY pair / quiet_change loader
# ----------------------------------------------------------------------------
def load_company_from_edinet(folder, cutoff_date=None,
                             filing_type_filter=None) -> dict | None:
    """Drop-in replacement for ``edinet_loader.load_company_from_edinet``.

    Builds a YoY pair from the latest two ASRs (annual reports) on or
    before ``cutoff_date``. Returns the same shape the original function
    returned, populated from cached Tempest data.
    """
    ticker = _ticker_from_folder(folder)
    series = load_asr_series(ticker)
    if cutoff_date is not None:
        cutoff_iso = cutoff_date.isoformat() if hasattr(cutoff_date, "isoformat") else str(cutoff_date)
        series = [s for s in series if s["filing_date"] <= cutoff_iso]
    if len(series) < 2:
        log.warning("tempest: %s has %d ASRs (need >=2) — skipping", ticker, len(series))
        return None

    curr = series[-1]
    prev = series[-2]

    # Segment ratios for current + prior fiscal years, business dimension.
    curr_segs = _segments_for_period(ticker, curr["fiscal_year"], "business", "net_sales")
    prev_segs = _segments_for_period(ticker, prev["fiscal_year"], "business", "net_sales")

    def _ratios(rows: list[dict]) -> list[dict]:
        total = sum(r["value"] for r in rows) or 0.0
        if total <= 0:
            return []
        return [{"segment_name": r["segment_name"], "ratio": r["value"] / total}
                for r in rows]

    # Multi-year segment history per segment (latest 5 fiscal years available).
    seg_history: dict[str, list[float]] = {}
    fy_window = sorted({r["fiscal_year"] for r in _get_segments(ticker)})[-5:]
    for fy in fy_window:
        rows = _segments_for_period(ticker, fy, "business", "net_sales")
        total = sum(r["value"] for r in rows) or 0.0
        if total <= 0:
            continue
        for r in rows:
            seg_history.setdefault(r["segment_name"], []).append(r["value"] / total)

    # Revenue proxy series for the agent's fallback when segments are sparse.
    seg_history.setdefault(
        "_revenue_proxy",
        [s["revenue"] for s in series],
    )

    return {
        "code": ticker,
        "name": ticker,   # caller (loader.py) overwrites with config name
        "announce_date": curr["filing_date"],
        "prev_text": prev["qualitative_text"][:8000],
        "curr_text": curr["qualitative_text"][:8000],
        "prev_raw_text": prev["qualitative_text_full"][:16000],
        "curr_raw_text": curr["qualitative_text_full"][:16000],
        "segments_prev": _ratios(prev_segs),
        "segments_curr": _ratios(curr_segs),
        "segment_history": seg_history,
        "business_description_ja": curr.get("business_description", ""),
        "source": "tempest",
        "filings_count": len(series),
        "revenue_points": len(series),
        "filing_type": "edinet_asr",
        "fiscal_period": "FY",
        "prev_filing": {
            "filing_date": prev["filing_date"],
            "period_end": prev["period_end"],
            "fiscal_period": "FY",
            "filing_type": "edinet_asr",
            "zip_path": prev["zip_path"],
            "doc_id": prev["doc_id"],
        },
        "curr_filing": {
            "filing_date": curr["filing_date"],
            "period_end": curr["period_end"],
            "fiscal_period": "FY",
            "filing_type": "edinet_asr",
            "zip_path": curr["zip_path"],
            "doc_id": curr["doc_id"],
        },
    }


def load_all_edinet(data_dir=None, cutoff_date=None) -> dict[str, dict[str, Any]]:
    """Drop-in replacement for ``edinet_loader.load_all_edinet``.

    Iterates the Tempest universe (TOPIX 100 only) instead of
    ``data_dir / 'edinet' / *``. The ``data_dir`` argument is accepted for
    signature compatibility but ignored.
    """
    universe = _load_json(META_DIR / "universe.json")
    rows = universe["rows"] if (universe and universe.get("rows")) else _scan_universe_from_disk()
    if not rows:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.get("is_topix100"):
            continue
        fund = load_company_from_edinet(row["ticker"], cutoff_date=cutoff_date)
        if fund is not None:
            out[fund["code"]] = fund
    return out
