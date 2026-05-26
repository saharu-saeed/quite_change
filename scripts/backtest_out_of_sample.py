"""Out-of-sample test on 15 fresh tickers.

Selection rule LOCKED in outputs/out_of_sample_selection.md before any runs.
Same rolling-window methodology as scripts/backtest_rolling_window.py.

Runs LLM (via Bedrock — Anthropic Direct key paused) on all pairs for each
of 15 tickers not in the original 20-ticker test set, then scores each
prediction against the next pair's revenue + 5-day stock outcome (the
original retired methodology, kept here for raw output consistency —
the real scoring under Recipe A v1/v2/C happens in separate scripts).

Cost: ~$2-3 in Bedrock calls. Wall time: ~60-90 min.
"""
from __future__ import annotations
import json
import os
import sys
import io
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()
assert not os.environ.get("ANTHROPIC_API_KEY"), \
    "ANTHROPIC_API_KEY must remain unset — user paused it. Aborting."

from app.subagents.quiet_change import analyze_company_multi_year  # noqa: E402

# LOCKED — see outputs/out_of_sample_selection.md
TICKERS = [
    "2371", "4063", "4502", "4519", "4716", "4751", "4755",
    "6098", "6501", "6701", "6702", "6758", "6857", "6861", "7203",
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


def main() -> int:
    print("Out-of-sample backtest — 15 fresh tickers via Bedrock", flush=True)
    print(f"Bedrock model: {os.environ.get('BEDROCK_MODEL_ID')}", flush=True)
    print(f"Tickers ({len(TICKERS)}): {TICKERS}\n", flush=True)

    print("[step 1] Running agent (LLM on ALL pairs)…", flush=True)
    results = {}
    t0 = time.time()
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
            print(f" ok ({n_real} pair(s), {time.time()-ts:.1f}s)", flush=True)
        except Exception as e:
            print(f" CRASHED: {type(e).__name__}: {e}", flush=True)
            r = {"error": str(e)}
        results[code] = r
    print(f"\n  total wall time: {time.time()-t0:.1f}s\n", flush=True)

    print("=" * 100, flush=True)
    print("ROLLING-WINDOW SCORING ON OUT-OF-SAMPLE SET", flush=True)
    print("=" * 100, flush=True)

    all_scored = []
    for code in TICKERS:
        r = results.get(code, {})
        if "error" in r:
            print(f"  {code}: ERROR -- {r.get('error')}", flush=True)
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
    print(f"\n  total: {len(all_scored)}, hits: {hits}, misses: {misses}, "
          f"abstains: {abstains}, confident: {confident}", flush=True)
    if confident > 0:
        print(f"  HIT RATE (original noisy metric): {hits}/{confident} = {hits/confident*100:.1f}%",
              flush=True)

    out_path = ROOT / "outputs" / "out_of_sample_rolling_window.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "methodology": "rolling-window, original noisy ground truth (rev+5d stock both pos = growth)",
        "selection_rule_locked": "outputs/out_of_sample_selection.md",
        "total_scored": len(all_scored),
        "hits": hits, "misses": misses, "abstains": abstains,
        "scored_predictions": all_scored,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
