# -*- coding: utf-8 -*-
"""Targeted recovery across FY2023/2024/2025 — only touches not-yet-ok targets (skips the ~1,590 done).
- Re-gates identity-fails from the saved file (full-width digit fix, NO download).
- Tests the f.irbank throttle once; if 403, runs jiji-only (skips f.irbank to not deepen the ban).
- Downloads everything the mirror(s) will serve; leaves image-only/garbled + f.irbank-throttled as the tail.
Reports recovered + remaining-by-reason. Nothing about the committed deliverable changes (separate store).
"""
from __future__ import annotations
import os, re, sys, json, time, sqlite3, urllib.request
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
import backfill_irbank as bi
import build_flash_db as bf
FR = ROOT / 'data' / 'flash_reports'
Z = str.maketrans('０１２３４５６７８９', '0123456789')
c = sqlite3.connect(FR / 'index.db')

# targets across all three years
TGT = []
TGT += json.loads((ROOT / 'data' / 'quarterly' / '_all_it_targets.json').read_text(encoding='utf-8'))
TGT += json.loads((ROOT / 'data' / 'quarterly' / '_all_it_targets_2023.json').read_text(encoding='utf-8'))

def is_ok(t, fy):
    r = c.execute("SELECT status FROM reports WHERE ticker=? AND fy=? AND authoritative=1", (t, fy)).fetchone()
    return r and r[0] == 'ok'

def cur_status(t, fy):
    r = c.execute("SELECT status FROM reports WHERE ticker=? AND fy=? AND authoritative=1", (t, fy)).fetchone()
    return r[0] if r else None

# 1) throttle test
def firb_ok():
    try:
        did, _ = bi.resolve('4689', '2025-03-31')
        urllib.request.urlopen(urllib.request.Request(f'https://f.irbank.net/pdf/{did[4:12]}/{did}.pdf',
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://irbank.net/'}), timeout=20)
        return True
    except Exception:
        return False
throttled = not firb_ok()
if throttled:
    os.environ['JIJI_ONLY'] = '1'
print(f'f.irbank throttle: {"STILL ACTIVE (jiji-only this run)" if throttled else "CLEARED (using both mirrors)"}')

todo = [(x['ticker'], x['fy'], x['period_end'], x['name']) for x in TGT if not is_ok(x['ticker'], x['fy'])]
print(f'not-yet-ok targets to attempt: {len(todo)}')
rec_gate = rec_dl = 0; remain = []
for t, fy, pe, name in todo:
    st0 = cur_status(t, fy)
    # a) identity false-reject -> re-gate from saved file, no download
    if st0 == 'miss:identity':
        tf_ = FR / t / f'{fy}_tanshin.txt'
        if tf_.exists():
            txt = tf_.read_text(encoding='utf-8')
            if '決算短信' in txt[:400] and t in txt[:1500].translate(Z):
                c.execute("UPDATE reports SET status='ok', gate_results=? WHERE ticker=? AND fy=? AND authoritative=1",
                          (json.dumps({'identity': True, 'note': 'recovered full-width'}), t, fy)); c.commit()
                rec_gate += 1; continue
    # b) attempt (re)download (jiji always; f.irbank only if not throttled)
    try:
        stt, dt, n = bf.process(c, t, fy, pe, name)
        if stt == 'ok':
            rec_dl += 1
        else:
            remain.append((t, fy, stt))
    except Exception as e:
        remain.append((t, fy, f'EXC:{str(e)[:25]}'))
    time.sleep(0.8)

print(f'\nRECOVERED: {rec_gate} via re-gate (identity) + {rec_dl} via download = {rec_gate + rec_dl}')
from collections import Counter
print('STILL REMAINING by reason:', dict(Counter(s for _, _, s in remain).most_common()))
for fy in ['2023', '2024', '2025']:
    ok = c.execute("SELECT COUNT(*) FROM reports WHERE fy=? AND authoritative=1 AND status='ok'", (fy,)).fetchone()[0]
    print(f'  FY{fy} ok now: {ok}')
print('total ok all years:', c.execute("SELECT COUNT(*) FROM reports WHERE authoritative=1 AND status='ok'").fetchone()[0])
