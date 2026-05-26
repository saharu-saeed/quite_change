"""Rolling-window backtest — methodologically correct version.

Each pair's judgment is scored as a 1-year-out prediction against the
NEXT pair's revenue + stock outcome. Compare to the old "bundled"
methodology that scored ONE aggregated verdict per company against the
majority of all subsequent outcome years.

Why this is the right way:
  - The agent in real life would re-read each new annual report and
    update its view. The bundled methodology held it frozen.
  - Each prediction tested against ONE specific future year, not an
    aggregate. Cleaner signal.
  - Many more samples (~60 individual predictions instead of 20 bundled
    verdicts).

Cost: ~$3.60 — calls LLM on ALL pairs (not just decision pairs) for
each of the 20 tickers, because the existing v5 cache only has the
decision pairs LLM'd (outcome pairs were skipped to save cost). To do
rolling-window properly every pair needs a real judgment.

Wall time: ~90 min.
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

TICKERS = [
    "4307", "4689", "9432", "9433", "9434", "9984", "9684", "9697",
    "4385", "3659", "9719", "4684", "4768", "3923", "3656", "4477",
    "4480", "4475", "3760", "4483",
]


def _score_outcome(rev_d: float | None, stock_5d: float | None) -> str:
    """Strict rule (same as current backtest): rev>0 AND stock>0 = growth."""
    if rev_d is None or stock_5d is None:
        return "n/a"
    return "growth" if (rev_d > 0 and stock_5d > 0) else "no_growth"


def _score_prediction(prediction: str, actual: str) -> str:
    """hit / miss / abstain / n/a — same scoring as backtest_quiet_change.py."""
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
    print("Rolling-window backtest — Bedrock Sonnet 4.6", flush=True)
    print(f"BEDROCK_MODEL_ID: {os.environ.get('BEDROCK_MODEL_ID')}", flush=True)
    print(f"Tickers ({len(TICKERS)}): {TICKERS}\n", flush=True)

    print("[step 1] Running agent with decision_cutoff_fy=None (LLM on ALL pairs)…",
          flush=True)
    results: dict[str, dict] = {}
    t0 = time.time()
    for i, code in enumerate(TICKERS, 1):
        print(f"  [{i}/{len(TICKERS)}] {code}: running…", end="", flush=True)
        ts = time.time()
        try:
            r = analyze_company_multi_year(
                code, min_year=2020, run_tests=False,
                skip_simplify=True,
                decision_cutoff_fy=None,    # <<< KEY: LLM on all pairs
                use_cache=True,
                use_prompt_caching=False,
            )
            n_real = len([p for p in r.get("pairs", []) if not p.get("history_only")])
            print(f" ok ({n_real} pair(s), {time.time()-ts:.1f}s)", flush=True)
        except Exception as e:
            print(f" CRASHED: {e}", flush=True)
            r = {"error": str(e)}
        results[code] = r
    print(f"\n  total wall time: {time.time()-t0:.1f}s\n", flush=True)

    # --- step 2: rolling-window scoring ---
    print("=" * 100, flush=True)
    print("ROLLING-WINDOW SCORING — each pair's judgment vs NEXT pair's rev+stock",
          flush=True)
    print("=" * 100, flush=True)
    print(f"\n  {'ticker':>6}  {'pair (prediction)':>22}  {'judgment':>16}  "
          f"{'next-year outcome':>20}  {'rev Δ':>8}  {'stock 5d':>10}  verdict",
          flush=True)
    print(f"  {'-'*6}  {'-'*22}  {'-'*16}  {'-'*20}  {'-'*8}  {'-'*10}  -------",
          flush=True)

    all_scored: list[dict] = []
    for code in TICKERS:
        r = results.get(code, {})
        if "error" in r:
            print(f"  {code}: ERROR -- {r.get('error')}", flush=True)
            continue
        pairs = [p for p in r.get("pairs", []) if not p.get("history_only")]
        pairs.sort(key=lambda p: p.get("curr_period_end", ""))

        # Score each pair i against pair i+1's revenue+stock
        for i in range(len(pairs) - 1):
            pred_pair = pairs[i]
            next_pair = pairs[i + 1]

            pred_label = (f"FY{pred_pair['prev_fiscal_year']}->"
                          f"FY{pred_pair['curr_fiscal_year']}")
            outcome_label = (f"FY{next_pair['prev_fiscal_year']}->"
                             f"FY{next_pair['curr_fiscal_year']}")
            judgment = pred_pair.get("outlook_judgment", "uncertain")

            rev_d = next_pair.get("revenue_delta_pct")
            stock = next_pair.get("stock_5d_return_pct")
            actual = _score_outcome(rev_d, stock)
            verdict = _score_prediction(judgment, actual)

            rev_s = "n/a" if rev_d is None else f"{rev_d:+.2f}%"
            stk_s = "n/a" if stock is None else f"{stock:+.2f}%"
            print(f"  {code:>6}  {pred_label:>22}  {judgment:>16}  "
                  f"{outcome_label:>20}  {rev_s:>8}  {stk_s:>10}  {verdict.upper()}",
                  flush=True)

            all_scored.append({
                "ticker": code,
                "prediction_pair":  pred_label,
                "judgment":         judgment,
                "outcome_pair":     outcome_label,
                "rev_delta_pct":    rev_d,
                "stock_5d_pct":     stock,
                "actual_outcome":   actual,
                "verdict":          verdict,
                "reason_en":        (pred_pair.get("outlook_reason_en") or "")[:200],
            })

    # --- step 3: aggregate ---
    hits = sum(1 for s in all_scored if s["verdict"] == "hit")
    misses = sum(1 for s in all_scored if s["verdict"] == "miss")
    abstains = sum(1 for s in all_scored if s["verdict"] == "abstain")
    n_a = sum(1 for s in all_scored if s["verdict"] == "n/a")
    confident = hits + misses
    hit_rate = (hits / confident * 100) if confident > 0 else 0.0

    print("\n" + "=" * 100, flush=True)
    print("AGGREGATE — ROLLING-WINDOW METHODOLOGY", flush=True)
    print("=" * 100, flush=True)
    print(f"\n  total predictions scored: {len(all_scored)}", flush=True)
    print(f"  hits:                     {hits}", flush=True)
    print(f"  misses:                   {misses}", flush=True)
    print(f"  abstains (uncertain):     {abstains}", flush=True)
    print(f"  n/a (missing outcome):    {n_a}", flush=True)
    print(f"  confident calls:          {confident}", flush=True)
    print(f"  HIT RATE:                 {hits}/{confident} = {hit_rate:.1f}%",
          flush=True)

    # By prediction class
    print(f"\n  By prediction class:", flush=True)
    for cls in ("growth_likely", "growth_unlikely", "uncertain"):
        cls_pairs = [s for s in all_scored if s["judgment"] == cls]
        cls_hits = sum(1 for s in cls_pairs if s["verdict"] == "hit")
        cls_misses = sum(1 for s in cls_pairs if s["verdict"] == "miss")
        cls_abstains = sum(1 for s in cls_pairs if s["verdict"] == "abstain")
        cls_confident = cls_hits + cls_misses
        cls_rate = (cls_hits / cls_confident * 100) if cls_confident > 0 else None
        rate_s = "n/a" if cls_rate is None else f"{cls_rate:.1f}%"
        print(f"    {cls:18s}: {cls_hits} hit / {cls_misses} miss / "
              f"{cls_abstains} abstain    precision: {rate_s}", flush=True)

    print(f"\n  Compare to OLD bundled methodology on same 20 tickers:", flush=True)
    print(f"    Phase 6 bundled hit rate: 70.6% (12 hit / 5 miss / 3 abstain = 17 confident)", flush=True)
    print(f"    Phase 6 bundled growth_unlikely precision: 87.5% (7 hit / 1 miss)", flush=True)

    out_path = ROOT / "outputs" / "rolling_window_backtest.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "methodology": "rolling-window: each pair's judgment scored vs next pair's rev+stock",
        "total_scored": len(all_scored),
        "hits": hits, "misses": misses, "abstains": abstains, "n_a": n_a,
        "hit_rate_pct": round(hit_rate, 2),
        "scored_predictions": all_scored,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
