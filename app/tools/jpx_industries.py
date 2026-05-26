"""JPX 33業種 industry classification lookup (Correction 4, Option 4a).

Primary industry gate for the Similar Company subagent. EDINET iXBRL does
not carry the TOPIX 33業種 classification — the only Industry-bearing tag
(``jpdei_cor:IndustryCode*DEI``) is a per-filer *industry-specific
accounting regulation* flag that returns ``CTE`` for virtually all
non-financial industrials (see Correction 4 investigation notes). The
canonical mapping is the JPX-published 上場銘柄一覧.

Source file: ``data/jpx/data_j.xls``
Canonical URL (verified 2026-04-20):
    https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls
Updated monthly by JPX; re-fetch when stale.

Columns used: ``コード``, ``銘柄名``, ``33業種コード``, ``33業種区分``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.config import ROOT

log = logging.getLogger(__name__)

JPX_XLS = Path(ROOT) / "data" / "jpx" / "data_j.xls"


@dataclass(frozen=True)
class IndustryRecord:
    code: str           # 4-digit ticker
    name: str           # JPX-registered 銘柄名
    code33: str         # 33業種コード, e.g. "3650"
    label33: str        # 33業種区分, e.g. "電気機器"


@lru_cache(maxsize=1)
def _table() -> dict[str, IndustryRecord]:
    if not JPX_XLS.exists():
        raise FileNotFoundError(
            f"JPX table not found at {JPX_XLS}. Fetch from "
            "https://www.jpx.co.jp/markets/statistics-equities/misc/"
            "tvdivq0000001vg2-att/data_j.xls"
        )
    df = pd.read_excel(JPX_XLS, dtype=str)
    out: dict[str, IndustryRecord] = {}
    for _, row in df.iterrows():
        code = row["コード"]
        code33 = row["33業種コード"]
        # ETFs / REITs have "-" in industry columns; skip them.
        if not code or not code33 or code33 == "-":
            continue
        out[code] = IndustryRecord(
            code=code,
            name=row["銘柄名"],
            code33=code33,
            label33=row["33業種区分"],
        )
    return out


# Manual overrides for tickers missing from the JPX master file (e.g. recent
# listings, post-rename codes, or master file staleness). Each entry must be
# verified against JPX's published industry classification before being added.
_OVERRIDES: dict[str, IndustryRecord] = {
    # NTTデータグループ — 2023 reorganization, not yet in older JPX master snapshots.
    "9613": IndustryRecord(code="9613", name="NTTデータグループ",
                           code33="5250", label33="情報・通信業"),
    # 楽天グループ — JPX classifies under 9050 サービス業 (legacy) but the business
    # is overwhelmingly internet/fintech/mobile, comparable to other 5250 peers.
    # Override so it joins the IT-comparison universe.
    "4755": IndustryRecord(code="4755", name="楽天グループ",
                           code33="5250", label33="情報・通信業"),
}


def lookup(ticker: str) -> IndustryRecord | None:
    """Return JPX 33業種 record for a 4-digit ticker, or None if not listed.

    Not-listed cases include: unlisted subsidiaries, pre-IPO companies,
    and recently delisted issuers. Caller should treat ``None`` as
    "industry code unknown" and fall back to cosine-only gating.
    """
    # Overrides take precedence — used to (a) supply records missing from the
    # JPX master snapshot and (b) re-classify cases where the JPX legacy code
    # doesn't reflect the company's current business (e.g. 楽天 listed under
    # 9050 Services despite being an internet/fintech business).
    if ticker in _OVERRIDES:
        return _OVERRIDES[ticker]
    return _table().get(ticker)
