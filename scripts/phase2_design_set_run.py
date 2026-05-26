"""Phase 2 step 4: Run Haiku structured scoring on all 50 design-set cases.

Compares Phase 2 verdicts side-by-side with:
  - LLM raw verdict (no vetoes)
  - Phase 1 verdict (LLM + 6 vetoes)
  - Actual outcome (lenient)

Identifies systematic disagreements so we know whether to:
  - Tighten Phase 2 (too lenient — letting misses through)
  - Loosen Phase 2 (too strict — killing hits)
  - Adjust hard floors, thresholds, or weights

Caches per-pair results to outputs/phase2_haiku_design/ so re-runs are free.
"""
from __future__ import annotations
import json
import sys
import io
import glob
import copy
import time
import hashlib
from pathlib import Path

import dotenv
dotenv.load_dotenv()

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import _enrich_pairs_with_confidence
from app.subagents.structured_scoring import score_pair, build_user_message, combine_scores

HAIKU = "claude-haiku-4-5-20251001"
CACHE_DIR = ROOT / "outputs" / "phase2_haiku_design"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_key_for(ticker, pred_pair):
    return f"{ticker}_{pred_pair.replace('->','to')}.json"


def load_pair(ticker, prev_fy):
    files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                 f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not files: return None
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


def score_with_cache(pair, ticker, pred_pair, force=False):
    """Run Haiku scoring; cache by (ticker, pair) so we don't pay twice."""
    cache_file = CACHE_DIR / cache_key_for(ticker, pred_pair)
    if cache_file.exists() and not force:
        with open(cache_file, encoding="utf-8") as f:
            cached = json.load(f)
        # Re-combine to apply current weights/thresholds (so we can tune
        # without re-calling the API)
        return combine_scores(cached["scores"], raw_response=cached.get("raw_response", ""),
                              model=cached.get("model", HAIKU))
    # Fresh call
    result = score_pair(pair, model=HAIKU)
    cache_file.write_text(json.dumps({
        "ticker": ticker,
        "prediction_pair": pred_pair,
        "model": result.model_used,
        "scores": result.scores,
        "weighted_sum": result.weighted_sum,
        "verdict": result.verdict,
        "verdict_reason": result.verdict_reason,
        "raw_response": result.raw_response,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return result


def main():
    # Load locked design split
    with open(ROOT / "outputs" / "phase2_split.json", encoding="utf-8") as f:
        split = json.load(f)
    design = split["design"]
    print(f"Design set: {len(design)} cases")

    # Load Phase 1 reference (lenient outcome + LLM + post-veto judgments)
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes_idx = {(r["ticker"], r["prediction_pair"]): r
                        for r in json.load(f)["rows"]}

    # We also need the post-veto verdicts. Re-run enrichment to get them.
    rows = []
    n_cached = 0
    n_called = 0
    t_start = time.time()
    for i, case in enumerate(design):
        tk = case["ticker"]
        pair_key = case["prediction_pair"]  # e.g. "FY2021->FY2022"
        prev_fy = int(pair_key.replace("FY", "").split("->")[0])

        # Phase 1 reference
        ref = outcomes_idx.get((tk, pair_key))
        if not ref:
            print(f"  ⚠️  no outcome ref for {tk} {pair_key}")
            continue

        pair = load_pair(tk, prev_fy)
        if pair is None:
            print(f"  ⚠️  no cache for {tk} FY{prev_fy}")
            continue

        # Post-veto verdict from the live pipeline
        post_veto_verdict = pair.get("outlook_judgment")

        # Phase 2 call (cached if available)
        cache_file = CACHE_DIR / cache_key_for(tk, pair_key)
        was_cached = cache_file.exists()
        try:
            r = score_with_cache(pair, tk, pair_key)
            if was_cached:
                n_cached += 1
            else:
                n_called += 1
            phase2 = r.verdict
        except Exception as e:
            print(f"  ⚠️  scoring failed for {tk} {pair_key}: {e}")
            continue

        # Score Phase 2 verdict against lenient outcome
        outcome = ref["outcome_lenient"]
        def score(verdict, outcome):
            if verdict == "uncertain": return "abstain"
            if verdict == "growth_likely" and outcome == "positive": return "hit"
            if verdict == "growth_unlikely" and outcome == "negative": return "hit"
            return "miss"

        rows.append({
            "ticker": tk,
            "prediction_pair": pair_key,
            "outcome_lenient": outcome,
            "llm_raw_verdict": ref["llm_verdict"],
            "llm_raw_score": ref["llm_lenient_score"],
            "post_veto_verdict": post_veto_verdict,
            "post_veto_score": score(post_veto_verdict, outcome),
            "phase2_verdict": phase2,
            "phase2_score": score(phase2, outcome),
            "phase2_weighted_sum": r.weighted_sum,
            "phase2_reason": r.verdict_reason,
            "phase2_scores": r.scores,
        })
        # Brief progress
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(design)} ({n_cached} cached, {n_called} fresh)")

    elapsed = time.time() - t_start
    print(f"\nCompleted {len(rows)}/{len(design)} cases in {elapsed:.1f}s")
    print(f"  Cached: {n_cached}    Fresh API calls: {n_called}")
    print(f"  Approx fresh cost: ${n_called * 0.0033:.3f}")

    # ============================================================
    # Headline metrics
    # ============================================================
    print("\n" + "=" * 100)
    print("DESIGN-SET RESULTS")
    print("=" * 100)

    for stage_label, verdict_key, score_key in [
        ("LLM raw",      "llm_raw_verdict",   "llm_raw_score"),
        ("Phase 1 (+vetoes)", "post_veto_verdict", "post_veto_score"),
        ("Phase 2 (scoring)", "phase2_verdict",    "phase2_score"),
    ]:
        print(f"\n  {stage_label}:")
        for cls in ("growth_likely", "growth_unlikely"):
            sub = [r for r in rows if r[verdict_key] == cls]
            h = sum(1 for r in sub if r[score_key] == "hit")
            m = sum(1 for r in sub if r[score_key] == "miss")
            c = h + m
            p = h/c*100 if c else None
            print(f"    {cls:<18} n={len(sub)}  hits={h}  misses={m}  precision={p:.1f}%" if p is not None
                  else f"    {cls:<18} n={len(sub)}  (no confident calls)")
        n_uncertain = sum(1 for r in rows if r[verdict_key] == "uncertain")
        n_confident = sum(1 for r in rows if r[verdict_key] in ("growth_likely", "growth_unlikely"))
        total_h = sum(1 for r in rows if r[verdict_key] in ("growth_likely", "growth_unlikely") and r[score_key] == "hit")
        total_m = sum(1 for r in rows if r[verdict_key] in ("growth_likely", "growth_unlikely") and r[score_key] == "miss")
        total_c = total_h + total_m
        total_p = total_h/total_c*100 if total_c else None
        print(f"    ALL CONFIDENT      n={n_confident}  hits={total_h}  misses={total_m}  precision={total_p:.1f}%" if total_p is not None else "")
        print(f"    uncertain          n={n_uncertain}")

    # ============================================================
    # Where Phase 2 disagrees with Phase 1
    # ============================================================
    print("\n" + "=" * 100)
    print("DISAGREEMENT MATRIX: Phase 1 verdict (rows) vs Phase 2 verdict (cols)")
    print("=" * 100)
    print(f"\n  {'':<22}{'P2:growth_likely':<22}{'P2:uncertain':<18}{'P2:growth_unlikely'}")
    for p1 in ("growth_likely", "uncertain", "growth_unlikely"):
        row = [f"  P1:{p1:<18}"]
        for p2 in ("growth_likely", "uncertain", "growth_unlikely"):
            n = sum(1 for r in rows if r["post_veto_verdict"] == p1 and r["phase2_verdict"] == p2)
            row.append(f"{n:<22}" if p2 != "growth_unlikely" else f"{n}")
        print("".join(row))

    # ============================================================
    # Cases where Phase 2 differs from Phase 1 — show details
    # ============================================================
    print("\n" + "=" * 100)
    print("CASES WHERE PHASE 2 DIFFERS FROM PHASE 1 (post-veto)")
    print("=" * 100)
    disagreed = [r for r in rows if r["post_veto_verdict"] != r["phase2_verdict"]]
    print(f"\n  {len(disagreed)} disagreements out of {len(rows)} cases\n")

    print(f"  {'Ticker':<7}{'Pair':<22}{'P1 verdict':<18}{'P2 verdict':<18}"
          f"{'P1 score':<10}{'P2 score':<10}{'outcome':<10}{'P2 sum'}")
    for r in disagreed:
        print(f"  {r['ticker']:<7}{r['prediction_pair']:<22}{r['post_veto_verdict']:<18}"
              f"{r['phase2_verdict']:<18}{r['post_veto_score']:<10}{r['phase2_score']:<10}"
              f"{r['outcome_lenient']:<10}{r['phase2_weighted_sum']:.1f}")

    # ============================================================
    # Net change: Phase 2 vs Phase 1 for the design set
    # ============================================================
    print("\n" + "=" * 100)
    print("NET COMPARISON: hit/miss/abstain transitions Phase 1 → Phase 2")
    print("=" * 100)
    from collections import Counter
    transitions = Counter()
    for r in rows:
        transitions[(r["post_veto_score"], r["phase2_score"])] += 1
    print(f"\n  {'P1 → P2':<18}{'count':<8}{'meaning'}")
    interp = {
        ("hit", "hit"):       "kept (good)",
        ("hit", "miss"):      "lost a hit (bad)",
        ("hit", "abstain"):   "downgraded a hit (cautious)",
        ("miss", "miss"):     "still wrong (no improvement)",
        ("miss", "hit"):      "flipped to correct (excellent)",
        ("miss", "abstain"):  "downgraded a miss (good)",
        ("abstain", "hit"):   "upgraded abstain to hit (excellent)",
        ("abstain", "miss"):  "upgraded abstain to miss (bad)",
        ("abstain", "abstain"): "stayed uncertain",
    }
    for (a, b), n in sorted(transitions.items()):
        label = f"{a} → {b}"
        print(f"  {label:<18}{n:<8}{interp.get((a, b), '')}")

    out = ROOT / "outputs" / "phase2_design_run.json"
    out.write_text(json.dumps({
        "model": HAIKU,
        "n": len(rows),
        "rows": rows,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()
