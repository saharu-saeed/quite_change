# -*- coding: utf-8 -*-
"""Patch stock_dir / P0 / P1 / category in an IT quarterly JSON using authentic prices.

Uses the shared price_feed module: J-Quants (if token in env) -> Yahoo -> Stooq, with
retry + backoff. If every source fails for a ticker, that ticker is left as
stock_dir="pending" (never guessed) and category stays provisional.

Usage (from quite_change/ directory):
    python -m research.patch_stock_prices Q4
    python -m research.patch_stock_prices Q4 --ticker 9433
    python -m research.patch_stock_prices Q4 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from research.price_feed import compute_p0_p1
except ImportError:
    from price_feed import compute_p0_p1

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data" / "quarterly"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("quarter", choices=["Q1", "Q2", "Q3", "Q4"])
    parser.add_argument("--ticker", help="Patch only this ticker")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--flat-threshold", type=float, default=0.0)
    args = parser.parse_args()

    json_path = DATA_DIR / f"it_{args.quarter.lower()}_2025.json"
    if not json_path.exists():
        print(f"Error: {json_path} not found.", file=sys.stderr)
        return 1

    data = json.loads(json_path.read_text(encoding="utf-8"))
    companies = data.get("companies", {})
    targets = {args.ticker: companies[args.ticker]} if args.ticker else companies

    changes = 0
    pending = 0
    for ticker, co in targets.items():
        announce_str = co.get("announce_date", "")
        if not announce_str:
            print(f"  {ticker}: no announce_date — skip", file=sys.stderr)
            continue

        try:
            announce_dt = datetime.strptime(announce_str, "%Y-%m-%d")
        except ValueError:
            print(f"  {ticker}: bad announce_date {announce_str!r} — skip", file=sys.stderr)
            continue

        res = compute_p0_p1(ticker, announce_dt,
                            flat_pct=args.flat_threshold, verbose=True)

        if res["stock_dir"] == "pending":
            print(f"  [PENDING] {ticker} {co.get('name_jp', '')[:12]:12} "
                  f"— all sources failed, left pending", file=sys.stderr)
            pending += 1
            if not args.dry_run:
                co["stock_dir"] = "pending"
                co["stock_source"] = "none"
            time.sleep(0.2)
            continue

        p0, p1 = res["p0"], res["p1"]
        new_dir = res["stock_dir"]
        rev_dir = co.get("revenue_dir", "up")
        r_sign = "+" if rev_dir == "up" else "-"
        # flat treated as S- for the binary 4-category screen (no upward reaction)
        s_sign = "+" if new_dir == "up" else "-"
        new_category = f"R{r_sign}xS{s_sign}"
        pct_str = f"{res['pct_change']:+.1f}%"

        old_cat = co.get("category", co.get("category_provisional", "?"))
        print(f"  [OK] {ticker} {co.get('name_jp', '')[:12]:12} "
              f"P0:{p0:.0f}({res['p0_date']})  P1:{p1:.0f}({res['p1_date']})  "
              f"{pct_str}  {new_dir}  cat:{old_cat}->{new_category}  src:{res['price_source']}",
              file=sys.stderr)
        changes += 1

        if not args.dry_run:
            co["stk_p0"] = p0
            co["stk_p1"] = p1
            co["stock_2w_estimate"] = pct_str
            co["stock_pct_change"] = res["pct_change"]
            co["stock_dir"] = new_dir
            co["stock_dir_estimated"] = False
            co["category"] = new_category
            co["p0_date"] = res["p0_date"]
            co["p1_date"] = res["p1_date"]
            co["stock_source"] = res["price_source"]

        time.sleep(0.2)

    print(f"\nDone. {changes} priced, {pending} pending.", file=sys.stderr)

    if not args.dry_run:
        bak = json_path.with_suffix(".bak.json")
        bak.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Written: {json_path}  (backup: {bak})", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
