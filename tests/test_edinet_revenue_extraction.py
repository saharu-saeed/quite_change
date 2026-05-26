"""Characterization tests for the EDINET quarterly revenue extractor
(unified Bug 1 / Bug 2 fix).

These run against real fetched filings in data/edinet/<code>/. Each test
would FAIL on the pre-fix extractor (either because the tag was unknown
or because decimals was being double-applied as a scale factor) and PASS
on the fixed extractor.

Expected values were computed by hand from the iXBRL source:
  * Toshiba 2021-Q1: RevenuesUSGAAPSummaryOfBusinessResults
      raw=727,863  scale=6  ->  727.863 billion JPY
  * JAL 2021-Q1: RevenueIFRS (jpigp_cor)
      raw=133,032,000,000  scale="" (absent)  ->  133.032 billion JPY
  * Rakuten 2021-Q1: RevenueIFRS
      raw=391,513,000,000  scale=""  ->  391.513 billion JPY
  * Lasertec cross-year: 2021-Q1 scale=3, 2023-Q1 scale=6. Any correct
    extractor should produce a ratio within a realistic single-digit range
    across a 2-year window; the pre-fix extractor produced ~27,000x because
    decimals was being compounded with scale.

Tests are skipped (not failed) if the source zip isn't present — the
fetcher must have run first.
"""
from __future__ import annotations
import zipfile
from pathlib import Path

import pytest

from app.config import ROOT
from app.ingest.edinet_loader import _extract_revenue


def _extract(rel_zip: str) -> float | None:
    p = Path(ROOT) / rel_zip
    if not p.exists():
        pytest.skip(f"source zip not present: {rel_zip}")
    with zipfile.ZipFile(p) as zf:
        return _extract_revenue(zf)


def test_toshiba_q1_fy2022_extracts_usgaap_summary_revenue():
    """Toshiba uses `RevenuesUSGAAPSummaryOfBusinessResults` (raw 727,863 with
    scale=6). Expected: ~727.9 billion JPY. Pre-fix: tag unknown -> None;
    even if the tag had been recognised, decimals=-6 would double-count and
    produce ~7.27e17."""
    val = _extract("data/edinet/6502/2021-08-12_140_S100M97K.zip")
    assert val is not None, "extractor returned None — tag not recognised?"
    # 727.863 billion; allow 1% wiggle for any residual rounding.
    assert 720e9 < val < 735e9, f"expected ~727.9 B, got {val:.3e}"


def test_jal_q1_fy2022_extracts_ifrs_revenue():
    """JAL uses `RevenueIFRS` (jpigp_cor namespace), raw 133,032,000,000,
    scale absent, decimals=-6. Pre-fix: tag unknown AND decimals would have
    multiplied by 10^6 if recognised. Expected: ~133.0 billion JPY."""
    val = _extract("data/edinet/9201/2021-08-04_140_S100M3I3.zip")
    assert val is not None
    assert 130e9 < val < 136e9, f"expected ~133.0 B, got {val:.3e}"


def test_rakuten_q1_2021_extracts_ifrs_revenue_calendar_year():
    """Rakuten is a calendar-year issuer on IFRS. `RevenueIFRS` raw
    391,513,000,000 with scale absent. Expected: ~391.5 billion JPY."""
    val = _extract("data/edinet/4755/2021-05-13_140_S100LAVL.zip")
    assert val is not None
    assert 388e9 < val < 395e9, f"expected ~391.5 B, got {val:.3e}"


def test_lasertec_cross_filing_scale_consistency():
    """The Bug 2 regression: Lasertec 2021-Q1 filings used scale=3, by 2023
    they switched to scale=6. Pre-fix code double-applied decimals+scale, so
    the same company appeared to grow ~1000x between filings. After fix,
    the ratio of any two Lasertec quarterly revenues must be in a physically
    plausible range (<10x)."""
    early = _extract("data/edinet/6920/2021-02-10_140_S100KPR1.zip")
    late = _extract("data/edinet/6920/2023-02-10_140_S100Q457.zip")
    assert early is not None and late is not None
    ratio = max(early, late) / min(early, late)
    assert ratio < 10.0, (
        f"cross-filing revenue ratio {ratio:.1f}x is not physical — "
        f"early={early:.3e}, late={late:.3e}"
    )
    # Both should be in the tens of billions (Lasertec's real revenue scale).
    for label, v in (("2021Q1", early), ("2023Q1", late)):
        assert 10e9 < v < 500e9, f"{label} out of plausible range: {v:.3e}"
