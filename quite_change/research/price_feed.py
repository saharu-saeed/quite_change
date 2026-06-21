# -*- coding: utf-8 -*-
"""Authentic, robust daily-close retrieval for TSE tickers.

Source priority (reachability order, confirmed 2026-06):
  1. J-Quants (official TSE OHLC, split-adjusted) — used ONLY if a token is provided
     via environment variables (never read from a committed .env file):
        JQUANTS_ID_TOKEN            (direct id token), OR
        JQUANTS_REFRESH_TOKEN       (exchanged for an id token), OR
        JQUANTS_MAILADDRESS + JQUANTS_PASSWORD  (full auth flow)
     Best for backtests: the free tier serves delayed data, which is fine for old
     dates (e.g. May 2025) but not for very recent ones.
  2. Yahoo Finance v8 JSON ({code}.T) — no auth, returns split-adjusted `adjclose`.
  3. Stooq daily CSV ({code}.jp) — no auth, best-effort (often behind a JS anti-bot
     challenge; kept as a last resort).

Hard rule: if EVERY source fails after retries, the caller returns stock_dir="pending".
Never guess or estimate a price/direction.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# ── Japan trading calendar ─────────────────────────────────────────────────
JP_HOLIDAYS = {
    "2024-01-01", "2024-01-08", "2024-02-11", "2024-02-12", "2024-02-23", "2024-03-20",
    "2024-04-29", "2024-05-03", "2024-05-04", "2024-05-05", "2024-05-06", "2024-07-15",
    "2024-08-11", "2024-08-12", "2024-09-16", "2024-09-22", "2024-09-23", "2024-10-14",
    "2024-11-03", "2024-11-04", "2024-11-05", "2024-11-23", "2025-01-01", "2025-01-13",
    "2025-02-11", "2025-02-23", "2025-02-24", "2025-03-20", "2025-04-29", "2025-05-03",
    "2025-05-04", "2025-05-05", "2025-05-06", "2025-07-21", "2025-08-11", "2025-09-15",
    "2025-09-23", "2025-10-13", "2025-11-03", "2025-11-23", "2025-11-24", "2026-01-01",
    "2026-01-12", "2026-02-11", "2026-02-23", "2026-03-20", "2026-04-29", "2026-05-03",
    "2026-05-04", "2026-05-05", "2026-05-06",
    # TSE year-end/new-year closures
    "2024-12-31", "2025-12-31", "2026-12-31",
}


def is_trading_day(d: datetime) -> bool:
    return d.weekday() < 5 and d.strftime("%Y-%m-%d") not in JP_HOLIDAYS


def add_trading_days(d: datetime, n: int) -> datetime:
    current = d
    for _ in range(n):
        current += timedelta(days=1)
        while not is_trading_day(current):
            current += timedelta(days=1)
    return current


# ── retry helper ───────────────────────────────────────────────────────────
def _http_get(url: str, headers: dict | None = None, timeout: int = 20,
              tries: int = 3, backoff: float = 1.5) -> bytes:
    """GET with retry + exponential backoff. Raises on final failure."""
    last_err: Exception | None = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001 - intentionally broad: any net error → retry
            last_err = e
            if attempt < tries - 1:
                time.sleep(backoff ** (attempt + 1))
    raise RuntimeError(f"GET failed after {tries} tries: {type(last_err).__name__}: {last_err}")


def _http_post_json(url: str, payload: dict, timeout: int = 20,
                    tries: int = 3, backoff: float = 1.5) -> dict:
    body = json.dumps(payload).encode()
    last_err: Exception | None = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < tries - 1:
                time.sleep(backoff ** (attempt + 1))
    raise RuntimeError(f"POST failed after {tries} tries: {type(last_err).__name__}: {last_err}")


# ── Source 0: Tempest (primary — official J-Quants daily, no freshness lag) ──
from pathlib import Path as _Path
def _load_tempest_env():
    for p in [_Path(__file__).parent.parent.parent / ".env", _Path.cwd() / ".env"]:
        if p.exists():
            env = {}
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
            return env.get("TEMPEST_API_URL", "").rstrip("/"), env.get("TEMPEST_API_KEY", "")
    return "", ""
_TEMPEST_BASE, _TEMPEST_KEY = _load_tempest_env()

def fetch_tempest(code: str, start: datetime, end: datetime) -> dict[str, float]:
    """Return {date: close} from the Tempest API (J-Quants-sourced). Raises if unavailable."""
    if not (_TEMPEST_BASE and _TEMPEST_KEY):
        raise RuntimeError("Tempest credentials not available")
    url = (f"{_TEMPEST_BASE}/companies/{code}/prices"
           f"?from={start.strftime('%Y-%m-%d')}&to={end.strftime('%Y-%m-%d')}&limit=200")
    raw = _http_get(url, headers={"Authorization": f"Bearer {_TEMPEST_KEY}", "User-Agent": "Mozilla/5.0"})
    rows = json.loads(raw).get("data", [])
    prices: dict[str, float] = {}
    for r in rows:
        if r.get("close") is None:
            continue
        prices[r["date"]] = round(float(r["close"]), 2)
    if not prices:
        raise RuntimeError("Tempest returned no price rows")
    return prices


# ── Source 1: J-Quants ─────────────────────────────────────────────────────
JQ_BASE = "https://api.jquants.com/v1"


def _jquants_id_token() -> str | None:
    """Resolve a J-Quants id token from environment, or None if unavailable."""
    tok = os.environ.get("JQUANTS_ID_TOKEN")
    if tok:
        return tok

    refresh = os.environ.get("JQUANTS_REFRESH_TOKEN")
    if not refresh:
        mail = os.environ.get("JQUANTS_MAILADDRESS")
        pw = os.environ.get("JQUANTS_PASSWORD")
        if mail and pw:
            try:
                r = _http_post_json(f"{JQ_BASE}/token/auth_user",
                                    {"mailaddress": mail, "password": pw})
                refresh = r.get("refreshToken")
            except Exception:
                return None
    if not refresh:
        return None

    try:
        url = f"{JQ_BASE}/token/auth_refresh?refreshtoken={urllib.parse.quote(refresh)}"
        # auth_refresh is a POST with empty body
        r = _http_post_json(url, {})
        return r.get("idToken")
    except Exception:
        return None


def fetch_jquants(code: str, start: datetime, end: datetime) -> dict[str, float]:
    """Return {date: split-adjusted close}. Raises if token missing or call fails."""
    token = _jquants_id_token()
    if not token:
        raise RuntimeError("J-Quants token not available (set JQUANTS_* env vars)")

    # J-Quants wants a 4 or 5 digit code; pass through as given.
    url = (f"{JQ_BASE}/prices/daily_quotes?code={code}"
           f"&from={start.strftime('%Y-%m-%d')}&to={end.strftime('%Y-%m-%d')}")
    raw = _http_get(url, headers={"Authorization": f"Bearer {token}",
                                  "User-Agent": "Mozilla/5.0"})
    data = json.loads(raw)
    quotes = data.get("daily_quotes", [])
    prices: dict[str, float] = {}
    for q in quotes:
        # AdjustmentClose is split-adjusted; fall back to Close.
        close = q.get("AdjustmentClose")
        if close is None:
            close = q.get("Close")
        if close is None:
            continue
        prices[q["Date"]] = round(float(close), 2)
    if not prices:
        raise RuntimeError("J-Quants returned no rows")
    return prices


# ── Source 2: Yahoo Finance v8 ─────────────────────────────────────────────
def fetch_yahoo(code: str, start: datetime, end: datetime) -> dict[str, float]:
    """Return {date(JST): split-adjusted close}. Raises on failure."""
    period1 = int(start.replace(tzinfo=timezone.utc).timestamp())
    period2 = int((end + timedelta(days=1)).replace(tzinfo=timezone.utc).timestamp())
    url = (f"https://query2.finance.yahoo.com/v8/finance/chart/{code}.T"
           f"?period1={period1}&period2={period2}&interval=1d")
    raw = _http_get(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(raw)
    result = data.get("chart", {}).get("result")
    if not result:
        raise RuntimeError("Yahoo returned no result block")
    block = result[0]
    timestamps = block.get("timestamp", [])
    indicators = block.get("indicators", {})
    adj = indicators.get("adjclose", [])
    if adj and adj[0].get("adjclose"):
        closes = adj[0]["adjclose"]
    else:
        q = indicators.get("quote", [])
        closes = q[0].get("close", []) if q else []
    prices: dict[str, float] = {}
    for ts, cl in zip(timestamps, closes):
        if cl is None:
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=9)  # JST
        prices[dt.strftime("%Y-%m-%d")] = round(float(cl), 2)
    if not prices:
        raise RuntimeError("Yahoo returned no usable closes")
    return prices


# ── Source 3: Stooq (best-effort) ──────────────────────────────────────────
def fetch_stooq(code: str, start: datetime, end: datetime) -> dict[str, float]:
    """Return {date: close}. Best-effort: Stooq often serves a JS challenge."""
    url = (f"https://stooq.com/q/d/l/?s={code}.jp"
           f"&d1={start.strftime('%Y%m%d')}&d2={end.strftime('%Y%m%d')}&i=d")
    raw = _http_get(url, headers={"User-Agent": "Mozilla/5.0"})
    text = raw.decode("utf-8", "replace")
    if not text.lstrip().lower().startswith("date"):
        raise RuntimeError("Stooq did not return CSV (likely JS anti-bot challenge)")
    prices: dict[str, float] = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            prices[row["Date"]] = round(float(row["Close"]), 2)
        except (KeyError, ValueError):
            continue
    if not prices:
        raise RuntimeError("Stooq CSV had no rows")
    return prices


# ── Unified multi-source fetch ─────────────────────────────────────────────
SOURCES = [
    ("tempest", fetch_tempest),   # primary: official J-Quants daily via internal API, no lag
    ("jquants", fetch_jquants),
    ("yahoo", fetch_yahoo),
    ("stooq", fetch_stooq),
]


def fetch_prices_multi(code: str, start: datetime, end: datetime,
                       verbose: bool = True) -> tuple[dict[str, float], str]:
    """Try each source in priority order. Return (prices, source_name).

    Returns ({}, "none") if every source fails.
    """
    errors = []
    for name, fn in SOURCES:
        try:
            prices = fn(code, start, end)
            if prices:
                if verbose:
                    print(f"  [{code}] price_source = {name} ({len(prices)} days)", file=sys.stderr)
                return prices, name
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
            if verbose:
                print(f"  [{code}] {name} failed: {e}", file=sys.stderr)
    if verbose:
        print(f"  [{code}] ALL SOURCES FAILED -> pending", file=sys.stderr)
    return {}, "none"


def compute_p0_p1(code: str, announce_date: datetime, trading_days: int = 10,
                  flat_pct: float = 0.0, verbose: bool = True) -> dict:
    """Pull the daily range once, pick P0 (announce close) and P1 (+N trading days).

    Output contract:
      p0, p0_date, p1, p1_date, pct_change, stock_dir, price_source
    stock_dir is "pending" if data is unavailable — never guessed.
    """
    # Pull a generous window once; pick exact trading days from what's returned.
    start = announce_date - timedelta(days=7)
    end = announce_date + timedelta(days=28)
    prices, source = fetch_prices_multi(code, start, end, verbose=verbose)

    result = {
        "ticker": code,
        "announce_date": announce_date.strftime("%Y-%m-%d"),
        "p0": None, "p0_date": None,
        "p1": None, "p1_date": None,
        "pct_change": None,
        "stock_dir": "pending",
        "price_source": source,
    }
    if not prices:
        return result

    sorted_days = sorted(prices)

    # P0 = the announce-date close, or the last trading day on/before it.
    p0_target = announce_date.strftime("%Y-%m-%d")
    p0_date = p0_target if p0_target in prices else None
    if p0_date is None:
        prior = [d for d in sorted_days if d <= p0_target]
        p0_date = prior[-1] if prior else None

    if p0_date is None:
        return result  # cannot anchor P0 -> stays pending

    # P1 = 10 trading days after the P0 date; snap to nearest available on/after.
    p1_target = add_trading_days(datetime.strptime(p0_date, "%Y-%m-%d"), trading_days)
    p1_target_str = p1_target.strftime("%Y-%m-%d")
    p1_date = p1_target_str if p1_target_str in prices else None
    if p1_date is None:
        after = [d for d in sorted_days if d >= p1_target_str]
        p1_date = after[0] if after else None

    if p1_date is None:
        return result  # window not fully available yet -> stays pending

    p0 = prices[p0_date]
    p1 = prices[p1_date]
    pct = (p1 - p0) / p0 * 100.0
    if abs(pct) <= flat_pct:
        direction = "flat"
    else:
        direction = "up" if pct > 0 else "down"

    result.update({
        "p0": p0, "p0_date": p0_date,
        "p1": p1, "p1_date": p1_date,
        "pct_change": round(pct, 2),
        "stock_dir": direction,
        "price_source": source,
    })
    return result
