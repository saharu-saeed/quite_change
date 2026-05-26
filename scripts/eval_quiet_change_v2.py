"""Evaluation harness for Quiet Change Agent v2.

Runs the agent against a labelled test set (5 meeting tickers + 8 sourced
from a Claude research pass on 2026-05-22) and produces:
  - per-ticker comparison: expected vs actual classification + in_scope
  - aggregate precision per class
  - a summary view of confidence + cost

Usage:
    python scripts/eval_quiet_change_v2.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change_v2 import analyze_ticker  # noqa: E402

OUTPUT_DIR = ROOT / "outputs" / "quiet_change_v2" / "eval"

# Test set: (ticker, name_jp, expected_class, sub_driver, source)
TEST_SET: list[dict[str, str]] = [
    # === MEETING TICKERS (2026-05-21 PM meeting) ===
    {"ticker": "7974", "name": "任天堂",          "expected": "negative", "driver": "FY27 guidance cut + Switch 2 costs", "source": "meeting"},
    {"ticker": "7011", "name": "三菱重工業",      "expected": "negative", "driver": "next-period orders down",          "source": "meeting"},
    {"ticker": "4751", "name": "サイバーエージェント", "expected": "negative", "driver": "down guidance + AI ad-sector fear", "source": "meeting+claude"},
    {"ticker": "4661", "name": "オリエンタルランド",  "expected": "negative", "driver": "FY27 guided down, no new growth",   "source": "meeting"},
    {"ticker": "4544", "name": "H.U.グループ",    "expected": "negative", "driver": "downward profit revision Feb 9",   "source": "meeting"},

    # === NEGATIVE (Claude research, high confidence on driver) ===
    {"ticker": "4324", "name": "電通グループ",     "expected": "negative", "driver": "down guidance + AI disruption", "source": "claude"},
    {"ticker": "7203", "name": "トヨタ自動車",     "expected": "negative", "driver": "tariffs cut OP forecast >20%",  "source": "claude"},
    {"ticker": "7270", "name": "SUBARU",          "expected": "negative", "driver": "tariffs, ~53% profit decline",  "source": "claude"},
    {"ticker": "7267", "name": "本田技研工業",     "expected": "negative", "driver": "tariffs + semiconductor supply", "source": "claude"},
    {"ticker": "2221", "name": "岩塚製菓",         "expected": "negative", "driver": "cost pressure, margin squeeze", "source": "claude"},
    {"ticker": "8253", "name": "クレディセゾン",   "expected": "negative", "driver": "cost/funding pressure",         "source": "claude"},

    # === POSITIVE (Claude candidates, profit-taking; may fail in_scope if rallied back) ===
    {"ticker": "8035", "name": "東京エレクトロン", "expected": "positive", "driver": "post-earnings profit-taking (AI-semi)", "source": "claude"},
    {"ticker": "6857", "name": "アドバンテスト",   "expected": "positive", "driver": "post-earnings profit-taking (AI-semi)", "source": "claude"},
]


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    results: list[dict] = []
    t0 = time.time()

    for i, case in enumerate(TEST_SET):
        ticker = case["ticker"]
        print(f"\n[{i+1}/{len(TEST_SET)}] {ticker} {case['name']} (expected: {case['expected']})", flush=True)
        try:
            res = analyze_ticker(ticker)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            results.append({**case, "error": str(e)})
            continue

        out_path = OUTPUT_DIR / f"{ticker}_{today}.json"
        out_path.write_text(
            json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        actual = res.get("classification") or "ERROR"
        conf = res.get("confidence") or "?"
        in_scope = res.get("in_scope")
        match = (actual == case["expected"])
        print(f"  -> actual: {actual} / {conf}  in_scope: {in_scope}  match: {'YES' if match else 'NO'}", flush=True)
        results.append({
            **case,
            "actual": actual,
            "confidence": conf,
            "in_scope": in_scope,
            "match": match,
            "rationale": (res.get("rationale_en") or "")[:200],
        })

    elapsed = time.time() - t0

    # === report ===
    print("\n\n" + "=" * 90)
    print("EVALUATION REPORT")
    print("=" * 90)
    print(f"{'Ticker':<7} {'Name':<22} {'Source':<14} {'Expected':<10} {'Actual':<10} {'Conf':<7} {'InScope':<8} {'OK':<3}")
    print("-" * 90)
    for r in results:
        if "error" in r:
            print(f"{r['ticker']:<7} {r['name']:<22} {r['source']:<14} {r['expected']:<10} ERROR")
            continue
        ok = "YES" if r["match"] else "NO "
        print(
            f"{r['ticker']:<7} "
            f"{r['name'][:21]:<22} "
            f"{r['source']:<14} "
            f"{r['expected']:<10} "
            f"{r['actual']:<10} "
            f"{r['confidence'][:6]:<7} "
            f"{str(r['in_scope'])[:7]:<8} "
            f"{ok:<3}"
        )

    # aggregate
    valid = [r for r in results if "error" not in r]
    matched = sum(1 for r in valid if r["match"])
    n = len(valid)
    print("-" * 90)
    print(f"Overall accuracy: {matched}/{n} = {matched/n*100:.1f}%")

    # per-class precision
    print()
    print("Per-class precision (of tickers the agent predicted X, how many were actually X):")
    for cls in ("negative", "positive", "neutral"):
        predicted = [r for r in valid if r["actual"] == cls]
        if not predicted:
            print(f"  {cls:<10}: no predictions")
            continue
        correct = sum(1 for r in predicted if r["match"])
        print(f"  {cls:<10}: {correct}/{len(predicted)} = {correct/len(predicted)*100:.0f}%")

    print()
    print("Per-class recall (of tickers actually X, how many did the agent catch):")
    for cls in ("negative", "positive", "neutral"):
        actual_cls = [r for r in valid if r["expected"] == cls]
        if not actual_cls:
            print(f"  {cls:<10}: no test cases")
            continue
        caught = sum(1 for r in actual_cls if r["match"])
        print(f"  {cls:<10}: {caught}/{len(actual_cls)} = {caught/len(actual_cls)*100:.0f}%")

    # in_scope summary
    in_scope_correct = sum(1 for r in valid if r["expected"] == "negative" and r.get("in_scope") is True)
    in_scope_neg = sum(1 for r in valid if r["expected"] == "negative")
    print()
    print(f"in_scope=True on negative cases (rev↑+stock↓ pattern): {in_scope_correct}/{in_scope_neg}")

    print()
    print(f"Total wall time: {elapsed:.1f}s ({elapsed/n:.1f}s/ticker)")

    # save aggregated results
    summary_path = OUTPUT_DIR / f"_eval_summary_{today}.json"
    summary_path.write_text(
        json.dumps({"results": results, "elapsed_s": elapsed}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nFull results saved to: {summary_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
