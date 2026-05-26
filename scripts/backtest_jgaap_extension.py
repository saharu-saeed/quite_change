"""JGAAP info/comm extension — 30 fresh tickers with per-call token tracking.

Selection LOCKED in outputs/jgaap_extension_selection.md before runs.
Same rolling-window methodology as scripts/backtest_rolling_window.py
and scripts/backtest_out_of_sample.py, with the addition of:

  - Tempest data fetch step (data isn't in local cache yet)
  - Per-ticker token + cost tracking via app/tools/bedrock.py tracker

Run cost (Bedrock Sonnet 4.6): ~$5-8 total. Wall time: 90-120 min.
"""
from __future__ import annotations
import json
import os
import sys
import io
import time
import subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(dotenv_path=ROOT / ".env")
assert not os.environ.get("ANTHROPIC_API_KEY"), \
    "ANTHROPIC_API_KEY must remain unset — user paused it. Aborting."

from app.subagents.quiet_change import analyze_company_multi_year  # noqa: E402
from app.tools.bedrock import get_usage_stats, reset_usage_stats  # noqa: E402

# LOCKED — see outputs/jgaap_extension_selection.md
TICKERS = [
    # TOPIX Mid400 (all 13)
    "3626", "3635", "3697", "3994", "4194", "4676", "4704", "4733",
    "9401", "9404", "9468", "9602", "9759",
    # TOPIX Small 1 (first 17 by ticker)
    "2121", "2317", "2326", "3636", "3660", "3661", "3668", "3765",
    "3778", "3844", "4071", "4384", "4443", "4686", "4722", "4776", "4812",
]


def _score_outcome(rev_d, stock_5d):
    if rev_d is None or stock_5d is None:
        return "n/a"
    return "growth" if (rev_d > 0 and stock_5d > 0) else "no_growth"


def _score_prediction(prediction, actual):
    if actual == "n/a":
        return "n/a"
    if prediction == "uncertain":
        return "abstain"
    if prediction == "growth_likely" and actual == "growth":
        return "hit"
    if prediction == "growth_unlikely" and actual == "no_growth":
        return "hit"
    return "miss"


def fetch_tempest_data(tickers: list[str]) -> None:
    """Invoke fetch_tempest.py for the ticker list. Skips already-cached files."""
    print(f"[step 1] Fetching Tempest data for {len(tickers)} tickers (24h cache freshness)…",
          flush=True)
    cmd = [sys.executable, str(ROOT / "fetch_tempest.py"),
           "--tickers", ",".join(tickers),
           "--max-age-hours", "168"]  # 1 week — be liberal with cache reuse
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    print(result.stdout, flush=True)
    if result.returncode != 0:
        print("STDERR:", result.stderr, flush=True)
        raise RuntimeError(f"fetch_tempest exited with code {result.returncode}")
    print(f"  Tempest fetch wall time: {time.time()-t0:.1f}s\n", flush=True)


def main() -> int:
    print("JGAAP info/comm extension — 30 fresh tickers", flush=True)
    print(f"Bedrock model: {os.environ.get('BEDROCK_MODEL_ID')}", flush=True)
    print(f"Tickers ({len(TICKERS)}): {TICKERS}\n", flush=True)

    # Reset cumulative token tracker
    reset_usage_stats()

    # Step 1: fetch Tempest data
    fetch_tempest_data(TICKERS)

    # Step 2: run agent with per-ticker cost reporting
    print("[step 2] Running agent (LLM on ALL pairs)…", flush=True)
    results: dict[str, dict] = {}
    per_ticker_cost: list[dict] = []
    t0 = time.time()
    prev_cost = 0.0
    prev_calls = 0
    for i, code in enumerate(TICKERS, 1):
        print(f"  [{i}/{len(TICKERS)}] {code}: running…", end="", flush=True)
        ts = time.time()
        try:
            r = analyze_company_multi_year(
                code, min_year=2020, run_tests=False,
                skip_simplify=True,
                decision_cutoff_fy=None,
                use_cache=True,
                use_prompt_caching=False,
            )
            n_real = len([p for p in r.get("pairs", []) if not p.get("history_only")])
            stats = get_usage_stats()
            delta_cost = stats["estimated_cost_usd"] - prev_cost
            delta_calls = stats["call_count"] - prev_calls
            prev_cost = stats["estimated_cost_usd"]
            prev_calls = stats["call_count"]
            print(f" ok ({n_real} pair(s), {time.time()-ts:.1f}s, "
                  f"+{delta_calls} calls, +${delta_cost:.3f}, "
                  f"running total ${stats['estimated_cost_usd']:.3f})", flush=True)
            per_ticker_cost.append({
                "ticker": code, "pairs": n_real, "elapsed_s": round(time.time() - ts, 1),
                "delta_calls": delta_calls, "delta_cost_usd": round(delta_cost, 4),
                "cumulative_cost_usd": stats["estimated_cost_usd"],
            })
        except Exception as e:
            print(f" CRASHED: {type(e).__name__}: {e}", flush=True)
            r = {"error": str(e)}
            per_ticker_cost.append({
                "ticker": code, "error": str(e),
                "cumulative_cost_usd": prev_cost,
            })
        results[code] = r
    print(f"\n  total wall time: {time.time()-t0:.1f}s\n", flush=True)

    # Final usage report
    final_stats = get_usage_stats()
    print("=" * 100, flush=True)
    print("FINAL TOKEN USAGE + COST", flush=True)
    print("=" * 100, flush=True)
    print(f"  Total LLM calls:           {final_stats['call_count']}", flush=True)
    print(f"  Input tokens:              {final_stats['input_tokens']:,}", flush=True)
    print(f"  Output tokens:             {final_stats['output_tokens']:,}", flush=True)
    print(f"  Cache read tokens:         {final_stats['cache_read_input_tokens']:,}", flush=True)
    print(f"  Cache creation tokens:     {final_stats['cache_creation_input_tokens']:,}", flush=True)
    print(f"  ESTIMATED COST:            ${final_stats['estimated_cost_usd']:.3f}", flush=True)

    # Score predictions (rolling-window, original metric — for raw output)
    print("\n[step 3] Rolling-window scoring (original noisy metric)…", flush=True)
    all_scored = []
    for code in TICKERS:
        r = results.get(code, {})
        if "error" in r:
            continue
        pairs = [p for p in r.get("pairs", []) if not p.get("history_only")]
        pairs.sort(key=lambda p: p.get("curr_period_end", ""))
        for i in range(len(pairs) - 1):
            pred_pair = pairs[i]
            next_pair = pairs[i + 1]
            pred_label = f"FY{pred_pair['prev_fiscal_year']}->FY{pred_pair['curr_fiscal_year']}"
            outcome_label = f"FY{next_pair['prev_fiscal_year']}->FY{next_pair['curr_fiscal_year']}"
            judgment = pred_pair.get("outlook_judgment", "uncertain")
            rev_d = next_pair.get("revenue_delta_pct")
            stock = next_pair.get("stock_5d_return_pct")
            actual = _score_outcome(rev_d, stock)
            verdict = _score_prediction(judgment, actual)
            all_scored.append({
                "ticker": code,
                "prediction_pair": pred_label,
                "judgment": judgment,
                "outcome_pair": outcome_label,
                "rev_delta_pct": rev_d,
                "stock_5d_pct": stock,
                "actual_outcome": actual,
                "verdict": verdict,
                "reason_en": (pred_pair.get("outlook_reason_en") or "")[:200],
            })

    hits = sum(1 for s in all_scored if s["verdict"] == "hit")
    misses = sum(1 for s in all_scored if s["verdict"] == "miss")
    abstains = sum(1 for s in all_scored if s["verdict"] == "abstain")
    confident = hits + misses
    print(f"  total predictions: {len(all_scored)}, hits: {hits}, misses: {misses}, abstains: {abstains}",
          flush=True)
    if confident > 0:
        print(f"  HIT RATE (original noisy metric): {hits}/{confident} = {hits/confident*100:.1f}%",
              flush=True)

    out_path = ROOT / "outputs" / "jgaap_extension_rolling_window.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "methodology": "rolling-window on JGAAP info/comm extension cohort",
        "selection_rule_locked": "outputs/jgaap_extension_selection.md",
        "total_scored": len(all_scored),
        "hits": hits, "misses": misses, "abstains": abstains,
        "scored_predictions": all_scored,
        "final_usage_stats": final_stats,
        "per_ticker_cost": per_ticker_cost,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
