# -*- coding: utf-8 -*-
"""Build the FULL IT (情報・通信業) target list for FY2024 + FY2025 flash-report retrieval.
Every domestic 情報・通信業 ticker (excl PRO Market / foreign) × the FY2024 and FY2025 fiscal periods
that exist in Tempest. Output: _all_it_targets.json = [{ticker, name, fy, period_end}] + count/estimate.
"""
from __future__ import annotations
import json, sys, concurrent.futures as cf
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from research import tempest_fetch as tf
Q = ROOT / 'data' / 'quarterly'

df = pd.read_excel(ROOT / 'data' / '_jpx_data_j.xls')
secol = [c for c in df.columns if '33業種区分' in str(c)][0]
mktcol = [c for c in df.columns if '市場' in str(c)][0]
it = df[df[secol].astype(str).str.contains('情報・通信')]
cand = []
for _, r in it.iterrows():
    t = str(r['コード']).strip(); mkt = str(r[mktcol])
    if len(t) == 4 and t.isdigit() and 'PRO' not in mkt and '外国' not in mkt:
        cand.append((t, str(r['銘柄名']).strip()))
print(f'domestic 情報・通信業 tickers: {len(cand)}')

def periods(c):
    t, name = c
    try:
        d = tf.api(f'/companies/{t}/financials?from_fy=2022&to_fy=2025&limit=20')
        rows = [r for r in d.get('data', []) if r.get('period_end')]
        out = []
        for fy in ('2024', '2025'):
            pe = next((r['period_end'] for r in rows if r['period_end'][:4] == fy), None)
            if pe:
                out.append({'ticker': t, 'name': name, 'fy': fy, 'period_end': pe})
        return out
    except Exception:
        return []

targets = []
with cf.ThreadPoolExecutor(max_workers=12) as ex:
    for i, r in enumerate(ex.map(periods, cand)):
        targets.extend(r)
        if (i + 1) % 100 == 0: print(f'  ...{i+1}/{len(cand)} checked, {len(targets)} target-reports')

(Q / '_all_it_targets.json').write_text(json.dumps(targets, ensure_ascii=False, indent=2), encoding='utf-8')
n24 = sum(1 for x in targets if x['fy'] == '2024'); n25 = sum(1 for x in targets if x['fy'] == '2025')
companies = len({x['ticker'] for x in targets})
print(f'\n== ALL-IT targets: {len(targets)} reports ({n24} FY2024 + {n25} FY2025) across {companies} companies ==')
# estimate from benchmark: 5.3s/report single-threaded, ~0.63 MB/PDF
print(f'EST time  (single-thread, 0.7s polite delay): {len(targets)*5.3/3600:.1f} h')
print(f'EST time  (modest 3x parallel):               {len(targets)*5.3/3600/3:.1f} h')
print(f'EST storage (~0.63 MB/PDF):                   {len(targets)*0.63/1024:.2f} GB')
