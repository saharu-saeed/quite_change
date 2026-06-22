import json, sys, concurrent.futures as cf
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).parent.parent; sys.path.insert(0, str(ROOT))
from research import tempest_fetch as tf

YEAR = sys.argv[1]; Q = ROOT / 'data' / 'quarterly'
df = pd.read_excel(ROOT / 'data' / '_jpx_data_j.xls')
sec = [c for c in df.columns if '33業種区分' in str(c)][0]
mk = [c for c in df.columns if '市場' in str(c)][0]
# domestic operating companies only (内国株式 = Prime/Standard/Growth); excludes ETF/REIT/PRO/foreign
dom = df[df[mk].astype(str).str.contains('内国株式')]
cand = [(str(r['コード']).strip(), str(r['銘柄名']).strip(), str(r[sec]).strip())
        for _, r in dom.iterrows()
        if len(str(r['コード']).strip()) == 4 and str(r['コード']).strip().isdigit()]
print(f'FY{YEAR}: {len(cand)} domestic companies across all sectors; resolving period_end via Tempest...')

def per(c):
    t, name, sector = c
    try:
        d = tf.api(f'/companies/{t}/financials?from_fy={int(YEAR)-2}&to_fy={YEAR}&limit=20')
        rows = [r for r in d.get('data', []) if r.get('period_end')]
        pe = next((r['period_end'] for r in rows if r['period_end'][:4] == YEAR), None)
        return {'ticker': t, 'name': name, 'sector': sector, 'fy': YEAR, 'period_end': pe} if pe else \
               {'ticker': t, 'name': name, 'sector': sector, 'fy': YEAR, 'period_end': None}
    except Exception:
        return {'ticker': t, 'name': name, 'sector': sector, 'fy': YEAR, 'period_end': None}

resolved, no_pe = [], []
with cf.ThreadPoolExecutor(max_workers=12) as ex:
    for r in ex.map(per, cand):
        (resolved if r['period_end'] else no_pe).append(r)
# keep only companies with a known period_end for the year (the ones we can fetch)
(Q / f'_all_sectors_targets_{YEAR}.json').write_text(json.dumps(resolved, ensure_ascii=False, indent=2), encoding='utf-8')
(Q / f'_all_sectors_nopE_{YEAR}.json').write_text(json.dumps(no_pe, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'FY{YEAR}: {len(resolved)} with period_end -> _all_sectors_targets_{YEAR}.json | '
      f'{len(no_pe)} without (not in Tempest / no filing that year) -> _all_sectors_nopE_{YEAR}.json')
