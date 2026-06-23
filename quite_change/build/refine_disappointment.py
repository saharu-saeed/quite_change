# -*- coding: utf-8 -*-
"""Refine pass — restore consensus_miss as the HONEST residual (fixes un-dump over-reach).

The combined stock-side pass emptied consensus_miss to 0 by over-assigning
guidance_disappointment — in several cases justified only by "below market
expectations/consensus", an inference we CANNOT make (no consensus data, PIT-clean).
This re-runs only the suspect set with a tightened rule:
  • guidance_disappointment requires a GROUNDED negative in the filing (guidance cut /
    profit decline / margin compression / dividend cut / segment loss / impairment).
  • stock fell but results good + guidance neutral/raised + NO grounded negative
    → consensus_miss (honest residual: reaction to unobservable expectations).
  • the "missed market expectations" inference is forbidden as grounding.
Path features reused from stored path_pct (no re-fetch). Staged only; committed untouched.

  python build/refine_disappointment.py --dry
  python build/refine_disappointment.py
"""
from __future__ import annotations
import os, sys, json, glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).parent.parent
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv(ROOT.parent / '.env', override=True)
from anthropic import AnthropicBedrock

YEARS = {'2022': '_pkts_2022_mdna', '2023': '_pkts_2023_mdna', '2024': '_pkts_2024_mdna', '2025': '_pkts_mdna'}
TAGS = ['rerating_on_growth', 'guidance_disappointment', 'consensus_miss',
        'capital_return_surprise', 'delayed_unexplained']
SCHEMA = {'type': 'object', 'properties': {
    'stock_reason_tag': {'type': 'string', 'enum': TAGS},
    'grounded_negative_quote': {'type': 'string'},
    'why_stock_moved': {'type': 'string'}, 'why_stock_moved_en': {'type': 'string'},
    'timing_basis': {'type': 'string', 'enum': ['on_print', 'delayed', 'accumulated', 'mixed']},
    'confidence': {'type': 'string', 'enum': ['high', 'med', 'low']}},
    'required': ['stock_reason_tag', 'grounded_negative_quote', 'why_stock_moved',
                 'why_stock_moved_en', 'timing_basis', 'confidence'], 'additionalProperties': False}


def feats_from_path(pp):
    if not pp or len(pp) < 4:
        return None
    net = pp[-1]; react = pp[2]; mx = max(pp); mn = min(pp)
    return {'net': net, 'react_2d': react, 'ratio': round(abs(react) / max(abs(net), 0.1) * 100),
            'max_up': mx, 'max_dn': mn, 'max_up_day': pp.index(mx), 'max_dn_day': pp.index(mn)}


def build_prompt(t, name, pr, f, num, guid, ground):
    when = f"最大{'上昇' if abs(f['max_up']) >= abs(f['max_dn']) else '下落'}は{max(f['max_up_day'], f['max_dn_day'])}営業日目付近"
    py = (num or {}).get('prior_year_yoy', {}) or {}
    return f"""あなたは日本株アナリスト。{t} {name} の決算後の株価反応を【厳格な接地ルール】で再判定する。

【確定事実(覆さない)】P0={pr.get('p0_date')}({pr.get('p0')})→P1={pr.get('p1_date')}({pr.get('p1')}) ネット{pr.get('pct_change')}% / 対TOPIX{pr.get('relative_pct')}% / 方向={pr.get('stock_dir')}
【値動きの形(事実)】初動(1〜2営業日){f['react_2d']:.2f}%（netの約{f['ratio']}%）／最大上昇{f['max_up']:.2f}%・最大下落{f['max_dn']:.2f}%（{when}）
【今期実績】売上{num.get('rev_pct')}% / 営業利益{num.get('op_pct')}% / 純利益{num.get('net_pct')}% ／前年同期 営業{py.get('op_pct')}%・純{py.get('net_pct')}% ／ガイダンス={guid}
【決算短信 本文(根拠はここだけ)】
{ground}

【★最重要・接地ルール(厳守)】
1. 市場コンセンサス／アナリスト予想／「市場の期待」は当方は保有せず観測不能。
   「実績は良いが市場の期待に届かず失望」という推論で guidance_disappointment を付けては絶対にならない(循環論法・接地不能)。
2. guidance_disappointment は短信に【接地した負の事実】がある時のみ:
   来期ガイダンスの下方/減益予想・今期の減益や営業赤字・利益率の明確な悪化・減配・セグメント損失・減損 等。
   → その該当箇所を grounded_negative_quote に短く引用すること(引用できないなら付けてはならない)。
3. 株価は下落したが、短信は増収増益かつガイダンス据置/上方で、接地した負の事実が無い
   → consensus_miss（観測不能な期待値に対する beat/miss 反応＝正直な"残余"。grounded_negative_quote="")。
4. rerating_on_growth は、実績(増収増益)や上方ガイダンスという接地事実で上昇が説明できる時のみ。
   「期待を上回った」だけが根拠なら consensus_miss。
5. 大きな値動きが発表当日でなく数営業日後(delayed)なら delayed_unexplained。
6. why_stock_moved: 形・タイミングは事実として明記。原因は短信に明記がある時だけ。捏造しない。平易な日本語2〜4文。英訳も。

返却(JSON): stock_reason_tag, grounded_negative_quote, why_stock_moved, why_stock_moved_en, timing_basis, confidence"""


def main():
    args = sys.argv[1:]; dry = '--dry' in args
    model = os.environ['BEDROCK_MODEL_ID']
    client = AnthropicBedrock(aws_region=os.environ['AWS_REGION'], aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_key=os.environ['AWS_SECRET_ACCESS_KEY'], aws_session_token=os.environ.get('AWS_SESSION_TOKEN') or None)
    from collections import Counter
    grand_before = Counter(); grand_after = Counter()
    for y in YEARS:
        sp = ROOT / 'data' / 'quarterly' / f'it_q4_{y}.staged.json'
        data = json.loads(sp.read_text(encoding='utf-8')); comps = data['companies']
        pk = {Path(f).stem: json.loads(Path(f).read_text(encoding='utf-8'))
              for f in glob.glob(str(ROOT / 'data' / 'quarterly' / YEARS[y] / '*.json'))}
        # suspect set: disappointment not aligned to a disappointing overlay, or rerating despite disappointing guidance
        suspects = []
        for t, c in comps.items():
            tag = c.get('stock_reason_tag'); go = c.get('guidance_overlay')
            if (tag == 'guidance_disappointment' and go != 'disappointment') or \
               (tag == 'rerating_on_growth' and go == 'disappointment'):
                suspects.append(t)
        grand_before.update(comps[t].get('stock_reason_tag') for t in suspects)
        print(f'[{y}] refining {len(suspects)} suspect cases...', flush=True)

        def work(t):
            c = comps[t]; p = pk.get(t, {}); pr = p.get('prices', {}) or {}
            f = feats_from_path(c.get('path_pct'))
            if not f:
                return t, None
            ground = (p.get('tanshin_text') or p.get('why_text') or '')[:6000]
            name = (lambda nj, nn: nj if (nj and nj != 'False') else nn)(p.get('name_jp'), p.get('name')) or t
            msg = client.messages.create(model=model, max_tokens=1100,
                messages=[{'role': 'user', 'content': build_prompt(t, name, pr, f, p.get('numbers', {}) or {}, c.get('guidance_overlay'), ground)}],
                output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}})
            return t, json.loads(''.join(b.text for b in msg.content if b.type == 'text'))

        changes = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = [ex.submit(work, t) for t in suspects]
            for fut in as_completed(futs):
                t, r = fut.result()
                if not r:
                    continue
                c = comps[t]; old = c.get('stock_reason_tag')
                tag = 'delayed_unexplained' if r['timing_basis'] == 'delayed' else r['stock_reason_tag']
                c['stock_reason_tag'] = tag
                c['why_stock_moved'] = r['why_stock_moved']; c['why_stock_moved_en'] = r['why_stock_moved_en']
                c['timing_basis'] = r['timing_basis']; c['needs_enrichment'] = (tag == 'delayed_unexplained')
                if r.get('grounded_negative_quote'):
                    c['disappointment_grounding'] = r['grounded_negative_quote']
                if tag != old:
                    changes.append((t, old, tag, r['timing_basis']))
        grand_after.update(comps[t].get('stock_reason_tag') for t in suspects)
        for t, o, n, tb in sorted(changes, key=lambda x: x[2]):
            print(f'   {t}  {o} → {n}  ({tb})')
        print(f'[{y}] changed {len(changes)} of {len(suspects)}')
        if not dry:
            sp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n' + '=' * 60)
    print('SUSPECT-SET before:', dict(grand_before))
    print('SUSPECT-SET after :', dict(grand_after))
    print('--dry (not written)' if dry else 'written to staged (committed untouched).')


if __name__ == '__main__':
    main()
