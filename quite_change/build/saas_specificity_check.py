# -*- coding: utf-8 -*-
"""Specificity-leak check on saas_arr_expansion (claude.ai's #1 review catch).

For every company staged as saas_arr_expansion, re-read its FULL announce-date
決算短信 and force the question: does the filing name a MORE-SPECIFIC driver as the
PRIMARY cause of the revenue/ARR growth (cybersecurity / sap_erp / public_sector /
cloud_migration / invoice / manufacturing_plm), or is generic SaaS/ARR accumulation
genuinely the most specific cause stated? Re-home only on a primary-cause match;
default to keeping saas. Applies confirmed re-homes to the staged files (cheap
relabel — no full re-classify). NOTHING committed.

  python build/saas_specificity_check.py            # check + apply re-homes to staged
  python build/saas_specificity_check.py --dry      # report only, do not modify staged
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

YEARS = {'2022': '_pkts_2022_mdna', '2023': '_pkts_2023_mdna', '2024': '_pkts_2024_mdna', '2025': '_pkts_mdna'}
MORE_SPECIFIC = ['cybersecurity_investment_demand', 'sap_erp_renewal_demand',
                 'public_sector_it_demand', 'cloud_migration_growth',
                 'invoice_electronic_ledger_demand', 'manufacturing_plm_it_demand']

SCHEMA = {
    'type': 'object',
    'properties': {
        'ticker': {'type': 'string'},
        'verdict': {'type': 'string', 'enum': ['saas_genuine', 'rehome']},
        'rehome_bucket': {'type': 'string',
            'enum': MORE_SPECIFIC + ['']},
        'primary_driver_quote': {'type': 'string'},
        'confidence': {'type': 'string', 'enum': ['high', 'med', 'low']},
    },
    'required': ['ticker', 'verdict', 'rehome_bucket', 'primary_driver_quote', 'confidence'],
    'additionalProperties': False,
}

PROMPT = """この企業は暫定で「saas_arr_expansion（SaaS・ARR拡大）」に分類された。決算短信本文を読み、
"より具体的な"成長ドライバーが【売上/ARR成長の"主因"として明記】されているか判定せよ。

候補（主因として明記がある時のみ re-home）:
  cybersecurity_investment_demand  サイバーセキュリティ投資需要が主因
  sap_erp_renewal_demand           SAP・ERP更改(2027問題)需要が主因
  public_sector_it_demand          官公庁・公共IT需要が主因
  cloud_migration_growth           顧客のクラウド移行(オンプレ→クラウド)が主因
  invoice_electronic_ledger_demand インボイス・電帳法対応特需が主因
  manufacturing_plm_it_demand      製造業向けIT・PLM需要が主因

判定ルール（厳格・cause-not-mention）:
 ・上記の具体ドライバーが「売上/ARRが伸びた"主たる理由"」として明記 → verdict="rehome", rehome_bucket=該当。
 ・本文が一般的なARR・継続課金・顧客基盤拡大・新規契約の積み上げを主因とし、上記の特定ドライバーを
   "主因"として挙げていない（単なる言及・製品名の一つに過ぎない）→ verdict="saas_genuine", rehome_bucket=""。
 ・迷えば saas_genuine（broad-over-specificの誤りより、specific-over-broadの誤りを避ける＝主因明記時のみ動かす）。

【決算短信 本文抜粋】
{ground}

返却(JSON): ticker="{t}", verdict, rehome_bucket, primary_driver_quote（主因の該当箇所を短く引用）, confidence"""


def load_saas(yrs):
    out = []
    for y in yrs:
        d = YEARS[y]
        staged = json.loads((ROOT / 'data' / 'quarterly' / f'it_q4_{y}.staged.json').read_text(encoding='utf-8'))['companies']
        saas = {t for t, c in staged.items() if c.get('specific_bucket') == 'saas_arr_expansion'}
        for f in glob.glob(str(ROOT / 'data' / 'quarterly' / d / '*.json')):
            pk = json.loads(Path(f).read_text(encoding='utf-8'))
            if pk['ticker'] in saas:
                out.append((y, pk))
    return out


def check(client, model, y, pk):
    ground = (pk.get('tanshin_text') or pk.get('why_text') or '')[:6500]
    msg = client.messages.create(
        model=model, max_tokens=500,
        messages=[{'role': 'user', 'content': PROMPT.format(ground=ground, t=pk['ticker'])}],
        output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}},
    )
    r = json.loads(''.join(b.text for b in msg.content if b.type == 'text'))
    return y, pk['ticker'], r


def main():
    dry = '--dry' in sys.argv
    model = os.environ['BEDROCK_MODEL_ID']
    client = AnthropicBedrock(
        aws_region=os.environ['AWS_REGION'], aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        aws_session_token=os.environ.get('AWS_SESSION_TOKEN') or None)
    yrs = [sys.argv[sys.argv.index('--year') + 1]] if '--year' in sys.argv else list(YEARS)
    saas = load_saas(yrs)
    print(f'Checking {len(saas)} saas_arr_expansion companies for absorbed specific reasons...\n')
    rehomes = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(check, client, model, y, pk) for y, pk in saas]
        for fut in as_completed(futs):
            y, t, r = fut.result()
            if r['verdict'] == 'rehome' and r['rehome_bucket']:
                rehomes.append((y, t, r['rehome_bucket'], r['confidence'], r.get('primary_driver_quote', '')))

    print('=' * 70)
    print(f'RE-HOME candidates (saas → more-specific): {len(rehomes)} of {len(saas)}')
    print('=' * 70)
    for y, t, b, conf, q in sorted(rehomes, key=lambda x: x[2]):
        print(f'  {y} {t} → {b} ({conf})')
        print(f'      {q[:150]}')
    if not rehomes:
        print('  (none — saas_arr_expansion is legitimately the most-specific grounded cause for all 34)')

    if not dry and rehomes:
        for y in yrs:
            p = ROOT / 'data' / 'quarterly' / f'it_q4_{y}.staged.json'
            data = json.loads(p.read_text(encoding='utf-8'))
            n = 0
            for yy, t, b, conf, q in rehomes:
                if yy == y and t in data['companies']:
                    data['companies'][t]['specific_bucket'] = b
                    data['companies'][t]['bucket_grounding'] = q
                    data['companies'][t]['rehomed_from'] = 'saas_arr_expansion'
                    n += 1
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'  [{y}] applied {n} re-homes to staged (committed untouched).')
    elif dry:
        print('\n(--dry: staged files NOT modified)')


if __name__ == '__main__':
    main()
