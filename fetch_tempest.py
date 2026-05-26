"""Pull TOPIX 100 ∪ 情報･通信業 from the TempestAI Finance API into data/tempest/.

USAGE
-----
    python fetch_tempest.py                # incremental (skip files <24h old)
    python fetch_tempest.py --force        # re-fetch everything
    python fetch_tempest.py --limit 5      # only first 5 tickers (smoke test)
    python fetch_tempest.py --tickers 7203,9432,4307   # specific tickers only
    python fetch_tempest.py --max-age-hours 168        # weekly refresh window

LAYOUT
------
    data/tempest/
        _meta/
            universe.json      # ticker list + last resolution time
            last_run.json      # per-run summary
        {ticker}/
            company.json
            snapshot.json
            prices.json
            financials.json              # TOPIX 100 only — empty otherwise
            financials_quarterly.json    # TOPIX 100 only
            financials_line_items.json   # TOPIX 100 only
            segments.json                # TOPIX 100 only
            indicators.json              # TOPIX 100 only
            indicators_quarterly.json    # TOPIX 100 only
            disclosures.json

The agent / UI should READ from these files instead of calling EDINET or
yfinance directly. See app/ingest/tempest_loader.py for the read side.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from dotenv import load_dotenv
load_dotenv()

from app.config import ROOT  # noqa: E402
from app.ingest import tempest_client as tc  # noqa: E402

DATA_DIR = ROOT / "data" / "tempest"
META_DIR = DATA_DIR / "_meta"
RATE_SLEEP = 0.65   # 100 req/min ⇒ 0.6s; +50ms safety margin

# Endpoint plan: (filename, fetch_fn, topix100_only)
# fetch_fn signature: (ticker: str) -> dict
HISTORY_FROM_FY = 2020   # 5 years of fundamentals
HISTORY_FROM_DATE = "2020-01-01"  # 5 years of prices

ENDPOINTS = [
    ("company",                 lambda t: tc.get_company(t),                                            False),
    ("snapshot",                lambda t: tc.get_snapshot(t),                                           False),
    ("prices",                  lambda t: tc.get_prices(t, date_from=HISTORY_FROM_DATE, limit=2000),    False),
    ("disclosures",             lambda t: tc.get_disclosures(t, limit=200),                             False),
    ("financials",              lambda t: tc.get_financials(t, from_fy=HISTORY_FROM_FY),                True),
    ("financials_quarterly",    lambda t: tc.get_financials_quarterly(t, from_fy=HISTORY_FROM_FY),      True),
    ("financials_line_items",   lambda t: tc.get_financials_line_items(t, from_fy=HISTORY_FROM_FY),     True),
    ("segments",                lambda t: tc.get_segments(t, from_fy=HISTORY_FROM_FY),                  True),
    ("indicators",              lambda t: tc.get_indicators(t, from_fy=HISTORY_FROM_FY),                True),
    ("indicators_quarterly",    lambda t: tc.get_indicators_quarterly(t),                               True),
]


def _save_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _is_fresh(path: Path, max_age: timedelta) -> bool:
    if not path.exists():
        return False
    age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    return age < max_age.total_seconds()


def resolve_or_load_universe(force: bool, max_age: timedelta) -> list[dict]:
    universe_path = META_DIR / "universe.json"
    if not force and _is_fresh(universe_path, max_age):
        cached = _load_json(universe_path)
        if cached and "rows" in cached:
            print(f"[universe] using cached: {len(cached['rows'])} tickers", flush=True)
            return cached["rows"]
    print("[universe] resolving TOPIX 100 ∪ 情報･通信業 from API...", flush=True)
    rows = tc.resolve_universe()
    _save_json(universe_path, {
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "topix100_count": sum(1 for r in rows if r.get("is_topix100")),
        "rows": rows,
    })
    print(f"[universe] resolved {len(rows)} tickers "
          f"({sum(1 for r in rows if r.get('is_topix100'))} TOPIX 100)", flush=True)
    return rows


ASR_TEXT_KEEP = 3   # how many most-recent annual reports to pull text bodies for


def _fetch_asr_texts(ticker: str, out_dir: Path, *, force: bool,
                     max_age: timedelta) -> dict[str, str]:
    """Pull text bodies for the latest N annual reports (doc_type_code=120).

    Both agents need the MD&A narrative + business description; those live
    inside the per-disclosure ``texts`` array. This is only worth doing for
    TOPIX 100 (the only tier where Tempest has parsed text — see docs §5).

    Files are saved at ``data/tempest/{ticker}/asr_texts/{doc_id}.json`` so
    the loader can map doc_id → text directly without re-hitting the API.
    """
    status: dict[str, str] = {}
    disc_path = out_dir / "disclosures.json"
    disc = _load_json(disc_path)
    if not disc or not disc.get("data"):
        return {"_asr_texts": "no_disclosures"}

    asrs = [r for r in disc["data"] if r.get("doc_type_code") == "120"]
    asrs.sort(key=lambda r: r.get("submit_datetime") or "", reverse=True)
    asrs = asrs[:ASR_TEXT_KEEP]

    text_dir = out_dir / "asr_texts"
    for asr in asrs:
        doc_id = asr["doc_id"]
        path = text_dir / f"{doc_id}.json"
        if not force and _is_fresh(path, max_age):
            status[f"asr_text:{doc_id}"] = "fresh_cached"
            continue
        try:
            payload = tc.get_disclosure(doc_id)
            _save_json(path, payload)
            status[f"asr_text:{doc_id}"] = "ok"
        except Exception as e:
            status[f"asr_text:{doc_id}"] = f"error: {e!r}"
        time.sleep(RATE_SLEEP)
    return status


def fetch_ticker(row: dict, *, force: bool, max_age: timedelta) -> dict:
    """Fetch all applicable endpoints for one ticker. Returns per-endpoint status."""
    ticker = row["ticker"]
    is_topix100 = bool(row.get("is_topix100"))
    out_dir = DATA_DIR / ticker
    status: dict[str, str] = {}

    for fname, fetch_fn, topix100_only in ENDPOINTS:
        path = out_dir / f"{fname}.json"
        if topix100_only and not is_topix100:
            status[fname] = "skipped_non_topix100"
            continue
        if not force and _is_fresh(path, max_age):
            status[fname] = "fresh_cached"
            continue
        try:
            payload = fetch_fn(ticker)
            _save_json(path, payload)
            status[fname] = "ok"
        except Exception as e:  # network / 5xx / unexpected schema
            status[fname] = f"error: {e!r}"
        time.sleep(RATE_SLEEP)

    # ASR text bodies — TOPIX 100 only (the only tier with parsed text).
    if is_topix100:
        status.update(_fetch_asr_texts(ticker, out_dir, force=force, max_age=max_age))
    return status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="Re-fetch all endpoints even if recently cached.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process only the first N tickers (for smoke testing).")
    ap.add_argument("--tickers", type=str, default=None,
                    help="Comma-separated tickers to fetch (overrides universe).")
    ap.add_argument("--max-age-hours", type=float, default=24.0,
                    help="Skip files newer than this. Default: 24h.")
    args = ap.parse_args()

    max_age = timedelta(hours=args.max_age_hours)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)

    # Connectivity probe — fail fast with a clear message instead of looping
    # through 700 tickers with the wrong env var set.
    print(f"[health] {tc.health()}", flush=True)

    if args.tickers:
        wanted = [t.strip() for t in args.tickers.split(",") if t.strip()]
        rows = []
        for t in wanted:
            try:
                c = tc.get_company(t)
                # tc.get() returns {} on 404 instead of raising — guard against
                # appending an empty dict that crashes the main fetch loop on
                # `row["ticker"]`. 2026-05-10 fix.
                if not c or not c.get("ticker"):
                    print(f"[universe] {t}: not found in Tempest (404 or empty body)", flush=True)
                    continue
                # When user explicitly names tickers, force-pull ALL endpoints.
                # Tempest has parsed XBRL for far more than just TOPIX 100 —
                # the original topix100-only gate was overcautious. If the
                # ticker doesn't actually have financials/segments, those
                # endpoints will just return empty and the fetch_ticker code
                # handles that gracefully. 2026-05-13 fix.
                c["is_topix100"] = True
                rows.append(c)
            except Exception as e:
                print(f"[universe] could not resolve {t}: {e}", flush=True)
            time.sleep(RATE_SLEEP)
    else:
        rows = resolve_or_load_universe(force=args.force, max_age=max_age)

    if args.limit:
        rows = rows[:args.limit]

    started = datetime.now(timezone.utc)
    summary = {"started_at": started.isoformat(), "tickers": {}}

    total = len(rows)
    print(f"[run] fetching {total} tickers (force={args.force}, "
          f"max_age={args.max_age_hours}h)", flush=True)

    for i, row in enumerate(rows, 1):
        ticker = row["ticker"]
        name = row.get("company_name", "")
        tag = "T100" if row.get("is_topix100") else "IT  "
        print(f"  [{i:4d}/{total}] {tag} {ticker} {name}", flush=True)
        status = fetch_ticker(row, force=args.force, max_age=max_age)
        summary["tickers"][ticker] = status

    finished = datetime.now(timezone.utc)
    summary["finished_at"] = finished.isoformat()
    summary["elapsed_seconds"] = (finished - started).total_seconds()
    _save_json(META_DIR / "last_run.json", summary)

    # Quick aggregate counts
    counts: dict[str, int] = {}
    for st in summary["tickers"].values():
        for v in st.values():
            counts[v] = counts.get(v, 0) + 1
    print(f"[done] elapsed={summary['elapsed_seconds']:.1f}s  results={counts}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
