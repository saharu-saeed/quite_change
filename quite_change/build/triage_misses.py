# -*- coding: utf-8 -*-
"""Triage the 28 misses (18 download_404 + 10 identity-fail): genuinely unavailable vs recoverable.
Free, retrieval-only, into the same store; nothing committed.
"""
from __future__ import annotations
import io, re, sys, json, time, sqlite3, urllib.request
from pathlib import Path
import pdfplumber
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
import backfill_irbank as bi
import build_flash_db as bf

FR = ROOT / 'data' / 'flash_reports'
TG = {(x['ticker'], x['fy']): x for x in json.loads((ROOT / 'data' / 'quarterly' / '_all_it_targets.json').read_text(encoding='utf-8'))}
m = json.loads((FR / '_misses_review.json').read_text(encoding='utf-8'))
D404 = [(x['ticker'], x['fy']) for x in m if x['status'] == 'miss:download_404']
IDF = [(x['ticker'], x['fy']) for x in m if x['status'] == 'miss:identity']
c = sqlite3.connect(FR / 'index.db')

print('=== download_404 triage (18) — re-resolve + retry both mirrors ===')
d404_rows = []
for t, fy in D404:
    pe = TG[(t, fy)]['period_end']; name = TG[(t, fy)]['name']
    docid, title = bi.resolve(t, pe)
    if not docid:
        d404_rows.append((t, fy, 'truly-unavailable', 'no doc-id resolves now')); print(f'  {t} FY{fy}: truly-unavailable (no doc-id)'); continue
    st, dt, n = bf.process(c, t, fy, pe, name)   # retry-hardened download + gates + store
    if st == 'ok':
        mir = c.execute("SELECT source_mirror FROM reports WHERE ticker=? AND fy=? AND authoritative=1", (t, fy)).fetchone()
        v = f'recovered (mirror={mir[0] if mir else "?"})'
    elif 'download_404' in st:
        v = 'genuine-mirror-gap (doc-id in listing, no mirror serves PDF)'
    else:
        v = f'now {st}'
    d404_rows.append((t, fy, v, docid)); print(f'  {t} FY{fy}: {v}')
    time.sleep(0.8)

print('\n=== identity-fail triage (10) — read fetched PDF, find actual コード番号/company ===')
def code_in(txt):
    mm = re.search(r'コード番号[\s　]*[:：]?[\s　]*(\d{4})', txt)
    if mm: return mm.group(1)
    mm = re.search(r'\((\d{4})\)', txt[:1500])  # e.g. 「社名(1234)」
    return mm.group(1) if mm else None
def company_in(txt):
    mm = re.search(r'上場会社名[\s　]*([^\n上]{2,30})', txt)
    return (mm.group(1).strip() if mm else '?')[:24]

idf_rows = []
for t, fy in IDF:
    want_name = TG[(t, fy)]['name']
    tf_ = FR / t / f'{fy}_tanshin.txt'
    txt = tf_.read_text(encoding='utf-8') if tf_.exists() else ''
    actual = code_in(txt); comp = company_in(txt)
    present_anywhere = t in txt
    if present_anywhere:
        verdict = 'false-reject (code present, past 900c / format)'; recov = 'Y (widen gate)'
    elif actual and actual != t:
        verdict = f'WRONG-MATCH (doc is {actual})'; recov = '?'
    else:
        verdict = 'false-reject (code not in text layer / header)'; recov = 'Y (parser/OCR)'
    # if wrong-match, re-resolve the correct doc-id
    rr = ''
    if 'WRONG-MATCH' in verdict:
        did, ti = bi.resolve(t, TG[(t, fy)]['period_end'])
        rr = f' re-resolved->{did}'
    idf_rows.append((t, fy, want_name, actual, comp, verdict, recov))
    print(f'  {t} FY{fy} want={want_name[:12]:12} | doc code={actual} comp={comp[:14]:14} | {verdict}{rr}')

# summary
rec = sum(1 for _, _, v, _ in d404_rows if v.startswith('recovered'))
gap = sum(1 for _, _, v, _ in d404_rows if 'mirror-gap' in v)
una = sum(1 for _, _, v, _ in d404_rows if 'truly-unavailable' in v)
fr = sum(1 for r in idf_rows if 'false-reject' in r[5]); wm = sum(1 for r in idf_rows if 'WRONG-MATCH' in r[5])
print('\n===== SUMMARY =====')
print(f'download_404 ({len(D404)}): recovered {rec} | genuine-mirror-gap {gap} | truly-unavailable {una} | other {len(D404)-rec-gap-una}')
print(f'identity-fail ({len(IDF)}): false-reject(parser quirk) {fr} | WRONG-MATCH(resolution issue) {wm}')
json.dump({'download_404': [list(x) for x in d404_rows], 'identity': [list(x) for x in idf_rows]},
          open(FR / '_misses_triage.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('-> data/flash_reports/_misses_triage.json')
