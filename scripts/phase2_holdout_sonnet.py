"""Phase 2 Step 5b: Re-run the locked 61-case holdout on Sonnet 4.6.

Same prompt, same combiner, same locked split as the Haiku holdout.
Only the LLM model changes. Lets us see if Sonnet's lower variance and
better instruction-following beats Haiku's 63% all-confident precision.

Cost: ~$0.92 (61 calls × $0.015/call with caching).
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

SONNET = "claude-sonnet-4-6"
CACHE_DIR = ROOT / "outputs" / "phase2_sonnet_holdout"
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
                              model=cached.get("model", SONNET))
    result = score_pair(pair, model=SONNET)
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
    if p1 == "uncertain" or p2 == "uncertain":
        return "uncertain"
    if p1 == p2:
        return p1
    return "uncertain"


def main():
    with open(ROOT / "outputs" / "phase2_split.json", encoding="utf-8") as f:
        split = json.load(f)
    holdout = split["holdout"]
    print(f"Holdout set: {len(holdout)} cases (LOCKED)")
    print(f"Model: {SONNET}")

    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes_idx = {(r["ticker"], r["prediction_pair"]): r
                        for r in json.load(f)["rows"]}

    # Also load Haiku results so we can compare
    haiku_idx = {}
    haiku_run = ROOT / "outputs" / "phase2_holdout_run.json"
    if haiku_run.exists():
        with open(haiku_run, encoding="utf-8") as f:
            for r in json.load(f)["rows"]:
                haiku_idx[(r["ticker"], r["prediction_pair"])] = r

    rows = []
    n_called = 0
    t0 = time.time()
    for i, case in enumerate(holdout):
        tk = case["ticker"]
        pair_key = case["prediction_pair"]
        prev_fy = int(pair_key.replace("FY", "").split("->")[0])
        ref = outcomes_idx.get((tk, pair_key))
        if not ref: continue
        pair = load_pair(tk, prev_fy)
        if pair is None: continue
        post_veto = pair.get("outlook_judgment")
        cf = CACHE_DIR / cache_key(tk, pair_key)
        was_cached = cf.exists()
        try:
            r = score_with_cache(pair, tk, pair_key)
            if not was_cached: n_called += 1
        except Exception as e:
            print(f"  ⚠️  {tk} {pair_key}: {e}")
            continue
        outcome = ref["outcome_lenient"]
        stacked = stacked_verdict(post_veto, r.verdict)
        haiku_ref = haiku_idx.get((tk, pair_key), {})
        rows.append({
            "ticker": tk, "prediction_pair": pair_key, "outcome_lenient": outcome,
            "phase1": post_veto,
            "phase1_score": score_outcome(post_veto, outcome),
            "haiku_verdict": haiku_ref.get("phase2"),
            "haiku_score": haiku_ref.get("phase2_score"),
            "sonnet_verdict": r.verdict,
            "sonnet_sum": r.weighted_sum,
            "sonnet_score": score_outcome(r.verdict, outcome),
            "sonnet_stacked": stacked,
            "sonnet_stacked_score": score_outcome(stacked, outcome),
        })
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(holdout)} done ({n_called} fresh)")

    elapsed = time.time() - t0
    cost = n_called * 0.015
    print(f"\nCompleted {len(rows)} cases in {elapsed:.0f}s   fresh API calls: {n_called}"
          f"   approx cost: ${cost:.2f}")

    # ==================================================================
    # Scoreboard
    # ==================================================================
    print("\n" + "=" * 110)
    print(f"HOLDOUT — Sonnet vs Haiku vs Phase 1  (n={len(rows)}, LOCKED)")
    print("=" * 110)
    print(f"\n  {'Approach':<28}{'GL':<26}{'GU':<26}{'All conf':<28}{'Volume'}")
    print("  " + "-" * 108)

    configs = [
        ("Phase 1 (vetoes)",     "phase1",          "phase1_score"),
        ("Phase 2 (Haiku)",      "haiku_verdict",   "haiku_score"),
        ("Phase 2 (Sonnet)",     "sonnet_verdict",  "sonnet_score"),
        ("Stacked P1∩Sonnet",    "sonnet_stacked",  "sonnet_stacked_score"),
    ]
    for name, vk, sk in configs:
        def stats(cls):
            h = sum(1 for r in rows if r.get(vk) == cls and r.get(sk) == "hit")
            m = sum(1 for r in rows if r.get(vk) == cls and r.get(sk) == "miss")
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
        print(f"  {name:<28}{fmt(gl_p,gl_ci,gl_h,gl_c):<26}{fmt(gu_p,gu_ci,gu_h,gu_c):<26}"
              f"{fmt(all_p,all_ci,all_h,all_c):<28}{all_c}/{len(rows)}")

    # ==================================================================
    # Haiku vs Sonnet agreement
    # ==================================================================
    print("\n" + "=" * 110)
    print("HAIKU vs SONNET verdict matrix (holdout)")
    print("=" * 110)
    print(f"\n  {'':<22}{'Sonnet:GL':<14}{'Sonnet:uncertain':<22}{'Sonnet:GU'}")
    for h in ("growth_likely", "uncertain", "growth_unlikely"):
        line = [f"  Haiku:{h:<14}"]
        for s in ("growth_likely", "uncertain", "growth_unlikely"):
            n = sum(1 for r in rows if r.get("haiku_verdict") == h and r["sonnet_verdict"] == s)
            line.append(f"{n:<14}" if s == "growth_likely" else (f"{n:<22}" if s == "uncertain" else f"{n}"))
        print("".join(line))

    n_agree = sum(1 for r in rows if r.get("haiku_verdict") == r["sonnet_verdict"])
    print(f"\n  Total agreement: {n_agree}/{len(rows)} = {n_agree/len(rows)*100:.1f}%")

    # ==================================================================
    # Cases where Sonnet differs from Haiku
    # ==================================================================
    print("\n" + "=" * 110)
    print("CASES where Sonnet differs from Haiku")
    print("=" * 110)
    diffs = [r for r in rows if r.get("haiku_verdict") and r.get("haiku_verdict") != r["sonnet_verdict"]]
    print(f"\n  {len(diffs)} disagreements out of {len(rows)}\n")
    print(f"  {'Ticker':<7}{'Pair':<20}{'P1':<16}{'Haiku':<16}{'Sonnet':<16}{'outcome':<10}{'Sonnet':<10}{'Haiku'}")
    print(f"  {'':<59}{'':<32}{'':<10}{'score':<10}{'score'}")
    for r in diffs:
        print(f"  {r['ticker']:<7}{r['prediction_pair']:<20}{r['phase1']:<16}"
              f"{r['haiku_verdict']:<16}{r['sonnet_verdict']:<16}{r['outcome_lenient']:<10}"
              f"{r['sonnet_score']:<10}{r['haiku_score']}")

    out = ROOT / "outputs" / "phase2_holdout_sonnet.json"
    out.write_text(json.dumps({
        "model": SONNET, "n": len(rows), "rows": rows,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()
