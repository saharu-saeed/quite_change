"""Filing-type + fiscal-period metadata extraction (Correction 1).

Pairs must compare like-to-like: same filing type, same fiscal period,
one fiscal year apart. This module extracts that metadata from the
iXBRL (primary, authoritative) with a filename heuristic as a secondary
sanity check, and selects the YoY pair.

Returns canonical labels so downstream code (loaders, aggregator, report)
can compare without knowing which source produced the filing.
"""
from __future__ import annotations

import logging
import re
import zipfile
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from lxml import etree

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# FY-disagreement warning suppression counters (per run).
# -----------------------------------------------------------------------------
# The filename-heuristic defaults to a March-31 fiscal year-end (the Japanese
# majority). Non-March issuers (e.g. Lasertec, June-30) trigger a warning per
# non-FY filing even though the iXBRL-wins logic handles them correctly. We
# suppress the warning when the disagreement is exactly 3 months — the common
# off-by-a-quarter pattern — and still surface larger disagreements as those
# could indicate real bugs. Counters are read and reset from the loader so a
# per-run summary can be logged.
_fy_suppressed_3mo = 0
_fy_suppressed_1mo = 0
_fy_surfaced_count = 0


def reset_fy_disagreement_counters() -> None:
    global _fy_suppressed_3mo, _fy_suppressed_1mo, _fy_surfaced_count
    _fy_suppressed_3mo = 0
    _fy_suppressed_1mo = 0
    _fy_surfaced_count = 0


def get_fy_disagreement_counts() -> tuple[int, int, int]:
    """Return (suppressed_3mo, suppressed_1mo, surfaced)."""
    return _fy_suppressed_3mo, _fy_suppressed_1mo, _fy_surfaced_count


# -----------------------------------------------------------------------------
# Canonical labels
# -----------------------------------------------------------------------------
# filing_type:
#   kessan_tanshin_annual   — TDnet 決算短信 (annual,    taxonomy acedjpsm)
#   kessan_tanshin_quarter  — TDnet 決算短信 (quarterly, taxonomy scedjpsy)
#   edinet_asr              — 有価証券報告書 (annual securities report)
#   edinet_srs              — 半期報告書
#   edinet_q1r/q2r/q3r      — 四半期報告書
#
# fiscal_period is orthogonal and takes values: "FY", "Q1", "Q2", "Q3"
# (Q2 = H1 interim in practice). "FY" pairs with "FY"; "Q2" pairs with "Q2"; etc.

FilingType = str
FiscalPeriod = str


@dataclass(frozen=True)
class FilingMeta:
    zip_path: Path
    filing_date: date
    period_end: date
    fiscal_year_end: date
    filing_type: FilingType
    fiscal_period: FiscalPeriod
    document_name: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d["zip_path"] = str(self.zip_path)
        d["filing_date"] = self.filing_date.isoformat()
        d["period_end"] = self.period_end.isoformat()
        d["fiscal_year_end"] = self.fiscal_year_end.isoformat()
        return d


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _parse_iso_date(s: str) -> date | None:
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


def _months_between(a: date, b: date) -> int:
    """Signed month difference a - b (approx), rounded to nearest integer."""
    return (a.year - b.year) * 12 + (a.month - b.month)


def _fiscal_period_from_months(period_end: date, fiscal_year_end: date) -> FiscalPeriod:
    """Derive Q1/Q2/Q3/FY from how far period_end is before fiscal_year_end.

    Japanese fiscal calendar: FY end → period 12, Q3 → -3mo, Q2/H1 → -6mo, Q1 → -9mo.
    """
    diff = _months_between(fiscal_year_end, period_end)  # positive = period_end is earlier
    # tolerate ±1 month for non-calendar-exact period ends (e.g., 30 Sep vs 1 Oct)
    if -1 <= diff <= 1:
        return "FY"
    if 2 <= diff <= 4:
        return "Q3"
    if 5 <= diff <= 7:
        return "Q2"
    if 8 <= diff <= 10:
        return "Q1"
    # Shouldn't happen for valid TDnet/EDINET filings; log and fallback.
    log.warning(
        "Unusual period offset: period_end=%s vs fiscal_year_end=%s (diff=%d months)",
        period_end, fiscal_year_end, diff,
    )
    return "FY"


# -----------------------------------------------------------------------------
# TDnet (決算短信) extractor
# -----------------------------------------------------------------------------
_TDNET_FILENAME_DATE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})")
# Summary iXBRL taxonomy prefix encodes annual vs quarterly.
# TDnet prefixes have the shape tse-<scope><basis>edjps<suffix>-
#   scope:  a (annual), s (semi-annual/banking), q (pre-reform quarterly)
#   basis:  c (consolidated), n (non-consolidated)
#   suffix: m (legacy)   or   y (post-2024-reform quarterly taxonomy)
# We accept all scope/basis combinations so older and non-consolidated
# filings are recognised; fiscal-period math below disambiguates
# annual-vs-quarterly for ambiguous prefixes.
_TDNET_SUMMARY_RE = re.compile(r"tse-([asq][cn]edjps[my])-", re.IGNORECASE)
# Unambiguously-annual scope prefix (vs quarterly/semi-annual).
_TDNET_ANNUAL_SCOPES = {"a"}
_TDNET_ATTACHMENT_DATES_RE = re.compile(
    r"tse-\w+-\d+-(\d{4}-\d{2}-\d{2})-\d+-(\d{4}-\d{2}-\d{2})",
)


def _tdnet_summary_raw(zf: zipfile.ZipFile) -> tuple[str, bytes] | None:
    for name in zf.namelist():
        if "Summary" in name and name.endswith("ixbrl.htm"):
            return name, zf.read(name)
    return None


def _tdnet_attachment_dates(zf: zipfile.ZipFile) -> tuple[date, date] | None:
    """Parse (period_end, filing_date) from Attachment filenames.

    Attachment filenames have the shape
        tse-scedjpfr-{CODE}-{PERIOD_END}-{SUBMISSION#}-{FILING_DATE}-...
    which embeds both dates directly.
    """
    for name in zf.namelist():
        if "Attachment" not in name:
            continue
        m = _TDNET_ATTACHMENT_DATES_RE.search(name)
        if m:
            pe = _parse_iso_date(m.group(1))
            fd = _parse_iso_date(m.group(2))
            if pe and fd:
                return pe, fd
    return None


def _ixbrl_facts(raw: bytes) -> dict[str, str]:
    """Return {local-name: text} for every ix:nonNumeric / ix:nonFraction fact."""
    try:
        root = etree.fromstring(raw, parser=etree.XMLParser(recover=True, huge_tree=True, ns_clean=True))
    except Exception:
        return {}
    if root is None:
        return {}
    facts: dict[str, str] = {}
    for el in root.iter():
        tag = etree.QName(el.tag).localname if isinstance(el.tag, str) else ""
        if tag not in ("nonNumeric", "nonFraction"):
            continue
        name = el.get("name") or ""
        local = name.split(":", 1)[-1] if name else ""
        if not local:
            continue
        # collect all text (ix:nonNumeric can contain markup)
        text = "".join(el.itertext()).strip()
        if text and local not in facts:
            facts[local] = text
    return facts


def extract_tdnet_filing_meta(zip_path: Path) -> FilingMeta | None:
    """Extract FilingMeta from a TDnet 決算短信 ZIP."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        log.warning("Bad zip, cannot extract meta: %s", zip_path)
        return None

    with zf:
        summary = _tdnet_summary_raw(zf)
        if summary is None:
            log.warning("No Summary iXBRL in %s", zip_path.name)
            return None
        summary_name, summary_raw = summary

        taxonomy_match = _TDNET_SUMMARY_RE.search(summary_name)
        if not taxonomy_match:
            log.warning("Could not read TDnet taxonomy prefix from %s", summary_name)
            return None
        taxonomy = taxonomy_match.group(1).lower()
        taxonomy_says_annual = taxonomy[:1] in _TDNET_ANNUAL_SCOPES
        # Note: `scedjpsy` (post-reform quarterly), `qcedjpsm` (pre-reform quarterly),
        # and `scedjpsm` (banking, both annual and semi-annual use this) are all
        # routed through the fiscal-period math below to decide annual-vs-quarterly.

        facts = _ixbrl_facts(summary_raw)
        fy_end = _parse_iso_date(facts.get("FiscalYearEnd", ""))
        document_name = facts.get("DocumentName", "")
        quarterly_period = facts.get("QuarterlyPeriod", "").strip()

        attach_dates = _tdnet_attachment_dates(zf)
        if attach_dates:
            period_end, filing_date = attach_dates
        else:
            # Fallback: filename date = filing date; period_end = fiscal_year_end (annual).
            m = _TDNET_FILENAME_DATE_RE.match(zip_path.name)
            if not m or not fy_end:
                log.warning("Cannot determine filing date / period_end for %s", zip_path.name)
                return None
            filing_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            period_end = fy_end

        if fy_end is None:
            # FiscalYearEnd missing from Summary — rare; derive from period_end assuming
            # annual filings have period_end == fiscal_year_end.
            if filing_type == "kessan_tanshin_annual":
                fy_end = period_end
            else:
                log.warning("FiscalYearEnd missing in %s and filing is non-annual", zip_path.name)
                return None

    # Decide annual vs quarterly. iXBRL is authoritative via QuarterlyPeriod;
    # fall back to fiscal-period math derived from (period_end, fy_end).
    if quarterly_period in ("1", "2", "3"):
        fiscal_period_ixbrl: FiscalPeriod = f"Q{quarterly_period}"
        fiscal_period_source = "iXBRL.QuarterlyPeriod"
    elif taxonomy_says_annual:
        fiscal_period_ixbrl = "FY"
        fiscal_period_source = "iXBRL.taxonomy"
    else:
        fiscal_period_ixbrl = _fiscal_period_from_months(period_end, fy_end)
        fiscal_period_source = "derived"

    filing_type: FilingType = (
        "kessan_tanshin_annual" if fiscal_period_ixbrl == "FY" else "kessan_tanshin_quarter"
    )

    # Sanity cross-check: if iXBRL-based decision disagrees with period-end math,
    # log so operators can catch pathological filings. Skip when the source *is*
    # the period-end math (no cross-check to run).
    if fiscal_period_source != "derived":
        fiscal_period_derived = _fiscal_period_from_months(period_end, fy_end)
        if fiscal_period_derived != fiscal_period_ixbrl:
            log.warning(
                "Fiscal-period disagreement in %s: %s says %s, period-end math says %s — trusting iXBRL",
                zip_path.name, fiscal_period_source, fiscal_period_ixbrl, fiscal_period_derived,
            )

    return FilingMeta(
        zip_path=zip_path,
        filing_date=filing_date,
        period_end=period_end,
        fiscal_year_end=fy_end,
        filing_type=filing_type,
        fiscal_period=fiscal_period_ixbrl,
        document_name=document_name,
    )


# -----------------------------------------------------------------------------
# EDINET extractor
# -----------------------------------------------------------------------------
# EDINET filename: jpcrp{form_code}-{form_suffix}-001_E{ID}-000_{PERIOD_END}_{SUB#}_{FILING_DATE}_...
_EDINET_FORM_RE = re.compile(
    r"jpcrp\d+-(asr|q1r|q2r|q3r|srs|ssr)-\d+_E\d+-\d+_(\d{4}-\d{2}-\d{2})_\d+_(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

_EDINET_FORM_TO_TYPE: dict[str, FilingType] = {
    "asr": "edinet_asr",
    # Japan's 2024 disclosure reform replaced 四半期報告書 (q2r) for 2Q with
    # 半期報告書 (srs/ssr). These are the same document class in business terms,
    # so we normalise them to a shared canonical filing_type. Without this,
    # any company that crossed the reform boundary (e.g. 3923 ラクス) would
    # silently lose its YoY pair and fall out of the pipeline.
    "srs": "edinet_h1_interim",
    "ssr": "edinet_h1_interim",
    "q2r": "edinet_h1_interim",
    # Pre-reform Q1/Q3 reports still appear in historical data; keep distinct.
    "q1r": "edinet_q1r",
    "q3r": "edinet_q3r",
}

_EDINET_FORM_TO_PERIOD: dict[str, FiscalPeriod] = {
    "asr": "FY",
    "srs": "Q2",
    "ssr": "Q2",
    "q1r": "Q1",
    "q2r": "Q2",
    "q3r": "Q3",
}


def extract_edinet_filing_meta(zip_path: Path) -> FilingMeta | None:
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        log.warning("Bad zip, cannot extract meta: %s", zip_path)
        return None

    form_code: str | None = None
    period_end: date | None = None
    filing_date: date | None = None

    with zf:
        for name in zf.namelist():
            m = _EDINET_FORM_RE.search(name)
            if not m:
                continue
            form_code = m.group(1).lower()
            period_end = _parse_iso_date(m.group(2))
            filing_date = _parse_iso_date(m.group(3))
            if form_code and period_end and filing_date:
                break

    if not form_code or not period_end or not filing_date:
        log.warning(
            "Could not extract EDINET metadata from %s (form=%s period_end=%s filing_date=%s)",
            zip_path.name, form_code, period_end, filing_date,
        )
        return None

    filing_type = _EDINET_FORM_TO_TYPE.get(form_code)
    fiscal_period = _EDINET_FORM_TO_PERIOD.get(form_code)
    if not filing_type or not fiscal_period:
        log.warning("Unknown EDINET form code %s in %s", form_code, zip_path.name)
        return None

    # Derive fiscal_year_end: for FY, it is period_end itself; otherwise take the
    # next March-31 on/after period_end as a default (most issuers). This is a
    # conservative fallback — the authoritative source would be the iXBRL
    # jpdei_cor:CurrentFiscalYearEndDateDEI fact, which we cross-check below.
    if fiscal_period == "FY":
        fy_end = period_end
    else:
        # March-31 year-end default
        yr = period_end.year if period_end.month <= 3 else period_end.year + 1
        fy_end = date(yr, 3, 31)

    # Try to refine fiscal_year_end from the iXBRL directly (best-effort).
    try:
        with zipfile.ZipFile(zip_path) as zf2:
            for name in zf2.namelist():
                if not (name.endswith(".htm") or name.endswith(".xbrl")) or "PublicDoc" not in name:
                    continue
                facts = _ixbrl_facts(zf2.read(name))
                fy_ixbrl = (
                    _parse_iso_date(facts.get("CurrentFiscalYearEndDateDEI", ""))
                    or _parse_iso_date(facts.get("FiscalYearEnd", ""))
                )
                if fy_ixbrl:
                    if fy_ixbrl != fy_end:
                        global _fy_suppressed_3mo, _fy_suppressed_1mo, _fy_surfaced_count
                        diff_months = abs(_months_between(fy_ixbrl, fy_end))
                        if diff_months == 3:
                            _fy_suppressed_3mo += 1
                            log.debug(
                                "EDINET FY-end off by 3mo in %s: %s vs iXBRL %s — suppressed (non-March FYE, e.g. Jun/Sep/Dec)",
                                zip_path.name, fy_end, fy_ixbrl,
                            )
                        elif diff_months == 1:
                            _fy_suppressed_1mo += 1
                            log.debug(
                                "EDINET FY-end off by 1mo in %s: %s vs iXBRL %s — suppressed (near-March FYE, e.g. Feb-28)",
                                zip_path.name, fy_end, fy_ixbrl,
                            )
                        else:
                            _fy_surfaced_count += 1
                            log.warning(
                                "EDINET fiscal-year-end disagreement in %s: filename heuristic %s vs iXBRL %s (diff=%d months) — trusting iXBRL",
                                zip_path.name, fy_end, fy_ixbrl, diff_months,
                            )
                    fy_end = fy_ixbrl
                    break
    except Exception:
        pass

    return FilingMeta(
        zip_path=zip_path,
        filing_date=filing_date,
        period_end=period_end,
        fiscal_year_end=fy_end,
        filing_type=filing_type,
        fiscal_period=fiscal_period,
        document_name=form_code.upper(),
    )


# -----------------------------------------------------------------------------
# YoY pair selection
# -----------------------------------------------------------------------------
def find_yoy_pair(
    filings: Iterable[FilingMeta],
    cutoff_date: date | None = None,
    filing_type_filter: set[str] | None = None,
) -> tuple[FilingMeta, FilingMeta] | None:
    """Pick (prev, curr) with same filing_type + same fiscal_period, ~12 months apart.

    Strategy:
      1. Sort by filing_date.
      2. If cutoff_date is provided (backtest mode), filter out any filing
         whose filing_date > cutoff_date — no look-ahead.
      3. Take the most recent remaining filing as `curr`.
      4. Among prior filings with identical filing_type and fiscal_period,
         pick the one whose period_end is closest to 12 months before curr's
         period_end, requiring the gap to fall within 9–15 months.
      5. Return None if no matching prior filing exists.
    """
    items = sorted(filings, key=lambda f: f.filing_date)
    if cutoff_date is not None:
        items = [f for f in items if f.filing_date <= cutoff_date]
    if filing_type_filter is not None:
        items = [f for f in items if f.filing_type in filing_type_filter]
    if len(items) < 2:
        return None

    curr = items[-1]
    best: FilingMeta | None = None
    best_err = 10**9
    for prev in items[:-1]:
        if prev.filing_type != curr.filing_type:
            continue
        if prev.fiscal_period != curr.fiscal_period:
            continue
        gap_months = _months_between(curr.period_end, prev.period_end)
        if not (9 <= gap_months <= 15):
            continue
        err = abs(gap_months - 12)
        if err < best_err:
            best_err = err
            best = prev

    if best is None:
        return None
    return best, curr
