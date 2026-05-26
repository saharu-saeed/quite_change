"""Quiet Change verification harness.

Loads tests/fixtures/quiet_change_golden.json, runs the agent against
each case, asserts deterministic fields against expected values within
tolerance, optionally invokes the LLM-as-judge for explanation quality,
and writes a Markdown report under outputs/eval/.

Usage:
  python -m scripts.eval_quiet_change                  # full eval (with judge, ~$1-2)
  python -m scripts.eval_quiet_change --skip-llm-judge # deterministic only (free)
  python -m scripts.eval_quiet_change --only 6758      # filter to one code
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import time
from datetime import datetime
from pathlib import Path

from app.config import ROOT
from app.ingest.edinet_loader import load_asr_series
from app.subagents.quiet_change import analyze_company_multi_year
from scripts.eval_quiet_change_judge import (
    judge_explanation,
    judge_bilingual_pair,
)


def _narrative_for_pair(code: str, min_year: int, curr_fy: int) -> str:
    """Re-fetch the narrative the agent saw for the given (code, curr_fy) pair."""
    folder = ROOT / "data" / "edinet" / code
    series = [s for s in load_asr_series(folder) if int(s["period_end"][:4]) >= min_year]
    for s in series:
        if int(s["period_end"][:4]) == curr_fy:
            return s.get("qualitative_text", "")
    return ""

log = logging.getLogger("eval_quiet_change")


def _load_fixture(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def _find_pair(pairs: list[dict], prev_fy: int, curr_fy: int) -> dict | None:
    for p in pairs:
        if p.get("prev_fiscal_year") == prev_fy and p.get("curr_fiscal_year") == curr_fy:
            return p
    return None


def _check_deterministic(expected: dict, actual: dict, tol: dict) -> dict:
    """Returns dict with per-field pass/fail and overall det_passed."""
    failures: list[str] = []

    # Revenue prev — within tolerance.revenue_pct of expected.
    if abs(actual.get("prev_revenue", 0) - expected["prev_revenue"]) / max(expected["prev_revenue"], 1) * 100 > tol["revenue_pct"]:
        failures.append(f"prev_revenue: expected {expected['prev_revenue']:,}, got {actual.get('prev_revenue', 0):,}")
    if abs(actual.get("curr_revenue", 0) - expected["curr_revenue"]) / max(expected["curr_revenue"], 1) * 100 > tol["revenue_pct"]:
        failures.append(f"curr_revenue: expected {expected['curr_revenue']:,}, got {actual.get('curr_revenue', 0):,}")

    # Profit status — exact match.
    if actual.get("profit_status") != expected["profit_status"]:
        failures.append(f"profit_status: expected {expected['profit_status']!r}, got {actual.get('profit_status')!r}")

    # Stock direction — exact match.
    if actual.get("stock_direction") != expected["stock_direction"]:
        failures.append(f"stock_direction: expected {expected['stock_direction']!r}, got {actual.get('stock_direction')!r}")

    # Stock 5d return — within absolute tolerance.stock_pct.
    exp_pct = expected.get("stock_5d_return_pct_approx")
    act_pct = actual.get("stock_5d_return_pct")
    if exp_pct is not None and act_pct is not None:
        if abs(act_pct - exp_pct) > tol["stock_pct"]:
            failures.append(f"stock_5d_return_pct: expected ~{exp_pct:+.2f}%, got {act_pct:+.2f}%")

    return {
        "passed": not failures,
        "failures": failures,
    }


def _judge_pair(case_id: str, code: str, min_year: int, expected: dict, pair: dict) -> dict:
    """Run the LLM judge across all four explanations + bilingual fidelity."""
    case_inputs = {
        "prev_revenue":            pair.get("prev_revenue", expected["prev_revenue"]),
        "curr_revenue":            pair.get("curr_revenue", expected["curr_revenue"]),
        "revenue_delta_pct_approx":pair.get("revenue_delta_pct", expected["revenue_delta_pct_approx"]),
        "profit_status":           pair.get("profit_status", expected["profit_status"]),
        "stock_direction":         pair.get("stock_direction", expected["stock_direction"]),
        "stock_5d_return_pct_approx": pair.get("stock_5d_return_pct"),
        "segments":                pair.get("segments", []),
        "narrative":               _narrative_for_pair(code, min_year, pair["curr_fiscal_year"]),
    }
    out = {}
    for kind in ("simple", "advanced"):
        for lang in ("en", "ja"):
            field = f"explanation_{kind}_{lang}"
            text = pair.get(field, "")
            log.info("    judging %s.%s ...", kind, lang)
            out[f"{kind}_{lang}"] = judge_explanation(case_inputs, text, kind, lang)
    # Cross-language fidelity (run once per kind, not per language).
    log.info("    bilingual fidelity (simple) ...")
    out["bilingual_simple"]   = judge_bilingual_pair(pair.get("explanation_simple_en", ""),
                                                    pair.get("explanation_simple_ja", ""))
    log.info("    bilingual fidelity (advanced) ...")
    out["bilingual_advanced"] = judge_bilingual_pair(pair.get("explanation_advanced_en", ""),
                                                    pair.get("explanation_advanced_ja", ""))
    return out


def _correlation(xs: list[float], ys: list[float]) -> float | None:
    """Pearson r. Returns None if either side is constant or len<2."""
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    mx = sum(xs) / n; my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _render_markdown(rows: list[dict], judge_rows: list[dict], correlation: float | None) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = [f"# Quiet Change eval report — {ts}\n"]

    # Deterministic table
    lines.append("## Deterministic checks")
    lines.append("| # | Case | Revenue prev | Revenue curr | Profit | Stock5d | Direction | Result |")
    lines.append("|---|------|--------------|--------------|--------|---------|-----------|--------|")
    pass_count = 0
    for i, r in enumerate(rows, 1):
        status = "PASS" if r["det"]["passed"] else "FAIL"
        if r["det"]["passed"]:
            pass_count += 1
        lines.append(
            f"| {i} | {r['case_id']} | {r['actual_prev']:,} | {r['actual_curr']:,} | "
            f"{r['actual_profit']} | {r['actual_stock_pct']} | {r['actual_direction']} | **{status}** |"
        )
    lines.append(f"\nDeterministic pass: **{pass_count}/{len(rows)}**\n")

    # Failure detail
    fails = [r for r in rows if not r["det"]["passed"]]
    if fails:
        lines.append("### Failures")
        for r in fails:
            lines.append(f"- **{r['case_id']}**:")
            for f in r["det"]["failures"]:
                lines.append(f"  - {f}")
        lines.append("")

    # Judge scores
    if judge_rows:
        lines.append("## LLM-as-judge rubric scores (0-5 scale)\n")
        lines.append("Per-explanation mean across all cases:")
        lines.append("| Dimension | simple_en | simple_ja | advanced_en | advanced_ja |")
        lines.append("|---|---|---|---|---|")
        dims = ["faithfulness", "completeness", "plain_language"]
        for dim in dims:
            row = [dim]
            for combo in ("simple_en", "simple_ja", "advanced_en", "advanced_ja"):
                scores = [j[combo][dim]["score"] for j in judge_rows
                          if j[combo][dim]["score"] >= 0]
                if scores:
                    row.append(f"{sum(scores)/len(scores):.2f}")
                else:
                    row.append("n/a")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
        lines.append("Bilingual EN↔JA fidelity (mean across cases):")
        bs_simple = [j["bilingual_simple"]["score"] for j in judge_rows]
        bs_adv    = [j["bilingual_advanced"]["score"] for j in judge_rows]
        lines.append(f"- Simple pair:   **{sum(bs_simple)/len(bs_simple):.2f}**")
        lines.append(f"- Advanced pair: **{sum(bs_adv)/len(bs_adv):.2f}**\n")

        # Per-case detail
        lines.append("### Per-case judge scores")
        lines.append("| Case | simple_en F/C/PL | simple_ja F/C/PL | adv_en F/C | adv_ja F/C | bi_simp | bi_adv |")
        lines.append("|---|---|---|---|---|---|---|")
        for r, j in zip(rows, judge_rows):
            def s3(combo):
                d = j[combo]
                return f"{d['faithfulness']['score']}/{d['completeness']['score']}/{d['plain_language']['score']}"
            def s2(combo):
                d = j[combo]
                return f"{d['faithfulness']['score']}/{d['completeness']['score']}"
            lines.append(
                f"| {r['case_id']} | {s3('simple_en')} | {s3('simple_ja')} | "
                f"{s2('advanced_en')} | {s2('advanced_ja')} | "
                f"{j['bilingual_simple']['score']} | {j['bilingual_advanced']['score']} |"
            )
        lines.append("")

    # Sanity correlation
    lines.append("## Cross-case sanity correlation\n")
    if correlation is None:
        lines.append("Not enough variance to compute (need >=2 distinct values on both axes).")
    else:
        lines.append(f"`revenue_delta_pct ↔ stock_5d_return_pct`  Pearson **r = {correlation:+.3f}**  "
                     f"(n={sum(1 for r in rows if r['actual_stock_pct_num'] is not None)})")
        lines.append("")
        lines.append("This is a 10-case smell test, not a real backtest. Sign matters more than magnitude.")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(ROOT / "tests" / "fixtures" / "quiet_change_golden.json"))
    ap.add_argument("--out",   default=None, help="output markdown path; default = outputs/eval/quiet_change_<ts>.md")
    ap.add_argument("--skip-llm-judge", action="store_true")
    ap.add_argument("--only", help="filter to one code (e.g., 6758)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    cases = _load_fixture(Path(args.cases))
    if args.only:
        cases = [c for c in cases if c["code"] == args.only]
    if not cases:
        log.error("no cases to run")
        return

    rows: list[dict] = []
    judge_rows: list[dict] = []
    rev_deltas: list[float] = []
    stock_pcts: list[float] = []

    for i, case in enumerate(cases, 1):
        cid = case["case_id"]
        expected = case["expected"]
        log.info("[%d/%d] %s ...", i, len(cases), cid)
        result = analyze_company_multi_year(case["code"], min_year=case["min_year"])
        if result.get("error"):
            log.error("  error: %s", result["error"])
            continue
        pair = _find_pair(result.get("pairs", []),
                          expected["prev_fiscal_year"], expected["curr_fiscal_year"])
        if pair is None:
            log.error("  could not locate pair %d→%d in agent output",
                      expected["prev_fiscal_year"], expected["curr_fiscal_year"])
            continue

        det = _check_deterministic(expected, pair, case["tolerance"])
        rows.append({
            "case_id": cid,
            "actual_prev": pair.get("prev_revenue", 0),
            "actual_curr": pair.get("curr_revenue", 0),
            "actual_profit": pair.get("profit_status", "?"),
            "actual_stock_pct": (f"{pair['stock_5d_return_pct']:+.2f}%"
                                  if pair.get("stock_5d_return_pct") is not None else "n/a"),
            "actual_stock_pct_num": pair.get("stock_5d_return_pct"),
            "actual_direction": pair.get("stock_direction", "?"),
            "det": det,
        })
        if pair.get("revenue_delta_pct") is not None and pair.get("stock_5d_return_pct") is not None:
            rev_deltas.append(pair["revenue_delta_pct"])
            stock_pcts.append(pair["stock_5d_return_pct"])

        if not args.skip_llm_judge:
            judge_rows.append(_judge_pair(cid, case["code"], case["min_year"], expected, pair))
            time.sleep(0.5)

    correlation = _correlation(rev_deltas, stock_pcts)
    md = _render_markdown(rows, judge_rows, correlation)

    out_path = Path(args.out) if args.out else (
        ROOT / "outputs" / "eval" / f"quiet_change_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    log.info("wrote report → %s", out_path)
    print("\n" + md)


if __name__ == "__main__":
    main()
