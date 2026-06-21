# -*- coding: utf-8 -*-
"""Grounding sanity-check on a MAIN sample: OLD (tables-only text + committed tags) vs
NEW (MD&A text + staged tags). Confirms the test-50 lift (16%->100%) holds on the main set.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).parent.parent
Q = ROOT / 'data' / 'quarterly'
sys.path.insert(0, str(ROOT / 'build'))
from run_it_batch import _env, MODEL
import anthropic
c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))

# tag-changed companies (where grounding quality matters most) + a few unchanged
SAMPLE = {'2024': ['3635', '9401', '9684', '4385', '3659', '9468', '9984', '3923'],
          '2025': ['4716', '6055', '9409', '4264', '4751', '4443', '4478', '4385']}
DIRS = {'2024': ('_pkts_2024', '_pkts_2024_mdna', 'it_q4_2024.json', 'it_q4_2024_mdna.json'),
        '2025': ('_pkts', '_pkts_mdna', 'it_q4_2025.json', 'it_q4_2025_mdna.json')}
SCHEMA = {'type': 'object', 'properties': {'business_grounded': {'type': 'boolean'},
    'narrative_faithful': {'type': 'boolean'}, 'issue': {'type': 'string'}},
    'required': ['business_grounded', 'narrative_faithful', 'issue'], 'additionalProperties': False}

def jp(g, o):
    return f"""決算短信抜粋と生成された分類を厳格に検証。
【短信抜粋】
{g[:7000]}
【分類】business_reason_tag: {o.get('business_reason_tag')}
why_business_moved: {o.get('why_business_moved','')[:600]}
判定: business_grounded=業績変動の原因が短信本文に明記されているか(推測/一般論はfalse)。narrative_faithful=数値・事実が短信に実在するか。issue=問題を短く。"""

reqs = {}
for yr, tickers in SAMPLE.items():
    olddir, newdir, oldf, newf = DIRS[yr]
    oldo = json.loads((Q / oldf).read_text(encoding='utf-8'))['companies']
    newo = json.loads((Q / newf).read_text(encoding='utf-8'))['companies']
    for t in tickers:
        for variant, pdir, outc in [('OLD', olddir, oldo), ('NEW', newdir, newo)]:
            pf = Q / pdir / f'{t}.json'
            if not pf.exists() or t not in outc:
                continue
            g = json.loads(pf.read_text(encoding='utf-8')).get('tanshin_text', '') or json.loads(pf.read_text(encoding='utf-8')).get('why_text', '')
            cid = f'{yr}_{t}_{variant}'
            reqs[cid] = {'custom_id': cid, 'params': {'model': MODEL, 'max_tokens': 500,
                'messages': [{'role': 'user', 'content': jp(g, outc[t])}],
                'output_config': {'format': {'type': 'json_schema', 'schema': SCHEMA}}}}

print(f'sanity batch: {len(reqs)} (sample x OLD/NEW)')
batch = c.messages.batches.create(requests=list(reqs.values()))
while True:
    b = c.messages.batches.retrieve(batch.id)
    if b.processing_status == 'ended': break
    time.sleep(20)
res = {}
for r in c.messages.batches.results(batch.id):
    if r.result.type == 'succeeded':
        res[r.custom_id] = json.loads(''.join(bl.text for bl in r.result.message.content if bl.type == 'text'))

for variant in ['OLD', 'NEW']:
    vs = [v for k, v in res.items() if k.endswith(variant)]
    bg = sum(1 for v in vs if v['business_grounded']); nf = sum(1 for v in vs if v['narrative_faithful'])
    print(f'{variant}: business_grounded {bg}/{len(vs)} ({100*bg//max(len(vs),1)}%) | narrative_faithful {nf}/{len(vs)} ({100*nf//max(len(vs),1)}%)')
