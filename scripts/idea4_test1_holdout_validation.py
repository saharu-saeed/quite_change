"""Test 1 — held-out validation of the Path C confidence layer.

The confidence layer's 22pp precision spread (LOW vs HIGH/MEDIUM) was
originally computed on all 73 calls, INCLUDING the 17 Idea 4 held-out
calls. This script splits the data:

  In-sample (diagnostic set):  56 confident calls from
    original 20 + OOS 15 + JGAAP extension 30
  Held-out (truly unseen):     17 confident calls from
    Idea 4 Phase 4 OLD-prompt run on 15 fresh JGAAP tickers

If the precision spread holds in the held-out subset, the layer
generalizes. If not, it was overfit to the diagnostic data.
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

# Same JGAAP cohort definitions as Path C
JGAAP_DIAGNOSTIC = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697",
                    "4063","4716","4751","6861",
                    "3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
                    "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"]
JGAAP_HOLDOUT = ["4825","5032","7595","7860","9409","9412","9413","9416","9418",
                 "9601","9605","9682","9692","9746","9889"]


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


def load_pairs(ticker):
    # Try v5 first (diagnostic-set cache), then v6_no_gl (held-out OLD-prompt cache)
    for pattern in [f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json",
                    f"{ticker}_min2020_simp1_cutoffnone_*_v6_*no_gl*.json"]:
        matches = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" / pattern)))
        if matches:
            with open(matches[-1], encoding="utf-8") as f:
                d = json.load(f)
            return [p for p in d.get("pairs", []) if not p.get("history_only")]
    return []


def extract_factors(pred_pair):
    pc = pred_pair.get("peer_comparison") or {}
    pc_my = pc.get("my") or {}
    pc_median = pc.get("sector_median") or {}
    f = {}
    if pc_my.get("op_margin_pct") is not None and pc_median.get("op_margin_pct") is not None:
        f["peer_level_gap_pp"] = pc_my["op_margin_pct"] - pc_median["op_margin_pct"]
    else:
        f["peer_level_gap_pp"] = None
    bs_hist = pred_pair.get("bs_quality_history", [])
    curr_bs = bs_hist[-1] if bs_hist else {}
    f["goodwill_to_equity_pct"] = curr_bs.get("goodwill_to_equity_pct")
    cfo_ratios = pred_pair.get("cashflow_yoy", {}).get("ratios", {}).get("cfo_to_ni", {})
    f["cfo_to_ni_ratio"] = cfo_ratios.get("curr")
    return f


def confidence_label(factors):
    peer_pass = factors["peer_level_gap_pp"] is not None and factors["peer_level_gap_pp"] > 10.0
    goodwill_pass = (factors["goodwill_to_equity_pct"] is None or factors["goodwill_to_equity_pct"] < 30.0)
    cfo_pass = factors["cfo_to_ni_ratio"] is not None and factors["cfo_to_ni_ratio"] > 0.8
    score = sum([peer_pass, goodwill_pass, cfo_pass])
    if score == 3: return "HIGH", score
    if score == 2: return "MEDIUM", score
    return "LOW", score


def score_v2(op_yoy, has_bad, thr=5.0):
    if op_yoy is None: return "n/a"
    if op_yoy <= -thr or has_bad: return "negative"
    if op_yoy >= thr: return "positive"
    return "mixed"


def score_pred(judgment, outcome):
    if outcome == "n/a": return "n/a"
    if judgment == "uncertain": return "abstain"
    if judgment == "growth_likely" and outcome == "positive": return "hit"
    if judgment == "growth_unlikely" and outcome == "negative": return "hit"
    return "miss"


def build_events_for(tickers):
    reg = defaultdict(list)
    for tk in tickers:
        for ev in detect_events(tk):
            reg[(ev[0], ev[1])].append(ev[2])
    return reg


def analyze_records(records, events_reg, pair_cache):
    analyzed = []
    for p in records:
        tk = p["ticker"]
        if tk not in pair_cache:
            pair_cache[tk] = load_pairs(tk)
        pairs = pair_cache[tk]
        pred_pair = next((pp for pp in pairs if f"FY{pp['prev_fiscal_year']}->FY{pp['curr_fiscal_year']}" == p["prediction_pair"]), None)
        out_pair = next((pp for pp in pairs if f"FY{pp['prev_fiscal_year']}->FY{pp['curr_fiscal_year']}" == p["outcome_pair"]), None)
        if not pred_pair or not out_pair: continue
        factors = extract_factors(pred_pair)
        label, score = confidence_label(factors)
        op_yoy = out_pair.get("op_profit_delta_pct")
        try: outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY",""))
        except: outcome_fy = None
        evs = events_reg.get((tk, outcome_fy), []) + (events_reg.get((tk, outcome_fy+1), []) if outcome_fy else [])
        outcome = score_v2(op_yoy, bool(evs))
        verdict = score_pred(p["judgment"], outcome)
        analyzed.append({**p, **factors, "conf_label": label, "conf_score": score,
                         "outcome": outcome, "verdict": verdict})
    return analyzed


def summarize_by_label(rows, label_grouping="binary"):
    """label_grouping: 'binary' (PASS=HIGH+MEDIUM, FAIL=LOW) or 'tier' (HIGH/MEDIUM/LOW)."""
    if label_grouping == "tier":
        groups = ["HIGH", "MEDIUM", "LOW"]
        def fn(r): return r["conf_label"]
    else:
        groups = ["PASS (HIGH/MEDIUM)", "FAIL (LOW)"]
        def fn(r): return "PASS (HIGH/MEDIUM)" if r["conf_label"] in ("HIGH","MEDIUM") else "FAIL (LOW)"

    result = {}
    for g in groups:
        sub = [r for r in rows if fn(r) == g]
        h = sum(1 for r in sub if r["verdict"] == "hit")
        m = sum(1 for r in sub if r["verdict"] == "miss")
        conf = h + m
        prec = h/conf*100 if conf else None
        ci = _wilson(h, conf)
        result[g] = {"n": len(sub), "hit": h, "miss": m,
                     "precision_pct": round(prec, 1) if prec is not None else None,
                     "ci_95_pct": (round(ci[0], 1), round(ci[1], 1)) if ci[0] is not None else None}
    return result


def main():
    print("Test 1 — Path C confidence layer held-out validation\n", flush=True)

    # Build event registries
    diag_events = build_events_for(JGAAP_DIAGNOSTIC)
    holdout_events = build_events_for(JGAAP_HOLDOUT)

    # Load diagnostic-set predictions (original + OOS + extension)
    diag_records = []
    for path in [ROOT/"outputs"/"rolling_window_backtest.json",
                 ROOT/"outputs"/"out_of_sample_rolling_window.json",
                 ROOT/"outputs"/"jgaap_extension_rolling_window.json"]:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for p in d["scored_predictions"]:
            if p["ticker"] in JGAAP_DIAGNOSTIC and p["judgment"] in ("growth_likely","growth_unlikely"):
                diag_records.append(p)

    # Load held-out predictions (idea4 OLD prompt)
    with open(ROOT/"outputs"/"idea4_holdout_v6_2026-05-18_no_gl.json", encoding="utf-8") as f:
        holdout_data = json.load(f)
    holdout_records = []
    for tk in holdout_data["tickers"]:
        per = holdout_data["per_ticker"].get(tk, {})
        pairs_list = per.get("pairs", [])
        for i in range(len(pairs_list)-1):
            p = pairs_list[i]; next_p = pairs_list[i+1]
            if p["judgment"] in ("growth_likely","growth_unlikely"):
                holdout_records.append({
                    "ticker": tk,
                    "prediction_pair": f"FY{p['prev_fy']}->FY{p['curr_fy']}",
                    "outcome_pair": f"FY{next_p['prev_fy']}->FY{next_p['curr_fy']}",
                    "judgment": p["judgment"],
                })

    print(f"Diagnostic set (in-sample): {len(diag_records)} confident calls", flush=True)
    print(f"Held-out set (truly unseen): {len(holdout_records)} confident calls\n", flush=True)

    # Build pair caches separately to avoid cross-contamination
    diag_pair_cache = {}
    holdout_pair_cache = {}
    diag_analyzed = analyze_records(diag_records, diag_events, diag_pair_cache)
    holdout_analyzed = analyze_records(holdout_records, holdout_events, holdout_pair_cache)

    print(f"After pair-data load: diag={len(diag_analyzed)}, holdout={len(holdout_analyzed)}\n", flush=True)

    print("=" * 100, flush=True)
    print("3-TIER LABELS (HIGH / MEDIUM / LOW)", flush=True)
    print("=" * 100, flush=True)
    for sample_label, rows in [("DIAGNOSTIC (in-sample)", diag_analyzed),
                                ("HELD-OUT (truly unseen)", holdout_analyzed)]:
        for judgment_cls in ("growth_likely", "growth_unlikely"):
            cls_rows = [r for r in rows if r["judgment"] == judgment_cls]
            if not cls_rows: continue
            print(f"\n{sample_label} — {judgment_cls} (n={len(cls_rows)}):", flush=True)
            summary = summarize_by_label(cls_rows, "tier")
            for grp, d in summary.items():
                p = d["precision_pct"]; ci = d["ci_95_pct"]
                p_s = f"{p}%" if p is not None else "n/a"
                ci_s = f"[{ci[0]}-{ci[1]}]" if ci else ""
                print(f"  {grp:8s}: n={d['n']:3d}, hit={d['hit']:3d}, miss={d['miss']:3d}, "
                      f"precision={p_s} {ci_s}", flush=True)

    print(f"\n{'='*100}", flush=True)
    print("BINARY LABELS (PASS = HIGH/MEDIUM, FAIL = LOW) — TEST 2 EMBEDDED", flush=True)
    print(f"{'='*100}", flush=True)
    for sample_label, rows in [("DIAGNOSTIC (in-sample)", diag_analyzed),
                                ("HELD-OUT (truly unseen)", holdout_analyzed)]:
        for judgment_cls in ("growth_likely", "growth_unlikely"):
            cls_rows = [r for r in rows if r["judgment"] == judgment_cls]
            if not cls_rows: continue
            print(f"\n{sample_label} — {judgment_cls} (n={len(cls_rows)}):", flush=True)
            summary = summarize_by_label(cls_rows, "binary")
            for grp, d in summary.items():
                p = d["precision_pct"]; ci = d["ci_95_pct"]
                p_s = f"{p}%" if p is not None else "n/a"
                ci_s = f"[{ci[0]}-{ci[1]}]" if ci else ""
                print(f"  {grp:20s}: n={d['n']:3d}, hit={d['hit']:3d}, miss={d['miss']:3d}, "
                      f"precision={p_s} {ci_s}", flush=True)

    # Save
    out_path = ROOT / "outputs" / "idea4_test1_results.json"
    out_path.write_text(json.dumps({
        "test": "held-out validation of confidence layer",
        "diag_n": len(diag_analyzed),
        "holdout_n": len(holdout_analyzed),
        "diag_rows": diag_analyzed,
        "holdout_rows": holdout_analyzed,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)


if __name__ == "__main__":
    main()
