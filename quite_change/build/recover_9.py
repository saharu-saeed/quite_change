# -*- coding: utf-8 -*-
"""Recover the companies that hit pause_turn (over-searched) — synchronous, NO web tools.

Grounds the 'why' in the Tempest packet's 有報 MD&A + one-off excerpts (already fetched),
so the model writes the structured answer in one shot. Merges into it_q4_2025.json.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import anthropic

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from run_it_batch import SCHEMA, TAG_GUARDS, num_summary, _env  # reuse

PKTDIR = ROOT / 'data' / 'quarterly' / '_pkts'
OUT = ROOT / 'data' / 'quarterly' / 'it_q4_2025.json'
MODEL = 'claude-sonnet-4-6'

def prompt_notools(pkt):
    t = pkt['ticker']; name = pkt.get('name_jp') or pkt.get('name') or t
    pe = pkt['period_end']; announce = pkt['announce_date']; tier = pkt.get('tier', 'mid')
    pr = pkt.get('prices', {}); pct = pr.get('pct_change'); sdir = (pr.get('stock_dir') or 'flat')
    fy = f"{pe[:4]}年{int(pe[5:7])}月期"
    why = (pkt.get('why_text') or '')[:4500]
    prior = (pkt.get('prior_year_oneoff_text') or '')[:2000]
    return f"""あなたは日本株アナリスト。{t} {name} の{fy}決算を分析し、普通の人が読んで分かる4部構成の説明を日本語で書く。

【検証済みの数値（覆さない）】
{num_summary(pkt)}
株価リアクション（実株価で検証済み）: {pct}% → stock_dir={sdir.upper()}。覆さない。

【理由は以下の決算資料抜粋に基づいて書く（PIT厳守。これ以外の後日資料は使わない）】
--- 当期 有報MD&A/一過性抜粋 ---
{why}
--- 前期 一過性抜粋（剥落判定用） ---
{prior}
⚠️ 資本還元（自社株買い・増配）は上記抜粋に明記がある場合のみ引用。年度を混同しない。
   catalyst_source_date に出典を明記。確認できなければ cited_catalyst="この決算で新規の資本還元発表なし"。

{TAG_GUARDS}

【4部構成・各3〜4文・物語的で詳しく・平易・具体的（「セグメントが伸びた」は不可）】
 overview: 何をする会社か、主力事業と戦略を物語的に。業績数字は書かない。
 about_business: 売上・営業利益・純利益の動きを数字（%）を言葉で。営業利益と純利益が乖離する場合は理由側で説明する利益ラインを示す。表面原因（コスト削減等）を断定しない。
 why_business_moved: 上記抜粋に基づく具体的理由を物語的に（ガード①②、一過性は金額も）。
 why_stock_moved: {sdir}の理由を物語的に（ガード③④、市場ロジックが分かるように）。

返却(JSON): ticker="{t}", tier="{tier}", business_reason_tag, stock_reason_tag, cited_catalyst, catalyst_source_date, overview, about_business, why_business_moved, why_stock_moved, sources"""

def main():
    targets = sys.argv[1:] or ['6055', '3844', '5034', '7383', '4385', '4481', '4053', '4443', '4498']
    c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))
    data = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'companies': {}}
    comps = data['companies']
    for t in targets:
        pkt = json.loads((PKTDIR / f'{t}.json').read_text(encoding='utf-8'))
        try:
            msg = c.messages.create(
                model=MODEL, max_tokens=4000,
                messages=[{'role': 'user', 'content': prompt_notools(pkt)}],
                output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}},
            )
            txt = ''.join(b.text for b in msg.content if b.type == 'text')
            comps[t] = json.loads(txt)
            print(f'  {t} OK  {comps[t].get("business_reason_tag")} x {comps[t].get("stock_reason_tag")}')
        except Exception as e:
            print(f'  {t} FAILED: {e}')
        time.sleep(0.5)
    json.dump({'companies': comps}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\nTotal companies now: {len(comps)}')

if __name__ == '__main__':
    main()
