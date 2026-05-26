"""Quality screen for Quiet Change Agent v2.

The previous universe filter only checked revenue_yoy_pct > 1% — a thin
quality bar that admits low-margin, weak-balance-sheet companies whose
"growth" is one lucky quarter. This module sits BEFORE / alongside the
universe filter and ranks tickers by composite quality, so the downstream
attention + divergence gates operate on a pool of genuinely-good-and-
overlooked names rather than "cheap and unknown for a reason" noise.

Design (three refinements baked in, from this project's own lessons):

  1. SECTOR-AWARE — same lesson as the divergence gate. A 3% operating-
     margin distributor is healthy in its sector; a 5% software firm is
     weak in its sector. Score every metric as a within-sector percentile.
     If a sector has fewer than SECTOR_MIN_PEERS members, fall back to
     the global cross-sector distribution for that metric.

  2. OPERATING PROFIT (not net income) — net income is noisy with one-
     time items (litigation provisions, asset impairments). Operating
     profitability is what we care about. Allow ONE down-year for OP
     (2 of 3 positive) so a single write-down doesn't kill a quality
     compounder.

  3. SCORED (not gated) — composite percentile rank 0-100. Cutoff is
     set after seeing the distribution, not hard-coded.

Hard floors are intentionally minimal — they only kick out genuinely
broken companies:
  - At least 3 years of annual financial history (need the trend)
  - Operating profit > 0 in at least 2 of last 3 years
  - Equity > 0 (not insolvent)
  - net_sales > 0 in latest year

Everything else is relative scoring.

Metrics (all higher-is-better):
  - revenue_cagr_3y    : (latest_sales / sales_3y_ago)^(1/3) - 1
  - op_margin_latest   : operating_profit / net_sales (latest year)
  - op_margin_trend_pp : latest margin minus mean of 2 prior years
  - equity_ratio_latest: equity / total_assets
  - roe_latest         : profit / equity

Composite = mean of 5 within-sector percentile ranks.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TEMPEST_DIR = ROOT / "data" / "tempest"

# Need at least N years of annual history to compute the trend metrics.
ANNUAL_HISTORY_MIN = 3

# Sectors with fewer than this many qualifying peers fall back to the
# global distribution for percentile-ranking. Same logic as the divergence
# gate's low_confidence flag.
SECTOR_MIN_PEERS = 5

# Five quality metrics, all higher-is-better.
QUALITY_METRICS = [
    "revenue_cagr_3y",
    "op_margin_latest",
    "op_margin_trend_pp",
    "equity_ratio_latest",
    "roe_latest",
]


def _load_annuals(ticker: str) -> list[dict] | None:
    """Read annual financial rows from Tempest cache, newest-first."""
    try:
        fin = json.load(open(TEMPEST_DIR / ticker / "financials.json", encoding="utf-8"))["data"]
    except Exception:
        return None
    annuals = [r for r in fin if r.get("fiscal_quarter") in (None, "null")]
    annuals.sort(key=lambda r: r.get("period_end") or "", reverse=True)
    return annuals or None


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_quality_metrics(ticker: str) -> dict[str, Any]:
    """Compute raw quality metrics for one ticker.

    Returns a dict with:
        data_ok: bool                   — passed hard floor checks
        reason:  str (if data_ok=False) — why it failed
        latest_period_end, years_used, op_positive_count_3y
        revenue_cagr_3y, op_margin_latest, op_margin_trend_pp,
        equity_ratio_latest, roe_latest
    """
    annuals = _load_annuals(ticker)
    if not annuals:
        return {"ticker": ticker, "data_ok": False, "reason": "no annuals in cache"}
    if len(annuals) < ANNUAL_HISTORY_MIN:
        return {
            "ticker": ticker, "data_ok": False,
            "reason": f"only {len(annuals)} annual rows (need {ANNUAL_HISTORY_MIN})",
        }

    a3 = annuals[:ANNUAL_HISTORY_MIN]  # 3 most recent years
    latest = a3[0]

    sales_latest = _to_float(latest.get("net_sales"))
    sales_3y_ago = _to_float(a3[-1].get("net_sales"))
    op_latest = _to_float(latest.get("operating_profit"))
    equity_latest = _to_float(latest.get("equity"))
    total_assets_latest = _to_float(latest.get("total_assets"))
    profit_latest = _to_float(latest.get("profit"))

    # Hard floors
    if sales_latest is None or sales_latest <= 0:
        return {"ticker": ticker, "data_ok": False, "reason": "net_sales missing/non-positive"}
    if sales_3y_ago is None or sales_3y_ago <= 0:
        return {"ticker": ticker, "data_ok": False, "reason": "3y-ago sales missing"}
    if op_latest is None:
        return {"ticker": ticker, "data_ok": False, "reason": "operating_profit missing"}
    if equity_latest is None or equity_latest <= 0:
        return {"ticker": ticker, "data_ok": False, "reason": "equity missing/non-positive"}

    op_values = [_to_float(r.get("operating_profit")) for r in a3]
    op_positive_count = sum(1 for v in op_values if v is not None and v > 0)
    if op_positive_count < 2:
        return {
            "ticker": ticker, "data_ok": False,
            "reason": f"OP positive only {op_positive_count}/3 years",
        }

    revenue_cagr_3y = (sales_latest / sales_3y_ago) ** (1.0 / 3.0) - 1.0
    op_margin_latest = op_latest / sales_latest

    prior_margins: list[float] = []
    for r in a3[1:]:
        s = _to_float(r.get("net_sales"))
        op = _to_float(r.get("operating_profit"))
        if s and s > 0 and op is not None:
            prior_margins.append(op / s)
    op_margin_trend = (op_margin_latest - statistics.mean(prior_margins)) if prior_margins else 0.0

    equity_ratio_latest = (
        equity_latest / total_assets_latest
        if total_assets_latest and total_assets_latest > 0
        else None
    )
    roe_latest = (profit_latest / equity_latest) if profit_latest is not None else None

    return {
        "ticker": ticker,
        "data_ok": True,
        "latest_period_end": latest.get("period_end"),
        "years_used": ANNUAL_HISTORY_MIN,
        "op_positive_count_3y": op_positive_count,
        "revenue_cagr_3y": round(revenue_cagr_3y * 100, 2),       # %
        "op_margin_latest": round(op_margin_latest * 100, 2),     # %
        "op_margin_trend_pp": round(op_margin_trend * 100, 2),    # pp change
        "equity_ratio_latest": (
            round(equity_ratio_latest * 100, 2) if equity_ratio_latest is not None else None
        ),
        "roe_latest": round(roe_latest * 100, 2) if roe_latest is not None else None,
    }


def _percentile_rank(value: float, sorted_values: list[float]) -> float:
    """0-100 percentile rank of value within sorted_values (ascending).

    Mid-rank for ties (so identical values get the same percentile, not
    one ranked above the other arbitrarily).
    """
    if not sorted_values:
        return 50.0
    n = len(sorted_values)
    below = sum(1 for v in sorted_values if v < value)
    equal = sum(1 for v in sorted_values if v == value)
    return ((below + equal / 2.0) / n) * 100.0


def compute_sector_norms(rows: list[dict]) -> dict[str, dict[str, list[float]]]:
    """For each sector_33_name, collect sorted metric distributions for ranking."""
    norms: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        if not r.get("data_ok"):
            continue
        sector = r.get("sector_33_name") or "_unknown"
        bucket = norms.setdefault(sector, {m: [] for m in QUALITY_METRICS})
        for m in QUALITY_METRICS:
            v = r.get(m)
            if v is not None:
                bucket[m].append(float(v))
    for bucket in norms.values():
        for m in bucket:
            bucket[m].sort()
    return norms


def compute_global_norms(rows: list[dict]) -> dict[str, list[float]]:
    """Cross-sector distribution per metric — fallback for thin sectors."""
    out: dict[str, list[float]] = {m: [] for m in QUALITY_METRICS}
    for r in rows:
        if not r.get("data_ok"):
            continue
        for m in QUALITY_METRICS:
            v = r.get(m)
            if v is not None:
                out[m].append(float(v))
    for m in out:
        out[m].sort()
    return out


def score_quality(
    row: dict,
    sector_norms: dict[str, dict[str, list[float]]],
    global_norms: dict[str, list[float]],
) -> dict[str, Any]:
    """Composite quality score: mean of within-sector percentile ranks across 5 metrics."""
    sector = row.get("sector_33_name") or "_unknown"
    sector_bucket = sector_norms.get(sector, {})
    per_metric: dict[str, float] = {}
    used_fallback: list[str] = []

    for m in QUALITY_METRICS:
        v = row.get(m)
        if v is None:
            per_metric[m] = 50.0
            continue
        sector_vals = sector_bucket.get(m, [])
        if len(sector_vals) >= SECTOR_MIN_PEERS:
            per_metric[m] = _percentile_rank(float(v), sector_vals)
        else:
            per_metric[m] = _percentile_rank(float(v), global_norms.get(m, []))
            used_fallback.append(m)

    composite = round(sum(per_metric.values()) / len(per_metric), 2)
    return {
        "composite_score": composite,
        "per_metric_percentile": {k: round(v, 1) for k, v in per_metric.items()},
        "sector_peers": len(sector_bucket.get("revenue_cagr_3y", [])),
        "used_global_fallback_for": used_fallback,
    }


def quality_screen(tickers: list[str]) -> list[dict]:
    """Apply quality screen to a list of tickers. Returns rows sorted by composite desc.

    Rows with data_ok=False are appended at the end (no score, but reason given).
    """
    from app.subagents.quiet_change_peers import load_sector_info  # local import to avoid cycle

    rows: list[dict] = []
    for t in tickers:
        m = compute_quality_metrics(t)
        sec = load_sector_info(t)
        m["sector_33_name"] = sec.get("sector_33_name")
        m["sector_17_name"] = sec.get("sector_17_name")
        m["scale_category"] = sec.get("scale_category")
        rows.append(m)

    valid = [r for r in rows if r.get("data_ok")]
    excluded = [r for r in rows if not r.get("data_ok")]

    sector_norms = compute_sector_norms(valid)
    global_norms = compute_global_norms(valid)

    for r in valid:
        r["quality_score"] = score_quality(r, sector_norms, global_norms)

    valid.sort(key=lambda r: -r["quality_score"]["composite_score"])
    return valid + excluded


# --------------------------------------------------------------------------
# Watch-list composite ranking
# --------------------------------------------------------------------------
# Replaces the strict YES/no dual_gate as the *primary* ranking signal.
# Rationale (from the post-chemicals review): "literally zero coverage" was
# selecting for obscure/uninvestable names, not for "the specific drop is
# under-analysed." Lead with company-specific signals (divergence + quality)
# and let attention rank/tie-break, not gate.
#
# Each input row should already carry:
#   r["sector_rel"]["sector_relative_pp"]    — divergence pp (negative = idio-down)
#   r["quality"]["quality_score"]["composite_score"]  — 0-100 quality
#   r["attention_score"]                      — lower = more under-covered
#
# We still keep `dual_gate.quiet_change_candidate` on each row as an
# *empirical-finding* annotation — useful for "across N sectors, the strict
# gate produced K hits", but no longer the headline.

WATCHLIST_WEIGHTS = {
    "divergence":  0.35,   # company-specific signal
    "quality":     0.35,   # company-specific signal
    "attention":   0.30,   # OVERLOOKED-thesis enforcer — must actively demote noticed names
}
# Rebalanced from 0.45/0.45/0.10 after the first aggregated sweep showed
# the list had drifted from "overlooked" to "biggest quality-adjusted fallers."
# At 0.10 attention was a tie-break, not a filter — a clearly-noticed candy
# brand (カンロ, attn +16) ranked #2 on the strength of divergence + quality
# alone. Bumping attention to 0.30 makes high-attention names actively pulled
# down, so the composite enforces the "overlooked" thesis the way the product
# is supposed to. Cost: low-attention/small-divergence names rank higher
# (which is correct — that's the actual target shape).


def _percentile_in_sorted(value: float, sorted_values: list[float]) -> float:
    """0-100 percentile of value within sorted_values (ascending)."""
    if not sorted_values:
        return 50.0
    below = sum(1 for v in sorted_values if v < value)
    equal = sum(1 for v in sorted_values if v == value)
    return ((below + equal / 2.0) / len(sorted_values)) * 100.0


def compute_watchlist_ranking(rows: list[dict]) -> None:
    """Mutates each row in place, adding:
        r["watchlist_composite"]: float 0-100
        r["watchlist_components"]: {div_signal, qual_signal, attn_signal}
    Higher composite = stronger watch-list candidate.

    Signal directions:
        - Divergence: more negative pp → stronger signal (idiosyncratic-down)
        - Quality:    higher composite → stronger signal
        - Attention:  lower score → stronger signal (thinner coverage of the anomaly)
    """
    divs = sorted(
        r["sector_rel"]["sector_relative_pp"]
        for r in rows
        if r.get("sector_rel", {}).get("sector_relative_pp") is not None
    )
    quals = sorted(
        r["quality"]["quality_score"]["composite_score"]
        for r in rows
        if r.get("quality", {}).get("data_ok")
    )
    attns = sorted(
        r["attention_score"] for r in rows if "attention_score" in r
    )

    for r in rows:
        d = r.get("sector_rel", {}).get("sector_relative_pp")
        q = (
            r["quality"]["quality_score"]["composite_score"]
            if r.get("quality", {}).get("data_ok")
            else None
        )
        a = r.get("attention_score")

        # invert direction so "higher percentile = stronger signal"
        div_signal = (100 - _percentile_in_sorted(d, divs)) if d is not None else 50.0
        qual_signal = _percentile_in_sorted(q, quals) if q is not None else 50.0
        attn_signal = (100 - _percentile_in_sorted(a, attns)) if a is not None else 50.0

        composite = (
            WATCHLIST_WEIGHTS["divergence"] * div_signal
            + WATCHLIST_WEIGHTS["quality"] * qual_signal
            + WATCHLIST_WEIGHTS["attention"] * attn_signal
        )

        r["watchlist_composite"] = round(composite, 1)
        r["watchlist_components"] = {
            "div_signal": round(div_signal, 1),
            "qual_signal": round(qual_signal, 1),
            "attn_signal": round(attn_signal, 1),
            "weights": WATCHLIST_WEIGHTS,
        }
