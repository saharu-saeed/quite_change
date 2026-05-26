"""CLI runner for Quiet Change Agent v2.

Usage:
    python scripts/run_quiet_change_v2.py 7974
    python scripts/run_quiet_change_v2.py 7974 7011 4751 4661 4544

For each ticker, calls analyze_ticker(), pretty-prints the JSON to stdout,
and writes it to outputs/quiet_change_v2/{ticker}_{YYYY-MM-DD}.json. After
all tickers run, prints a summary table.
"""
from __future__ import annotations

import json
import sys
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

OUTPUT_DIR = ROOT / "outputs" / "quiet_change_v2"

PRICING = {
    "claude-haiku-4-5-20251001": {
        "input": 1.0, "output": 5.0, "cache_read": 0.1, "cache_write": 1.25,
    },
    "claude-sonnet-4-6": {
        "input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75,
    },
    # Bedrock pricing (same per-token as direct API for these models)
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": {
        "input": 1.0, "output": 5.0, "cache_read": 0.1, "cache_write": 1.25,
    },
    "us.anthropic.claude-sonnet-4-6-v1": {
        "input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75,
    },
    "us.anthropic.claude-sonnet-4-6": {
        "input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75,
    },
}
TAVILY_COST_PER_SEARCH = {"basic": 0.005, "advanced": 0.01}
ANTHROPIC_WEB_SEARCH_COST_PER_CALL = 0.01
# SerpAPI Developer plan: $50 / 5000 searches = $0.01 per search.
# Free tier (100/month) is $0/search until you hit the cap.
SERPAPI_COST_PER_SEARCH = 0.01


def _estimate_cost(result: dict) -> float:
    model = result.get("model", "")
    price = PRICING.get(model)
    if not price:
        return 0.0
    usage = result.get("usage", {}) or {}
    cost = (
        usage.get("input_tokens", 0) * price["input"] / 1e6
        + usage.get("output_tokens", 0) * price["output"] / 1e6
        + usage.get("cache_read_input_tokens", 0) * price["cache_read"] / 1e6
        + usage.get("cache_creation_input_tokens", 0) * price["cache_write"] / 1e6
    )
    provider = result.get("search_provider")
    if provider == "tavily":
        per = TAVILY_COST_PER_SEARCH.get(result.get("search_depth", "basic"), 0.005)
        cost += per * (result.get("search_count", 1) or 1)
    elif provider == "anthropic_web_search":
        cost += ANTHROPIC_WEB_SEARCH_COST_PER_CALL * (result.get("search_count", 0) or 0)
    elif provider == "serpapi":
        cost += SERPAPI_COST_PER_SEARCH * (result.get("search_count", 1) or 1)
    return cost


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def main(tickers: list[str]) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    rows: list[dict] = []

    for code in tickers:
        print(f"\n=== Analyzing {code} ===", flush=True)
        try:
            result = analyze_ticker(code)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            rows.append({"ticker": code, "error": str(e)})
            continue

        out_path = OUTPUT_DIR / f"{code}_{today}.json"
        out_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
        print(f"  -> wrote {out_path}", flush=True)

        if "error" in result:
            rows.append({"ticker": code, "error": result["error"]})
        else:
            rows.append({
                "ticker": code,
                "name": result.get("company_name_ja") or result.get("company_name_en") or "?",
                "in_scope": result.get("in_scope"),
                "classification": result.get("classification"),
                "confidence": result.get("confidence"),
                "cost": _estimate_cost(result),
            })

    print("\n\n=== SUMMARY ===")
    header = f"{'Ticker':<8} {'Name':<24} {'In-scope':<10} {'Class':<10} {'Conf':<6} {'Cost($)':<8}"
    print(header)
    print("-" * len(header))
    total_cost = 0.0
    for row in rows:
        if "error" in row:
            print(f"{row['ticker']:<8} ERROR: {row['error']}")
        else:
            cost = row.get("cost", 0.0)
            total_cost += cost
            print(
                f"{row['ticker']:<8} "
                f"{_truncate(str(row.get('name', '')), 24):<24} "
                f"{str(row.get('in_scope')):<10} "
                f"{str(row.get('classification', '')):<10} "
                f"{str(row.get('confidence', ''))[:5]:<6} "
                f"{cost:<8.4f}"
            )
    print("-" * len(header))
    print(f"{'TOTAL':<54} {total_cost:.4f}")

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_quiet_change_v2.py TICKER [TICKER ...]")
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
