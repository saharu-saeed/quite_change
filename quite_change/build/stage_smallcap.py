# -*- coding: utf-8 -*-
"""Retrieval-only validation (NO classification) on the 50 smallest-cap IT companies, FY2025.
Per company: resolve 通期 doc-id (irbank/tdnet) → download (jiji→f.irbank) → pdfplumber → de-garble →
gates (識別子=ticker, 通期 not quarterly/deck, cover-date) + readability. Every MISS is typed:
  not_found | image_only | garbled | odd_listing
Usage: python build/stage_smallcap.py stage1   (8-sample)   |   python build/stage_smallcap.py all
"""
from __future__ import annotations
import io, re, sys, json, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import pdfplumber
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
import backfill_irbank as bi
Q = ROOT / 'data' / 'quarterly'
SEL = {r['ticker']: r for r in json.loads((Q / '_smallcap50_selection.json').read_text(encoding='utf-8'))}
STAGE1 = ['4316', '4265', '4394', '3624', '5240', '5025', '4370', '4416']  # spread across the 50

def _get(url, hdr):
    return urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=40).read()

def download(docid):
    try:
        return _get(f'https://equity.jiji.com/storage/tdnet/{docid}.pdf', {'User-Agent': 'Mozilla/5.0'}), 'jiji'
    except Exception:
        pass
    for i in range(3):
        try:
            return _get(f'https://f.irbank.net/pdf/{docid[4:12]}/{docid}.pdf', {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://irbank.net/'}), 'firb'
        except Exception:
            time.sleep(2 + 2 * i)
    return None, None

def cover_date(t):
    for y, m, d in re.findall(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日', t[:800]):
        try: return datetime(int(y), int(m), int(d)).strftime('%Y-%m-%d')
        except ValueError: pass
    return None

def check(t):
    s = SEL[t]; pe = s['period_end']
    docid, title = bi.resolve(t, pe)
    if not docid:
        return dict(t=t, name=s['name'], hit=False, miss='not_found', detail='no doc-id on irbank/tdnet')
    data, mirror = download(docid)
    if not data:
        return dict(t=t, name=s['name'], hit=False, miss='not_found', detail='doc-id ok but jiji+f.irbank 404', docid=docid)
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            txt = '\n'.join((p.extract_text() or '') for p in pdf.pages[:3])
    except Exception as e:
        return dict(t=t, name=s['name'], hit=False, miss='odd_listing', detail=f'parse fail {str(e)[:25]}', docid=docid)
    raw_len = len(txt); degarbled = False
    if '決算短信' not in txt[:300]:
        dd = re.sub(r'(.)\1{2,}', r'\1', txt)
        if '決算短信' in dd[:300]:
            txt = dd; degarbled = True
        elif raw_len < 300:
            return dict(t=t, name=s['name'], hit=False, miss='image_only', detail=f'no text layer ({raw_len}c)', docid=docid, mirror=mirror)
        else:
            return dict(t=t, name=s['name'], hit=False, miss='garbled', detail=f'de-garble failed ({raw_len}c)', docid=docid, mirror=mirror)
    head = txt[:400]
    got = '決算短信' in head
    quarterly = any(q in head for q in ('第１四半期', '第２四半期', '第３四半期', '四半期決算短信', '中間決算短信'))
    identity = t in txt[:900]
    cd = cover_date(txt)
    readable = len(txt) > 1000
    if got and not quarterly and identity:
        return dict(t=t, name=s['name'], hit=True, identity=identity, doctype_ok=True, cover_date=cd,
                    readable=readable, degarbled=degarbled, mirror=mirror, docid=docid)
    detail = 'quarterly/interim' if quarterly else ('identity-fail' if not identity else 'no 決算短信 in head')
    return dict(t=t, name=s['name'], hit=False, miss='odd_listing', detail=detail, docid=docid, mirror=mirror)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'stage1'
    tickers = STAGE1 if mode == 'stage1' else list(SEL.keys())
    res = []
    for t in tickers:
        r = check(t); res.append(r)
        tag = 'HIT ' if r['hit'] else f'MISS:{r["miss"]}'
        extra = f'id={r.get("identity")} 通期={r.get("doctype_ok")} cd={r.get("cover_date")} read={r.get("readable")} {"[de-garbled]" if r.get("degarbled") else ""}' if r['hit'] else r.get('detail', '')
        print(f'{t} {SEL[t]["name"][:16]:16} {SEL[t]["mcap"]/1e8:5.1f}億 {tag:16} {extra}')
        time.sleep(1)
    hits = sum(1 for r in res if r['hit']); n = len(res)
    print(f'\n== {mode}: HIT {hits}/{n} = {100*hits//n}% ==')
    if mode != 'stage1':
        from collections import Counter
        miss = Counter(r['miss'] for r in res if not r['hit'])
        print('MISS breakdown:', dict(miss))
        cd_ok = sum(1 for r in res if r['hit'] and r.get('cover_date')); read_ok = sum(1 for r in res if r['hit'] and r.get('readable'))
        print(f'gate pass (of {hits} hits): identity {hits}/{hits} | doc-type 通期 {hits}/{hits} | cover-date {cd_ok}/{hits} | readable {read_ok}/{hits}')
        (Q / '_smallcap50_retrieval.json').write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
        print('-> _smallcap50_retrieval.json')

if __name__ == '__main__':
    main()
