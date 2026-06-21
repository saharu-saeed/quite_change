# -*- coding: utf-8 -*-
"""Stage 1 — retrieval-authenticity check on an 8-company sample of the test-50.
For each: resolve the 通期 doc-id (irbank/tdnet) → f.irbank PDF → run gates:
  (1) HIT: got a 通期 決算短信 at all
  (2) IDENTITY: コード番号/ticker appears in the header
  (3) DOC-TYPE: 通期 決算短信 (not quarterly/中間/deck/有報)
  (4) DATE: cover (as-filed) date present + in the post-FYE window
Reports hit rate + per-company gate pass/fail. (Stop full run if hit-rate << ~85%.)
"""
from __future__ import annotations
import io, re, sys, json, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import pdfplumber
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
import backfill_irbank as bi

SAMPLE = ['9766', '3769', '9449', '3687', '4180', '3854', '3733', '9405']  # varied cap + FYE
Z = str.maketrans('０１２３４５６７８９', '0123456789')

def _get(url, hdr):
    return urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=40).read()

def fetch(docid):
    """Try jiji first (no referer, reliable), then f.irbank (referer) with backoff on 403/throttle."""
    jiji = f'https://equity.jiji.com/storage/tdnet/{docid}.pdf'
    firb = f'https://f.irbank.net/pdf/{docid[4:12]}/{docid}.pdf'
    try:
        return _get(jiji, {'User-Agent': 'Mozilla/5.0'})
    except Exception:
        pass
    last = None
    for i in range(3):  # f.irbank fallback, polite backoff
        try:
            return _get(firb, {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://irbank.net/'})
        except Exception as e:
            last = e; time.sleep(2 + 2 * i)
    raise last

def cover_date(t):
    for y, m, d in re.findall(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日', t[:800]):
        try: return datetime(int(y), int(m), int(d)).strftime('%Y-%m-%d')
        except ValueError: pass
    return None

def main():
    sel = {r['ticker']: r for r in json.loads((ROOT / 'data' / 'quarterly' / '_test50_selection.json').read_text(encoding='utf-8'))}
    hits = 0; rows = []
    for t in SAMPLE:
        pe = sel[t]['period_end']; nm = sel[t]['name']
        docid, title = bi.resolve(t, pe)
        if not docid:
            rows.append((t, nm, pe, 'NO-DOCID', '-', '-', '-', '-')); continue
        try:
            data = fetch(docid)
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                txt = '\n'.join((p.extract_text() or '') for p in pdf.pages[:2])
        except Exception as e:
            rows.append((t, nm, pe, f'DL-FAIL {str(e)[:18]}', '-', '-', '-', docid)); time.sleep(1); continue
        if '決算短信' not in txt[:300]:               # de-garble repeated-glyph PDFs
            dd = re.sub(r'(.)\1{2,}', r'\1', txt)
            if '決算短信' in dd[:300]: txt = dd
        head = txt[:400]
        got = '決算短信' in head
        ident = (t in txt[:900]) or ('コード番号' in head and t in head)
        # 通期 = full-year 短信; reject ONLY quarterly/interim markers (validated gate in extract_tanshin_local)
        doctype_ok = got and not any(q in head for q in ('第１四半期','第２四半期','第３四半期','四半期決算短信','中間決算短信'))
        time.sleep(1)  # be a good citizen between companies
        cd = cover_date(txt)
        try:
            in_win = bool(cd) and (datetime.strptime(pe,'%Y-%m-%d')+timedelta(days=5) <= datetime.strptime(cd,'%Y-%m-%d') <= datetime.strptime(pe,'%Y-%m-%d')+timedelta(days=130))
        except Exception:
            in_win = False
        if got and doctype_ok: hits += 1
        rows.append((t, nm, pe, 'HIT' if got else 'no-短信', 'OK' if ident else 'FAIL',
                     'OK(通期)' if doctype_ok else 'FAIL', f'{cd}{"" if in_win else " OUT!"}' if cd else 'none', docid))
    print(f'{"tkr":5}{"name":18}{"FYE":12}{"hit":9}{"ident":6}{"doctype":9}{"cover-date":16}docid')
    for t, nm, pe, h, idn, dt, cd, did in rows:
        print(f'{t:5}{nm[:16]:18}{pe:12}{h:9}{idn:6}{dt:9}{cd:16}{did}')
    print(f'\nSTAGE-1 HIT RATE: {hits}/{len(SAMPLE)} = {100*hits//len(SAMPLE)}%  (threshold ~85% = 7/8)')

if __name__ == '__main__':
    main()
