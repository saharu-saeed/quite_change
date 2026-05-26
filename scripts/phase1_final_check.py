"""Last look at the 6 GL misses that survive all vetoes.

Pull op_margin_trend_pp from misjudgment_analysis_results.json (where it
was computed directly from raw financials), join with survivor list, and
check if any new rule emerges. If not — Phase 1 is genuinely done.
"""
from __future__ import annotations
import json
import sys
import io
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
ALL_JGAAP = set(JGAAP_ORIG + JGAAP_OOS + JGAAP_EXT)


def load_post_veto():
    out = {}
    for tk in ALL_JGAAP:
        files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                     f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if not files: continue
        with open(files[-1], encoding="utf-8") as f:
            data = json.load(f)
        result = copy.deepcopy(data)
        for pair in result.get("pairs", []):
            for k in ("confidence_label", "confidence_factors",
                      "veto_triggered", "veto_rule", "veto_reason", "original_judgment"):
                pair.pop(k, None)
        _enrich_pairs_with_confidence(result)
        for pair in result.get("pairs", []):
            if pair.get("history_only"): continue
            prev_fy = pair.get("prev_fiscal_year")
            curr_fy = pair.get("curr_fiscal_year")
            if prev_fy is None or curr_fy is None: continue
            key = (tk, f"FY{prev_fy}->FY{curr_fy}")
            out[key] = pair.get("outlook_judgment")
    return out


def main():
    # Load misjudgment file (has op_margin_trend_pp)
    with open(ROOT / "outputs" / "misjudgment_analysis_results.json", encoding="utf-8") as f:
        misj = json.load(f)
    miss_features = {}
    for m in misj["growth_likely_misses"]:
        key = (m["ticker"], m["prediction_pair"])
        miss_features[key] = m

    # Load outcomes + post-veto
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes = json.load(f)["rows"]
    post_veto = load_post_veto()

    rows = []
    for r in outcomes:
        key = (r["ticker"], r["prediction_pair"])
        post = post_veto.get(key, r["llm_verdict"])
        outcome = r["outcome_lenient"]
        if post == "uncertain":
            post_score = "abstain"
        elif post == "growth_likely" and outcome == "positive":
            post_score = "hit"
        elif post == "growth_unlikely" and outcome == "negative":
            post_score = "hit"
        else:
            post_score = "miss"
        rows.append({**r, "post_veto_judgment": post, "post_veto_score": post_score,
                     "misj_features": miss_features.get(key)})

    # Show the 6 remaining uncaught GL misses with ALL features from misj file
    remaining = [r for r in rows if r["post_veto_judgment"] == "growth_likely"
                 and r["post_veto_score"] == "miss"]
    print("=" * 130)
    print(f"REMAINING UNCAUGHT GL MISSES ({len(remaining)})")
    print("=" * 130)
    for r in sorted(remaining, key=lambda x: x["ticker"]):
        mf = r.get("misj_features") or {}
        print(f"\n  {r['ticker']} {r['prediction_pair']}")
        print(f"    peer_gap          = {mf.get('peer_gap', 'n/a')}")
        print(f"    op_margin_level   = {mf.get('op_margin_level', 'n/a')}")
        print(f"    op_margin_trend_pp= {mf.get('op_margin_trend_pp', 'n/a')}")
        print(f"    goodwill          = {mf.get('goodwill', 'n/a')}")
        print(f"    cfo_ni            = {mf.get('cfo_ni', 'n/a')}")
        print(f"    top_segment_share = {mf.get('top_segment_share', 'n/a')}")
        print(f"    op_profit_yoy_pred= {mf.get('op_profit_yoy_pred', 'n/a')}")
        print(f"    op_profit_yoy_out = {mf.get('op_profit_yoy_outcome', 'n/a')}")
        print(f"    miss_patterns     = {mf.get('miss_patterns', 'n/a')}")

    # ============================================================
    # Test op_margin_trend rule on ALL GL survivors using misj data
    # ============================================================
    print("\n" + "=" * 130)
    print("OP_MARGIN_TREND_PP TEST on GL survivors (peer_gap > 0 by definition after R5)")
    print("=" * 130)

    gl_survivors = [r for r in rows if r["post_veto_judgment"] == "growth_likely"]
    # We can only test the rule on cases where the misjudgment file
    # has the data — i.e. cases that were misses originally. For hits,
    # we need to compute it ourselves. Let me check how many we have.
    have_trend_data = [r for r in gl_survivors if r.get("misj_features")
                       and r["misj_features"].get("op_margin_trend_pp") is not None]
    print(f"\n  GL survivors with op_margin_trend_pp available: {len(have_trend_data)} / {len(gl_survivors)}")
    print(f"  (only misses are in misj file, so hits show n/a here — we'd need to compute for hits too)")

    # Show distribution
    print(f"\n  Misses with op_margin_trend:")
    for r in have_trend_data:
        if r["post_veto_score"] == "miss":
            mf = r["misj_features"]
            print(f"    {r['ticker']} {r['prediction_pair']:<22} trend={mf['op_margin_trend_pp']:+.2f}pp")


if __name__ == "__main__":
    main()
