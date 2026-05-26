"""Balance-sheet extractor for the Quiet Change agent.

Pulls 11 standard balance-sheet line items from an EDINET XBRL filing so
the prompt's divergence-reasoning rule (profit-up / stock-down or vice-
versa) has concrete BS context — impairment, goodwill writedown,
inventory build, debt jump, etc. — instead of having to speculate from
revenue alone.

Mirrors the shape of `app/ingest/segment_extract.py`: pure function, no
disk cache. Opens the ZIP, iterates the `PublicDoc` XBRL instance files,
matches a per-item priority list of tag fallbacks (IFRS first, then JGAAP
fallbacks), filters out `Prior` / `Forecast` / `Segment` / `Member`
contexts the same way `edinet_loader._extract_revenue` does.

Eleven items returned (in `items` dict). When a tag isn't found, the key
is added to `missing` rather than set to None, so prompt builders can
branch on presence without having to filter None values.

  total_assets, tangible_fixed_assets, intangible_assets, goodwill,
  inventory, trade_receivables, cash_and_equivalents,
  interest_bearing_debt, equity, impairment_loss,
  extraordinary_loss_total

`framework` is a coarse hint ("IFRS" if any IFRS-suffixed tag matched,
else "JGAAP") — used by the prompt builder to render an "n/a (framework
changed)" note when prev/curr ZIPs differ. Not a precise classification;
just enough signal to flag the apples-to-oranges YoY case.
"""
from __future__ import annotations
import zipfile
from pathlib import Path

from lxml import etree


# Per-item tag fallback lists. First match wins. Tag names are matched by
# local-name (namespace-agnostic) the same way every other extractor in
# this codebase does. IFRS variants come first, JGAAP fallbacks follow.
#
# Special case: `interest_bearing_debt` is a SUM of multiple component
# tags (current borrowings + long-term borrowings + bonds), not a single
# tag. The extractor sums every matching component into one value.
#
# Special case: `equity` — IFRS filers expose `EquityIFRSSummaryOfBusinessResults`
# from the 5-year-history table; JGAAP filers expose `NetAssets`. The
# Summary tag is preferred because it's the regulator-required figure.
SINGLE_TAG_ITEMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("total_assets", (
        "AssetsIFRSSummaryOfBusinessResults",
        "TotalAssetsIFRSSummaryOfBusinessResults",
        "TotalAssetsSummaryOfBusinessResults",
        "AssetsIFRS",
        "Assets",
        "TotalAssets",
    )),
    ("tangible_fixed_assets", (
        "PropertyPlantAndEquipmentIFRS",
        "PropertyPlantAndEquipment",
        "TangibleFixedAssets",
    )),
    ("intangible_assets", (
        # IFRS issuers usually report "IntangibleAssetsIFRS" excluding goodwill.
        # JGAAP "IntangibleAssets" sometimes includes goodwill — that's a known
        # imprecision; the goodwill row is reported separately so the LLM has
        # the cleaner figure to cite if it wants to.
        "IntangibleAssetsExcludingGoodwillIFRS",
        "IntangibleAssetsIFRS",
        "IntangibleAssets",
    )),
    ("goodwill", (
        "GoodwillIFRS",
        "Goodwill",
    )),
    ("inventory", (
        # IFRS namespace puts inventories on the BS with a `CAIFRS`
        # (Current Assets) suffix. Bare `Inventories` is the JGAAP fallback.
        "InventoriesCAIFRS",
        "InventoriesIFRS",
        "Inventories",
        "MerchandiseAndFinishedGoods",
    )),
    ("trade_receivables", (
        # IFRS BS-side tag is `TradeAndOtherReceivablesCAIFRS`. JGAAP filers
        # use `NotesAndAccountsReceivableTrade(AndContractAssets)` —
        # the contract-assets variant became standard after the 2021
        # JGAAP revenue-recognition revisions.
        "TradeAndOtherReceivablesCAIFRS",
        "TradeAndOtherReceivablesIFRS",
        "NotesAndAccountsReceivableTradeAndContractAssets",
        "NotesAndAccountsReceivableTrade",
        "AccountsReceivableTrade",
        "TradeReceivables",
    )),
    ("cash_and_equivalents", (
        "CashAndCashEquivalentsCAIFRS",
        "CashAndCashEquivalentsIFRS",
        "CashAndCashEquivalents",
        "CashAndDeposits",
    )),
    ("equity", (
        "EquityIFRSSummaryOfBusinessResults",
        "NetAssetsSummaryOfBusinessResults",
        "EquityIFRS",
        "NetAssets",
        "Equity",
    )),
    ("impairment_loss", (
        # P/L line — the "factory writedown" or "goodwill writedown" hit.
        # When >0 in the current year, this is almost always the
        # divergence reason. Most filers expose at most one of these.
        # JGAAP `ImpairmentLossEL` (EL = Extraordinary Loss section) is the
        # canonical placement for asset-impairment hits in domestic-GAAP
        # filings.
        "ImpairmentLossIFRS",
        "ImpairmentLossEL",
        "ImpairmentLoss",
        "ImpairmentLossOfNoncurrentAssets",
        "LossOnImpairmentOfFixedAssets",
    )),
    ("extraordinary_loss_total", (
        # JGAAP-only concept; IFRS folds these into operating items.
        # Empty for IFRS filers — that's expected, not a bug.
        "ExtraordinaryLoss",
        "TotalExtraordinaryLosses",
    )),
)

# `interest_bearing_debt` aggregation strategy: IFRS filers expose a
# single explicit pair `InterestBearingLiabilitiesCLIFRS` (current) +
# `InterestBearingLiabilitiesNCLIFRS` (non-current) that together equal
# the total interest-bearing-debt balance. When either is present, we use
# their sum and stop — much cleaner than chasing every component.
#
# JGAAP filers don't have that aggregate; we sum the per-component tags
# (short/long-term loans, bonds, commercial paper) the same way an
# analyst would when computing leverage. Lease liabilities are
# DELIBERATELY excluded from both paths — they're a separate IFRS-16
# concept that some users count and others don't, and we'd rather
# under-report than over-report (an inflated debt figure could trigger
# spurious mover flags and lead the LLM astray).
IFRS_INTEREST_BEARING_DEBT_TAGS: tuple[str, ...] = (
    "InterestBearingLiabilitiesCLIFRS",
    "InterestBearingLiabilitiesNCLIFRS",
)
JGAAP_DEBT_COMPONENT_TAGS: tuple[str, ...] = (
    "ShortTermLoansPayable",
    "CurrentPortionOfLongTermLoansPayable",
    "LongTermLoansPayable",
    "BondsPayable",
    "CurrentPortionOfBonds",
    "CommercialPapers",
    "CommercialPaper",
)
# Backward-compat alias for any test that imports the old name.
DEBT_COMPONENT_TAGS = IFRS_INTEREST_BEARING_DEBT_TAGS + JGAAP_DEBT_COMPONENT_TAGS


def _scaled_value(node) -> float | None:
    """Same iXBRL value parser used across all extractors in this codebase.

    Only `scale` is a magnitude multiplier — `decimals` is a precision hint
    and must NOT be applied as a scale. The bug this avoided was values off
    by 10^6+ on Summary-of-Business-Results rows that carry both.
    """
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


def _is_consolidated_context(ctx) -> bool:
    """True iff context refers to the current/main consolidated period.

    Mirrors the rule used by `_extract_revenue` and `_extract_operating_profit`
    in `edinet_loader.py`: exclude prior-year comparatives, forecasts, and any
    dimensioned axis (segment / reconciling-items / member).
    """
    cid = ctx.get("id") or ""
    if "Prior" in cid or "Forecast" in cid:
        return False
    if "Segment" in cid or "Member" in cid:
        return False
    # Also exclude any context carrying an explicitMember dimension, even
    # when the cid string itself doesn't contain the marker.
    members = ctx.xpath(".//*[local-name()='explicitMember']")
    if members:
        return False
    return True


def _first_consolidated_value(root, contexts: dict, tag_local: str) -> float | None:
    """Return the first non-None consolidated value for a tag in the XBRL."""
    nodes = root.xpath(f"//*[local-name()='{tag_local}']")
    for node in nodes:
        ctx = contexts.get(node.get("contextRef") or "")
        if ctx is None or not _is_consolidated_context(ctx):
            continue
        val = _scaled_value(node)
        if val is not None:
            return val
    return None


def _sum_consolidated_values(root, contexts: dict, tag_locals: tuple[str, ...]) -> float | None:
    """Sum the first consolidated value found for every component tag.

    Returns None if no component tag matched at all (so the caller can mark
    the item as missing). Returns 0.0 if all matched tags reported zero.
    """
    total: float | None = None
    for tag_local in tag_locals:
        val = _first_consolidated_value(root, contexts, tag_local)
        if val is None:
            continue
        if total is None:
            total = 0.0
        total += val
    return total


def extract_balance_sheet(zip_path: Path | str) -> dict:
    """Open `zip_path` and return the BS panel.

    Returns:
        {
          "items": {key: float, ...},      # only populated keys
          "missing": [key, ...],           # keys that no tag matched
          "framework": "IFRS" | "JGAAP" | "unknown",
          "matched_tags": {key: tag, ...}, # diagnostic — which tag won per item
        }

    On bad ZIP / file-not-found, returns the empty-result shape with
    every key in `missing` so downstream code can render "BS data
    unavailable" without special-casing.
    """
    item_keys = [k for k, _ in SINGLE_TAG_ITEMS] + ["interest_bearing_debt"]
    result: dict = {
        "items": {},
        "missing": list(item_keys),
        "framework": "unknown",
        "matched_tags": {},
    }
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, FileNotFoundError, OSError):
        return result

    try:
        xbrl_files = [n for n in zf.namelist()
                      if n.lower().endswith(".xbrl")
                      and "PublicDoc" in n]
        if not xbrl_files:
            return result

        ifrs_hits = 0
        jgaap_hits = 0

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

            # Single-tag items.
            for key, tag_priority in SINGLE_TAG_ITEMS:
                if key in result["items"]:
                    continue
                for tag in tag_priority:
                    val = _first_consolidated_value(root, contexts, tag)
                    if val is None:
                        continue
                    result["items"][key] = val
                    result["matched_tags"][key] = tag
                    if "IFRS" in tag:
                        ifrs_hits += 1
                    else:
                        jgaap_hits += 1
                    break

            # Aggregated debt total. Prefer the IFRS aggregate pair
            # (current + non-current interest-bearing liabilities) when
            # present; fall back to summing JGAAP per-component tags.
            if "interest_bearing_debt" not in result["items"]:
                ifrs_total = _sum_consolidated_values(
                    root, contexts, IFRS_INTEREST_BEARING_DEBT_TAGS,
                )
                if ifrs_total is not None:
                    result["items"]["interest_bearing_debt"] = ifrs_total
                    result["matched_tags"]["interest_bearing_debt"] = (
                        "sum(InterestBearingLiabilitiesCLIFRS+NCLIFRS)"
                    )
                    ifrs_hits += 1
                else:
                    debt_total = _sum_consolidated_values(
                        root, contexts, JGAAP_DEBT_COMPONENT_TAGS,
                    )
                    if debt_total is not None:
                        result["items"]["interest_bearing_debt"] = debt_total
                        result["matched_tags"]["interest_bearing_debt"] = (
                            "sum(loans+bonds+CP, JGAAP)"
                        )
                        jgaap_hits += 1

        result["missing"] = [k for k in item_keys if k not in result["items"]]
        if ifrs_hits and ifrs_hits >= jgaap_hits:
            result["framework"] = "IFRS"
        elif jgaap_hits:
            result["framework"] = "JGAAP"
        # else "unknown" — neither side matched (shouldn't happen on a real ASR)
        return result
    finally:
        zf.close()


def extract_balance_sheet_from_zip_path(zip_path) -> dict:
    """Public entry — alias for `extract_balance_sheet`. Naming mirrors the
    `extract_revenue_from_zip_path` / `extract_operating_profit_from_zip_path`
    convention in `edinet_loader.py` so the import sites read consistently.
    """
    return extract_balance_sheet(zip_path)
