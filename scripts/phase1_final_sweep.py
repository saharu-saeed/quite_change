"""Phase 1 final sweep — check angles we haven't fully tested:
  - op_margin_trend_pp (margin direction)
  - goodwill_to_equity_pct as veto (not just confidence factor)
  - top_segment_share thresholds
  - Strict outcome scoring (vs lenient) — does the veto stack still help?

If any new rule beats the bar (catches >0 misses with 0 hits killed,
generalizes to TEST), it's worth shipping.
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


def extract_features(pair):
    pc = pair.get("peer_comparison") or {}
    my = pc.get("my") or {}
    med = pc.get("sector_median") or {}
    peer_gap = (my.get("op_margin_pct") - med.get("op_margin_pct")) \
        if my.get("op_margin_pct") is not None and med.get("op_margin_pct") is not None else None

    # Fix: pull margin trend from margin_trajectory_block correctly
    mt = pair.get("margin_trajectory") or []
    op_margin_trend_pp = None
    if len(mt) >= 2:
        latest = mt[-1].get("op_margin_pct") if isinstance(mt[-1], dict) else None
        prev = mt[-2].get("op_margin_pct") if isinstance(mt[-2], dict) else None
        if latest is not None and prev is not None:
            op_margin_trend_pp = latest - prev

    bs_hist = pair.get("bs_quality_history") or []
    gw = bs_hist[-1].get("goodwill_to_equity_pct") if bs_hist else None

    # Segment concentration — sum & top-share
    segs = pair.get("segments") or []
    top_seg = None
    if segs:
        total = sum((s.get("curr") or 0) for s in segs)
        if total > 0:
            top_seg = max((s.get("curr") or 0) for s in segs) / total * 100

    return {
        "peer_gap_pp": peer_gap,
        "op_margin_trend_pp": op_margin_trend_pp,
        "goodwill_to_equity_pct": gw,
        "top_segment_share": top_seg,
        "op_profit_delta_pct": pair.get("op_profit_delta_pct"),
    }


def load_all():
    out = {}
    for tk in ALL_JGAAP:
        files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                     f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if not files:
            continue
        with open(files[-1], encoding="utf-8") as f:
            data = json.load(f)
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
            feats = extract_features(pair)
            feats["post_veto_judgment"] = pair.get("outlook_judgment")
            feats["pre_veto_judgment"] = pair.get("original_judgment")
            out[key] = feats
    return out


def main():
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes = json.load(f)["rows"]
    feats = load_all()
    rows = []
    for r in outcomes:
        key = (r["ticker"], r["prediction_pair"])
        e = feats.get(key)
        if not e:
            continue
        # Re-derive scores after R5/R6/GU-2 vetoes
        outcome_l = r["outcome_lenient"]
        outcome_s = r["outcome_strict"]
        post = e["post_veto_judgment"]

        def score(verdict, outcome):
            if verdict == "uncertain": return "abstain"
            if verdict == "growth_likely" and outcome == "positive": return "hit"
            if verdict == "growth_unlikely" and outcome == "negative": return "hit"
            return "miss"

        rows.append({**r, **e,
                     "post_veto_lenient_score": score(post, outcome_l),
                     "post_veto_strict_score": score(post, outcome_s)})

    # ========================================================================
    # 1. Verify R5+R6+GU-2 still help under STRICT scoring
    # ========================================================================
    print("=" * 100)
    print("1. STRICT OUTCOME SCORING — does the veto stack still help?")
    print("=" * 100)
    for cohort_name, cohort_set in [("FULL", ALL_JGAAP), ("TRAIN", TRAIN_TICKERS), ("TEST", TEST_TICKERS)]:
        sub = [r for r in rows if r["ticker"] in cohort_set]
        for cls in ("growth_likely", "growth_unlikely"):
            pre_h = sum(1 for r in sub if r["llm_verdict"] == cls and r["llm_strict_score"] == "hit")
            pre_m = sum(1 for r in sub if r["llm_verdict"] == cls and r["llm_strict_score"] == "miss")
            post_h = sum(1 for r in sub if r["post_veto_judgment"] == cls and r["post_veto_strict_score"] == "hit")
            post_m = sum(1 for r in sub if r["post_veto_judgment"] == cls and r["post_veto_strict_score"] == "miss")
            pre_c = pre_h + pre_m
            post_c = post_h + post_m
            pre_p = pre_h/pre_c*100 if pre_c else None
            post_p = post_h/post_c*100 if post_c else None
            d = f"{(post_p-pre_p):+.1f}pp" if pre_p is not None and post_p is not None else "n/a"
            pre_s = f"{pre_p:.1f}% ({pre_h}/{pre_c})" if pre_p is not None else "n/a"
            post_s = f"{post_p:.1f}% ({post_h}/{post_c})" if post_p is not None else "n/a"
            print(f"  {cohort_name:<6} {cls:<17} STRICT: pre={pre_s:<18} post={post_s:<18} Δ={d}")
        print()

    # ========================================================================
    # 2. Candidate Rule 7 thresholds — applied AFTER R5+R6+GU-2 vetoes
    # ========================================================================
    print("=" * 100)
    print("2. EXPLORING ADDITIONAL VETO RULES on GL survivors")
    print("=" * 100)

    gl_survivors = [r for r in rows if r["post_veto_judgment"] == "growth_likely"]
    print(f"\nGL survivors after R5+R6: {len(gl_survivors)}")
    print(f"  Hits: {sum(1 for r in gl_survivors if r['post_veto_lenient_score']=='hit')}")
    print(f"  Misses: {sum(1 for r in gl_survivors if r['post_veto_lenient_score']=='miss')}\n")

    # Dump indicator coverage for survivors
    survivor_misses = [r for r in gl_survivors if r["post_veto_lenient_score"] == "miss"]
    survivor_hits = [r for r in gl_survivors if r["post_veto_lenient_score"] == "hit"]
    print(f"  Remaining MISSES (n={len(survivor_misses)}):")
    print(f"    {'Ticker':<7}{'Pair':<20}{'peer_gap':<10}{'gw_eq':<10}{'op_trend':<11}{'top_seg':<10}{'op_yoy':<10}")
    for r in sorted(survivor_misses, key=lambda x: x["ticker"]):
        print(f"    {r['ticker']:<7}{r['prediction_pair']:<20}"
              f"{_fmt(r['peer_gap_pp']):<10}{_fmt(r['goodwill_to_equity_pct']):<10}"
              f"{_fmt(r['op_margin_trend_pp']):<11}{_fmt(r['top_segment_share']):<10}"
              f"{_fmt(r['op_profit_delta_pct']):<10}")

    print(f"\n  Remaining HITS (n={len(survivor_hits)}):")
    print(f"    {'Ticker':<7}{'Pair':<20}{'peer_gap':<10}{'gw_eq':<10}{'op_trend':<11}{'top_seg':<10}{'op_yoy':<10}")
    for r in sorted(survivor_hits, key=lambda x: x["ticker"]):
        print(f"    {r['ticker']:<7}{r['prediction_pair']:<20}"
              f"{_fmt(r['peer_gap_pp']):<10}{_fmt(r['goodwill_to_equity_pct']):<10}"
              f"{_fmt(r['op_margin_trend_pp']):<11}{_fmt(r['top_segment_share']):<10}"
              f"{_fmt(r['op_profit_delta_pct']):<10}")

    # ========================================================================
    # 3. Candidate rule sweeps
    # ========================================================================
    print("\n" + "=" * 100)
    print("3. CANDIDATE RULE 7+ — sweep each axis on GL survivors")
    print("=" * 100)

    def test_rule(name, predicate):
        killed = [r for r in gl_survivors if predicate(r)]
        h = sum(1 for r in killed if r["post_veto_lenient_score"] == "hit")
        m = sum(1 for r in killed if r["post_veto_lenient_score"] == "miss")
        if h + m == 0:
            return
        verdict = "PERFECT" if h == 0 and m > 0 else "GOOD" if m > h else "wash" if m == h else "BAD"
        print(f"  {name:<48} killed={len(killed):<3} caught_miss={m:<3} killed_hit={h:<3} → {verdict}")

    # Top segment share thresholds
    print("\n  Top segment share thresholds:")
    for thresh in [60, 70, 75, 80, 85, 90]:
        test_rule(f"top_segment_share > {thresh}%",
                  lambda r, t=thresh: r["top_segment_share"] is not None and r["top_segment_share"] > t)

    # Op margin trend (declining is bad)
    print("\n  Op margin trend (margin direction):")
    for thresh in [0, -0.5, -1.0, -2.0]:
        test_rule(f"op_margin_trend_pp < {thresh}",
                  lambda r, t=thresh: r["op_margin_trend_pp"] is not None and r["op_margin_trend_pp"] < t)

    # Goodwill thresholds
    print("\n  Goodwill / equity thresholds:")
    for thresh in [10, 15, 20, 30]:
        test_rule(f"goodwill_to_equity > {thresh}%",
                  lambda r, t=thresh: r["goodwill_to_equity_pct"] is not None and r["goodwill_to_equity_pct"] > t)

    # Combined rules
    print("\n  Combined rules:")
    test_rule("top_seg>80 AND op_yoy<30",
              lambda r: (r["top_segment_share"] is not None and r["top_segment_share"] > 80
                        and r["op_profit_delta_pct"] is not None and r["op_profit_delta_pct"] < 30))
    test_rule("op_margin_trend < -1 (declining margin)",
              lambda r: r["op_margin_trend_pp"] is not None and r["op_margin_trend_pp"] < -1.0)
    test_rule("op_margin_trend < 0 AND peer_gap < 10",
              lambda r: (r["op_margin_trend_pp"] is not None and r["op_margin_trend_pp"] < 0
                        and r["peer_gap_pp"] is not None and r["peer_gap_pp"] < 10))

    out = ROOT / "outputs" / "phase1_final_sweep.json"
    out.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


def _fmt(v):
    return f"{v:+.2f}" if isinstance(v, (int, float)) else "n/a"


if __name__ == "__main__":
    main()
