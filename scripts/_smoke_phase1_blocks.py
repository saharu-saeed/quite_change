"""Phase 1 smoke test: cashflow extractor + new prompt blocks on NTT.

Zero LLM calls. Verifies:
  - extract_cashflow_from_zip_path returns sensible numbers
  - _cashflow_yoy handles both full and missing-prev pairs
  - _detect_cfo_ni_low_quality streak detector works
  - _build_cashflow_block renders correctly (with + without flag)
  - _build_margin_trajectory_block (extended) shows revenue YoY + net margin
"""
from __future__ import annotations
import sys
import io
import json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import (   # noqa: E402
    _cashflow_yoy, _detect_cfo_ni_low_quality,
)
from app.subagents.quiet_change_prompt import (   # noqa: E402
    _build_cashflow_block, _build_margin_trajectory_block,
)
from app.ingest.tempest_loader import (   # noqa: E402
    extract_cashflow_from_zip_path, extract_pl_from_zip_path,
    load_asr_series, _ticker_dir,
)


def _fmt_pct(v):
    return "None" if v is None else f"{v:.2f}%"


def _fmt_ratio(v):
    return "None" if v is None else f"{v:.2f}x"


def main() -> int:
    print("=== Phase 1 smoke test: NTT (9432) ===", flush=True)
    series = load_asr_series(_ticker_dir("9432"))
    print(f"  {len(series)} ASRs found\n", flush=True)

    # Build the per-year trajectory + cashflow_history exactly the way
    # analyze_company_multi_year does.
    margin_trajectory = []
    cashflow_history = []
    for s in series:
        zp = Path(s["zip_path"])
        fy = int(s["period_end"][:4])
        pl = extract_pl_from_zip_path(zp)
        items = pl.get("items", {})
        derived = pl.get("derived", {})
        rev = items.get("revenue")
        op = items.get("operating_income")
        if rev and rev > 0 and op is not None:
            margin_trajectory.append({
                "fiscal_year":    fy,
                "revenue":        rev,
                "op_margin_pct":  op / rev * 100.0,
                "net_margin_pct": derived.get("net_margin_pct"),
            })
        cf = extract_cashflow_from_zip_path(zp)
        cashflow_history.append({
            "fiscal_year":     fy,
            "cfo_to_ni_ratio": cf.get("derived", {}).get("cfo_to_ni_ratio"),
        })

    print("--- per-year trajectory ---", flush=True)
    for r in margin_trajectory:
        print(f"  FY{r['fiscal_year']}: rev={r['revenue']/1e9:>10,.1f}bn  "
              f"op_margin={r['op_margin_pct']:6.2f}%  "
              f"net_margin={_fmt_pct(r['net_margin_pct'])}", flush=True)
    print(flush=True)

    print("--- CFO/NI history ---", flush=True)
    for r in cashflow_history:
        print(f"  FY{r['fiscal_year']}: CFO/NI={_fmt_ratio(r['cfo_to_ni_ratio'])}",
              flush=True)
    print(flush=True)

    # --- _cashflow_yoy on FY2023->FY2024 (full data both sides) ---
    print("--- _cashflow_yoy(FY2023, FY2024) ---", flush=True)
    prev_zp = Path(series[2]["zip_path"])
    curr_zp = Path(series[3]["zip_path"])
    cf_yoy = _cashflow_yoy(prev_zp, curr_zp)
    print(json.dumps(cf_yoy, indent=2, default=str), flush=True)
    print(flush=True)

    # --- low-quality detector at FY2024 ---
    flag = _detect_cfo_ni_low_quality(cashflow_history, 2024)
    print("--- _detect_cfo_ni_low_quality(curr_fy=2024) ---", flush=True)
    print(json.dumps(flag, indent=2, default=str), flush=True)
    print(flush=True)

    # --- rendered cashflow block ---
    print("--- _build_cashflow_block (FY2023→FY2024) ---", flush=True)
    print(_build_cashflow_block(cf_yoy, flag), flush=True)

    # --- rendered extended trajectory block ---
    print("--- _build_margin_trajectory_block (5y context, curr=FY2024) ---", flush=True)
    print(_build_margin_trajectory_block(margin_trajectory, curr_fiscal_year=2024),
          flush=True)

    # --- graceful degradation on missing prev CF (FY2021→FY2022) ---
    print("--- _cashflow_yoy(FY2021, FY2022) — no CF data either side ---", flush=True)
    prev_zp = Path(series[0]["zip_path"])
    curr_zp = Path(series[1]["zip_path"])
    cf_yoy_old = _cashflow_yoy(prev_zp, curr_zp)
    print(f"  items.cfo: {cf_yoy_old['items'].get('cfo')}", flush=True)
    print(f"  derived.fcf: {cf_yoy_old['derived'].get('fcf')}", flush=True)
    print()
    print("--- _build_cashflow_block (empty pair) ---", flush=True)
    print(_build_cashflow_block(cf_yoy_old, None), flush=True)

    # --- graceful degradation on missing prev CF (FY2022→FY2023, prev empty curr full) ---
    print("--- _cashflow_yoy(FY2022, FY2023) — prev missing, curr present ---", flush=True)
    prev_zp = Path(series[1]["zip_path"])
    curr_zp = Path(series[2]["zip_path"])
    cf_yoy_mix = _cashflow_yoy(prev_zp, curr_zp)
    flag_mix = _detect_cfo_ni_low_quality(cashflow_history, 2023)
    print(f"  items.cfo prev: {cf_yoy_mix['items']['cfo'].get('prev')}", flush=True)
    print(f"  items.cfo curr: {cf_yoy_mix['items']['cfo'].get('curr')}", flush=True)
    print()
    print("--- _build_cashflow_block (mixed pair, FY2023 active) ---", flush=True)
    print(_build_cashflow_block(cf_yoy_mix, flag_mix), flush=True)

    print("=== DONE ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
