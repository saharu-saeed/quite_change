"""Option B — does feeding the agent a longer-window INPUT signal change predictions?

The 5d outcome window was empirically validated as best in Option A. Open question:
is that result partly because the agent reads 5d INPUT signals and reasons in a
5d frame? Test: monkey-patch STOCK_REACTION_WINDOW_TRADING_DAYS = 20, re-run the
agent on tickers where the decision-pair quadrant flips, compare predictions.

CHEAP SHORTCUT: only re-run the 13 tickers identified by
window_input_flip_analysis.py as having ≥1 decision-pair quadrant flip at 20d.
For the other 7 tickers, the agent would see the same quadrant chip → same
reasoning → same prediction (we keep the 5d-input verdict).

Score against the 5d outcomes (validated as best in Option A).
"""
from __future__ import annotations
import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Monkey-patch BEFORE importing analyze_company_multi_year so the constant
# is set at the new value when the agent runs.
import app.subagents.quiet_change as qc  # noqa: E402
qc.STOCK_REACTION_WINDOW_TRADING_DAYS = 20

from app.subagents.quiet_change import analyze_company_multi_year  # noqa: E402
from scripts.backtest_quiet_change import (  # noqa: E402
    vote_trend_aware, vote_recency_weighted, _score,
)

BACKTEST_FILE = ROOT / "outputs" / "backtest_20_it_5250.json"
FLIP_FILE = ROOT / "outputs" / "window_input_flip_analysis.json"
DECISION_CUTOFF_FY = 2023
NEW_WINDOW = 20


def _classify_actual_outcome_5d(outcome_pairs: list[dict]) -> str:
    """Score against 5d outcomes (the validated best window per Option A)."""
    growth_votes = 0
    scored = 0
    for p in outcome_pairs:
        rev = p.get("revenue_delta_pct")
        stk = p.get("stock_5d_pct")
        if rev is None or stk is None:
            continue
        scored += 1
        if rev > 0 and stk > 0:
            growth_votes += 1
    if scored == 0:
        return "n/a"
    return "growth" if (growth_votes * 2 > scored) else "no_growth"


def main() -> int:
    baseline = json.loads(BACKTEST_FILE.read_text(encoding="utf-8"))
    flip_data = json.loads(FLIP_FILE.read_text(encoding="utf-8"))

    # Identify tickers with any decision-pair flip at 20d
    affected: set[str] = set()
    for code, rec in flip_data["per_ticker"].items():
        for pair in rec["pairs"]:
            if pair.get("flip_20d"):
                affected.add(code)
                break

    print(f"Affected tickers (need re-run at 20d): {len(affected)}", flush=True)
    print(f"  {sorted(affected)}", flush=True)
    print(f"\nMonkey-patched STOCK_REACTION_WINDOW_TRADING_DAYS = {qc.STOCK_REACTION_WINDOW_TRADING_DAYS}", flush=True)
    print(f"Re-running agent on {len(affected)} tickers...\n", flush=True)

    # Re-run agent on affected tickers
    new_rows: dict[str, dict] = {}
    for i, code in enumerate(sorted(affected), 1):
        print(f"  [{i}/{len(affected)}] {code}: running...", end="", flush=True)
        try:
            result = analyze_company_multi_year(code, min_year=2020, run_tests=False,
                                                skip_simplify=True)
            if "error" in result:
                print(f" ERROR: {result['error']}", flush=True)
                continue
            new_rows[code] = result
            n_pairs = len([p for p in result.get("pairs", []) if not p.get("history_only")])
            print(f" got {n_pairs} pairs", flush=True)
        except Exception as e:
            print(f" CRASHED: {e}", flush=True)

    # ---- Score: combine 20d-input judgments for affected, 5d-input for others
    print("\n" + "=" * 100, flush=True)
    print(f"COMPARING 5d-input vs 20d-input predictions (scored against 5d outcomes)", flush=True)
    print("=" * 100, flush=True)
    print(f"\n  {'ticker':>6s} | {'5d-pred':>16s} {'5d-verd':>8s} | {'20d-pred':>16s} {'20d-verd':>8s} | {'changed':>7s}", flush=True)
    print(f"  {'-'*6} | {'-'*16} {'-'*8} | {'-'*16} {'-'*8} | {'-'*7}", flush=True)

    results: list[dict] = []
    for row in baseline["rows"]:
        if "error" in row:
            continue
        code = row["code"]
        # 5d prediction = baseline trend_aware
        pred_5d = row["by_strategy"]["trend_aware"]["prediction"]
        actual = _classify_actual_outcome_5d(row.get("outcome_detail", []))
        verdict_5d = _score(pred_5d, actual)

        # 20d prediction: if affected, recompute from new agent output; else same as 5d
        if code in new_rows:
            res = new_rows[code]
            decision_pairs = sorted(
                [p for p in res.get("pairs", []) if not p.get("history_only")
                 and p.get("curr_fiscal_year", 0) <= DECISION_CUTOFF_FY],
                key=lambda p: p["curr_fiscal_year"],
            )
            judgments_20d = [p.get("outlook_judgment", "uncertain") for p in decision_pairs]
            pred_20d = vote_trend_aware(judgments_20d)
        else:
            judgments_20d = None
            pred_20d = pred_5d  # unchanged

        verdict_20d = _score(pred_20d, actual)
        changed = "YES" if pred_5d != pred_20d else ""
        print(f"  {code:>6s} | {pred_5d:>16s} {verdict_5d:>8s} | {pred_20d:>16s} {verdict_20d:>8s} | {changed:>7s}", flush=True)

        results.append({
            "code": code,
            "actual_outcome_5d": actual,
            "pred_5d": pred_5d, "verdict_5d": verdict_5d,
            "pred_20d": pred_20d, "verdict_20d": verdict_20d,
            "judgments_20d": judgments_20d,
            "re_ran": code in new_rows,
        })

    # ---- Aggregate
    def _agg(key_pred: str, key_verd: str) -> dict:
        bucket = {"hit": 0, "miss": 0, "abstain": 0, "n/a": 0}
        fo_hit = fo_miss = ke_hit = ke_miss = 0
        for r in results:
            bucket[r[key_verd]] += 1
            actual = r["actual_outcome_5d"]
            if actual == "n/a":
                continue
            if r[key_pred] == "growth_unlikely":
                if actual == "no_growth":
                    fo_hit += 1
                else:
                    fo_miss += 1
            elif r[key_pred] == "growth_likely":
                if actual == "growth":
                    ke_hit += 1
                else:
                    ke_miss += 1
        denom = bucket["hit"] + bucket["miss"]
        return {
            **bucket,
            "hit_rate": bucket["hit"] / denom if denom else None,
            "filter_out_precision": fo_hit / (fo_hit + fo_miss) if (fo_hit + fo_miss) else None,
            "keep_precision": ke_hit / (ke_hit + ke_miss) if (ke_hit + ke_miss) else None,
        }

    agg_5d = _agg("pred_5d", "verdict_5d")
    agg_20d = _agg("pred_20d", "verdict_20d")

    def _row(label: str, a: dict) -> None:
        denom = a["hit"] + a["miss"]
        hr = f"{a['hit_rate']*100:.1f}%" if a["hit_rate"] is not None else "n/a"
        fo = f"{a['filter_out_precision']*100:.1f}%" if a["filter_out_precision"] is not None else "n/a"
        ke = f"{a['keep_precision']*100:.1f}%" if a["keep_precision"] is not None else "n/a"
        print(f"  {label:<14s}  {a['hit']:>3d}  {a['miss']:>4d}  {a['abstain']:>7d}  {a['n/a']:>3d}    "
              f"{hr:>7s}    {fo:>7s}    {ke:>7s}", flush=True)

    print("\n" + "=" * 100, flush=True)
    print(f"AGGREGATE (n={len(results)} tickers, scored against 5d outcomes)", flush=True)
    print("=" * 100, flush=True)
    print(f"  {'config':<14s}  {'hit':>3s}  {'miss':>4s}  {'abstain':>7s}  {'n/a':>3s}    {'hit_rate':>7s}    "
          f"{'FO_prec':>7s}    {'KEEP_prec':>7s}", flush=True)
    _row("5d input", agg_5d)
    _row(f"{NEW_WINDOW}d input", agg_20d)

    n_changed = sum(1 for r in results if r["pred_5d"] != r["pred_20d"])
    print(f"\n  Predictions changed: {n_changed} / {len(results)}", flush=True)

    out_json = ROOT / "outputs" / f"option_b_window_input_{NEW_WINDOW}d.json"
    out_json.write_text(json.dumps({
        "config": {"new_window": NEW_WINDOW, "affected_tickers": sorted(affected)},
        "per_ticker": results,
        "aggregate": {"5d_input": agg_5d, f"{NEW_WINDOW}d_input": agg_20d},
        "predictions_changed": n_changed,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out_json}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
