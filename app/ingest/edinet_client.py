"""Minimal EDINET v2 API client. Lists documents for a date and downloads a filing zip.

Docs: https://disclosure2.edinet-fsa.go.jp/
We only use endpoints that are safe to call at low rate with a subscription key.
"""
from __future__ import annotations
import os
from pathlib import Path
import requests

EDINET_BASE = "https://api.edinet-fsa.go.jp/api/v2"


def _headers() -> dict[str, str]:
    return {"User-Agent": "tempest-ai-research/0.1 (research@example.com)"}


def list_documents(date_yyyy_mm_dd: str) -> list[dict]:
    """List all filings submitted on the given date."""
    key = os.environ.get("EDINET_API_KEY", "")
    if not key:
        raise RuntimeError("EDINET_API_KEY not set")
    r = requests.get(
        f"{EDINET_BASE}/documents.json",
        params={"date": date_yyyy_mm_dd, "type": 2, "Subscription-Key": key},
        headers=_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("results", [])


def download(doc_id: str, out_dir: Path, kind: int = 1) -> Path:
    """Download a filing. kind=1 → XBRL zip, kind=5 → CSV."""
    key = os.environ.get("EDINET_API_KEY", "")
    if not key:
        raise RuntimeError("EDINET_API_KEY not set")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_id}.zip"
    if out_path.exists():
        return out_path
    r = requests.get(
        f"{EDINET_BASE}/documents/{doc_id}",
        params={"type": kind, "Subscription-Key": key},
        headers=_headers(),
        timeout=60,
    )
    r.raise_for_status()
    out_path.write_bytes(r.content)
    return out_path


def find_filing_by_code(date_yyyy_mm_dd: str, code4: str, doc_type_codes: tuple[str, ...] = ("120", "140", "160")) -> dict | None:
    """Find the first filing on `date` for ticker `code4`.

    doc_type_codes: 120=有報, 140=四半期, 160=半期. Default covers quarterly + annual.
    """
    code5 = code4 + "0"
    for row in list_documents(date_yyyy_mm_dd):
        if row.get("secCode") == code5 and row.get("docTypeCode") in doc_type_codes:
            return row
    return None
