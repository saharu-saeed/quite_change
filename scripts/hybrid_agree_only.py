"""Hybrid agree-only mode test.

Hypothesis: when LLM and V1 BOTH say growth_likely (or BOTH say growth_unlikely),
the call is high-conviction and precision should be substantially higher than
either alone.

Method: reuse the V1 verdicts already computed in
code_based_scorer_v2_results.json. Bucket by (LLM, V1) verdict pair, compute
precision in each bucket under the multi-axis outcome metric.

Reports: TRAIN-only, TEST-only (held-out 30 tickers), and FULL.
"""
from __future__ import annotations
import json
import sys
import io
import math
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent


def _wilson(hits, n, z=1.96):
    if n == 0: return (None, None)
    p = hits/n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    r = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den
    return (max(0.0,(c-r)*100), min(100.0,(c+r)*100))


def score_pred(judgment, outcome):
    if outcome == "n/a": return "n/a"
    if judgment == "uncertain": return "abstain"
    if judgment == "growth_likely" and outcome == "positive": return "hit"
    if judgment == "growth_unlikely" and outcome == "negative": return "hit"
    return "miss"


def precision_for(rows):
    h = sum(1 for r in rows if r["outcome_score"] == "hit")
    m = sum(1 for r in rows if r["outcome_score"] == "miss")
    c = h + m
    prec = h/c*100 if c else None
    ci = _wilson(h, c)
    return h, m, c, prec, ci


def fmt(h, m, c, prec, ci):
    if prec is None: return f"n/a (n={h+m})"
    return f"{prec:5.1f}% ({h}/{c}) CI [{ci[0]:.1f}-{ci[1]:.1f}]"


def main():
    print("Hybrid agree-only test — when LLM and V1 agree, how good is the call?\n", flush=True)

    # Load V2 results — has both code_v1_verdict and llm_verdict per row
    with open(ROOT / "outputs" / "code_based_scorer_v2_results.json", encoding="utf-8") as f:
        data = json.load(f)
    rows = data["rows"]

    # Re-derive outcome score for each verdict source using stored outcome
    for r in rows:
        r["llm_outcome_score"] = score_pred(r["llm_verdict"], r["outcome_multi_axis"])
        r["v1_outcome_score"] = score_pred(r["code_v1_verdict"], r["outcome_multi_axis"])

    print(f"Total predictions: {len(rows)}", flush=True)
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    print(f"  TRAIN: {len(train)}  TEST: {len(test)}\n", flush=True)

    def evaluate_block(cohort, label):
        print(f"=" * 90, flush=True)
        print(f"  {label}  (n={len(cohort)})", flush=True)
        print(f"=" * 90, flush=True)

        # Baseline: LLM alone, V1 alone
        print(f"\n{'Source':<30}{'growth_likely':<32}{'growth_unlikely':<32}", flush=True)
        print("-" * 94, flush=True)
        for src_name, vk, ok in [("LLM alone", "llm_verdict", "llm_outcome_score"),
                                 ("V1 alone (code, 4 indicators)", "code_v1_verdict", "v1_outcome_score")]:
            gl = [r for r in cohort if r[vk] == "growth_likely"]
            for r in gl: r["outcome_score"] = r[ok]
            h,m,c,p,ci = precision_for(gl)
            gu = [r for r in cohort if r[vk] == "growth_unlikely"]
            for r in gu: r["outcome_score"] = r[ok]
            h2,m2,c2,p2,ci2 = precision_for(gu)
            print(f"  {src_name:<28}{fmt(h,m,c,p,ci):<32}{fmt(h2,m2,c2,p2,ci2):<32}", flush=True)

        # Agree-only: both say growth_likely, both say growth_unlikely
        agree_gl = [r for r in cohort if r["llm_verdict"] == "growth_likely" and r["code_v1_verdict"] == "growth_likely"]
        for r in agree_gl: r["outcome_score"] = r["llm_outcome_score"]  # both agree, either works
        agree_gu = [r for r in cohort if r["llm_verdict"] == "growth_unlikely" and r["code_v1_verdict"] == "growth_unlikely"]
        for r in agree_gu: r["outcome_score"] = r["llm_outcome_score"]
        h,m,c,p,ci = precision_for(agree_gl)
        h2,m2,c2,p2,ci2 = precision_for(agree_gu)
        print(f"\n  {'AGREE-ONLY (LLM ∩ V1)':<28}{fmt(h,m,c,p,ci):<32}{fmt(h2,m2,c2,p2,ci2):<32}", flush=True)

        # Disagreement cases
        only_llm_gl = [r for r in cohort if r["llm_verdict"] == "growth_likely" and r["code_v1_verdict"] != "growth_likely"]
        only_v1_gl = [r for r in cohort if r["llm_verdict"] != "growth_likely" and r["code_v1_verdict"] == "growth_likely"]
        only_llm_gu = [r for r in cohort if r["llm_verdict"] == "growth_unlikely" and r["code_v1_verdict"] != "growth_unlikely"]
        only_v1_gu = [r for r in cohort if r["llm_verdict"] != "growth_unlikely" and r["code_v1_verdict"] == "growth_unlikely"]

        print(f"\n  Disagreement breakdown:", flush=True)
        print(f"    LLM=likely but V1≠likely:        n={len(only_llm_gl):3d}  (LLM was right: "
              f"{sum(1 for r in only_llm_gl if r['llm_outcome_score']=='hit')} times, "
              f"wrong: {sum(1 for r in only_llm_gl if r['llm_outcome_score']=='miss')})", flush=True)
        print(f"    V1=likely but LLM≠likely:        n={len(only_v1_gl):3d}  (V1 was right: "
              f"{sum(1 for r in only_v1_gl if r['v1_outcome_score']=='hit')} times, "
              f"wrong: {sum(1 for r in only_v1_gl if r['v1_outcome_score']=='miss')})", flush=True)
        print(f"    LLM=unlikely but V1≠unlikely:    n={len(only_llm_gu):3d}  (LLM was right: "
              f"{sum(1 for r in only_llm_gu if r['llm_outcome_score']=='hit')} times, "
              f"wrong: {sum(1 for r in only_llm_gu if r['llm_outcome_score']=='miss')})", flush=True)
        print(f"    V1=unlikely but LLM≠unlikely:    n={len(only_v1_gu):3d}  (V1 was right: "
              f"{sum(1 for r in only_v1_gu if r['v1_outcome_score']=='hit')} times, "
              f"wrong: {sum(1 for r in only_v1_gu if r['v1_outcome_score']=='miss')})", flush=True)

        return {
            "agree_gl": (h,m,c,p),
            "agree_gu": (h2,m2,c2,p2),
            "only_llm_gl": (len(only_llm_gl), sum(1 for r in only_llm_gl if r['llm_outcome_score']=='hit')),
            "only_v1_gl": (len(only_v1_gl), sum(1 for r in only_v1_gl if r['v1_outcome_score']=='hit')),
        }

    full = evaluate_block(rows, "FULL cohort (45 tickers)")
    print()
    train_r = evaluate_block(train, "TRAIN cohort (15 tickers)")
    print()
    test_r = evaluate_block(test, "TEST — held-out (30 tickers)")

    # ========================================================================
    # Summary table — the headline numbers
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("HEADLINE — agree-only precision comparison", flush=True)
    print("=" * 90, flush=True)
    print(f"\n{'Cohort':<14}{'Class':<20}{'LLM alone':<22}{'V1 alone':<22}{'AGREE-ONLY':<22}", flush=True)
    print("-" * 100, flush=True)
    for label, cohort in [("FULL", rows), ("TRAIN", train), ("TEST", test)]:
        for cls in ("growth_likely", "growth_unlikely"):
            llm = [r for r in cohort if r["llm_verdict"] == cls]
            for r in llm: r["outcome_score"] = r["llm_outcome_score"]
            _,_,_,llm_p,_ = precision_for(llm)
            v1 = [r for r in cohort if r["code_v1_verdict"] == cls]
            for r in v1: r["outcome_score"] = r["v1_outcome_score"]
            _,_,_,v1_p,_ = precision_for(v1)
            ag = [r for r in cohort if r["llm_verdict"] == cls and r["code_v1_verdict"] == cls]
            for r in ag: r["outcome_score"] = r["llm_outcome_score"]
            h,m,c,ag_p,ag_ci = precision_for(ag)
            llm_s = f"{llm_p:.1f}% (n={len(llm)})" if llm_p is not None else f"n/a ({len(llm)})"
            v1_s = f"{v1_p:.1f}% (n={len(v1)})" if v1_p is not None else f"n/a ({len(v1)})"
            ag_s = f"{ag_p:.1f}% ({h}/{c})" if ag_p is not None else f"n/a ({h+m})"
            print(f"  {label:<12}{cls:<20}{llm_s:<22}{v1_s:<22}{ag_s:<22}", flush=True)
        print(f"  {'-'*12}", flush=True)

    # Save
    out = ROOT / "outputs" / "hybrid_agree_only_results.json"
    out.write_text(json.dumps({"full": full, "train": train_r, "test": test_r,
                              "rows": rows}, ensure_ascii=False, indent=2, default=str),
                  encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
