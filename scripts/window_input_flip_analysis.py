"""Compute quadrant flips at alternative INPUT windows (10d, 20d).

For each ticker × decision pair (FY2021->2022, FY2022->2023), compute
the post-filing stock return at 5d, 10d, 20d and determine if the
4-quadrant cell (oo/ox/xo/xx) changes.

Output: which tickers would need re-running at each alternative window
for Option B (the cheap shortcut).
"""
from __future__ import annotations
import json
import sys
import io
from pathlib import Path
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ingest import prices  # noqa: E402
from app.ingest.tempest_loader import (  # noqa: E402
    load_asr_series,
    extract_revenue_history_from_zip_path,
)

BACKTEST_FILE = ROOT / "outputs" / "backtest_20_it_5250.json"
WINDOWS = [5, 10, 20]
DECISION_CUTOFF_FY = 2023


def _quad(rev_pct: float, stk_pct: float) -> str:
    r = "o" if rev_pct > 0 else "x"
    s = "o" if stk_pct > 0 else "x"
    return r + s


def _stock_return(ticker: str, filing_date: str, window: int) -> float | None:
    if not filing_date:
        return None
    d = datetime.strptime(filing_date, "%Y-%m-%d")
    pad = max(35, int(window * 1.7) + 20)
    end = (d + timedelta(days=pad)).strftime("%Y-%m-%d")
    df = prices.fetch_prices_df(ticker, filing_date, end)
    if df is None or df.empty:
        return None
    closes = df["Close"].squeeze().dropna()
    if len(closes) < 2:
        return None
    anchor = float(closes.iloc[0])
    target_idx = min(window, len(closes) - 1)
    end_px = float(closes.iloc[target_idx])
    return round((end_px - anchor) / anchor * 100.0, 3)


def main() -> int:
    bt = json.loads(BACKTEST_FILE.read_text(encoding="utf-8"))
    tickers = [r["code"] for r in bt["rows"] if "error" not in r]

    print(f"Analyzing {len(tickers)} tickers × decision pairs at windows {WINDOWS}\n", flush=True)
    print(f"  {'ticker':>6s} | {'pair':>15s} | {'rev%':>7s} | "
          f"{'5d%':>7s} {'10d%':>7s} {'20d%':>7s} | {'5d':>3s} {'10d':>3s} {'20d':>3s} | "
          f"{'flip_10d':>8s} {'flip_20d':>8s}", flush=True)
    print(f"  {'-'*6} | {'-'*15} | {'-'*7} | {'-'*7} {'-'*7} {'-'*7} | {'-'*3} {'-'*3} {'-'*3} | "
          f"{'-'*8} {'-'*8}", flush=True)

    flip_summary = {w: {"latest": [], "earlier": []} for w in [10, 20]}
    per_ticker_flips: dict[str, dict] = {}

    for code in tickers:
        folder = ROOT / "data" / "tempest" / code
        series = load_asr_series(folder)
        # Decision pairs only: curr_fiscal_year <= cutoff (using period_end_year convention)
        decision_pairs = []
        for prev, curr in zip(series, series[1:]):
            curr_fy = int(curr["period_end"][:4])
            if curr_fy <= DECISION_CUTOFF_FY:
                decision_pairs.append((prev, curr))
        if not decision_pairs:
            continue

        # Multi-year history for restated revenue lookup
        latest_zip = Path(series[-1]["zip_path"])
        history = extract_revenue_history_from_zip_path(latest_zip)
        hist_by_year = {h["fiscal_year"]: h["revenue"] for h in history}

        ticker_record = {"pairs": []}
        for i, (prev, curr) in enumerate(decision_pairs):
            is_latest = (i == len(decision_pairs) - 1)
            prev_rev = hist_by_year.get(prev["fiscal_year"], prev["revenue"])
            curr_rev = hist_by_year.get(curr["fiscal_year"], curr["revenue"])
            if not prev_rev or prev_rev == 0:
                continue
            rev_pct = (curr_rev - prev_rev) / prev_rev * 100.0

            filing_date = curr["filing_date"]
            stk = {w: _stock_return(code, filing_date, w) for w in WINDOWS}
            quad = {w: (_quad(rev_pct, stk[w]) if stk[w] is not None else "n/a") for w in WINDOWS}

            pair_label = f"FY{int(prev['period_end'][:4])}->FY{int(curr['period_end'][:4])}"
            flip_10 = "YES" if quad[10] != quad[5] and quad[10] != "n/a" and quad[5] != "n/a" else ""
            flip_20 = "YES" if quad[20] != quad[5] and quad[20] != "n/a" and quad[5] != "n/a" else ""

            print(f"  {code:>6s} | {pair_label:>15s} | {rev_pct:>+6.2f}% | "
                  f"{stk[5]:>+6.2f}% {stk[10]:>+6.2f}% {stk[20]:>+6.2f}% | "
                  f"{quad[5]:>3s} {quad[10]:>3s} {quad[20]:>3s} | "
                  f"{flip_10:>8s} {flip_20:>8s}{'  (LATEST)' if is_latest else ''}", flush=True)

            ticker_record["pairs"].append({
                "pair": pair_label,
                "is_latest": is_latest,
                "rev_pct": rev_pct,
                "quad_5d": quad[5], "quad_10d": quad[10], "quad_20d": quad[20],
                "flip_10d": bool(flip_10), "flip_20d": bool(flip_20),
            })
            if flip_10:
                flip_summary[10]["latest" if is_latest else "earlier"].append((code, pair_label))
            if flip_20:
                flip_summary[20]["latest" if is_latest else "earlier"].append((code, pair_label))

        per_ticker_flips[code] = ticker_record

    print("\n" + "=" * 80, flush=True)
    print("FLIP SUMMARY (which tickers need re-running for Option B)", flush=True)
    print("=" * 80, flush=True)
    for w in (10, 20):
        latest_flips = flip_summary[w]["latest"]
        earlier_flips = flip_summary[w]["earlier"]
        affected_tickers = {t for t, _ in latest_flips} | {t for t, _ in earlier_flips}
        print(f"\nAt {w}d:")
        print(f"  Latest-pair flips (high-impact): {len(latest_flips)}", flush=True)
        for t, p in latest_flips:
            print(f"      {t}  {p}", flush=True)
        print(f"  Earlier-pair flips (medium-impact, only matter when latest=uncertain): {len(earlier_flips)}", flush=True)
        for t, p in earlier_flips:
            print(f"      {t}  {p}", flush=True)
        print(f"  Total distinct tickers needing re-run: {len(affected_tickers)}", flush=True)
        # Estimate LLM cost: re-run those tickers × ~4 pairs × $0.04
        # But strictly we only need to re-run the FLIPPED pairs.
        n_flipped_pairs = len(latest_flips) + len(earlier_flips)
        print(f"  Strictly: {n_flipped_pairs} flipped pairs × $0.04 = ${n_flipped_pairs*0.04:.2f}", flush=True)
        print(f"  Practically (whole-ticker re-runs): "
              f"{len(affected_tickers)} tickers × 4 pairs × $0.04 = ${len(affected_tickers)*4*0.04:.2f}", flush=True)

    out = ROOT / "outputs" / "window_input_flip_analysis.json"
    out.write_text(json.dumps({
        "per_ticker": per_ticker_flips,
        "flip_summary": flip_summary,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
