"""Phase 2 iteration: sweep growth_likely threshold without re-calling API.

Uses cached scores from outputs/phase2_haiku_design/ and just re-combines
with different thresholds. Pure code; $0.
"""
from __future__ import annotations
import json
import sys
import io
import glob
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.structured_scoring import combine_scores, DEFAULT_THRESHOLDS

CACHE_DIR = ROOT / "outputs" / "phase2_haiku_design"


def load_outcomes():
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        return {(r["ticker"], r["prediction_pair"]): r for r in json.load(f)["rows"]}


def score_against(verdict, outcome):
    if verdict == "uncertain": return "abstain"
    if verdict == "growth_likely" and outcome == "positive": return "hit"
    if verdict == "growth_unlikely" and outcome == "negative": return "hit"
    return "miss"


def evaluate(thresholds):
    outcomes = load_outcomes()
    h = m = abstain = 0
    h_gl = m_gl = h_gu = m_gu = 0
    rows = []
    for cf in CACHE_DIR.glob("*.json"):
        with open(cf, encoding="utf-8") as f:
            cached = json.load(f)
        result = combine_scores(cached["scores"], thresholds=thresholds)
        ref = outcomes.get((cached["ticker"], cached["prediction_pair"]))
        if not ref: continue
        sc = score_against(result.verdict, ref["outcome_lenient"])
        rows.append({"ticker": cached["ticker"], "pair": cached["prediction_pair"],
                     "verdict": result.verdict, "sum": result.weighted_sum,
                     "outcome": ref["outcome_lenient"], "score": sc})
        if sc == "hit":
            h += 1
            if result.verdict == "growth_likely": h_gl += 1
            else: h_gu += 1
        elif sc == "miss":
            m += 1
            if result.verdict == "growth_likely": m_gl += 1
            else: m_gu += 1
        else:
            abstain += 1
    c = h + m
    p = h/c*100 if c else None
    p_gl = h_gl/(h_gl+m_gl)*100 if (h_gl+m_gl) else None
    p_gu = h_gu/(h_gu+m_gu)*100 if (h_gu+m_gu) else None
    return {
        "thresholds": thresholds,
        "n_confident": c,
        "n_abstain": abstain,
        "hits": h, "misses": m, "precision": p,
        "gl_h": h_gl, "gl_m": m_gl, "gl_p": p_gl,
        "gu_h": h_gu, "gu_m": m_gu, "gu_p": p_gu,
        "rows": rows,
    }


def main():
    print("Sweeping growth_likely_min threshold (growth_unlikely_max fixed at 10)\n")
    print(f"{'GL min':<10}{'GU max':<10}{'GL prec':<22}{'GU prec':<22}{'ALL prec':<22}{'volume'}")
    print("-" * 110)
    for gl_min in [16.0, 16.5, 17.0, 17.5, 18.0, 18.5]:
        for gu_max in [10.0]:
            t = {"growth_likely_min": gl_min, "growth_unlikely_max": gu_max}
            r = evaluate(t)
            gl_str = f"{r['gl_p']:.1f}% ({r['gl_h']}/{r['gl_h']+r['gl_m']})" if r['gl_p'] is not None else "n/a"
            gu_str = f"{r['gu_p']:.1f}% ({r['gu_h']}/{r['gu_h']+r['gu_m']})" if r['gu_p'] is not None else "n/a"
            all_str = f"{r['precision']:.1f}% ({r['hits']}/{r['n_confident']})" if r['precision'] is not None else "n/a"
            print(f"{gl_min:<10}{gu_max:<10}{gl_str:<22}{gu_str:<22}{all_str:<22}{r['n_confident']}/50")

    # Detail for the most promising threshold
    print("\n\nDETAIL — threshold = 17.0 (recommended candidate):")
    r = evaluate({"growth_likely_min": 17.0, "growth_unlikely_max": 10.0})
    print(f"  n_confident: {r['n_confident']}  hits: {r['hits']}  misses: {r['misses']}  "
          f"precision: {r['precision']:.1f}%")
    print(f"\n  Cases that became confident (vs threshold 18):")
    # Compare to baseline (18.0)
    baseline = evaluate({"growth_likely_min": 18.0, "growth_unlikely_max": 10.0})
    b_idx = {(x["ticker"], x["pair"]): x for x in baseline["rows"]}
    for r2 in r["rows"]:
        b = b_idx.get((r2["ticker"], r2["pair"]))
        if not b: continue
        if r2["verdict"] != b["verdict"]:
            print(f"    {r2['ticker']} {r2['pair']:<22} "
                  f"sum={r2['sum']:.1f}  P2@18={b['verdict']:<18}P2@17={r2['verdict']:<18}"
                  f"outcome={r2['outcome']:<10}new_score={r2['score']}")


if __name__ == "__main__":
    main()
