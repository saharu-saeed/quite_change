"""Tests for the EDINET fetch helper (Correction 4).

All tests use mocked HTTP — no live API calls. Covers:
  * success path (one target filing fetched to disk)
  * non-target doc types are filtered out (130/150/170 amendments)
  * non-target secCodes are filtered out
  * network failures on list calls are survived
  * network failures on downloads are counted as errors, not crashes
  * existing files are skipped (idempotence)
  * missing API key raises before any network traffic
  * API key never appears in log output
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.ingest import edinet_fetcher


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _mk_list_response(results: list[dict]) -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"results": results}
    return r


def _mk_download_response(body: bytes, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.iter_content.return_value = [body] if body else []
    return r


def _session_returning(responses: list[MagicMock]) -> MagicMock:
    """Return a fake Session whose .get() yields the given responses in order."""
    it = iter(responses)
    sess = MagicMock(spec=requests.Session)
    sess.get.side_effect = lambda *a, **kw: next(it)
    return sess


@pytest.fixture(autouse=True)
def _api_key_env(monkeypatch):
    monkeypatch.setenv("EDINET_API_KEY", "test-key-xyz")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(edinet_fetcher.time, "sleep", lambda *_: None)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------
def test_fetches_target_filing_and_writes_zip(tmp_path: Path):
    list_resp = _mk_list_response([
        {"secCode": "72010", "docTypeCode": "120", "docID": "S100AAAA"},
    ])
    dl_resp = _mk_download_response(b"PK\x03\x04fakezip")
    session = _session_returning([list_resp, dl_resp])

    stats = edinet_fetcher.fetch_codes(
        ["7201"], date(2024, 6, 3), date(2024, 6, 3), tmp_path, session=session,
    )

    assert stats["7201"]["fetched"] == 1
    assert stats["7201"]["errors"] == 0
    zips = list((tmp_path / "edinet" / "7201").glob("*.zip"))
    assert len(zips) == 1
    assert zips[0].read_bytes() == b"PK\x03\x04fakezip"
    # Filename encodes date + doctype + docID so loader can discover without API.
    assert "2024-06-03" in zips[0].name
    assert "120" in zips[0].name
    assert "S100AAAA" in zips[0].name


def test_only_target_doc_types_are_downloaded(tmp_path: Path):
    """Amendments (130) and unrelated types (030) must be filtered out
    BEFORE we call the download endpoint — otherwise we waste requests."""
    list_resp = _mk_list_response([
        {"secCode": "72010", "docTypeCode": "130", "docID": "AMEND"},   # skip
        {"secCode": "72010", "docTypeCode": "030", "docID": "OTHER"},   # skip
        {"secCode": "72010", "docTypeCode": "160", "docID": "S100GOOD"},  # keep
    ])
    dl_resp = _mk_download_response(b"zip")
    session = _session_returning([list_resp, dl_resp])

    stats = edinet_fetcher.fetch_codes(
        ["7201"], date(2024, 6, 3), date(2024, 6, 3), tmp_path, session=session,
    )

    assert stats["7201"]["fetched"] == 1
    # Exactly two .get calls: one list, one download. Not four.
    assert session.get.call_count == 2


def test_other_companies_in_same_day_are_ignored(tmp_path: Path):
    """The list endpoint returns ALL issuers for the day — we must filter to
    our target secCodes only."""
    list_resp = _mk_list_response([
        {"secCode": "99990", "docTypeCode": "120", "docID": "OTHER"},
        {"secCode": "72010", "docTypeCode": "120", "docID": "MINE"},
    ])
    dl_resp = _mk_download_response(b"zip")
    session = _session_returning([list_resp, dl_resp])

    stats = edinet_fetcher.fetch_codes(
        ["7201"], date(2024, 6, 3), date(2024, 6, 3), tmp_path, session=session,
    )

    assert stats["7201"]["fetched"] == 1
    assert session.get.call_count == 2  # one list, one download


# ---------------------------------------------------------------------------
# Error handling — batch must survive
# ---------------------------------------------------------------------------
def test_list_endpoint_failure_is_logged_and_day_is_skipped(tmp_path: Path, caplog):
    """A 500 from documents.json on one day must not crash the batch."""
    fail = MagicMock(status_code=500)
    ok_list = _mk_list_response([
        {"secCode": "72010", "docTypeCode": "120", "docID": "S100"},
    ])
    dl = _mk_download_response(b"zip")
    session = _session_returning([fail, ok_list, dl])

    with caplog.at_level(logging.WARNING):
        stats = edinet_fetcher.fetch_codes(
            ["7201"], date(2024, 6, 3), date(2024, 6, 4), tmp_path, session=session,
        )

    assert stats["7201"]["fetched"] == 1
    assert any("HTTP 500" in r.message for r in caplog.records)


def test_network_exception_on_list_is_swallowed(tmp_path: Path):
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError("boom")

    stats = edinet_fetcher.fetch_codes(
        ["7201"], date(2024, 6, 3), date(2024, 6, 3), tmp_path, session=session,
    )

    assert stats["7201"]["fetched"] == 0
    assert stats["7201"]["errors"] == 0   # nothing attempted to download


def test_download_failure_counts_as_error_not_crash(tmp_path: Path):
    list_resp = _mk_list_response([
        {"secCode": "72010", "docTypeCode": "120", "docID": "S100"},
    ])
    dl_fail = MagicMock(status_code=404)
    dl_fail.iter_content.return_value = []
    session = _session_returning([list_resp, dl_fail])

    stats = edinet_fetcher.fetch_codes(
        ["7201"], date(2024, 6, 3), date(2024, 6, 3), tmp_path, session=session,
    )

    assert stats["7201"]["fetched"] == 0
    assert stats["7201"]["errors"] == 1
    # No corrupt zip left behind.
    assert not any((tmp_path / "edinet" / "7201").glob("*.zip"))


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------
def test_existing_file_is_skipped(tmp_path: Path):
    """Re-running the fetcher must not re-download what is already on disk."""
    out = tmp_path / "edinet" / "7201"
    out.mkdir(parents=True)
    existing = out / "2024-06-03_120_S100AAAA.zip"
    existing.write_bytes(b"already here")

    list_resp = _mk_list_response([
        {"secCode": "72010", "docTypeCode": "120", "docID": "S100AAAA"},
    ])
    session = _session_returning([list_resp])  # no download call expected

    stats = edinet_fetcher.fetch_codes(
        ["7201"], date(2024, 6, 3), date(2024, 6, 3), tmp_path, session=session,
    )

    assert stats["7201"]["skipped_existing"] == 1
    assert stats["7201"]["fetched"] == 0
    assert existing.read_bytes() == b"already here"
    assert session.get.call_count == 1


# ---------------------------------------------------------------------------
# Weekends
# ---------------------------------------------------------------------------
def test_weekends_are_not_scanned(tmp_path: Path):
    """EDINET does not post on Saturdays/Sundays — scanning them wastes
    half the request budget."""
    # 2024-06-01 is a Saturday; 2024-06-02 Sunday; 2024-06-03 Monday.
    list_resp = _mk_list_response([])
    session = _session_returning([list_resp])  # only Monday should hit

    edinet_fetcher.fetch_codes(
        ["7201"], date(2024, 6, 1), date(2024, 6, 3), tmp_path, session=session,
    )

    assert session.get.call_count == 1


# ---------------------------------------------------------------------------
# Auth — missing key and log hygiene
# ---------------------------------------------------------------------------
def test_missing_api_key_raises_before_network(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("EDINET_API_KEY", raising=False)
    session = MagicMock(spec=requests.Session)

    with pytest.raises(RuntimeError, match="EDINET_API_KEY"):
        edinet_fetcher.fetch_codes(
            ["7201"], date(2024, 6, 3), date(2024, 6, 3), tmp_path, session=session,
        )
    session.get.assert_not_called()


def test_api_key_never_appears_in_logs(tmp_path: Path, caplog, monkeypatch):
    """The key gets passed as a query parameter. If it ever ends up in a log
    message (e.g. via a naive repr of the request URL), we have leaked it."""
    secret = "super-secret-key-abc123"
    monkeypatch.setenv("EDINET_API_KEY", secret)

    # Mix of successes and failures to exercise every logging branch.
    fail = MagicMock(status_code=500)
    list_resp = _mk_list_response([
        {"secCode": "72010", "docTypeCode": "120", "docID": "S100"},
    ])
    dl_fail = MagicMock(status_code=404)
    dl_fail.iter_content.return_value = []
    session = _session_returning([fail, list_resp, dl_fail])

    with caplog.at_level(logging.DEBUG):
        edinet_fetcher.fetch_codes(
            ["7201"], date(2024, 6, 3), date(2024, 6, 4), tmp_path, session=session,
        )

    for record in caplog.records:
        assert secret not in record.getMessage(), (
            f"API key leaked into log record: {record.getMessage()!r}"
        )
