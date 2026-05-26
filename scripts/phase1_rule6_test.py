"""Phase 1 Rule 6: 'big op-profit jump + weak peer dominance' candidate.

Hypothesis: companies with a very large op_profit jump (op_yoy > 50%) but
only weakly beating peers (peer_gap < +10pp) are showing an unsustainable
one-time surge, not structural growth.

Tests Rule 6 in isolation AND stacked on top of Rule 5 + Rule 2 (GU).
Sweeps thresholds to find the best operating point.
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


def load_all():
    """For each pair, return: pre_veto_judgment (LLM raw), peer_gap, cfo_ni,
    op_profit_delta_pct, post_R5_judgment (after Rule 5/2 vetoes), outcome score."""
    out = {}
    for tk in ALL_JGAAP:
        files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                     f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if not files:
            continue
        with open(files[-1], encoding="utf-8") as f:
            data = json.load(f)
        # Strip prior enrichment and re-run
        result = copy.deepcopy(data)
        for pair in result.get("pairs", []):
            for k in ("confidence_label", "confidence_factors",
                      "veto_triggered", "veto_rule", "veto_reason", "original_judgment"):
                pair.pop(k, None)
        _enrich_pairs_with_confidence(result)
        for pair in result.get("pairs", []):
            if pair.get("history_only"):
                continue
            prev_fy = pair.get("prev_fiscal_year")
            curr_fy = pair.get("curr_fiscal_year")
            if prev_fy is None or curr_fy is None:
                continue
            key = (tk, f"FY{prev_fy}->FY{curr_fy}")
            pc = pair.get("peer_comparison") or {}
            my = pc.get("my") or {}
            med = pc.get("sector_median") or {}
            peer_gap = (my.get("op_margin_pct") - med.get("op_margin_pct")) \
                if my.get("op_margin_pct") is not None and med.get("op_margin_pct") is not None else None
            out[key] = {
                "pre_veto_judgment": pair.get("original_judgment"),
                "post_R5_judgment": pair.get("outlook_judgment"),
                "veto_triggered_R5": pair.get("veto_triggered"),
                "peer_gap_pp": peer_gap,
                "op_profit_delta_pct": pair.get("op_profit_delta_pct"),
            }
    return out


def rule6_test(rows, op_yoy_thresh, peer_gap_upper):
    """Apply Rule 6 on top of existing Rule 5 results. Returns new rows
    with post_R6_judgment + score."""
    new_rows = []
    for r in rows:
        post_r5 = r["post_R5_judgment"]
        post_r6 = post_r5
        fired = False
        if post_r5 == "growth_likely":
            op_yoy = r.get("op_profit_delta_pct")
            peer_gap = r.get("peer_gap_pp")
            if (op_yoy is not None and op_yoy > op_yoy_thresh
                    and peer_gap is not None and peer_gap < peer_gap_upper):
                post_r6 = "uncertain"
                fired = True
        # Score
        outcome = r["outcome_lenient"]
        if post_r6 == "uncertain":
            score = "abstain"
        elif post_r6 == "growth_likely" and outcome == "positive":
            score = "hit"
        elif post_r6 == "growth_unlikely" and outcome == "negative":
            score = "hit"
        else:
            score = "miss"
        new_rows.append({**r, "post_R6_judgment": post_r6, "R6_fired": fired, "post_R6_score": score})
    return new_rows


def precision(rows, score_key, verdict_key=None, verdict_val=None):
    if verdict_key:
        rows = [r for r in rows if r[verdict_key] == verdict_val]
    h = sum(1 for r in rows if r[score_key] == "hit")
    m = sum(1 for r in rows if r[score_key] == "miss")
    c = h + m
    p = h/c*100 if c else None
    ci = _wilson(h, c)
    return h, m, c, p, ci


def main():
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes = json.load(f)["rows"]
    enrich = load_all()
    rows = []
    for r in outcomes:
        key = (r["ticker"], r["prediction_pair"])
        e = enrich.get(key)
        if not e:
            continue
        # Compute the Rule-5 post-veto score (re-derive from outcome)
        post_r5 = e["post_R5_judgment"]
        outcome = r["outcome_lenient"]
        if post_r5 == "uncertain":
            r5_score = "abstain"
        elif post_r5 == "growth_likely" and outcome == "positive":
            r5_score = "hit"
        elif post_r5 == "growth_unlikely" and outcome == "negative":
            r5_score = "hit"
        else:
            r5_score = "miss"
        rows.append({**r, **e, "post_R5_score": r5_score})

    # ======== Sweep thresholds ========
    print("=" * 110)
    print("RULE 6 THRESHOLD SWEEP")
    print("=" * 110)
    print(f"\nBaseline (LLM raw):         "
          f"GL prec = {precision(rows, 'llm_lenient_score', 'llm_verdict', 'growth_likely')[3]:.1f}%  "
          f"(n_GL={sum(1 for r in rows if r['llm_verdict']=='growth_likely')})")
    print(f"After Rule 5 + GU-2:        "
          f"GL prec = {precision(rows, 'post_R5_score', 'post_R5_judgment', 'growth_likely')[3]:.1f}%  "
          f"(n_GL={sum(1 for r in rows if r['post_R5_judgment']=='growth_likely')})")

    print(f"\n{'op_yoy>':<10}{'peer<':<8}{'fired':<8}{'caught_miss':<14}{'killed_hit':<12}"
          f"{'GL_prec_post_R6':<22}{'volume':<10}")
    print("-" * 100)
    for op_t in [40, 50, 60, 70, 100]:
        for pg_u in [5, 7, 10, 15, 999]:  # 999 = ignore peer threshold
            test_rows = rule6_test(rows, op_t, pg_u)
            fired_total = sum(1 for r in test_rows if r["R6_fired"])
            fired_were_hit = sum(1 for r in test_rows if r["R6_fired"] and r["post_R5_score"] == "hit")
            fired_were_miss = sum(1 for r in test_rows if r["R6_fired"] and r["post_R5_score"] == "miss")
            h, m, c, p, ci = precision(test_rows, "post_R6_score", "post_R6_judgment", "growth_likely")
            pstr = f"{p:.1f}% ({h}/{c}) CI[{ci[0]:.0f}-{ci[1]:.0f}]" if p is not None else "n/a"
            base_n = sum(1 for r in rows if r['llm_verdict']=='growth_likely')
            print(f"{op_t:<10}{pg_u:<8}{fired_total:<8}{fired_were_miss:<14}{fired_were_hit:<12}"
                  f"{pstr:<22}{c}/{base_n}")

    # ======== Best choice: op_yoy > 50 AND peer < 10 ========
    print("\n" + "=" * 110)
    print("RULE 6 BEST OPERATING POINT: op_yoy > 50% AND peer_gap < 10pp")
    print("=" * 110)
    best_rows = rule6_test(rows, 50, 10)

    for cohort_name, cohort_set in [("FULL (45t)", ALL_JGAAP), ("TRAIN (15t)", TRAIN_TICKERS), ("TEST (30t)", TEST_TICKERS)]:
        sub = [r for r in best_rows if r["ticker"] in cohort_set]
        print(f"\n  {cohort_name}  (n={len(sub)})")
        # Compare LLM raw / post-R5 / post-R6 on GL precision
        for stage, score_key, verdict_key, verdict_val in [
            ("LLM raw",     "llm_lenient_score", "llm_verdict",        "growth_likely"),
            ("+Rule 5/2",   "post_R5_score",     "post_R5_judgment",   "growth_likely"),
            ("+Rule 6",     "post_R6_score",     "post_R6_judgment",   "growth_likely"),
        ]:
            h, m, c, p, ci = precision(sub, score_key, verdict_key, verdict_val)
            pstr = f"{p:5.1f}% ({h}/{c}) CI[{ci[0]:.0f}-{ci[1]:.0f}]" if p is not None else "n/a"
            print(f"    {stage:<14} GL: {pstr}")

    # ======== Cases fired ========
    print("\n" + "=" * 110)
    print("RULE 6 FIRED on these cases:")
    print("=" * 110)
    fired = [r for r in best_rows if r["R6_fired"]]
    for r in fired:
        split = "train" if r["ticker"] in TRAIN_TICKERS else "test"
        print(f"  {r['ticker']} {r['prediction_pair']:<22} op_yoy={r['op_profit_delta_pct']:+.2f}%  "
              f"peer_gap={r['peer_gap_pp']:+.2f}pp  outcome={r['outcome_lenient']:<10} "
              f"pre_R5_score={r['llm_lenient_score']:<8} [{split}]")

    out = ROOT / "outputs" / "phase1_rule6_test.json"
    out.write_text(json.dumps({"rows": best_rows}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()
