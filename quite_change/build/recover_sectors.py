# -*- coding: utf-8 -*-
"""Recover the NON-OCR all-sector 2024/2025 misses (skip image_only/garbled).
- identity false-rejects -> re-gate from the saved .txt (full-width digit fix, no download)
- everything else (not_attempted / notice / quarterly) -> re-attempt download via build_flash_db
  (fixed f.irbank disclosure-date path + real-report gate + latest-real-report-wins).
Free; gentle pacing. Reports recovered + what still remains.
"""
from __future__ import annotations
import os, sys, json, time, sqlite3
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
os.environ.pop('JIJI_ONLY', None)        # use both mirrors (f.irbank path bug is fixed)
import build_flash_db as bf
Z = str.maketrans('０１２３４５６７８９', '0123456789')

c = sqlite3.connect(bf.DB, timeout=120)
c.execute('PRAGMA busy_timeout=120000')
meta = {}
for y in ['2024', '2025']:
    for x in json.load(open(ROOT / 'data' / 'quarterly' / f'_all_sectors_targets_{y}.json', encoding='utf-8')):
        meta[(x['ticker'], x['fy'])] = (x['period_end'], x['name'])
miss = json.load(open(ROOT / 'data' / 'quarterly' / '_all_sectors_misses_2425.json', encoding='utf-8'))
OCR = {'miss:image_only', 'miss:garbled'}
todo = [m for m in miss if m['reason'] not in OCR]
print(f'recovering {len(todo)} non-OCR misses (skipping {sum(1 for m in miss if m["reason"] in OCR)} OCR ones)')

rec_gate = rec_dl = 0; still = []
for i, m in enumerate(todo):
    t, fy, r = m['ticker'], m['fy'], m['reason']
    pe, name = meta.get((t, fy), (None, None))
    if not pe:
        still.append((t, fy, 'no_period_end')); continue
    if r == 'miss:identity':
        tf_ = bf.FR / t / f'{fy}_tanshin.txt'
        if tf_.exists():
            txt = tf_.read_text(encoding='utf-8')
            if '決算短信' in txt[:400] and t in txt[:1500].translate(Z):
                c.execute("UPDATE reports SET status='ok' WHERE ticker=? AND fy=? AND authoritative=1", (t, fy))
                c.commit(); rec_gate += 1; continue
    try:
        st, dt, n = bf.process(c, t, fy, pe, name)
        if st == 'ok':
            rec_dl += 1; print(f'  [{i+1}/{len(todo)}] RECOVERED {t} FY{fy} (was {r})')
        else:
            still.append((t, fy, st))
    except Exception as e:
        still.append((t, fy, f'EXC:{str(e)[:25]}'))
    time.sleep(0.5)

print(f'\nRECOVERED {rec_gate} via re-gate + {rec_dl} via download = {rec_gate + rec_dl}/{len(todo)}')
print('still missing (non-OCR):', dict(Counter(s for _, _, s in still).most_common()))
ok2425 = c.execute("SELECT COUNT(*) FROM reports WHERE authoritative=1 AND fy IN ('2024','2025') AND status='ok'").fetchone()[0]
print(f'all-sector 2024+2025 OK now: {ok2425}')
