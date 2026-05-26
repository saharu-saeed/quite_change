"""Phase 5 smoke test — qualitative signals block on NTT (9432). No LLM call.

Verifies:
  - extract_text_section_from_zip_path returns the risk + governance sections
  - _qualitative_signals_yoy correctly truncates prev/curr to budgets
  - _build_qualitative_signals_block renders the framing rules + excerpts
  - Full prompt assembly succeeds and contains the new block
  - Total prompt length is reasonable (Sonnet 4.6 context budget)
"""
from __future__ import annotations
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import _qualitative_signals_yoy   # noqa: E402
from app.subagents.quiet_change_prompt import (                   # noqa: E402
    _build_qualitative_signals_block, build_advanced_prompt,
)
from app.ingest.tempest_loader import (                           # noqa: E402
    extract_text_section_from_zip_path, SECTION_BUSINESS_RISKS,
    SECTION_CORPORATE_GOVERNANCE, load_asr_series, _ticker_dir,
)


def main() -> int:
    print("=== Phase 5 smoke test: NTT (9432) ===", flush=True)
    series = load_asr_series(_ticker_dir("9432"))
    print(f"  {len(series)} ASRs found", flush=True)

    # Pick prev (FY2023) and curr (FY2024) ZIPs — the pair that already has
    # CF data on both sides from Phase 1 testing.
    prev_zip = Path(series[2]["zip_path"])  # FY2023
    curr_zip = Path(series[3]["zip_path"])  # FY2024

    print("\n--- Direct extractor calls ---", flush=True)
    prev_risk = extract_text_section_from_zip_path(prev_zip, SECTION_BUSINESS_RISKS)
    curr_risk = extract_text_section_from_zip_path(curr_zip, SECTION_BUSINESS_RISKS)
    prev_gov = extract_text_section_from_zip_path(prev_zip, SECTION_CORPORATE_GOVERNANCE)
    curr_gov = extract_text_section_from_zip_path(curr_zip, SECTION_CORPORATE_GOVERNANCE)
    print(f"  business_risks       prev={len(prev_risk):,d} chars  curr={len(curr_risk):,d} chars")
    print(f"  corporate_governance prev={len(prev_gov):,d} chars  curr={len(curr_gov):,d} chars")

    print("\n--- _qualitative_signals_yoy (with truncation budgets) ---", flush=True)
    qual = _qualitative_signals_yoy(prev_zip, curr_zip)
    rf = qual["risk_factors"]
    gv = qual["corporate_governance"]
    print(f"  prev_has_risk:       {qual['prev_has_risk']}")
    print(f"  curr_has_risk:       {qual['curr_has_risk']}")
    print(f"  prev_has_governance: {qual['prev_has_governance']}")
    print(f"  curr_has_governance: {qual['curr_has_governance']}")
    print(f"  truncated risk prev: {len(rf['prev']):,d} chars (budget 4000)")
    print(f"  truncated risk curr: {len(rf['curr']):,d} chars (budget 4000)")
    print(f"  truncated gov prev:  {len(gv['prev']):,d} chars (budget 2500)")
    print(f"  truncated gov curr:  {len(gv['curr']):,d} chars (budget 2500)")

    print("\n--- _build_qualitative_signals_block (first 1500 chars of render) ---",
          flush=True)
    block = _build_qualitative_signals_block(qual)
    print(f"  full block length: {len(block):,d} chars")
    print()
    print(block[:1500])
    print("…[truncated for smoke-test display]")

    print("\n--- Empty-data case (None) ---", flush=True)
    empty_block = _build_qualitative_signals_block(None)
    print(f"  block when qual_data=None: {len(empty_block)} chars (expected 0)")

    print("\n--- Both sections empty case ---", flush=True)
    empty_qual = {
        "risk_factors":         {"prev": "", "curr": ""},
        "corporate_governance": {"prev": "", "curr": ""},
        "prev_has_risk": False, "curr_has_risk": False,
        "prev_has_governance": False, "curr_has_governance": False,
    }
    print(f"  block when both sections empty: "
          f"{len(_build_qualitative_signals_block(empty_qual))} chars (expected 0)")

    print("\n--- Full prompt assembly (build_advanced_prompt with all blocks) ---",
          flush=True)
    full = build_advanced_prompt(
        prev_revenue=12.16e12, curr_revenue=13.14e12, revenue_delta_pct=8.1,
        profit_status="profit", segments=[], narrative="テスト",
        stock_pct=6.5, stock_direction="positive",
        qual_data=qual,
        margin_trajectory=[
            {"fiscal_year": y, "revenue": 12e12 + (y - 2020) * 0.3e12,
             "op_margin_pct": 14.0 - (y - 2020) * 0.1,
             "net_margin_pct": 9.0 - (y - 2020) * 0.1}
            for y in range(2020, 2024)
        ],
        curr_fiscal_year=2023,
    )
    print(f"  total prompt length: {len(full):,d} chars  (~{len(full)//4:,d} tokens)")
    print(f"  contains 事業等のリスク marker: {'事業等のリスク' in full}")
    print(f"  contains READING RULES marker: {'READING RULES' in full}")
    print(f"  contains corporate governance marker: {'コーポレート・ガバナンス' in full}")

    print("\n=== DONE — no LLM call made ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
