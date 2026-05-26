"""Stock price loader — backed by the cached TempestAI Finance API.

Reads ``data/tempest/{ticker}/prices.json`` (populated by ``fetch_tempest.py``)
instead of calling yfinance live. Public function signatures match the
original yfinance-based version so existing callers keep working.

Tickers that look like ``"1306.T"`` (yfinance Japanese-equity convention)
have the ``.T`` suffix stripped before lookup. Bare 4/5-digit tickers
work directly.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import ROOT

log = logging.getLogger(__name__)

DATA_DIR = ROOT / "data" / "tempest"


def _normalize_ticker(t: str) -> str:
    """``"1306.T"`` → ``"1306"`` (yfinance suffix → Tempest convention)."""
    return t.split(".")[0]


def _adjust_for_splits(s: pd.Series) -> pd.Series:
    """Back-adjust prior prices for stock splits / reverse splits.

    Tempest returns raw close prices with NO adjustment factor — so a 25:1
    forward split (e.g., NTT 2023-06-29: ¥4,405 → ¥171.20) shows up in our
    data as a 96% one-day "crash" that breaks every downstream calculation
    using these prices (CAR, 5-day post-filing return, returns chart).

    Detection rule: a consecutive-day close ratio outside [0.5, 2.0] is
    flagged as a candidate split, AND the new price level must persist for
    at least 3 more trading days (mean-reverting spikes are not splits).
    When confirmed, all PRIOR closes are multiplied by the ratio so they
    sit on the same basis as the post-split prices.

    Added 2026-05-12 after demo run on 9432 NTT exposed the bug.
    """
    if len(s) < 5:
        return s
    closes = s.values.astype(float).copy()
    dates = s.index
    i = 1
    while i < len(closes):
        prev = closes[i - 1]
        curr = closes[i]
        if prev <= 0 or curr <= 0:
            i += 1
            continue
        ratio = curr / prev
        if 0.5 <= ratio <= 2.0:
            i += 1
            continue
        # Candidate split — confirm persistence over the next 3 trading days.
        # Mean-reverting one-day data spikes are NOT splits; splits stay put.
        end = min(i + 4, len(closes))
        forward = closes[i:end]
        if len(forward) < 2 or any(f <= 0 for f in forward):
            i += 1
            continue
        sorted_fwd = sorted(forward)
        median_forward = sorted_fwd[len(sorted_fwd) // 2]
        forward_vs_today = median_forward / curr
        forward_vs_yesterday = median_forward / prev
        if 0.7 <= forward_vs_today <= 1.4 and abs(forward_vs_yesterday - 1.0) > 0.3:
            # Confirmed split — back-adjust all prior closes by the ratio so
            # the historical series is on the SAME basis as the post-split prices.
            closes[:i] = closes[:i] * ratio
            log.info("split detected for %s on %s: ratio %.4f, adjusted %d prior closes",
                     s.name, dates[i].date(), ratio, i)
        i += 1
    return pd.Series(closes, index=dates, name=s.name)


def _load_close(ticker: str) -> pd.Series:
    """Return a date-indexed Series of close prices for ``ticker``.

    Empty Series if the cache file is missing or has no rows.
    Prices are SPLIT-ADJUSTED via `_adjust_for_splits()`.
    """
    code = _normalize_ticker(ticker)
    path = DATA_DIR / code / "prices.json"
    if not path.exists():
        log.warning("tempest prices cache missing for %s — run fetch_tempest.py "
                    "with --tickers %s", code, code)
        return pd.Series(dtype=float, name=ticker)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return pd.Series(dtype=float, name=ticker)
    rows = payload.get("data", [])
    if not rows:
        return pd.Series(dtype=float, name=ticker)
    dates: list[pd.Timestamp] = []
    closes: list[float] = []
    for r in rows:
        d = r.get("date")
        c = r.get("close")
        if not d or c is None:
            continue
        try:
            closes.append(float(c))
        except (TypeError, ValueError):
            continue
        dates.append(pd.Timestamp(d))
    if not dates:
        return pd.Series(dtype=float, name=ticker)
    s = pd.Series(closes, index=pd.DatetimeIndex(dates), name=ticker)
    # Tempest returns rows in DESCENDING date order — sort ascending so log()
    # diff returns sensible per-day returns.
    s = s.sort_index()
    s = _adjust_for_splits(s)
    return s


def _slice(s: pd.Series, start: str, end: str) -> pd.Series:
    if s.empty:
        return s
    return s.loc[(s.index >= pd.Timestamp(start)) & (s.index < pd.Timestamp(end))]


def fetch_close(code: str, start: str, end: str) -> pd.Series:
    """Daily close prices for [start, end). Replaces ``yf.download(...)["Close"]``."""
    return _slice(_load_close(code), start, end)


def fetch_returns(code4: str, start: str, end: str) -> pd.Series:
    """Daily log returns over [start, end). Same shape as the old yfinance version."""
    px = fetch_close(code4, start, end)
    if px.empty:
        return pd.Series(dtype=float, name=code4)
    r = np.log(px).diff().dropna()
    r.name = code4
    return r


def fetch_benchmark(ticker: str, start: str, end: str) -> pd.Series:
    """Benchmark log returns. ``ticker`` is the bare ETF code (e.g. ``"1306"``);
    ``"1306.T"`` is also accepted for back-compat with yfinance call sites."""
    px = fetch_close(ticker, start, end)
    if px.empty:
        return pd.Series(dtype=float, name=ticker)
    r = np.log(px).diff().dropna()
    r.name = ticker
    return r


def fetch_prices_df(code: str, start: str, end: str) -> pd.DataFrame:
    """yfinance-shaped frame with a ``Close`` column. Used by the agent's
    5-day move check, which reads ``df["Close"]`` directly."""
    px = fetch_close(code, start, end)
    if px.empty:
        return pd.DataFrame(columns=["Close"])
    return pd.DataFrame({"Close": px})
