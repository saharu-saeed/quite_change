# -*- coding: utf-8 -*-
"""Apply the MD&A-extraction upgrade to the MAIN sets — STAGED (originals untouched).
Copies each packet from the source dir to a new _mdna dir; for 短信-grounded companies it
re-downloads the 通期 短信 (by doc-id), extracts the「経営成績等の概況」MD&A cause-prose, and sets
tanshin_text = MD&A-prose-FIRST (so it survives the prompt's char cap) + a compact summary tail.
有報-only / image-only companies are copied unchanged. Caches PDFs.

Usage: python build/build_mdna_main.py _pkts_2024 _pkts_2024_mdna
"""
from __future__ import annotations
import io, re, sys, json, time, urllib.request, shutil
from pathlib import Path
import pdfplumber
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
import backfill_irbank as bi

SRC = ROOT / 'data' / 'quarterly' / sys.argv[1]
DST = ROOT / 'data' / 'quarterly' / sys.argv[2]; DST.mkdir(parents=True, exist_ok=True)
CACHE = ROOT / 'data' / 'quarterly' / '_mdna_pdfs'; CACHE.mkdir(parents=True, exist_ok=True)

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
    f = re.sub(r'…{2,}[^\n]*', '', full)
    for h in ['経営成績に関する分析', '当期の経営成績の概況', '経営成績の概況', '経営成績等の概況', '当期の経営成績', '財政状態、経営成績']:
        for m in re.finditer(h, f):
            seg = f[m.start():m.start() + 4500]
            if seg.count('。') >= 3:
                return seg
    return ''

def main():
    upgraded = copied = noprose = 0
    for pf in sorted(SRC.glob('*.json')):
        p = json.loads(pf.read_text(encoding='utf-8')); t = p['ticker']
        dst = DST / f'{t}.json'
        if not p.get('tanshin_text'):           # 有報-only / ungrounded — copy unchanged
            shutil.copyfile(pf, dst); copied += 1; continue
        docid, _ = bi.resolve(t, p['period_end'])
        if not docid:
            shutil.copyfile(pf, dst); copied += 1; continue
        cf = CACHE / f'{SRC.name}_{t}.pdf'
        try:
            data = cf.read_bytes() if cf.exists() else download(docid)
            if not cf.exists(): cf.write_bytes(data); time.sleep(1)
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                full = '\n'.join((pg.extract_text() or '') for pg in pdf.pages[:8])
        except Exception:
            shutil.copyfile(pf, dst); copied += 1; continue
        if '決算短信' not in full[:300]:
            full = re.sub(r'(.)\1{2,}', r'\1', full)
        prose = mdna_prose(full)
        if not prose:                            # couldn't isolate MD&A — keep existing text
            shutil.copyfile(pf, dst); noprose += 1; continue
        summary = full[:1800]
        p['tanshin_text'] = (prose + '\n\n【サマリー】\n' + summary)[:8500]  # MD&A FIRST
        p['mdna_upgraded'] = True
        dst.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding='utf-8')
        upgraded += 1
    print(f'{SRC.name} -> {DST.name}: MD&A-upgraded {upgraded} | copied-unchanged {copied} | no-prose {noprose}')

if __name__ == '__main__':
    main()
