"""One-shot script: capture the agent's current deterministic outputs as
golden ground-truth fixtures. Run this ONCE to seed
tests/fixtures/quiet_change_golden.json, then manually verify each row
against the actual EDINET filing + Yahoo Finance and tighten the
ground_truth_source field per case.

This deliberately AVOIDS the LLM call (no $$ spent during bootstrap).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.ingest.edinet_loader import load_asr_series
from app.subagents.quiet_change import (
    _classify_revenue,
    _segment_yoy,
    _stock_5d_move,
)
from app.config import ROOT


# Hand-picked mix: 5 large-cap with diverse stock outcomes, 5 mid/specialised
# with longer histories so multi-year coverage is exercised.
CASES = [
    {"code": "6758", "min_year": 2024, "label": "FY24_FY25"},   # Sony
    {"code": "9983", "min_year": 2024, "label": "FY24_FY25"},   # Fast Retailing
    {"code": "9432", "min_year": 2024, "label": "FY24_FY25"},   # NTT
    {"code": "9984", "min_year": 2024, "label": "FY24_FY25"},   # SoftBank
    {"code": "8001", "min_year": 2024, "label": "FY24_FY25"},   # Itochu
    {"code": "7201", "min_year": 2024, "label": "FY24_FY25"},   # Nissan
    {"code": "7733", "min_year": 2024, "label": "FY24_FY25"},   # Olympus
    {"code": "9201", "min_year": 2024, "label": "FY24_FY25"},   # JAL
    {"code": "8233", "min_year": 2024, "label": "FY24_FY25"},   # Takashimaya
    {"code": "6920", "min_year": 2024, "label": "FY24_FY25"},   # Lasertec
]


def bootstrap_one(code: str, min_year: int) -> dict | None:
    folder = ROOT / "data" / "edinet" / code
    series = [s for s in load_asr_series(folder) if int(s["period_end"][:4]) >= min_year]
    if len(series) < 2:
        print(f"  {code}: insufficient ASRs (have {len(series)}, need >=2)")
        return None
    prev, curr = series[-2], series[-1]
    segments, total_prev, total_curr = _segment_yoy(Path(prev["zip_path"]), Path(curr["zip_path"]))
    if total_prev == 0:
        total_prev = prev["revenue"]
    if total_curr == 0:
        total_curr = curr["revenue"]
    profit_status, delta_pct = _classify_revenue(total_prev, total_curr)
    stock = _stock_5d_move(code, curr["filing_date"])
    top_segments = [s["name"] for s in sorted(segments, key=lambda r: -(r["prev"] + r["curr"]))[:3]]

    return {
        "case_id": f"{code}_FY{int(prev['period_end'][:4]) % 100}_FY{int(curr['period_end'][:4]) % 100}",
        "code": code,
        "min_year": min_year,
        "expected": {
            "prev_fiscal_year": int(prev["period_end"][:4]),
            "curr_fiscal_year": int(curr["period_end"][:4]),
            "prev_filing_date": prev["filing_date"],
            "curr_filing_date": curr["filing_date"],
            "prev_revenue": int(total_prev),
            "curr_revenue": int(total_curr),
            "revenue_delta_pct_approx": round(delta_pct, 3),
            "profit_status": profit_status,
            "stock_5d_return_pct_approx": stock.get("stock_5d_return_pct"),
            "stock_direction": stock.get("stock_direction"),
            "anchor_date": stock.get("anchor_date"),
            "end_date": stock.get("end_date"),
            "expected_top_segments_by_size": top_segments,
            "ground_truth_source": (
                "AGENT-BOOTSTRAPPED — verify each value manually against "
                "the actual EDINET filing (有報) and Yahoo Finance / Kabutan "
                "before relying on this as a regression baseline."
            ),
        },
        "tolerance": {
            "revenue_pct": 1.0,    # 1% of expected
            "stock_pct": 0.5,      # 0.5 percentage points absolute
        },
    }


def main():
    out_path = ROOT / "tests" / "fixtures" / "quiet_change_golden.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fixtures = []
    for c in CASES:
        print(f"bootstrapping {c['code']}...")
        row = bootstrap_one(c["code"], c["min_year"])
        if row is not None:
            fixtures.append(row)

    out_path.write_text(json.dumps({"cases": fixtures}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(fixtures)} cases → {out_path}")


if __name__ == "__main__":
    main()
