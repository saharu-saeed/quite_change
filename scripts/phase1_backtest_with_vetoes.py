"""Phase 1 backtest: confirm the veto layer (Rule 5 GL + Rule 2 GU) actually
delivers the predicted +9.7pp precision gain when applied through the live
pipeline.

This invokes _enrich_pairs_with_confidence on freshly-loaded cache files,
which now applies the veto and downgrades outlook_judgment to "uncertain"
when the rule fires. We then re-score against the lenient outcome metric
and compare to baseline.
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
import copy
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import _enrich_pairs_with_confidence

JGAAP_ORIG = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697"]
JGAAP_OOS = ["4063","4716","4751","6861"]
JGAAP_EXT = ["3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
             "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"]
TRAIN_TICKERS = set(JGAAP_ORIG + JGAAP_OOS)
TEST_TICKERS = set(JGAAP_EXT)
ALL_JGAAP = TRAIN_TICKERS | TEST_TICKERS


def _wilson(hits, n, z=1.96):
    if n == 0: return (None, None)
    p = hits/n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    r = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den
    return (max(0.0,(c-r)*100), min(100.0,(c+r)*100))


def load_vetoed_predictions():
    """{(ticker, pred_pair): {pre_veto_judgment, post_veto_judgment, veto_rule, veto_reason}}"""
    out = {}
    for tk in ALL_JGAAP:
        files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                     f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if not files:
            continue
        with open(files[-1], encoding="utf-8") as f:
            data = json.load(f)
        # Strip pre-existing enrichment so the function re-runs cleanly
        result = copy.deepcopy(data)
        for pair in result.get("pairs", []):
            for k in ("confidence_label", "confidence_factors",
                      "veto_triggered", "veto_rule", "veto_reason", "original_judgment"):
                pair.pop(k, None)
        # Run the live enrichment path
        _enrich_pairs_with_confidence(result)
        for pair in result.get("pairs", []):
            if pair.get("history_only"):
                continue
            prev_fy = pair.get("prev_fiscal_year")
            curr_fy = pair.get("curr_fiscal_year")
            if prev_fy is None or curr_fy is None:
                continue
            key = (tk, f"FY{prev_fy}->FY{curr_fy}")
            out[key] = {
                "pre_veto_judgment": pair.get("original_judgment"),
                "post_veto_judgment": pair.get("outlook_judgment"),
                "veto_triggered": pair.get("veto_triggered"),
                "veto_rule": pair.get("veto_rule"),
                "veto_reason": pair.get("veto_reason"),
                "confidence_label": pair.get("confidence_label"),
            }
    return out


def main():
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes = json.load(f)["rows"]

    vetoed = load_vetoed_predictions()

    rows = []
    for r in outcomes:
        key = (r["ticker"], r["prediction_pair"])
        v = vetoed.get(key)
        if not v:
            continue
        # Re-score with post-veto judgment
        outcome_lenient = r["outcome_lenient"]
        post = v["post_veto_judgment"]
        if post == "uncertain":
            post_score = "abstain"
        elif post == "growth_likely" and outcome_lenient == "positive":
            post_score = "hit"
        elif post == "growth_unlikely" and outcome_lenient == "negative":
            post_score = "hit"
        else:
            post_score = "miss"
        rows.append({
            **r,
            "pre_veto_judgment": v["pre_veto_judgment"],
            "post_veto_judgment": post,
            "veto_triggered": v["veto_triggered"],
            "veto_rule": v["veto_rule"],
            "veto_reason": v["veto_reason"],
            "post_veto_score": post_score,
        })

    # ============================================================
    # Headline: precision before vs after, FULL cohort
    # ============================================================
    print("=" * 100)
    print(f"PHASE 1 BACKTEST — Rule 5 (GL) + Rule 2 (GU) applied through live pipeline")
    print(f"n={len(rows)}")
    print("=" * 100)

    for cohort_name, cohort_set in [("FULL (45t)", ALL_JGAAP), ("TRAIN (15t)", TRAIN_TICKERS), ("TEST (30t)", TEST_TICKERS)]:
        sub = [r for r in rows if r["ticker"] in cohort_set]
        print(f"\n  {cohort_name}  (n={len(sub)})")
        for cls in ("growth_likely", "growth_unlikely", "ALL_CONFIDENT"):
            if cls == "ALL_CONFIDENT":
                pre_sub = [r for r in sub if r["llm_verdict"] in ("growth_likely", "growth_unlikely")]
                post_sub = [r for r in sub if r["post_veto_judgment"] in ("growth_likely", "growth_unlikely")]
            else:
                pre_sub = [r for r in sub if r["llm_verdict"] == cls]
                post_sub = [r for r in sub if r["post_veto_judgment"] == cls]
            pre_h = sum(1 for r in pre_sub if r["llm_lenient_score"] == "hit")
            pre_m = sum(1 for r in pre_sub if r["llm_lenient_score"] == "miss")
            pre_c = pre_h + pre_m
            pre_p = pre_h/pre_c*100 if pre_c else None
            pre_ci = _wilson(pre_h, pre_c)
            post_h = sum(1 for r in post_sub if r["post_veto_score"] == "hit")
            post_m = sum(1 for r in post_sub if r["post_veto_score"] == "miss")
            post_c = post_h + post_m
            post_p = post_h/post_c*100 if post_c else None
            post_ci = _wilson(post_h, post_c)

            def f_(p, ci, h, c):
                if p is None: return "n/a"
                return f"{p:5.1f}% ({h}/{c}) CI[{ci[0]:.0f}-{ci[1]:.0f}]"

            delta = f"{(post_p - pre_p):+.1f}pp" if (pre_p is not None and post_p is not None) else "n/a"
            print(f"    {cls:<17} pre: {f_(pre_p, pre_ci, pre_h, pre_c):<28}"
                  f"  post: {f_(post_p, post_ci, post_h, post_c):<28}  Δ={delta}")

    # ============================================================
    # Veto firing detail
    # ============================================================
    print("\n" + "=" * 100)
    print("VETO FIRING DETAIL")
    print("=" * 100)
    vetoed_rows = [r for r in rows if r["veto_triggered"]]
    print(f"\n  Total vetoes triggered: {len(vetoed_rows)} / {len(rows)} predictions")
    from collections import Counter
    rule_counts = Counter(r["veto_rule"] for r in vetoed_rows)
    for rule, n in rule_counts.most_common():
        print(f"    {rule}: {n}")

    print(f"\n  Outcome of vetoed calls (would-have-been-confident → forced-uncertain):")
    pre_hit = sum(1 for r in vetoed_rows if r["llm_lenient_score"] == "hit")
    pre_miss = sum(1 for r in vetoed_rows if r["llm_lenient_score"] == "miss")
    pre_abstain = sum(1 for r in vetoed_rows if r["llm_lenient_score"] == "abstain")
    print(f"    Misses we now correctly abstain on (good): {pre_miss}")
    print(f"    Hits we now incorrectly abstain on (cost): {pre_hit}")
    print(f"    Already-abstaining (no effect): {pre_abstain}")
    print(f"    Net change: +{pre_miss} misses removed, -{pre_hit} hits lost  → net {pre_miss - pre_hit:+d}")

    out = ROOT / "outputs" / "phase1_backtest_with_vetoes.json"
    out.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()
