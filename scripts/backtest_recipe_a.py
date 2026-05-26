"""Recipe A backtest — 2-axis ground truth re-scoring.

Re-scores the 28 confident predictions from the existing rolling-window
backtest against a stricter 2-axis ground truth:
  Axis 1: Operating profit YoY (already in cached pair data)
  Axis 2: TOPIX-adjusted forward stock return (filing-date to filing-date)

Methodology pre-registered at outputs/recipe_a_methodology.md.
Thresholds locked BEFORE this script ran. No LLM calls.

Reports precision under three threshold settings (±3%, ±5%, ±10%) with
Wilson 95% CIs to quantify how robust the result is to threshold choice.
"""
from __future__ import annotations
import json
import sys
import io
import math
from pathlib import Path
from datetime import date, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "outputs" / "agent_cache"
ROLLING_PATH = ROOT / "outputs" / "rolling_window_backtest.json"
OUT_PATH = ROOT / "outputs" / "recipe_a_results.json"
PRICES_DIR = ROOT / "data" / "tempest"
TOPIX_TICKER = "1306"  # Nomura TOPIX-100 ETF
THRESHOLDS = [3.0, 5.0, 10.0]


def _load_prices_adjusted(ticker: str) -> dict[str, float]:
    """Return {date_str: close_adj} with auto-split adjustment.

    Scans for daily ratios < 0.5 or > 2.0 (split-like jumps) and applies
    the inverse factor to all prior dates so the series is split-adjusted
    forward. This is a heuristic; documented as a known limitation.
    """
    p = PRICES_DIR / ticker / "prices.json"
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    rows = sorted(d["data"], key=lambda r: r["date"])
    # Detect splits: when close_today / close_yesterday < 0.5 or > 2.0,
    # treat as a split and back-adjust prior closes.
    closes = [float(r["close"]) for r in rows]
    dates = [r["date"] for r in rows]
    adj_factor = 1.0
    adjusted: list[float] = [0.0] * len(closes)
    # Walk backward, applying adjustments forward to past dates
    for i in range(len(closes) - 1, 0, -1):
        adjusted[i] = closes[i] * adj_factor
        ratio = closes[i] / closes[i - 1]
        if ratio < 0.5 or ratio > 2.0:
            # split: adjust all prior dates so the past matches the new scale
            split_factor = ratio
            adj_factor *= split_factor
    adjusted[0] = closes[0] * adj_factor
    return {dates[i]: adjusted[i] for i in range(len(closes))}


def _nearest_price_on_or_after(prices: dict[str, float], target: str) -> float | None:
    """Return the close on or after `target` date. None if past series end."""
    keys = sorted(k for k in prices.keys() if k >= target)
    return prices[keys[0]] if keys else None


def _wilson_ci(hits: int, n: int, z: float = 1.96) -> tuple[float, float] | tuple[None, None]:
    """Wilson 95% CI for a binomial proportion."""
    if n == 0:
        return (None, None)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    rad = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, (center - rad) * 100), min(100.0, (center + rad) * 100))


def _load_pair_data(ticker: str) -> list[dict]:
    """Load the agent's full-history pair data (cutoff=none)."""
    matches = sorted(CACHE_DIR.glob(f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json"))
    if not matches:
        raise FileNotFoundError(f"No cached pair data for {ticker}")
    with open(matches[-1], encoding="utf-8") as f:
        d = json.load(f)
    pairs = [p for p in d.get("pairs", []) if not p.get("history_only")]
    pairs.sort(key=lambda p: p.get("curr_period_end", ""))
    return pairs


def _score_outcome(op_yoy: float | None, topix_adj_ret: float | None,
                   threshold: float) -> str:
    """Return 'positive', 'negative', or 'mixed' under given threshold."""
    if op_yoy is None or topix_adj_ret is None:
        return "n/a"
    if op_yoy >= threshold and topix_adj_ret >= threshold:
        return "positive"
    if op_yoy <= -threshold and topix_adj_ret <= -threshold:
        return "negative"
    return "mixed"


def _score_prediction(judgment: str, outcome: str) -> str:
    if outcome == "n/a":
        return "n/a"
    if judgment == "uncertain":
        return "abstain"
    if judgment == "growth_likely" and outcome == "positive":
        return "hit"
    if judgment == "growth_unlikely" and outcome == "negative":
        return "hit"
    return "miss"


def main() -> int:
    print("Recipe A backtest — 2-axis ground truth", flush=True)
    print(f"Methodology: {ROOT / 'outputs' / 'recipe_a_methodology.md'}", flush=True)
    print(f"Thresholds (locked): ±{THRESHOLDS[0]}%, ±{THRESHOLDS[1]}%, ±{THRESHOLDS[2]}%\n",
          flush=True)

    # Load existing rolling-window predictions (judgments are frozen)
    with open(ROLLING_PATH, encoding="utf-8") as f:
        roll = json.load(f)
    preds_in = roll["scored_predictions"]
    print(f"Loaded {len(preds_in)} predictions from rolling-window backtest.\n", flush=True)

    # Pre-load TOPIX
    print("Loading TOPIX (1306) prices…", flush=True)
    topix_prices = _load_prices_adjusted(TOPIX_TICKER)
    print(f"  {len(topix_prices)} dates, range {min(topix_prices)}..{max(topix_prices)}\n",
          flush=True)

    # Cache per-ticker pair data and prices
    pair_cache: dict[str, list[dict]] = {}
    price_cache: dict[str, dict[str, float]] = {}

    enriched: list[dict] = []
    for row in preds_in:
        tk = row["ticker"]
        pred_pair_label = row["prediction_pair"]
        outcome_pair_label = row["outcome_pair"]
        judgment = row["judgment"]

        if tk not in pair_cache:
            try:
                pair_cache[tk] = _load_pair_data(tk)
            except FileNotFoundError as e:
                print(f"  [{tk}] {e}", flush=True)
                pair_cache[tk] = []
        if tk not in price_cache:
            price_cache[tk] = _load_prices_adjusted(tk)

        pairs = pair_cache[tk]
        # Match by FY labels (e.g., "FY2021->FY2022")
        def match(p, label):
            return f"FY{p['prev_fiscal_year']}->FY{p['curr_fiscal_year']}" == label

        pred_pair = next((p for p in pairs if match(p, pred_pair_label)), None)
        out_pair = next((p for p in pairs if match(p, outcome_pair_label)), None)
        if pred_pair is None or out_pair is None:
            print(f"  [{tk}] missing pair: pred={pred_pair_label}, out={outcome_pair_label}",
                  flush=True)
            continue

        # Axis 1: operating profit YoY at the outcome pair
        op_yoy = out_pair.get("op_profit_delta_pct")

        # Axis 2: TOPIX-adjusted forward stock return
        # window: pred_pair.curr_filing_date → out_pair.curr_filing_date
        start_date = pred_pair.get("curr_filing_date")
        end_date = out_pair.get("curr_filing_date")
        stock_ret = None
        topix_ret = None
        topix_adj = None
        if start_date and end_date and start_date < end_date:
            tk_p_start = _nearest_price_on_or_after(price_cache[tk], start_date)
            tk_p_end = _nearest_price_on_or_after(price_cache[tk], end_date)
            tx_p_start = _nearest_price_on_or_after(topix_prices, start_date)
            tx_p_end = _nearest_price_on_or_after(topix_prices, end_date)
            if tk_p_start and tk_p_end and tx_p_start and tx_p_end:
                stock_ret = (tk_p_end / tk_p_start - 1) * 100
                topix_ret = (tx_p_end / tx_p_start - 1) * 100
                topix_adj = stock_ret - topix_ret

        enriched.append({
            "ticker": tk,
            "prediction_pair": pred_pair_label,
            "outcome_pair": outcome_pair_label,
            "judgment": judgment,
            "old_verdict": row.get("verdict"),
            "old_rev_delta_pct": row.get("rev_delta_pct"),
            "old_stock_5d_pct": row.get("stock_5d_pct"),
            "op_profit_yoy_pct": op_yoy,
            "filing_start": start_date,
            "filing_end": end_date,
            "raw_stock_ret_pct": round(stock_ret, 2) if stock_ret is not None else None,
            "topix_ret_pct": round(topix_ret, 2) if topix_ret is not None else None,
            "topix_adj_ret_pct": round(topix_adj, 2) if topix_adj is not None else None,
        })

    print(f"\nEnriched {len(enriched)} rows with new axes.\n", flush=True)

    # Score under each threshold
    summary: dict[str, dict] = {}
    for thr in THRESHOLDS:
        scored: list[dict] = []
        for e in enriched:
            outcome = _score_outcome(e["op_profit_yoy_pct"], e["topix_adj_ret_pct"], thr)
            verdict = _score_prediction(e["judgment"], outcome)
            scored.append({**e, "outcome_at_thr": outcome, "verdict_at_thr": verdict})

        # Aggregate
        total = len(scored)
        n_a = sum(1 for s in scored if s["verdict_at_thr"] == "n/a")
        abstain = sum(1 for s in scored if s["verdict_at_thr"] == "abstain")
        hit = sum(1 for s in scored if s["verdict_at_thr"] == "hit")
        miss = sum(1 for s in scored if s["verdict_at_thr"] == "miss")
        confident = hit + miss
        overall_prec = (hit / confident * 100) if confident else None
        overall_ci = _wilson_ci(hit, confident)

        # By class
        by_class: dict[str, dict] = {}
        for cls in ("growth_likely", "growth_unlikely", "uncertain"):
            cls_rows = [s for s in scored if s["judgment"] == cls]
            cls_hit = sum(1 for s in cls_rows if s["verdict_at_thr"] == "hit")
            cls_miss = sum(1 for s in cls_rows if s["verdict_at_thr"] == "miss")
            cls_abs = sum(1 for s in cls_rows if s["verdict_at_thr"] == "abstain")
            cls_na = sum(1 for s in cls_rows if s["verdict_at_thr"] == "n/a")
            cls_conf = cls_hit + cls_miss
            cls_prec = (cls_hit / cls_conf * 100) if cls_conf else None
            cls_ci = _wilson_ci(cls_hit, cls_conf)
            by_class[cls] = {
                "n": len(cls_rows), "hit": cls_hit, "miss": cls_miss,
                "abstain": cls_abs, "n_a": cls_na,
                "precision_pct": round(cls_prec, 1) if cls_prec is not None else None,
                "ci_95_pct": (round(cls_ci[0], 1), round(cls_ci[1], 1))
                              if cls_ci[0] is not None else None,
            }

        summary[f"thr_{int(thr)}"] = {
            "threshold_pct": thr, "total": total,
            "hit": hit, "miss": miss, "abstain": abstain, "n_a": n_a,
            "confident": confident,
            "overall_precision_pct": round(overall_prec, 1) if overall_prec is not None else None,
            "overall_ci_95_pct": (round(overall_ci[0], 1), round(overall_ci[1], 1))
                                  if overall_ci[0] is not None else None,
            "by_class": by_class,
            "rows": scored,
        }

    # Print summary table
    print("=" * 100, flush=True)
    print("RECIPE A — RESULTS UNDER THREE THRESHOLD SETTINGS", flush=True)
    print("=" * 100, flush=True)
    print(f"\n{'Threshold':<12}{'Class':<20}{'N':<5}{'Hit':<5}{'Miss':<5}"
          f"{'Abst':<6}{'N/A':<5}{'Prec':<8}{'95% CI':<20}", flush=True)
    print("-" * 100, flush=True)
    for thr_key, s in summary.items():
        thr_lbl = f"±{int(s['threshold_pct'])}%"
        # Overall
        prec = s["overall_precision_pct"]
        ci = s["overall_ci_95_pct"]
        prec_s = f"{prec:.1f}%" if prec is not None else "n/a"
        ci_s = f"[{ci[0]:.1f}-{ci[1]:.1f}]" if ci else "n/a"
        print(f"{thr_lbl:<12}{'OVERALL':<20}{s['total']:<5}{s['hit']:<5}{s['miss']:<5}"
              f"{s['abstain']:<6}{s['n_a']:<5}{prec_s:<8}{ci_s:<20}", flush=True)
        for cls, c in s["by_class"].items():
            prec = c["precision_pct"]
            ci = c["ci_95_pct"]
            prec_s = f"{prec:.1f}%" if prec is not None else "n/a"
            ci_s = f"[{ci[0]:.1f}-{ci[1]:.1f}]" if ci else "n/a"
            print(f"{'':<12}{cls:<20}{c['n']:<5}{c['hit']:<5}{c['miss']:<5}"
                  f"{c['abstain']:<6}{c['n_a']:<5}{prec_s:<8}{ci_s:<20}", flush=True)
        print("-" * 100, flush=True)

    # FCF supplementary sidebar — compute CFO/capex YoY where available
    # For now we just count cases where op_yoy and topix_adj agreed
    # (which is when the outcome is positive or negative, not mixed)
    print("\nFCF SUPPLEMENTARY DIAGNOSTIC (NOT scored, sidebar only):", flush=True)
    for thr_key, s in summary.items():
        agreed = sum(1 for r in s["rows"]
                     if r["outcome_at_thr"] in ("positive", "negative"))
        print(f"  At {thr_key}: {agreed}/{s['total']} cases had op_yoy and TOPIX-adj agree "
              f"(outcome 'positive' or 'negative', not 'mixed')", flush=True)

    OUT_PATH.write_text(json.dumps({
        "methodology": "recipe_a_methodology.md",
        "thresholds_tested": THRESHOLDS,
        "topix_ticker": TOPIX_TICKER,
        "n_predictions": len(enriched),
        "stock_window": "filing-to-filing (pred_pair.curr_filing_date to outcome_pair.curr_filing_date)",
        "summary": summary,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
