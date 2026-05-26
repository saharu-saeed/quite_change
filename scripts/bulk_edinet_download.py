"""Bulk EDINET download — scan filings from 2020-01-01 to today and download
documents for the top N most-active companies (by filing count) that we
don't already have locally.

Usage:
    python scripts/bulk_edinet_download.py --target 100 --start 2020-01-01

Steps:
  1. Scan EDINET documents.json for each business day in the range.
  2. Collect all 4-digit secCodes that appear in doc types 120/140/160.
  3. Rank by filing count; pick the top --target codes not already downloaded.
  4. Download their filings into data/edinet/<code>/.

This is idempotent — existing ZIPs are skipped.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EDINET_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"
TARGET_DOC_TYPES = frozenset({"120", "140", "160"})
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 120
DELAY = 0.5  # seconds between API calls


def _api_key() -> str:
    key = os.environ.get("EDINET_API_KEY", "").strip()
    if not key:
        raise RuntimeError("EDINET_API_KEY not set in environment / .env")
    return key


def _iter_business_days(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def _already_downloaded() -> set[str]:
    """Return 4-digit codes that already have at least 2 ZIPs in data/edinet/."""
    codes: set[str] = set()
    edn = DATA_DIR / "edinet"
    if not edn.is_dir():
        return codes
    for sub in edn.iterdir():
        if sub.is_dir() and len(sub.name) == 4 and sub.name.isdigit():
            zips = list(sub.glob("*.zip"))
            if len(zips) >= 2:
                codes.add(sub.name)
    return codes


def scan_filing_counts(start: date, end: date, session: requests.Session, api_key: str) -> dict[str, int]:
    """Scan EDINET for all business days and return filing count per sec code."""
    counts: dict[str, int] = defaultdict(int)
    days = list(_iter_business_days(start, end))
    log.info("Scanning %d business days (%s → %s) …", len(days), start, end)
    for i, d in enumerate(days):
        if i % 50 == 0:
            log.info("  day %d/%d (%s) — unique codes so far: %d", i, len(days), d, len(counts))
        time.sleep(DELAY)
        url = f"{EDINET_API_BASE}/documents.json"
        params = {"date": d.isoformat(), "type": "2", "Subscription-Key": api_key}
        try:
            r = session.get(url, params=params, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        except requests.RequestException as e:
            log.warning("documents.json %s failed: %s", d, e)
            continue
        if r.status_code != 200:
            continue
        try:
            results = r.json().get("results") or []
        except ValueError:
            continue
        for doc in results:
            sec = (doc.get("secCode") or "").strip()
            dtype = str(doc.get("docTypeCode") or "")
            if dtype in TARGET_DOC_TYPES and len(sec) == 5 and sec[:4].isdigit():
                counts[sec[:4]] += 1
    return dict(counts)


def download_for_codes(
    codes: list[str], start: date, end: date,
    session: requests.Session, api_key: str,
) -> dict[str, int]:
    """Download filings for selected codes. Returns {code: n_downloaded}."""
    sec5_map = {f"{c}0": c for c in codes}
    fetched: dict[str, int] = defaultdict(int)

    days = list(_iter_business_days(start, end))
    log.info("Downloading filings for %d codes over %d days …", len(codes), len(days))
    for i, d in enumerate(days):
        if i % 100 == 0:
            log.info("  fetch day %d/%d (%s)", i, len(days), d)
        time.sleep(DELAY)
        url = f"{EDINET_API_BASE}/documents.json"
        params = {"date": d.isoformat(), "type": "2", "Subscription-Key": api_key}
        try:
            r = session.get(url, params=params, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        except requests.RequestException as e:
            log.warning("list %s failed: %s", d, e)
            continue
        if r.status_code != 200:
            continue
        try:
            results = r.json().get("results") or []
        except ValueError:
            continue

        for doc in results:
            sec = (doc.get("secCode") or "").strip()
            if sec not in sec5_map:
                continue
            dtype = str(doc.get("docTypeCode") or "")
            if dtype not in TARGET_DOC_TYPES:
                continue
            doc_id = (doc.get("docID") or "").strip()
            if not doc_id:
                continue
            code = sec5_map[sec]
            dest = DATA_DIR / "edinet" / code / f"{d.isoformat()}_{dtype}_{doc_id}.zip"
            if dest.exists() and dest.stat().st_size > 0:
                continue
            time.sleep(DELAY)
            dl_url = f"{EDINET_API_BASE}/documents/{doc_id}"
            dl_params = {"type": "1", "Subscription-Key": api_key}
            try:
                dl = session.get(dl_url, params=dl_params,
                                 timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), stream=True)
            except requests.RequestException as e:
                log.warning("download %s failed: %s", doc_id, e)
                continue
            if dl.status_code != 200:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".part")
            try:
                with open(tmp, "wb") as f:
                    for chunk in dl.iter_content(65536):
                        if chunk:
                            f.write(chunk)
                if tmp.stat().st_size == 0:
                    tmp.unlink(missing_ok=True)
                    continue
                tmp.replace(dest)
                fetched[code] += 1
            except OSError as e:
                log.warning("write %s failed: %s", dest, e)
                tmp.unlink(missing_ok=True)

    return dict(fetched)


def main() -> None:
    ap = argparse.ArgumentParser(description="Bulk EDINET filing download")
    ap.add_argument("--target", type=int, default=100,
                    help="Total companies to have after download (default: 100)")
    ap.add_argument("--start", default="2020-01-01",
                    help="Start date for scan (default: 2020-01-01)")
    ap.add_argument("--end", default=date.today().isoformat(),
                    help="End date for scan (default: today)")
    ap.add_argument("--scan-cache", default="outputs/edinet_scan_cache.json",
                    help="Cache file for filing-count scan results (skip re-scan if exists)")
    args = ap.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    target = args.target
    scan_cache = ROOT / args.scan_cache

    api_key = _api_key()
    session = requests.Session()

    # Step 1: get or load filing counts
    if scan_cache.exists():
        log.info("Loading scan cache from %s", scan_cache)
        counts = json.loads(scan_cache.read_text(encoding="utf-8"))
    else:
        counts = scan_filing_counts(start, end, session, api_key)
        scan_cache.parent.mkdir(parents=True, exist_ok=True)
        scan_cache.write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Saved scan cache → %s (%d codes)", scan_cache, len(counts))

    # Step 2: pick top-N not already downloaded
    already = _already_downloaded()
    log.info("Already have %d codes with ≥2 ZIPs locally.", len(already))
    new_needed = max(0, target - len(already))
    log.info("Need %d more codes to reach target=%d.", new_needed, target)

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    to_fetch = [code for code, _ in ranked if code not in already][:new_needed]
    log.info("Will download filings for %d codes: %s", len(to_fetch), to_fetch[:20])

    if not to_fetch:
        log.info("Already at or above target. Nothing to download.")
        return

    # Step 3: download
    fetched = download_for_codes(to_fetch, start, end, session, api_key)
    total_zips = sum(fetched.values())
    log.info("Done. Downloaded %d ZIPs across %d companies.", total_zips, len(fetched))
    for code, n in sorted(fetched.items(), key=lambda kv: -kv[1])[:20]:
        log.info("  %s: %d ZIPs", code, n)


if __name__ == "__main__":
    main()
