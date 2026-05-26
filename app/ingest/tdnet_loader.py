"""TDnet 決算短信 loader.

Reads the SharePoint download layout:

    data/<batch>/<batch>/<code>_<name>[_suffix]/
      ├── 決算短信/
      │     ├── YYYYMMDD<...>GENERAL.pdf
      │     └── YYYYMMDD<...>ZIP.zip          ← XBRL inside
      ├── 中計(TD)/  |  中計(企業サイト)/
      └── 中計取得元URL.txt

For each company we collect every quarterly filing, sort by filing date, and emit:
  - prev_text / curr_text         from qualitative.htm of 2nd-latest / latest ZIPs
  - announce_date                 latest filing date
  - revenue_history               list[float] of OrdinaryRevenuesBK | NetSales
                                  per quarter (proxy for segment trajectory;
                                  consumed by similar_company via DTW)
  - segments_prev / segments_curr empty for now (TDnet XBRL rarely carries
                                  structured segment breakdowns; PDF parsing
                                  would be a separate task).
"""
from __future__ import annotations
import logging
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from lxml import etree

from app.ingest.filing_meta import extract_tdnet_filing_meta, find_yoy_pair

log = logging.getLogger(__name__)

# XBRL numeric tags we try, in order of priority. Covers banks, insurance,
# and standard industrial reporters.
REVENUE_TAGS = (
    "OrdinaryRevenuesBK",          # banks
    "OrdinaryRevenuesIN",          # insurance
    "NetSales",                    # industrial
    "Revenue",                     # IFRS
    "OperatingRevenues",           # services
)

QUALITATIVE_FILE_NAMES = ("qualitative.htm", "qualitative.html")


def _skip_toc(text: str) -> str:
    """Skip table-of-contents; return the narrative starting at first content section."""
    markers = [
        "経営成績に関する説明", "当期の経営成績", "業績の概要",
        "経営成績等の概況", "当中間期の経営成績", "当四半期の経営成績",
    ]
    for marker in markers:
        idx = text.find(marker)
        if idx > 200:
            return text[idx:]
    return text[min(1500, len(text) // 4):]


def _strip_html(s: str) -> str:
    # drop <script>...</script>, <style>...</style>, and HTML comments first
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.DOTALL)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;|&#160;", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _parse_filing_date(zip_name: str) -> str | None:
    """Filenames start with YYYYMMDD."""
    m = re.match(r"(\d{4})(\d{2})(\d{2})", zip_name)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _extract_qualitative(zf: zipfile.ZipFile) -> str:
    for name in zf.namelist():
        lower = name.lower()
        if any(lower.endswith(q) for q in QUALITATIVE_FILE_NAMES):
            raw = zf.read(name).decode("utf-8", errors="replace")
            return _strip_html(raw)
    return ""


_IX_NAMESPACES = (
    "http://www.xbrl.org/2008/inlineXBRL",  # TDnet 決算短信 (most common)
    "http://www.xbrl.org/2013/inlineXBRL",  # EDINET / newer
)


def _extract_revenue(zf: zipfile.ZipFile) -> float | None:
    """Parse the iXBRL Summary HTML as XML to pick up <ix:nonFraction> facts.

    Strategy:
      1. Parse with recover=True (ignore malformed bits).
      2. Find all ix:nonFraction elements whose @name matches a revenue tag.
      3. Prefer current-period contexts; skip Prior* and Forecast* contexts.
      4. Apply @scale (decimals can also adjust, but most TDnet files use scale).
    """
    summary = [n for n in zf.namelist() if "Summary" in n and n.endswith(".htm")]
    if not summary:
        return None
    raw = zf.read(summary[0])
    try:
        root = etree.fromstring(raw, parser=etree.XMLParser(recover=True, huge_tree=True, ns_clean=True))
    except Exception:
        return None
    if root is None:
        return None
    nodes: list = []
    for ns in _IX_NAMESPACES:
        nodes = root.xpath(".//ix:nonFraction", namespaces={"ix": ns})
        if nodes:
            break
    for tag in REVENUE_TAGS:
        for node in nodes:
            name = node.get("name") or ""
            if not name.endswith(":" + tag):
                continue
            ctx = node.get("contextRef") or ""
            if "Prior" in ctx or "Forecast" in ctx:
                continue
            txt = (node.text or "").strip().replace(",", "")
            if not txt or txt == "-":
                continue
            try:
                val = float(txt)
                scale = node.get("scale")
                if scale:
                    val *= 10 ** int(scale)
                sign = node.get("sign") or ""
                if sign == "-":
                    val = -val
                return val
            except ValueError:
                continue
    return None


def _parse_company_folder(folder: Path) -> tuple[str, str] | None:
    """`5233_太平洋ｾﾒ` -> ('5233', '太平洋ｾﾒ'). Strips trailing `_中計直近のみ` etc."""
    name = folder.name
    m = re.match(r"(\d{4})_(.+)", name)
    if not m:
        return None
    code = m.group(1)
    disp = m.group(2).split("_")[0]
    return code, disp


def _walk_batch_roots(data_dir: Path) -> list[Path]:
    """Find every batch/batch/<company>/ folder under data/.

    Batches look like: data/20260403/20260403/5233_太平洋ｾﾒ/
    """
    out: list[Path] = []
    if not data_dir.exists():
        return out
    for outer in sorted(data_dir.iterdir()):
        if not outer.is_dir():
            continue
        # nested duplicate folder (SharePoint download pattern)
        inner = outer / outer.name
        root = inner if inner.is_dir() else outer
        for company in sorted(root.iterdir()):
            if company.is_dir() and re.match(r"\d{4}_", company.name):
                out.append(company)
    return out


def load_company_from_tdnet(
    folder: Path, cutoff_date: date | None = None
) -> dict[str, Any] | None:
    parsed = _parse_company_folder(folder)
    if not parsed:
        return None
    code, name = parsed
    tanshin = folder / "決算短信"
    if not tanshin.is_dir():
        return None
    zips = sorted(tanshin.glob("*.zip"), key=lambda p: p.name)
    if len(zips) < 2:
        log.warning("%s: only %d filings, need >=2", code, len(zips))
        return None

    # Metadata pass: extract FilingMeta + qualitative text + revenue per zip.
    metas = []
    qual_by_zip: dict[str, str] = {}
    revenues: list[tuple[str, float]] = []   # (date, revenue)

    for z in zips:
        meta = extract_tdnet_filing_meta(z)
        try:
            with zipfile.ZipFile(z) as zf:
                q = _extract_qualitative(zf)
                if q:
                    qual_by_zip[z.name] = q
                r = _extract_revenue(zf)
                if r is not None and meta is not None:
                    revenues.append((meta.filing_date.isoformat(), r))
        except zipfile.BadZipFile:
            log.warning("bad zip: %s", z)
            continue
        if meta is not None and z.name in qual_by_zip:
            metas.append(meta)

    if len(metas) < 2:
        log.warning("%s: only %d usable filings with parseable metadata + qualitative text — skipping", code, len(metas))
        return None

    pair = find_yoy_pair(metas, cutoff_date=cutoff_date)
    if pair is None:
        log.warning(
            "%s: no matching YoY pair (same filing_type + fiscal_period, 9–15 months apart) — skipping",
            code,
        )
        return None
    prev_meta, curr_meta = pair

    # Correction 2: keep the raw (TOC-included) text so split_sections can
    # find ALL section headers; also keep the TOC-trimmed version for the
    # whole-blob fallback path when no canonical sections are detected.
    prev_raw = qual_by_zip[prev_meta.zip_path.name]
    curr_raw = qual_by_zip[curr_meta.zip_path.name]
    prev_text = _skip_toc(prev_raw)
    curr_text = _skip_toc(curr_raw)
    announce_date = curr_meta.filing_date.isoformat()

    # Revenue trajectory → segment_history proxy
    revenues.sort(key=lambda kv: kv[0])
    rev_series = [v for _, v in revenues]
    segment_history: dict[str, list[float]] = {}
    if rev_series:
        segment_history["_revenue_proxy"] = rev_series

    return {
        "code": code,
        "name": name,
        "announce_date": announce_date,
        "prev_text": prev_text[:8000],          # trim to keep LLM cost bounded
        "curr_text": curr_text[:8000],
        "prev_raw_text": prev_raw[:16000],      # Correction 2: pre-TOC-skip for section-splitting
        "curr_raw_text": curr_raw[:16000],
        "segments_prev": [],                    # not available from TDnet XBRL alone
        "segments_curr": [],
        "segment_history": segment_history,
        # TDnet 決算短信 does not carry jpcrp_cor:DescriptionOfBusinessTextBlock —
        # that tag lives in the EDINET 有価証券報告書. TDnet-sourced candidates
        # therefore cannot supply a 事業の内容 string; the similar-company
        # industry gate's JPX-code exact-match path handles them without one,
        # and the cosine-fallback path degrades to company-name comparison.
        "business_description_ja": "",
        "source": "tdnet",
        "filings_count": len(zips),
        "revenue_points": len(rev_series),
        # Correction 1: filing metadata propagated downstream.
        "filing_type": curr_meta.filing_type,
        "fiscal_period": curr_meta.fiscal_period,
        "prev_filing": prev_meta.as_dict(),
        "curr_filing": curr_meta.as_dict(),
    }


def load_all_tdnet(
    data_dir: Path, cutoff_date: date | None = None
) -> dict[str, dict[str, Any]]:
    """Walk every batch folder, return code -> fundamentals dict.

    When cutoff_date is provided (backtest mode), each company's YoY pair is
    selected from filings with filing_date ≤ cutoff_date only.
    """
    out: dict[str, dict[str, Any]] = {}
    for folder in _walk_batch_roots(data_dir):
        log.info("TDnet load: %s", folder.name)
        fund = load_company_from_tdnet(folder, cutoff_date=cutoff_date)
        if fund is not None:
            out[fund["code"]] = fund
    return out
