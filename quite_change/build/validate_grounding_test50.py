# -*- coding: utf-8 -*-
"""Stage 2c — generation validation: grounding / cause-not-mention check over the 50 (Batch API).
For each company the judge reads the 短信 excerpt + the generated output and rules on:
  - business_grounded: is the business_reason_tag NAMED as a cause in the 短信 (not inferred)?
  - narrative_faithful: do the figures/claims in the narrative actually appear in the 短信 (no fabrication)?
  - stock_consistent: is stock_reason_tag consistent with the actual price move (market interpretation,
    not required to be in the 短信)?
Flags any failure. Writes _test50_grounding.json.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from run_it_batch import _env, MODEL
import anthropic

PKDIR = ROOT / 'data' / 'quarterly' / '_pkts_2024_test50'
OUT = json.loads((ROOT / 'data' / 'quarterly' / 'it_q4_2024_test50.json').read_text(encoding='utf-8'))['companies']
c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))

SCHEMA = {'type': 'object', 'properties': {
    'business_grounded': {'type': 'boolean'},
    'narrative_faithful': {'type': 'boolean'},
    'stock_consistent': {'type': 'boolean'},
    'issue': {'type': 'string'}},
    'required': ['business_grounded', 'narrative_faithful', 'stock_consistent', 'issue'],
    'additionalProperties': False}

reqs = {}
for f in sorted(PKDIR.glob('*.json')):
    p = json.loads(f.read_text(encoding='utf-8')); t = p['ticker']
    if t not in OUT:
        continue
    o = OUT[t]; pr = p.get('prices', {}) or {}
    g = (p.get('tanshin_text') or '')[:8500]   # judge must see the SAME text the classifier used
    prompt = f"""決算短信抜粋と、それを基に生成された分類結果を検証せよ。

【決算短信抜粋】
{g}

【生成された分類】
business_reason_tag: {o.get('business_reason_tag')}
stock_reason_tag: {o.get('stock_reason_tag')}（株価2週間リアクション: {pr.get('pct_change')}%）
why_business_moved: {o.get('why_business_moved','')[:500]}
why_stock_moved: {o.get('why_stock_moved','')[:400]}

判定（厳格に）:
- business_grounded: business_reason_tag が示す業績変動の【原因】が短信本文に明記されているか（単なる一般論・推測はfalse）。
- narrative_faithful: why_business_moved 内の数値・事実が短信に実在するか（捏造・矛盾があればfalse）。
- stock_consistent: stock_reason_tag が実際の株価リアクション({pr.get('pct_change')}%)と整合するか（株安なのにcapital_return等は不整合。市場解釈であり短信記載は不要）。
- issue: 問題があれば短く具体的に（なければ「問題なし」）。"""
    reqs[t] = {'custom_id': t, 'params': {'model': MODEL, 'max_tokens': 600,
        'messages': [{'role': 'user', 'content': prompt}],
        'output_config': {'format': {'type': 'json_schema', 'schema': SCHEMA}}}}

print(f'grounding-judge batch: {len(reqs)} companies')
batch = c.messages.batches.create(requests=list(reqs.values()))
while True:
    b = c.messages.batches.retrieve(batch.id)
    if b.processing_status == 'ended':
        break
    time.sleep(20)

res = {}
for r in c.messages.batches.results(batch.id):
    if r.result.type == 'succeeded':
        res[r.custom_id] = json.loads(''.join(bl.text for bl in r.result.message.content if bl.type == 'text'))

(ROOT / 'data' / 'quarterly' / '_test50_grounding.json').write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
bg = sum(1 for v in res.values() if v['business_grounded'])
nf = sum(1 for v in res.values() if v['narrative_faithful'])
sc = sum(1 for v in res.values() if v['stock_consistent'])
n = len(res)
print(f'\n== grounding ({n} judged) ==')
print(f'business_grounded:  {bg}/{n} ({100*bg//n}%)')
print(f'narrative_faithful: {nf}/{n} ({100*nf//n}%)')
print(f'stock_consistent:   {sc}/{n} ({100*sc//n}%)')
print('\nFLAGGED:')
for t, v in res.items():
    if not (v['business_grounded'] and v['narrative_faithful'] and v['stock_consistent']):
        bad = [k for k in ('business_grounded','narrative_faithful','stock_consistent') if not v[k]]
        print(f'  {t} {OUT[t].get("business_reason_tag")}/{OUT[t].get("stock_reason_tag")} FAIL{bad}: {v["issue"][:90]}')
