"""Multi-axis outcome scoring — restores revenue + stock to outcome metric.

Methodology pre-registered at outputs/multi_axis_outcome_methodology.md
before this script ran. No LLM calls.

Axes (locked):
  - Revenue YoY ≥/≤ ±3%
  - Op profit YoY ≥/≤ ±5%
  - Stock 5-day post-filing return ≥/≤ ±5%
  - Adverse event in next 2 years (asymmetric — negative-only)

Voting:
  Positive = ≥2 of 3 directional axes positive AND no adverse event
  Negative = ≥2 of 3 directional axes negative OR adverse event triggered
  Mixed = otherwise
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


def multi_axis_outcome(rev_yoy, op_yoy, stock_5d, has_bad_event):
    """Locked methodology: 3 directional axes + 1 asymmetric event axis."""
    pos_votes = 0
    neg_votes = 0
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


def score_pred(judgment, outcome):
    if outcome == "n/a": return "n/a"
    if judgment == "uncertain": return "abstain"
    if judgment == "growth_likely" and outcome == "positive": return "hit"
    if judgment == "growth_unlikely" and outcome == "negative": return "hit"
    return "miss"


def main():
    print("Multi-axis outcome scoring — restores revenue + stock\n", flush=True)
    print(f"Methodology: outputs/multi_axis_outcome_methodology.md (LOCKED)\n", flush=True)

    # Build event registry
    event_reg = defaultdict(list)
    for tk in ALL_JGAAP:
        for ev in detect_events(tk):
            event_reg[(ev[0], ev[1])].append(ev[2])

    # Load all predictions across 3 samples
    all_preds = []
    for path in [ROOT/"outputs"/"rolling_window_backtest.json",
                 ROOT/"outputs"/"out_of_sample_rolling_window.json",
                 ROOT/"outputs"/"jgaap_extension_rolling_window.json"]:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        all_preds.extend(d["scored_predictions"])

    # Filter to JGAAP cohort, score under multi-axis methodology
    scored = []
    for p in all_preds:
        tk = p["ticker"]
        if tk not in ALL_JGAAP: continue
        if p["judgment"] == "uncertain": continue

        # All three pieces (rev, op, stock_5d) live on the OUTCOME pair, not the prediction pair.
        # The rolling_window output already gives us the next pair's metrics keyed on prediction pair.
        rev_yoy = p.get("rev_delta_pct")
        stock_5d = p.get("stock_5d_pct")
        # op profit YoY comes from the OUTCOME pair — need to load the cached pair data
        # to find op_profit_delta_pct on the outcome pair
        try:
            outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except Exception:
            outcome_fy = None

        # Load outcome pair to find op_profit_delta_pct
        op_yoy = None
        if outcome_fy is not None:
            cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                               f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
            if cache_files:
                with open(cache_files[-1], encoding="utf-8") as f:
                    d = json.load(f)
                for pair in d.get("pairs", []):
                    if pair.get("history_only"): continue
                    if pair.get("curr_fiscal_year") == outcome_fy:
                        op_yoy = pair.get("op_profit_delta_pct")
                        break

        # Adverse events in outcome FY OR outcome FY+1
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])

        outcome = multi_axis_outcome(rev_yoy, op_yoy, stock_5d, bool(evs_2y))
        verdict = score_pred(p["judgment"], outcome)
        scored.append({
            **p,
            "rev_yoy": rev_yoy, "op_yoy": op_yoy, "stock_5d": stock_5d,
            "has_adverse_event": bool(evs_2y),
            "multi_axis_outcome": outcome,
            "multi_axis_verdict": verdict,
        })

    print(f"Scored {len(scored)} confident JGAAP calls under multi-axis methodology\n", flush=True)

    # Aggregate
    print("=" * 100, flush=True)
    print("RESULTS — multi-axis outcome scoring on 45 JGAAP cohort", flush=True)
    print("=" * 100, flush=True)
    for cls in ("growth_likely", "growth_unlikely"):
        sub = [s for s in scored if s["judgment"] == cls]
        h = sum(1 for s in sub if s["multi_axis_verdict"] == "hit")
        m = sum(1 for s in sub if s["multi_axis_verdict"] == "miss")
        c = h + m
        prec = h/c*100 if c else None
        ci = _wilson(h, c)
        p_s = f"{prec:.1f}%" if prec is not None else "n/a"
        ci_s = f"[{ci[0]:.1f}-{ci[1]:.1f}]" if ci[0] is not None else "n/a"
        print(f"\n{cls}:", flush=True)
        print(f"  n={len(sub)}, hit={h}, miss={m}", flush=True)
        print(f"  Precision: {p_s}  95% CI: {ci_s}", flush=True)

    # Outcome distribution
    outcome_counts = Counter(s["multi_axis_outcome"] for s in scored)
    print(f"\nOutcome distribution across confident calls:", flush=True)
    for k, v in sorted(outcome_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}", flush=True)

    # Compare with current Recipe A v2 (op profit + adverse event)
    print("\n" + "=" * 100, flush=True)
    print("COMPARISON: current Recipe A v2 vs new multi-axis", flush=True)
    print("=" * 100, flush=True)

    def score_recipe_a_v2(op_yoy, has_bad):
        if op_yoy is None: return "n/a"
        if op_yoy <= -5.0 or has_bad: return "negative"
        if op_yoy >= 5.0: return "positive"
        return "mixed"

    print(f"\n{'Class':<20}{'Recipe A v2 prec':<22}{'Multi-axis prec':<22}{'Δ':<8}", flush=True)
    print("-" * 80, flush=True)
    for cls in ("growth_likely", "growth_unlikely"):
        sub = [s for s in scored if s["judgment"] == cls]
        # Recipe A v2
        v2_h = v2_m = 0
        for s in sub:
            v2_outcome = score_recipe_a_v2(s["op_yoy"], s["has_adverse_event"])
            v2_v = score_pred(s["judgment"], v2_outcome)
            if v2_v == "hit": v2_h += 1
            elif v2_v == "miss": v2_m += 1
        v2_c = v2_h + v2_m
        v2_prec = v2_h/v2_c*100 if v2_c else 0
        # Multi-axis
        ma_h = sum(1 for s in sub if s["multi_axis_verdict"] == "hit")
        ma_m = sum(1 for s in sub if s["multi_axis_verdict"] == "miss")
        ma_c = ma_h + ma_m
        ma_prec = ma_h/ma_c*100 if ma_c else 0
        delta = ma_prec - v2_prec
        print(f"{cls:<20}{v2_prec:5.1f}% ({v2_h}/{v2_c}){' '*8}"
              f"{ma_prec:5.1f}% ({ma_h}/{ma_c}){' '*8}{delta:+.1f}pp", flush=True)

    # Per-prediction detail for growth_unlikely
    print("\n" + "=" * 100, flush=True)
    print("Per-call detail: growth_unlikely under multi-axis", flush=True)
    print("=" * 100, flush=True)
    for s in scored:
        if s["judgment"] != "growth_unlikely": continue
        rev = f"{s['rev_yoy']:+.1f}%" if s['rev_yoy'] is not None else "n/a"
        op = f"{s['op_yoy']:+.1f}%" if s['op_yoy'] is not None else "n/a"
        stk = f"{s['stock_5d']:+.1f}%" if s['stock_5d'] is not None else "n/a"
        evs = "YES" if s["has_adverse_event"] else "no"
        print(f"  {s['ticker']:<6} {s['prediction_pair']:<22} "
              f"rev={rev:>8} op={op:>8} stk={stk:>8} bad_ev={evs:<3} "
              f"→ {s['multi_axis_outcome']:<10} → {s['multi_axis_verdict'].upper()}", flush=True)

    # Save
    out = ROOT / "outputs" / "multi_axis_outcome_results.json"
    out.write_text(json.dumps({
        "methodology": "multi_axis_outcome_methodology.md",
        "n_scored": len(scored),
        "scored_rows": scored,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
