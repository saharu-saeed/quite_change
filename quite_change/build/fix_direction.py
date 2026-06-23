# -*- coding: utf-8 -*-
"""Direction-consistency fix — the stock_reason_tag must match the net move direction.

A guidance_disappointment cannot explain a stock that rose; rerating_on_growth cannot
explain a stock that fell. Re-evaluates only the direction-contradicting cases with a
direction-constrained enum + the same grounding discipline (no expectations inference;
grounded negative required for disappointment; grounded growth for rerating; else
consensus_miss; delayed → delayed_unexplained). Staged only; committed untouched.
"""
from __future__ import annotations
import os, sys, json, glob
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv(ROOT.parent / '.env', override=True)
from anthropic import AnthropicBedrock

YEARS = {'2022': '_pkts_2022_mdna', '2023': '_pkts_2023_mdna', '2024': '_pkts_2024_mdna', '2025': '_pkts_mdna'}
UP_TAGS = ['rerating_on_growth', 'capital_return_surprise', 'consensus_miss', 'delayed_unexplained']
DOWN_TAGS = ['guidance_disappointment', 'consensus_miss', 'delayed_unexplained']


def feats(pp):
    net = pp[-1]; react = pp[2]; mx = max(pp); mn = min(pp)
    return dict(net=net, react=react, mx=mx, mn=mn, ratio=round(abs(react)/max(abs(net),0.1)*100),
                day=max(pp.index(mx), pp.index(mn)))


def main():
    dry = '--dry' in sys.argv
    model = os.environ['BEDROCK_MODEL_ID']
    client = AnthropicBedrock(aws_region=os.environ['AWS_REGION'], aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_key=os.environ['AWS_SECRET_ACCESS_KEY'], aws_session_token=os.environ.get('AWS_SESSION_TOKEN') or None)
    for y in YEARS:
        sp = ROOT / 'data' / 'quarterly' / f'it_q4_{y}.staged.json'
        data = json.loads(sp.read_text(encoding='utf-8')); comps = data['companies']
        pk = {Path(f).stem: json.loads(Path(f).read_text(encoding='utf-8'))
              for f in glob.glob(str(ROOT / 'data' / 'quarterly' / YEARS[y] / '*.json'))}
        targets = []
        for t, c in comps.items():
            d = (pk.get(t, {}).get('prices', {}) or {}).get('stock_dir'); tag = c.get('stock_reason_tag')
            if (tag == 'guidance_disappointment' and d == 'up') or (tag == 'rerating_on_growth' and d == 'down'):
                targets.append((t, d))
        if not targets:
            print(f'[{y}] no contradictions'); continue
        for t, d in targets:
            c = comps[t]; p = pk.get(t, {}); pr = p.get('prices', {}) or {}
            f = feats(c['path_pct']); num = p.get('numbers', {}) or {}
            allowed = UP_TAGS if d == 'up' else DOWN_TAGS
            name = (lambda nj, nn: nj if (nj and nj != 'False') else nn)(p.get('name_jp'), p.get('name')) or t
            schema = {'type': 'object', 'properties': {
                'stock_reason_tag': {'type': 'string', 'enum': allowed},
                'grounded_quote': {'type': 'string'},
                'why_stock_moved': {'type': 'string'}, 'why_stock_moved_en': {'type': 'string'},
                'timing_basis': {'type': 'string', 'enum': ['on_print', 'delayed', 'accumulated', 'mixed']}},
                'required': ['stock_reason_tag', 'grounded_quote', 'why_stock_moved', 'why_stock_moved_en', 'timing_basis'],
                'additionalProperties': False}
            prompt = f"""{t} {name}: 株価は決算後ネット{pr.get('pct_change')}%で方向は【{d}（{'上昇' if d=='up' else '下落'}）】。
この【{d}方向の動き】を説明する stock_reason_tag を選べ（方向と矛盾するタグは選択肢から除外済み）。
値動きの形(事実): 初動{f['react']:.2f}%(netの約{f['ratio']}%) / 最大上昇{f['mx']:.2f}%・最大下落{f['mn']:.2f}%({f['day']}営業日目付近)
今期実績: 売上{num.get('rev_pct')}% 営業利益{num.get('op_pct')}% 純利益{num.get('net_pct')}% / ガイダンス={c.get('guidance_overlay')}

接地ルール(厳守):
・市場コンセンサス/期待は観測不能。「期待を上回った/下回った」だけを根拠にしてはならない。
・{'rerating_on_growth は増収増益や上方ガイダンス等の接地事実で上昇を説明できる時のみ。' if d=='up' else 'guidance_disappointment は減益・ガイダンス下方・減配・減損等の接地した負の事実がある時のみ（grounded_quote に引用）。'}
・接地できない場合は consensus_miss（観測不能な期待への反応＝正直な残余）。
・大きな動きが発表当日でなく数営業日後なら delayed_unexplained。
・why_stock_moved: 形・タイミングは事実、原因は短信明記時のみ、捏造禁止、平易な日本語2〜4文＋英訳。

決算短信本文:
{(p.get('tanshin_text') or p.get('why_text') or '')[:5500]}

返却(JSON): stock_reason_tag, grounded_quote, why_stock_moved, why_stock_moved_en, timing_basis"""
            msg = client.messages.create(model=model, max_tokens=1000,
                messages=[{'role': 'user', 'content': prompt}],
                output_config={'format': {'type': 'json_schema', 'schema': schema}})
            r = json.loads(''.join(b.text for b in msg.content if b.type == 'text'))
            tag = 'delayed_unexplained' if r['timing_basis'] == 'delayed' else r['stock_reason_tag']
            old = c['stock_reason_tag']
            c['stock_reason_tag'] = tag; c['why_stock_moved'] = r['why_stock_moved']
            c['why_stock_moved_en'] = r['why_stock_moved_en']; c['timing_basis'] = r['timing_basis']
            c['needs_enrichment'] = (tag == 'delayed_unexplained')
            if r.get('grounded_quote'):
                c['disappointment_grounding'] = r['grounded_quote']
            print(f'  [{y}] {t} ({d}): {old} → {tag} ({r["timing_basis"]})')
        if not dry:
            sp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('done.' if not dry else '--dry')


if __name__ == '__main__':
    main()
