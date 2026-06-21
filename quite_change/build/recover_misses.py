# -*- coding: utf-8 -*-
"""Corrected triage + recovery: (A) re-gate the 10 identity-fails from already-saved files with
full-width-normalized identity (no mirror hit); (B) gentle jiji-only retry for the 18 download_404
(f.irbank is 403-throttling us today, so skip it). Updates the DB for recovered. Nothing committed.
"""
from __future__ import annotations
import io, re, sys, json, time, sqlite3, urllib.request
from datetime import datetime
from pathlib import Path
import pdfplumber
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
import backfill_irbank as bi
FR = ROOT / 'data' / 'flash_reports'
Z = str.maketrans('０１２３４５６７８９', '0123456789')
TG = {(x['ticker'], x['fy']): x for x in json.loads((ROOT / 'data' / 'quarterly' / '_all_it_targets.json').read_text(encoding='utf-8'))}
m = json.loads((FR / '_misses_review.json').read_text(encoding='utf-8'))
D404 = [(x['ticker'], x['fy']) for x in m if x['status'] == 'miss:download_404']
IDF = [(x['ticker'], x['fy']) for x in m if x['status'] == 'miss:identity']
c = sqlite3.connect(FR / 'index.db')

print('=== A) identity-fails re-gated from SAVED file (full-width normalized, no download) ===')
id_rows = []
for t, fy in IDF:
    tf_ = FR / t / f'{fy}_tanshin.txt'
    txt = tf_.read_text(encoding='utf-8') if tf_.exists() else ''
    norm = txt.translate(Z)
    head = txt[:400]
    got = '決算短信' in head or '決算短信' in re.sub(r'(.)\1{2,}', r'\1', head)
    ident = t in norm[:1500]
    if got and ident:
        c.execute("UPDATE reports SET status='ok', gate_results=? WHERE ticker=? AND fy=? AND authoritative=1",
                  (json.dumps({'identity': True, 'note': 'recovered: full-width code'}), t, fy))
        c.commit(); verdict = 'FALSE-REJECT -> recovered (code in full-width)'
    elif t in norm:
        verdict = 'false-reject (code present but format/position) — parser note'
    else:
        verdict = 'code genuinely absent in text layer — needs look/OCR'
    id_rows.append((t, fy, verdict)); print(f'  {t} FY{fy}: {verdict}')

print('\n=== B) download_404 gentle jiji-only retry (skip throttled f.irbank), 4s spacing ===')
d_rows = []
for t, fy in D404:
    pe = TG[(t, fy)]['period_end']; name = TG[(t, fy)]['name']
    docid, _ = bi.resolve(t, pe)
    if not docid:
        d_rows.append((t, fy, 'no-docid')); print(f'  {t} FY{fy}: no-docid'); continue
    try:
        data = urllib.request.urlopen(urllib.request.Request(
            f'https://equity.jiji.com/storage/tdnet/{docid}.pdf', headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read()
        ok = data[:4] == b'%PDF'
    except urllib.error.HTTPError as e:
        ok = False; code = f'jiji-{e.code}'
    except Exception:
        ok = False; code = 'jiji-err'
    if ok:
        cdir = FR / t; cdir.mkdir(exist_ok=True)
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            txt = '\n'.join((p.extract_text() or '') for p in pdf.pages[:3])
        (cdir / f'{fy}_tanshin.pdf').write_bytes(data); (cdir / f'{fy}_tanshin.txt').write_text(txt, encoding='utf-8')
        ident = t in txt[:1500].translate(Z); got = '決算短信' in txt[:400]
        st = 'ok' if (got and ident) else 'miss:check'
        c.execute("UPDATE reports SET status=?, source_mirror='jiji', file_path=? WHERE ticker=? AND fy=? AND authoritative=1",
                  (st, str((cdir / f'{fy}_tanshin.pdf').relative_to(ROOT)), t, fy)); c.commit()
        d_rows.append((t, fy, f'RECOVERED via jiji ({st})')); print(f'  {t} FY{fy}: RECOVERED via jiji')
    else:
        d_rows.append((t, fy, 'jiji-404; f.irbank throttled(403) — retry after cooldown')); print(f'  {t} FY{fy}: jiji-miss; f.irbank throttled -> cooldown retry')
    time.sleep(4)

rec_id = sum(1 for r in id_rows if 'recovered' in r[2])
rec_d = sum(1 for r in d_rows if 'RECOVERED' in r[2])
print('\n===== CORRECTED SUMMARY =====')
print(f'identity-fails: {rec_id}/{len(IDF)} recovered (full-width false-rejects), {len(IDF)-rec_id} need look')
print(f'download_404: {rec_d}/{len(D404)} recovered now via jiji; rest = f.irbank throttled today (recoverable after cooldown, NOT genuine gaps)')
import sqlite3 as _s
ok=c.execute("SELECT COUNT(*) FROM reports WHERE authoritative=1 AND status='ok'").fetchone()[0]
print(f'DB ok now: {ok}/1098 = {100*ok//1098}%')
json.dump({'identity': id_rows, 'download_404': d_rows}, open(FR / '_misses_triage_corrected.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
