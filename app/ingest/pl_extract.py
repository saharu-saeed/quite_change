"""Profit & loss extractor for the Quiet Change agent.

Mirrors the shape of `app/ingest/bs_extract.py`. Returns a flat dict of
P/L line items (operating income, ordinary/pretax, net income,
comprehensive income, basic EPS) plus derived margin ratios so the
forward-outlook reasoning has access to "PL + BS + segment all together"
context the senior asked for (会話 2026-05-10).

Real implementation lives in `app.ingest.tempest_loader` because the
data source is the cached Tempest line-items JSON, not raw XBRL — this
file is a thin re-export so call sites can import from a name that
parallels `bs_extract.extract_balance_sheet_from_zip_path`.
"""
from __future__ import annotations

from app.ingest.tempest_loader import extract_pl_from_zip_path

__all__ = ("extract_pl_from_zip_path",)
