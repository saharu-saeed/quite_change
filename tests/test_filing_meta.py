"""Tests for Correction 1: filing-type + fiscal-period metadata extractor
and YoY pair matcher.

The extractor tests run against real zips in the repo's data/ tree
(TDnet 5233 太平洋セメント and EDINET 3923 ラクス) — these are the
exact examples called out in the audit memo. find_yoy_pair is tested
with synthesised FilingMeta inputs to cover branches that real data
does not easily exercise (reform-boundary normalisation, period-end
gap outside 9–15 months, missing counterpart type).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.config import ROOT
from app.ingest.filing_meta import (
    FilingMeta,
    extract_edinet_filing_meta,
    extract_tdnet_filing_meta,
    find_yoy_pair,
    get_fy_disagreement_counts,
    reset_fy_disagreement_counters,
)


# ---------------------------------------------------------------------------
# Real-data extractor tests (skip if the sample data is not checked in)
# ---------------------------------------------------------------------------
TDNET_5233_Q2_2025 = ROOT / "data/20260403/20260403/5233_太平洋ｾﾒ/決算短信/2025111059331901ZIP.zip"
TDNET_5233_FY_2025 = ROOT / "data/20260403/20260403/5233_太平洋ｾﾒ/決算短信/2025051254315801ZIP.zip"
EDINET_3923_2024H1 = ROOT / "data/edinet/3923/2024H1.zip"
EDINET_3923_2025H1 = ROOT / "data/edinet/3923/2025H1.zip"
EDINET_3923_2025FY = ROOT / "data/edinet/3923/2025FY.zip"


@pytest.mark.skipif(not TDNET_5233_Q2_2025.exists(), reason="sample TDnet zip missing")
def test_tdnet_q2_recognised_as_quarterly_h1():
    meta = extract_tdnet_filing_meta(TDNET_5233_Q2_2025)
    assert meta is not None
    assert meta.filing_type == "kessan_tanshin_quarter"
    assert meta.fiscal_period == "Q2"
    assert meta.period_end == date(2025, 9, 30)
    assert meta.filing_date == date(2025, 11, 11)
    assert meta.fiscal_year_end == date(2026, 3, 31)


@pytest.mark.skipif(not TDNET_5233_FY_2025.exists(), reason="sample TDnet zip missing")
def test_tdnet_annual_recognised_as_fy():
    meta = extract_tdnet_filing_meta(TDNET_5233_FY_2025)
    assert meta is not None
    assert meta.filing_type == "kessan_tanshin_annual"
    assert meta.fiscal_period == "FY"
    assert meta.period_end == meta.fiscal_year_end == date(2025, 3, 31)


@pytest.mark.skipif(not EDINET_3923_2025H1.exists(), reason="sample EDINET zip missing")
def test_edinet_srs_normalised_to_h1_interim():
    """The 2024 disclosure reform renamed 四半期報告書 (q2r) to 半期報告書 (srs).
    Both must normalise to the same canonical filing_type so YoY pairs
    stay matchable across the reform boundary.
    """
    meta_srs = extract_edinet_filing_meta(EDINET_3923_2025H1)
    meta_q2r = extract_edinet_filing_meta(EDINET_3923_2024H1)
    assert meta_srs is not None and meta_q2r is not None
    assert meta_srs.filing_type == meta_q2r.filing_type == "edinet_h1_interim"
    assert meta_srs.fiscal_period == meta_q2r.fiscal_period == "Q2"


@pytest.mark.skipif(not EDINET_3923_2025FY.exists(), reason="sample EDINET zip missing")
def test_edinet_asr_recognised_as_fy():
    meta = extract_edinet_filing_meta(EDINET_3923_2025FY)
    assert meta is not None
    assert meta.filing_type == "edinet_asr"
    assert meta.fiscal_period == "FY"


@pytest.mark.skipif(
    not (EDINET_3923_2024H1.exists() and EDINET_3923_2025H1.exists()),
    reason="sample EDINET zips missing",
)
def test_yoy_pair_real_data_3923_picks_h1_to_h1_not_annual_to_interim():
    """The audit's headline bug: 3923 ラクス was pairing annual FY2025 against
    H1 2025 (annual-vs-interim mismatch). The fix must pair 2024 H1 → 2025 H1.
    """
    zips = sorted(EDINET_3923_2024H1.parent.glob("*.zip"))
    metas = [m for z in zips for m in [extract_edinet_filing_meta(z)] if m is not None]
    pair = find_yoy_pair(metas)
    assert pair is not None, "expected a YoY H1-to-H1 pair to be found"
    prev, curr = pair
    assert prev.zip_path.name == "2024H1.zip"
    assert curr.zip_path.name == "2025H1.zip"
    assert prev.filing_type == curr.filing_type
    assert prev.fiscal_period == curr.fiscal_period == "Q2"


# ---------------------------------------------------------------------------
# find_yoy_pair branch coverage with synthesised FilingMeta
# ---------------------------------------------------------------------------
def _meta(
    name: str,
    filing_date: date,
    period_end: date,
    filing_type: str = "edinet_asr",
    fiscal_period: str = "FY",
    fiscal_year_end: date | None = None,
) -> FilingMeta:
    return FilingMeta(
        zip_path=Path(name),
        filing_date=filing_date,
        period_end=period_end,
        fiscal_year_end=fiscal_year_end or period_end,
        filing_type=filing_type,
        fiscal_period=fiscal_period,
    )


def test_find_yoy_pair_skips_mismatched_filing_type():
    filings = [
        _meta("2024_annual.zip", date(2024, 6, 30), date(2024, 3, 31),
              filing_type="edinet_asr", fiscal_period="FY"),
        _meta("2025_interim.zip", date(2025, 11, 14), date(2025, 9, 30),
              filing_type="edinet_h1_interim", fiscal_period="Q2",
              fiscal_year_end=date(2026, 3, 31)),
    ]
    assert find_yoy_pair(filings) is None, "annual should not pair with interim"


def test_find_yoy_pair_rejects_gap_outside_window():
    """A prior filing 18 months earlier must not be accepted as YoY."""
    filings = [
        _meta("2023_annual.zip", date(2023, 6, 30), date(2023, 3, 31)),
        _meta("2025_annual.zip", date(2025, 6, 30), date(2025, 3, 31)),
    ]
    assert find_yoy_pair(filings) is None


def test_find_yoy_pair_picks_closest_to_12_months():
    """When multiple valid prior filings exist, pick the one closest to 12 months."""
    filings = [
        _meta("2023_annual.zip", date(2023, 6, 30), date(2023, 3, 31)),
        _meta("2024_annual.zip", date(2024, 6, 30), date(2024, 3, 31)),
        _meta("2025_annual.zip", date(2025, 6, 30), date(2025, 3, 31)),
    ]
    pair = find_yoy_pair(filings)
    assert pair is not None
    prev, curr = pair
    assert prev.zip_path.name == "2024_annual.zip"
    assert curr.zip_path.name == "2025_annual.zip"


def test_find_yoy_pair_returns_none_for_single_filing():
    assert find_yoy_pair([_meta("x.zip", date(2025, 1, 1), date(2024, 12, 31))]) is None


def test_find_yoy_pair_accepts_reform_boundary_interim():
    """2024 H1 filed as q2r (pre-reform) and 2025 H1 filed as srs (post-reform)
    must pair because both normalise to edinet_h1_interim."""
    filings = [
        _meta("2024H1.zip", date(2024, 11, 13), date(2024, 9, 30),
              filing_type="edinet_h1_interim", fiscal_period="Q2",
              fiscal_year_end=date(2025, 3, 31)),
        _meta("2025H1.zip", date(2025, 11, 14), date(2025, 9, 30),
              filing_type="edinet_h1_interim", fiscal_period="Q2",
              fiscal_year_end=date(2026, 3, 31)),
    ]
    pair = find_yoy_pair(filings)
    assert pair is not None
    assert (pair[0].zip_path.name, pair[1].zip_path.name) == ("2024H1.zip", "2025H1.zip")


# ---------------------------------------------------------------------------
# FY-disagreement warning suppression (3-month and 1-month branches)
# ---------------------------------------------------------------------------
LASERTEC_6920_INTERIM = ROOT / "data/edinet/6920/2019-02-12_140_S100F49C.zip"   # Jun-30 FYE, 3mo off
TAKASHIMAYA_8233_INTERIM = ROOT / "data/edinet/8233/2019-01-11_140_S100EVW1.zip"  # Feb-28 FYE, 1mo off
RAKUTEN_4755_ASR = ROOT / "data/edinet/4755/2019-05-10_140_S100FQ5O.zip"          # Dec-31 FYE, 9mo off (Q1r)


@pytest.mark.skipif(not LASERTEC_6920_INTERIM.exists(), reason="sample Lasertec zip missing")
def test_fy_disagreement_3mo_is_suppressed():
    """Jun-30 FYE (Lasertec) differs from March-31 default by exactly 3 months —
    suppressed. Extraction still trusts the iXBRL FY-end."""
    reset_fy_disagreement_counters()
    meta = extract_edinet_filing_meta(LASERTEC_6920_INTERIM)
    assert meta is not None
    assert meta.fiscal_year_end == date(2019, 6, 30)
    supp3, supp1, surfaced = get_fy_disagreement_counts()
    assert supp3 == 1
    assert supp1 == 0
    assert surfaced == 0


@pytest.mark.skipif(not TAKASHIMAYA_8233_INTERIM.exists(), reason="sample Takashimaya zip missing")
def test_fy_disagreement_1mo_is_suppressed():
    """Feb-28 FYE (Takashimaya) differs from March-31 default by exactly 1 month —
    suppressed under the extended rule. Extraction still trusts the iXBRL FY-end."""
    reset_fy_disagreement_counters()
    meta = extract_edinet_filing_meta(TAKASHIMAYA_8233_INTERIM)
    assert meta is not None
    assert meta.fiscal_year_end.month == 2
    supp3, supp1, surfaced = get_fy_disagreement_counts()
    assert supp3 == 0
    assert supp1 == 1
    assert surfaced == 0


@pytest.mark.skipif(not RAKUTEN_4755_ASR.exists(), reason="sample Rakuten zip missing")
def test_fy_disagreement_9mo_still_surfaces():
    """Dec-31 FYE (Rakuten) differs from March-31 default by 9 months for the
    annual filing — outside the suppression rule, must still surface."""
    reset_fy_disagreement_counters()
    meta = extract_edinet_filing_meta(RAKUTEN_4755_ASR)
    assert meta is not None
    assert meta.fiscal_year_end.month == 12
    supp3, supp1, surfaced = get_fy_disagreement_counts()
    # The annual filing must contribute to surfaced, not suppressed.
    assert surfaced >= 1
    assert supp3 == 0 and supp1 == 0
