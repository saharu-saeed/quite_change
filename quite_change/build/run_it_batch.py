# -*- coding: utf-8 -*-
"""IT Q4-2025 — Batch run via the direct Anthropic API (Batch API, 50% off).

Reuses the canonical hybrid prompt + locked tag guards (build/wf_it_hybrid.js), inlines
each company's VERIFIED Tempest numbers + P0/P1 stock direction, and attaches web tools
so the model reads the announce-date 決算短信 itself (PIT-strict) — matching the validated
pipeline. Japanese explanations. Output schema-forced (4-part + tags + PIT catalyst).

Usage:
  python build/run_it_batch.py                 # DRY-RUN: build requests, print count (no spend)
  python build/run_it_batch.py --limit 3 --submit   # submit a 3-company test batch
  python build/run_it_batch.py --submit        # submit the full ~99 batch
  python build/run_it_batch.py --poll          # poll the saved batch until done + collect
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

ROOT = Path(__file__).parent.parent
PKTDIR = ROOT / 'data' / 'quarterly' / '_pkts'
DATES = ROOT / 'data' / 'quarterly' / 'it_100_dates.json'
OUT = ROOT / 'data' / 'quarterly' / 'it_q4_2025.json'
BATCH_ID_FILE = ROOT / 'data' / 'quarterly' / '_batch_id.txt'
MODEL = 'claude-sonnet-4-6'

def _env(key):
    for p in [ROOT.parent / '.env', ROOT / '.env']:
        if p.exists():
            for line in p.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line and not line.startswith('#') and line.split('=', 1)[0].strip() == key:
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''

def client():
    key = _env('ANTHROPIC_API_KEY')
    if not key:
        sys.exit('No ANTHROPIC_API_KEY in .env')
    return anthropic.Anthropic(api_key=key)

# ── locked tag guards (mirror of wf_it_hybrid.js) ──
TAG_GUARDS = """business_reason_tag:
  one-off_cost_rolloff（前期の一過性費用の剥落で利益増）/ one_off_gain（当期の一過性利益で利益増）/
  one_off_loss（当期の一過性損失で利益減）/ one_off_gain_rolloff（前期の一過性利益消失で利益減）/
  margin_expansion / margin_compression / volume_demand_growth / price_arpu_growth /
  m&a_consolidation / fx_tailwind / fx_headwind / cyclical_recovery / other

⚠️ ガード①【売上マグニチュード優先＝volume か margin か】★最重要★
   「営業利益が売上より速く伸びた」だけで margin にしてはいけない（それは volume でも margin でも起きる＝判定不能）。
   判定は【売上の伸び率】を第一基準にする：
   ・売上が大きく伸びた（目安：~15%以上の二桁%増）→ volume_demand_growth。
     利益がさらに速く伸びても、それは需要増に対するレバレッジの"副産物"であり margin にしない。
     例：Sakura 売上+44%、unerry +31%、RAKSUL +21%、Capcom +11%(数量増) は volume。
   ・売上が緩やか（一桁%、~10-15%未満）だが、単位あたり採算改善（コスト効率・価格・ミックス）で利益が大きく伸びた
     → margin_expansion。例：NRI +3.8%(利益率16.4→17.6%)、Mercari +2.8%(利益率10→14%)。
   ・中間帯（~10-20%）はナラティブで：「数量を多く売った/提供した」=volume、「同じ規模で採算改善」=margin。
   ・減益（特に純利益マイナス。例 IG Port）→ volume にしない（増益でないため）。利益方向を必ず確認。
⚠️ ガード①c【増収企業(R+)は"増収の要因"を business_reason_tag にする＝一過性損益で代替しない】★重要★
   売上がプラス（増収）の企業では、business_reason_tag は原則として「なぜ売上が伸びたか」を説明するタグ
   （volume_demand_growth / price_arpu_growth / m&a_consolidation / cyclical_recovery / fx_tailwind）から選ぶ。
   一過性損益タグ（one_off_loss / one_off_gain / one_off_gain_rolloff / one-off_cost_rolloff）は【利益ライン】の
   一過性要因であって"増収の理由"ではない。一過性が利益に効いていても、それを business_reason_tag にせず、
   about_business / why_business_moved の本文で説明する（短信のMD&Aで一過性が目立っても、それに引きずられない）。
   ・特に R+S+（増収かつ株高）で one_off_loss を選ばない（増収・株高の説明にならない＝矛盾）。主因は需要/採算/還元側。
   ・one_off_* を business_reason_tag にしてよいのは、増収幅が小さく(一桁%前後)かつ当期の【損益】を一過性が
     明確に支配している場合に限る。判断に迷えば増収要因タグ（volume/margin）を優先する。
   ・純利益変動の主因が為替差損益のスイング → fx_headwind / fx_tailwind（one_off_gain_rolloff ではない）。
   ・投資持株会社等で利益変動の主因が保有株式の評価損益・投資損益（公正価値変動。例 SoftBank ~4.26兆円の投資利益）
     → one_off_gain / one_off_loss（為替が主因でない限り fx_* にしない）。
⚠️ ガード②b【margin_compression＝増収減益の構造圧迫】増収なのに減益で、原因が特定できる一過性損失ではなく
   コスト増・人件費・減価償却・採算悪化（営業段階の構造的圧迫。例 NTT 増収だが営業減益）なら margin_compression。
   本文に具体的な一過性損失（減損額・引当額等）が特定できる時のみ one_off_loss にする。
⚠️ 方向自己チェック：選んだタグの利益方向（gain系=増、loss/gain_rolloff=減）が実際の利益方向と一致するか確認。

stock_reason_tag:
  UP:   capital_return_surprise（【大型】還元が支配的な時のみ）/ rerating_on_growth
  DOWN: consensus_miss / guidance_disappointment / sector_narrative_cooling / valuation_too_high
  flat: muted_no_reaction ／ both: other
⚠️ ガード⓪【方向整合性・絶対・最優先】stock_dir と矛盾するタグは禁止：
   ・stock_dir=UP → capital_return_surprise / rerating_on_growth / other のみ（DOWNタグ consensus_miss・guidance_disappointment等は禁止）。
   ・stock_dir=DOWN → consensus_miss / guidance_disappointment / sector_narrative_cooling / valuation_too_high / other のみ（UPタグ禁止）。
   ・stock_dir=FLAT → muted_no_reaction（ガード⑤）。
   弱いガイダンス等のネガティブ材料があっても、株価が【上昇】したなら、上昇の理由をUP側タグで説明する
   （例 MIXI：株価+8.4%上昇＋大型還元(総還元性向100%超・自己株式取得)が支配的 → capital_return_surprise。
     翌期ガイダンスが弱くても株価は上がっているので guidance_disappointment は禁止）。
⚠️ ガード③【実績ミス vs ガイダンス失望をデータで判別】株価DOWNの理由は街予想の数値なしで以下の基準で決める：
  ・consensus_miss ＝【当期の"実績"】が市場の期待に届かなかった時。判定（数値捏造不要）：
     当期が減益（特に純利益の大幅減）／増益でも小幅、かつ株価が「市場が横ばい〜上昇の中で」下落
     （Tier2が個別要因/逆行を示す）。→ 文章は「実績が市場の期待に届かなかった」と正直に（コンセンサス数値は書かない）。
  ・guidance_disappointment ＝【翌期の"業績予想"が実際に弱い】時のみ。判定：翌期ガイダンスが前年比マイナス、
     または当期の実勢(run-rate)を明確に下回り、かつそれが主たる失望要因。翌期予想が前年比プラスで妥当なら使わない。
  ・❌最頻の誤り：「下落した＋ガイダンスが存在する」だけで guidance_disappointment にしない。
     実績が弱くて下げたなら consensus_miss、翌期予想が実際に弱い時だけ guidance_disappointment。
⚠️ ガード④【UP側の判別＝growth / capital_return を取り違えない】株価UPの理由：
  ・rerating_on_growth ＝【実際に増収増益の"成長"】があり、かつ【株価が"個別要因"で上昇】(Tier2がcompany_specific)の時のみ。
     次は rerating_on_growth にしない：
     - 株価が相場つれ（Tier2がwith_market＝対TOPIXほぼ±0。例 en Japan +7.26% vs 市場+7.17%、相対+0.09%）
       → muted_no_reaction または other（個別の成長評価ではない）。
     - 減収（売上マイナス。例 Square Enix 売上-8.9%）や、利益"回復"が前期一過性損失の剥落に過ぎない場合
       → growth ではない。capital_return が無ければ other（増益の質を踏まえ rerating は避ける）。
     - 株高の主因が大型還元（自社株買い・消却・特別増配）の場合 → capital_return_surprise。
  ・capital_return_surprise ＝【新規または大型の株主還元が株高の支配的要因】の時。
     決算短信の【後発事象/自己株式取得/消却/増配】の記載を確認（例 MIXI：2.4百万株消却＋増配＋総還元性向100%超）。
     年度厳守：この決算短信に記載の還元のみ（前年/翌年と混同しない）。
  ・小幅増配だけで株価上昇＝rerating_on_growth（小幅増配は capital_return_surprise ではない）。
⚠️ ガード⑤【flatは"絶対値"で判定・例外なし】騰落の方向は【絶対値の騰落率】で決める。±1%以内なら
   【他の全材料（弱いガイダンス・対TOPIX出遅れ等）に優先して】必ず muted_no_reaction とする。例外なし。
   stock_dir=FLAT と明示されていれば、何があっても down系タグ（consensus_miss等）にしてはいけない。
   相対比較は文章の彩りとしてのみ使い、タグは flat のまま。
⚠️ ガード⑥【一過性は"原因"の時だけ＝caused-vs-overcame】one-off系は、一過性項目が
   【具体的に特定でき(金額/名称)】かつ【その変動の"実際の原因"】である時のみ使う。
   ❌「利益が大きく伸びた/減っただけ」では one-off にしない（過剰検出の禁止）。
   ★克服(despite)テスト：問い「この一過性が変動を"引き起こした"のか、会社がそれ"にもかかわらず"動いたのか？」。
     一過性を克服して実力で伸びた場合は、その一過性ではなく【実際のドライバー】をタグ付けする。
     例：NRIは前期の海外子会社売却益の剥落（逆風）を、本業の営業利益+12%(実力)で吸収して増益
       → one_off_gain_rolloff ではなく margin_expansion（売上+3.8%と緩やか＝ガード①）。
   特定の一過性が無く採算改善が主因なら margin_expansion（例 Mercari）。前期の特定一過性"利益"が今期消失し
   "それが減益の主因"なら one_off_gain_rolloff。
   ★ガード②優先：原因が【為替】なら fx_headwind / fx_tailwind（one_off_gain_rolloff にしない）。"""

SCHEMA = {
    'type': 'object',
    'properties': {
        'ticker': {'type': 'string'}, 'tier': {'type': 'string'},
        'business_reason_tag': {'type': 'string'}, 'stock_reason_tag': {'type': 'string'},
        'cited_catalyst': {'type': 'string'}, 'catalyst_source_date': {'type': 'string'},
        'overview': {'type': 'string'}, 'about_business': {'type': 'string'},
        'why_business_moved': {'type': 'string'}, 'why_stock_moved': {'type': 'string'},
        'sources': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['ticker', 'tier', 'business_reason_tag', 'stock_reason_tag', 'cited_catalyst',
                 'catalyst_source_date', 'overview', 'about_business', 'why_business_moved',
                 'why_stock_moved', 'sources'],
    'additionalProperties': False,
}

def num_summary(pkt):
    n = pkt.get('numbers', {}) or {}
    ov = n.get('_pit_override') or {}
    # ── PIT NUMBERS GATE ──
    # If Tempest's figures are restated (訂正) or missing, they are NOT the announce-date
    # values. Without a vetted override, do NOT assert them — have the model read the
    # headline figures from the primary 決算短信 numbers table (now guaranteed primary-PDF).
    if pkt.get('needs_tanshin') and not ov:
        reason = pkt.get('needs_tanshin_reason', '')
        why = ("Tempestのこの期の財務数値は『訂正版（訂正有報）』で、発表時点の値ではない"
               if reason == 'restated_use_original'
               else "Tempestにこの期の確定数値が無い／不完全")
        lines = [f"⚠️ {why}。",
                 "売上高・営業利益・純利益とその前年比（増収/減益等）は、必ず下記の決算資料（発表日の決算短信"
                 "または有価証券報告書の原本）の【経営成績】の数値表から読み取って使うこと。Tempest由来の数値・金額・前年比は一切引用しない。"]
        py = n.get('prior_year_yoy') or {}
        if py:
            lines.append(f"参考（前期自体のYoY・一過性の手掛かりのみ。当期数値には使わない）: "
                         f"前期({py.get('period_end')}) 営業{py.get('op_pct')}% 純益{py.get('net_pct')}%")
        return "\n".join(lines)
    pick = lambda k: ov.get(k) if ov.get(k) is not None else n.get(k)
    rev, op, net = pick('rev_pct'), pick('op_pct'), pick('net_pct')
    py = n.get('prior_year_yoy') or {}
    fmt = lambda v: f"{v}%" if v is not None else "（不明・決算短信本文から補う）"
    # absolute figures in 億円 — AUTHORITATIVE. Use these for the headline 売上/利益額.
    def oku(k):
        v = n.get(k)
        try: return f"{float(v)/1e8:,.0f}億円"
        except (TypeError, ValueError): return None
    abs_parts = [f"売上高 {oku('net_sales')}" if oku('net_sales') else '',
                 f"営業利益 {oku('operating_profit')}" if oku('operating_profit') else '',
                 f"純利益 {oku('profit')}" if oku('profit') else '']
    abs_line = " / ".join(p for p in abs_parts if p)
    lines = [f"売上高 前年比 {fmt(rev)} / 営業利益 前年比 {fmt(op)} / 純利益 前年比 {fmt(net)}"]
    if abs_line:
        lines.append(f"【金額（億円・確定値。見出しの売上・利益額は必ずこれを使う。本文から別の数値を持ち込まない）】{abs_line}")
        lines.append("⚠️ 一過性項目の金額（減損額・売却益等）を本文から引用する時は桁を必ず確認（億/百万の取り違え厳禁）。確信が持てなければ金額を書かず定性的に述べる。")
    if ov:
        lines.append("（注：Tempestの値は訂正版のため、決算短信原本の値を優先：" +
                     f"売上{ov.get('rev_pct')}% 営業{ov.get('op_pct')}% 純益{ov.get('net_pct')}%）")
    if py:
        lines.append(f"前期({py.get('period_end')})自体のYoY: 営業{py.get('op_pct')}% 純益{py.get('net_pct')}%（一過性の有無の手掛かり）")
    if pkt.get('needs_tanshin'):
        lines.append("⚠️ Tempest数値が不完全/欠落。売上・利益の数値は決算短信本文から補うこと。")
    return "\n".join(lines)

def prompt(pkt):
    t = pkt['ticker']; name = pkt.get('name_jp') or pkt.get('name') or t
    pe = pkt['period_end']; announce = pkt['announce_date']; tier = pkt.get('tier', 'mid')
    pr = pkt.get('prices', {})
    pct = pr.get('pct_change'); sdir = (pr.get('stock_dir') or 'flat')
    fy = f"{pe[:4]}年{int(pe[5:7])}月期"
    why_excerpt = (pkt.get('why_text') or '')[:1800]
    return f"""あなたは日本株アナリスト。{t} {name} の{fy}決算を分析し、普通の人が読んで分かる4部構成の説明を日本語で書く。

【検証済みの数値（覆さない）】
{num_summary(pkt)}
株価リアクション（発表日P0→10営業日後P1、実株価で検証済み）: {pct}% → stock_dir={sdir.upper()}。この方向は覆さない。

【「理由」は発表日（{announce}）の決算短信を読んで書く（最重要・PIT厳守）】
WebSearch で {name}（{t}）の{fy}【決算短信】（{announce}前後に適時開示で発表）の公式IR/PDFを特定し、WebFetch で本文を読む。
 ⚠️ 後日のEDINET有報や別四半期の資料は使わない。{announce}発表の決算短信そのものに基づく。
 ⚠️【資本還元イベントの年度厳守】自社株買い・増配は、この{fy}決算短信に記載のもののみ引用可。前年/翌年と混同しない。
    catalyst_source_date に「{announce}発表の決算短信」と明記。確認できなければ cited_catalyst="この決算で新規の資本還元発表なし"。
{'【一過性プローブ】利益と売上の乖離があれば原因（減損・引当・売却益・為替差損等）を本文で確認。前期費用の剥落か当期の損益かを区別。' if tier in ('large','hard') else '【具体ドライバー必須】業績の具体的ドライバー（製品・事業の実名）とこの決算のカタリストを決算短信本文から必ず拾う（「セグメントが伸びた」は不可）。'}

参考（後日のEDINET有報の抜粋。文脈用。カタリストは上の決算短信から取ること）:
{why_excerpt}

{TAG_GUARDS}

【4部構成・各3〜4文・物語的で詳しく・平易（専門用語は日常語に）・具体的（実際のドライバーを書く。「セグメントが伸びた」は不可）】
 overview（会社について）: 何をする会社か、主力事業と戦略を物語的に。業績数字は書かない。
 about_business（業績について）: 今期の売上・営業利益・純利益がどう動いたかを数字（%）を言葉で。
  ⚠️営業利益と純利益の伸びが乖離する場合、後段の「理由」で説明する利益ライン（一過性が直撃するのは多くは営業利益）を必ず示す。
  ⚠️後段の「理由」と矛盾する表面原因（「コスト削減」「効率化」等）を断定しない。「効率化のように見えるが実際の理由は別」と伏線を張る。
 why_business_moved（業績が動いた理由）: 決算短信に基づく具体的な理由を物語的に（ガード①②適用）。一過性は可能なら金額も。
 why_stock_moved（株価が動いた理由）: {sdir}の理由を物語的に（ガード③④適用、カタリストはこの決算のもの）。「市場は成長ではなく予想超えを評価する」等、株価ロジックが分かるように。

返却(JSON): ticker="{t}", tier="{tier}", business_reason_tag, stock_reason_tag, cited_catalyst, catalyst_source_date, overview, about_business, why_business_moved, why_stock_moved, sources"""

WEB_TOOLS = [
    {'type': 'web_search_20260209', 'name': 'web_search'},
    {'type': 'web_fetch_20260209', 'name': 'web_fetch'},
]

def build_requests(limit=None):
    pkts = sorted(PKTDIR.glob('*.json'))
    reqs = []
    for f in pkts:
        pkt = json.loads(f.read_text(encoding='utf-8'))
        if not pkt.get('prices', {}).get('stock_dir'):
            continue
        reqs.append(Request(
            custom_id=pkt['ticker'],
            params=MessageCreateParamsNonStreaming(
                model=MODEL, max_tokens=4000,
                messages=[{'role': 'user', 'content': prompt(pkt)}],
                tools=WEB_TOOLS,
                output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}},
            ),
        ))
        if limit and len(reqs) >= limit:
            break
    return reqs

def collect(c, batch_id):
    companies = {}
    for res in c.messages.batches.results(batch_id):
        if res.result.type != 'succeeded':
            print(f'  {res.custom_id}: {res.result.type}'); continue
        msg = res.result.message
        txt = next((b.text for b in msg.content if b.type == 'text'), '')
        try:
            companies[res.custom_id] = json.loads(txt)
        except Exception:
            print(f'  {res.custom_id}: unparseable output')
    json.dump({'companies': companies}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\nSaved {len(companies)} companies → {OUT}')

def main():
    args = sys.argv[1:]
    c = client()
    if '--poll' in args:
        bid = BATCH_ID_FILE.read_text().strip()
        print(f'Polling batch {bid} ...')
        while True:
            b = c.messages.batches.retrieve(bid)
            rc = b.request_counts
            print(f'  status={b.processing_status} done={rc.succeeded} err={rc.errored} proc={rc.processing}')
            if b.processing_status == 'ended':
                break
            time.sleep(60)
        collect(c, bid)
        return

    limit = None
    if '--limit' in args:
        limit = int(args[args.index('--limit') + 1])
    reqs = build_requests(limit)
    print(f'Built {len(reqs)} batch requests (model={MODEL}, web tools on, schema-forced).')
    if '--submit' not in args:
        print('DRY-RUN. Re-run with --submit to send (and --limit N to test small first).')
        print('Sample custom_ids:', [r['custom_id'] for r in reqs[:8]])
        return
    batch = c.messages.batches.create(requests=reqs)
    BATCH_ID_FILE.write_text(batch.id)
    print(f'SUBMITTED batch {batch.id}  status={batch.processing_status}')
    print(f'Poll with: python build/run_it_batch.py --poll')

if __name__ == '__main__':
    main()
