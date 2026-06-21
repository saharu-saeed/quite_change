# -*- coding: utf-8 -*-
"""Stage 2c (fix-demo) — re-extract the 50 with the MD&A cause-prose, not just the number tables.
Root cause found in validation: tanshin_text was pages 1-3 (cover + summary + share tables), which
miss the「経営成績等の概況／経営成績に関する分析」MD&A prose (page 3+) where the CAUSE is stated.
New tanshin_text = page-1/2 summary (for the figures) + the MD&A analysis section (for the causes).
Caches PDFs to _test50_pdfs/. Updates the test packets in place (test batch only).
"""
from __future__ import annotations
import io, re, sys, json, time, urllib.request
from pathlib import Path
import pdfplumber
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
import backfill_irbank as bi

PKDIR = ROOT / 'data' / 'quarterly' / '_pkts_2024_test50'
CACHE = ROOT / 'data' / 'quarterly' / '_test50_pdfs'; CACHE.mkdir(parents=True, exist_ok=True)

def download(docid):
    try:
        return urllib.request.urlopen(urllib.request.Request(f'https://equity.jiji.com/storage/tdnet/{docid}.pdf', headers={'User-Agent': 'Mozilla/5.0'}), timeout=45).read()
    except Exception:
        for i in range(3):
            try:
                return urllib.request.urlopen(urllib.request.Request(f'https://f.irbank.net/pdf/{docid[4:12]}/{docid}.pdf', headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://irbank.net/'}), timeout=45).read()
            except Exception as e:
                last = e; time.sleep(2 + 2 * i)
        raise last

def mdna_prose(full):
    f = re.sub(r'…{2,}[^\n]*', '', full)  # drop TOC dotted lines
    for h in ['経営成績に関する分析', '当期の経営成績の概況', '経営成績の概況', '経営成績等の概況', '当期の経営成績', '財政状態、経営成績']:
        for m in re.finditer(h, f):
            seg = f[m.start():m.start() + 4500]
            if seg.count('。') >= 3:   # real prose, not the TOC entry
                return seg
    return ''

def main():
    n = ok = 0
    for pf in sorted(PKDIR.glob('*.json')):
        p = json.loads(pf.read_text(encoding='utf-8')); t = p['ticker']
        docid = (p.get('tanshin_source_url', '') or '').replace('tdnet:', '').split(' ')[0]
        if not docid or not docid.isdigit():
            docid, _ = bi.resolve(t, p['period_end'])
        cf = CACHE / f'{t}.pdf'
        try:
            data = cf.read_bytes() if cf.exists() else download(docid)
            if not cf.exists(): cf.write_bytes(data); time.sleep(1)
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages = [(pg.extract_text() or '') for pg in pdf.pages[:8]]
        except Exception as e:
            print(f'{t} re-extract FAIL {str(e)[:30]}'); n += 1; continue
        full = '\n'.join(pages)
        if '決算短信' not in full[:300]:
            full = re.sub(r'(.)\1{2,}', r'\1', full)  # de-garble
        summary = full[:3000]                          # cover + consolidated summary (figures)
        prose = mdna_prose(full)                        # MD&A causes
        p['tanshin_text'] = (summary + '\n\n【経営成績の概況（定性的情報）】\n' + prose)[:9000]
        p['mdna_found'] = bool(prose)
        pf.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding='utf-8')
        n += 1; ok += 1 if prose else 0
        if not prose: print(f'{t} {p.get("name_jp","")[:14]:14} MD&A prose NOT found (summary only)')
    print(f'\n== re-extracted {n} | MD&A prose captured {ok}/{n} ==')

if __name__ == '__main__':
    main()
