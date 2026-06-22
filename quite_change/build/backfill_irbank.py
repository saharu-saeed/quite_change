# -*- coding: utf-8 -*-
"""Historical backfill — resolve the 通期 決算短信 doc-id for ANY year, deterministically, free.

The KEY discovery: irbank's per-company page `irbank.net/{ticker}/tdnet` is SERVER-RENDERED
(plain HTML — unlike /results which is JS-injected). Its disclosure table lists every year's
通期 決算短信 with the real TDnet doc-id in the href. From the doc-id we build the jiji mirror
PDF (equity.jiji.com/storage/tdnet/{docid}.pdf — verified working). So for any (ticker, fiscal
period) we can get the right full-year 短信 with no search, no JS browser, no paid feed.

This SUPERSEDES the earlier "needs Playwright / manual / paid" floor: that conclusion was drawn
from irbank's JS-rendered /results page; the /tdnet page is scrapable.

Usage: python build/backfill_irbank.py 2024 _pkts_2024   (writes _urls_irbank_2024.json for the
       residual = packets with no tanshin_text; then run extract_tanshin_local on it)
"""
from __future__ import annotations
import json, re, sys, urllib.request, time
from pathlib import Path
ROOT = Path(__file__).parent.parent
Z = str.maketrans('０１２３４５６７８９', '0123456789')  # full-width → half-width digits

def fetch(url, tries=3):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read().decode('utf-8', 'ignore')
        except Exception:
            if i == tries - 1: raise
            time.sleep(2)

def title_period(title):
    """Return (year, month) the title's 通期 短信 covers — handles calendar (2024年3月期) and
    reiwa (令和6年3月期) and full-width digits."""
    s = title.translate(Z)
    m = re.search(r'令和(\d+)年度?(\d+)月期', s)
    if m: return 2018 + int(m.group(1)), int(m.group(2))
    m = re.search(r'(20\d{2})年度?(\d+)月期', s)
    if m: return int(m.group(1)), int(m.group(2))
    return None

def resolve(ticker, period_end):
    """Find the full-year 決算短信 doc-id whose covered period == period_end. None if not listed."""
    Y, M = int(period_end[:4]), int(period_end[5:7])
    try:
        h = fetch(f'https://irbank.net/{ticker}/tdnet')
    except Exception:
        return None, None
    for title, docid in re.findall(r'<a[^>]*?title="([^"]*決算短信[^"]*)" href="/\d{4}/(\d{14,18})"', h):
        if '四半期' in title or '中間' in title or '補足' in title:
            continue  # 通期 only
        p = title_period(title)
        if p == (Y, M):
            return docid, title
    return None, None

def resolve_all(ticker, period_end):
    """ALL full-year 決算短信 entries for the period (original + 訂正), for dedup/correction handling.
    Returns [(title, docid), ...] in page order. Also surfaces 開示延期 (disclosure-postponed) notices
    so the caller can flag a delayed filing rather than mistaking the notice for the 短信."""
    Y, M = int(period_end[:4]), int(period_end[5:7])
    try:
        h = fetch(f'https://irbank.net/{ticker}/tdnet')
    except Exception:
        return []
    out = []
    for title, docid in re.findall(r'<a[^>]*?title="([^"]*決算短信[^"]*)" href="/\d{4}/(\d{14,18})"', h):
        if '四半期' in title or '中間' in title or '補足' in title:
            continue
        if title_period(title) == (Y, M):
            out.append((title, docid))
    return out

def firbank_pdf_url(ticker, docid):
    """Real f.irbank PDF URL for a doc-id. f.irbank files PDFs under the DISCLOSURE date, which can
    differ from the doc-id's embedded (submission) date — so the doc-page link is authoritative.
    Falls back to the doc-id-date construction if the page can't be read."""
    try:
        h = fetch(f'https://irbank.net/{ticker}/{docid}')
        m = re.search(r'(https?://f\.irbank\.net)?(/pdf/\d{8}/' + re.escape(docid) + r'\.pdf)', h)
        if m:
            return 'https://f.irbank.net' + m.group(2)
    except Exception:
        pass
    return f'https://f.irbank.net/pdf/{docid[4:12]}/{docid}.pdf'

def main():
    year = sys.argv[1]
    pkdir = ROOT / 'data' / 'quarterly' / (sys.argv[2] if len(sys.argv) > 2 else '_pkts')
    out = []
    hit = miss = 0
    for f in sorted(pkdir.glob('*.json')):
        p = json.loads(f.read_text(encoding='utf-8'))
        if p.get('tanshin_text'):
            continue  # already grounded — only work the residual
        docid, title = resolve(p['ticker'], p['period_end'])
        if docid:
            # f.irbank.net is the authoritative source (irbank just listed it) and has no gaps;
            # jiji is a partial mirror that 404s on some. URL: /pdf/{YYYYMMDD}/{docid}.pdf
            # (date = chars 4-12 of the doc-id). Needs a Referer header (see extract_tanshin_local).
            out.append({'t': p['ticker'], 'url': f'https://f.irbank.net/pdf/{docid[4:12]}/{docid}.pdf'})
            hit += 1
            print(f"  {p['ticker']}: {docid}  {title.translate(Z)[:34]}")
        else:
            miss += 1
            print(f"  {p['ticker']}: not listed for {p['period_end']}")
    dest = ROOT / 'data' / 'quarterly' / '_grounding_results' / f'_urls_irbank_{year}.json'
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\nresolved {hit} doc-ids, {miss} not-listed -> {dest.name} (run extract_tanshin_local next)')

if __name__ == '__main__':
    main()
