"""Phase 2 step 3: A/B test Haiku 4.5 vs Sonnet 4.6 on 5 pinned cases.

For each case, calls both models and compares:
  - Per-axis score agreement (within ±1 = "match")
  - Final verdict agreement (after code combiner)
  - Reasoning quality

Loads ANTHROPIC_API_KEY from .env via python-dotenv.
Cost: ~10 API calls, expected ~$0.05-0.10.
"""
from __future__ import annotations
import json
import sys
import io
import glob
import copy
import time
from pathlib import Path

import dotenv
dotenv.load_dotenv()  # load .env into os.environ

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import _enrich_pairs_with_confidence
from app.subagents.structured_scoring import score_pair


HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"  # latest Sonnet (Anthropic API)

# Cases for A/B comparison — diversified across hit/miss/stubborn-miss
TEST_CASES = [
    ("4684", 2022, "Strong HIT — peer_gap +49, op_margin 62%"),
    ("4385", 2021, "Mercari MISS — low cash conversion (cfo_ni -2.82)"),
    ("3760", 2022, "Surge MISS — op_yoy +667% from low base"),
    ("9684", 2021, "STUBBORN UNCAUGHT MISS — Phase 2's bar"),
    ("2326", 2023, "Margin-declining MISS — op_margin trend -3.83pp"),
]


def load_pair(ticker, prev_fy):
    files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                 f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    with open(files[-1], encoding="utf-8") as f:
        data = json.load(f)
    result = copy.deepcopy(data)
    for pair in result.get("pairs", []):
        for k in ("confidence_label", "confidence_factors",
                  "veto_triggered", "veto_rule", "veto_reason", "original_judgment"):
            pair.pop(k, None)
    _enrich_pairs_with_confidence(result)
    for pair in result["pairs"]:
        if pair.get("history_only"): continue
        if pair.get("prev_fiscal_year") == prev_fy:
            pair["ticker"] = ticker
            return pair
    return None


def main():
    print("=" * 100)
    print(f"PHASE 2 STEP 3 — A/B test Haiku vs Sonnet on 5 cases")
    print(f"  Haiku model:  {HAIKU}")
    print(f"  Sonnet model: {SONNET}")
    print("=" * 100)

    all_results = []
    for tk, prev_fy, label in TEST_CASES:
        pair = load_pair(tk, prev_fy)
        if pair is None:
            print(f"\n⚠️  No pair for {tk} FY{prev_fy}")
            continue

        print(f"\n\n{'='*100}")
        print(f"{tk} FY{prev_fy}->FY{prev_fy+1}  ({label})")
        print(f"{'='*100}")

        results = {}
        for model_name, model in [("Haiku", HAIKU), ("Sonnet", SONNET)]:
            try:
                t0 = time.time()
                r = score_pair(pair, model=model)
                elapsed = time.time() - t0
                results[model_name] = r
                print(f"\n  {model_name}  (took {elapsed:.1f}s)")
                print(f"    verdict      = {r.verdict}")
                print(f"    weighted_sum = {r.weighted_sum:.1f}")
                print(f"    reason       = {r.verdict_reason}")
                print(f"    scores:")
                for axis, v in r.scores.items():
                    if isinstance(v, dict):
                        s = v.get("score")
                        reason = (v.get("reasoning") or "")[:90]
                        print(f"      {axis:<20} = {s}  ({reason})")
            except Exception as e:
                print(f"\n  {model_name} FAILED: {type(e).__name__}: {e}")
                results[model_name] = None

        # Compare
        if results.get("Haiku") and results.get("Sonnet"):
            h, s = results["Haiku"], results["Sonnet"]
            verdict_match = h.verdict == s.verdict
            print(f"\n  AGREEMENT:")
            print(f"    Verdict: {'✓ MATCH' if verdict_match else '✗ DIVERGE'} "
                  f"({h.verdict} vs {s.verdict})")
            # Per-axis comparison
            for axis in h.scores:
                h_s = h.scores[axis].get("score") if isinstance(h.scores[axis], dict) else None
                s_s = s.scores.get(axis, {}).get("score") if isinstance(s.scores.get(axis), dict) else None
                if h_s is not None and s_s is not None:
                    diff = abs(h_s - s_s)
                    flag = "✓" if diff <= 1 else "✗"
                    print(f"    {axis:<20}: Haiku={h_s}  Sonnet={s_s}  diff={diff}  {flag}")

        all_results.append({
            "ticker": tk,
            "prediction_pair": f"FY{prev_fy}->FY{prev_fy+1}",
            "label": label,
            "haiku": _serialize(results.get("Haiku")),
            "sonnet": _serialize(results.get("Sonnet")),
        })

    # ============================================================
    # Summary
    # ============================================================
    print("\n\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"\n{'Case':<30}{'Haiku verdict':<20}{'Sonnet verdict':<20}{'Match?':<10}{'Axis dev'}")
    print("-" * 100)
    verdict_matches = 0
    total_cases = 0
    for r in all_results:
        h, s = r["haiku"], r["sonnet"]
        if not h or not s: continue
        total_cases += 1
        match = h["verdict"] == s["verdict"]
        if match: verdict_matches += 1
        # Sum of absolute differences across axes
        axis_dev = 0
        for axis in h["scores"]:
            h_s = h["scores"][axis].get("score") if isinstance(h["scores"][axis], dict) else None
            s_s = s["scores"].get(axis, {}).get("score") if isinstance(s["scores"].get(axis), dict) else None
            if h_s is not None and s_s is not None:
                axis_dev += abs(h_s - s_s)
        case_label = f"{r['ticker']} {r['prediction_pair']}"
        match_str = "✓" if match else "✗"
        print(f"{case_label:<30}{h['verdict']:<20}{s['verdict']:<20}{match_str:<10}{axis_dev}")

    print(f"\nVerdict agreement: {verdict_matches}/{total_cases} = {verdict_matches/total_cases*100:.0f}%")

    out = ROOT / "outputs" / "phase2_ab_haiku_vs_sonnet.json"
    out.write_text(json.dumps({
        "haiku_model": HAIKU,
        "sonnet_model": SONNET,
        "results": all_results,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


def _serialize(r):
    if r is None: return None
    return {
        "verdict": r.verdict,
        "weighted_sum": r.weighted_sum,
        "verdict_reason": r.verdict_reason,
        "scores": r.scores,
    }


if __name__ == "__main__":
    main()
