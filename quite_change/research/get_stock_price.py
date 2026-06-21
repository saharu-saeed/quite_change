# -*- coding: utf-8 -*-
"""Get exact P0/P1 closing prices for a Japanese stock around an announcement date.

Authentic, robust, multi-source: J-Quants (if token in env) -> Yahoo -> Stooq, each
with retry + backoff. If every source fails, returns stock_dir="pending" (never a guess).

Usage:
    python -m research.get_stock_price 9433 2025-05-14
    python -m research.get_stock_price 9433 2025-05-14 --days 10
    python -m research.get_stock_price 9433 2025-05-14 --flat-threshold 0.5

Output (JSON to stdout):
    {
      "ticker": "9433", "announce_date": "2025-05-14",
      "p0": 4830.0, "p0_date": "2025-05-14",
      "p1": 5010.0, "p1_date": "2025-05-28",
      "pct_change": 3.73, "stock_dir": "up", "price_source": "yahoo"
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

try:  # allow both "python -m research.get_stock_price" and direct execution
    from research.price_feed import compute_p0_p1
except ImportError:
    from price_feed import compute_p0_p1

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Authentic P0/P1 stock prices for a TSE ticker")
    parser.add_argument("ticker", help="4-digit ticker (e.g. 9433)")
    parser.add_argument("announce_date", help="Announcement date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=10, help="Trading days for P1 (default 10)")
    parser.add_argument("--flat-threshold", type=float, default=0.0,
                        help="abs %% change <= this is 'flat' (default 0.0 = binary up/down)")
    args = parser.parse_args()

    announce_dt = datetime.strptime(args.announce_date, "%Y-%m-%d")
    print(f"Fetching {args.ticker} around {args.announce_date} ...", file=sys.stderr)

    result = compute_p0_p1(args.ticker, announce_dt,
                           trading_days=args.days, flat_pct=args.flat_threshold)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["stock_dir"] != "pending" else 2


if __name__ == "__main__":
    sys.exit(main())
