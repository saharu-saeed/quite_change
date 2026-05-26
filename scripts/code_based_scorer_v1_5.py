"""V1.5 — V1 (4 indicators) PLUS rev_yoy_pred only.

Why: pattern discovery suggested 3 new indicators but held-out V2 showed
adding all 3 wasn't strictly better. rev_yoy_pred was the strongest single
signal (+23pp lift on growth_unlikely in-sample). This script tests whether
adding ONLY that one indicator captures most of V2's gain without the noise.
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
import copy
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


CONFIG_V1_5 = {
    "thresholds": {
        "peer_gap_pos": 10.0, "peer_gap_neg": -5.0,
        "margin_pos": 15.0, "margin_neg": 5.0,
        "goodwill_neg": 30.0,
        "cfo_pos": 0.8, "cfo_neg": 0.5,
        "profit_crash": -10.0,
        # The one new indicator
        "rev_yoy_pos": 5.0, "rev_yoy_neg": -5.0,
        "score_pos_threshold": 2.0,
        "score_neg_threshold": -1.5,
    },
    "weights": {
        "peer_gap": 1.0, "margin": 1.0, "goodwill": 0.5,
        "cfo": 1.0, "profit_crash": 1.5,
        "rev_yoy": 1.5,  # strongest single signal — high weight
    },
}


def verdict_v1_5(ind, cfg):
    th = cfg["thresholds"]; w = cfg["weights"]
    signals = {}; score = 0.0
    if ind["peer_gap"] is not None:
        if ind["peer_gap"] > th["peer_gap_pos"]:
            signals["peer_gap"] = "+"; score += w["peer_gap"]
        elif ind["peer_gap"] < th["peer_gap_neg"]:
            signals["peer_gap"] = "-"; score -= w["peer_gap"]
    if ind["op_margin_level"] is not None:
        if ind["op_margin_level"] > th["margin_pos"]:
            signals["margin"] = "+"; score += w["margin"]
        elif ind["op_margin_level"] < th["margin_neg"]:
            signals["margin"] = "-"; score -= w["margin"]
    if ind["goodwill"] is not None and ind["goodwill"] > th["goodwill_neg"]:
        signals["goodwill"] = "-"; score -= w["goodwill"]
    if ind["cfo_ni"] is not None:
        if ind["cfo_ni"] > th["cfo_pos"]:
            signals["cfo"] = "+"; score += w["cfo"]
        elif ind["cfo_ni"] < th["cfo_neg"]:
            signals["cfo"] = "-"; score -= w["cfo"]
    # Only new indicator: rev_yoy
    if ind["rev_yoy_pred"] is not None:
        if ind["rev_yoy_pred"] > th["rev_yoy_pos"]:
            signals["rev_yoy"] = "+"; score += w["rev_yoy"]
        elif ind["rev_yoy_pred"] < th["rev_yoy_neg"]:
            signals["rev_yoy"] = "-"; score -= w["rev_yoy"]
    if ind["op_profit_yoy_pred"] is not None and ind["op_profit_yoy_pred"] < th["profit_crash"]:
        signals["profit_crash"] = "-"; score -= w["profit_crash"]
    if score >= th["score_pos_threshold"]:
        verdict = "growth_likely"
    elif score <= th["score_neg_threshold"]:
        verdict = "growth_unlikely"
    else:
        verdict = "uncertain"
    return {"verdict": verdict, "score": round(score, 2), "signals": signals}


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
    out = {k: None for k in ["peer_gap","op_margin_level","goodwill","cfo_ni",
                              "rev_yoy_pred","op_profit_yoy_pred","op_profit_yoy_outcome"]}
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
            out["rev_yoy_pred"] = pair.get("rev_delta_pct") or pc_my.get("revenue_yoy_pct")
        if outcome_fy is not None and pair.get("curr_fiscal_year") == outcome_fy:
            out["op_profit_yoy_outcome"] = pair.get("op_profit_delta_pct")
    return out


def precision_block(rows, col):
    h = sum(1 for r in rows if r[col] == "hit")
    m = sum(1 for r in rows if r[col] == "miss")
    c = h + m
    prec = h/c*100 if c else None
    ci = _wilson(h, c)
    return {"hit": h, "miss": m, "n_scored": c, "precision": prec, "ci_lo": ci[0], "ci_hi": ci[1]}


def fmt(b):
    if b["precision"] is None: return "n/a"
    return f"{b['precision']:5.1f}% ({b['hit']}/{b['n_scored']}) CI [{b['ci_lo']:.1f}-{b['ci_hi']:.1f}]"


def main():
    print("V1.5 — V1 + only rev_yoy as new indicator\n", flush=True)

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
        cb = verdict_v1_5(ind, CONFIG_V1_5)
        enriched.append({
            "ticker": tk, "split": "train" if tk in TRAIN_TICKERS else "test",
            "prediction_pair": p["prediction_pair"],
            "llm_verdict": p["judgment"],
            "outcome": outcome,
            "llm_v_outcome": score_pred(p["judgment"], outcome),
            "v15_verdict": cb["verdict"],
            "v15_v_outcome": score_pred(cb["verdict"], outcome),
            **ind,
        })

    train = [e for e in enriched if e["split"] == "train"]
    test = [e for e in enriched if e["split"] == "test"]
    print(f"Total: {len(enriched)} predictions  (TRAIN {len(train)}, TEST {len(test)})\n", flush=True)

    print("=" * 90, flush=True)
    print("V1.5 vs LLM under multi-axis outcome", flush=True)
    print("=" * 90, flush=True)
    for label, rows in [("TRAIN (15 tickers)", train),
                        ("TEST — held-out (30 tickers)", test),
                        ("FULL (45 tickers)", enriched)]:
        print(f"\n  {label} — n={len(rows)}", flush=True)
        print(f"  {'Class':<20}{'LLM':<40}{'V1.5':<40}", flush=True)
        print("  " + "-" * 96, flush=True)
        for cls in ("growth_likely", "growth_unlikely"):
            llm = precision_block([e for e in rows if e["llm_verdict"]==cls], "llm_v_outcome")
            v15 = precision_block([e for e in rows if e["v15_verdict"]==cls], "v15_v_outcome")
            print(f"  {cls:<20}{fmt(llm):<40}{fmt(v15):<40}", flush=True)

    out_path = ROOT / "outputs" / "code_based_scorer_v1_5_results.json"
    out_path.write_text(json.dumps({"config": CONFIG_V1_5, "n": len(enriched), "rows": enriched},
                                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)


if __name__ == "__main__":
    main()
