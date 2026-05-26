"""TRAIN-only pattern discovery + clean held-out evaluation.

Methodology:
  1. Restrict the candidate-indicator sweep to TRAIN tickers (15 = ORIG + OOS)
  2. Identify the best (indicator, direction, threshold) per verdict class
     using ONLY training data
  3. PRE-REGISTER those thresholds (write them to file before evaluating)
  4. Evaluate the chosen thresholds on TEST tickers (30 = EXTENSION)
  5. Report whatever comes out — no re-tuning after seeing test results

This removes the residual leakage in V1.5: previously the thresholds for
rev_yoy_pred ≥ +5% / ≤ -5% were chosen looking at the full cohort. Now
they're chosen using only the training set.
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
from pathlib import Path
from collections import defaultdict
from datetime import datetime

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


def multi_axis_outcome(rev_yoy, op_yoy, stock_5d, has_bad_event):
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
    if has_bad_event: return "negative"
    if neg >= 2: return "negative"
    if pos >= 2: return "positive"
    return "mixed"


def score_pred(judgment, outcome):
    if outcome == "n/a": return "n/a"
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
    out = {k: None for k in [
        "peer_gap","op_margin_level","goodwill","cfo_ni",
        "op_margin_trend_pp","rev_yoy_pred","top_segment_share","herfindahl",
        "op_profit_yoy_pred","op_profit_yoy_outcome","net_margin_level",
        "rev_vs_sector_pp","operating_leverage","inventory_days",
    ]}
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
            out["op_margin_trend_pp"] = pc_my.get("op_margin_pp_delta")
            out["net_margin_level"] = pc_my.get("net_margin_pct")
            if pc_my.get("revenue_yoy_pct") is not None and pc_med.get("rev_yoy_pct") is not None:
                out["rev_vs_sector_pp"] = pc_my["revenue_yoy_pct"] - pc_med["rev_yoy_pct"]
            bs_hist = pair.get("bs_quality_history") or []
            if bs_hist:
                out["goodwill"] = bs_hist[-1].get("goodwill_to_equity_pct")
                out["top_segment_share"] = bs_hist[-1].get("top_segment_share_pct")
                out["herfindahl"] = bs_hist[-1].get("herfindahl_index")
                out["inventory_days"] = bs_hist[-1].get("inventory_days")
            cfo_r = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
            out["cfo_ni"] = cfo_r.get("curr")
            out["op_profit_yoy_pred"] = pair.get("op_profit_delta_pct")
            out["rev_yoy_pred"] = pair.get("rev_delta_pct") or pc_my.get("revenue_yoy_pct")
            if out["op_profit_yoy_pred"] is not None and out["rev_yoy_pred"] is not None and abs(out["rev_yoy_pred"]) > 1.0:
                out["operating_leverage"] = out["op_profit_yoy_pred"] / out["rev_yoy_pred"]
        if outcome_fy is not None and pair.get("curr_fiscal_year") == outcome_fy:
            out["op_profit_yoy_outcome"] = pair.get("op_profit_delta_pct")
    return out


INDICATOR_SWEEPS = {
    "peer_gap":              [("ge", t) for t in (0, 5, 10, 15)] + [("le", t) for t in (0, -5, -10)],
    "op_margin_level":       [("ge", t) for t in (10, 15, 20)] + [("le", t) for t in (10, 5, 0)],
    "goodwill":              [("le", t) for t in (50, 30, 20)] + [("ge", t) for t in (30, 50)],
    "cfo_ni":                [("ge", t) for t in (0.5, 0.8, 1.0, 1.2)] + [("le", t) for t in (0.5, 0.0)],
    "net_margin_level":      [("ge", t) for t in (5, 10, 15)] + [("le", t) for t in (5, 0)],
    "op_margin_trend_pp":    [("ge", t) for t in (0, 1, 2)] + [("le", t) for t in (0, -1, -2, -5)],
    "rev_vs_sector_pp":      [("ge", t) for t in (0, 5, 10)] + [("le", t) for t in (0, -5)],
    "top_segment_share":     [("le", t) for t in (60, 70, 80)] + [("ge", t) for t in (80, 90)],
    "herfindahl":            [("ge", t) for t in (6000, 8000)],
    "inventory_days":        [("le", t) for t in (30, 60)] + [("ge", t) for t in (60, 90)],
    "operating_leverage":    [("ge", t) for t in (1.0, 2.0)] + [("le", t) for t in (1.0, 0.0)],
    "rev_yoy_pred":          [("ge", t) for t in (0, 5, 10, 15)] + [("le", t) for t in (0, -5, -10)],
    "op_profit_yoy_pred":    [("ge", t) for t in (0, 5, 10)] + [("le", t) for t in (0, -10, -25)],
}


def evaluate_filter(rows, ind, direction, threshold, llm_class):
    target = [r for r in rows if r["llm_verdict"] == llm_class]
    kept = []
    for r in target:
        v = r.get(ind)
        if v is None:
            kept.append(r); continue
        if direction == "ge" and v >= threshold: kept.append(r)
        elif direction == "le" and v <= threshold: kept.append(r)
    h = sum(1 for r in kept if r["llm_v_outcome"] == "hit")
    m = sum(1 for r in kept if r["llm_v_outcome"] == "miss")
    c = h + m
    prec = h/c*100 if c else None
    ci = _wilson(h, c)
    return {"kept": len(kept), "scored": c, "hit": h, "miss": m,
            "precision": prec, "ci_lo": ci[0], "ci_hi": ci[1],
            "baseline_n": len(target)}


def main():
    print("TRAIN-only pattern discovery → pre-registered held-out evaluation\n", flush=True)

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
        enriched.append({
            "ticker": tk, "split": "train" if tk in TRAIN_TICKERS else "test",
            "prediction_pair": p["prediction_pair"],
            "llm_verdict": p["judgment"],
            "outcome": outcome,
            "llm_v_outcome": score_pred(p["judgment"], outcome),
            **ind,
        })

    train = [e for e in enriched if e["split"] == "train"]
    test = [e for e in enriched if e["split"] == "test"]
    print(f"TRAIN: {len(train)} predictions  TEST: {len(test)} predictions\n", flush=True)

    # Baselines per split
    def class_baseline(rows, cls):
        sub = [r for r in rows if r["llm_verdict"] == cls]
        h = sum(1 for r in sub if r["llm_v_outcome"] == "hit")
        m = sum(1 for r in sub if r["llm_v_outcome"] == "miss")
        c = h + m
        return {"n": len(sub), "hit": h, "miss": m, "scored": c,
                "precision": h/c*100 if c else 0}

    print("=" * 90, flush=True)
    print("STEP 1 — Baselines on TRAIN and TEST (LLM verdict, no filtering)", flush=True)
    print("=" * 90, flush=True)
    train_baselines = {}; test_baselines = {}
    for cls in ("growth_likely", "growth_unlikely"):
        tb = class_baseline(train, cls); train_baselines[cls] = tb
        te = class_baseline(test, cls); test_baselines[cls] = te
        ci_tr = _wilson(tb["hit"], tb["scored"])
        ci_te = _wilson(te["hit"], te["scored"])
        print(f"\n  {cls}:", flush=True)
        print(f"    TRAIN: {tb['precision']:.1f}% ({tb['hit']}/{tb['scored']}) "
              f"CI [{ci_tr[0]:.1f}-{ci_tr[1]:.1f}]  (n_total={tb['n']})", flush=True)
        print(f"    TEST:  {te['precision']:.1f}% ({te['hit']}/{te['scored']}) "
              f"CI [{ci_te[0]:.1f}-{ci_te[1]:.1f}]  (n_total={te['n']})", flush=True)

    # ========================================================================
    # STEP 2 — Discover best filters on TRAIN ONLY
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("STEP 2 — Best filters DISCOVERED ON TRAIN ONLY (15 tickers, 38 predictions)", flush=True)
    print("=" * 90, flush=True)

    chosen_filters = {}
    for cls in ("growth_likely", "growth_unlikely"):
        candidates = []
        for ind, sweeps in INDICATOR_SWEEPS.items():
            for direction, threshold in sweeps:
                r = evaluate_filter(train, ind, direction, threshold, cls)
                if r["precision"] is None: continue
                if r["kept"] / max(r["baseline_n"], 1) < 0.5: continue  # require ≥50% retention
                if r["scored"] < 5: continue  # require ≥5 scored cases
                lift = r["precision"] - train_baselines[cls]["precision"]
                retention = r["kept"] / max(r["baseline_n"], 1)
                # Score: prefer high lift AND high retention
                score = lift * retention
                candidates.append({
                    "indicator": ind, "direction": direction, "threshold": threshold,
                    "kept": r["kept"], "scored": r["scored"], "hit": r["hit"], "miss": r["miss"],
                    "precision": r["precision"], "lift": lift, "retention_pct": retention*100, "score": score,
                })
        ranked = sorted(candidates, key=lambda x: -x["score"])
        print(f"\n  Top 5 single filters on TRAIN for {cls.upper()}:", flush=True)
        print(f"  Baseline TRAIN precision: {train_baselines[cls]['precision']:.1f}%", flush=True)
        for r in ranked[:5]:
            op = ">=" if r["direction"] == "ge" else "<="
            print(f"    {r['indicator']:<22} {op} {r['threshold']:<6.1f}  "
                  f"n_scored={r['scored']:<3}  prec={r['precision']:5.1f}% "
                  f"lift={r['lift']:+5.1f}pp  retent={r['retention_pct']:.0f}%", flush=True)
        # Pre-register the top filter for held-out evaluation
        if ranked:
            chosen_filters[cls] = ranked[0]
            print(f"  PRE-REGISTERED for held-out test → {chosen_filters[cls]['indicator']} "
                  f"{'>=' if chosen_filters[cls]['direction']=='ge' else '<='} "
                  f"{chosen_filters[cls]['threshold']}", flush=True)

    # Write pre-registration BEFORE evaluating on test
    preregister_path = ROOT / "outputs" / "train_only_preregistered_filters.json"
    preregister_path.write_text(json.dumps({
        "registered_at": datetime.now().isoformat(),
        "train_baselines": train_baselines,
        "chosen_filters": chosen_filters,
        "note": "These filters were chosen using TRAIN data only. Held-out TEST evaluation follows.",
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[pre-registered] {preregister_path}", flush=True)

    # ========================================================================
    # STEP 3 — Apply chosen filters to TEST set (the moment of truth)
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("STEP 3 — Apply pre-registered filters to held-out TEST set (30 tickers)", flush=True)
    print("=" * 90, flush=True)

    for cls in ("growth_likely", "growth_unlikely"):
        if cls not in chosen_filters: continue
        f = chosen_filters[cls]
        r_test = evaluate_filter(test, f["indicator"], f["direction"], f["threshold"], cls)
        r_train = evaluate_filter(train, f["indicator"], f["direction"], f["threshold"], cls)
        op = ">=" if f["direction"] == "ge" else "<="
        train_baseline = train_baselines[cls]["precision"]
        test_baseline = test_baselines[cls]["precision"]
        ci_te = _wilson(r_test["hit"], r_test["scored"])

        print(f"\n  {cls}: filter = {f['indicator']} {op} {f['threshold']}", flush=True)
        print(f"  ───────────────────────────────────────────────────────────────────", flush=True)
        print(f"  TRAIN: baseline {train_baseline:5.1f}%  filtered {r_train['precision']:5.1f}%  "
              f"({r_train['hit']}/{r_train['scored']})  "
              f"lift {r_train['precision']-train_baseline:+5.1f}pp", flush=True)
        print(f"  TEST:  baseline {test_baseline:5.1f}%  filtered {r_test['precision']:5.1f}%  "
              f"({r_test['hit']}/{r_test['scored']})  CI [{ci_te[0]:.1f}-{ci_te[1]:.1f}]  "
              f"lift {r_test['precision']-test_baseline:+5.1f}pp", flush=True)
        if r_train['precision'] - train_baseline > 0 and r_test['precision'] - test_baseline > 0:
            print(f"  → SURVIVED: lift positive on both TRAIN and TEST", flush=True)
        elif r_train['precision'] - train_baseline > 0:
            print(f"  → IN-SAMPLE ONLY: lift was positive on TRAIN, evaporated on TEST", flush=True)
        else:
            print(f"  → INVALID: didn't lift on TRAIN to begin with", flush=True)

    # Save full enriched data
    out_path = ROOT / "outputs" / "train_only_discovery_results.json"
    out_path.write_text(json.dumps({
        "n_train": len(train), "n_test": len(test),
        "train_baselines": train_baselines,
        "test_baselines": test_baselines,
        "chosen_filters": chosen_filters,
        "rows": enriched,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)


if __name__ == "__main__":
    main()
