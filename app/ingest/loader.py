"""Unified ingest.

Resolution order per company:
    1. TDnet loader — walks data/<batch>/<batch>/<code>_<name>/ folders
    2. EDINET loader — walks data/edinet/<code>/ folders
    3. data/manual/{code}.json fallback (skipped in backtest mode — its
       contents are fixed to the most recent filing pair and ignore the
       cutoff, which would leak look-ahead into historical replay).

Also attaches yfinance return series around the announcement date so the
quiet_change subagent can compute CAR.

`ingest_all` supports two candidate universes:
    * ``universe="config"``         — only codes in CONFIG.companies (prod)
    * ``universe="all_downloaded"`` — every locally-downloaded TDnet +
                                     EDINET folder, unioned with CONFIG.companies
                                     (backtest; widens the pool beyond the
                                     hand-curated list).
"""
from __future__ import annotations
import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from app.config import CONFIG, DATA_MANUAL, ROOT
from app.ingest import prices
from app.ingest import tdnet_loader
# Source switch (2026-05-10): the EDINET-equivalent data (annual reports,
# segments, financials, MD&A) now comes from the cached TempestAI Finance
# API JSON. tempest_loader exposes the same public surface as the old
# edinet_loader (load_all_edinet, load_company_from_edinet), aliased here
# so call sites stay readable. TDnet (quarterly short forms) is unchanged
# — it's a different source and not in Tempest's scope.
from app.ingest import tempest_loader as edinet_loader

log = logging.getLogger(__name__)


_TDNET_CACHE: dict[str, dict[str, Any]] | None = None
_EDINET_CACHE: dict[str, dict[str, Any]] | None = None
_CACHE_CUTOFF: date | None = None   # cutoff the current cache was built with


def _ensure_caches(cutoff_date: date | None) -> None:
    """Reload both loaders' caches whenever the cutoff changes (backtest mode)."""
    global _TDNET_CACHE, _EDINET_CACHE, _CACHE_CUTOFF
    if (_TDNET_CACHE is not None and _EDINET_CACHE is not None
            and _CACHE_CUTOFF == cutoff_date):
        return
    _TDNET_CACHE = tdnet_loader.load_all_tdnet(ROOT / "data", cutoff_date=cutoff_date)
    _EDINET_CACHE = edinet_loader.load_all_edinet(ROOT / "data", cutoff_date=cutoff_date)
    _CACHE_CUTOFF = cutoff_date
    log.info("TDnet: loaded %d companies (%s)", len(_TDNET_CACHE), sorted(_TDNET_CACHE.keys()))
    if _EDINET_CACHE:
        log.info("EDINET manual: loaded %d companies (%s)",
                 len(_EDINET_CACHE), sorted(_EDINET_CACHE.keys()))


def _get_tdnet(cutoff_date: date | None = None) -> dict[str, dict[str, Any]]:
    _ensure_caches(cutoff_date)
    return _TDNET_CACHE or {}


def _get_edinet(cutoff_date: date | None = None) -> dict[str, dict[str, Any]]:
    _ensure_caches(cutoff_date)
    return _EDINET_CACHE or {}


def _load_manual(code: str) -> dict[str, Any] | None:
    p = DATA_MANUAL / f"{code}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _discover_all_downloaded_codes() -> set[str]:
    """Every 4-digit code that has a local folder under data/ (TDnet or EDINET)."""
    codes: set[str] = set()
    for company in tdnet_loader._walk_batch_roots(ROOT / "data"):
        m = re.match(r"(\d{4})_", company.name)
        if m:
            codes.add(m.group(1))
    edn = ROOT / "data" / "edinet"
    if edn.is_dir():
        for sub in edn.iterdir():
            if sub.is_dir() and re.match(r"^\d{4}$", sub.name):
                codes.add(sub.name)
    return codes


def load_company_fundamentals(
    code: str, cutoff_date: date | None = None, skip_manual: bool = False
) -> dict[str, Any] | None:
    """Return fundamentals for one company. TDnet first, manual JSON fallback.

    Shape:
        {
          code, name, announce_date (YYYY-MM-DD),
          prev_text, curr_text,
          segments_prev: [{segment_name, ratio}, ...],
          segments_curr: [{segment_name, ratio}, ...],
          segment_history: {segment_name: [ratio, ratio, ...]},
          source: "tdnet" | "manual",
        }
    """
    tdn = _get_tdnet(cutoff_date).get(code)
    if tdn is not None:
        return tdn
    edn = _get_edinet(cutoff_date).get(code)
    if edn is not None:
        return edn
    manual = _load_manual(code)
    if manual is not None:
        if skip_manual:
            log.warning(
                "%s: manual fallback exists at data/manual/%s.json but skip_manual=True "
                "(backtest mode — manual files are not cutoff-aware and would leak "
                "look-ahead); skipping.",
                code, code,
            )
            return None
        manual.setdefault("source", "manual")
        return manual
    log.warning("No data for %s in TDnet batches, EDINET, or data/manual/; skipping.", code)
    return None


def load_prices_around(code: str, announce_date: str, days_before: int = 260, days_after: int = 30) -> dict[str, Any]:
    """Fetch daily log returns for code + benchmark around the announcement date.

    Correction 3: default `days_before` widened to 260 calendar days so that the
    market-model CAR has enough history to fit α/β over 120 trading days ending
    30 trading days before the event day (≈ 150 trading days ≈ 220 calendar
    days; 260 gives comfortable headroom for holidays and missing bars).
    """
    d = datetime.strptime(announce_date, "%Y-%m-%d")
    start = (d - timedelta(days=days_before)).strftime("%Y-%m-%d")
    end = (d + timedelta(days=days_after)).strftime("%Y-%m-%d")
    try:
        r_stock = prices.fetch_returns(code, start, end)
        r_bench = prices.fetch_benchmark(CONFIG.benchmark_ticker, start, end)
    except Exception as e:
        log.warning("Price fetch failed for %s: %s", code, e)
        return {"returns": [], "benchmark_returns": []}
    return {
        "returns": [(str(idx.date()), float(v)) for idx, v in r_stock.items() if not pd.isna(v)],
        "benchmark_returns": [(str(idx.date()), float(v)) for idx, v in r_bench.items() if not pd.isna(v)],
    }


ASR_ONLY = {"edinet_asr"}   # 有価証券報告書 (annual securities report)


def load_edinet_only(
    codes: list[str], cutoff_date: date | None = None
) -> dict[str, dict[str, Any]]:
    """EDINET-only ingest for the quiet_change agent.

    Bypasses the shared cache and re-pairs each code with an ASR-only
    filter so the YoY pair always points at two annual reports — not the
    most-recent half-year interim. Only returns codes that have a
    parseable annual YoY pair under data/edinet/<code>/.
    """
    config_by_code = {c.code: c for c in CONFIG.companies}
    out: dict[str, dict[str, Any]] = {}
    for code in codes:
        # Tempest path: load_company_from_edinet accepts the bare ticker
        # string. The "folder" argument is honored for back-compat (path
        # whose ``.name`` is the ticker), but a string is preferred.
        f = edinet_loader.load_company_from_edinet(
            code, cutoff_date=cutoff_date, filing_type_filter=ASR_ONLY,
        )
        if f is None:
            log.warning("quiet_change: %s has no annual (有価証券報告書) YoY pair", code)
            continue
        c = config_by_code.get(code)
        if c is not None and (not f.get("name") or f["name"] == code):
            f["name"] = c.name
        out[code] = f
    return out


def ingest_all(
    cutoff_date: date | None = None,
    universe: Literal["config", "all_downloaded"] = "config",
    skip_manual: bool = False,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Primary ingest entry point.

    Parameters:
      * ``cutoff_date`` — None in production mode (use every filing);
        a date in backtest mode (YoY pair drawn from filings ≤ cutoff only,
        caches rebuilt on cutoff change).
      * ``universe`` — "config" ingests only codes listed in CONFIG.companies
        (production default). "all_downloaded" ingests every locally-downloaded
        TDnet + EDINET folder, unioned with CONFIG.companies — used by the
        backtest to avoid the narrow 8-code CONFIG list being the pool-size
        bottleneck.
      * ``skip_manual`` — when True, skip the data/manual/*.json fallback.
        Must be True in backtest mode: the manual files are static snapshots
        of the most recent filing pair and would leak post-cutoff data.
    """
    config_by_code = {c.code: c for c in CONFIG.companies}
    if universe == "all_downloaded":
        codes = sorted(set(config_by_code) | _discover_all_downloaded_codes())
        log.info(
            "ingest universe=all_downloaded: %d codes (CONFIG=%d, discovered=%d)",
            len(codes), len(config_by_code), len(codes) - len(set(config_by_code)),
        )
    else:
        codes = [c.code for c in CONFIG.companies]

    fundamentals: dict[str, dict[str, Any]] = {}
    price_data: dict[str, dict[str, Any]] = {}
    for code in codes:
        f = load_company_fundamentals(code, cutoff_date=cutoff_date, skip_manual=skip_manual)
        if f is None:
            continue
        c = config_by_code.get(code)
        if c is not None:
            if not f.get("name") or f["name"] == code:
                f["name"] = c.name
            f["role"] = c.role
            f["template_key"] = c.template_key
            f["template_segment"] = c.template_segment
        else:
            # Discovered-only candidate — loader-derived name is fine; role
            # defaults to candidate (backtest pool only ranks candidates).
            f.setdefault("role", "candidate")
            f.setdefault("template_key", None)
            f.setdefault("template_segment", None)
        fundamentals[code] = f
        price_data[code] = load_prices_around(code, f["announce_date"])
    return fundamentals, price_data
