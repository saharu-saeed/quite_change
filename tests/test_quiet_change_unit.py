"""Pure unit tests for quiet_change math/classification helpers.
No LLM, no XBRL, no network. Safe to run in CI on every change.
"""
from __future__ import annotations

import pytest

from app.subagents.quiet_change import (
    _classify_revenue,
    _classify_stock_direction,
)


class TestClassifyRevenue:
    def test_revenue_growth(self):
        status, pct = _classify_revenue(100.0, 110.0)
        assert status == "profit"
        assert pct == pytest.approx(10.0)

    def test_revenue_decline(self):
        status, pct = _classify_revenue(100.0, 90.0)
        assert status == "loss"
        assert pct == pytest.approx(-10.0)

    def test_revenue_flat(self):
        status, pct = _classify_revenue(100.0, 100.0)
        assert status == "flat"
        assert pct == 0.0

    def test_zero_prev_returns_flat(self):
        # Defensive — divide-by-zero guard.
        status, pct = _classify_revenue(0.0, 100.0)
        assert status == "flat"
        assert pct == 0.0

    def test_negative_prev_returns_flat(self):
        # Defensive — negative previous is nonsensical for revenue.
        status, pct = _classify_revenue(-50.0, 100.0)
        assert status == "flat"
        assert pct == 0.0

    def test_large_numbers_no_overflow(self):
        # Sony-scale: ~12T JPY.
        status, pct = _classify_revenue(11_260_037_000_000.0, 12_034_917_000_000.0)
        assert status == "profit"
        assert pct == pytest.approx(6.882, abs=0.01)


class TestClassifyStockDirection:
    def test_positive(self):
        assert _classify_stock_direction(0.001) == "positive"
        assert _classify_stock_direction(5.07) == "positive"

    def test_negative(self):
        assert _classify_stock_direction(-0.001) == "negative"
        assert _classify_stock_direction(-3.5) == "negative"

    def test_unchanged(self):
        assert _classify_stock_direction(0.0) == "unchanged"

    def test_none_is_unknown(self):
        assert _classify_stock_direction(None) == "unknown"
