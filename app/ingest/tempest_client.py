"""TempestAI Finance API client (staging).

Replaces direct EDINET / yfinance fetches for the universe of TOPIX 100
plus 情報･通信業 (sector code 5250). The API exposes 5 years of daily
prices, financials, segments, indicators, and disclosure metadata in a
unified JSON shape.

Docs: docs/api-for-members.md (or the PDF Shunsuke distributes).
Important quirk: sector_33_name uses HALFWIDTH middle dot (U+FF65, '･'),
not the fullwidth '・' a Japanese IME emits by default. The constant
SECTOR_IT below is correct — copy it verbatim.
"""
from __future__ import annotations
import os
from typing import Any, Iterable

import requests

BASE_URL_DEFAULT = (
    "http://tempestai-finance-staging-alb-1031368927."
    "ap-northeast-1.elb.amazonaws.com"
)

SECTOR_IT = "情報･通信業"  # halfwidth ･ (U+FF65) — see module docstring
TOPIX100_TAGS = ("TOPIX Core30", "TOPIX Large70")


def _base_url() -> str:
    return os.environ.get("TEMPEST_API_URL", BASE_URL_DEFAULT).rstrip("/")


def _headers() -> dict[str, str]:
    key = os.environ.get("TEMPEST_API_KEY", "")
    if not key:
        raise RuntimeError("TEMPEST_API_KEY not set in .env")
    return {"Authorization": f"Bearer {key}"}


def get(path: str, **params: Any) -> dict:
    """Low-level GET. Raises on non-2xx (except 404 → returns {})."""
    url = _base_url() + (path if path.startswith("/") else "/" + path)
    # requests handles UTF-8 percent-encoding correctly when params are str.
    r = requests.get(url, params=params, headers=_headers(), timeout=30)
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    # Force UTF-8 — staging sometimes omits charset in Content-Type and
    # requests then defaults to ISO-8859-1, mojibaking Japanese fields.
    r.encoding = "utf-8"
    return r.json()


def list_companies(
    *, sector_33_name: str | None = None, market_code: str | None = None,
    q: str | None = None, limit: int = 200, offset: int = 0,
) -> dict:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if sector_33_name:
        params["sector_33_name"] = sector_33_name
    if market_code:
        params["market_code"] = market_code
    if q:
        params["q"] = q
    return get("/companies", **params)


def list_all_companies(**filters: Any) -> list[dict]:
    """Paginate /companies until exhausted. Filters forwarded to list_companies."""
    out: list[dict] = []
    offset = 0
    page_size = 500
    while True:
        page = list_companies(limit=page_size, offset=offset, **filters)
        rows = page.get("data", [])
        out.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def resolve_universe() -> list[dict]:
    """TOPIX 100 ∪ 情報･通信業, deduplicated by ticker.

    Each row gains a synthetic ``is_topix100`` bool so the driver can
    decide which endpoints are worth calling for that ticker.
    """
    by_ticker: dict[str, dict] = {}

    # All companies — we filter TOPIX 100 client-side via scale_category
    # (the API has no scale_category filter parameter).
    for c in list_all_companies():
        if c.get("scale_category") in TOPIX100_TAGS:
            c["is_topix100"] = True
            by_ticker[c["ticker"]] = c

    # IT sector (情報･通信業)
    for c in list_all_companies(sector_33_name=SECTOR_IT):
        if c["ticker"] in by_ticker:
            continue  # already TOPIX 100, keep that record
        c["is_topix100"] = c.get("scale_category") in TOPIX100_TAGS
        by_ticker[c["ticker"]] = c

    return sorted(by_ticker.values(), key=lambda r: r["ticker"])


# ---------- per-ticker endpoints ----------

def get_company(ticker: str) -> dict:
    return get(f"/companies/{ticker}")


def get_snapshot(ticker: str) -> dict:
    return get(f"/companies/{ticker}/snapshot")


def get_prices(ticker: str, *, date_from: str | None = None,
               date_to: str | None = None, limit: int = 2000) -> dict:
    p: dict[str, Any] = {"limit": limit}
    if date_from:
        p["from"] = date_from
    if date_to:
        p["to"] = date_to
    return get(f"/companies/{ticker}/prices", **p)


def get_financials(ticker: str, *, from_fy: int | None = None,
                   to_fy: int | None = None, source: str | None = None) -> dict:
    p: dict[str, Any] = {}
    if from_fy is not None:
        p["from_fy"] = from_fy
    if to_fy is not None:
        p["to_fy"] = to_fy
    if source:
        p["source"] = source
    return get(f"/companies/{ticker}/financials", **p)


def get_financials_quarterly(ticker: str, *, from_fy: int | None = None,
                             to_fy: int | None = None) -> dict:
    p: dict[str, Any] = {}
    if from_fy is not None:
        p["from_fy"] = from_fy
    if to_fy is not None:
        p["to_fy"] = to_fy
    return get(f"/companies/{ticker}/financials/quarterly", **p)


def get_financials_line_items(ticker: str, *, from_fy: int | None = None,
                              to_fy: int | None = None) -> dict:
    p: dict[str, Any] = {}
    if from_fy is not None:
        p["from_fy"] = from_fy
    if to_fy is not None:
        p["to_fy"] = to_fy
    return get(f"/companies/{ticker}/financials/line-items", **p)


def get_segments(ticker: str, *, from_fy: int | None = None,
                 to_fy: int | None = None) -> dict:
    p: dict[str, Any] = {}
    if from_fy is not None:
        p["from_fy"] = from_fy
    if to_fy is not None:
        p["to_fy"] = to_fy
    return get(f"/companies/{ticker}/segments", **p)


def get_indicators(ticker: str, *, from_fy: int | None = None,
                   to_fy: int | None = None) -> dict:
    p: dict[str, Any] = {}
    if from_fy is not None:
        p["from_fy"] = from_fy
    if to_fy is not None:
        p["to_fy"] = to_fy
    return get(f"/companies/{ticker}/indicators", **p)


def get_indicators_quarterly(ticker: str, *, limit: int = 40) -> dict:
    return get(f"/companies/{ticker}/indicators/quarterly", limit=limit)


def get_disclosures(ticker: str, *, doc_type: str | None = None,
                    limit: int = 200) -> dict:
    p: dict[str, Any] = {"limit": limit}
    if doc_type:
        p["doc_type"] = doc_type
    return get(f"/companies/{ticker}/disclosures", **p)


def get_disclosure(doc_id: str) -> dict:
    return get(f"/disclosures/{doc_id}")


def list_sectors() -> dict:
    return get("/sectors")


def health() -> dict:
    """Unauthenticated. Useful as a connectivity probe before a full run."""
    url = _base_url() + "/health"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.json()
