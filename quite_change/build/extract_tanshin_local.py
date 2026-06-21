# -*- coding: utf-8 -*-
"""Local 決算短信 grounding extractor (the reliable path — WebFetch can't read PDFs, pdfplumber can).

Input: data/quarterly/_grounding_results/_urls_{YEAR}.json = [{"t":ticker,"url":primary_pdf_url}, ...]
For each: download the PDF, pdfplumber-extract pages 1-3 (the summary: 連結経営成績 + 配当 +
業績予想 + 自己株式), set pkt['tanshin_text'] + tanshin_source_url, and pull the cover date.
PRIMARY URLs only (is_primary_source gate). Pages 1-2 of a 決算短信 carry results, next-year
guidance, dividends and buybacks — exactly what recovers guidance_disappointment + capital_return.

Usage: PKTDIR_NAME=_pkts_2024 python build/extract_tanshin_local.py 2024
"""
from __future__ import annotations
import io, json, os, re, sys, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import pdfplumber
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
from research import tempest_fetch as tf
from prefetch_tanshin import is_primary_source
import importlib.util
spec = importlib.util.spec_from_file_location('t2', ROOT / 'build' / 'add_tier2.py')
t2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t2)

YEAR = sys.argv[1]
PKTDIR = ROOT / 'data' / 'quarterly' / os.environ.get('PKTDIR_NAME', '_pkts')
URLS = ROOT / 'data' / 'quarterly' / '_grounding_results' / f'_urls_{YEAR}.json'

def fetch_pdf_text(url, max_pages=3, max_chars=8000):
    import time as _t
    data = None
    hdr = {'User-Agent': 'Mozilla/5.0'}
    if 'f.irbank.net' in url:  # anti-hotlink: f.irbank serves the PDF only with a Referer
        hdr['Referer'] = 'https://irbank.net/'
    for _i in range(3):  # retry transient DNS/network failures (the getaddrinfo glitches)
        try:
            req = urllib.request.Request(url, headers=hdr)
            data = urllib.request.urlopen(req, timeout=90).read(); break
        except Exception:
            if _i == 2: raise
            _t.sleep(2)
    out = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pg in pdf.pages[:max_pages]:
            out.append(pg.extract_text() or '')
    return '\n'.join(out)[:max_chars]

def cover_date(text):
    # the disclosure date sits in the header, after the period line
    for y, m, d in re.findall(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日', text[:800]):
        try:
            dt = datetime(int(y), int(m), int(d)); return dt.strftime('%Y-%m-%d')
        except ValueError:
            pass
    return None

def in_window(d, pe):
    try: dt = datetime.strptime(d, '%Y-%m-%d'); p = datetime.strptime(pe, '%Y-%m-%d')
    except Exception: return False
    return p + timedelta(days=5) <= dt <= p + timedelta(days=130)

def main():
    urls = {r['t']: r['url'] for r in json.loads(URLS.read_text(encoding='utf-8')) if r.get('url')}
    ok = fail = rewin = skip = 0
    flips = []
    for t, url in urls.items():
        pf = PKTDIR / f'{t}.json'
        if not pf.exists() or not is_primary_source(url):
            skip += 1; continue
        try:
            txt = fetch_pdf_text(url)
        except Exception as e:
            print(f'  {t} DL/parse FAIL {str(e)[:50]}'); fail += 1; continue
        # GARBLED-GLYPH RECOVERY: some PDFs (broadcaster fonts) extract every char repeated ×N
        # ("決決決決決算算算算算"). Collapse runs of 3+ identical chars → readable narrative. Numbers
        # may mangle, but we ground numbers from the feed (not the 短信) — this is narrative-only.
        if '決算短信' not in txt[:300]:
            dd = re.sub(r'(.)\1{2,}', r'\1', txt)
            if '決算短信' in dd[:300]:
                txt = dd; print(f'  {t} (de-garbled repeated-glyph PDF)')
        if len(txt) < 400 or ('百万円' not in txt and '億円' not in txt and '円' not in txt):
            print(f'  {t} thin/binary text ({len(txt)}c) — skip'); fail += 1; continue
        pkt = json.loads(pf.read_text(encoding='utf-8')); pe = pkt['period_end']
        # IDENTITY GATE — the doc must be THIS company (ticker in url/text, or a JP name token).
        # Prevents wrong-company contamination (the Kyosan/Nissui/Sanbio mix-ups).
        import re as _re
        nmjp = pkt.get('name_official_jp') or ''
        toks = [w for w in _re.findall(r'[ぁ-んァ-ヶ一-龠]{3,}', nmjp)]
        if not ((t in url) or (t in txt) or any(tok in txt for tok in toks)):
            print(f'  {t} IDENTITY FAIL (doc not {t}/{nmjp}) — skip'); fail += 1; continue
        # DOC-TYPE GATE — full-year 決算短信 ONLY. Reject slide decks (決算説明資料 — the AI inside
        # trap), quarterly 短信 (第N四半期/中間), and 有報. Labels are explicit on the cover.
        head = txt[:300]
        if '決算短信' not in head:
            print(f'  {t} NOT a 決算短信 (deck/有報/other) — skip'); fail += 1; continue
        if any(q in head for q in ('第１四半期', '第２四半期', '第３四半期', '四半期決算短信', '中間決算短信')):
            print(f'  {t} quarterly/interim 短信 — skip (need 通期 full-year)'); fail += 1; continue
        cd = cover_date(txt)
        if cd and not in_window(cd, pe):  # wrong-period doc (cover date outside the FY window)
            print(f'  {t} WRONG-PERIOD doc (cover {cd}, pe {pe}) — skip'); fail += 1; continue
        if len(txt) < 1500:  # too thin to be a real summary
            print(f'  {t} thin ({len(txt)}c) — skip'); fail += 1; continue
        pkt['tanshin_text'] = txt; pkt['tanshin_source_url'] = url
        if cd and in_window(cd, pe) and cd != pkt.get('announce_date'):
            old = pkt.get('announce_date'); od = (pkt.get('prices', {}) or {}).get('stock_dir')
            try:
                pr = tf.fetch_prices(t, cd); mk = t2.topix_move(pr['p0_date'], pr['p1_date']); rel, mt = t2.classify(pr['pct_change'], mk)
                pr['market_pct'] = mk; pr['relative_pct'] = rel; pr['move_type'] = mt
                pkt['announce_date'] = cd; pkt['announce_date_doc'] = cd; pkt['prices'] = pr; rewin += 1
                if od and pr['stock_dir'] != od: flips.append((t, old, cd, od, pr['stock_dir'], pr['pct_change']))
            except Exception as e:
                print(f'  {t} rewindow fail {e}')
        pf.write_text(json.dumps(pkt, ensure_ascii=False, indent=2), encoding='utf-8')
        ok += 1
        print(f'  {t} OK ({len(txt)}c) cover={cd} {url[:48]}')
    print(f'\n== local extract {YEAR}: grounded={ok} fail={fail} skip={skip} cover-date rewindows={rewin} ==')
    print(f'cover-date S± flips: {flips}')

if __name__ == '__main__':
    main()
