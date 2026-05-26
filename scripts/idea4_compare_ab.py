"""Idea 4 Phase 4c — compare paired A/B results.

Loads NEW prompt (GL rules) and OLD prompt (no GL rules) results from the
held-out 15-ticker sample, applies Recipe A v2 scoring with consistent
event detection, reports verdict flips and precision changes.
"""
from __future__ import annotations
import json
import sys
import io
import math
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent

NEW_PATH = ROOT / "outputs" / "idea4_holdout_v6_2026-05-18_gl_calibration.json"
OLD_PATH = ROOT / "outputs" / "idea4_holdout_v6_2026-05-18_no_gl.json"

# Same JGAAP event detection as Recipe A v2
def _f(v):
    if v is None: return None
    try: return float(v)
    except: return None

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

def _wilson(hits, n, z=1.96):
    if n == 0: return (None, None)
    p = hits/n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    r = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den
    return (max(0.0,(c-r)*100), min(100.0,(c+r)*100))

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
    print("Idea 4 Phase 4c — Paired A/B Comparison\n", flush=True)
    with open(NEW_PATH, encoding="utf-8") as f:
        new_data = json.load(f)
    with open(OLD_PATH, encoding="utf-8") as f:
        old_data = json.load(f)

    print(f"NEW prompt cost: ${new_data['usage_stats']['estimated_cost_usd']:.3f}", flush=True)
    print(f"OLD prompt cost: ${old_data['usage_stats']['estimated_cost_usd']:.3f}", flush=True)
    print(f"COMBINED Phase 4 cost: ${new_data['usage_stats']['estimated_cost_usd'] + old_data['usage_stats']['estimated_cost_usd']:.3f}\n",
          flush=True)

    # Build event registry for the 15 held-out tickers
    tickers = new_data["tickers"]
    event_reg = defaultdict(list)
    for tk in tickers:
        for ev in detect_events(tk):
            event_reg[(ev[0], ev[1])].append(ev[2])

    # Compare verdicts per (ticker, pair) — running rolling-window predictions
    flips = []  # cases where verdict differed
    pair_records = []  # all records with both verdicts + outcome

    for tk in tickers:
        new_t = new_data["per_ticker"].get(tk, {})
        old_t = old_data["per_ticker"].get(tk, {})
        new_pairs = new_t.get("pairs", [])
        old_pairs = old_t.get("pairs", [])
        # Index by (prev_fy, curr_fy)
        new_by_key = {(p["prev_fy"], p["curr_fy"]): p for p in new_pairs}
        old_by_key = {(p["prev_fy"], p["curr_fy"]): p for p in old_pairs}
        # Rolling-window: pair i's judgment scored vs pair i+1's outcome
        all_pairs = sorted(set(new_by_key.keys()) | set(old_by_key.keys()))
        for i in range(len(all_pairs) - 1):
            pred_key = all_pairs[i]
            outcome_key = all_pairs[i + 1]
            outcome_pair_record = new_by_key.get(outcome_key) or old_by_key.get(outcome_key)
            if outcome_pair_record is None:
                continue
            new_pred = new_by_key.get(pred_key, {})
            old_pred = old_by_key.get(pred_key, {})
            new_j = new_pred.get("judgment")
            old_j = old_pred.get("judgment")
            # Recipe A v2 outcome
            op_yoy = outcome_pair_record.get("op_profit_delta_pct")
            outcome_fy = outcome_key[1]
            evs = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
            outcome = score_v2(op_yoy, bool(evs))
            new_verdict = score_pred(new_j, outcome)
            old_verdict = score_pred(old_j, outcome)
            rec = {
                "ticker": tk,
                "prediction_pair": f"FY{pred_key[0]}->FY{pred_key[1]}",
                "outcome_pair": f"FY{outcome_key[0]}->FY{outcome_key[1]}",
                "new_judgment": new_j,
                "old_judgment": old_j,
                "op_yoy_next": op_yoy,
                "has_bad_event_2y": bool(evs),
                "outcome_a_v2": outcome,
                "new_verdict": new_verdict,
                "old_verdict": old_verdict,
                "flipped": new_j != old_j,
            }
            pair_records.append(rec)
            if new_j != old_j:
                flips.append(rec)

    print(f"=" * 100, flush=True)
    print(f"VERDICT FLIPS — cases where NEW and OLD prompts disagreed", flush=True)
    print(f"=" * 100, flush=True)
    print(f"Total pair-predictions in held-out: {len(pair_records)}", flush=True)
    print(f"Verdicts flipped between OLD and NEW: {len(flips)} "
          f"({len(flips)/len(pair_records)*100:.1f}% if any)\n", flush=True)

    if flips:
        print(f"{'ticker':<8}{'pair':<22}{'OLD verdict':<18}{'→':^4}{'NEW verdict':<18}"
              f"{'outcome':<12}{'old A/v2':<10}{'new A/v2':<10}", flush=True)
        print("-" * 100, flush=True)
        for r in flips:
            print(f"  {r['ticker']:<6}{r['prediction_pair']:<22}{r['old_judgment'] or '?':<18}"
                  f"{'→':^4}{r['new_judgment'] or '?':<18}{r['outcome_a_v2']:<12}"
                  f"{r['old_verdict']:<10}{r['new_verdict']:<10}", flush=True)

    # Class precision compare
    print(f"\n{'='*100}", flush=True)
    print(f"PRECISION BY CLASS — OLD vs NEW", flush=True)
    print(f"{'='*100}", flush=True)
    def class_metrics(records, judgment_key):
        confident = [r for r in records if r[judgment_key] in ("growth_likely", "growth_unlikely")]
        per_class = {}
        for cls in ("growth_likely", "growth_unlikely", "uncertain"):
            sub = [r for r in records if r[judgment_key] == cls]
            verdict_key = "new_verdict" if judgment_key == "new_judgment" else "old_verdict"
            h = sum(1 for r in sub if r[verdict_key] == "hit")
            m = sum(1 for r in sub if r[verdict_key] == "miss")
            a = sum(1 for r in sub if r[verdict_key] == "abstain")
            c = h + m
            prec = h/c*100 if c else None
            ci = _wilson(h, c)
            per_class[cls] = {"n": len(sub), "hit": h, "miss": m, "abstain": a,
                              "precision_pct": round(prec, 1) if prec is not None else None,
                              "ci_95_pct": (round(ci[0], 1), round(ci[1], 1)) if ci[0] is not None else None}
        # Overall (confident only)
        h_total = sum(c["hit"] for c in per_class.values() if isinstance(c, dict))
        m_total = sum(c["miss"] for c in per_class.values() if isinstance(c, dict))
        total_conf = h_total + m_total
        overall = h_total/total_conf*100 if total_conf else None
        overall_ci = _wilson(h_total, total_conf)
        return per_class, overall, overall_ci, h_total, m_total

    print(f"\n--- OLD PROMPT (without GL rules) on held-out 15 ---", flush=True)
    old_pc, old_overall, old_ci, old_h, old_m = class_metrics(pair_records, "old_judgment")
    print(f"  Overall: {old_overall}% CI [{old_ci[0]:.1f}-{old_ci[1]:.1f}]  ({old_h}H/{old_m}M)" if old_overall else "n/a", flush=True)
    for cls, c in old_pc.items():
        p = c['precision_pct']; ci = c['ci_95_pct']
        p_s = f"{p}%" if p is not None else "n/a"
        ci_s = f"[{ci[0]}-{ci[1]}]" if ci else ""
        print(f"    {cls:18s}: n={c['n']}, hit={c['hit']}, miss={c['miss']}, abstain={c['abstain']}, prec={p_s} {ci_s}", flush=True)

    print(f"\n--- NEW PROMPT (with GL rules) on held-out 15 ---", flush=True)
    new_pc, new_overall, new_ci, new_h, new_m = class_metrics(pair_records, "new_judgment")
    print(f"  Overall: {new_overall}% CI [{new_ci[0]:.1f}-{new_ci[1]:.1f}]  ({new_h}H/{new_m}M)" if new_overall else "n/a", flush=True)
    for cls, c in new_pc.items():
        p = c['precision_pct']; ci = c['ci_95_pct']
        p_s = f"{p}%" if p is not None else "n/a"
        ci_s = f"[{ci[0]}-{ci[1]}]" if ci else ""
        print(f"    {cls:18s}: n={c['n']}, hit={c['hit']}, miss={c['miss']}, abstain={c['abstain']}, prec={p_s} {ci_s}", flush=True)

    # Abstain rate comparison
    old_abstain_pct = sum(1 for r in pair_records if r["old_judgment"] == "uncertain") / len(pair_records) * 100 if pair_records else 0
    new_abstain_pct = sum(1 for r in pair_records if r["new_judgment"] == "uncertain") / len(pair_records) * 100 if pair_records else 0
    print(f"\nAbstain rate: OLD={old_abstain_pct:.1f}% → NEW={new_abstain_pct:.1f}% (Δ {new_abstain_pct - old_abstain_pct:+.1f}pp)", flush=True)

    # Save
    out = ROOT / "outputs" / "idea4_phase4_ab_comparison.json"
    out.write_text(json.dumps({
        "n_pair_records": len(pair_records),
        "n_flipped": len(flips),
        "old_overall_precision": old_overall,
        "old_overall_ci": old_ci,
        "old_by_class": old_pc,
        "old_abstain_rate_pct": old_abstain_pct,
        "new_overall_precision": new_overall,
        "new_overall_ci": new_ci,
        "new_by_class": new_pc,
        "new_abstain_rate_pct": new_abstain_pct,
        "flips_detail": flips,
        "all_pair_records": pair_records,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
