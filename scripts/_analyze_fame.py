"""Compute approx market cap for every name in the sweep watch-list and
flag fame failure cases (mega-brand with low anomaly-attention).

The anomaly-attention signal asks "is the SPECIFIC DROP being written
about?" — which is well-defined for unknown/under-followed names but
meaningless for household-name mega-brands whose general coverage is
high regardless. A famous company with a mild drop will look "thin"
to the anomaly search but is in fact wall-to-wall covered.

Heuristic: market cap > ~¥500B is a rough "definitely famous" line for
Japanese mid-caps. Names above that with attention ≤ 8 should be
re-examined manually — the search likely missed coverage.
"""
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SWEEP = ROOT / "outputs" / "quiet_change_v2" / "sweep" / "_sweep_2026-05-22.json"
TEMPEST = ROOT / "data" / "tempest"

FAME_MARKET_CAP_JPY = 500e9  # ¥500B — rough "definitely well-covered" line


def _approx_market_cap(ticker: str) -> float | None:
    try:
        prices = json.load(open(TEMPEST / ticker / "prices.json", encoding="utf-8"))["data"]
        inds = json.load(open(TEMPEST / ticker / "indicators.json", encoding="utf-8"))["data"]
    except Exception:
        return None
    if not prices or not inds:
        return None
    latest_close = float(prices[0]["close"])
    inds = sorted(inds, key=lambda r: r.get("fiscal_year") or 0, reverse=True)
    so = inds[0].get("shares_outstanding")
    if not so:
        return None
    try:
        return latest_close * float(so)
    except (TypeError, ValueError):
        return None


def main() -> int:
    data = json.load(open(SWEEP, encoding="utf-8"))
    rows = data.get("global_watchlist_top", [])

    print(f"{'Rk':<4} {'Ticker':<7} {'Company':<24} {'Sector':<14} {'Scale':<14} "
          f"{'MCap(¥B)':<10} {'Attn':<6} {'Comp':<6} {'Fame?':<10}")
    print("-" * 110)
    fame_cases = []
    for i, r in enumerate(rows, 1):
        ticker = r["ticker"]
        mcap = _approx_market_cap(ticker)
        mcap_str = f"¥{mcap/1e9:7.0f}B" if mcap else "      -"
        attn = r.get("attention_score") or 0
        comp = r.get("watchlist_composite") or 0
        flag = ""
        if mcap and mcap >= FAME_MARKET_CAP_JPY and attn <= 8.0:
            flag = "FAME-LOW-ATTN"
            fame_cases.append((i, ticker, r["company_name"], mcap, attn, comp))
        elif mcap and mcap >= FAME_MARKET_CAP_JPY:
            flag = "large"
        print(
            f"{i:<4} {ticker:<7} {r['company_name'][:23]:<24} "
            f"{r.get('_sector','?'):<14} {r.get('scale_category','?'):<14} "
            f"{mcap_str:<10} {attn:+5.1f}  {comp:5.1f}  {flag:<10}"
        )

    print(f"\nFame-failure cases (mcap >= ¥{FAME_MARKET_CAP_JPY/1e9:.0f}B AND attn <= 8.0):")
    for rank, ticker, name, mcap, attn, comp in fame_cases:
        print(f"  rank {rank:>2} | {ticker} {name}  ¥{mcap/1e9:.0f}B  attn={attn:+.1f}  comp={comp:.1f}")
    print(f"\nTotal fame-failures in top-{len(rows)}: {len(fame_cases)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
