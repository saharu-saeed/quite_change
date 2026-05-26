"""Idea 4 Phase 1 — structured-data diagnostic on 56 confident JGAAP calls.

Reads cached pair data for each confident prediction, extracts the 10
pre-registered factors (see outputs/idea4_factor_preregistration.md),
cross-tabs against Recipe A v2 HIT/MISS outcome, computes effect sizes.

No LLM calls. Pure structured-data analysis.
"""
from __future__ import annotations
import json
import sys
import io
import glob
import statistics
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent

JGAAP_ORIG = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697"]
JGAAP_OOS = ["4063","4716","4751","6861"]
JGAAP_EXT = ["3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
             "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"]
ALL_JGAAP = set(JGAAP_ORIG + JGAAP_OOS + JGAAP_EXT)


def load_pairs(ticker):
    matches = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                  f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not matches:
        return []
    with open(matches[-1], encoding="utf-8") as f:
        d = json.load(f)
    return [p for p in d.get("pairs", []) if not p.get("history_only")]


def annual_line_value(items_list, key, fy, std="Japan GAAP"):
    matches = [i for i in items_list
               if i["line_item_key"] == key and i["fiscal_year"] == fy
               and i.get("fiscal_quarter") is None
               and i.get("accounting_standard") == std]
    if not matches:
        return None
    v = matches[0]["value"]
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def detect_events_for_ticker(ticker):
    p = ROOT / "data" / "tempest" / ticker / "financials_line_items.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        items = json.load(f)["data"]
    fys = sorted(set(i["fiscal_year"] for i in items
                     if i.get("fiscal_quarter") is None
                     and i.get("accounting_standard") == "Japan GAAP"))
    events = []
    for fy in fys:
        prev_eq = annual_line_value(items, "total_equity", fy - 1)
        prev_ni = annual_line_value(items, "profit_loss", fy - 1) or \
                  annual_line_value(items, "profit_attributable_to_owners_of_parent", fy - 1)
        rev = annual_line_value(items, "net_sales", fy)
        impair = annual_line_value(items, "impairment_loss", fy)
        if impair and impair > 0:
            if (prev_eq and prev_eq > 0 and impair / prev_eq * 100 >= 1.0) or \
               (prev_ni and abs(prev_ni) > 0 and impair / abs(prev_ni) * 100 >= 5.0):
                events.append((ticker, fy, "impairment"))
        extra = annual_line_value(items, "extraordinary_loss", fy)
        if extra and extra > 0:
            if (rev and rev > 0 and extra / rev * 100 >= 5.0) or \
               (prev_ni and abs(prev_ni) > 0 and extra / abs(prev_ni) * 100 >= 10.0):
                events.append((ticker, fy, "extraordinary"))
    return events


def extract_factors(ticker, pred_pair, all_pairs):
    """Pull the 10 pre-registered factors for one prediction."""
    f = {"ticker": ticker, "prediction_pair":
         f"FY{pred_pair['prev_fiscal_year']}->FY{pred_pair['curr_fiscal_year']}"}

    pl_margins = pred_pair.get("pl_yoy", {}).get("margins", {})
    op_m = pl_margins.get("op_margin_pct", {})
    f["op_margin_curr_pct"] = op_m.get("curr")
    f["op_margin_pp_delta"] = op_m.get("pp_delta")

    # trajectory: slope of margin across 3 years (FY[N-1], FY[N-1], FY[N])
    # For pair FY[N-1]->FY[N], we have prev (=FY[N-1]) and curr (=FY[N]).
    # Need previous pair FY[N-2]->FY[N-1] for FY[N-2] margin.
    prev_fy = pred_pair.get("prev_fiscal_year")
    prev_pair = next((pp for pp in all_pairs if pp.get("curr_fiscal_year") == prev_fy), None)
    op_margins_3y = []
    if prev_pair:
        prev_op = prev_pair.get("pl_yoy", {}).get("margins", {}).get("op_margin_pct", {})
        if prev_op.get("prev") is not None:
            op_margins_3y.append(prev_op["prev"])
        if op_m.get("prev") is not None:
            op_margins_3y.append(op_m["prev"])
    else:
        if op_m.get("prev") is not None:
            op_margins_3y.append(op_m["prev"])
    if op_m.get("curr") is not None:
        op_margins_3y.append(op_m["curr"])

    # Linear slope if we have 3 points
    if len(op_margins_3y) >= 2:
        n = len(op_margins_3y)
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(op_margins_3y) / n
        num = sum((xs[i] - x_mean) * (op_margins_3y[i] - y_mean) for i in range(n))
        den = sum((x - x_mean) ** 2 for x in xs)
        slope = num / den if den != 0 else 0
        f["margin_trajectory_slope"] = slope
        if slope > 0.5:
            f["margin_trajectory_dir"] = "improving"
        elif slope < -0.5:
            f["margin_trajectory_dir"] = "declining"
        else:
            f["margin_trajectory_dir"] = "flat"
    else:
        f["margin_trajectory_slope"] = None
        f["margin_trajectory_dir"] = "insufficient_data"

    f["revenue_yoy_pct"] = pred_pair.get("revenue_delta_pct")

    cfo_ratios = pred_pair.get("cashflow_yoy", {}).get("ratios", {}).get("cfo_to_ni", {})
    f["cfo_to_ni_ratio_curr"] = cfo_ratios.get("curr")

    bs_hist = pred_pair.get("bs_quality_history", [])
    curr_bs = bs_hist[-1] if bs_hist else {}
    f["goodwill_to_equity_pct"] = curr_bs.get("goodwill_to_equity_pct")
    f["herfindahl_index"] = curr_bs.get("herfindahl_index")
    f["top_segment_share_pct"] = curr_bs.get("top_segment_share_pct")

    f["stock_5d_return_pct"] = pred_pair.get("stock_5d_return_pct")

    pc = pred_pair.get("peer_comparison") or {}
    pc_my = pc.get("my") or {}
    pc_median = pc.get("sector_median") or {}
    f["peer_op_margin_gap_pp"] = pc_my.get("op_margin_pp_delta")
    if pc_my.get("op_margin_pct") is not None and pc_median.get("op_margin_pct") is not None:
        f["peer_op_margin_level_gap_pp"] = pc_my["op_margin_pct"] - pc_median["op_margin_pct"]
    else:
        f["peer_op_margin_level_gap_pp"] = None

    return f


# === Score under Recipe A v2 ===
def score_v2(op_yoy, has_bad_event, threshold=5.0):
    if op_yoy is None:
        return "n/a"
    if op_yoy <= -threshold or has_bad_event:
        return "negative"
    if op_yoy >= threshold:
        return "positive"
    return "mixed"


def score_pred(judgment, outcome):
    if outcome == "n/a":
        return "n/a"
    if judgment == "uncertain":
        return "abstain"
    if judgment == "growth_likely" and outcome == "positive":
        return "hit"
    if judgment == "growth_unlikely" and outcome == "negative":
        return "hit"
    return "miss"


def main():
    print("Idea 4 Phase 1 — Structured-Data Diagnostic\n", flush=True)
    print(f"Cohort: {len(ALL_JGAAP)} JGAAP tickers", flush=True)

    # Build event registry
    event_reg = defaultdict(list)
    for tk in ALL_JGAAP:
        for ev in detect_events_for_ticker(tk):
            event_reg[(ev[0], ev[1])].append(ev[2])

    # Load all predictions
    all_preds = []
    for path in [ROOT / "outputs" / "rolling_window_backtest.json",
                 ROOT / "outputs" / "out_of_sample_rolling_window.json",
                 ROOT / "outputs" / "jgaap_extension_rolling_window.json"]:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        all_preds.extend(d["scored_predictions"])

    # Extract factors + score for JGAAP confident calls
    pair_cache = {}
    diagnostic_rows = []
    for p in all_preds:
        tk = p["ticker"]
        if tk not in ALL_JGAAP:
            continue
        if p["judgment"] == "uncertain":
            continue
        if tk not in pair_cache:
            pair_cache[tk] = load_pairs(tk)
        pairs = pair_cache[tk]
        pred_pair = next(
            (pp for pp in pairs
             if f"FY{pp['prev_fiscal_year']}->FY{pp['curr_fiscal_year']}" == p["prediction_pair"]),
            None)
        out_pair = next(
            (pp for pp in pairs
             if f"FY{pp['prev_fiscal_year']}->FY{pp['curr_fiscal_year']}" == p["outcome_pair"]),
            None)
        if pred_pair is None or out_pair is None:
            continue
        factors = extract_factors(tk, pred_pair, pairs)
        op_yoy = out_pair.get("op_profit_delta_pct")
        try:
            outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except Exception:
            outcome_fy = None
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
        outcome = score_v2(op_yoy, bool(evs_2y))
        verdict = score_pred(p["judgment"], outcome)
        diagnostic_rows.append({**factors,
                                 "judgment": p["judgment"], "verdict": verdict,
                                 "outcome": outcome,
                                 "op_profit_yoy_next": op_yoy,
                                 "has_bad_event_2y": bool(evs_2y)})

    print(f"Total confident JGAAP rows: {len(diagnostic_rows)}", flush=True)

    # Compute effect sizes per factor, per class
    factor_keys = [
        "op_margin_curr_pct",
        "op_margin_pp_delta",
        "margin_trajectory_slope",
        "revenue_yoy_pct",
        "cfo_to_ni_ratio_curr",
        "goodwill_to_equity_pct",
        "herfindahl_index",
        "top_segment_share_pct",
        "stock_5d_return_pct",
        "peer_op_margin_gap_pp",
        "peer_op_margin_level_gap_pp",
    ]

    print("\n" + "=" * 110, flush=True)
    print("EFFECT SIZES — mean factor value among HITs vs MISSes, per class", flush=True)
    print("=" * 110, flush=True)
    findings = {}
    for cls in ("growth_likely", "growth_unlikely"):
        print(f"\n--- {cls} ---", flush=True)
        hits = [r for r in diagnostic_rows if r["judgment"] == cls and r["verdict"] == "hit"]
        misses = [r for r in diagnostic_rows if r["judgment"] == cls and r["verdict"] == "miss"]
        print(f"  n_hits={len(hits)}, n_misses={len(misses)}", flush=True)
        findings[cls] = {"n_hits": len(hits), "n_misses": len(misses), "factors": {}}
        for fk in factor_keys:
            hit_vals = [r[fk] for r in hits if r.get(fk) is not None]
            miss_vals = [r[fk] for r in misses if r.get(fk) is not None]
            hit_mean = statistics.mean(hit_vals) if hit_vals else None
            miss_mean = statistics.mean(miss_vals) if miss_vals else None
            delta = None
            if hit_mean is not None and miss_mean is not None:
                delta = hit_mean - miss_mean
            findings[cls]["factors"][fk] = {
                "hit_n": len(hit_vals), "miss_n": len(miss_vals),
                "hit_mean": hit_mean, "miss_mean": miss_mean,
                "delta_hit_minus_miss": delta,
            }
            # Print
            h = f"{hit_mean:8.2f}" if hit_mean is not None else "      n/a"
            m = f"{miss_mean:8.2f}" if miss_mean is not None else "      n/a"
            dl = f"{delta:+8.2f}" if delta is not None else "      n/a"
            print(f"    {fk:30s}  HITs (n={len(hit_vals):2d}): {h}  MISSes (n={len(miss_vals):2d}): {m}  Δ: {dl}",
                  flush=True)

    # Save diagnostic
    out_path = ROOT / "outputs" / "idea4_diagnostic_results.json"
    out_path.write_text(json.dumps({
        "preregistration": "outputs/idea4_factor_preregistration.md",
        "n_total_rows": len(diagnostic_rows),
        "findings": findings,
        "per_call_rows": diagnostic_rows,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)


if __name__ == "__main__":
    main()
