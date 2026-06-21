# -*- coding: utf-8 -*-
"""Stage 2b — classify the 50 test packets on their real 短信 via the Batch API (50% off).
Isolated output: it_q4_2024_test50.json. Nothing touches the main deliverable.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from run_it_noweb import prompt, MODEL, SCHEMA
from run_it_batch import _env
import anthropic

PKDIR = ROOT / 'data' / 'quarterly' / '_pkts_2024_test50'
c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))

reqs, pkts = [], {}
for f in sorted(PKDIR.glob('*.json')):
    p = json.loads(f.read_text(encoding='utf-8')); t = p['ticker']; pkts[t] = p
    reqs.append({'custom_id': t, 'params': {'model': MODEL, 'max_tokens': 5500,
        'messages': [{'role': 'user', 'content': prompt(p)}],
        'output_config': {'format': {'type': 'json_schema', 'schema': SCHEMA}}}})

print(f'submitting batch: {len(reqs)} companies')
batch = c.messages.batches.create(requests=reqs)
while True:
    b = c.messages.batches.retrieve(batch.id)
    if b.processing_status == 'ended':
        break
    time.sleep(20)

out = {}
for r in c.messages.batches.results(batch.id):
    if r.result.type == 'succeeded':
        cc = json.loads(''.join(bl.text for bl in r.result.message.content if bl.type == 'text'))
        p = pkts[r.custom_id]; pr = p.get('prices', {}) or {}
        ab, rel = pr.get('pct_change'), pr.get('relative_pct')
        if ab is not None:
            if abs(ab) <= 1.0: cc['stock_reason_tag'] = 'muted_no_reaction'
            elif rel is not None and abs(rel) <= 1.0: cc['stock_reason_tag'] = 'other'
        out[r.custom_id] = cc

(ROOT / 'data' / 'quarterly' / 'it_q4_2024_test50.json').write_text(
    json.dumps({'companies': out}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'batch ended: {len(out)}/{len(reqs)} classified -> it_q4_2024_test50.json')
