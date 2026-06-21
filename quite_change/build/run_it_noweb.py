# -*- coding: utf-8 -*-
"""IT Q4-2025 — SAFE no-web-tools runner (Tier 1 + Tier 2). Cheap, PIT-clean, no snowball.

vs the $217 web-tools run: NO web tools at all (no agentic loop -> no token snowball).
Grounding is embedded:
  • Tempest numbers (rev/op/net, PIT override)         — exact, verified
  • Tier 1: announce-date tanshin text if pre-fetched (pkt['tanshin_text']),
            else the 有報 MD&A excerpt (pkt['why_text'])  — the 'why' source
  • Tier 2: stock move vs TOPIX over the same window     — company-specific vs market-wide
Honest-framing rules baked in:
  • Use 対計画比 (vs the company's OWN forecast); say "missed its own forecast by X%",
    NEVER "missed consensus" (we don't have the street number).
  • Expectation-gap rule: if the stock moved MORE than the own-plan-miss explains
    (Tier 2 shows a company-specific move), say so truthfully — "in line with its own
    forecast, yet fell ~X% while the market was flat — the market expected more."

Usage (DRY-RUN by default — builds requests, no spend):
  python build/run_it_noweb.py
  python build/run_it_noweb.py --limit 3 --submit     # 3-company test (needs key spend OK)
  python build/run_it_noweb.py --submit               # full 99
Collect with build/collect_batch.py (robust download).
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from run_it_batch import SCHEMA, TAG_GUARDS, num_summary, _env, MODEL  # reuse

import os
PKTDIR = ROOT / 'data' / 'quarterly' / os.environ.get('PKTDIR_NAME', '_pkts')
OUT = ROOT / 'data' / 'quarterly' / os.environ.get('OUT_FILE', 'it_q4_2025.json')
BATCH_ID_FILE = ROOT / 'data' / 'quarterly' / '_batch_id_noweb.txt'

_JUNK = {'false', 'true', 'none', 'nan', 'null', ''}
def clean(v):
    """Never let a blank/False/None/'False' leak into a prompt."""
    if v is None or v is False or v is True:
        return ''
    s = str(v).strip()
    return '' if s.lower() in _JUNK else s

def pick_name(pkt):
    # authoritative Tempest names first (census names had wrong-company labels, e.g. 3741)
    return (clean(pkt.get('name_official_jp')) or clean(pkt.get('name_official'))
            or clean(pkt.get('name_jp')) or clean(pkt.get('name')) or pkt['ticker'])

def tier2_line(pkt):
    pr = pkt.get('prices', {})
    mp, rel, mt = pr.get('market_pct'), pr.get('relative_pct'), pr.get('move_type')
    if mp is None:
        return ''
    label = {'company_specific': '個別要因（市場と無関係に動いた）',
             'with_market': '市場全体と同方向（相場つれ）',
             'against_market': '市場と逆方向（相場に逆らって動いた）'}.get(mt, mt)
    return (f"\n【株価の相対比較（Tier2・PIT検証済み）】同じ2週間でTOPIX(1306)は{mp:+.2f}%。"
            f"本銘柄は対TOPIXで{rel:+.2f}%（{label}）。"
            f"→ 株価理由はこの相対情報を反映（個別要因か相場つれかを明示）。")

HONEST_RULES = """【正直ルール（必須）】
1. 具体的な【街・アナリストのコンセンサス金額】は持っていないので捏造しない。
   ただし「実績が市場の期待に届かなかった」という趣旨は、当期実績が弱く（減益・小幅増益）かつ
   市場が横ばい〜上昇の中で株価が下落した事実から、数値なしで正直に書いてよい（これがconsensus_missの根拠）。
   抜粋に会社自身の予想(対計画比)があればそれを併記する。
2.【期待ギャップ】実績が会社予想とほぼ同等なのに株価が大きく動いた場合（Tier2が個別要因を示す等）、
   数値を捏造せず正直に：「実績は会社計画とほぼ同等だったが、市場が横ばいの中で株価は約X%下落した。
   市場はそれ以上を期待していたとみられる」のように書く。
3.【ガイダンス失望は実際に弱い時だけ】翌期予想(業績予想)が前年比プラスで妥当なら guidance_disappointment と書かない。
4. 使った根拠だけを書く。確認できない数値・カタリストは書かない。"""

def prompt(pkt):
    t = pkt['ticker']; name = pick_name(pkt)
    pe = pkt['period_end']; announce = pkt['announce_date']; tier = pkt.get('tier', 'mid')
    pr = pkt.get('prices', {}); pct = pr.get('pct_change'); sdir = (pr.get('stock_dir') or 'flat')
    fy = f"{pe[:4]}年{int(pe[5:7])}月期"
    ground = (pkt.get('tanshin_text') or pkt.get('why_text') or '')[:6500]  # fits MD&A prose + summary
    gsrc = '発表日の決算短信' if pkt.get('tanshin_text') else '有価証券報告書（EDINET）MD&A'
    if not ground.strip():  # no filing at all -> do NOT fabricate a why (numbers-only)
        ground = ('（決算資料を取得できませんでした。why_business_moved / why_stock_moved は確定数値とTier2のみに基づき'
                  '限定的に記述し、決算短信本文に基づく具体的カタリスト・一過性・ガイダンスの主張は一切しないこと。'
                  'cited_catalyst="決算資料未取得のため確認不可"。）')
        gsrc = '決算資料なし（数値のみ）'
    prior = (pkt.get('prior_year_oneoff_text') or '')[:1500]
    return f"""あなたは日本株アナリスト。{t} {name} の{fy}決算を分析し、普通の人が読んで分かる4部構成の説明を日本語で書く。
⚠️ 対象会計期間は必ず「{fy}」（period_end={pe}）と表記する。本文中の年度表記もこれに統一し、他の年度（翌期・前期）と取り違えない。

【検証済みの数値（覆さない）】
{num_summary(pkt)}
株価リアクション（発表日P0→10営業日後P1、実株価で検証済み）: {pct}% → stock_dir={sdir.upper()}。覆さない。{tier2_line(pkt)}

【理由は以下の決算資料抜粋に基づく（出典: {gsrc}。これ以外の後日資料・推測は使わない・PIT厳守）】
--- 当期 抜粋 ---
{ground}
--- 前期 一過性抜粋（剥落判定用） ---
{prior}
⚠️ 資本還元（自社株買い・増配）・翌期ガイダンス・対計画比は、上記抜粋に明記がある場合のみ引用。年度を混同しない。
   catalyst_source_date に出典を明記。確認できなければ cited_catalyst="この決算で新規の資本還元発表なし"。
⚠️【単位厳守・桁ミス厳禁】抜粋中の金額は原則「百万円」表記。億円に換算する時は必ず ÷100（例：1,858百万円＝18.6億円、≠186億円／6,454百万円＝64.5億円、≠645億円）。
   セグメント・研究開発費・一過性損益などの金額を引用する際は桁を厳密に確認し、上記【金額（億円・確定値）】の売上規模と整合しない金額（例：一部門の売上が全社売上を超える）は書かない。迷えば百万円のまま、または金額を書かず定性的に述べる。

{TAG_GUARDS}

{HONEST_RULES}

【4部構成・各3〜4文・物語的で詳しく・平易・具体的（「セグメントが伸びた」は不可）】
 overview: 何をする会社か、主力事業と戦略を物語的に。業績数字は書かない。
 about_business: 売上・営業利益・純利益の動きを数字（%）で。営業利益と純利益が乖離する場合は理由側で説明する利益ラインを示す。表面原因（コスト削減等）を断定しない。
 why_business_moved: 上記抜粋に基づく具体的理由を物語的に（ガード①②、一過性は金額も）。
 why_stock_moved: {sdir}の理由を物語的に（ガード③④＋正直ルール＋Tier2の相対情報。市場ロジックが分かるように）。

返却(JSON): ticker="{t}", tier="{tier}", business_reason_tag, stock_reason_tag, cited_catalyst, catalyst_source_date, overview, about_business, why_business_moved, why_stock_moved, sources"""

def build_requests(limit=None):
    reqs = []
    for f in sorted(PKTDIR.glob('*.json')):
        pkt = json.loads(f.read_text(encoding='utf-8'))
        if not pkt.get('prices', {}).get('stock_dir'):
            continue
        reqs.append(Request(custom_id=pkt['ticker'], params=MessageCreateParamsNonStreaming(
            model=MODEL, max_tokens=5500,
            messages=[{'role': 'user', 'content': prompt(pkt)}],
            output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}},
        )))  # NOTE: no tools -> no snowball
        if limit and len(reqs) >= limit:
            break
    return reqs

def main():
    args = sys.argv[1:]
    limit = int(args[args.index('--limit') + 1]) if '--limit' in args else None
    reqs = build_requests(limit)
    print(f'Built {len(reqs)} requests (NO web tools, Tier1+Tier2, honest framing).')
    # show a sample prompt token estimate is done elsewhere; here just dry-run unless --submit
    if '--submit' not in args:
        print('DRY-RUN (no key spend). Add --submit (and --limit N) to send.')
        return
    c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))
    batch = c.messages.batches.create(requests=reqs)
    BATCH_ID_FILE.write_text(batch.id)
    print(f'SUBMITTED {batch.id}. Collect with: python build/collect_batch.py {batch.id}')

if __name__ == '__main__':
    main()
