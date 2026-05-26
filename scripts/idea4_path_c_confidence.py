"""Idea 4 Path C — post-hoc confidence layer for growth_likely.

Computes a 3-factor confidence score for each growth_likely call across all
our existing JGAAP cohort data (original 20 + OOS 15 + extension 30 +
held-out 15 OLD prompt = 80 tickers, ~58 growth_likely calls).

Factors (each contributes 0 or 1 to a 0-3 total):
  +1 if peer_op_margin LEVEL gap > +10pp vs sector median
  +1 if goodwill / equity < 30%
  +1 if CFO / NI ratio > 0.8

Confidence labels:
  HIGH (3/3): all three positive signals
  MEDIUM (2/3): two of three positive
  LOW (0-1/3): few or no positive signals

Then cross-tabs confidence-label vs HIT/MISS under Recipe A v2 scoring.
If HIGH-confidence calls have materially better precision than LOW, the
layer is a useful product feature.
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
JGAAP_HOLDOUT = ["4825","5032","7595","7860","9409","9412","9413","9416","9418",
                 "9601","9605","9682","9692","9746","9889"]
ALL_JGAAP = set(JGAAP_ORIG + JGAAP_OOS + JGAAP_EXT + JGAAP_HOLDOUT)


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


# Event detection (same as Recipe A v2 elsewhere)
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
    stds = set(i.get("accounting_standard") for i in items if i.get("accounting_standard"))
    if "Japan GAAP" not in stds: return []
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
    # Cache files exist for any cache version that was active — try multiple patterns
    matches = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                  f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not matches:
        matches = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                      f"{ticker}_min2020_simp1_cutoffnone_*_v6_*no_gl*.json")))
    if not matches: return []
    with open(matches[-1], encoding="utf-8") as f:
        d = json.load(f)
    return [p for p in d.get("pairs", []) if not p.get("history_only")]


def extract_factors(pred_pair):
    """Pull the 3 confidence factors from a pair's structured data."""
    f = {}
    pc = pred_pair.get("peer_comparison") or {}
    pc_my = pc.get("my") or {}
    pc_median = pc.get("sector_median") or {}
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


def confidence_score(factors):
    """Binary 0-3 score across the 3 factors."""
    sub = {}
    sub["peer_pass"] = (factors["peer_level_gap_pp"] is not None
                       and factors["peer_level_gap_pp"] > 10.0)
    sub["goodwill_pass"] = (factors["goodwill_to_equity_pct"] is None  # absent = pass (not high-goodwill)
                           or factors["goodwill_to_equity_pct"] < 30.0)
    sub["cfo_pass"] = (factors["cfo_to_ni_ratio"] is not None
                      and factors["cfo_to_ni_ratio"] > 0.8)
    score = sum([sub["peer_pass"], sub["goodwill_pass"], sub["cfo_pass"]])
    if score == 3:
        label = "HIGH"
    elif score == 2:
        label = "MEDIUM"
    else:
        label = "LOW"
    return score, label, sub


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


def main():
    print("Idea 4 Path C — Post-hoc confidence layer analysis\n", flush=True)

    # Build event registry
    event_reg = defaultdict(list)
    for tk in ALL_JGAAP:
        for ev in detect_events(tk):
            event_reg[(ev[0], ev[1])].append(ev[2])

    # Gather all OLD-prompt growth_likely calls (and growth_unlikely for comparison)
    all_preds = []
    for path in [ROOT / "outputs" / "rolling_window_backtest.json",
                 ROOT / "outputs" / "out_of_sample_rolling_window.json",
                 ROOT / "outputs" / "jgaap_extension_rolling_window.json"]:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for pred in d["scored_predictions"]:
            all_preds.append({**pred, "sample": path.stem})

    # Add held-out OLD-prompt results from idea4_holdout_v6_2026-05-18_no_gl.json
    holdout_old_path = ROOT / "outputs" / "idea4_holdout_v6_2026-05-18_no_gl.json"
    with open(holdout_old_path, encoding="utf-8") as f:
        holdout_data = json.load(f)
    # Convert held-out per_ticker structure → rolling-window predictions
    for tk in holdout_data["tickers"]:
        per = holdout_data["per_ticker"].get(tk, {})
        pairs = per.get("pairs", [])
        for i in range(len(pairs) - 1):
            p = pairs[i]
            next_p = pairs[i+1]
            all_preds.append({
                "ticker": tk,
                "prediction_pair": f"FY{p['prev_fy']}->FY{p['curr_fy']}",
                "outcome_pair": f"FY{next_p['prev_fy']}->FY{next_p['curr_fy']}",
                "judgment": p["judgment"],
                "sample": "holdout_old",
            })

    print(f"Total predictions loaded: {len(all_preds)}", flush=True)

    # Filter to JGAAP cohort + analyze growth_likely calls
    pair_cache = {}
    analyzed = []
    for p in all_preds:
        tk = p["ticker"]
        if tk not in ALL_JGAAP: continue
        if p["judgment"] not in ("growth_likely", "growth_unlikely"): continue
        if tk not in pair_cache:
            pair_cache[tk] = load_pairs(tk)
        pairs = pair_cache[tk]
        pred_pair = next((pp for pp in pairs if
                          f"FY{pp['prev_fiscal_year']}->FY{pp['curr_fiscal_year']}" == p["prediction_pair"]),
                         None)
        out_pair = next((pp for pp in pairs if
                         f"FY{pp['prev_fiscal_year']}->FY{pp['curr_fiscal_year']}" == p["outcome_pair"]),
                        None)
        if not pred_pair or not out_pair:
            continue
        factors = extract_factors(pred_pair)
        score, label, sub = confidence_score(factors)
        # Score outcome
        op_yoy = out_pair.get("op_profit_delta_pct")
        try:
            outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except: outcome_fy = None
        evs = event_reg.get((tk, outcome_fy), []) + (event_reg.get((tk, outcome_fy+1), []) if outcome_fy else [])
        outcome = score_v2(op_yoy, bool(evs))
        verdict = score_pred(p["judgment"], outcome)
        analyzed.append({
            "ticker": tk, "prediction_pair": p["prediction_pair"],
            "judgment": p["judgment"], "verdict": verdict, "outcome": outcome,
            **factors, "conf_score": score, "conf_label": label, **sub,
            "sample": p.get("sample", "?"),
        })

    print(f"Analyzed JGAAP confident calls: {len(analyzed)}\n", flush=True)
    print(f"By judgment: {Counter(r['judgment'] for r in analyzed)}", flush=True)
    print(f"By confidence label: {Counter(r['conf_label'] for r in analyzed)}\n", flush=True)

    # Cross-tab confidence × verdict for growth_likely
    for cls in ("growth_likely", "growth_unlikely"):
        print(f"=" * 100, flush=True)
        print(f"{cls.upper()} — confidence layer cross-tab", flush=True)
        print(f"=" * 100, flush=True)
        cls_rows = [r for r in analyzed if r["judgment"] == cls]
        if not cls_rows:
            continue
        print(f"\nTotal {cls} calls: {len(cls_rows)}", flush=True)
        for conf in ("HIGH", "MEDIUM", "LOW"):
            sub = [r for r in cls_rows if r["conf_label"] == conf]
            h = sum(1 for r in sub if r["verdict"] == "hit")
            m = sum(1 for r in sub if r["verdict"] == "miss")
            total_confident = h + m
            prec = h/total_confident*100 if total_confident else None
            ci = _wilson(h, total_confident)
            p_s = f"{prec:.1f}%" if prec is not None else "n/a"
            ci_s = f"[{ci[0]:.1f}-{ci[1]:.1f}]" if ci[0] is not None else "n/a"
            print(f"  {conf:8s}: n={len(sub):3d}, hit={h:3d}, miss={m:3d}, precision={p_s:8s} CI {ci_s}",
                  flush=True)

    # Detailed: what does the confidence layer look like for growth_likely MISSes?
    print(f"\n{'='*100}", flush=True)
    print(f"GROWTH_LIKELY MISSes — what confidence layer would have flagged them?", flush=True)
    print(f"{'='*100}", flush=True)
    misses = [r for r in analyzed if r["judgment"] == "growth_likely" and r["verdict"] == "miss"]
    print(f"Total growth_likely MISSes: {len(misses)}", flush=True)
    miss_conf = Counter(r["conf_label"] for r in misses)
    print(f"  By confidence: {dict(miss_conf)}", flush=True)
    print(f"  If we treated LOW-confidence as 'needs human review' (not auto-trusted growth_likely):",
          flush=True)
    print(f"    Number of MISSes that would have been LOW-flagged: {miss_conf.get('LOW', 0)} / {len(misses)} "
          f"({miss_conf.get('LOW', 0)/len(misses)*100:.0f}% of MISSes correctly tagged as risky)", flush=True)

    # And HITs
    hits = [r for r in analyzed if r["judgment"] == "growth_likely" and r["verdict"] == "hit"]
    hit_conf = Counter(r["conf_label"] for r in hits)
    print(f"\nGrowth_likely HITs by confidence: {dict(hit_conf)}", flush=True)
    print(f"  LOW-confidence HITs (false-flags if we filtered LOW): {hit_conf.get('LOW', 0)} / {len(hits)} "
          f"({hit_conf.get('LOW', 0)/len(hits)*100:.0f}%)", flush=True)

    # Save
    out = ROOT / "outputs" / "idea4_path_c_results.json"
    out.write_text(json.dumps({
        "n_growth_likely": len([r for r in analyzed if r["judgment"] == "growth_likely"]),
        "n_growth_unlikely": len([r for r in analyzed if r["judgment"] == "growth_unlikely"]),
        "by_label": dict(Counter(r["conf_label"] for r in analyzed)),
        "per_call": analyzed,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
