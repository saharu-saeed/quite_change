"""LLM-with-V1-veto mode.

Rule:
  - If LLM says growth_likely AND V1 says growth_unlikely → veto → emit "uncertain"
  - If LLM says growth_unlikely AND V1 says growth_likely → veto → emit "uncertain"
  - Otherwise, keep the LLM verdict.

Hypothesis: V1's disagreement is a stronger signal than V1's agreement.
Filtering out the cases where V1 strongly disagrees with LLM should remove
the LLM's worst calls without losing much volume.

Reuses pre-computed verdicts in code_based_scorer_v2_results.json.
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


def veto_verdict(llm, v1):
    """LLM-with-V1-veto rule."""
    if llm == "growth_likely" and v1 == "growth_unlikely":
        return "uncertain"  # veto
    if llm == "growth_unlikely" and v1 == "growth_likely":
        return "uncertain"  # veto
    return llm


def precision_for(rows, verdict_key, outcome_key):
    h = sum(1 for r in rows if r[outcome_key] == "hit")
    m = sum(1 for r in rows if r[outcome_key] == "miss")
    c = h + m
    prec = h/c*100 if c else None
    ci = _wilson(h, c)
    return h, m, c, prec, ci


def fmt(h, m, c, prec, ci):
    if prec is None: return f"n/a (kept={h+m})"
    return f"{prec:5.1f}% ({h}/{c}) CI [{ci[0]:.1f}-{ci[1]:.1f}]"


def main():
    print("LLM-with-V1-veto test\n", flush=True)
    print("Rule: if LLM and V1 strongly disagree → emit uncertain. Else keep LLM.\n", flush=True)

    with open(ROOT / "outputs" / "code_based_scorer_v2_results.json", encoding="utf-8") as f:
        data = json.load(f)
    rows = data["rows"]

    for r in rows:
        r["llm_outcome_score"] = score_pred(r["llm_verdict"], r["outcome_multi_axis"])
        r["veto_verdict"] = veto_verdict(r["llm_verdict"], r["code_v1_verdict"])
        r["veto_outcome_score"] = score_pred(r["veto_verdict"], r["outcome_multi_axis"])

    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]

    def report(cohort, label):
        print(f"=" * 90, flush=True)
        print(f"  {label}  (n={len(cohort)})", flush=True)
        print(f"=" * 90, flush=True)

        # Count vetoes
        veto_count = sum(1 for r in cohort if (
            (r["llm_verdict"] == "growth_likely" and r["code_v1_verdict"] == "growth_unlikely")
            or (r["llm_verdict"] == "growth_unlikely" and r["code_v1_verdict"] == "growth_likely")
        ))
        veto_correct = sum(1 for r in cohort if (
            (r["llm_verdict"] == "growth_likely" and r["code_v1_verdict"] == "growth_unlikely"
             and r["llm_outcome_score"] == "miss")
            or (r["llm_verdict"] == "growth_unlikely" and r["code_v1_verdict"] == "growth_likely"
                and r["llm_outcome_score"] == "miss")
        ))
        print(f"\n  Veto fired on {veto_count} cases; LLM would have been wrong on {veto_correct} of them "
              f"({veto_correct/veto_count*100 if veto_count else 0:.0f}%).", flush=True)

        print(f"\n  {'Class':<22}{'LLM alone':<32}{'LLM + V1 veto':<32}", flush=True)
        print("  " + "-" * 86, flush=True)
        for cls in ("growth_likely", "growth_unlikely"):
            llm = [r for r in cohort if r["llm_verdict"] == cls]
            veto = [r for r in cohort if r["veto_verdict"] == cls]
            lh,lm_,lc,lp,lci = precision_for(llm, "llm_verdict", "llm_outcome_score")
            vh,vm,vc,vp,vci = precision_for(veto, "veto_verdict", "veto_outcome_score")
            print(f"  {cls:<22}{fmt(lh,lm_,lc,lp,lci):<32}{fmt(vh,vm,vc,vp,vci):<32}", flush=True)

        # Abstain rate
        abs_llm = sum(1 for r in cohort if r["llm_verdict"] == "uncertain")
        abs_veto = sum(1 for r in cohort if r["veto_verdict"] == "uncertain")
        print(f"\n  Abstain rate: LLM {abs_llm}/{len(cohort)} ({abs_llm/len(cohort)*100:.0f}%) → "
              f"LLM+veto {abs_veto}/{len(cohort)} ({abs_veto/len(cohort)*100:.0f}%) "
              f"(+{(abs_veto-abs_llm)/len(cohort)*100:.0f}pp)", flush=True)

    report(rows, "FULL cohort (45 tickers)")
    print()
    report(train, "TRAIN cohort (15 tickers)")
    print()
    report(test, "TEST — held-out (30 tickers)")

    # Show the specific vetoed cases on TEST
    print("\n" + "=" * 90, flush=True)
    print("Vetoed cases on TEST cohort", flush=True)
    print("=" * 90, flush=True)
    vetoed = [r for r in test if r["veto_verdict"] == "uncertain"
              and r["llm_verdict"] != "uncertain"]
    print(f"\n{'Ticker':<8}{'Pair':<22}{'LLM':<18}{'V1':<18}{'LLM was':<10}", flush=True)
    print("-" * 76, flush=True)
    for r in vetoed:
        print(f"  {r['ticker']:<6}{r['prediction_pair']:<22}{r['llm_verdict']:<18}"
              f"{r['code_v1_verdict']:<18}"
              f"{'WRONG' if r['llm_outcome_score']=='miss' else 'RIGHT'}", flush=True)

    # ========================================================================
    # Headline summary table
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("HEADLINE", flush=True)
    print("=" * 90, flush=True)
    print(f"\n{'Cohort':<14}{'Class':<22}{'LLM alone':<24}{'LLM + V1 veto':<24}", flush=True)
    print("-" * 84, flush=True)
    for label, cohort in [("FULL", rows), ("TRAIN", train), ("TEST", test)]:
        for cls in ("growth_likely", "growth_unlikely"):
            llm = [r for r in cohort if r["llm_verdict"] == cls]
            veto = [r for r in cohort if r["veto_verdict"] == cls]
            lh,_,lc,lp,_ = precision_for(llm, "llm_verdict", "llm_outcome_score")
            vh,_,vc,vp,_ = precision_for(veto, "veto_verdict", "veto_outcome_score")
            llm_s = f"{lp:.1f}% ({lh}/{lc})" if lp is not None else f"n/a"
            veto_s = f"{vp:.1f}% ({vh}/{vc})" if vp is not None else f"n/a"
            delta = f"{vp - lp:+.1f}pp" if (lp is not None and vp is not None) else "n/a"
            print(f"  {label:<12}{cls:<22}{llm_s:<24}{veto_s:<20}{delta}", flush=True)
        print(f"  {'-'*12}", flush=True)

    out = ROOT / "outputs" / "llm_with_v1_veto_results.json"
    out.write_text(json.dumps({"n": len(rows), "rows": rows},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
