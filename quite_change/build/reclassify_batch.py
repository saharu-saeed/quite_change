# -*- coding: utf-8 -*-
"""Batch-reclassify the newly-grounded companies on their real 決算短信 (Anthropic Batch API, 50% off).
Picks every company in the irbank backfill url-lists that now has tanshin_text, re-runs the
classifier, applies the near-flat stock-tag rule, writes the year outputs, re-renders both views.
"""
from __future__ import annotations
import json, sys, time, subprocess
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from run_it_noweb import prompt, MODEL, SCHEMA
from run_it_batch import _env
import anthropic

YEARS = [('2024', '_pkts_2024'), ('2025', '_pkts')]
c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))

reqs, meta = [], {}
for year, d in YEARS:
    uf = ROOT / 'data' / 'quarterly' / '_grounding_results' / f'_urls_irbank_{year}.json'
    for r in json.loads(uf.read_text(encoding='utf-8')):
        t = r['t']; pf = ROOT / 'data' / 'quarterly' / d / f'{t}.json'
        p = json.loads(pf.read_text(encoding='utf-8'))
        if not p.get('tanshin_text'):
            continue  # failed grounding (garbled/thin) — leave on prior classification
        cid = f'{year}_{t}'
        reqs.append({'custom_id': cid, 'params': {'model': MODEL, 'max_tokens': 5500,
            'messages': [{'role': 'user', 'content': prompt(p)}],
            'output_config': {'format': {'type': 'json_schema', 'schema': SCHEMA}}}})
        meta[cid] = (year, d, t)

print(f'submitting batch: {len(reqs)} newly-grounded companies')
batch = c.messages.batches.create(requests=reqs)
while True:
    b = c.messages.batches.retrieve(batch.id)
    if b.processing_status == 'ended':
        break
    time.sleep(20)

res = {}
for r in c.messages.batches.results(batch.id):
    if r.result.type == 'succeeded':
        res[r.custom_id] = json.loads(''.join(bl.text for bl in r.result.message.content if bl.type == 'text'))
print(f'batch ended: {len(res)}/{len(reqs)} succeeded')

for year, d in YEARS:
    of = ROOT / 'data' / 'quarterly' / f'it_q4_{year}.json'
    out = json.loads(of.read_text(encoding='utf-8'))['companies']
    n = 0
    for cid, cc in res.items():
        y, dd, t = meta[cid]
        if y != year:
            continue
        p = json.loads((ROOT / 'data' / 'quarterly' / dd / f'{t}.json').read_text(encoding='utf-8'))
        pr = p.get('prices', {}) or {}; ab, rel = pr.get('pct_change'), pr.get('relative_pct')
        if ab is not None:
            if abs(ab) <= 1.0: cc['stock_reason_tag'] = 'muted_no_reaction'
            elif rel is not None and abs(rel) <= 1.0: cc['stock_reason_tag'] = 'other'
        out[t] = cc; n += 1
    of.write_text(json.dumps({'companies': out}, ensure_ascii=False, indent=2), encoding='utf-8')
    view = ROOT / 'deliverables' / 'quarterly' / f'VIEW_IT_{year}Q4.html'
    import os
    env = {**os.environ, 'PKTDIR_NAME': d}
    subprocess.run(['python', '-X', 'utf8', 'build/build_reason_buckets.py', str(of), str(view)], env=env, cwd=str(ROOT))
    print(f'{year}: applied {n}, re-rendered {view.name}')
print('done')
