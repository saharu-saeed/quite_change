"""EDINET manual-download loader.

Reads ZIPs you manually downloaded from https://disclosure2.edinet-fsa.go.jp/
and placed under:

    data/edinet/<code>/
      ├── 2024Q2.zip
      ├── 2024Q3.zip
      └── 2024Q4.zip

Each ZIP is a standard EDINET XBRL package (PublicDoc/ layout).
Needs at least 2 ZIPs per company (prev + curr pair).

Returns the same shape as tdnet_loader so loader.py can use it transparently.
"""
from __future__ import annotations
import logging
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from lxml import etree

from app.ingest.filing_meta import (
    extract_edinet_filing_meta,
    find_yoy_pair,
    get_fy_disagreement_counts,
    reset_fy_disagreement_counters,
)

log = logging.getLogger(__name__)

EDINET_DIR_NAME = "edinet"

# Qualitative text tags (EDINET namespace-agnostic via local-name())
QUALITATIVE_TAGS = (
    # MD&A narrative — what we actually want (prioritised first)
    "ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock",
    "OperatingResultsTextBlock",
    "OverviewOfBusinessResultsTextBlock",
    "BusinessResultsTextBlock",
    # Broader blocks — OK if they don't start with a financial summary table
    "BusinessResultsOfGroupTextBlock",
)

# Revenue tags in priority order. The extractor returns the first tag that
# yields a non-zero consolidated value — so ordering matters.
#
#   1. *SummaryOfBusinessResults — the canonical five-year-history rows that
#      every Japanese issuer is required to report (jpcrp_cor namespace).
#      Always the consolidated number; safe to trust across US-GAAP, IFRS,
#      and Japanese-GAAP filers.
#   2. *IFRS — issuers reporting under IFRS (jpigp_cor namespace): airlines,
#      Rakuten, Olympus, and most globally-oriented filers post-2016.
#   3. Bare GAAP (jppfs_cor namespace) — legacy fallback for domestic
#      Japanese-GAAP issuers whose Summary rows somehow failed to parse.
REVENUE_TAGS = (
    # (1) 5-year-history / regulator-required summary tags. These are the
    #     canonical figures companies quote in IR materials and that news
    #     reports use. ALWAYS prefer these — they include all revenue scopes
    #     the company itself considers headline (e.g., for Sony this is
    #     sales + financial-services revenue, not pure operating sales).
    "NetSalesSummaryOfBusinessResults",
    "RevenuesUSGAAPSummaryOfBusinessResults",
    "RevenueIFRSSummaryOfBusinessResults",
    "NetSalesIFRSSummaryOfBusinessResults",
    "OrdinaryRevenuesSummaryOfBusinessResults",
    # Sector-specific top-line tags from the 5-year-history table.
    #   OrdinaryIncomeSummaryOfBusinessResults — 経常収益, used by BANKS as
    #     the top-line equivalent of revenue. Distinct from the bare
    #     `OrdinaryIncome` tag for IT/manufacturing filers, which is 経常利益
    #     (a profit line). The summary suffix anchors this to the
    #     5-year-history table where it always means top-line for banks.
    #   OperatingRevenue1SummaryOfBusinessResults — 営業収益, used by
    #     transport (rail / marine / air), insurance, warehousing, and
    #     other regulated industries that don't post NetSales.
    "OrdinaryIncomeSummaryOfBusinessResults",
    "OperatingRevenue1SummaryOfBusinessResults",
    # KeyFinancialData variants — modern IFRS filers (Sony, etc.) use these
    # for the same 5-year-history disclosure. Prioritised at top so the
    # broader scope wins for conglomerates with financial-services arms.
    "SalesAndFinancialServicesRevenueIFRSKeyFinancialData",
    "SalesAndOperatingRevenueIFRSKeyFinancialData",
    "RevenueIFRSKeyFinancialData",
    "NetSalesIFRSKeyFinancialData",
    "OperatingRevenuesIFRSKeyFinancialData",
    # (2) IFRS income-statement tags (used when no 5-yr summary tag exists)
    "RevenueIFRS",
    "NetSalesIFRS",
    "SalesIFRS",
    "OperatingRevenuesIFRS",
    # (3) Bare GAAP tags (legacy / domestic-GAAP filers)
    "NetSales",
    "Revenue",
    "OrdinaryRevenues",
    "OperatingRevenues",
    # Bare income-statement equivalent for transport / insurance.
    # Safe to add at the end — IT/manufacturing filers don't emit this tag,
    # so it only fires for sectors that actually post 営業収益.
    "OperatingRevenue1",
)


def _is_financial_table(text: str) -> bool:
    """Detect financial summary tables — not useful narrative for the LLM."""
    head = text[:400]
    return "連結経営指標等" in head or ("回次" in head and "百万円" in head)


def _skip_toc(text: str) -> str:
    """Skip table-of-contents boilerplate; return the actual narrative portion."""
    markers = [
        "経営成績に関する説明", "当期の経営成績", "業績の概要",
        "事業の経過及び成果", "経営者による財政状態", "当社グループの経営成績",
    ]
    for marker in markers:
        idx = text.find(marker)
        if idx > 200:
            return text[idx:]
    # fallback: skip first 20% if no marker found (likely TOC)
    skip = min(2000, len(text) // 5)
    return text[skip:]


def _strip_html(s: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<style\b[^>]*>.*?</style>",  " ", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.DOTALL)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;|&#160;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _extract_qualitative(zf: zipfile.ZipFile) -> str:
    """Try EDINET XBRL tags first, then fall back to qualitative.htm."""
    htm_files = [n for n in zf.namelist()
                 if n.lower().endswith((".htm", ".html", ".xbrl"))]
    # prefer PublicDoc files
    htm_files.sort(key=lambda n: (0 if "PublicDoc" in n else 1))

    for name in htm_files:
        try:
            data = zf.read(name)
            root = etree.fromstring(data, parser=etree.XMLParser(recover=True, huge_tree=True, ns_clean=True))
        except Exception:
            continue
        if root is None:
            continue
        for tag in QUALITATIVE_TAGS:
            nodes = root.xpath(f"//*[local-name()='{tag}']")
            if nodes:
                text = _strip_html("".join(nodes[0].itertext()))
                # Skip if it's a financial summary table (numbers, not narrative)
                if len(text) > 200 and not _is_financial_table(text):
                    return text

    # qualitative.htm fallback (TDnet-style file sometimes bundled)
    for name in zf.namelist():
        if "qualitative" in name.lower():
            raw = zf.read(name).decode("utf-8", errors="replace")
            text = _strip_html(raw)
            if len(text) > 200:
                return text

    return ""


def extract_business_description_from_zip_path(zip_path) -> str:
    """Public entry: open a ZIP and return its 事業の内容 narrative, or ''."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return _extract_business_description(zf)
    except (zipfile.BadZipFile, FileNotFoundError):
        return ""


def load_asr_series(folder: Path) -> list[dict[str, Any]]:
    """Return every annual securities report (有価証券報告書) under
    data/edinet/<code>/, sorted by filing_date ascending.

    Each entry: {filing_date, period_end, fiscal_period, zip_path,
    revenue, qualitative_text}. Used by the multi-year quiet_change view.
    """
    code = folder.name
    if not re.match(r"^\d{4}$", code):
        return []
    out: list[dict[str, Any]] = []
    for z in sorted(folder.glob("*.zip")):
        meta = extract_edinet_filing_meta(z)
        if meta is None or meta.filing_type != "edinet_asr":
            continue
        try:
            with zipfile.ZipFile(z) as zf:
                rev = _extract_revenue(zf)
                qual = _extract_qualitative(zf)
        except zipfile.BadZipFile:
            continue
        if rev is None:
            continue
        out.append({
            "filing_date": meta.filing_date.isoformat(),
            "period_end": meta.period_end.isoformat(),
            "fiscal_period": meta.fiscal_period,
            "zip_path": str(z),
            "revenue": float(rev),
            # Truncated copy for the LLM prompt (token budget). Unified at
            # 8000 chars so both code paths (single-pair `analyze_company`
            # and multi-year `analyze_company_multi_year`) hand the same
            # window to the model.
            "qualitative_text": qual[:8000],
            # Un-truncated copy for the regex post-check. Regex is cheap;
            # truncating the source meant the post-check missed trigger
            # tokens that fell past the LLM-budget cutoff (real bug found
            # on NTT's divestiture mention sitting at chars 6000-8000).
            "qualitative_text_full": qual,
        })
    return out


def extract_revenue_from_zip_path(zip_path) -> float | None:
    """Public entry: open a ZIP and return its top-level revenue, or None."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return _extract_revenue(zf)
    except (zipfile.BadZipFile, FileNotFoundError):
        return None


# Operating-profit tags. Same priority logic as REVENUE_TAGS:
#   (1) 5-year-history / SummaryOfBusinessResults variants — canonical figure
#   (2) IFRS income-statement tag
#   (3) Bare GAAP fallbacks
# Most filers expose at least one of these. Used by the Quiet Change agent to
# detect profit-up / stock-down divergence; not used by Similar Company.
OPERATING_PROFIT_TAGS = (
    "OperatingProfitLossIFRSSummaryOfBusinessResults",
    "OperatingIncomeSummaryOfBusinessResults",
    "OperatingProfitLossIFRSKeyFinancialData",
    "OperatingIncomeKeyFinancialData",
    "OperatingProfitLossIFRS",
    "OperatingIncome",
)


def _extract_operating_profit(zf: zipfile.ZipFile) -> float | None:
    """Pull the consolidated operating-profit/income figure from XBRL.

    Mirrors `_extract_revenue` but drops the val>0 guard — operating income
    can legitimately be negative (loss-making years). Excludes prior-year /
    forecast / dimensioned contexts the same way revenue does.
    """
    xbrl_files = [n for n in zf.namelist()
                  if n.lower().endswith((".xbrl", ".htm"))
                  and "PublicDoc" in n]
    for name in xbrl_files:
        try:
            data = zf.read(name)
            root = etree.fromstring(data, parser=etree.XMLParser(recover=True, huge_tree=True, ns_clean=True))
        except Exception:
            continue
        if root is None:
            continue
        for tag in OPERATING_PROFIT_TAGS:
            nodes = root.xpath(f"//*[local-name()='{tag}']")
            for node in nodes:
                ctx = node.get("contextRef") or ""
                if ("Prior" in ctx or "Forecast" in ctx
                        or "Segment" in ctx or "Member" in ctx):
                    continue
                txt = (node.text or "").strip().replace(",", "")
                if not txt or txt == "-":
                    continue
                try:
                    val = float(txt)
                except ValueError:
                    continue
                scale = node.get("scale")
                if scale:
                    try:
                        val *= 10 ** int(scale)
                    except ValueError:
                        pass
                return val
    return None


def extract_operating_profit_from_zip_path(zip_path) -> float | None:
    """Public entry: open a ZIP and return consolidated operating profit, or None."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return _extract_operating_profit(zf)
    except (zipfile.BadZipFile, FileNotFoundError):
        return None


# Human-readable scope hints, shown to the LLM and the user when a filing
# discloses multiple revenue scopes. Mapped from XBRL tag-name fragments to
# a short "what this number includes" description (EN + JA).
TAG_SCOPE_HINTS: tuple[tuple[str, str, str], ...] = (
    # (tag-name fragment, EN scope description, JA scope description)
    ("SalesAndFinancialServicesRevenue",
     "operating sales + financial-services revenue (insurance premiums, banking, etc.) — the broader 'total revenue' figure the company reports in IR materials",
     "売上高＋金融ビジネス収入(保険料、銀行業務等)を含む広義の売上高(IR資料で開示される総収益)"),
    ("SalesAndOperatingRevenue",
     "operating sales + other operating revenue",
     "売上高＋その他営業収益"),
    ("FinancialServicesRevenue",
     "financial-services revenue only (insurance premiums, banking interest)",
     "金融ビジネス収入のみ(保険料、銀行業務利息)"),
    ("OrdinaryRevenue",
     "ordinary revenues (banking / insurance industry standard)",
     "経常収益(銀行・保険業の標準)"),
    ("OperatingRevenue",
     "operating revenues (telecom / utility industry standard)",
     "営業収益(通信・公益事業の標準)"),
    ("RevenueFromContractsWithCustomers",
     "revenue under IFRS 15 (contract-based)",
     "顧客との契約から生じる収益(IFRS 15)"),
    ("RevenueFromExternalCustomers",
     "external-customer revenue (excludes intersegment)",
     "外部顧客への売上高(セグメント間取引を除く)"),
    ("NetSales",
     "pure operating sales (excludes financial-services revenue if separately reported)",
     "純売上高(金融ビジネス収入が別掲の場合は除外)"),
    ("Revenue",
     "consolidated revenue",
     "連結売上高"),
)


def _scope_for_tag(tag: str) -> tuple[str, str]:
    """Return (en_description, ja_description) for a revenue tag.
    Uses the most specific match — checks the more discriminating fragments first."""
    for fragment, en, ja in TAG_SCOPE_HINTS:
        if fragment in tag:
            return en, ja
    return "consolidated revenue (scope unspecified)", "連結売上(範囲不明)"


_REVENUE_NAME_KEYWORDS = ("NetSales", "Revenue", "Sales", "OrdinaryRevenues", "OperatingRevenues")
_REVENUE_NAME_EXCLUDES = (
    "Cost", "Loss", "Profit", "Tax", "PerShare", "Income", "Margin", "Ratio",
    "Forecast", "Estimate", "Previous", "Prior",
    "Intersegment", "Adjustment", "Insurance", "Investment", "Proceeds",
    "OtherRevenue",
)


def extract_revenue_history_from_zip_path(zip_path) -> list[dict]:
    """Pull the full multi-year revenue history from this filing's
    Summary-of-Business-Results / KeyFinancialData table.

    Every Japanese annual securities report includes a 5-year history
    (主要な経営指標等の推移) where each row of the headline revenue tag
    has its own ``contextRef`` pointing to a different fiscal year. For
    a company that has restated prior-year comparatives (e.g. IFRS 17
    adoption), this table contains the restated values — the same
    figures the company quotes in IR materials and that analysts use.

    Returns a list of {fiscal_year, period_end, revenue} dicts sorted
    by year ascending. Empty list if no multi-year tag is found.

    Walks REVENUE_TAGS in priority order; the first tag that yields ≥2
    distinct years wins.
    """
    out: list[dict] = []
    try:
        with zipfile.ZipFile(zip_path) as zf:
            xbrl_files = [n for n in zf.namelist()
                          if n.lower().endswith(".xbrl")
                          and "PublicDoc" in n]
            for name in xbrl_files:
                try:
                    root = etree.fromstring(
                        zf.read(name),
                        parser=etree.XMLParser(recover=True, huge_tree=True, ns_clean=True),
                    )
                except Exception:
                    continue
                if root is None:
                    continue
                contexts = {c.get("id"): c for c in root.xpath("//*[local-name()='context']")}
                # Pre-compute (cid → period_end) so we can group facts by year.
                ctx_period_end: dict[str, str] = {}
                for cid, c in contexts.items():
                    ends = c.xpath(".//*[local-name()='endDate']")
                    if ends:
                        txt = (ends[0].text or "").strip()
                        if len(txt) >= 10:
                            ctx_period_end[cid] = txt[:10]   # YYYY-MM-DD

                for tag in REVENUE_TAGS:
                    by_year: dict[int, tuple[str, float]] = {}   # year → (period_end, value)
                    for el in root.xpath(f"//*[local-name()='{tag}']"):
                        cid = el.get("contextRef") or ""
                        if "Forecast" in cid:
                            continue
                        ctx = contexts.get(cid)
                        if ctx is None:
                            continue
                        # Skip dimensioned facts (segment/member rows).
                        if ctx.xpath(".//*[local-name()='explicitMember']"):
                            continue
                        pe = ctx_period_end.get(cid)
                        if not pe:
                            continue
                        try:
                            yr = int(pe[:4])
                        except ValueError:
                            continue
                        txt = (el.text or "").strip().replace(",", "")
                        if not txt or txt == "-":
                            continue
                        try:
                            val = float(txt)
                        except ValueError:
                            continue
                        scale = el.get("scale")
                        if scale:
                            try:
                                val *= 10 ** int(scale)
                            except ValueError:
                                pass
                        if val <= 0:
                            continue
                        # If multiple facts for same year (rare), keep the larger.
                        prev = by_year.get(yr)
                        if prev is None or val > prev[1]:
                            by_year[yr] = (pe, val)
                    if len(by_year) >= 2:
                        return [
                            {"fiscal_year": yr, "period_end": pe, "revenue": v}
                            for yr, (pe, v) in sorted(by_year.items())
                        ]
            return out
    except (zipfile.BadZipFile, FileNotFoundError):
        return out


def detect_revenue_scope(zip_path, picked_value: float) -> dict | None:
    """Detect whether the filing discloses multiple distinct revenue scopes.

    Returns None when there's no meaningful ambiguity (≤1 distinct revenue
    figure, or all candidates agree within 1%). Otherwise returns a dict:

        {
          "ambiguous": True,
          "picked_value": float,
          "picked_tag": str,
          "picked_scope_en": str,        # human-readable scope description
          "picked_scope_ja": str,
          "alternatives": [
              {"tag": str, "value": float, "diff_pct": float,
               "scope_en": str, "scope_ja": str},
              ...
          ],
        }

    Used by the agent to pass scope context into the LLM prompt so the
    explanation can name BOTH figures and tell the reader which one was used.
    """
    cands = extract_all_revenue_candidates_from_zip_path(zip_path)
    if len(cands) < 2 or picked_value <= 0:
        return None

    # Find the candidate that matches picked_value exactly (within 0.1% rounding).
    picked_cand = None
    for c in cands:
        if abs(c["value"] - picked_value) / picked_value * 100 < 0.1:
            picked_cand = c
            break
    if picked_cand is None:
        return None

    # Collect candidates that look like alternative total-revenue scopes.
    # Filtering rules (all must hold):
    #   - Different from picked value by ≥1% (real scope difference, not rounding)
    #   - At least 50% as large as the picked value (rejects sub-component tags
    #     like financial-services-only sub-totals — those aren't an alternative
    #     "total revenue" reading, just a piece of one)
    #   - Tag name doesn't look like a sub-component breakdown (Goods/Services/
    #     Domestic/Overseas/Wholesale/Retail — these are slices BY product type
    #     or geography, not alternative scope definitions of total revenue)
    #   - Distinct value (don't list the same number twice under different tags)
    SUBCOMPONENT_HINTS = (
        "OfGoods", "OfService", "OfRendering", "Domestic", "Overseas",
        "Wholesale", "Retail", "ByProduct", "ByGeography",
    )
    seen_vals: list[float] = []
    alternatives: list[dict] = []
    for c in cands:
        if c["tag"] == picked_cand["tag"]:
            continue
        diff_pct = (c["value"] - picked_value) / picked_value * 100
        if abs(diff_pct) < 1.0:
            continue
        if c["value"] < picked_value * 0.5:
            continue   # sub-component, not an alternative total
        if any(h in c["tag"] for h in SUBCOMPONENT_HINTS):
            continue   # named like a slice (goods/services/domestic/overseas) — skip
        if any(abs(c["value"] - v) / v * 100 < 0.1 for v in seen_vals):
            continue
        seen_vals.append(c["value"])
        alt_en, alt_ja = _scope_for_tag(c["tag"])
        alternatives.append({
            "tag": c["tag"],
            "value": c["value"],
            "diff_pct": diff_pct,
            "scope_en": alt_en,
            "scope_ja": alt_ja,
        })

    if not alternatives:
        return None

    picked_en, picked_ja = _scope_for_tag(picked_cand["tag"])
    return {
        "ambiguous": True,
        "picked_value": picked_value,
        "picked_tag": picked_cand["tag"],
        "picked_scope_en": picked_en,
        "picked_scope_ja": picked_ja,
        "alternatives": alternatives,
    }


def extract_all_revenue_candidates_from_zip_path(zip_path) -> list[dict]:
    """Diagnostic: scan the XBRL for EVERY revenue-shaped tag at the
    consolidated (non-segment, non-prior, non-forecast) level. Used by the
    verification harness to triangulate the agent's chosen value against
    every other revenue tag the filer disclosed.

    Each entry: {tag, value, scale, decimals, family} where family is one of:
      'summary'   — 5-year-history rows (SummaryOfBusinessResults / KeyFinancialData)
      'ifrs'      — IFRS-namespace tags (no summary marker)
      'gaap'      — bare GAAP tags
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            xbrl_files = [n for n in zf.namelist()
                          if n.lower().endswith(".xbrl")
                          and "PublicDoc" in n]
            seen: dict[str, dict] = {}
            for name in xbrl_files:
                try:
                    root = etree.fromstring(
                        zf.read(name),
                        parser=etree.XMLParser(recover=True, huge_tree=True, ns_clean=True),
                    )
                except Exception:
                    continue
                if root is None:
                    continue
                contexts = {c.get("id"): c for c in root.xpath("//*[local-name()='context']")}
                for el in root.iter():
                    tag = etree.QName(el).localname
                    if not any(k in tag for k in _REVENUE_NAME_KEYWORDS):
                        continue
                    if any(b in tag for b in _REVENUE_NAME_EXCLUDES):
                        continue
                    if tag in seen:
                        continue
                    ctx = contexts.get(el.get("contextRef") or "")
                    if ctx is None:
                        continue
                    cid = ctx.get("id") or ""
                    if "Prior" in cid or "Forecast" in cid:
                        continue
                    members = ctx.xpath(".//*[local-name()='explicitMember']")
                    if any("Member" in (m.text or "") for m in members):
                        continue
                    txt = (el.text or "").strip().replace(",", "")
                    if not txt or txt == "-":
                        continue
                    try:
                        val = float(txt)
                    except ValueError:
                        continue
                    scale = el.get("scale")
                    if scale:
                        try:
                            val *= 10 ** int(scale)
                        except ValueError:
                            pass
                    if val < 1_000_000_000:   # skip per-share figures, sub-billion-yen items
                        continue
                    if "SummaryOfBusinessResults" in tag or "KeyFinancialData" in tag:
                        family = "summary"
                    elif "IFRS" in tag:
                        family = "ifrs"
                    else:
                        family = "gaap"
                    seen[tag] = {
                        "tag": tag,
                        "value": val,
                        "scale": scale or "",
                        "decimals": el.get("decimals", ""),
                        "family": family,
                    }
            return list(seen.values())
    except (zipfile.BadZipFile, FileNotFoundError):
        return []


def _extract_revenue(zf: zipfile.ZipFile) -> float | None:
    """Pull a top-level revenue figure from XBRL."""
    xbrl_files = [n for n in zf.namelist()
                  if n.lower().endswith((".xbrl", ".htm"))
                  and "PublicDoc" in n]
    for name in xbrl_files:
        try:
            data = zf.read(name)
            root = etree.fromstring(data, parser=etree.XMLParser(recover=True, huge_tree=True, ns_clean=True))
        except Exception:
            continue
        if root is None:
            continue
        for tag in REVENUE_TAGS:
            nodes = root.xpath(f"//*[local-name()='{tag}']")
            for node in nodes:
                ctx = node.get("contextRef") or ""
                # Exclude prior-year comparatives, forecasts, and any
                # dimensioned axis (segment/reconciling/etc.). "Member" is
                # the XBRL convention for any dimension member, so rejecting
                # it catches ReconcilingItemsMember as well as segment rows.
                if ("Prior" in ctx or "Forecast" in ctx
                        or "Segment" in ctx or "Member" in ctx):
                    continue
                txt = (node.text or "").strip().replace(",", "")
                if not txt or txt == "-":
                    continue
                try:
                    val = float(txt)
                except ValueError:
                    continue
                # iXBRL: only `scale` is a magnitude multiplier. `decimals`
                # is a precision hint (how many digits are significant) and
                # must NOT be applied as a scale — doing so double-counts
                # whenever both attributes are present and produces values
                # off by factors of 10^6+ on Summary-of-Business-Results
                # rows (which routinely carry decimals=-6 and scale=6).
                scale = node.get("scale")
                if scale:
                    try:
                        val *= 10 ** int(scale)
                    except ValueError:
                        pass
                if val > 0:
                    return val
    return None


def _extract_business_description(zf: zipfile.ZipFile) -> str:
    """Pull jpcrp_cor:DescriptionOfBusinessTextBlock from the 有価証券報告書.

    Present in ASR (annual). Not populated in SRS/Q*R interim filings. Callers
    cache whatever they find across the filings they scanned; an empty string
    means no annual-report-sourced description was available.
    """
    for name in zf.namelist():
        if not (name.endswith(".htm") or name.endswith(".xbrl")):
            continue
        if "PublicDoc" not in name:
            continue
        try:
            data = zf.read(name)
            root = etree.fromstring(
                data, parser=etree.XMLParser(recover=True, huge_tree=True, ns_clean=True)
            )
        except Exception:
            continue
        if root is None:
            continue
        nodes = root.xpath("//*[local-name()='DescriptionOfBusinessTextBlock']")
        if nodes:
            text = _strip_html("".join(nodes[0].itertext()))
            if text:
                return text
    return ""


def load_company_from_edinet(
    folder: Path,
    cutoff_date: date | None = None,
    filing_type_filter: set[str] | None = None,
) -> dict[str, Any] | None:
    """Load one company from data/edinet/<code>/ folder."""
    code = folder.name
    if not re.match(r"^\d{4}$", code):
        return None

    zips = sorted(folder.glob("*.zip"))
    if len(zips) < 2:
        log.warning("EDINET %s: only %d ZIPs, need >=2", code, len(zips))
        return None

    metas = []
    qual_by_zip: dict[str, str] = {}
    revenues: list[tuple[str, float]] = []
    business_description = ""

    for z in zips:
        meta = extract_edinet_filing_meta(z)
        try:
            with zipfile.ZipFile(z) as zf:
                q = _extract_qualitative(zf)
                if q:
                    qual_by_zip[z.name] = q
                r = _extract_revenue(zf)
                if r is not None and meta is not None:
                    revenues.append((meta.filing_date.isoformat(), r))
                # Prefer the most recent ASR (annual) description — iterate in
                # filename order (sorted ascending) and overwrite each hit so
                # the last annual report's description wins.
                if meta is not None and meta.filing_type == "edinet_asr":
                    desc = _extract_business_description(zf)
                    if desc:
                        business_description = desc
        except zipfile.BadZipFile:
            log.warning("bad zip: %s", z)
            continue
        if meta is not None and z.name in qual_by_zip:
            metas.append(meta)

    if not business_description:
        log.warning(
            "EDINET %s: no DescriptionOfBusinessTextBlock found in any ASR — "
            "falling back to company name for industry-gate cosine path",
            code,
        )

    if len(metas) < 2:
        log.warning("EDINET %s: only %d usable filings with parseable metadata + qualitative text — skipping", code, len(metas))
        return None

    pair = find_yoy_pair(metas, cutoff_date=cutoff_date,
                         filing_type_filter=filing_type_filter)
    if pair is None:
        log.warning(
            "EDINET %s: no matching YoY pair (same filing_type + fiscal_period, 9–15 months apart) — skipping",
            code,
        )
        return None
    prev_meta, curr_meta = pair

    prev_raw = qual_by_zip[prev_meta.zip_path.name]
    curr_raw = qual_by_zip[curr_meta.zip_path.name]
    prev_text = _skip_toc(prev_raw)
    curr_text = _skip_toc(curr_raw)
    announce_date = curr_meta.filing_date.isoformat()

    revenues.sort(key=lambda kv: kv[0])
    rev_series = [v for _, v in revenues]
    segment_history: dict[str, list[float]] = {}
    if rev_series:
        segment_history["_revenue_proxy"] = rev_series

    return {
        "code": code,
        "name": code,           # caller (loader.py) will overwrite with config name
        "announce_date": announce_date,
        "prev_text": prev_text[:8000],
        "curr_text": curr_text[:8000],
        "prev_raw_text": prev_raw[:16000],
        "curr_raw_text": curr_raw[:16000],
        "segments_prev": [],
        "segments_curr": [],
        "segment_history": segment_history,
        "business_description_ja": business_description,
        "source": "edinet_manual",
        "filings_count": len(zips),
        "revenue_points": len(rev_series),
        # Correction 1: filing metadata propagated downstream.
        "filing_type": curr_meta.filing_type,
        "fiscal_period": curr_meta.fiscal_period,
        "prev_filing": prev_meta.as_dict(),
        "curr_filing": curr_meta.as_dict(),
    }


def load_all_edinet(
    data_dir: Path, cutoff_date: date | None = None
) -> dict[str, dict[str, Any]]:
    """Walk data/edinet/<code>/ and return code → fundamentals.

    When cutoff_date is provided (backtest mode), each company's YoY pair is
    selected from filings with filing_date ≤ cutoff_date only.
    """
    out: dict[str, dict[str, Any]] = {}
    edinet_dir = data_dir / EDINET_DIR_NAME
    if not edinet_dir.exists():
        return out
    reset_fy_disagreement_counters()
    for folder in sorted(edinet_dir.iterdir()):
        if not folder.is_dir():
            continue
        fund = load_company_from_edinet(folder, cutoff_date=cutoff_date)
        if fund is not None:
            log.info("EDINET manual load: %s (%d filings)", fund["code"], fund["filings_count"])
            out[fund["code"]] = fund
    supp3, supp1, surfaced = get_fy_disagreement_counts()
    log.info(
        "EDINET FY-end disagreement summary: suppressed_3mo=%d, suppressed_1mo=%d, surfaced=%d (other offsets — inspect)",
        supp3, supp1, surfaced,
    )
    return out
