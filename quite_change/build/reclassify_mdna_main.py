# -*- coding: utf-8 -*-
"""Re-classify the MAIN sets on the MD&A-upgraded packets — STAGED output (Batch API).
Writes it_q4_2024_mdna.json / it_q4_2025_mdna.json. Does NOT touch the committed it_q4_*.json.
custom_id is year-namespaced (a ticker can appear in both years).
"""
from __future__ import annotations
import json, sys, time, os
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from run_it_noweb import prompt
from run_it_batch import _env, MODEL, SCHEMA
import anthropic

YEARS = [('2024', '_pkts_2024_mdna', 'it_q4_2024_mdna.json'),
         ('2025', '_pkts_mdna', 'it_q4_2025_mdna.json')]
c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))

reqs, meta = [], {}
for year, d, _out in YEARS:
    for f in sorted((ROOT / 'data' / 'quarterly' / d).glob('*.json')):
        p = json.loads(f.read_text(encoding='utf-8')); t = p['ticker']
        if not (p.get('prices', {}) or {}).get('stock_dir'):
            continue
        cid = f'{year}_{t}'
        reqs.append({'custom_id': cid, 'params': {'model': MODEL, 'max_tokens': 5500,
            'messages': [{'role': 'user', 'content': prompt(p)}],
            'output_config': {'format': {'type': 'json_schema', 'schema': SCHEMA}}}})
        meta[cid] = (year, d, t, p)

print(f'submitting batch: {len(reqs)} companies (both years)')
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
print(f'batch ended: {len(res)}/{len(reqs)} ok')

COMMITTED = {'2024': 'it_q4_2024.json', '2025': 'it_q4_2025.json'}
for year, d, out in YEARS:
    committed = json.loads((ROOT / 'data' / 'quarterly' / COMMITTED[year]).read_text(encoding='utf-8'))['companies']
    o = {}
    for cid, cc in res.items():
        yr, dd, t, p = meta[cid]
        if yr != year:
            continue
        # SCOPE THE CHANGE: adopt new BUSINESS-side fields (the MD&A fix); PRESERVE the committed
        # STOCK-side work (the earlier guidance_disappointment sub-split etc.) so it doesn't regress.
        old = committed.get(t)
        if old:
            cc['stock_reason_tag'] = old.get('stock_reason_tag', cc.get('stock_reason_tag'))
            if old.get('why_stock_moved'):
                cc['why_stock_moved'] = old['why_stock_moved']
        else:  # not in committed → apply near-flat rule to the fresh stock tag
            pr = p.get('prices', {}) or {}; ab, rel = pr.get('pct_change'), pr.get('relative_pct')
            if ab is not None:
                if abs(ab) <= 1.0: cc['stock_reason_tag'] = 'muted_no_reaction'
                elif rel is not None and abs(rel) <= 1.0: cc['stock_reason_tag'] = 'other'
        o[t] = cc
    (ROOT / 'data' / 'quarterly' / out).write_text(json.dumps({'companies': o}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{year}: {len(o)} -> {out} (STAGED; business=new, stock=committed)')
