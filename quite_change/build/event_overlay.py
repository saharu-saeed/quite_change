# -*- coding: utf-8 -*-
"""Events-as-OVERLAY (provisional structural proposal for 中町氏 — revert-cheap).

claude.ai's catch: a contract win/loss sits ON TOP of a growth story (mentioned in
~19, won the single primary bucket in 1) — exactly like guidance, which already
works as an overlay. So make events an overlay too: detect a material contract
win / loss-churn per company and store it as `event_overlay`, alongside the
primary business bucket. backlog_shift is DROPPED (0 hits).

For the few companies currently classified with an event AS primary, re-derive a
non-event business primary (the event moves to the overlay). All staged; committed
files untouched; fully reversible (delete event_overlay + restore primary).

  python build/event_overlay.py            # detect + apply to staged
  python build/event_overlay.py --dry      # report only
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

YEARS = {'2024': '_pkts_2024_mdna', '2025': '_pkts_mdna'}
EVENT_PRIMARY = {'contract_win', 'contract_loss_churn', 'backlog_shift'}
# non-event primaries the re-derive may choose from
NON_EVENT = [
    'saas_arr_expansion', 'cloud_migration_growth', 'cybersecurity_investment_demand',
    'public_sector_it_demand', 'manufacturing_plm_it_demand', 'sap_erp_renewal_demand',
    'invoice_electronic_ledger_demand', 'price_arpu_improvement', 'm_and_a_consolidation',
    'cyclical_recovery_post_covid', 'inbound_tourism_demand', 'margin_expansion',
    'margin_compression_cost_investment', 'one_off_gain', 'one_off_loss', 'one_off_cost_rolloff',
    'new_game_title_launch', 'existing_game_title_decline', 'game_title_prior_year_high_base_rolloff',
    'ip_content_hit_title', 'tv_ad_revenue_structural_decline', 'no_report_reason_found', 'other',
]

SCHEMA = {
    'type': 'object',
    'properties': {
        'ticker': {'type': 'string'},
        'event_overlay': {'type': 'string', 'enum': ['none', 'contract_win', 'contract_loss_churn']},
        'event_quote': {'type': 'string'},
        'primary_business_bucket': {'type': 'string', 'enum': NON_EVENT},
        'confidence': {'type': 'string', 'enum': ['high', 'med', 'low']},
    },
    'required': ['ticker', 'event_overlay', 'event_quote', 'primary_business_bucket', 'confidence'],
    'additionalProperties': False,
}

PROMPT = """決算短信本文を読み、2つを判定する。

A) event_overlay（重ね＝主因の"上"に乗るイベント。決算短信に【具体的・重要な】記載がある時のみ）:
   contract_win        — 大型受注の獲得・大口契約の締結（金額/相手/案件が具体的）
   contract_loss_churn — 大口の失注・契約終了・解約(チャーン)（具体的）
   none                — 上記の具体的イベントの明記がない（汎用的な「受注は堅調」等は none）
   ※ backlog（受注残）は対象外。

B) primary_business_bucket（その会社の"主たる"事業理由。イベントではなく、売上/利益が動いた本筋。
   下記から1つ。短信が原因を明記しない場合 no_report_reason_found）:
   saas_arr_expansion / cloud_migration_growth / cybersecurity_investment_demand /
   public_sector_it_demand / manufacturing_plm_it_demand / sap_erp_renewal_demand /
   invoice_electronic_ledger_demand / price_arpu_improvement / m_and_a_consolidation /
   cyclical_recovery_post_covid / inbound_tourism_demand / margin_expansion /
   margin_compression_cost_investment / one_off_gain / one_off_loss / one_off_cost_rolloff /
   new_game_title_launch / existing_game_title_decline / game_title_prior_year_high_base_rolloff /
   ip_content_hit_title / tv_ad_revenue_structural_decline / no_report_reason_found / other

⚠️ イベントは"主因"ではなく"重ね"。受注獲得があっても、売上成長の本筋（需要/採算/SaaS等）を
   primary_business_bucket にし、受注は event_overlay に置く（ガイダンスと同じ扱い）。

【決算短信 本文抜粋】
{ground}

返却(JSON): ticker="{t}", event_overlay, event_quote（該当箇所を短く引用／noneなら""）, primary_business_bucket, confidence"""


def detect(client, model, y, pk):
    ground = (pk.get('tanshin_text') or pk.get('why_text') or '')[:6500]
    msg = client.messages.create(
        model=model, max_tokens=500,
        messages=[{'role': 'user', 'content': PROMPT.format(ground=ground, t=pk['ticker'])}],
        output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}},
    )
    return y, pk['ticker'], json.loads(''.join(b.text for b in msg.content if b.type == 'text'))


def main():
    dry = '--dry' in sys.argv
    model = os.environ['BEDROCK_MODEL_ID']
    client = AnthropicBedrock(
        aws_region=os.environ['AWS_REGION'], aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        aws_session_token=os.environ.get('AWS_SESSION_TOKEN') or None)

    staged = {y: json.loads((ROOT / 'data' / 'quarterly' / f'it_q4_{y}.staged.json').read_text(encoding='utf-8'))
              for y in YEARS}
    jobs = []
    for y, d in YEARS.items():
        comps = staged[y]['companies']
        for f in glob.glob(str(ROOT / 'data' / 'quarterly' / d / '*.json')):
            pk = json.loads(Path(f).read_text(encoding='utf-8'))
            if pk['ticker'] in comps and comps[pk['ticker']].get('specific_bucket'):
                jobs.append((y, pk))
    print(f'Detecting event overlays across {len(jobs)} companies...\n')

    res = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(detect, client, model, y, pk) for y, pk in jobs]
        for fut in as_completed(futs):
            res.append(fut.result())

    overlays = [(y, t, r) for y, t, r in res if r['event_overlay'] != 'none']
    reprimaried = []
    from collections import Counter
    ov_counts = Counter(r['event_overlay'] for _, _, r in res)
    for y, t, r in res:
        sc = staged[y]['companies'][t]
        old_primary = sc.get('specific_bucket')
        sc['event_overlay'] = r['event_overlay']
        if r['event_overlay'] != 'none':
            sc['event_quote'] = r.get('event_quote', '')
        # if the current PRIMARY was an event, replace it with the re-derived non-event primary
        if old_primary in EVENT_PRIMARY:
            sc['specific_bucket'] = r['primary_business_bucket']
            sc['rehomed_from'] = old_primary
            reprimaried.append((y, t, old_primary, r['primary_business_bucket']))

    print('=' * 70)
    print(f"EVENT OVERLAYS: win={ov_counts['contract_win']}  loss_churn={ov_counts['contract_loss_churn']}  (none={ov_counts['none']})")
    print('=' * 70)
    for y, t, r in sorted(overlays, key=lambda x: x[2]['event_overlay']):
        print(f"  {y} {t}: {r['event_overlay']} ({r['confidence']}) — {(r.get('event_quote') or '')[:90]}")
    print(f'\nRE-PRIMARIED (event-as-primary → business primary, event moved to overlay): {len(reprimaried)}')
    for y, t, oldp, newp in reprimaried:
        print(f'  {y} {t}: {oldp} → {newp} (+event_overlay)')

    if dry:
        print('\n(--dry: staged NOT modified)')
        return
    for y in YEARS:
        p = ROOT / 'data' / 'quarterly' / f'it_q4_{y}.staged.json'
        p.write_text(json.dumps(staged[y], ensure_ascii=False, indent=2), encoding='utf-8')
    print('\nApplied event_overlay to staged (committed untouched). backlog_shift dropped (0).')


if __name__ == '__main__':
    main()
