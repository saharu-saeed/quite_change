"""EDINET API fetcher — downloads ZIPs for a set of securities codes over a
date range into ``data/edinet/<code>/``. Used by Correction 4 to build the
historical template library.

Design notes
------------
* **Auth.** EDINET requires a Subscription-Key. It is read once from the
  ``EDINET_API_KEY`` environment variable and passed as a query parameter.
  The key is NEVER written to logs or the filesystem — only the fact that
  it is present/absent is reported.

* **Traversal.** ``documents.json?date=YYYY-MM-DD&type=2`` returns every
  filing submitted on that day across all issuers. We iterate dates once
  (skipping weekends — EDINET does not accept filings on Sat/Sun) and, for
  each day, scan the returned list for our target ``secCode``s. This means
  ~1250 list calls cover 5 years of history regardless of how many codes
  we are tracking — much cheaper than per-company iteration.

* **Target documents.** docTypeCode 120 (有価証券報告書), 140 (四半期報告書),
  160 (半期報告書). Amendments (130/150/170) are intentionally skipped —
  the original filing is canonical for revenue trajectory extraction.

* **Rate limiting.** A 0.5s sleep between API calls. EDINET has no
  documented hard rate limit for subscribed users, but the FSA's terms of
  use ask for "reasonable" usage; this gives ~2 req/s which is polite.

* **Error handling.** Network errors, non-200 responses, malformed JSON,
  and disk-write failures are all logged and skipped. A single company's
  failures never abort the batch. Partial downloads are written to a
  ``.part`` sidecar and atomically renamed on success, so a crash or
  network drop mid-stream never leaves a truncated ZIP.

* **Idempotence.** Existing non-empty ZIPs at the destination path are
  skipped, so re-running the fetcher only pulls new filings.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import requests
from dotenv import load_dotenv

# Load .env at module import so the fetcher is self-sufficient even when
# invoked as a one-off script that does not import app.config.
load_dotenv()

log = logging.getLogger(__name__)

EDINET_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"

# docTypeCode values we want. Amendments (130/150/170) are deliberately
# excluded — we want the originally-filed revenue snapshot, not restated ones.
TARGET_DOC_TYPE_CODES: frozenset[str] = frozenset({"120", "140", "160"})

DEFAULT_DELAY_SEC = 0.5
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 120


def _api_key() -> str:
    """Return the EDINET API key from env, or raise. Never echoes the value."""
    key = os.environ.get("EDINET_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "EDINET_API_KEY env var is not set. Set it to your EDINET "
            "subscription key (obtain one at https://disclosure2.edinet-fsa.go.jp/)."
        )
    return key


def _sec_code_5digit(code: str) -> str:
    """EDINET stores securities codes as the 4-digit ticker plus a trailing '0'."""
    return f"{code}0"


def _iter_business_days(start: date, end: date) -> Iterable[date]:
    """Yield every Mon–Fri date in [start, end]. Holidays are included
    (EDINET returns empty results for them; cost is one list call)."""
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def _list_documents_for_date(
    d: date, session: requests.Session, api_key: str,
) -> list[dict]:
    """Fetch documents.json for one date. Returns [] on any failure."""
    url = f"{EDINET_API_BASE}/documents.json"
    params = {"date": d.isoformat(), "type": "2", "Subscription-Key": api_key}
    try:
        r = session.get(url, params=params, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    except requests.RequestException as e:
        log.warning("documents.json %s failed: %s", d, e)
        return []
    if r.status_code != 200:
        log.warning("documents.json %s -> HTTP %d", d, r.status_code)
        return []
    try:
        payload = r.json()
    except ValueError:
        log.warning("documents.json %s returned non-JSON", d)
        return []
    return payload.get("results", []) or []


def _download_document(
    doc_id: str, dest: Path, session: requests.Session, api_key: str,
) -> bool:
    """Download the main-body ZIP (type=1) to ``dest``. Atomic write."""
    url = f"{EDINET_API_BASE}/documents/{doc_id}"
    params = {"type": "1", "Subscription-Key": api_key}
    try:
        r = session.get(
            url, params=params,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            stream=True,
        )
    except requests.RequestException as e:
        log.warning("download %s failed: %s", doc_id, e)
        return False
    if r.status_code != 200:
        log.warning("download %s -> HTTP %d", doc_id, r.status_code)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        if tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            log.warning("download %s produced empty body", doc_id)
            return False
        tmp.replace(dest)
    except OSError as e:
        log.warning("write failed for %s: %s", dest, e)
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return False
    return True


def fetch_codes(
    codes: list[str],
    start_date: date,
    end_date: date,
    data_dir: Path,
    *,
    delay_sec: float = DEFAULT_DELAY_SEC,
    session: requests.Session | None = None,
) -> dict[str, dict[str, int]]:
    """Fetch target filings for ``codes`` across [start_date, end_date].

    One pass through dates; for each day we do one list call and filter
    the returned array for any of our target ``secCode``s. This amortises
    list calls across the batch.

    Returns a per-code stats dict:
      ``{"<code>": {"fetched": N, "skipped_existing": M, "errors": K}, ...}``
    plus a top-level ``"_scanned_days": D`` entry.
    """
    api_key = _api_key()
    session = session or requests.Session()
    sec5_to_code = {_sec_code_5digit(c): c for c in codes}

    stats: dict[str, dict[str, int]] = {
        c: {"fetched": 0, "skipped_existing": 0, "errors": 0} for c in codes
    }
    scanned = 0

    for d in _iter_business_days(start_date, end_date):
        scanned += 1
        time.sleep(delay_sec)
        docs = _list_documents_for_date(d, session, api_key)
        for doc in docs:
            sec = doc.get("secCode") or ""
            if sec not in sec5_to_code:
                continue
            doc_type = str(doc.get("docTypeCode") or "")
            if doc_type not in TARGET_DOC_TYPE_CODES:
                continue
            doc_id = doc.get("docID") or ""
            if not doc_id:
                continue
            code = sec5_to_code[sec]
            out_dir = data_dir / "edinet" / code
            dest = out_dir / f"{d.isoformat()}_{doc_type}_{doc_id}.zip"
            if dest.exists() and dest.stat().st_size > 0:
                stats[code]["skipped_existing"] += 1
                continue
            time.sleep(delay_sec)
            if _download_document(doc_id, dest, session, api_key):
                stats[code]["fetched"] += 1
                log.info("%s %s doctype=%s -> %s", code, d, doc_type, dest.name)
            else:
                stats[code]["errors"] += 1

    stats["_scanned_days"] = scanned  # type: ignore[assignment]
    return stats


def ensure_asr_years(
    code: str,
    min_year: int,
    data_dir: Path,
    *,
    max_year: int | None = None,
    delay_sec: float = DEFAULT_DELAY_SEC,
) -> dict:
    """Ensure annual securities reports (docTypeCode=120) are present locally
    for every fiscal year in [min_year, max_year] for one company.

    A Japanese ASR for fiscal-year-ending March YYYY is filed by end of June
    YYYY. We scan YYYY-04-01 .. YYYY-09-30 (covers late filers) for each
    missing year and download the matching filing.

    Returns:
      {
        "code": str,
        "needed_years": [int, ...],
        "missing_years_before": [int, ...],
        "downloaded_years": [int, ...],
        "still_missing_years": [int, ...],
        "scanned_days": int,
      }
    """
    from app.ingest.filing_meta import extract_edinet_filing_meta

    today = date.today()
    if max_year is None:
        # Japanese ASRs for FY ending March YYYY are filed by end of June YYYY.
        # Before July YYYY, that year's ASR likely isn't filed yet — don't waste
        # a search on it.
        max_year = today.year if today.month >= 7 else today.year - 1

    folder = data_dir / "edinet" / code
    folder.mkdir(parents=True, exist_ok=True)

    # Discover which fiscal years (by period_end year) we already have.
    have_years: set[int] = set()
    for z in folder.glob("*.zip"):
        try:
            meta = extract_edinet_filing_meta(z)
        except Exception:
            continue
        if meta is None or meta.filing_type != "edinet_asr":
            continue
        have_years.add(meta.period_end.year)

    needed_years = list(range(min_year, max_year + 1))
    missing_years = [y for y in needed_years if y not in have_years]
    downloaded_years: list[int] = []
    still_missing: list[int] = []
    scanned_days = 0

    if not missing_years:
        return {
            "code": code, "needed_years": needed_years,
            "missing_years_before": [], "downloaded_years": [],
            "still_missing_years": [], "scanned_days": 0,
        }

    api_key = _api_key()
    sec5 = _sec_code_5digit(code)
    session = requests.Session()

    for yr in missing_years:
        # ASRs for fiscal year ending Mar YYYY are filed Apr-Jun YYYY (regulatory
        # deadline = within 3 months). Widen to Sep for late filers / non-March
        # year-ends. Don't search future dates.
        win_start = date(yr, 4, 1)
        win_end = min(date(yr, 9, 30), today)
        if win_start > today:
            still_missing.append(yr)
            continue
        found_doc_id: str | None = None
        found_date: date | None = None
        for d in _iter_business_days(win_start, win_end):
            scanned_days += 1
            time.sleep(delay_sec)
            for doc in _list_documents_for_date(d, session, api_key):
                if (doc.get("secCode") or "") != sec5:
                    continue
                if str(doc.get("docTypeCode") or "") != "120":
                    continue
                found_doc_id = doc.get("docID") or ""
                found_date = d
                break
            if found_doc_id:
                break
        if not found_doc_id or found_date is None:
            still_missing.append(yr)
            log.warning("ASR for %s FY%d not found in EDINET window %s..%s",
                        code, yr, win_start, win_end)
            continue
        dest = folder / f"{found_date.isoformat()}_120_{found_doc_id}.zip"
        time.sleep(delay_sec)
        if _download_document(found_doc_id, dest, session, api_key):
            downloaded_years.append(yr)
            log.info("ASR auto-fetch: %s FY%d -> %s", code, yr, dest.name)
        else:
            still_missing.append(yr)

    return {
        "code": code, "needed_years": needed_years,
        "missing_years_before": missing_years,
        "downloaded_years": downloaded_years,
        "still_missing_years": still_missing,
        "scanned_days": scanned_days,
    }
