# -*- coding: utf-8 -*-
"""Forward-engine: capture 決算短信 from the FREE official TDnet site (release.tdnet.info).

The daily disclosure listing is plain raw HTML (no JS wall, unlike irbank), so we can scrape
it deterministically: for each date, read every listing page, keep the FULL-YEAR (通期) 決算短信
rows for our target tickers, and download the PDF (+ XBRL) into a local DB keyed by ticker+date.
Run on a schedule (weekly) so every report is caught inside TDnet's ~30-day window — that's the
durable, free, any-year-going-forward pipeline. (Past/expired reports need the historical
backfill instead — irbank via headless browser — TDnet only keeps ~30 days.)

Usage: python build/collect_tdnet.py 2026-05-25 2026-06-19   [tickers.txt | all]
"""
from __future__ import annotations
import io, re, sys, json, urllib.request
from datetime import date, timedelta
from pathlib import Path
ROOT = Path(__file__).parent.parent
DB = ROOT / 'data' / 'quarterly' / '_tdnet_db'
BASE = 'https://www.release.tdnet.info/inbs/'

ROW = re.compile(r'kjCode"[^>]*>(\d{4})\d?<.*?kjTitle"[^>]*><a href="([^"]+\.pdf)"[^>]*>([^<]+)</a>', re.S)
QUARTERLY = ('第１四半期', '第２四半期', '第３四半期', '第１四半期', '中間', '四半期')

def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read()

def list_day(d):
    """All (ticker, pdf_url, title) 決算短信 rows for a date, across listing pages."""
    out = []
    for pg in range(1, 12):  # paginate until empty
        url = f'{BASE}I_list_{pg:03d}_{d}.html'
        try:
            html = fetch(url).decode('utf-8', 'ignore')
        except Exception:
            break
        rows = ROW.findall(html)
        if not rows:
            break
        for code, href, title in rows:
            if '決算短信' in title and not any(q in title for q in QUARTERLY):  # 通期 only
                out.append((code, BASE + href.split('/')[-1], title.strip()))
    return out

def main():
    # No args = scheduled mode: scan the last 8 days (overlaps weekly runs → ~4 shots per report
    # inside TDnet's 30-day window) for our IT universe.
    if len(sys.argv) < 3:
        end = date.today().isoformat(); start = (date.today() - timedelta(days=8)).isoformat()
        uni = ROOT / 'data' / 'quarterly' / '_it_universe.txt'
        targets = set(uni.read_text().split()) if uni.exists() else None
    else:
        start = sys.argv[1]; end = sys.argv[2]
        targets = None
        if len(sys.argv) > 3 and sys.argv[3] != 'all':
            targets = set(Path(sys.argv[3]).read_text().split())
    DB.mkdir(parents=True, exist_ok=True)
    index = json.loads((DB / '_index.json').read_text(encoding='utf-8')) if (DB / '_index.json').exists() else {}
    d0 = date.fromisoformat(start); d1 = date.fromisoformat(end)
    captured = 0; seen_days = 0
    d = d0
    while d <= d1:
        ds = d.strftime('%Y%m%d')
        rows = list_day(ds)
        seen_days += 1
        for code, pdfurl, title in rows:
            if targets and code not in targets:
                continue
            try:
                data = fetch(pdfurl)
            except Exception as e:
                print(f'  {code} {ds} dl-fail {str(e)[:30]}'); continue
            f = DB / f'{code}_{ds}.pdf'
            f.write_bytes(data)
            index[f'{code}_{ds}'] = {'ticker': code, 'date': d.isoformat(), 'title': title, 'src': pdfurl, 'bytes': len(data)}
            captured += 1
            print(f'  CAPTURED {code} {ds}: {title[:40]} ({len(data)//1024}KB)')
        d += timedelta(days=1)
    (DB / '_index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding='utf-8')
    summary = f'scanned {seen_days} days {start}..{end} | captured {captured} 通期決算短信 | DB now {len(index)} docs'
    from datetime import datetime as _dt
    with (DB / '_runlog.txt').open('a', encoding='utf-8') as lg:  # so a silent failed/missed run is visible
        lg.write(f'{_dt.now().strftime("%Y-%m-%d %H:%M")}  {summary}\n')
    print(f'\n{summary} -> {DB.name}/')

if __name__ == '__main__':
    main()
