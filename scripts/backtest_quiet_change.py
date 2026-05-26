"""Quiet-Change accuracy backtest (per senior 2026-05-10).

Walks the agent over each ticker's full ASR history, collects the
`outlook_judgment` from EVERY pair whose curr_fiscal_year is ≤
`--decision-cutoff-fy`, aggregates them into a single multi-year
prediction, and scores against actual revenue + stock outcomes from
the later "outcome" pairs (curr_fiscal_year > decision_cutoff).

Multi-year voting rule (per user 2026-05-10 design refinement):
  - Collect every per-pair outlook_judgment in the decision window
  - Filter out the "uncertain" votes
  - If non-uncertain votes all agree → that's the prediction
  - If they disagree (mix of growth_likely + growth_unlikely) → uncertain
  - If every vote was "uncertain" → uncertain
This matches the senior's 「2020-2023 のデータから判定」 — use the whole
history window, not just the last year. Single-year snapshots hide
repeating patterns; multi-year consensus surfaces them.

Senior's spec:
  (1) 2020-2023 のデータから「伸びる/伸びない」を判定
  (2) 2024-2025 の実データと答え合わせ
  (3) 情報通信業 630 社全社 — this script supports any subset, default 4 cached.

Usage:
    python scripts/backtest_quiet_change.py
    python scripts/backtest_quiet_change.py --tickers 9432,9433,4307
    python scripts/backtest_quiet_change.py --decision-cutoff-fy 2023

Output: stdout table + JSON written to outputs/backtest_quiet_change.json.

Hit rule:
  prediction=growth_likely    + actual_outcome=growth     -> HIT
  prediction=growth_unlikely  + actual_outcome=no_growth  -> HIT
  prediction=uncertain                                    -> SCORED-AS-ABSTAIN

`actual_outcome` = "growth" iff (revenue_delta_pct > 0 AND stock_5d_return_pct > 0)
                   in the MAJORITY of outcome pairs. Else "no_growth".
This matches the senior's filter intent: companies worth KEEPING are
ones whose revenue grows AND the market validates with a positive
post-filing reaction. Anything else is filter-out material.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Make `app.*` importable when this script runs from the repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import (   # noqa: E402
    analyze_company_multi_year,
    analyze_company_quarterly,
)

# Default ticker list — the four cached 5250 / 3700 tickers with FY2021-2025
# coverage. 4307 is FY2021-2024 only (1 outcome year instead of 2).
# Default 10-ticker pool: 4 already cached + 6 new sector-5250 (情報・通信業)
# names that are likely TOPIX 100 (Tempest only parses TOPIX 100). The
# senior's universe is 情報通信業 (sector 5250); 7203 Toyota is included as
# an out-of-sector control to confirm the agent generalises.
DEFAULT_TICKERS = [
    "4307",  # Nomura Research Institute (5250) — cached
    "9432",  # NTT (5250) — cached
    "9433",  # KDDI (5250) — cached
    "7203",  # Toyota (3700) — control, cached
    "4755",  # Rakuten Group (5250)
    "9434",  # SoftBank Corp (5250)
    "9684",  # Square Enix Holdings (5250)
    "9697",  # Capcom (5250)
    "9984",  # SoftBank Group (5250)
    "6098",  # Recruit Holdings (5250)
]


def _classify_actual_outcome(outcome_pairs: list[dict]) -> str:
    """Aggregate actual-result signal across one or more outcome pairs.

    Returns "growth" iff a majority of pairs show BOTH revenue ↑ AND
    post-filing stock ↑. The conjunction matches the senior's filter
    intent: companies "worth keeping" are validated by both
    fundamentals (revenue) and market reaction (stock).

    Returns "no_growth" otherwise. Returns "n/a" if every pair is
    history-only / lacks stock data.
    """
    if not outcome_pairs:
        return "n/a"
    growth_votes = 0
    scored = 0
    for p in outcome_pairs:
        if p.get("history_only"):
            continue
        rev = p.get("revenue_delta_pct")
        stk = p.get("stock_5d_return_pct")
        if rev is None or stk is None:
            continue
        scored += 1
        if rev > 0 and stk > 0:
            growth_votes += 1
    if scored == 0:
        return "n/a"
    return "growth" if (growth_votes * 2 > scored) else "no_growth"


def _score(prediction: str, actual: str) -> str:
    """Pure scoring. Returns 'hit' / 'miss' / 'abstain' / 'n/a'."""
    if actual == "n/a":
        return "n/a"
    if prediction == "uncertain":
        return "abstain"
    if prediction == "growth_likely" and actual == "growth":
        return "hit"
    if prediction == "growth_unlikely" and actual == "no_growth":
        return "hit"
    return "miss"


# Multi-year voting strategies.
# `judgments` is the list of per-pair outlook_judgment values, ORDERED OLDEST
# FIRST (last element = latest decision pair).
# All return one of: 'growth_likely' / 'growth_unlikely' / 'uncertain'.

def vote_simple(judgments: list[str]) -> str:
    """Original rule: all non-uncertain pairs must agree on the same direction.

    Failure mode discovered 2026-05-10: an OLD positive judgment paired with
    a NEW uncertain one gets called 'growth_likely' because uncertain doesn't
    count — even though the trend is deteriorating. Kept for comparison.
    """
    non_uncertain = [j for j in judgments
                     if j in ("growth_likely", "growth_unlikely")]
    if not non_uncertain:
        return "uncertain"
    if all(j == "growth_likely" for j in non_uncertain):
        return "growth_likely"
    if all(j == "growth_unlikely" for j in non_uncertain):
        return "growth_unlikely"
    return "uncertain"


def vote_recency_weighted(judgments: list[str]) -> str:
    """Recency-weighted majority. Latest pair = 2x weight, others = 1x.

    Tally weighted votes for growth_likely vs growth_unlikely (uncertain
    contributes 0). Higher tally wins; tie → uncertain. This biases toward
    the most recent signal so a fresh deteriorating call isn't overridden
    by an older optimistic one.
    """
    if not judgments:
        return "uncertain"
    likely_w = 0.0
    unlikely_w = 0.0
    n = len(judgments)
    for i, j in enumerate(judgments):
        # Latest pair = index n-1 → weight 2; all others → weight 1.
        w = 2.0 if i == n - 1 else 1.0
        if j == "growth_likely":
            likely_w += w
        elif j == "growth_unlikely":
            unlikely_w += w
        # uncertain contributes 0
    if likely_w == 0 and unlikely_w == 0:
        return "uncertain"
    if likely_w > unlikely_w:
        return "growth_likely"
    if unlikely_w > likely_w:
        return "growth_unlikely"
    return "uncertain"


def vote_trend_aware(judgments: list[str]) -> str:
    """Trend-aware rule that reads the SHAPE of the sequence.

    The intuition: a sequential analyst doesn't just count votes — they
    notice momentum. "Was good, now uncertain" is a deteriorating signal
    that should land as growth_unlikely. "Was bad, now uncertain" is a
    softening that doesn't reach growth_likely.

    Rules (latest pair drives the call, prior pairs MODIFY it):
      - latest = growth_likely → growth_likely (current state is good)
      - latest = growth_unlikely → growth_unlikely (current state is bad)
      - latest = uncertain:
          * any prior was growth_likely → growth_unlikely (deteriorating)
          * any prior was growth_unlikely (and none was likely) → growth_unlikely (still soft)
          * all priors were uncertain (or no priors) → uncertain (no signal)
    """
    if not judgments:
        return "uncertain"
    latest = judgments[-1]
    if latest in ("growth_likely", "growth_unlikely"):
        return latest
    # latest is uncertain — read the prior pairs' direction
    priors = judgments[:-1]
    if any(j == "growth_likely" for j in priors):
        return "growth_unlikely"   # was good, now uncertain → deteriorating
    if any(j == "growth_unlikely" for j in priors):
        return "growth_unlikely"   # was bad, now uncertain → still soft
    return "uncertain"


VOTING_STRATEGIES = {
    # `simple` was retired 2026-05-10 after n=24 backtest showed 41.7% hit
    # rate vs trend_aware's 61.9% AND a 50% abstention rate. Kept defined
    # above (vote_simple function) for reference but excluded from the
    # production comparison to reduce report noise.
    "recency_weighted":  vote_recency_weighted,
    "trend_aware":       vote_trend_aware,
}

# Default voting strategy when a single answer is needed (e.g. when the
# script is invoked downstream by the filter pipeline). Picked 2026-05-10
# based on the n=14 backtest in outputs/backtest_quiet_change.json:
#   simple:           42.9% hit rate, 7/14 abstentions
#   recency_weighted: 61.5% hit rate
#   trend_aware:      69.2% hit rate AND 100% precision on growth_likely
# trend_aware was selected because:
#   (a) highest overall hit rate
#   (b) 100% precision on its "growth_likely" calls — never falsely says
#       "keep this company", which means we never accidentally filter out
#       an actual winner. This asymmetric quality is ideal for the filter
#       use case the senior described 2026-05-10.
DEFAULT_VOTING_STRATEGY = "trend_aware"


def _aggregate_predictions(per_pair_judgments: list[str],
                           strategy: str = "simple") -> str:
    """Dispatch to a named voting strategy."""
    fn = VOTING_STRATEGIES.get(strategy, vote_simple)
    return fn(per_pair_judgments)


def backtest_ticker(code: str, decision_cutoff_fy: int = 2023,
                    mode: str = "annual", skip_simplify: bool = True,
                    skip_outcome_pairs: bool = False,
                    use_cache: bool = True) -> dict[str, Any]:
    """Run the agent on `code`, aggregate outlook across every pair ending
    <= cutoff into a single multi-year prediction, score against subsequent
    actual outcomes.

    `mode`:
      - "annual"    — annual YoY pairs (analyze_company_multi_year, default)
      - "quarterly" — quarterly YoY pairs (analyze_company_quarterly, ~3-4×
                      more decision points per ticker, faster signal but
                      no segment / BS context per pair)
    """
    if mode == "quarterly":
        result = analyze_company_quarterly(code, min_year=2020)
    else:
        # Backtest scoring only reads outlook_judgment / outlook_reason from
        # the Advanced call. The Simplify call is purely UI dressing — skip
        # it by default in backtest mode for 50% LLM-cost savings.
        result = analyze_company_multi_year(
            code, min_year=2020, run_tests=False,
            skip_simplify=skip_simplify,
            decision_cutoff_fy=decision_cutoff_fy if skip_outcome_pairs else None,
            use_cache=use_cache,
        )
    if "error" in result:
        return {"code": code, "error": result["error"]}

    pairs = result.get("pairs", [])
    real_pairs = [p for p in pairs if not p.get("history_only")]
    if not real_pairs:
        return {"code": code, "name": result.get("name", code),
                "error": "no real (non-history-only) pairs available"}

    # Decision pairs = ALL real pairs whose curr_fiscal_year <= cutoff.
    # In quarterly mode this includes Q1/Q2/Q3 of the cutoff year.
    decision_pairs = sorted(
        [p for p in real_pairs if p.get("curr_fiscal_year", 0) <= decision_cutoff_fy],
        key=lambda p: (p["curr_fiscal_year"], p.get("curr_fiscal_quarter", 0)),
    )
    if not decision_pairs:
        return {"code": code, "name": result.get("name", code),
                "error": f"no real pair ending <= FY{decision_cutoff_fy}"}

    def _pair_label(p: dict) -> str:
        if mode == "quarterly":
            return (f"FY{p['prev_fiscal_year']}Q{p.get('prev_fiscal_quarter','?')}->"
                    f"FY{p['curr_fiscal_year']}Q{p.get('curr_fiscal_quarter','?')}")
        return f"FY{p['prev_fiscal_year']}->FY{p['curr_fiscal_year']}"

    per_pair = [
        {"pair": _pair_label(p),
         "judgment": p.get("outlook_judgment", "uncertain"),
         "reason_en": (p.get("outlook_reason_en") or "")[:200]}
        for p in decision_pairs
    ]
    judgments_only = [d["judgment"] for d in per_pair]

    # Outcome pairs = real pairs whose curr_fiscal_year > cutoff.
    outcome_pairs = [p for p in real_pairs
                     if p.get("curr_fiscal_year", 0) > decision_cutoff_fy]
    actual = _classify_actual_outcome(outcome_pairs)

    # Score against ALL THREE voting strategies in one pass — judgments are
    # the same expensive LLM calls; the aggregation is pure arithmetic.
    strategy_results = {
        name: {
            "prediction": _aggregate_predictions(judgments_only, name),
            "verdict": _score(_aggregate_predictions(judgments_only, name), actual),
        }
        for name in VOTING_STRATEGIES
    }

    return {
        "code": code,
        "name": result.get("name", code),
        "mode": mode,
        "decision_window": f"FY{decision_pairs[0]['prev_fiscal_year']}->FY{decision_pairs[-1]['curr_fiscal_year']}",
        "decision_pairs_used": len(decision_pairs),
        "per_pair_judgments": per_pair,
        "outcome_pairs_used": len(outcome_pairs),
        "outcome_years": [p.get("curr_fiscal_year") for p in outcome_pairs],
        "actual_outcome": actual,
        "outcome_detail": [
            {
                "fy": p.get("curr_fiscal_year"),
                "fq": p.get("curr_fiscal_quarter"),  # None in annual mode
                "revenue_delta_pct": p.get("revenue_delta_pct"),
                "stock_5d_pct": p.get("stock_5d_return_pct"),
            }
            for p in outcome_pairs
        ],
        "by_strategy": strategy_results,
    }


def aggregate(rows: list[dict]) -> dict[str, Any]:
    """Per-strategy aggregate: overall hit/miss/abstain rates."""
    out: dict[str, Any] = {}
    def _rate(b: dict[str, int]) -> float | None:
        denom = b["hit"] + b["miss"]
        return (b["hit"] / denom) if denom else None
    for strat in VOTING_STRATEGIES:
        by_pred: dict[str, dict[str, int]] = {}
        overall = {"hit": 0, "miss": 0, "abstain": 0, "n/a": 0, "errors": 0}
        for r in rows:
            if "error" in r:
                overall["errors"] += 1
                continue
            sr = r.get("by_strategy", {}).get(strat, {})
            pred = sr.get("prediction", "uncertain")
            verdict = sr.get("verdict", "n/a")
            bucket = by_pred.setdefault(pred, {"hit": 0, "miss": 0, "abstain": 0, "n/a": 0})
            bucket[verdict] += 1
            overall[verdict] += 1
        out[strat] = {
            "overall": {**overall, "hit_rate": _rate(overall)},
            "by_prediction": {k: {**v, "hit_rate": _rate(v)} for k, v in by_pred.items()},
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", default=",".join(DEFAULT_TICKERS),
                    help="Comma-separated ticker codes.")
    ap.add_argument("--decision-cutoff-fy", type=int, default=2023,
                    help="Latest fiscal year to use as the agent's decision point. "
                         "Outcomes are checked against pairs AFTER this year.")
    ap.add_argument("--mode", choices=["annual", "quarterly"], default="annual",
                    help="annual = year-pair decisions (default), quarterly = "
                         "quarterly YoY pair decisions (3-4× more LLM calls per "
                         "ticker but catches deterioration / recovery faster).")
    ap.add_argument("--out", default=None,
                    help="Where to write the full result JSON. Defaults to "
                         "outputs/backtest_quiet_change_{mode}.json.")
    ap.add_argument("--include-simplify", action="store_true",
                    help="By default the backtest skips the Simplify LLM call "
                         "(saves ~50%% cost — scoring only reads the Advanced "
                         "output). Pass this flag to include Simplify too.")
    ap.add_argument("--skip-outcome-pairs", action="store_true",
                    help="Skip LLM calls on OUTCOME pairs (curr_fiscal_year > "
                         "decision-cutoff-fy). The backtest only reads raw "
                         "revenue + stock numbers from outcome pairs, not the "
                         "LLM judgment — those calls are wasted. Halves cost "
                         "on a typical 4-pair company (2 decision + 2 outcome).")
    ap.add_argument("--no-cache", action="store_true",
                    help="Bypass the on-disk agent result cache (outputs/agent_cache/) "
                         "and force a fresh LLM run for every ticker. By default the "
                         "cache is used — re-runs of the same ticker with the same "
                         "args + prompt template return cached output instantly. "
                         "Use this flag when you want to verify cost / refresh data.")
    args = ap.parse_args()

    if args.out is None:
        args.out = f"outputs/backtest_quiet_change_{args.mode}.json"

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    print(f"Backtest: {len(tickers)} tickers, mode={args.mode}, "
          f"decision cutoff FY{args.decision_cutoff_fy}")
    print(f"Tickers: {', '.join(tickers)}\n")

    rows = []
    for code in tickers:
        print(f"  -> {code}: running agent...", end="", flush=True)
        try:
            row = backtest_ticker(code, decision_cutoff_fy=args.decision_cutoff_fy,
                                  mode=args.mode,
                                  skip_simplify=not args.include_simplify,
                                  skip_outcome_pairs=args.skip_outcome_pairs,
                                  use_cache=not args.no_cache)
        except Exception as e:
            row = {"code": code, "error": f"crashed: {e}"}
        rows.append(row)
        if "error" in row:
            print(f" ERROR: {row['error']}")
        else:
            votes = " | ".join(f"{p['pair'][2:]}={p['judgment'][:3]}"
                               for p in row.get("per_pair_judgments", []))
            print(f" votes=[{votes}]  actual={row['actual_outcome']}")
            for strat, sr in row.get("by_strategy", {}).items():
                print(f"      [{strat:18s}] pred={sr['prediction']:16s} -> {sr['verdict'].upper()}")

    print("\n" + "=" * 80)
    print("PER-TICKER DETAIL")
    print("=" * 80)
    for r in rows:
        if "error" in r:
            print(f"\n{r['code']}: ERROR -- {r['error']}")
            continue
        print(f"\n{r['code']} {r['name']}")
        print(f"  Decision window:  {r['decision_window']}  ({r['decision_pairs_used']} pairs)")
        print(f"  Per-pair votes:")
        for p in r.get("per_pair_judgments", []):
            print(f"    {p['pair']:18s} -> {p['judgment']}")
            if p.get("reason_en"):
                print(f"      reason: {p['reason_en']}")
        print(f"  Outcome years:    {r['outcome_years']}")
        for d in r["outcome_detail"]:
            rd = d["revenue_delta_pct"]
            sd = d["stock_5d_pct"]
            rd_s = "n/a" if rd is None else f"{rd:+.2f}%"
            sd_s = "n/a" if sd is None else f"{sd:+.2f}%"
            print(f"    FY{d['fy']}: revenue d= {rd_s}, stock 5d {sd_s}")
        print(f"  Actual outcome:   {r['actual_outcome']}")
        print(f"  Predictions by strategy:")
        for strat, sr in r.get("by_strategy", {}).items():
            print(f"    {strat:18s} -> {sr['prediction']:16s} verdict={sr['verdict'].upper()}")

    agg = aggregate(rows)
    print("\n" + "=" * 80)
    print("AGGREGATE — STRATEGY COMPARISON")
    print("=" * 80)
    print(f"  {'strategy':<20s} {'hit':>4s} {'miss':>4s} {'abstain':>7s} {'n/a':>4s} {'err':>4s}  hit_rate")
    print(f"  {'-'*20} {'-'*4} {'-'*4} {'-'*7} {'-'*4} {'-'*4}  --------")
    for strat, data in agg.items():
        o = data["overall"]
        rate = o.get("hit_rate")
        rate_s = "n/a" if rate is None else f"{rate*100:5.1f}%"
        print(f"  {strat:<20s} {o['hit']:>4d} {o['miss']:>4d} {o['abstain']:>7d} "
              f"{o['n/a']:>4d} {o['errors']:>4d}   {rate_s}")
    print()
    for strat, data in agg.items():
        print(f"  By prediction class — {strat}:")
        for cls, b in data["by_prediction"].items():
            rate = b.get("hit_rate")
            rate_s = "n/a" if rate is None else f"{rate*100:.1f}%"
            print(f"    {cls:18s}: {b['hit']} hit / {b['miss']} miss / "
                  f"{b['abstain']} abstain  (hit rate: {rate_s})")
        print()

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"rows": rows, "aggregate": agg},
                                   indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nFull JSON written to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
