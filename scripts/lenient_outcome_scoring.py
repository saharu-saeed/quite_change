"""Strict vs lenient outcome scoring — side-by-side comparison.

Methodology pre-registered at:
  outputs/lenient_outcome_methodology.md (LOCKED before this script ran)

Reports BOTH strict and lenient precision for LLM and V1 verdicts,
across TRAIN/TEST/FULL cohorts. No threshold tuning after seeing results.
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


def _ni_usable_for_threshold(prev_ni, current_revenue):
    """Adverse-event NI denominator is meaningless when prior NI is <=0 or tiny.
    Drop NI leg if prev_ni <= 0 OR abs(prev_ni) < 0.5% of current revenue.
    Per spec correctness patch 2026-05-21.
    """
    if prev_ni is None or prev_ni <= 0:
        return False
    if current_revenue and current_revenue > 0:
        if abs(prev_ni) < 0.005 * current_revenue:
            return False
    return True


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
        ni_usable = _ni_usable_for_threshold(prev_ni, rev)
        impair = annual_val(items, "impairment_loss", fy)
        if impair and impair > 0:
            equity_leg = (prev_eq and prev_eq > 0 and impair/prev_eq*100 >= 1.0)
            ni_leg = (ni_usable and impair/abs(prev_ni)*100 >= 5.0)
            if equity_leg or ni_leg:
                events.append((ticker, fy, "impairment"))
        extra = annual_val(items, "extraordinary_loss", fy)
        if extra and extra > 0:
            rev_leg = (rev and rev > 0 and extra/rev*100 >= 5.0)
            ni_leg = (ni_usable and extra/abs(prev_ni)*100 >= 10.0)
            if rev_leg or ni_leg:
                events.append((ticker, fy, "extraordinary"))
    return events


def get_op_yoy_outcome(ticker, outcome_fy):
    cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                       f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not cache_files: return None
    with open(cache_files[-1], encoding="utf-8") as f:
        d = json.load(f)
    for pair in d.get("pairs", []):
        if pair.get("history_only"): continue
        if pair.get("curr_fiscal_year") == outcome_fy:
            return pair.get("op_profit_delta_pct")
    return None


def strict_outcome(rev_yoy, op_yoy, stock_5d, has_bad):
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


def lenient_outcome(rev_yoy, op_yoy, stock_5d, has_bad):
    """PRE-REGISTERED in outputs/lenient_outcome_methodology.md.
    Lenient positive = ≥1 strong pos AND 0 strong neg AND no adverse event.
    Lenient negative = ≥1 strong neg OR adverse event (but mixed if also has pos).
    Lenient mixed = ≥1 pos AND ≥1 neg.
    """
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
    if neg >= 1:
        return "mixed" if pos >= 1 else "negative"
    if pos >= 1: return "positive"
    return "mixed"


def score(judgment, outcome):
    if judgment == "uncertain": return "abstain"
    if judgment == "growth_likely" and outcome == "positive": return "hit"
    if judgment == "growth_unlikely" and outcome == "negative": return "hit"
    return "miss"


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
    print("Strict vs Lenient outcome scoring — side-by-side\n", flush=True)
    print(f"Methodology: outputs/lenient_outcome_methodology.md (LOCKED)\n", flush=True)

    # Build event registry
    event_reg = defaultdict(list)
    for tk in ALL_JGAAP:
        for ev in detect_events(tk):
            event_reg[(ev[0], ev[1])].append(ev[2])

    # Load V1 verdicts from earlier results
    with open(ROOT / "outputs" / "code_based_scorer_v2_results.json", encoding="utf-8") as f:
        v2_data = json.load(f)
    v1_by_key = {(r["ticker"], r["prediction_pair"]): r["code_v1_verdict"] for r in v2_data["rows"]}

    # Load raw predictions
    all_preds = []
    for path in [ROOT/"outputs"/"rolling_window_backtest.json",
                 ROOT/"outputs"/"out_of_sample_rolling_window.json",
                 ROOT/"outputs"/"jgaap_extension_rolling_window.json"]:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        all_preds.extend(d["scored_predictions"])

    rows = []
    for p in all_preds:
        tk = p["ticker"]
        if tk not in ALL_JGAAP: continue
        try: outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except: outcome_fy = None

        rev = p.get("rev_delta_pct")
        stk = p.get("stock_5d_pct")
        op_outcome = get_op_yoy_outcome(tk, outcome_fy)
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
        has_bad = bool(evs_2y)

        out_strict = strict_outcome(rev, op_outcome, stk, has_bad)
        out_lenient = lenient_outcome(rev, op_outcome, stk, has_bad)
        v1 = v1_by_key.get((tk, p["prediction_pair"]), "uncertain")

        rows.append({
            "ticker": tk,
            "prediction_pair": p["prediction_pair"],
            "outcome_pair": p["outcome_pair"],
            "split": "train" if tk in TRAIN_TICKERS else "test",
            "llm_verdict": p["judgment"],
            "code_v1_verdict": v1,
            "rev_yoy": rev, "op_yoy_outcome": op_outcome, "stock_5d": stk,
            "has_adverse_event": has_bad,
            "outcome_strict": out_strict,
            "outcome_lenient": out_lenient,
            "llm_strict_score": score(p["judgment"], out_strict),
            "llm_lenient_score": score(p["judgment"], out_lenient),
            "v1_strict_score": score(v1, out_strict),
            "v1_lenient_score": score(v1, out_lenient),
        })

    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    print(f"Total predictions: {len(rows)}  TRAIN: {len(train)}  TEST: {len(test)}\n", flush=True)

    # ========================================================================
    # Outcome distribution
    # ========================================================================
    print("=" * 90, flush=True)
    print("Outcome distribution shift", flush=True)
    print("=" * 90, flush=True)
    strict_c = Counter(r["outcome_strict"] for r in rows)
    lenient_c = Counter(r["outcome_lenient"] for r in rows)
    print(f"\n{'Outcome':<14}{'Strict':<10}{'Lenient':<10}{'Δ':<10}", flush=True)
    for k in ("positive", "negative", "mixed"):
        s = strict_c.get(k, 0); l = lenient_c.get(k, 0)
        print(f"  {k:<12}{s:<10}{l:<10}{l-s:+d}", flush=True)

    reclass = sum(1 for r in rows if r["outcome_strict"] != r["outcome_lenient"])
    print(f"\nOutcomes that changed under lenient rule: {reclass}/{len(rows)} ({reclass/len(rows)*100:.1f}%)", flush=True)
    rc = Counter((r["outcome_strict"], r["outcome_lenient"]) for r in rows if r["outcome_strict"] != r["outcome_lenient"])
    print(f"\n  Reclassification breakdown:", flush=True)
    for (s, l), n in rc.most_common():
        print(f"    {s:<10} → {l:<10}  n={n}", flush=True)

    # ========================================================================
    # Precision per cohort
    # ========================================================================
    def report_cohort(cohort, label):
        print("\n" + "=" * 90, flush=True)
        print(f"  {label}  (n={len(cohort)})", flush=True)
        print("=" * 90, flush=True)
        print(f"\n  {'Source':<14}{'Class':<20}{'STRICT':<32}{'LENIENT':<32}", flush=True)
        print("  " + "-" * 98, flush=True)
        for src_name, vk, ss, ls in [
            ("LLM", "llm_verdict", "llm_strict_score", "llm_lenient_score"),
            ("V1 (code)", "code_v1_verdict", "v1_strict_score", "v1_lenient_score"),
        ]:
            for cls in ("growth_likely", "growth_unlikely"):
                sub = [r for r in cohort if r[vk] == cls]
                sh,sm,sc,sp,sci = precision_block(sub, ss)
                lh,lm,lc,lp,lci = precision_block(sub, ls)
                print(f"  {src_name:<14}{cls:<20}{fmt(sh,sm,sc,sp,sci):<32}{fmt(lh,lm,lc,lp,lci):<32}", flush=True)

    report_cohort(rows, "FULL cohort (45 tickers)")
    report_cohort(train, "TRAIN cohort")
    report_cohort(test, "TEST cohort — held-out")

    # ========================================================================
    # Headline summary table
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("HEADLINE SUMMARY", flush=True)
    print("=" * 90, flush=True)
    print(f"\n{'Cohort':<10}{'Source':<10}{'Class':<20}{'STRICT':<22}{'LENIENT':<22}{'Δ':<10}", flush=True)
    print("-" * 94, flush=True)
    for label, cohort in [("FULL", rows), ("TRAIN", train), ("TEST", test)]:
        for src_name, vk, ss, ls in [
            ("LLM", "llm_verdict", "llm_strict_score", "llm_lenient_score"),
            ("V1", "code_v1_verdict", "v1_strict_score", "v1_lenient_score"),
        ]:
            for cls in ("growth_likely", "growth_unlikely"):
                sub = [r for r in cohort if r[vk] == cls]
                sh,_,sc,sp,_ = precision_block(sub, ss)
                lh,_,lc,lp,_ = precision_block(sub, ls)
                s_s = f"{sp:.1f}% ({sh}/{sc})" if sp is not None else "n/a"
                l_s = f"{lp:.1f}% ({lh}/{lc})" if lp is not None else "n/a"
                delta = f"{lp-sp:+.1f}pp" if (sp is not None and lp is not None) else "n/a"
                print(f"  {label:<8}{src_name:<10}{cls:<20}{s_s:<22}{l_s:<22}{delta}", flush=True)
            print(f"  {'-'*6}", flush=True)

    # ========================================================================
    # Which cases got reclassified for LLM growth_likely?
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("LLM growth_likely cases flipped miss → hit under lenient (FULL)", flush=True)
    print("=" * 90, flush=True)
    flipped = [r for r in rows if r["llm_verdict"] == "growth_likely"
               and r["llm_strict_score"] == "miss" and r["llm_lenient_score"] == "hit"]
    print(f"\nn = {len(flipped)}", flush=True)
    for r in flipped:
        rev_s = f"{r['rev_yoy']:+5.1f}%" if r['rev_yoy'] is not None else "n/a"
        op_s = f"{r['op_yoy_outcome']:+5.1f}%" if r['op_yoy_outcome'] is not None else "n/a"
        stk_s = f"{r['stock_5d']:+5.1f}%" if r['stock_5d'] is not None else "n/a"
        ev = "Y" if r["has_adverse_event"] else "."
        print(f"  {r['ticker']} {r['prediction_pair']:<22} rev={rev_s:>8} op={op_s:>8} stk={stk_s:>8} "
              f"adv={ev}  strict→{r['outcome_strict']:<8} lenient→{r['outcome_lenient']}", flush=True)

    out = ROOT / "outputs" / "lenient_outcome_results.json"
    out.write_text(json.dumps({
        "methodology": "lenient_outcome_methodology.md",
        "n_total": len(rows),
        "n_outcomes_reclassified": reclass,
        "rows": rows,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
