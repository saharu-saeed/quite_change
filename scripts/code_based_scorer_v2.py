"""Code-based scorer v2 — adds the 3 new indicators discovered by
pattern_discovery.py: op_margin_trend_pp, rev_yoy_pred, top_segment_share.

Also runs a PROPER held-out evaluation:
  TRAIN set = ORIG (11 tickers) + OOS (4 tickers) = 15 tickers
  TEST set  = EXTENSION (30 tickers)
The thresholds in DEFAULT_CONFIG_V2 are pre-registered (based on pattern
discovery findings on the FULL cohort). We report precision separately on
TRAIN and TEST so we can see how much in-sample lift survives.

Pre-registration discipline: thresholds below were chosen BEFORE looking
at the held-out test set. We will report whatever comes out.
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


# ============================================================================
# V2 CONFIG — adds 3 new indicators. Thresholds pre-registered from pattern
# discovery on full cohort. Held-out test below tells us how much survives.
# ============================================================================
DEFAULT_CONFIG_V2 = {
    "thresholds": {
        # Existing 4
        "peer_gap_pos": 10.0,
        "peer_gap_neg": -5.0,
        "margin_pos": 15.0,
        "margin_neg": 5.0,
        "goodwill_neg": 30.0,
        "cfo_pos": 0.8,
        "cfo_neg": 0.5,
        # Existing override
        "profit_crash": -10.0,
        # NEW: margin trend (op_margin_pp_delta)
        "margin_trend_pos": 1.0,
        "margin_trend_neg": -2.0,
        # NEW: revenue YoY at prediction pair (strongest signal on growth_unlikely)
        "rev_yoy_pos": 5.0,
        "rev_yoy_neg": -5.0,
        # NEW: segment concentration (asymmetric, only negative)
        "segment_concentration_neg": 80.0,
        # Verdict score thresholds (raised because more indicators contribute now)
        "score_pos_threshold": 2.0,
        "score_neg_threshold": -1.5,
    },
    "weights": {
        # Existing
        "peer_gap": 1.0,
        "margin": 1.0,
        "goodwill": 0.5,
        "cfo": 1.0,
        "profit_crash": 1.5,
        # New — rev_yoy gets the highest weight (strongest single signal)
        "margin_trend": 1.0,
        "rev_yoy": 1.5,
        "segment_concentration": 0.5,
    },
}


def code_based_verdict_v2(ind, cfg):
    """V2 verdict with 7 indicator buckets + 1 override. ind is a dict from extract_indicators."""
    th = cfg["thresholds"]; w = cfg["weights"]
    signals = {}; score = 0.0

    # (1) Peer LEVEL gap
    if ind["peer_gap"] is not None:
        if ind["peer_gap"] > th["peer_gap_pos"]:
            signals["peer_gap"] = "+"; score += w["peer_gap"]
        elif ind["peer_gap"] < th["peer_gap_neg"]:
            signals["peer_gap"] = "-"; score -= w["peer_gap"]
    # (2) Op margin LEVEL
    if ind["op_margin_level"] is not None:
        if ind["op_margin_level"] > th["margin_pos"]:
            signals["margin"] = "+"; score += w["margin"]
        elif ind["op_margin_level"] < th["margin_neg"]:
            signals["margin"] = "-"; score -= w["margin"]
    # (3) Goodwill (asymmetric)
    if ind["goodwill"] is not None and ind["goodwill"] > th["goodwill_neg"]:
        signals["goodwill"] = "-"; score -= w["goodwill"]
    # (4) CFO/NI
    if ind["cfo_ni"] is not None:
        if ind["cfo_ni"] > th["cfo_pos"]:
            signals["cfo"] = "+"; score += w["cfo"]
        elif ind["cfo_ni"] < th["cfo_neg"]:
            signals["cfo"] = "-"; score -= w["cfo"]
    # (5) NEW: margin TREND
    if ind["op_margin_trend_pp"] is not None:
        if ind["op_margin_trend_pp"] > th["margin_trend_pos"]:
            signals["margin_trend"] = "+"; score += w["margin_trend"]
        elif ind["op_margin_trend_pp"] < th["margin_trend_neg"]:
            signals["margin_trend"] = "-"; score -= w["margin_trend"]
    # (6) NEW: revenue YoY at prediction pair (strongest single signal)
    if ind["rev_yoy_pred"] is not None:
        if ind["rev_yoy_pred"] > th["rev_yoy_pos"]:
            signals["rev_yoy"] = "+"; score += w["rev_yoy"]
        elif ind["rev_yoy_pred"] < th["rev_yoy_neg"]:
            signals["rev_yoy"] = "-"; score -= w["rev_yoy"]
    # (7) NEW: segment concentration (asymmetric)
    if ind["top_segment_share"] is not None and ind["top_segment_share"] > th["segment_concentration_neg"]:
        signals["segment_concentration"] = "-"; score -= w["segment_concentration"]
    # Profit-down override (existing)
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
    out = {k: None for k in [
        "peer_gap", "op_margin_level", "goodwill", "cfo_ni",
        "op_margin_trend_pp", "rev_yoy_pred", "top_segment_share",
        "op_profit_yoy_pred", "op_profit_yoy_outcome",
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
            bs_hist = pair.get("bs_quality_history") or []
            if bs_hist:
                out["goodwill"] = bs_hist[-1].get("goodwill_to_equity_pct")
                out["top_segment_share"] = bs_hist[-1].get("top_segment_share_pct")
            cfo_r = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
            out["cfo_ni"] = cfo_r.get("curr")
            out["op_profit_yoy_pred"] = pair.get("op_profit_delta_pct")
            out["rev_yoy_pred"] = pair.get("rev_delta_pct") or pc_my.get("revenue_yoy_pct")
        if outcome_fy is not None and pair.get("curr_fiscal_year") == outcome_fy:
            out["op_profit_yoy_outcome"] = pair.get("op_profit_delta_pct")
    return out


def precision_block(rows, verdict_col):
    h = sum(1 for r in rows if r[verdict_col] == "hit")
    m = sum(1 for r in rows if r[verdict_col] == "miss")
    c = h + m
    prec = h/c*100 if c else None
    ci = _wilson(h, c)
    return {"hit": h, "miss": m, "n_scored": c, "n_total": len(rows),
            "precision_pct": prec, "ci_lo": ci[0], "ci_hi": ci[1]}


def fmt_prec(b):
    if b["precision_pct"] is None: return "n/a"
    return f"{b['precision_pct']:5.1f}% ({b['hit']}/{b['n_scored']}) CI [{b['ci_lo']:.1f}-{b['ci_hi']:.1f}]"


def evaluate_cohort(rows, label):
    print(f"\n{'-' * 90}", flush=True)
    print(f"  {label}  (n={len(rows)})", flush=True)
    print(f"{'-' * 90}", flush=True)
    print(f"{'Class':<20}{'LLM precision':<42}{'Code v2 precision':<42}", flush=True)
    for cls in ("growth_likely", "growth_unlikely"):
        llm_rows = [r for r in rows if r["llm_verdict"] == cls]
        code_rows = [r for r in rows if r["code_v2_verdict"] == cls]
        llm_b = precision_block(llm_rows, "llm_v_outcome")
        code_b = precision_block(code_rows, "code_v2_v_outcome")
        print(f"{cls:<20}{fmt_prec(llm_b):<42}{fmt_prec(code_b):<42}", flush=True)
    # Hybrid mode: LLM growth_likely, dropped if code v2 says growth_unlikely
    hybrid_rows = []
    for r in rows:
        if r["llm_verdict"] != "growth_likely": continue
        if r["code_v2_verdict"] == "growth_unlikely": continue
        hybrid_rows.append(r)
    hb = precision_block(hybrid_rows, "llm_v_outcome")
    print(f"Hybrid (LLM growth_likely filtered by code-v2): {fmt_prec(hb)}", flush=True)
    hybrid_un = []
    for r in rows:
        if r["llm_verdict"] != "growth_unlikely": continue
        if r["code_v2_verdict"] == "growth_likely": continue
        hybrid_un.append(r)
    hbu = precision_block(hybrid_un, "llm_v_outcome")
    print(f"Hybrid (LLM growth_unlikely filtered by code-v2): {fmt_prec(hbu)}", flush=True)


def main():
    print("Code-based scorer v2 — 7 indicator buckets + held-out evaluation\n", flush=True)
    print(f"TRAIN: {len(TRAIN_TICKERS)} tickers (ORIG 11 + OOS 4)", flush=True)
    print(f"TEST:  {len(TEST_TICKERS)} tickers (EXTENSION 30)", flush=True)
    print("Thresholds in DEFAULT_CONFIG_V2 are pre-registered. Reporting both sets honestly.\n", flush=True)

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
        try:
            outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except: outcome_fy = None
        ind = extract_indicators(tk, p["prediction_pair"], outcome_fy)
        if ind is None: continue
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
        outcome = multi_axis_outcome(p.get("rev_delta_pct"), ind["op_profit_yoy_outcome"],
                                     p.get("stock_5d_pct"), bool(evs_2y))
        cb = code_based_verdict_v2(ind, DEFAULT_CONFIG_V2)
        enriched.append({
            "ticker": tk,
            "prediction_pair": p["prediction_pair"],
            "outcome_pair": p["outcome_pair"],
            "llm_verdict": p["judgment"],
            "outcome_multi_axis": outcome,
            "llm_v_outcome": score_pred(p["judgment"], outcome),
            "code_v2_verdict": cb["verdict"],
            "code_v2_score": cb["score"],
            "code_v2_signals": cb["signals"],
            "code_v2_v_outcome": score_pred(cb["verdict"], outcome),
            "split": "train" if tk in TRAIN_TICKERS else "test",
            **ind,
        })

    print(f"Enriched: {len(enriched)} predictions ({len({e['ticker'] for e in enriched})} tickers)", flush=True)
    train_rows = [e for e in enriched if e["split"] == "train"]
    test_rows = [e for e in enriched if e["split"] == "test"]
    print(f"  TRAIN rows: {len(train_rows)} ({len({e['ticker'] for e in train_rows})} tickers)", flush=True)
    print(f"  TEST rows:  {len(test_rows)} ({len({e['ticker'] for e in test_rows})} tickers)", flush=True)

    # ========================================================================
    # MAIN OUTPUT — head-to-head on TRAIN, TEST, and FULL
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("HEAD-TO-HEAD: LLM vs Code v2 under multi-axis outcome", flush=True)
    print("=" * 90, flush=True)
    evaluate_cohort(train_rows, "TRAIN cohort (15 tickers)")
    evaluate_cohort(test_rows, "TEST cohort — held-out (30 tickers)")
    evaluate_cohort(enriched, "FULL cohort (45 tickers)")

    # ========================================================================
    # Compare v1 vs v2 by re-running v1 logic on the same data
    # ========================================================================
    print("\n\n" + "=" * 90, flush=True)
    print("V1 vs V2 — does adding the 3 new indicators help?", flush=True)
    print("=" * 90, flush=True)
    # Inline v1 verdict (no margin_trend, rev_yoy, segment_conc rules)
    cfg_v1 = copy.deepcopy(DEFAULT_CONFIG_V2)
    for k in ("margin_trend", "rev_yoy", "segment_concentration"):
        cfg_v1["weights"][k] = 0.0
    cfg_v1["thresholds"]["score_pos_threshold"] = 1.5  # v1 default
    cfg_v1["thresholds"]["score_neg_threshold"] = -1.0  # v1 default

    for e in enriched:
        cb_v1 = code_based_verdict_v2(e, cfg_v1)
        e["code_v1_verdict"] = cb_v1["verdict"]
        e["code_v1_v_outcome"] = score_pred(cb_v1["verdict"], e["outcome_multi_axis"])

    for label, rows in [("TRAIN", train_rows), ("TEST (held-out)", test_rows), ("FULL", enriched)]:
        print(f"\n  {label}", flush=True)
        print(f"  {'Class':<20}{'Code v1':<42}{'Code v2':<42}", flush=True)
        for cls in ("growth_likely", "growth_unlikely"):
            v1_rows = [r for r in rows if r["code_v1_verdict"] == cls]
            v2_rows = [r for r in rows if r["code_v2_verdict"] == cls]
            v1b = precision_block(v1_rows, "code_v1_v_outcome")
            v2b = precision_block(v2_rows, "code_v2_v_outcome")
            print(f"  {cls:<20}{fmt_prec(v1b):<42}{fmt_prec(v2b):<42}", flush=True)

    # Save
    out_path = ROOT / "outputs" / "code_based_scorer_v2_results.json"
    out_path.write_text(json.dumps({
        "config_v2": DEFAULT_CONFIG_V2,
        "n_enriched": len(enriched),
        "n_train": len(train_rows),
        "n_test": len(test_rows),
        "rows": enriched,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)


if __name__ == "__main__":
    main()
