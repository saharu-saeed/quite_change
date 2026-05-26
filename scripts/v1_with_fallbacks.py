"""V1.6 — V1 with structured fallback indicators when primary signals missing.

Methodology pre-registered at outputs/fallback_indicators_methodology.md
(LOCKED before this script ran).

When CFO/NI is missing: use margin-trend + level as proxy (weight 0.5).
When goodwill is missing: detect "never had goodwill" → no impairment risk;
otherwise carry-back from later years within 2 FY.
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


def get_ticker_goodwill_history(ticker):
    """Return list of all (fy, goodwill_pct) from this ticker's cache, sorted by fy."""
    cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                       f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not cache_files: return []
    with open(cache_files[-1], encoding="utf-8") as f:
        d = json.load(f)
    history = []
    seen_fys = set()
    for pair in d.get("pairs", []):
        bs_hist = pair.get("bs_quality_history") or []
        for entry in bs_hist:
            fy = entry.get("fiscal_year")
            gw = entry.get("goodwill_to_equity_pct")
            if fy is not None and fy not in seen_fys:
                seen_fys.add(fy)
                history.append((fy, gw))
    history.sort()
    return history


def extract_indicators(ticker, pred_pair_label, outcome_fy, gw_history):
    cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                       f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not cache_files: return None
    with open(cache_files[-1], encoding="utf-8") as f:
        d = json.load(f)
    out = {k: None for k in ["peer_gap","op_margin_level","op_margin_trend_pp","goodwill","cfo_ni",
                              "op_profit_yoy_pred","op_profit_yoy_outcome","pair_curr_fy"]}
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
            cfo_r = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
            out["cfo_ni"] = cfo_r.get("curr")
            out["op_profit_yoy_pred"] = pair.get("op_profit_delta_pct")
            out["pair_curr_fy"] = pair["curr_fiscal_year"]
        if outcome_fy is not None and pair.get("curr_fiscal_year") == outcome_fy:
            out["op_profit_yoy_outcome"] = pair.get("op_profit_delta_pct")
    return out


def goodwill_with_fallback(ind, gw_history):
    """Apply goodwill fallback rules. Returns (effective_goodwill, fallback_used)."""
    if ind["goodwill"] is not None:
        return ind["goodwill"], "direct"
    # Rule 1: ticker has NEVER had goodwill data
    has_any_goodwill = any(gw is not None for _, gw in gw_history)
    if not has_any_goodwill:
        return 0.0, "never_had_goodwill"  # explicit 0 = no impairment risk
    # Rule 2: carry-back from later years (within 2 FY)
    pair_fy = ind.get("pair_curr_fy")
    if pair_fy is not None:
        for fy, gw in gw_history:
            if gw is not None and pair_fy <= fy <= pair_fy + 2:
                return gw, "carryback"
    return None, "no_fallback"


def cfo_with_fallback(ind):
    """Apply CFO fallback rules. Returns (vote, weight, fallback_used)."""
    if ind["cfo_ni"] is not None:
        # Primary signal
        if ind["cfo_ni"] > 0.8: return "pos", 1.0, "direct"
        if ind["cfo_ni"] < 0.5: return "neg", 1.0, "direct"
        return "neutral", 0.0, "direct"
    # Fallback: margin trend + level proxy
    trend = ind.get("op_margin_trend_pp")
    level = ind.get("op_margin_level")
    if trend is not None and level is not None:
        if trend >= 1.0 and level >= 10.0:
            return "pos", 0.5, "margin_proxy"
        if trend <= -2.0:
            return "neg", 0.5, "margin_proxy"
    return "neutral", 0.0, "no_fallback"


def v1_baseline(ind):
    """V1 baseline: 4 indicators + profit_crash. Goodwill dropped (confirmed dead today)."""
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
    if score >= 1.5: return "growth_likely", score
    if score <= -1.0: return "growth_unlikely", score
    return "uncertain", score


def v1_6_with_fallbacks(ind, gw_history):
    """V1.6: V1 with fallbacks when goodwill/CFO missing."""
    score = 0.0
    fallbacks = {}
    if ind["peer_gap"] is not None:
        if ind["peer_gap"] > 10.0: score += 1.0
        elif ind["peer_gap"] < -5.0: score -= 1.0
    if ind["op_margin_level"] is not None:
        if ind["op_margin_level"] > 15.0: score += 1.0
        elif ind["op_margin_level"] < 5.0: score -= 1.0
    # Goodwill with fallback (kept in V1.6 because fallback might enable signal)
    eff_gw, gw_fb = goodwill_with_fallback(ind, gw_history)
    fallbacks["goodwill"] = gw_fb
    if eff_gw is not None and eff_gw > 30.0:
        score -= 0.5
    # CFO with fallback (this is the main new thing)
    cfo_vote, cfo_w, cfo_fb = cfo_with_fallback(ind)
    fallbacks["cfo"] = cfo_fb
    if cfo_vote == "pos": score += cfo_w
    elif cfo_vote == "neg": score -= cfo_w
    # Profit crash unchanged
    if ind["op_profit_yoy_pred"] is not None and ind["op_profit_yoy_pred"] < -10.0:
        score -= 1.5
    if score >= 1.5: return "growth_likely", score, fallbacks
    if score <= -1.0: return "growth_unlikely", score, fallbacks
    return "uncertain", score, fallbacks


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
    print("V1.6 — V1 with structured fallbacks for missing goodwill / CFO\n", flush=True)
    print("Methodology: outputs/fallback_indicators_methodology.md (LOCKED)\n", flush=True)

    event_reg = defaultdict(list)
    for tk in ALL_JGAAP:
        for ev in detect_events(tk):
            event_reg[(ev[0], ev[1])].append(ev[2])

    # Build goodwill history per ticker (used for fallback rules)
    gw_history_per_ticker = {}
    for tk in ALL_JGAAP:
        gw_history_per_ticker[tk] = get_ticker_goodwill_history(tk)

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
        ind = extract_indicators(tk, p["prediction_pair"], outcome_fy, gw_history_per_ticker[tk])
        if ind is None: continue
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
        outcome = multi_axis_outcome(p.get("rev_delta_pct"), ind["op_profit_yoy_outcome"],
                                     p.get("stock_5d_pct"), bool(evs_2y))
        v1_v, v1_s = v1_baseline(ind)
        v16_v, v16_s, fbs = v1_6_with_fallbacks(ind, gw_history_per_ticker[tk])
        enriched.append({
            "ticker": tk, "split": "train" if tk in TRAIN_TICKERS else "test",
            "prediction_pair": p["prediction_pair"],
            "outcome": outcome,
            "v1_verdict": v1_v, "v1_score": v1_s,
            "v16_verdict": v16_v, "v16_score": v16_s,
            "v1_outcome_score": score_pred(v1_v, outcome),
            "v16_outcome_score": score_pred(v16_v, outcome),
            "fallbacks": fbs,
            "cfo_ni_present": ind["cfo_ni"] is not None,
            "goodwill_present": ind["goodwill"] is not None,
        })

    train = [e for e in enriched if e["split"] == "train"]
    test = [e for e in enriched if e["split"] == "test"]

    # Coverage stats
    print(f"Total: {len(enriched)}. TRAIN: {len(train)}, TEST: {len(test)}", flush=True)
    print(f"\nFallback usage (FULL):", flush=True)
    from collections import Counter
    cfo_fb_counter = Counter(e["fallbacks"]["cfo"] for e in enriched)
    gw_fb_counter = Counter(e["fallbacks"]["goodwill"] for e in enriched)
    print(f"  CFO fallback breakdown:", flush=True)
    for k, v in cfo_fb_counter.most_common():
        print(f"    {k}: {v}", flush=True)
    print(f"  Goodwill fallback breakdown:", flush=True)
    for k, v in gw_fb_counter.most_common():
        print(f"    {k}: {v}", flush=True)

    # Cases where V1 said uncertain but V1.6 says a verdict (fallback unlocked decision)
    unlocked = [e for e in enriched if e["v1_verdict"] == "uncertain" and e["v16_verdict"] != "uncertain"]
    flipped_same_direction = [e for e in enriched if e["v1_verdict"] != "uncertain"
                              and e["v16_verdict"] != "uncertain"
                              and e["v1_verdict"] != e["v16_verdict"]]
    print(f"\n  Cases V1.6 unlocks (V1=uncertain → V1.6=verdict): {len(unlocked)}", flush=True)
    print(f"  Cases V1.6 flips verdict direction:                {len(flipped_same_direction)}", flush=True)

    def report(cohort, label):
        print(f"\n  {label}  (n={len(cohort)})", flush=True)
        print(f"  {'Class':<22}{'V1 (baseline)':<36}{'V1.6 (with fallbacks)':<36}{'Δ':<10}", flush=True)
        print("  " + "-" * 106, flush=True)
        for cls in ("growth_likely", "growth_unlikely"):
            v1_sub = [e for e in cohort if e["v1_verdict"] == cls]
            v16_sub = [e for e in cohort if e["v16_verdict"] == cls]
            h1,m1,c1,p1,ci1 = precision_block(v1_sub, "v1_outcome_score")
            h2,m2,c2,p2,ci2 = precision_block(v16_sub, "v16_outcome_score")
            delta = f"{p2-p1:+.1f}pp" if (p1 is not None and p2 is not None) else "n/a"
            print(f"  {cls:<22}{fmt(h1,m1,c1,p1,ci1):<36}{fmt(h2,m2,c2,p2,ci2):<36}{delta}", flush=True)

    print("\n" + "=" * 110, flush=True)
    print("Precision comparison", flush=True)
    print("=" * 110, flush=True)
    report(enriched, "FULL")
    report(train, "TRAIN")
    report(test, "TEST — held-out (the one that matters)")

    # Pre-registered criterion check
    print("\n" + "=" * 110, flush=True)
    print("Pre-registered criterion check (TEST cohort)", flush=True)
    print("=" * 110, flush=True)
    for cls, v1_baseline_prec in [("growth_likely", 57.9), ("growth_unlikely", 60.0)]:
        v16_sub = [e for e in test if e["v16_verdict"] == cls]
        h, m, c, p, ci = precision_block(v16_sub, "v16_outcome_score")
        if p is None:
            print(f"  {cls}: V1.6 n/a", flush=True)
            continue
        passes = p >= v1_baseline_prec
        print(f"  {cls}: V1 baseline = {v1_baseline_prec}%, V1.6 = {p:.1f}% (n={c}) — "
              f"{'PASS' if passes else 'FAIL'}", flush=True)

    n_fallback_test = sum(1 for e in test if e["fallbacks"]["cfo"] == "margin_proxy")
    print(f"\n  CFO-margin-proxy fallback fired on TEST: {n_fallback_test} cases "
          f"(criterion: ≥ 5 → {'PASS' if n_fallback_test >= 5 else 'FAIL'})", flush=True)

    # Save
    out = ROOT / "outputs" / "v1_with_fallbacks_results.json"
    out.write_text(json.dumps({"n": len(enriched), "rows": enriched},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
