"""Profit-crash weight reduction test.

Methodology pre-registered at outputs/profit_crash_weight_methodology.md
(LOCKED before this script ran).

Tests V1 with profit_crash weight at 1.5 (baseline), 1.0, and 0.5.
Reports TRAIN and TEST precision honestly.
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
    out = {k: None for k in ["peer_gap","op_margin_level","cfo_ni",
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
            cfo_r = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
            out["cfo_ni"] = cfo_r.get("curr")
            out["op_profit_yoy_pred"] = pair.get("op_profit_delta_pct")
        if outcome_fy is not None and pair.get("curr_fiscal_year") == outcome_fy:
            out["op_profit_yoy_outcome"] = pair.get("op_profit_delta_pct")
    return out


def v1_verdict(ind, profit_crash_weight):
    """V1 with tunable profit_crash weight. Goodwill removed (confirmed dead)."""
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
        score -= profit_crash_weight
    if score >= 1.5: return "growth_likely", score
    if score <= -1.0: return "growth_unlikely", score
    return "uncertain", score


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
    print("Profit-crash weight reduction test\n", flush=True)
    print("Methodology: outputs/profit_crash_weight_methodology.md (LOCKED)\n", flush=True)

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

    base_rows = []
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
        base_rows.append({
            "ticker": tk, "split": "train" if tk in TRAIN_TICKERS else "test",
            "prediction_pair": p["prediction_pair"],
            "outcome": outcome,
            "ind": ind,
            "profit_crash_fires": ind["op_profit_yoy_pred"] is not None and ind["op_profit_yoy_pred"] < -10.0,
        })

    # Run V1 with each profit_crash weight
    for weight in (1.5, 1.0, 0.5):
        for r in base_rows:
            v, s = v1_verdict(r["ind"], weight)
            r[f"v{weight}_verdict"] = v
            r[f"v{weight}_score"] = s
            r[f"v{weight}_outcome_score"] = score_pred(v, r["outcome"])

    train = [r for r in base_rows if r["split"] == "train"]
    test = [r for r in base_rows if r["split"] == "test"]

    n_crash = sum(1 for r in base_rows if r["profit_crash_fires"])
    print(f"Total: {len(base_rows)} predictions. profit_crash rule fires on {n_crash}.\n", flush=True)

    def report(cohort, label):
        print(f"\n  {label}  (n={len(cohort)})", flush=True)
        print(f"  {'Weight':<10}{'Class':<22}{'Precision':<36}", flush=True)
        print("  " + "-" * 68, flush=True)
        for w in (1.5, 1.0, 0.5):
            for cls in ("growth_likely", "growth_unlikely"):
                sub = [r for r in cohort if r[f"v{w}_verdict"] == cls]
                h, m, c, p, ci = precision_block(sub, f"v{w}_outcome_score")
                marker = " ← baseline" if w == 1.5 else ""
                print(f"  W={w:<7}{cls:<22}{fmt(h,m,c,p,ci):<36}{marker}", flush=True)
            print(f"  {'-'*4}", flush=True)

    print("=" * 90, flush=True)
    print("Results by profit_crash weight", flush=True)
    print("=" * 90, flush=True)
    report(base_rows, "FULL")
    report(train, "TRAIN")
    report(test, "TEST — held-out (the one that matters)")

    # Check pre-registered criterion on TEST
    print("\n" + "=" * 90, flush=True)
    print("Pre-registered criterion check (TEST cohort)", flush=True)
    print("=" * 90, flush=True)
    baseline_gu = [r for r in test if r["v1.5_verdict"] == "growth_unlikely"]
    h_base = sum(1 for r in baseline_gu if r["v1.5_outcome_score"] == "hit")
    c_base = sum(1 for r in baseline_gu if r["v1.5_outcome_score"] in ("hit","miss"))
    p_base = h_base/c_base*100 if c_base else 0
    vol_threshold = 0.8 * c_base
    print(f"\n  Baseline (W=1.5): growth_unlikely n_scored={c_base}, precision={p_base:.1f}%", flush=True)
    print(f"  Volume threshold (80% of baseline): {vol_threshold:.1f}", flush=True)

    for w in (1.0, 0.5):
        sub = [r for r in test if r[f"v{w}_verdict"] == "growth_unlikely"]
        h = sum(1 for r in sub if r[f"v{w}_outcome_score"] == "hit")
        c = sum(1 for r in sub if r[f"v{w}_outcome_score"] in ("hit","miss"))
        p = h/c*100 if c else 0
        passes_prec = p >= p_base
        passes_vol = c >= vol_threshold
        verdict = "PASS" if (passes_prec and passes_vol) else "FAIL"
        print(f"\n  W={w}: growth_unlikely n_scored={c}, precision={p:.1f}%", flush=True)
        print(f"    precision >= baseline ({p_base:.1f}%)? {passes_prec}", flush=True)
        print(f"    volume >= {vol_threshold:.0f}? {passes_vol}", flush=True)
        print(f"    overall: {verdict}", flush=True)

    out = ROOT / "outputs" / "profit_crash_weight_results.json"
    out.write_text(json.dumps({"n": len(base_rows), "rows": base_rows},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
