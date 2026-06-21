# -*- coding: utf-8 -*-
"""Per-company grounding gate for theme membership (cause-not-mention).
For each theme member, the LLM reads the company's ACTUAL filing grounding and confirms the
theme driver is NAMED AS THE CAUSE of the move — not merely mentioned. Members that fail are
DROPPED. Writes themes_verified.json (the surviving memberships) + a dropped-list report.
Commits nothing to the run files. Themes are layered on existing mechanical tags (no new tags).
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from run_it_batch import _env, MODEL
import anthropic

# 7 accepted themes: canonical -> {ja desc, base mechanical tag, members "year:ticker"}
THEMES = {
 'invoice_eltax_regulatory_demand': {'ja':'インボイス制度・電子帳簿保存法改正による特需（バックオフィス/会計SaaS・ERPの需要増）','base':'volume_demand_growth',
    'members':['2024:3994','2024:4733','2025:3994','2025:4733','2025:9746']},
 'ai_infrastructure_gpu_demand_growth': {'ja':'生成AI・GPUインフラ需要による高成長','base':'volume_demand_growth',
    'members':['2025:3778','2025:3915','2025:4382']},
 'cybersecurity_investment_demand': {'ja':'企業向けサイバーセキュリティ投資拡大による増収','base':'volume_demand_growth',
    'members':['2025:3762','2025:4264','2025:4493']},
 'preemptive_headcount_investment_margin_lag': {'ja':'先行的な人材採用・エンジニア人件費増による増収減益（先行投資コスト）','base':'margin_compression',
    'members':['2024:2317','2024:3636','2024:3697','2024:4071','2024:4480','2024:4812']},
 'telecom_5g_capex_rakuten_competition_cost': {'ja':'5G設備投資の償却負担増・楽天モバイル参入による競争激化に伴うコスト増','base':'margin_compression',
    'members':['2024:9432','2024:9433','2024:9434']},
 'mobile_game_title_natural_decay': {'ja':'モバイルゲーム既存タイトルの自然減衰（課金逓減）による減収','base':'margin_compression',
    'members':['2024:3656','2024:3668','2024:3765']},
 'terrestrial_tv_ad_structural_decline': {'ja':'地上波テレビ広告収入の構造的減少','base':'margin_compression',
    'members':['2024:9404','2024:9409','2024:9413']},
}

def ground(yr, t):
    d = '_pkts' if yr == '2025' else '_pkts_2024'
    f = ROOT / 'data' / 'quarterly' / d / f'{t}.json'
    if not f.exists(): return ''
    p = json.loads(f.read_text(encoding='utf-8'))
    return (p.get('tanshin_text') or p.get('why_text') or '')[:3000]

SCHEMA = {'type':'object','properties':{'verdicts':{'type':'array','items':{'type':'object',
    'properties':{'member':{'type':'string'},'named_as_cause':{'type':'boolean'},'evidence':{'type':'string'}},
    'required':['member','named_as_cause','evidence'],'additionalProperties':False}}},
    'required':['verdicts'],'additionalProperties':False}

def main():
    c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))
    verified = {}; dropped = []; ti = to = 0
    for name, th in THEMES.items():
        blocks = []
        for m in th['members']:
            yr, t = m.split(':'); g = ground(yr, t) or '(grounding empty)'
            blocks.append(f'=== member {m} ===\n{g}')
        prompt = f"""テーマ「{th['ja']}」。
各メンバー企業の決算資料抜粋を読み、このテーマのドライバーが当該企業の業績/株価が動いた【原因】として本文に明記されているかを判定せよ。
単なる言及（業界一般論・リスク列挙）は named_as_cause=false。原因として具体的に述べられていれば true。
evidence に根拠の短い引用（無ければ「該当記述なし」）。

{chr(10).join(blocks)}"""
        m = c.messages.create(model=MODEL, max_tokens=2000, messages=[{'role':'user','content':prompt}],
                              output_config={'format':{'type':'json_schema','schema':SCHEMA}})
        ti += m.usage.input_tokens; to += m.usage.output_tokens
        res = json.loads(''.join(b.text for b in m.content if b.type=='text'))
        keep = []
        for v in res['verdicts']:
            if v['named_as_cause']:
                keep.append(v['member'])
            else:
                dropped.append((name, v['member'], v['evidence'][:80]))
        verified[name] = {'ja': th['ja'], 'base': th['base'], 'members': keep}
        print(f"{name}: kept {len(keep)}/{len(th['members'])}")
    (ROOT/'data'/'quarterly'/'themes_verified.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'\nDROPPED (cause not named — only mentioned):')
    for nm,mem,ev in dropped: print(f'  {nm}  {mem}: {ev}')
    print(f'\nLLM ${(ti/1e6)*3+(to/1e6)*15:.4f}  -> themes_verified.json')

if __name__ == '__main__':
    main()
