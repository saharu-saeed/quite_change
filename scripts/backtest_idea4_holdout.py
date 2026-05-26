"""Idea 4 Phase 4 — paired A/B held-out validation on 15 fresh JGAAP tickers.

Selection LOCKED in outputs/idea4_phase4_holdout_selection.md before runs.
Runs agent with WHATEVER prompt state is in app/subagents/quiet_change_prompt.py
at the time of invocation. Saves to a file tagged by cache version.

To do paired A/B: invoke this script TWICE, once with each prompt state
(NEW with GL rules, OLD without). The prompt file must be edited between
invocations. Cache version must also change between invocations so cache
keys don't collide.
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

from app.subagents.quiet_change import analyze_company_multi_year, _AGENT_CACHE_VERSION  # noqa: E402
from app.tools.bedrock import get_usage_stats, reset_usage_stats  # noqa: E402

TICKERS = ["4825", "5032", "7595", "7860", "9409", "9412", "9413", "9416", "9418",
           "9601", "9605", "9682", "9692", "9746", "9889"]


def fetch_tempest(tickers):
    print(f"[step 1] Fetching Tempest data for {len(tickers)} tickers…", flush=True)
    cmd = [sys.executable, str(ROOT / "fetch_tempest.py"),
           "--tickers", ",".join(tickers), "--max-age-hours", "168"]
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode != 0:
        print("STDERR:", result.stderr, flush=True)
        raise RuntimeError(f"fetch_tempest exit {result.returncode}")
    print(f"  fetch wall time: {time.time()-t0:.1f}s\n", flush=True)


def main():
    print(f"Idea 4 Phase 4 — held-out validation", flush=True)
    print(f"Cache version (prompt state tag): {_AGENT_CACHE_VERSION}\n", flush=True)
    reset_usage_stats()

    # Fetch data (idempotent — 168h freshness)
    fetch_tempest(TICKERS)

    print("[step 2] Running agent…", flush=True)
    results = {}
    t0 = time.time()
    for i, code in enumerate(TICKERS, 1):
        print(f"  [{i}/{len(TICKERS)}] {code}: running…", end="", flush=True)
        ts = time.time()
        try:
            r = analyze_company_multi_year(
                code, min_year=2020, run_tests=False,
                skip_simplify=True, decision_cutoff_fy=None,
                use_cache=True, use_prompt_caching=False,
            )
            n_real = len([p for p in r.get("pairs", []) if not p.get("history_only")])
            stats = get_usage_stats()
            print(f" ok ({n_real} pair(s), {time.time()-ts:.1f}s, "
                  f"running total ${stats['estimated_cost_usd']:.3f})", flush=True)
        except Exception as e:
            print(f" CRASHED: {type(e).__name__}: {e}", flush=True)
            r = {"error": str(e)}
        results[code] = r
    print(f"\n  total wall time: {time.time()-t0:.1f}s", flush=True)

    final = get_usage_stats()
    print(f"  ESTIMATED COST: ${final['estimated_cost_usd']:.3f}\n", flush=True)

    # Save results tagged by cache version
    out_path = ROOT / "outputs" / f"idea4_holdout_{_AGENT_CACHE_VERSION}.json"
    summary = {
        "cache_version_at_run": _AGENT_CACHE_VERSION,
        "tickers": TICKERS,
        "usage_stats": final,
        "per_ticker": {},
    }
    for code in TICKERS:
        r = results[code]
        if "error" in r:
            summary["per_ticker"][code] = {"error": r["error"]}
            continue
        pairs = [p for p in r.get("pairs", []) if not p.get("history_only")]
        pairs.sort(key=lambda p: p.get("curr_period_end", ""))
        summary["per_ticker"][code] = {
            "n_pairs": len(pairs),
            "pairs": [
                {
                    "prev_fy": p["prev_fiscal_year"],
                    "curr_fy": p["curr_fiscal_year"],
                    "judgment": p.get("outlook_judgment"),
                    "op_profit_delta_pct": p.get("op_profit_delta_pct"),
                    "revenue_delta_pct": p.get("revenue_delta_pct"),
                    "stock_5d_return_pct": p.get("stock_5d_return_pct"),
                    "outlook_reason_en": (p.get("outlook_reason_en") or "")[:300],
                } for p in pairs
            ],
        }
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    print(f"[saved] {out_path}", flush=True)


if __name__ == "__main__":
    main()
