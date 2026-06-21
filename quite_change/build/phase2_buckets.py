# -*- coding: utf-8 -*-
"""PHASE 2 — assign the approved 26-bucket SPECIFIC reason to all 194 IT companies.

Staged & reversible: reads the committed it_q4_{year}.json + the MD&A-grounded
packets, asks the model for ONE grounded specific_bucket per company (NO web —
PIT-clean, reads the embedded announce-date 決算短信 text only), and writes the
result to it_q4_{year}.staged.json. THE COMMITTED FILES ARE NEVER TOUCHED. A
diff report (committed → staged) is printed; nothing is committed until approved.

Provisional decisions baked in (claude.ai leans — relabel-cheap, not re-classify):
  • 5  media/content kept at full granularity (launch vs decline, hit vs rolloff,
       TV-ad vs streaming) — never merged across direction.
  • 6  BUSINESS reason is the PRIMARY specific_bucket; guidance is layered as a
       separate guidance_overlay (shown prominently in S- quadrants, not primary).
  • 9  the 3 report-stated EVENT buckets included (contract_win / contract_loss_churn
       / backlog_shift).
Honesty rails: a bucket is assigned ONLY if the filing NAMES it as the cause
(cause-not-mention). If the report gives no cause -> no_report_reason_found (the
overlooked-candidate residual). Never fabricated; never "recoverable" (no forecast).

Usage:
  python build/phase2_buckets.py --limit 11        # gold-check (small spend)
  python build/phase2_buckets.py                   # full 194 (staged)
  python build/phase2_buckets.py --year 2025       # one year only
"""
from __future__ import annotations
import os, sys, json, glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT.parent / '.env', override=True)
sys.path.insert(0, str(ROOT / 'build'))
sys.stdout.reconfigure(encoding='utf-8')
from anthropic import AnthropicBedrock
from run_it_batch import num_summary               # verified-number block (reused)

YEARS = {'2022': '_pkts_2022_mdna', '2023': '_pkts_2023_mdna', '2024': '_pkts_2024_mdna', '2025': '_pkts_mdna'}

# ── the approved 26-bucket SPECIFIC vocabulary (23 business/reason + 3 event) ──
# guidance_* are intentionally NOT primary buckets here (decision 6 → overlay).
SPECIFIC_BUCKETS = """specific_bucket（主＝事業側の具体理由を1つ。決算短信が「原因」として明記している時のみ。
   明記がなければ no_report_reason_found。当てはまらなければ other）:
 ── 需要・売上ドライバー ──
  saas_arr_expansion              SaaS・ARR拡大（顧客数増・積み上げ収益）
  cloud_migration_growth          クラウド移行・クラウド売上成長
  cybersecurity_investment_demand サイバーセキュリティ投資需要
  public_sector_it_demand         官公庁・公共IT需要（自治体標準化・ガバメントクラウド）
  manufacturing_plm_it_demand     製造業向けIT・PLM需要（EV/CASE対応含む）
  sap_erp_renewal_demand          SAP・ERP保守期限（2027年問題）対応需要
  invoice_electronic_ledger_demand インボイス・電帳法対応特需
  price_arpu_improvement          価格改定・ARPU向上による増収
  m_and_a_consolidation           M&A連結効果による増収
  cyclical_recovery_post_covid    コロナ後の需要正常化・景気回復
  inbound_tourism_demand          インバウンド需要増加
 ── 採算・一過性（利益ライン） ──
  margin_expansion                採算改善・営業レバレッジによる増益
  margin_compression_cost_investment 費用先行・コスト増によるマージン圧迫（増収減益）
  one_off_gain                    当期の一過性利益（売却益・評価益）
  one_off_loss                    当期の一過性損失（減損・評価損・中止損）
  one_off_cost_rolloff            前期一過性コスト・損失の剥落による改善
 ── メディア・コンテンツ（decision5＝方向で分け、統合しない） ──
  new_game_title_launch           新規ゲームタイトル投入・大型新作ヒット
  existing_game_title_decline     既存ゲームの自然減・課金縮小
  game_title_prior_year_high_base_rolloff 前期大型タイトルの反動減
  ip_content_hit_title            IP・映画・アニメのヒット作貢献
  tv_ad_revenue_structural_decline 地上波テレビ広告の構造的減少
 ── 報告書記載のイベント（decision9） ──
  contract_win                    大型受注・契約獲得（短信に明記）
  contract_loss_churn             失注・大口解約・チャーン（短信に明記）
  backlog_shift                   受注残・バックログの増減（短信に明記）
 ── 残余（捏造しない） ──
  no_report_reason_found          決算短信に株価/業績変動の原因が明記されていない＝見過ごされ候補（将来予測はしない）
  other                           上記いずれにも当てはまらない

guidance_overlay（decision6＝ガイダンスは"主"ではなく"重ね"。事業理由を主にしつつ翌期予想を別枠で）:
  none / disappointment（翌期が前年比マイナス等で実際に弱い）/ raise（翌期上方・強気）

⚠️ グラウンディング・ゲート（cause-not-mention）: specific_bucket は決算短信が
   その要因を「変動の"原因"」として明記している場合のみ付ける。単なる言及（全IT企業が言う
   "DX需要"等）や業界一般論では付けない。原因の記載が無ければ no_report_reason_found。
⚠️ 方向整合: 利益方向（gain系=増益, loss/compression=減益）と実際の利益方向を一致させる。
⚠️ バケットの"向き"と"対象"を取り違えない（最重要・9601型の誤りを防ぐ）:
   ・「ヒット・新作・拡大・貢献（プラス寄与）」を、"反動減・rolloff・decline（マイナス寄与）"の
     バケットに入れない。逆も同様。短信が「大ヒット／増収に貢献」と言うなら hit/launch/expansion 側、
     「前期の大型作の反動で減」と言うなら rolloff/decline 側。grounding引用の向きと一致させる。
   ・game_* は【ゲーム】専用。映画・アニメ・演劇・配信などの映像/コンテンツは ip_content_hit_title
     （ヒット貢献）を使い、game_title_* に入れない。
   ・配信・ストリーミング広告など、既存26バケットに無い具体ドライバーは安易に margin に寄せず、
     採算改善が主因でなければ no_report_reason_found か other。
⚠️ decision6: 事業側の具体理由があれば、たとえ翌期ガイダンスが弱くても specific_bucket は
   事業理由にし、ガイダンスは guidance_overlay に置く。ガイダンスが唯一の材料の時のみ
   specific_bucket=other＋guidance_overlay で表す。"""

SCHEMA = {
    'type': 'object',
    'properties': {
        'ticker': {'type': 'string'},
        'specific_bucket': {'type': 'string'},
        'guidance_overlay': {'type': 'string', 'enum': ['none', 'disappointment', 'raise']},
        'bucket_grounding': {'type': 'string',
            'description': '短信本文の該当箇所を短く引用（原因として明記された語句）。'
                           'no_report_reason_found の場合は "" '},
        'bucket_confidence': {'type': 'string', 'enum': ['high', 'med', 'low']},
    },
    'required': ['ticker', 'specific_bucket', 'guidance_overlay', 'bucket_grounding', 'bucket_confidence'],
    'additionalProperties': False,
}

ALLOWED = {  # validation set for the staged output
    'saas_arr_expansion', 'cloud_migration_growth', 'cybersecurity_investment_demand',
    'public_sector_it_demand', 'manufacturing_plm_it_demand', 'sap_erp_renewal_demand',
    'invoice_electronic_ledger_demand', 'price_arpu_improvement', 'm_and_a_consolidation',
    'cyclical_recovery_post_covid', 'inbound_tourism_demand', 'margin_expansion',
    'margin_compression_cost_investment', 'one_off_gain', 'one_off_loss', 'one_off_cost_rolloff',
    'new_game_title_launch', 'existing_game_title_decline', 'game_title_prior_year_high_base_rolloff',
    'ip_content_hit_title', 'tv_ad_revenue_structural_decline', 'contract_win',
    'contract_loss_churn', 'backlog_shift', 'no_report_reason_found', 'other',
}


def make_prompt(pkt, committed):
    t = pkt['ticker']
    name = pkt.get('name_jp') or pkt.get('name') or t
    pe = pkt['period_end']
    fy = f"{pe[:4]}年{int(pe[5:7])}月期"
    pr = pkt.get('prices', {}) or {}
    sdir = (pr.get('stock_dir') or 'flat')
    ground = (pkt.get('tanshin_text') or pkt.get('why_text') or '')[:6500]
    gsrc = '発表日の決算短信' if pkt.get('tanshin_text') else '有価証券報告書MD&A'
    prior = (pkt.get('prior_year_oneoff_text') or '')[:1200]
    # the already-committed mechanical classification (kept underneath)
    btag = committed.get('business_reason_tag', '?')
    stag = committed.get('stock_reason_tag', '?')
    why_b = (committed.get('why_business_moved') or '')[:600]
    return f"""あなたは日本株アナリスト。{t} {name} の{fy}決算について、承認済みの「具体的理由バケット（26）」を1つだけ割り当てる。
事業の方向・株価の方向・機械的タグ（下記）は確定済みで、その下に"具体理由"を1段だけ足す作業。捏造禁止・PIT厳守。

【確定済み（覆さない）】
{num_summary(pkt)}
株価方向: stock_dir={sdir.upper()}。機械的タグ: business={btag} / stock={stag}。
既出の業績理由メモ: {why_b}

【理由の根拠＝この決算短信本文のみ（出典:{gsrc}・後日資料/推測は不可）】
--- 当期 抜粋 ---
{ground}
--- 前期 一過性抜粋（剥落判定用） ---
{prior}

{SPECIFIC_BUCKETS}

【返却(JSON)】ticker="{t}", specific_bucket, guidance_overlay, bucket_grounding（短信の該当語句を短く引用）, bucket_confidence"""


def classify(client, model, pkt, committed):
    msg = client.messages.create(
        model=model, max_tokens=900,
        messages=[{'role': 'user', 'content': make_prompt(pkt, committed)}],
        output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}},
    )
    txt = ''.join(b.text for b in msg.content if b.type == 'text')
    r = json.loads(txt)
    if r.get('specific_bucket') not in ALLOWED:
        r['specific_bucket'] = 'other'
    return r, (msg.usage.input_tokens, msg.usage.output_tokens)


def run_year(client, model, year, pktdir, limit, only_tickers):
    committed = json.loads((ROOT / 'data' / 'quarterly' / f'it_q4_{year}.json').read_text(encoding='utf-8'))
    comps = committed['companies']
    pkts = []
    for f in sorted(glob.glob(str(ROOT / 'data' / 'quarterly' / pktdir / '*.json'))):
        pk = json.loads(Path(f).read_text(encoding='utf-8'))
        t = pk['ticker']
        if t not in comps:
            continue
        if only_tickers and t not in only_tickers:
            continue
        if not (pk.get('prices', {}) or {}).get('stock_dir'):
            continue
        pkts.append(pk)
    if limit:
        pkts = pkts[:limit]
    print(f'[{year}] classifying {len(pkts)} companies (no web, Bedrock {model})...')

    results, toks = {}, [0, 0]
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(classify, client, model, pk, comps[pk['ticker']]): pk['ticker'] for pk in pkts}
        for fut in as_completed(futs):
            t = futs[fut]
            try:
                r, (ti, to) = fut.result()
                results[t] = r
                toks[0] += ti; toks[1] += to
            except Exception as e:
                print(f'  {t}: ERROR {e}')
    # ── stage: merge specific fields onto a COPY; committed file untouched ──
    staged = {'companies': {t: dict(c) for t, c in comps.items()}}
    diff = []
    for t, r in results.items():
        sc = staged['companies'][t]
        sc['specific_bucket'] = r['specific_bucket']
        sc['guidance_overlay'] = r['guidance_overlay']
        sc['bucket_grounding'] = r.get('bucket_grounding', '')
        sc['bucket_confidence'] = r.get('bucket_confidence', '')
        diff.append((t, comps[t].get('business_reason_tag', '?'), r['specific_bucket'],
                     r['guidance_overlay'], r.get('bucket_confidence', '')))
    out = ROOT / 'data' / 'quarterly' / f'it_q4_{year}.staged.json'
    out.write_text(json.dumps(staged, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[{year}] STAGED -> {out.name} ({len(results)} classified). committed file untouched.')
    print(f'[{year}] tokens: in={toks[0]:,} out={toks[1]:,}')
    return diff, results


def main():
    args = sys.argv[1:]
    limit = int(args[args.index('--limit') + 1]) if '--limit' in args else None
    one_year = args[args.index('--year') + 1] if '--year' in args else None
    only = set(args[args.index('--tickers') + 1].split(',')) if '--tickers' in args else None

    model = os.environ['BEDROCK_MODEL_ID']
    client = AnthropicBedrock(
        aws_region=os.environ['AWS_REGION'],
        aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        aws_session_token=os.environ.get('AWS_SESSION_TOKEN') or None,
    )
    from collections import Counter
    all_diff, counts = [], Counter()
    years = [one_year] if one_year else list(YEARS)
    for y in years:
        diff, results = run_year(client, model, y, YEARS[y], limit, only)
        all_diff += [(y, *d) for d in diff]
        counts.update(r['specific_bucket'] for r in results.values())

    print('\n' + '=' * 70)
    print('STAGED DIFF (committed mechanical tag → new specific_bucket)')
    print('=' * 70)
    for y, t, btag, sb, ov, conf in sorted(all_diff, key=lambda x: (x[0], x[3])):
        ovs = f' +guidance:{ov}' if ov and ov != 'none' else ''
        print(f'  {y} {t:5s} {btag:24s} → {sb:34s}{ovs}  ({conf})')
    print('\nBUCKET COUNTS (staged):')
    for b, n in counts.most_common():
        print(f'  {n:3d}  {b}')
    rep = ROOT / 'data' / 'quarterly' / '_phase2_staged_diff.json'
    rep.write_text(json.dumps({'diff': all_diff, 'counts': dict(counts)}, ensure_ascii=False, indent=2),
                   encoding='utf-8')
    print(f'\nDiff report -> {rep.name}. NOTHING COMMITTED. Review, then approve to promote staged→committed.')


if __name__ == '__main__':
    main()
