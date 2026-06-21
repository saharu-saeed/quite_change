# -*- coding: utf-8 -*-
"""Select the 50 SMALLEST-cap 情報・通信業 companies (any R±), excluding every already-used ticker
(existing 95 + 99 + FY2024 test-50). For each candidate pull FY2025 period_end + market cap from
Tempest; rank by market cap ASCENDING; take the 50 smallest. Retrieval-test universe only.
"""
from __future__ import annotations
import json, sys, concurrent.futures as cf
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from research import tempest_fetch as tf
Q = ROOT / 'data' / 'quarterly'

# used = union of the three committed/test sets
used = set(json.loads((Q / 'it_q4_2024.json').read_text(encoding='utf-8'))['companies'])
used |= set(json.loads((Q / 'it_q4_2025.json').read_text(encoding='utf-8'))['companies'])
used |= {r['ticker'] for r in json.loads((Q / '_test50_selection.json').read_text(encoding='utf-8'))}
print(f'excluding {len(used)} already-used tickers')

df = pd.read_excel(ROOT / 'data' / '_jpx_data_j.xls')
secol = [c for c in df.columns if '33業種区分' in str(c)][0]
mktcol = [c for c in df.columns if '市場' in str(c)][0]
it = df[df[secol].astype(str).str.contains('情報・通信')]
cand = []
for _, r in it.iterrows():
    t = str(r['コード']).strip(); mkt = str(r[mktcol])
    if len(t) == 4 and t.isdigit() and t not in used and 'PRO' not in mkt and '外国' not in mkt:
        cand.append((t, str(r['銘柄名']).strip()))
print(f'{len(cand)} candidates after exclusions')

def assess(c):
    t, name = c
    try:
        d = tf.api(f'/companies/{t}/financials?from_fy=2023&to_fy=2025&limit=20')
        rows = [r for r in d.get('data', []) if r.get('period_end')]
        cur = next((r for r in rows if r['period_end'][:4] == '2025'), None)
        if not cur:
            return None
        s = tf.api(f'/companies/{t}/snapshot')
        ind = (s.get('data', s) or {}).get('latest_indicators', {}) or {}
        mcap = float(ind.get('market_cap') or 0)
        if mcap <= 0:
            return None
        rev = None
        prev = next((r for r in rows if r['period_end'] == f'2024{cur["period_end"][4:]}' and r.get('net_sales')), None)
        if prev and cur.get('net_sales'):
            try: rev = round((float(cur['net_sales']) - float(prev['net_sales'])) / abs(float(prev['net_sales'])) * 100, 1)
            except Exception: pass
        return {'ticker': t, 'name': name, 'period_end': cur['period_end'], 'mcap': mcap, 'rev_pct': rev}
    except Exception:
        return None

out = []
with cf.ThreadPoolExecutor(max_workers=12) as ex:
    for i, r in enumerate(ex.map(assess, cand)):
        if r: out.append(r)
        if (i + 1) % 80 == 0: print(f'  ...assessed {i+1}/{len(cand)} (usable {len(out)})')

out.sort(key=lambda r: r['mcap'])   # ASCENDING — smallest first
sel = out[:50]
(Q / '_smallcap50_selection.json').write_text(json.dumps(sel, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\nusable candidates: {len(out)} | selected 50 smallest by market cap')
print(f'cap range: {sel[0]["mcap"]/1e8:.1f}億 (#1 smallest) … {sel[-1]["mcap"]/1e8:.1f}億 (#50)')
for i, r in enumerate(sel):
    rv = f'{r["rev_pct"]:+.1f}%' if r['rev_pct'] is not None else 'n/a'
    print(f'{i+1:2}. {r["ticker"]} {r["name"][:18]:18} cap={r["mcap"]/1e8:6.1f}億 rev {rv:>7} FY{r["period_end"]}')
