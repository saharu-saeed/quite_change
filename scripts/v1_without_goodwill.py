"""V1 without goodwill — verify that dropping goodwill doesn't hurt precision.

If goodwill is dead weight (as per_class_weights.py found), removing it
should leave precision unchanged or slightly improved.
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


# V1 verdict with and without goodwill
def v1_verdict(ind, include_goodwill=True):
    th = {"peer_gap_pos":10.0,"peer_gap_neg":-5.0,"margin_pos":15.0,"margin_neg":5.0,
          "goodwill_neg":30.0,"cfo_pos":0.8,"cfo_neg":0.5,"profit_crash":-10.0,
          "score_pos_threshold":1.5,"score_neg_threshold":-1.0}
    w = {"peer_gap":1.0,"margin":1.0,"goodwill":0.5,"cfo":1.0,"profit_crash":1.5}
    score = 0.0
    if ind["peer_gap"] is not None:
        if ind["peer_gap"] > th["peer_gap_pos"]: score += w["peer_gap"]
        elif ind["peer_gap"] < th["peer_gap_neg"]: score -= w["peer_gap"]
    if ind["op_margin_level"] is not None:
        if ind["op_margin_level"] > th["margin_pos"]: score += w["margin"]
        elif ind["op_margin_level"] < th["margin_neg"]: score -= w["margin"]
    if include_goodwill and ind["goodwill"] is not None and ind["goodwill"] > th["goodwill_neg"]:
        score -= w["goodwill"]
    if ind["cfo_ni"] is not None:
        if ind["cfo_ni"] > th["cfo_pos"]: score += w["cfo"]
        elif ind["cfo_ni"] < th["cfo_neg"]: score -= w["cfo"]
    if ind["op_profit_yoy_pred"] is not None and ind["op_profit_yoy_pred"] < th["profit_crash"]:
        score -= w["profit_crash"]
    if score >= th["score_pos_threshold"]: return "growth_likely"
    if score <= th["score_neg_threshold"]: return "growth_unlikely"
    return "uncertain"


def precision_block(rows, score_key):
    h = sum(1 for r in rows if r[score_key] == "hit")
    m = sum(1 for r in rows if r[score_key] == "miss")
    c = h + m
    prec = h/c*100 if c else None
    ci = _wilson(h, c)
    return h, m, c, prec, ci


def fmt(h, m, c, prec, ci):
    if prec is None: return "n/a"
    return f"{prec:5.1f}% ({h}/{c}) CI [{ci[0]:.1f}-{ci[1]:.1f}]"


def main():
    print("V1 with goodwill vs V1 without goodwill — verification\n", flush=True)

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
        v1_with = v1_verdict(ind, include_goodwill=True)
        v1_no_gw = v1_verdict(ind, include_goodwill=False)
        enriched.append({
            "ticker": tk, "split": "train" if tk in TRAIN_TICKERS else "test",
            "v1_with": v1_with, "v1_no_gw": v1_no_gw,
            "v1_with_score": score_pred(v1_with, outcome),
            "v1_no_gw_score": score_pred(v1_no_gw, outcome),
            "goodwill": ind["goodwill"],
            "goodwill_present": ind["goodwill"] is not None,
            "goodwill_triggered": ind["goodwill"] is not None and ind["goodwill"] > 30.0,
        })

    # Goodwill coverage stats
    gw_present = sum(1 for e in enriched if e["goodwill_present"])
    gw_triggered = sum(1 for e in enriched if e["goodwill_triggered"])
    print(f"Goodwill data present:  {gw_present}/{len(enriched)} = {gw_present/len(enriched)*100:.0f}%", flush=True)
    print(f"Goodwill rule fired:    {gw_triggered}/{len(enriched)} = {gw_triggered/len(enriched)*100:.0f}%", flush=True)

    # How many verdicts changed?
    changed = sum(1 for e in enriched if e["v1_with"] != e["v1_no_gw"])
    print(f"Verdicts changed when goodwill removed: {changed}/{len(enriched)}\n", flush=True)

    train = [e for e in enriched if e["split"] == "train"]
    test = [e for e in enriched if e["split"] == "test"]

    def report(cohort, label):
        print(f"\n  {label}  (n={len(cohort)})", flush=True)
        print(f"  {'Class':<22}{'V1 (with goodwill)':<36}{'V1 (no goodwill)':<36}", flush=True)
        print("  " + "-" * 96, flush=True)
        for cls in ("growth_likely", "growth_unlikely"):
            v1_sub = [e for e in cohort if e["v1_with"] == cls]
            no_sub = [e for e in cohort if e["v1_no_gw"] == cls]
            h1,m1,c1,p1,ci1 = precision_block(v1_sub, "v1_with_score")
            h2,m2,c2,p2,ci2 = precision_block(no_sub, "v1_no_gw_score")
            delta = f"{p2-p1:+.1f}pp" if (p1 is not None and p2 is not None) else "n/a"
            print(f"  {cls:<22}{fmt(h1,m1,c1,p1,ci1):<36}{fmt(h2,m2,c2,p2,ci2):<28}{delta}", flush=True)

    print("=" * 100, flush=True)
    print("Precision comparison", flush=True)
    print("=" * 100, flush=True)
    report(enriched, "FULL")
    report(train, "TRAIN")
    report(test, "TEST — held-out")

    # Show the cases where goodwill rule fires
    print("\n" + "=" * 100, flush=True)
    print("Cases where the goodwill rule fired (goodwill > 30%)", flush=True)
    print("=" * 100, flush=True)
    fired = [e for e in enriched if e["goodwill_triggered"]]
    print(f"\nn = {len(fired)}", flush=True)
    if fired:
        for e in fired:
            print(f"  {e['ticker']}: goodwill={e['goodwill']:.0f}%, V1_with={e['v1_with']}, V1_no={e['v1_no_gw']}, "
                  f"verdict_change={'YES' if e['v1_with']!=e['v1_no_gw'] else 'no'}", flush=True)

    out = ROOT / "outputs" / "v1_without_goodwill_results.json"
    out.write_text(json.dumps({"n": len(enriched), "rows": enriched},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
