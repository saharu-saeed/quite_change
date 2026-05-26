"""Phase 2 Step 5: Run Haiku scoring on the LOCKED 61-case holdout.

This is the once-only run. No prompt/threshold changes allowed after this.

Then scores 4 configurations side-by-side:
  - LLM raw         (no vetoes, no Phase 2)
  - Phase 1 only   (current shipped — LLM + 6 vetoes)
  - Phase 2 only   (replace vetoes with structured scoring)
  - Stacked        (Phase 1 veto first, then Phase 2 must also agree to confirm)

The stacked configuration: confident verdict only if BOTH Phase 1 (post-veto)
and Phase 2 agree on the same confident direction. Otherwise → uncertain.
"""
from __future__ import annotations
import json
import sys
import io
import glob
import copy
import time
import math
from pathlib import Path

import dotenv
dotenv.load_dotenv()

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import _enrich_pairs_with_confidence
from app.subagents.structured_scoring import score_pair, combine_scores

HAIKU = "claude-haiku-4-5-20251001"
CACHE_DIR = ROOT / "outputs" / "phase2_haiku_holdout"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _wilson(hits, n, z=1.96):
    if n == 0: return (None, None)
    p = hits/n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    r = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den
    return (max(0.0,(c-r)*100), min(100.0,(c+r)*100))


def cache_key(tk, pair_key):
    return f"{tk}_{pair_key.replace('->','to')}.json"


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


def score_with_cache(pair, tk, pair_key, force=False):
    cf = CACHE_DIR / cache_key(tk, pair_key)
    if cf.exists() and not force:
        with open(cf, encoding="utf-8") as f:
            cached = json.load(f)
        return combine_scores(cached["scores"], raw_response=cached.get("raw_response", ""),
                              model=cached.get("model", HAIKU))
    result = score_pair(pair, model=HAIKU)
    cf.write_text(json.dumps({
        "ticker": tk, "prediction_pair": pair_key, "model": result.model_used,
        "scores": result.scores, "weighted_sum": result.weighted_sum,
        "verdict": result.verdict, "verdict_reason": result.verdict_reason,
        "raw_response": result.raw_response,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return result


def score_outcome(verdict, outcome):
    if verdict == "uncertain": return "abstain"
    if verdict == "growth_likely" and outcome == "positive": return "hit"
    if verdict == "growth_unlikely" and outcome == "negative": return "hit"
    return "miss"


def stacked_verdict(p1, p2):
    """Both Phase 1 (post-veto) AND Phase 2 must agree to confirm a confident verdict."""
    if p1 == "uncertain" or p2 == "uncertain":
        return "uncertain"
    if p1 == p2:
        return p1
    return "uncertain"  # conflict


def main():
    with open(ROOT / "outputs" / "phase2_split.json", encoding="utf-8") as f:
        split = json.load(f)
    holdout = split["holdout"]
    print(f"Holdout set: {len(holdout)} cases (LOCKED)")
    print(f"Model: {HAIKU}")
    print()

    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes_idx = {(r["ticker"], r["prediction_pair"]): r
                        for r in json.load(f)["rows"]}

    rows = []
    n_called = 0
    t0 = time.time()
    for i, case in enumerate(holdout):
        tk = case["ticker"]
        pair_key = case["prediction_pair"]
        prev_fy = int(pair_key.replace("FY", "").split("->")[0])

        ref = outcomes_idx.get((tk, pair_key))
        if not ref:
            print(f"  ⚠️  no outcome ref for {tk} {pair_key}")
            continue

        pair = load_pair(tk, prev_fy)
        if pair is None:
            print(f"  ⚠️  no cache for {tk} FY{prev_fy}")
            continue

        post_veto = pair.get("outlook_judgment")
        cf = CACHE_DIR / cache_key(tk, pair_key)
        was_cached = cf.exists()
        try:
            r = score_with_cache(pair, tk, pair_key)
            if not was_cached: n_called += 1
        except Exception as e:
            print(f"  ⚠️  scoring failed for {tk} {pair_key}: {e}")
            continue

        outcome = ref["outcome_lenient"]
        stacked = stacked_verdict(post_veto, r.verdict)

        rows.append({
            "ticker": tk, "prediction_pair": pair_key, "outcome_lenient": outcome,
            "llm_raw": ref["llm_verdict"],
            "llm_raw_score": ref["llm_lenient_score"],
            "phase1": post_veto,
            "phase1_score": score_outcome(post_veto, outcome),
            "phase2": r.verdict,
            "phase2_sum": r.weighted_sum,
            "phase2_score": score_outcome(r.verdict, outcome),
            "stacked": stacked,
            "stacked_score": score_outcome(stacked, outcome),
        })
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(holdout)} done ({n_called} fresh)")

    elapsed = time.time() - t0
    print(f"\nCompleted {len(rows)} cases in {elapsed:.0f}s   fresh API calls: {n_called}"
          f"   cost ≈ ${n_called * 0.0033:.3f}")

    # =====================================================================
    # Headline scoreboard
    # =====================================================================
    print("\n" + "=" * 110)
    print(f"HOLDOUT RESULTS  (n={len(rows)}, LOCKED — single run)")
    print("=" * 110)

    print(f"\n  {'Approach':<24}{'GL precision':<28}{'GU precision':<28}{'All conf':<28}{'Volume'}")
    print("  " + "-" * 108)
    configs = [
        ("LLM raw",         "llm_raw",  "llm_raw_score"),
        ("Phase 1 (vetoes)", "phase1",   "phase1_score"),
        ("Phase 2 (scoring)","phase2",   "phase2_score"),
        ("Stacked (P1∩P2)",  "stacked",  "stacked_score"),
    ]
    for name, vk, sk in configs:
        def stats(cls):
            h = sum(1 for r in rows if r[vk] == cls and r[sk] == "hit")
            m = sum(1 for r in rows if r[vk] == cls and r[sk] == "miss")
            c = h + m
            p = h/c*100 if c else None
            ci = _wilson(h, c)
            return h, m, c, p, ci
        gl_h, gl_m, gl_c, gl_p, gl_ci = stats("growth_likely")
        gu_h, gu_m, gu_c, gu_p, gu_ci = stats("growth_unlikely")
        all_h = gl_h + gu_h; all_m = gl_m + gu_m; all_c = all_h + all_m
        all_p = all_h/all_c*100 if all_c else None
        all_ci = _wilson(all_h, all_c)
        def fmt(p, ci, h, c):
            if p is None: return "n/a"
            return f"{p:5.1f}% ({h}/{c}) CI[{ci[0]:.0f}-{ci[1]:.0f}]"
        print(f"  {name:<24}{fmt(gl_p,gl_ci,gl_h,gl_c):<28}{fmt(gu_p,gu_ci,gu_h,gu_c):<28}"
              f"{fmt(all_p,all_ci,all_h,all_c):<28}{all_c}/{len(rows)}")

    # =====================================================================
    # Side-by-side disagreement matrix
    # =====================================================================
    print("\n" + "=" * 110)
    print("PHASE 1 vs PHASE 2 verdict matrix (holdout)")
    print("=" * 110)
    print(f"\n  {'':<22}{'P2:growth_likely':<22}{'P2:uncertain':<18}{'P2:growth_unlikely'}")
    for p1 in ("growth_likely", "uncertain", "growth_unlikely"):
        line = [f"  P1:{p1:<18}"]
        for p2 in ("growth_likely", "uncertain", "growth_unlikely"):
            n = sum(1 for r in rows if r["phase1"] == p1 and r["phase2"] == p2)
            line.append(f"{n:<22}" if p2 != "growth_unlikely" else f"{n}")
        print("".join(line))

    # =====================================================================
    # Transition analysis (Phase 1 → Phase 2)
    # =====================================================================
    from collections import Counter
    print("\n" + "=" * 110)
    print("Transition: Phase 1 score → Phase 2 score")
    print("=" * 110)
    tr = Counter()
    for r in rows:
        tr[(r["phase1_score"], r["phase2_score"])] += 1
    interp = {
        ("hit", "hit"): "kept (good)",
        ("hit", "miss"): "LOST a hit (bad)",
        ("hit", "abstain"): "downgraded a hit (cautious)",
        ("miss", "miss"): "still wrong",
        ("miss", "hit"): "FLIPPED to correct (excellent)",
        ("miss", "abstain"): "caught a miss (good)",
        ("abstain", "hit"): "upgraded to hit (excellent)",
        ("abstain", "miss"): "upgraded to miss (bad)",
        ("abstain", "abstain"): "stayed uncertain",
    }
    print(f"\n  {'P1 → P2':<18}{'count':<8}{'meaning'}")
    for (a, b), n in sorted(tr.items()):
        print(f"  {a:<8} → {b:<8} {n:<8}{interp.get((a, b), '')}")

    out = ROOT / "outputs" / "phase2_holdout_run.json"
    out.write_text(json.dumps({
        "model": HAIKU, "n": len(rows), "rows": rows,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()
