"""Phase 6 smoke test — balance-sheet quality + concentration block on NTT (9432).

Zero LLM calls. Verifies:
  - Per-year BS items + segment shares extracted cleanly
  - _compute_bs_quality_history derives 5 metrics correctly
  - _build_bs_quality_block renders 3-5y table with trend lines + reading rules
  - Full prompt assembly succeeds
  - Phase 5 (qualitative text) block is GONE from the assembled prompt
"""
from __future__ import annotations
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import (   # noqa: E402
    _compute_bs_quality_history, _segment_yoy,
)
from app.subagents.quiet_change_prompt import (  # noqa: E402
    _build_bs_quality_block, build_advanced_prompt,
)
from app.ingest.tempest_loader import (   # noqa: E402
    extract_pl_from_zip_path, extract_balance_sheet_from_zip_path,
    extract_cashflow_from_zip_path, load_asr_series, _ticker_dir,
)


def _build_raw_history(ticker: str) -> list[dict]:
    """Mirror the analyze_company_multi_year per-year collection loop."""
    series = load_asr_series(_ticker_dir(ticker))
    raw = []
    for s in series:
        zp = Path(s["zip_path"])
        fy = int(s["period_end"][:4])
        try:
            pl = extract_pl_from_zip_path(zp)
        except Exception:
            pl = {"items": {}}
        rev = pl.get("items", {}).get("revenue")

        try:
            bs = extract_balance_sheet_from_zip_path(zp)
        except Exception:
            bs = {"items": {}}
        bs_items = bs.get("items", {})

        try:
            seg_rows, _seg_prev_total, seg_curr_total = _segment_yoy(zp, zp)
            shares = []
            if seg_curr_total and seg_curr_total > 0:
                for r in seg_rows:
                    sv = r.get("curr") or 0.0
                    if sv > 0:
                        shares.append(sv / seg_curr_total)
        except Exception:
            shares = []

        raw.append({
            "fiscal_year":         fy,
            "revenue":             rev,
            "goodwill":            bs_items.get("goodwill"),
            "equity":              bs_items.get("equity"),
            "inventory":           bs_items.get("inventory"),
            "trade_receivables":   bs_items.get("trade_receivables"),
            "segment_shares":      shares,
        })
    return raw


def main() -> int:
    print("=== Phase 6 smoke test: NTT (9432) ===", flush=True)
    raw = _build_raw_history("9432")
    print(f"  {len(raw)} years collected", flush=True)
    print(flush=True)

    print("--- raw per-year inputs ---", flush=True)
    for r in raw:
        def fmt_bn(v):
            return "    —    " if v is None else f"{v/1e9:>8,.1f}bn"
        print(f"  FY{r['fiscal_year']}: rev={fmt_bn(r['revenue'])}  "
              f"goodwill={fmt_bn(r['goodwill'])}  equity={fmt_bn(r['equity'])}  "
              f"inv={fmt_bn(r['inventory'])}  AR={fmt_bn(r['trade_receivables'])}  "
              f"n_segments={len(r['segment_shares'])}")
    print(flush=True)

    print("--- derived bs_quality_history (curr=FY2023) ---", flush=True)
    derived = _compute_bs_quality_history(raw, curr_fiscal_year=2023)
    for r in derived:
        def fp(v): return "  —  " if v is None else f"{v:>5.1f}"
        def fh(v): return "  —  " if v is None else f"{v:>6.0f}"
        print(f"  FY{r['fiscal_year']}: top_seg={fp(r['top_segment_share_pct'])}%  "
              f"Herf={fh(r['herfindahl_index'])}  goodwill/eq={fp(r['goodwill_to_equity_pct'])}%  "
              f"DSO={fp(r['dso_days'])}d  inv_days={fp(r['inventory_days'])}d")
    print(flush=True)

    print("--- rendered Phase 6 block (first 2500 chars) ---", flush=True)
    block = _build_bs_quality_block(derived, curr_fiscal_year=2023)
    print(f"  full block length: {len(block):,d} chars\n")
    print(block[:2500])
    print()

    print("--- _compute_bs_quality_history with empty input ---", flush=True)
    empty = _compute_bs_quality_history([], curr_fiscal_year=2023)
    print(f"  empty history → {len(empty)} rows  (expected 0)")
    empty_block = _build_bs_quality_block(empty, curr_fiscal_year=2023)
    print(f"  empty block → {len(empty_block)} chars  (expected 0)")
    print()

    print("--- 2-year history (below 3-year minimum) ---", flush=True)
    short = derived[:2]
    short_block = _build_bs_quality_block(short, curr_fiscal_year=2023)
    print(f"  2-year input → {len(short_block)} chars  (expected 0; below min)")
    print()

    print("--- full prompt assembly check ---", flush=True)
    prompt = build_advanced_prompt(
        prev_revenue=12.16e12, curr_revenue=13.14e12, revenue_delta_pct=8.1,
        profit_status="profit", segments=[], narrative="テスト",
        stock_pct=6.5, stock_direction="positive",
        bs_quality_history=derived,
        margin_trajectory=[
            {"fiscal_year": y, "revenue": 12e12 + (y - 2020) * 0.3e12,
             "op_margin_pct": 14.0 - (y - 2020) * 0.1,
             "net_margin_pct": 9.0 - (y - 2020) * 0.1}
            for y in range(2020, 2024)
        ],
        curr_fiscal_year=2023,
    )
    print(f"  total prompt length: {len(prompt):,d} chars  (~{len(prompt)//4:,d} tokens)")
    print(f"  contains Phase 6 marker 'Balance-sheet quality & concentration': "
          f"{'Balance-sheet quality & concentration' in prompt}")
    print(f"  contains Phase 5 marker '事業等のリスク': "
          f"{'事業等のリスク' in prompt}  (expected False — Phase 5 rolled back)")
    print(f"  contains Phase 2 marker 'Sector peer comparison': "
          f"{'Sector peer comparison' in prompt}  (note: needs peer_data; with None=False)")
    print(f"  contains Phase 1 marker 'Multi-year trajectory': "
          f"{'Multi-year trajectory' in prompt}")

    print("\n=== DONE — no LLM call made ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
