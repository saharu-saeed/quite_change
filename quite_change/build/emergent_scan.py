# -*- coding: utf-8 -*-
"""Emergent-reason scan — DETECT new common reasons automatically (add them DELIBERATELY).

After a quarter is tagged, this reads the narratives that already exist and surfaces
recurring REASONS/THEMES the fixed bucket vocabulary doesn't capture:
  • mechanical reasons piling up in `other`, AND
  • cross-cutting era/event themes spread across many tags (e.g., a pandemic, an AI-capex
    wave, a regulation) — the COVID case: it would be split across volume/margin/etc. but
    all share one real driver.

It does NOT invent per-company labels (that fragments the pattern). It clusters into ONE
consistent candidate per theme, lists the member companies, and flags whether the theme is
announce-date-groundable — so a human can add it as a proper bucket with a clean trigger.

One cheap LLM call over existing narratives (~$0.05-0.25). Usage:
  python build/emergent_scan.py [run.json]   # default data/quarterly/it_q4_2025.json
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import anthropic

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from run_it_batch import _env, MODEL  # reuse key loader + model

RUN = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'quarterly' / 'it_q4_2025.json'
OUT = RUN.with_name(RUN.stem + '_emergent_candidates.json')

VOCAB = ("business: one-off_cost_rolloff, one_off_gain, one_off_loss, one_off_gain_rolloff, "
         "margin_expansion, margin_compression, volume_demand_growth, price_arpu_growth, "
         "m&a_consolidation, fx_tailwind, fx_headwind, cyclical_recovery, other ; "
         "stock: capital_return_surprise, rerating_on_growth, consensus_miss, "
         "guidance_disappointment, sector_narrative_cooling, valuation_too_high, "
         "muted_no_reaction, other")

SCHEMA = {
    'type': 'object',
    'properties': {
        'candidates': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'theme_name': {'type': 'string'},
                'description': {'type': 'string'},
                'tickers': {'type': 'array', 'items': {'type': 'string'}},
                'spans_tags': {'type': 'string'},
                'announce_date_groundable': {'type': 'string'},
                'suggested_bucket': {'type': 'string'},
            },
            'required': ['theme_name', 'description', 'tickers', 'spans_tags',
                         'announce_date_groundable', 'suggested_bucket'],
            'additionalProperties': False,
        }}
    },
    'required': ['candidates'], 'additionalProperties': False,
}

def main():
    comps = json.loads(RUN.read_text(encoding='utf-8'))['companies']
    lines = []
    for t, c in comps.items():
        wb = (c.get('why_business_moved') or '')[:280]
        ws = (c.get('why_stock_moved') or '')[:280]
        lines.append(f"{t} [{c.get('business_reason_tag')}/{c.get('stock_reason_tag')}] 業績:{wb} 株価:{ws}")
    blob = "\n".join(lines)
    prompt = f"""以下は{len(comps)}社の決算「理由」ナラティブ（既存タグ付き）。
現在のバケット語彙：{VOCAB}

タスク：この語彙では【うまく捉えられていない、複数社に共通する"理由・テーマ"】を発見せよ。特に：
 (1) `other` に溜まっている新種の理由、(2) 既存タグをまたいで多数社に共通する時代/イベント要因
   （例：パンデミック、AI設備投資ブーム、特定の規制・補助金、半導体サイクル等）。
   COVIDの例：需要急増(volume)と需要消失(margin/減益)に散らばるが、根本ドライバーは1つ。

ルール：
 ・社ごとにバラバラの名前を付けない。同じテーマは【1つの一貫した候補名】に集約する。
 ・各候補に：theme_name、description、該当tickers、spans_tags（どの既存タグにまたがるか）、
   announce_date_groundable（発表日の決算短信で確認できるか yes/部分的/no）、suggested_bucket（新タグ名の提案）。
 ・最低2社以上に共通するテーマのみ。無ければ candidates を空配列に。
 ・確実なものだけ。憶測で時代テーマを作らない。

ナラティブ：
{blob}"""
    c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))
    msg = c.messages.create(model=MODEL, max_tokens=8000,
                            messages=[{'role': 'user', 'content': prompt}],
                            output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}})
    res = json.loads(''.join(b.text for b in msg.content if b.type == 'text'))
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
    cands = res.get('candidates', [])
    print(f'Emergent candidates: {len(cands)}  ->  {OUT.name}')
    for x in cands:
        print(f"\n  • {x['theme_name']}  ({len(x['tickers'])} cos, groundable={x['announce_date_groundable']})")
        print(f"    {x['description'][:140]}")
        print(f"    spans: {x['spans_tags']} | suggest bucket: {x['suggested_bucket']}")
        print(f"    tickers: {', '.join(x['tickers'][:15])}")

if __name__ == '__main__':
    main()
