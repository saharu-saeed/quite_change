"""Smoke-test: build the Phase 2 structured-scoring prompt for a few
real cached pairs. Verifies the input formatting works AND estimates
actual token counts so we can refine the cost estimate.

NO API CALLS — purely local.
"""
from __future__ import annotations
import sys
import io
import json
import glob
import copy
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import _enrich_pairs_with_confidence
from app.subagents.structured_scoring import (
    SCORING_SYSTEM_PROMPT, build_user_message, combine_scores,
)


def main():
    # Pick 3 representative cases from the design set
    test_cases = [
        ("3760", 2022),  # Mercari-style surge miss (caught by R6)
        ("9684", 2021),  # Stubborn ADVERSE_EVENT_AFTER miss
        ("4684", 2022),  # Strong hit (Marvelous, peer_gap +49)
    ]

    print("=" * 90)
    print("PHASE 2 PROMPT SMOKE TEST")
    print("=" * 90)
    print(f"\nSystem prompt: {len(SCORING_SYSTEM_PROMPT)} chars  "
          f"≈ {len(SCORING_SYSTEM_PROMPT)//4} tokens (rough)")
    print()

    user_msg_lengths = []
    for tk, prev_fy in test_cases:
        files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                     f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if not files:
            print(f"⚠️  No cache for {tk}")
            continue
        with open(files[-1], encoding="utf-8") as f:
            data = json.load(f)
        # Enrich (so op_margin_trend_pp is populated)
        result = copy.deepcopy(data)
        for pair in result.get("pairs", []):
            for k in ("confidence_label", "confidence_factors",
                      "veto_triggered", "veto_rule", "veto_reason", "original_judgment"):
                pair.pop(k, None)
        _enrich_pairs_with_confidence(result)

        target = None
        for p in result["pairs"]:
            if p.get("history_only"): continue
            if p.get("prev_fiscal_year") == prev_fy:
                target = p
                break
        if target is None:
            print(f"⚠️  No pair for {tk} FY{prev_fy}")
            continue

        target.setdefault("ticker", tk)
        msg = build_user_message(target)
        user_msg_lengths.append(len(msg))
        print(f"\n--- {tk} FY{prev_fy}->FY{prev_fy+1} ---")
        print(f"User message: {len(msg)} chars ≈ {len(msg)//4} tokens (rough)")
        print(msg)
        print()

    avg_user = sum(user_msg_lengths) / len(user_msg_lengths) if user_msg_lengths else 0
    sys_toks = len(SCORING_SYSTEM_PROMPT) // 4
    usr_toks = int(avg_user) // 4
    print("=" * 90)
    print("TOKEN ESTIMATES (rough — 4 chars/token)")
    print("=" * 90)
    print(f"  System prompt:        ~{sys_toks} tokens  (cached across calls)")
    print(f"  User message avg:     ~{usr_toks} tokens  (fresh per call)")
    print(f"  Total input per call: ~{sys_toks + usr_toks} tokens")
    print(f"  Expected output:      ~500-700 tokens (5 scores × short reasoning)")

    # Cost projection
    print("\n  PER-CALL COST (with prompt caching active):")
    sys_cached_haiku = sys_toks * 0.10 / 1_000_000   # cache reads are ~10x cheaper
    sys_cached_sonnet = sys_toks * 0.30 / 1_000_000
    haiku_in = usr_toks * 1.0 / 1_000_000
    haiku_out = 600 * 5.0 / 1_000_000
    sonnet_in = usr_toks * 3.0 / 1_000_000
    sonnet_out = 600 * 15.0 / 1_000_000
    print(f"    Haiku 4.5:  ${sys_cached_haiku + haiku_in + haiku_out:.5f}")
    print(f"    Sonnet 4.6: ${sys_cached_sonnet + sonnet_in + sonnet_out:.5f}")

    # Project totals for full Phase 2
    n_design_iter = 50 * 4   # 50 design × 4 iterations
    n_holdout = 61           # one run
    n_ab_test = 10           # 5 cases × 2 models in step 3
    total_calls = n_design_iter + n_holdout + n_ab_test
    haiku_per = sys_cached_haiku + haiku_in + haiku_out
    sonnet_per = sys_cached_sonnet + sonnet_in + sonnet_out
    print(f"\n  TOTAL PHASE 2 COST ({total_calls} calls = {n_ab_test} A/B + {n_design_iter} iter + {n_holdout} holdout):")
    print(f"    Haiku-only:   ${haiku_per * total_calls:.2f}")
    print(f"    Sonnet-only:  ${sonnet_per * total_calls:.2f}")
    print(f"    Hybrid (Haiku iter + Sonnet holdout): "
          f"${haiku_per * (n_design_iter + n_ab_test) + sonnet_per * n_holdout:.2f}")

    # Demo: code combiner with synthetic scores
    print("\n" + "=" * 90)
    print("CODE COMBINER SMOKE TEST (synthetic scores, no API call)")
    print("=" * 90)
    print("\nCase A: strong hit candidate (all 4s and 5s)")
    demo_scores = {
        "peer_dominance":     {"score": 5, "reasoning": "+25pp above sector"},
        "margin_quality":     {"score": 5, "reasoning": "margin 45% +2pp YoY"},
        "cash_conversion":    {"score": 4, "reasoning": "CFO/NI 1.25"},
        "growth_durability":  {"score": 4, "reasoning": "+15% steady growth"},
        "concentration_risk": {"score": 3, "reasoning": "top seg 75%"},
    }
    result = combine_scores(demo_scores)
    print(f"  weighted_sum = {result.weighted_sum:.1f}")
    print(f"  verdict      = {result.verdict}")
    print(f"  reason       = {result.verdict_reason}")

    print("\nCase B: Mercari-pattern miss (low cash conversion)")
    demo_scores = {
        "peer_dominance":     {"score": 2, "reasoning": "below sector median"},
        "margin_quality":     {"score": 3, "reasoning": "margin recovery from loss"},
        "cash_conversion":    {"score": 1, "reasoning": "CFO/NI = -2.8x"},
        "growth_durability":  {"score": 3, "reasoning": "+550% op-profit from low base"},
        "concentration_risk": {"score": 3, "reasoning": "two segments"},
    }
    result = combine_scores(demo_scores)
    print(f"  weighted_sum = {result.weighted_sum:.1f}")
    print(f"  verdict      = {result.verdict}")
    print(f"  reason       = {result.verdict_reason}")

    print("\nCase C: ambiguous mid-range")
    demo_scores = {
        "peer_dominance":     {"score": 3, "reasoning": "near parity"},
        "margin_quality":     {"score": 3, "reasoning": "stable margin"},
        "cash_conversion":    {"score": 3, "reasoning": "CFO/NI ~0.9"},
        "growth_durability":  {"score": 3, "reasoning": "mixed signals"},
        "concentration_risk": {"score": 3, "reasoning": "moderate concentration"},
    }
    result = combine_scores(demo_scores)
    print(f"  weighted_sum = {result.weighted_sum:.1f}")
    print(f"  verdict      = {result.verdict}")
    print(f"  reason       = {result.verdict_reason}")


if __name__ == "__main__":
    main()
