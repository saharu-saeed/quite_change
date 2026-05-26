"""Valuation screen — the missing axis for Profile C.

In Profile A/B the recent price drop tells you something is being mispriced;
in Profile C (genuinely-unseen quality growers) the price move on tiny names
is too noisy to mean much. What tells you the price is *wrong* there is
**valuation** — "this verified-good business is trading cheap vs its peers."

Metrics computed (all cache-only, free):
  - P/E ratio        : latest_close / latest_eps  (annual)
  - P/B ratio        : latest_close / latest_bps
  - Optional: EV/OP   (operating-profit-based, defined when OP > 0)

Composite score: sector-aware percentile rank. Cheaper = higher signal
(we invert the percentile so "low P/E = high score"). Same shape as the
quality screen, just inverted direction.

Hard rule baked in: a name only gets a valuation_score if the prerequisites
for the metrics are well-defined — eps > 0 AND bps > 0 AND latest_close > 0.
This means a name with negative earnings (whose P/E would be undefined
or misleadingly negative) returns data_ok=False here, even if the quality
screen passes it. This is the "gate-protects-the-ranker-twice" property:
the strict quality gate ALREADY requires 3-of-3 OP positive, so eps
should generally be positive too for names that survive that gate.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TEMPEST_DIR = ROOT / "data" / "tempest"

VALUATION_METRICS = ["pe_ratio", "pb_ratio"]
SECTOR_MIN_PEERS = 5


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_valuation_metrics(ticker: str) -> dict[str, Any]:
    """Compute valuation metrics from cached Tempest data. Free, no API calls."""
    prices_path = TEMPEST_DIR / ticker / "prices.json"
    indicators_path = TEMPEST_DIR / ticker / "indicators.json"

    if not prices_path.exists() or not indicators_path.exists():
        return {"ticker": ticker, "data_ok": False, "reason": "no prices/indicators in cache"}

    try:
        prices = json.load(open(prices_path, encoding="utf-8"))["data"]
        indicators = json.load(open(indicators_path, encoding="utf-8"))["data"]
    except Exception as e:
        return {"ticker": ticker, "data_ok": False, "reason": f"file load error: {e}"}

    if not prices or not indicators:
        return {"ticker": ticker, "data_ok": False, "reason": "empty prices or indicators"}

    try:
        latest_close = float(prices[0]["close"])
    except (KeyError, TypeError, ValueError):
        return {"ticker": ticker, "data_ok": False, "reason": "no latest close"}

    # Latest annual indicators
    indicators = sorted(indicators, key=lambda r: r.get("fiscal_year") or 0, reverse=True)
    latest_inds = indicators[0]
    eps = _to_float(latest_inds.get("eps"))
    bps = _to_float(latest_inds.get("bps"))

    if latest_close <= 0:
        return {"ticker": ticker, "data_ok": False, "reason": "latest close <= 0"}
    if eps is None or eps <= 0:
        return {
            "ticker": ticker, "data_ok": False,
            "reason": "eps missing or non-positive — P/E undefined or misleading",
            "latest_close": latest_close,
        }
    if bps is None or bps <= 0:
        return {
            "ticker": ticker, "data_ok": False,
            "reason": "bps missing or non-positive — P/B undefined",
            "latest_close": latest_close,
            "eps": eps,
        }

    pe_ratio = latest_close / eps
    pb_ratio = latest_close / bps

    return {
        "ticker": ticker,
        "data_ok": True,
        "latest_close": round(latest_close, 2),
        "eps": round(eps, 2),
        "bps": round(bps, 2),
        "pe_ratio": round(pe_ratio, 2),
        "pb_ratio": round(pb_ratio, 2),
        "fiscal_year": latest_inds.get("fiscal_year"),
    }


def _percentile_rank_low_is_better(value: float, sorted_values: list[float]) -> float:
    """0-100 percentile rank where LOW values get HIGH scores (cheaper = better).

    Mid-rank for ties — same tie-handling as the quality screen.
    """
    if not sorted_values:
        return 50.0
    n = len(sorted_values)
    above = sum(1 for v in sorted_values if v > value)
    equal = sum(1 for v in sorted_values if v == value)
    return ((above + equal / 2.0) / n) * 100.0


def compute_sector_valuation_norms(rows: list[dict]) -> dict[str, dict[str, list[float]]]:
    """Per-sector P/E and P/B distributions for percentile-ranking."""
    norms: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        if not r.get("data_ok"):
            continue
        sector = r.get("sector_33_name") or "_unknown"
        bucket = norms.setdefault(sector, {m: [] for m in VALUATION_METRICS})
        for m in VALUATION_METRICS:
            v = r.get(m)
            if v is not None:
                bucket[m].append(float(v))
    for bucket in norms.values():
        for m in bucket:
            bucket[m].sort()
    return norms


def compute_global_valuation_norms(rows: list[dict]) -> dict[str, list[float]]:
    """Cross-sector distribution per metric — fallback for thin sectors."""
    out: dict[str, list[float]] = {m: [] for m in VALUATION_METRICS}
    for r in rows:
        if not r.get("data_ok"):
            continue
        for m in VALUATION_METRICS:
            v = r.get(m)
            if v is not None:
                out[m].append(float(v))
    for m in out:
        out[m].sort()
    return out


def score_valuation(
    row: dict,
    sector_norms: dict[str, dict[str, list[float]]],
    global_norms: dict[str, list[float]],
) -> dict[str, Any]:
    """Composite valuation score: mean of within-sector percentile ranks across
    P/E and P/B. CHEAPER = HIGHER (inverted percentile). 0-100."""
    sector = row.get("sector_33_name") or "_unknown"
    sector_bucket = sector_norms.get(sector, {})
    per_metric: dict[str, float] = {}
    used_fallback: list[str] = []

    for m in VALUATION_METRICS:
        v = row.get(m)
        if v is None:
            per_metric[m] = 50.0
            continue
        sector_vals = sector_bucket.get(m, [])
        if len(sector_vals) >= SECTOR_MIN_PEERS:
            per_metric[m] = _percentile_rank_low_is_better(float(v), sector_vals)
        else:
            per_metric[m] = _percentile_rank_low_is_better(float(v), global_norms.get(m, []))
            used_fallback.append(m)

    composite = round(sum(per_metric.values()) / len(per_metric), 2)
    return {
        "composite_valuation_score": composite,
        "per_metric_percentile_cheap": {k: round(v, 1) for k, v in per_metric.items()},
        "sector_peers": len(sector_bucket.get("pe_ratio", [])),
        "used_global_fallback_for": used_fallback,
    }


# --------------------------------------------------------------------------
# Strict quality gate for Profile C
# --------------------------------------------------------------------------
# Stricter than the Profile A/B quality screen. In Profile C the quality
# signal is doing all the heavy lifting (attention and divergence have been
# dropped), so the gate must be tighter to keep value traps and roll-ups
# out by construction.

PROFILE_C_MIN_REVENUE_JPY = 3e9            # ¥3B floor — avoids shell-tier names
PROFILE_C_MIN_EQUITY_RATIO_PCT = 30.0      # healthy balance sheet
PROFILE_C_MIN_CAGR_3Y_PCT = 3.0            # "growing properly" requires multi-year
PROFILE_C_REQUIRED_OP_POSITIVE_YEARS = 3   # all 3 years, not 2-of-3 like A/B

# Unseen filters — the label "genuinely-unseen" must be backed by coverage AND
# size criteria, not just by the quality gate. Otherwise well-covered industrial
# leaders (太平洋セメント) and retail-pumped consumer brands (ブシロード) end up
# at the top of an "overlooked" track, which is the exact label-vs-criterion
# mismatch we've been correcting throughout this project.
PROFILE_C_MAX_ATTENTION = 8.0              # "thin" by the post-retail-channel threshold
PROFILE_C_MAX_RETAIL_CHATTER = 2           # not retail-pumped
PROFILE_C_MAX_MARKET_CAP_JPY = 200e9       # "small to mid" — exclude large/mega names

# Valuation sanity bounds — a P/E this low on a profitable company is almost
# always a one-off (gain on sale, deconsolidation, tax credit) inflating EPS
# temporarily. Flag it so the desk verifies before trusting the "cheap" signal.
# Note: a P/E this low could also be a data artifact (stale price, wrong
# shares outstanding). Either way, the percentile composite can't catch it
# because P/E and P/B share the same price/market-cap numerator — a bad
# numerator breaks both at once.
VALUATION_PE_SUSPECT_FLOOR = 3.0
VALUATION_PB_SUSPECT_FLOOR = 0.2


def valuation_sanity_flag(pe: float | None, pb: float | None) -> str:
    """Return a verify-this flag if valuation metrics look suspect."""
    flags = []
    if pe is not None and pe < VALUATION_PE_SUSPECT_FLOOR:
        flags.append(f"PE_SUSPECT<{VALUATION_PE_SUSPECT_FLOOR}")
    if pb is not None and pb < VALUATION_PB_SUSPECT_FLOOR:
        flags.append(f"PB_SUSPECT<{VALUATION_PB_SUSPECT_FLOOR}")
    return "|".join(flags)


def passes_profile_c_unseen_filter(
    attention_score: float | None,
    retail_chatter: int | None,
    market_cap_jpy: float | None,
) -> tuple[bool, str]:
    """Profile C unseen gate — must actually be unseen to belong here.

    Applied BEFORE the quality gate. A name only enters Profile C if all
    three are true:
      - attention_score <= PROFILE_C_MAX_ATTENTION  (low coverage of the drop)
      - retail_chatter <= PROFILE_C_MAX_RETAIL_CHATTER  (not retail-pumped)
      - market_cap < PROFILE_C_MAX_MARKET_CAP_JPY  ("small to mid")
    """
    if attention_score is not None and attention_score > PROFILE_C_MAX_ATTENTION:
        return False, f"attention {attention_score} > {PROFILE_C_MAX_ATTENTION} (not thin)"
    if retail_chatter is not None and retail_chatter > PROFILE_C_MAX_RETAIL_CHATTER:
        return False, f"retail_chatter {retail_chatter} > {PROFILE_C_MAX_RETAIL_CHATTER} (pumped)"
    if market_cap_jpy is not None and market_cap_jpy > PROFILE_C_MAX_MARKET_CAP_JPY:
        return False, f"mcap ¥{market_cap_jpy/1e9:.0f}B > ¥{PROFILE_C_MAX_MARKET_CAP_JPY/1e9:.0f}B (too large)"
    return True, "passes unseen filter"


def passes_profile_c_strict_gate(
    quality_metrics: dict, latest_revenue_jpy: float | None
) -> tuple[bool, str]:
    """Profile C gate: returns (pass, reason_if_failed).

    The strict hard floors that make valuation-only ranking safe — they
    eliminate cheap-for-a-reason names (value traps) by construction.
    Names that fail any check are excluded from Profile C entirely.
    """
    if not quality_metrics.get("data_ok"):
        return False, f"quality data not ok: {quality_metrics.get('reason', '?')}"

    op_pos = quality_metrics.get("op_positive_count_3y", 0)
    if op_pos < PROFILE_C_REQUIRED_OP_POSITIVE_YEARS:
        return False, f"OP positive only {op_pos}/{PROFILE_C_REQUIRED_OP_POSITIVE_YEARS} years"

    eq = quality_metrics.get("equity_ratio_latest")
    if eq is None or eq < PROFILE_C_MIN_EQUITY_RATIO_PCT:
        return False, f"equity ratio {eq}% < {PROFILE_C_MIN_EQUITY_RATIO_PCT}%"

    cagr = quality_metrics.get("revenue_cagr_3y")
    if cagr is None or cagr < PROFILE_C_MIN_CAGR_3Y_PCT:
        return False, f"3yr CAGR {cagr}% < {PROFILE_C_MIN_CAGR_3Y_PCT}%"

    if latest_revenue_jpy is None or latest_revenue_jpy < PROFILE_C_MIN_REVENUE_JPY:
        rev_str = f"¥{latest_revenue_jpy/1e9:.1f}B" if latest_revenue_jpy else "?"
        return False, f"latest revenue {rev_str} < ¥{PROFILE_C_MIN_REVENUE_JPY/1e9:.0f}B floor"

    return True, "passes all Profile C strict floors"
