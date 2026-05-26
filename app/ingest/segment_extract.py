"""Extract segment revenue + ratios from an EDINET XBRL filing.

Filers use very different tag conventions for segment-level revenue
depending on accounting standard (J-GAAP / IFRS / US-GAAP) and on which
schema version they're submitting. We cast a wide net by matching tag
*substrings* in priority order, then pick the first pattern that
yields ≥2 distinct segments.

Examples observed in real EDINET data (2024-2025 filings):
  * Sony 6758  → SalesAndFinancialServicesRevenueToCustomersIFRS
  * NTT  9432  → OperatingRevenuesIFRS
  * Fast Ret. 9983 → RevenueIFRS
  * SoftBank 9984 → SalesToExternalCustomersIFRS
  * Nissan 7201 → RevenueFromExternalCustomers (the legacy default)
  * Takashimaya 8233 → RevenuesFromExternalCustomers
"""
from __future__ import annotations
import re
import zipfile
from pathlib import Path

import pandas as pd
from lxml import etree

# Priority-ordered patterns. The extractor tries each pattern, collects all
# matching tags whose name contains it as a substring, and stops when it
# finds enough segments (≥2 distinct members). External-customer revenue
# tags come first so internal/intersegment revenue gets ignored.
SEGMENT_REVENUE_TAG_PATTERNS = (
    "RevenueFromExternalCustomers",          # J-GAAP/IFRS canonical
    "RevenuesFromExternalCustomers",         # plural variant (Takashimaya)
    "SalesToExternalCustomersIFRS",          # SoftBank
    "SalesAndFinancialServicesRevenueToCustomers",  # Sony (IFRS)
    "RevenueFromContractsWithCustomers",     # IFRS 15
    "NetSalesOfReportableSegments",          # legacy
    "OrdinaryRevenuesReportableSegments",    # banking
    "OperatingRevenuesReportableSegments",
    "OperatingRevenuesIFRS",                 # NTT
    "OperatingRevenue1",                     # Takashimaya secondary
    "RevenueIFRS",                           # Fast Retailing
    "NetSalesIFRS",
    "Revenue",                               # broadest fallback
    "NetSales",
    "Sales",
)

# Tag-name fragments that indicate INTERNAL or NON-EXTERNAL revenue.
# Skipped even if they otherwise match a pattern above.
EXCLUDE_TAG_PATTERNS = (
    "Intersegment",
    "Adjustment",
    "Elimination",
)

# Member-name fragments that indicate bookkeeping rows (not real segments).
EXCLUDE_MEMBER_PATTERNS = (
    "ReconcilingItems",
    "Adjustment",
    "Elimination",
    "Total",
    "Consolidated",
)

# Exact member names that are aggregator/sum rows — they appear ALONGSIDE
# the real per-segment rows and equal the sum of those rows. Must be
# excluded by exact match (not substring), because the real segments
# contain "ReportableSegment" in their names too (e.g.,
# "GameAndNetworkServicesReportableSegmentMember").
EXACT_EXCLUDE_MEMBERS = frozenset({
    "ReportableSegmentsMember",
    "ReportableSegmentMember",
    "OperatingSegmentsMember",
    "OperatingSegmentMember",
    "BusinessSegmentsMember",
    "BusinessSegmentMember",
    "AllReportableSegmentsMember",
})

# Dimension-name fragments that mark a context as segment-axis-bearing.
SEGMENT_AXIS_PATTERNS = ("Segment", "Business", "Reportable")


_LONG_OTHER_PATTERNS = (
    "OperatingSegmentsNotIncludedInReportableSegments",
    "NotIncludedInReportableSegments",
    "OtherRevenueGeneratingBusinessActivities",
)


def _humanise(member_local_name: str) -> str:
    """Convert 'GameAndNetworkServicesReportableSegmentMember' →
    'Game And Network Services'. Collapse the standardised long-form
    'OperatingSegmentsNotIncludedInReportableSegmentsAndOtherRevenue
    GeneratingBusinessActivitiesMember' to 'Other'."""
    if any(p in member_local_name for p in _LONG_OTHER_PATTERNS):
        return "Other"
    s = re.sub(r"(ReportableSegments?|OperatingSegments?|BusinessSegments?)?Member$", "", member_local_name)
    # CamelCase → words
    s = re.sub(r"(?<!^)(?=[A-Z])", " ", s)
    return s.strip() or member_local_name


def _strip_boilerplate(text: str) -> str:
    """Strip the standardised "、報告セグメント [メンバー]" suffix
    that some filers append to their JA labels. Only strips when the
    text after the comma matches the known boilerplate pattern — so a
    real parenthetical like "その他（不動産、エネルギー等）" is preserved."""
    # Match: optional comma + "報告セグメント" / "オペレーティング" / "事業セグメント"
    # / "[メンバー]" / "[Member]" suffix at end of string.
    return re.sub(
        r"[、,]\s*(?:報告|オペレーティング|事業)?セグメント.*$|"
        r"[、,]\s*\[(?:メンバー|Member)\].*$|"
        r"\s*\[(?:メンバー|Member)\]\s*$",
        "",
        text,
    ).strip()


def _japanise(member_local_name: str, ja_labels: dict[str, str]) -> str:
    """Look up the Japanese label for a segment member.

    Two filer conventions observed in real EDINET data:
      * Sony / most JPCRP filings: xlink:label = "label_<ElementName>"
      * Nissan-style filings:      xlink:label =
            "<namespace>_<EDINETcode>_<ElementName>_label"
    We try both, then fall back to substring search. A ``_2`` or ``_1``
    suffix indicates the boilerplate-decorated variant — its text is
    stripped at the first ``、``/``,``.
    """
    if any(p in member_local_name for p in _LONG_OTHER_PATTERNS):
        return "その他"

    # Pattern 1: Sony-style — clean and decorated.
    sony_key = f"label_{member_local_name}"
    if sony_key in ja_labels:
        return _strip_boilerplate(ja_labels[sony_key])
    if f"{sony_key}_2" in ja_labels:
        return _strip_boilerplate(ja_labels[f"{sony_key}_2"])

    # Pattern 2: Nissan-style — find any key that contains the element name
    # AND ends with "_label" (clean) or "_label_<n>" (decorated).
    candidates: list[tuple[int, str]] = []   # (priority, label_text) — lower = better
    needle = f"_{member_local_name}_label"
    for k, v in ja_labels.items():
        if needle not in k:
            continue
        # Prefer "_label" exact-suffix (clean) over "_label_1", "_label_2", …
        if k.endswith("_label"):
            candidates.append((0, v))
        else:
            candidates.append((1, v))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return _strip_boilerplate(candidates[0][1])

    # Pattern 3: last-resort substring scan — any label whose key contains the element name.
    for k, v in ja_labels.items():
        if member_local_name in k:
            return _strip_boilerplate(v)

    return _humanise(member_local_name)


def _load_ja_labels(zf: zipfile.ZipFile) -> dict[str, str]:
    """Scan the ZIP for *_lab.xml and return a {xlink:label → JA text} map.
    Empty dict if none found."""
    out: dict[str, str] = {}
    for name in zf.namelist():
        if not name.endswith("_lab.xml") or "PublicDoc" not in name:
            continue
        try:
            root = etree.fromstring(
                zf.read(name),
                parser=etree.XMLParser(recover=True, huge_tree=True),
            )
        except Exception:
            continue
        for el in root.xpath("//*[local-name()='label']"):
            lang = None
            for k, v in el.attrib.items():
                if k.endswith("}lang"):
                    lang = v
                    break
            if lang != "ja":
                continue
            xlink_label = el.get("{http://www.w3.org/1999/xlink}label", "")
            text = (el.text or "").strip()
            if xlink_label and text and xlink_label not in out:
                out[xlink_label] = text
    return out


def _is_segment_context(ctx) -> tuple[bool, str | None, str | None]:
    """Return (is_segment, segment_member_local_name, axis_local_name) for a context."""
    members = ctx.xpath(".//*[local-name()='explicitMember']")
    for m in members:
        dim = (m.get("dimension") or "")
        dim_local = dim.split(":")[-1]
        if not any(p in dim_local for p in SEGMENT_AXIS_PATTERNS):
            continue
        member_full = (m.text or "")
        member_local = member_full.split(":")[-1]
        if member_local in EXACT_EXCLUDE_MEMBERS:
            continue
        if any(p in member_local for p in EXCLUDE_MEMBER_PATTERNS):
            continue
        return True, member_local, dim_local
    return False, None, None


def _is_current_period(ctx) -> bool:
    """True if the context refers to the current/main period (not Prior, not Forecast)."""
    cid = ctx.get("id") or ""
    if "Prior" in cid or "Forecast" in cid:
        return False
    return True


def _is_prior_period(ctx) -> bool:
    """True if the context refers to the immediate prior fiscal year (Prior1Year*)
    and is not a forecast. We accept any 'Prior1' or 'Prior1Year' marker — these
    are the IFRS-mandated restated prior-year comparatives that sit alongside
    the current-year segment data inside the SAME filing."""
    cid = ctx.get("id") or ""
    if "Forecast" in cid:
        return False
    return ("Prior1Year" in cid) or ("Prior1Instant" in cid) or cid.endswith("Prior1") or "Prior1Duration" in cid


def _scaled_value(node) -> float | None:
    txt = (node.text or "").strip().replace(",", "")
    if not txt or txt == "-":
        return None
    try:
        val = float(txt)
    except ValueError:
        return None
    scale = node.get("scale")
    if scale:
        try:
            val *= 10 ** int(scale)
        except ValueError:
            pass
    return val


def _try_pattern(root, contexts: dict, pattern: str,
                 ja_labels: dict[str, str], *, period: str = "current") -> list[dict]:
    """Find all elements whose tag local-name contains `pattern` AND whose
    context carries a segment-axis member. Return one row per (segment, value).

    `period` selects which contexts to keep:
      - "current" → the filing's main period (default)
      - "prior"   → IFRS-mandated restated prior-year comparatives in the SAME
                    filing. Used to source prev-year segments when the previous
                    filing uses a different accounting standard (e.g., Sony's
                    US-GAAP→IFRS switch made the prev ZIP's tags unmatchable).
    """
    period_check = _is_prior_period if period == "prior" else _is_current_period
    rows: list[dict] = []
    for el in root.iter():
        tag_local = etree.QName(el).localname
        if pattern not in tag_local:
            continue
        if any(bad in tag_local for bad in EXCLUDE_TAG_PATTERNS):
            continue
        ctx = contexts.get(el.get("contextRef") or "")
        if ctx is None or not period_check(ctx):
            continue
        is_seg, member_local, axis_local = _is_segment_context(ctx)
        if not is_seg:
            continue
        val = _scaled_value(el)
        if val is None or val <= 0:
            continue
        rows.append({
            "segment_name": _humanise(member_local),
            "segment_name_ja": _japanise(member_local, ja_labels),
            "segment_member_raw": member_local,
            "axis": axis_local,
            "tag": tag_local,
            "revenue": val,
        })
    return rows


def extract_segments(zip_path: Path, *, period: str = "current") -> pd.DataFrame:
    """Return DataFrame[segment_name, revenue, ratio]. Empty if nothing parseable.

    Tries tag patterns in priority order; the first pattern that yields
    ≥2 distinct segments wins. This avoids picking up a single 'Total
    Revenue' row when the real per-segment data lives under a different
    (more specific) tag.

    `period` selects which fiscal year to extract from the same ZIP:
      - "current" (default) → the filing's main period
      - "prior"             → restated prior-year comparatives in the same
                              filing (IFRS-mandated). Use this to source
                              prev-year segments when the previous filing
                              uses a different accounting standard.
    """
    with zipfile.ZipFile(zip_path) as zf:
        ja_labels = _load_ja_labels(zf)
        xbrl_names = [n for n in zf.namelist() if n.endswith(".xbrl") and "PublicDoc" in n]
        for name in xbrl_names:
            try:
                root = etree.fromstring(
                    zf.read(name),
                    parser=etree.XMLParser(recover=True, huge_tree=True),
                )
            except Exception:
                continue
            contexts = {c.get("id"): c for c in root.xpath("//*[local-name()='context']")}

            for pattern in SEGMENT_REVENUE_TAG_PATTERNS:
                rows = _try_pattern(root, contexts, pattern, ja_labels, period=period)
                if not rows:
                    continue
                df = (pd.DataFrame(rows)
                        .groupby(["segment_name", "segment_name_ja"], as_index=False)
                        .agg(revenue=("revenue", "max")))   # max over duplicate periods
                if len(df) < 2:
                    continue
                total = df["revenue"].sum()
                df["ratio"] = df["revenue"] / total if total else 0.0
                return df.sort_values("revenue", ascending=False).reset_index(drop=True)

    return pd.DataFrame(columns=["segment_name", "segment_name_ja", "revenue", "ratio"])
