"""V1 score magnitude calibration — is a HIGHER V1 score actually more reliable?

V1 outputs a continuous score from ~-3 to +3. We currently use thresholds
(>= 1.5 → growth_likely, <= -1.0 → growth_unlikely). But we've never asked:
does the score MAGNITUDE correlate with precision?

If V1 score >= 2.5 has much higher hit rate than V1 score 1.5-2.0, we have
a free confidence layer with no new data needed.

This is fresh ground — different from the failed post-hoc confidence layer
because it uses V1's internal score directly, not derived indicators.
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent

JGAAP_ORIG = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697"]
JGAAP_OOS = ["4063","4716","4751","6861"]
JGAAP_EXT = ["3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
             "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"]
TRAIN_TICKERS = set(JGAAP_ORIG + JGAAP_OOS)
TEST_TICKERS = set(JGAAP_EXT)
ALL_JGAAP = TRAIN_TICKERS | TEST_TICKERS


def _f(v):
    if v is None: return None
    try: return float(v)
    except: return None


def _wilson(hits, n, z=1.96):
    if n == 0: return (None, None)
    p = hits/n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    r = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den
    return (max(0.0,(c-r)*100), min(100.0,(c+r)*100))


def annual_val(items, key, fy):
    matches = [i for i in items if i["line_item_key"]==key and i["fiscal_year"]==fy
               and i.get("fiscal_quarter") is None and i.get("accounting_standard")=="Japan GAAP"]
    if not matches: return None
    return _f(matches[0]["value"])


def detect_events(ticker):
    p = ROOT / "data" / "tempest" / ticker / "financials_line_items.json"
    if not p.exists(): return []
    with open(p, encoding="utf-8") as f:
        items = json.load(f)["data"]
    fys = sorted(set(i["fiscal_year"] for i in items if i.get("fiscal_quarter") is None
                     and i.get("accounting_standard")=="Japan GAAP"))
    events = []
    for fy in fys:
        prev_eq = annual_val(items, "total_equity", fy-1)
        prev_ni = annual_val(items, "profit_loss", fy-1) or annual_val(items, "profit_attributable_to_owners_of_parent", fy-1)
        rev = annual_val(items, "net_sales", fy)
        impair = annual_val(items, "impairment_loss", fy)
        if impair and impair > 0:
            if (prev_eq and prev_eq>0 and impair/prev_eq*100>=1.0) or (prev_ni and abs(prev_ni)>0 and impair/abs(prev_ni)*100>=5.0):
                events.append((ticker, fy, "impairment"))
        extra = annual_val(items, "extraordinary_loss", fy)
        if extra and extra > 0:
            if (rev and rev>0 and extra/rev*100>=5.0) or (prev_ni and abs(prev_ni)>0 and extra/abs(prev_ni)*100>=10.0):
                events.append((ticker, fy, "extraordinary"))
    return events


def multi_axis_outcome(rev_yoy, op_yoy, stock_5d, has_bad):
    pos = neg = 0
    if rev_yoy is not None:
        if rev_yoy >= 3.0: pos += 1
        elif rev_yoy <= -3.0: neg += 1
    if op_yoy is not None:
        if op_yoy >= 5.0: pos += 1
        elif op_yoy <= -5.0: neg += 1
    if stock_5d is not None:
        if stock_5d >= 5.0: pos += 1
        elif stock_5d <= -5.0: neg += 1
    if has_bad: return "negative"
    if neg >= 2: return "negative"
    if pos >= 2: return "positive"
    return "mixed"


def score_pred(judgment, outcome):
    if judgment == "uncertain": return "abstain"
    if judgment == "growth_likely" and outcome == "positive": return "hit"
    if judgment == "growth_unlikely" and outcome == "negative": return "hit"
    return "miss"


def extract_indicators(ticker, pred_pair_label, outcome_fy):
    cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                       f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not cache_files: return None
    with open(cache_files[-1], encoding="utf-8") as f:
        d = json.load(f)
    out = {k: None for k in ["peer_gap","op_margin_level","goodwill","cfo_ni",
                              "op_profit_yoy_pred","op_profit_yoy_outcome"]}
    for pair in d.get("pairs", []):
        if pair.get("history_only"): continue
        lbl = f"FY{pair['prev_fiscal_year']}->FY{pair['curr_fiscal_year']}"
        if lbl == pred_pair_label:
            pc = pair.get("peer_comparison") or {}
            pc_my = pc.get("my") or {}
            pc_med = pc.get("sector_median") or {}
            if pc_my.get("op_margin_pct") is not None and pc_med.get("op_margin_pct") is not None:
                out["peer_gap"] = pc_my["op_margin_pct"] - pc_med["op_margin_pct"]
            out["op_margin_level"] = pc_my.get("op_margin_pct")
            bs_hist = pair.get("bs_quality_history") or []
            if bs_hist:
                out["goodwill"] = bs_hist[-1].get("goodwill_to_equity_pct")
            cfo_r = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
            out["cfo_ni"] = cfo_r.get("curr")
            out["op_profit_yoy_pred"] = pair.get("op_profit_delta_pct")
        if outcome_fy is not None and pair.get("curr_fiscal_year") == outcome_fy:
            out["op_profit_yoy_outcome"] = pair.get("op_profit_delta_pct")
    return out


def v1_score_and_verdict(ind):
    """V1 (4 useful indicators, goodwill dropped per audit). Returns (score, verdict)."""
    score = 0.0
    if ind["peer_gap"] is not None:
        if ind["peer_gap"] > 10.0: score += 1.0
        elif ind["peer_gap"] < -5.0: score -= 1.0
    if ind["op_margin_level"] is not None:
        if ind["op_margin_level"] > 15.0: score += 1.0
        elif ind["op_margin_level"] < 5.0: score -= 1.0
    if ind["cfo_ni"] is not None:
        if ind["cfo_ni"] > 0.8: score += 1.0
        elif ind["cfo_ni"] < 0.5: score -= 1.0
    if ind["op_profit_yoy_pred"] is not None and ind["op_profit_yoy_pred"] < -10.0:
        score -= 1.5
    if score >= 1.5: verdict = "growth_likely"
    elif score <= -1.0: verdict = "growth_unlikely"
    else: verdict = "uncertain"
    return round(score, 2), verdict


def precision_block(rows, score_key):
    h = sum(1 for r in rows if r[score_key] == "hit")
    m = sum(1 for r in rows if r[score_key] == "miss")
    c = h + m
    prec = h/c*100 if c else None
    ci = _wilson(h, c)
    return h, m, c, prec, ci


def main():
    print("V1 score magnitude as confidence layer\n", flush=True)

    event_reg = defaultdict(list)
    for tk in ALL_JGAAP:
        for ev in detect_events(tk):
            event_reg[(ev[0], ev[1])].append(ev[2])

    all_preds = []
    for path in [ROOT/"outputs"/"rolling_window_backtest.json",
                 ROOT/"outputs"/"out_of_sample_rolling_window.json",
                 ROOT/"outputs"/"jgaap_extension_rolling_window.json"]:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        all_preds.extend(d["scored_predictions"])

    enriched = []
    for p in all_preds:
        tk = p["ticker"]
        if tk not in ALL_JGAAP: continue
        try: outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except: outcome_fy = None
        ind = extract_indicators(tk, p["prediction_pair"], outcome_fy)
        if ind is None: continue
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
        outcome = multi_axis_outcome(p.get("rev_delta_pct"), ind["op_profit_yoy_outcome"],
                                     p.get("stock_5d_pct"), bool(evs_2y))
        v1_score, v1_verdict = v1_score_and_verdict(ind)
        enriched.append({
            "ticker": tk, "split": "train" if tk in TRAIN_TICKERS else "test",
            "prediction_pair": p["prediction_pair"],
            "v1_score": v1_score, "v1_verdict": v1_verdict,
            "v1_outcome_score": score_pred(v1_verdict, outcome),
            "outcome": outcome,
        })

    print(f"Total: {len(enriched)} predictions ({len([e for e in enriched if e['split']=='train'])} TRAIN, "
          f"{len([e for e in enriched if e['split']=='test'])} TEST)\n", flush=True)

    # ========================================================================
    # Distribution of V1 scores per verdict
    # ========================================================================
    print("=" * 90, flush=True)
    print("V1 score distribution per verdict (FULL cohort)", flush=True)
    print("=" * 90, flush=True)

    for cls in ("growth_likely", "growth_unlikely"):
        sub = [e for e in enriched if e["v1_verdict"] == cls]
        scores = sorted([e["v1_score"] for e in sub])
        if scores:
            print(f"\n  {cls} (n={len(sub)}):", flush=True)
            print(f"    range: [{min(scores):+.1f}, {max(scores):+.1f}]", flush=True)
            print(f"    quartiles: Q1={scores[len(scores)//4]:+.1f}  median={scores[len(scores)//2]:+.1f}  "
                  f"Q3={scores[3*len(scores)//4]:+.1f}", flush=True)

    # ========================================================================
    # Precision by score-magnitude bin
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("Precision by V1 score magnitude bin", flush=True)
    print("=" * 90, flush=True)

    # Bins for growth_likely (positive scores)
    gl_bins = [
        ("borderline (+1.5)",   lambda s: 1.5 <= s < 2.0),
        ("medium (+2.0)",       lambda s: 2.0 <= s < 2.5),
        ("high (+2.5)",         lambda s: 2.5 <= s < 3.0),
        ("very high (+3.0+)",   lambda s: s >= 3.0),
    ]
    # Bins for growth_unlikely (negative scores)
    gu_bins = [
        ("borderline (-1.0)",   lambda s: -1.5 < s <= -1.0),
        ("medium (-1.5)",       lambda s: -2.0 < s <= -1.5),
        ("high (-2.0)",         lambda s: -2.5 < s <= -2.0),
        ("very high (-2.5+)",   lambda s: s <= -2.5),
    ]

    for cohort_name, cohort in [("FULL", enriched),
                                ("TEST (held-out)", [e for e in enriched if e["split"]=="test"])]:
        print(f"\n  Cohort: {cohort_name} (n={len(cohort)})", flush=True)
        print(f"\n  {'V1 verdict':<18}{'Score bin':<22}{'n_in_bin':<10}{'precision':<28}", flush=True)
        print("  " + "-" * 76, flush=True)
        for cls, bins in [("growth_likely", gl_bins), ("growth_unlikely", gu_bins)]:
            for bin_name, bin_fn in bins:
                sub = [e for e in cohort if e["v1_verdict"] == cls and bin_fn(e["v1_score"])]
                h, m, c, p, ci = precision_block(sub, "v1_outcome_score")
                if c > 0:
                    print(f"  {cls:<18}{bin_name:<22}{len(sub):<10}"
                          f"{p:5.1f}% ({h}/{c}) CI [{ci[0]:.1f}-{ci[1]:.1f}]", flush=True)
                elif len(sub) > 0:
                    print(f"  {cls:<18}{bin_name:<22}{len(sub):<10}"
                          f"n/a (no scored cases)", flush=True)

    # ========================================================================
    # Simpler view — high vs low magnitude
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("Simplified: HIGH magnitude (≥2.5 or ≤-2.0) vs BORDERLINE (1.5-2.0 or -1.5 to -1.0)", flush=True)
    print("=" * 90, flush=True)
    for cohort_name, cohort in [("FULL", enriched),
                                ("TEST (held-out)", [e for e in enriched if e["split"]=="test"])]:
        print(f"\n  Cohort: {cohort_name}", flush=True)
        for cls in ("growth_likely", "growth_unlikely"):
            high_thr = 2.5 if cls == "growth_likely" else -2.0
            border_lo = 1.5 if cls == "growth_likely" else -1.5
            border_hi = 2.0 if cls == "growth_likely" else -1.0
            if cls == "growth_likely":
                high = [e for e in cohort if e["v1_verdict"]==cls and e["v1_score"] >= high_thr]
                border = [e for e in cohort if e["v1_verdict"]==cls and border_lo <= e["v1_score"] < border_hi]
                all_sub = [e for e in cohort if e["v1_verdict"]==cls]
            else:
                high = [e for e in cohort if e["v1_verdict"]==cls and e["v1_score"] <= high_thr]
                border = [e for e in cohort if e["v1_verdict"]==cls and border_hi >= e["v1_score"] > border_lo]
                all_sub = [e for e in cohort if e["v1_verdict"]==cls]
            for label, sub in [("ALL", all_sub), ("HIGH", high), ("BORDERLINE", border)]:
                h, m, c, p, ci = precision_block(sub, "v1_outcome_score")
                if c > 0:
                    print(f"    {cls:<20}{label:<14}n={len(sub):<4}precision={p:5.1f}% ({h}/{c}) "
                          f"CI [{ci[0]:.1f}-{ci[1]:.1f}]", flush=True)
                else:
                    print(f"    {cls:<20}{label:<14}n={len(sub):<4}precision=n/a", flush=True)

    # Save
    out = ROOT / "outputs" / "v1_score_magnitude_results.json"
    out.write_text(json.dumps({"n": len(enriched), "rows": enriched},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
