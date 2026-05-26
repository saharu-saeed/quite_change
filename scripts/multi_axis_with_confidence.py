"""Multi-axis outcome × confidence layer cross-tab.

Takes the 56 confident JGAAP calls and reports precision broken down by
confidence label (HIGH/MEDIUM/LOW) under the new multi-axis methodology.
Compares with the previous Recipe A v2 × confidence breakdown.
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent

JGAAP_ORIG = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697"]
JGAAP_OOS = ["4063","4716","4751","6861"]
JGAAP_EXT = ["3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
             "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"]
ALL_JGAAP = set(JGAAP_ORIG + JGAAP_OOS + JGAAP_EXT)


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


def annual_val(items, key, fy, std="Japan GAAP"):
    matches = [i for i in items if i["line_item_key"]==key and i["fiscal_year"]==fy
               and i.get("fiscal_quarter") is None and i.get("accounting_standard")==std]
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


def confidence_label(peer_gap_pp, goodwill_pct, cfo_ni_ratio):
    peer_pass = peer_gap_pp is not None and peer_gap_pp > 10.0
    goodwill_pass = goodwill_pct is None or goodwill_pct < 30.0  # missing = pass
    cfo_pass = cfo_ni_ratio is not None and cfo_ni_ratio > 0.8
    score = sum([peer_pass, goodwill_pass, cfo_pass])
    if score == 3: return "HIGH"
    if score == 2: return "MEDIUM"
    return "LOW"


def multi_axis_outcome(rev_yoy, op_yoy, stock_5d, has_bad_event):
    pos_votes = 0; neg_votes = 0
    if rev_yoy is not None:
        if rev_yoy >= 3.0: pos_votes += 1
        elif rev_yoy <= -3.0: neg_votes += 1
    if op_yoy is not None:
        if op_yoy >= 5.0: pos_votes += 1
        elif op_yoy <= -5.0: neg_votes += 1
    if stock_5d is not None:
        if stock_5d >= 5.0: pos_votes += 1
        elif stock_5d <= -5.0: neg_votes += 1
    if has_bad_event:
        return "negative"
    if neg_votes >= 2:
        return "negative"
    if pos_votes >= 2:
        return "positive"
    return "mixed"


def recipe_a_v2_outcome(op_yoy, has_bad):
    if op_yoy is None: return "n/a"
    if op_yoy <= -5.0 or has_bad: return "negative"
    if op_yoy >= 5.0: return "positive"
    return "mixed"


def score_pred(judgment, outcome):
    if outcome == "n/a": return "n/a"
    if judgment == "uncertain": return "abstain"
    if judgment == "growth_likely" and outcome == "positive": return "hit"
    if judgment == "growth_unlikely" and outcome == "negative": return "hit"
    return "miss"


def main():
    print("Multi-axis × confidence layer cross-tab\n", flush=True)

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

    scored = []
    for p in all_preds:
        tk = p["ticker"]
        if tk not in ALL_JGAAP: continue
        if p["judgment"] == "uncertain": continue
        rev_yoy = p.get("rev_delta_pct")
        stock_5d = p.get("stock_5d_pct")
        try:
            outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except: outcome_fy = None
        # Load cached pair data for op_profit_delta + confidence factors
        cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                           f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
        op_yoy = None; peer_gap = None; goodwill = None; cfo_ni = None
        pred_pair_label = p["prediction_pair"]
        if cache_files:
            with open(cache_files[-1], encoding="utf-8") as f:
                d = json.load(f)
            for pair in d.get("pairs", []):
                if pair.get("history_only"): continue
                lbl = f"FY{pair['prev_fiscal_year']}->FY{pair['curr_fiscal_year']}"
                # Op_profit_delta_pct comes from OUTCOME pair
                if pair.get("curr_fiscal_year") == outcome_fy:
                    op_yoy = pair.get("op_profit_delta_pct")
                # Confidence factors come from PREDICTION pair
                if lbl == pred_pair_label:
                    pc = pair.get("peer_comparison") or {}
                    pc_my = pc.get("my") or {}
                    pc_med = pc.get("sector_median") or {}
                    if pc_my.get("op_margin_pct") is not None and pc_med.get("op_margin_pct") is not None:
                        peer_gap = pc_my["op_margin_pct"] - pc_med["op_margin_pct"]
                    bs_hist = pair.get("bs_quality_history") or []
                    if bs_hist:
                        goodwill = bs_hist[-1].get("goodwill_to_equity_pct")
                    cfo_ratios = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
                    cfo_ni = cfo_ratios.get("curr")

        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])

        ma_outcome = multi_axis_outcome(rev_yoy, op_yoy, stock_5d, bool(evs_2y))
        ma_verdict = score_pred(p["judgment"], ma_outcome)
        v2_outcome = recipe_a_v2_outcome(op_yoy, bool(evs_2y))
        v2_verdict = score_pred(p["judgment"], v2_outcome)
        conf = confidence_label(peer_gap, goodwill, cfo_ni)

        scored.append({**p,
                       "rev_yoy": rev_yoy, "op_yoy": op_yoy, "stock_5d": stock_5d,
                       "has_adverse_event": bool(evs_2y),
                       "peer_gap": peer_gap, "goodwill": goodwill, "cfo_ni": cfo_ni,
                       "conf_label": conf,
                       "multi_axis_verdict": ma_verdict,
                       "recipe_a_v2_verdict": v2_verdict})

    print(f"Scored {len(scored)} confident JGAAP calls\n", flush=True)

    def cross_tab(rows, verdict_key, label):
        print(f"=" * 100, flush=True)
        print(f"{label}", flush=True)
        print(f"=" * 100, flush=True)
        for cls in ("growth_likely", "growth_unlikely"):
            cls_rows = [r for r in rows if r["judgment"] == cls]
            if not cls_rows: continue
            print(f"\n{cls} (n={len(cls_rows)}):", flush=True)
            for conf_tier in ("HIGH", "MEDIUM", "LOW"):
                sub = [r for r in cls_rows if r["conf_label"] == conf_tier]
                h = sum(1 for r in sub if r[verdict_key] == "hit")
                m = sum(1 for r in sub if r[verdict_key] == "miss")
                c = h + m
                prec = h/c*100 if c else None
                ci = _wilson(h, c)
                p_s = f"{prec:.1f}%" if prec is not None else "n/a"
                ci_s = f"[{ci[0]:.1f}-{ci[1]:.1f}]" if ci[0] is not None else ""
                print(f"  {conf_tier:8s}: n={len(sub):3d}, hit={h:3d}, miss={m:3d}, "
                      f"precision={p_s:8s} CI {ci_s}", flush=True)
            # Binary view (PASS = HIGH+MEDIUM)
            pass_rows = [r for r in cls_rows if r["conf_label"] in ("HIGH","MEDIUM")]
            fail_rows = [r for r in cls_rows if r["conf_label"] == "LOW"]
            print(f"  ---", flush=True)
            for grp_name, grp in [("PASS (HIGH/MED)", pass_rows), ("FAIL (LOW)", fail_rows)]:
                h = sum(1 for r in grp if r[verdict_key] == "hit")
                m = sum(1 for r in grp if r[verdict_key] == "miss")
                c = h + m
                prec = h/c*100 if c else None
                ci = _wilson(h, c)
                p_s = f"{prec:.1f}%" if prec is not None else "n/a"
                ci_s = f"[{ci[0]:.1f}-{ci[1]:.1f}]" if ci[0] is not None else ""
                print(f"  {grp_name:18s}: n={len(grp):3d}, hit={h:3d}, miss={m:3d}, "
                      f"precision={p_s:8s} CI {ci_s}", flush=True)

    cross_tab(scored, "recipe_a_v2_verdict", "RECIPE A v2 (current, op profit + events) × CONFIDENCE LAYER")
    print()
    cross_tab(scored, "multi_axis_verdict", "MULTI-AXIS (rev + op profit + stock + events) × CONFIDENCE LAYER")

    # Direct comparison table
    print("\n" + "=" * 100, flush=True)
    print("DIRECT COMPARISON — same confidence cohort, two outcome methodologies", flush=True)
    print("=" * 100, flush=True)
    print(f"\n{'Class':<18}{'Confidence':<16}{'Recipe A v2':<22}{'Multi-axis':<22}{'Δ':<8}", flush=True)
    print("-" * 86, flush=True)
    for cls in ("growth_likely", "growth_unlikely"):
        for conf_tier in [("PASS", ["HIGH","MEDIUM"]), ("FAIL (LOW)", ["LOW"])]:
            cls_rows = [r for r in scored if r["judgment"] == cls and r["conf_label"] in conf_tier[1]]
            v2_h = sum(1 for r in cls_rows if r["recipe_a_v2_verdict"] == "hit")
            v2_m = sum(1 for r in cls_rows if r["recipe_a_v2_verdict"] == "miss")
            v2_c = v2_h + v2_m
            v2_prec = v2_h/v2_c*100 if v2_c else 0
            ma_h = sum(1 for r in cls_rows if r["multi_axis_verdict"] == "hit")
            ma_m = sum(1 for r in cls_rows if r["multi_axis_verdict"] == "miss")
            ma_c = ma_h + ma_m
            ma_prec = ma_h/ma_c*100 if ma_c else 0
            delta = ma_prec - v2_prec
            print(f"{cls:<18}{conf_tier[0]:<16}{v2_prec:5.1f}% ({v2_h}/{v2_c}){' '*7}"
                  f"{ma_prec:5.1f}% ({ma_h}/{ma_c}){' '*7}{delta:+.1f}pp", flush=True)
        print("-" * 86, flush=True)

    out = ROOT / "outputs" / "multi_axis_with_confidence_results.json"
    out.write_text(json.dumps({"n_scored": len(scored), "scored_rows": scored},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
