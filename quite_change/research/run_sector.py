# -*- coding: utf-8 -*-
"""Run the locked lighter prompt against a list of companies (one sector).

Takes a JSON or CSV file of {code, name} entries and produces a single sector
JSON file in the same shape as data/company_research_*.json.

Usage:
    # From a JSON list of {code, name}:
    python -m research.run_sector tickers.json --output data/company_research_my_sector.json

    # From a CSV with header "code,name":
    python -m research.run_sector tickers.csv --output data/company_research_my_sector.json

    # Limit concurrency (default 4 — keep low to respect rate limits):
    python -m research.run_sector tickers.json -o out.json --concurrency 2

Requirements:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...

For a small sector (3-10 companies) this finishes in ~10-15 minutes wall-clock.
For larger sectors or the full 2,900-company universe, prefer the Anthropic
Batch API (50% discount, 24h turnaround) — separate script not included here.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr — needed on Windows so that Japanese chars in the
# help text or output don't trigger UnicodeEncodeError under cp932/cp1252.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

try:
    from anthropic import Anthropic
except ImportError:
    print(
        "Error: the 'anthropic' package is not installed.\n"
        "Install it with:  pip install anthropic",
        file=sys.stderr,
    )
    sys.exit(1)

if __package__:
    from .run_one_company import research_company
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from run_one_company import research_company  # type: ignore


def load_tickers(path: str) -> list[dict]:
    """Load {code, name} entries from JSON or CSV."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "companies" in data:
            data = data["companies"]
        if not isinstance(data, list):
            raise ValueError("JSON input must be a list of {code, name} objects, or {companies: [...]}")
        return [{"code": str(d["code"] if "code" in d else d["ticker"]), "name": d["name"]} for d in data]

    if p.suffix.lower() == ".csv":
        with open(p, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [{"code": str(row.get("code") or row.get("ticker") or "").strip(),
                     "name": (row.get("name") or "").strip()} for row in reader]

    raise ValueError(f"Unsupported file extension: {p.suffix}. Use .json or .csv")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Research a list of companies and write a single sector JSON file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Input format (JSON):\n"
            '  [{"code": "7974", "name": "Nintendo"}, {"code": "9201", "name": "Japan Airlines"}, ...]\n'
            "\n"
            "Input format (CSV with header):\n"
            "  code,name\n"
            "  7974,Nintendo\n"
            "  9201,Japan Airlines\n"
        ),
    )
    parser.add_argument("input", help="Path to .json or .csv listing companies to research")
    parser.add_argument("--output", "-o", required=True, help="Output sector JSON file")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max parallel API calls (default 4). Keep low (≤8) to stay within tier rate limits.",
    )
    parser.add_argument(
        "--sector-name",
        default="Custom",
        help="Sector display name to write into the _meta block (default 'Custom')",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY environment variable is not set.\n"
            "Get one from https://console.anthropic.com/ and:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        return 1

    try:
        tickers = load_tickers(args.input)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"Loaded {len(tickers)} companies from {args.input}", file=sys.stderr)
    print(f"Concurrency: {args.concurrency} parallel calls", file=sys.stderr)
    print(f"Output: {args.output}", file=sys.stderr)
    print(file=sys.stderr)

    client = Anthropic(api_key=api_key)
    results: dict = {}
    failures: list[tuple[str, str, str]] = []  # (code, name, error)

    def _one(entry: dict) -> tuple[str, dict | None, str | None]:
        code, name = entry["code"], entry["name"]
        try:
            data = research_company(client, code, name, lang="en")
            return code, data, None
        except Exception as e:  # noqa: BLE001
            return code, None, str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(_one, t): t for t in tickers}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), start=1):
            t = futures[fut]
            code, data, err = fut.result()
            if err:
                print(f"  [{i}/{len(tickers)}] {code} {t['name']}: ERROR — {err}", file=sys.stderr)
                failures.append((code, t["name"], err))
            else:
                print(f"  [{i}/{len(tickers)}] {code} {t['name']}: ok", file=sys.stderr)
                # The model returns { "{code}": {entry} } — unwrap one level if needed
                inner = data.get(code, data) if isinstance(data, dict) else data
                if isinstance(inner, dict):
                    inner.setdefault("name", t["name"])
                    results[code] = inner

    output = {
        "_meta": {
            "sector": args.sector_name,
            "generated_via": "research/run_sector.py",
            "model": "claude-sonnet-4-6",
            "total_attempted": len(tickers),
            "successful": len(results),
            "failed": len(failures),
            "failures": [{"code": c, "name": n, "error": e} for c, n, e in failures],
        },
        **results,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(file=sys.stderr)
    print(f"Wrote {args.output}: {len(results)} successful, {len(failures)} failed", file=sys.stderr)
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
