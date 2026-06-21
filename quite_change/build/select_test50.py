# -*- coding: utf-8 -*-
"""Select 50 NEW 情報・通信業 companies (R+ FY2024), not in the existing 95, ranked by market cap.
Same spirit as the original (market-cap ranked); adds the R+ revenue filter. Test batch only.
"""
from __future__ import annotations
import json, sys, concurrent.futures as cf
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from research import tempest_fetch as tf

cand = json.loads((ROOT / 'data' / 'quarterly' / '_jpx_it_candidates.json').read_text(encoding='utf-8'))

def assess(c):
    t, name, mkt = c
    if 'PRO' in mkt or '外国' in mkt:
        return None
    try:
        d = tf.api(f'/companies/{t}/financials?from_fy=2021&to_fy=2024&limit=20')
        rows = [r for r in d.get('data', []) if r.get('period_end')]
        cur = next((r for r in rows if r['period_end'][:4] == '2024' and r.get('net_sales')), None)
        if not cur:
            return None
        pe = cur['period_end']; yr = int(pe[:4])
        prev = next((r for r in rows if r['period_end'] == f'{yr-1}{pe[4:]}' and r.get('net_sales')), None)
        if not prev:
            return None
        c0, p0 = float(cur['net_sales']), float(prev['net_sales'])
        rev_pct = (c0 - p0) / abs(p0) * 100 if p0 else 0
        if rev_pct <= 0:           # R+ ONLY
            return None
        s = tf.api(f'/companies/{t}/snapshot')
        ind = (s.get('data', s) or {}).get('latest_indicators', {}) or {}
        mcap = float(ind.get('market_cap') or 0)
        return {'ticker': t, 'name': name, 'market': mkt, 'period_end': pe,
                'rev_pct': round(rev_pct, 1), 'net_sales': cur['net_sales'], 'mcap': mcap}
    except Exception:
        return None

out = []
with cf.ThreadPoolExecutor(max_workers=12) as ex:
    for i, r in enumerate(ex.map(assess, cand)):
        if r:
            out.append(r)
        if (i + 1) % 80 == 0:
            print(f'  ...assessed {i+1}/{len(cand)}  (R+ so far {len(out)})')

out.sort(key=lambda r: -r['mcap'])
top50 = out[:50]
(ROOT / 'data' / 'quarterly' / '_test50_selection.json').write_text(json.dumps(top50, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\nR+ candidates total: {len(out)}  |  selected top 50 by market cap')
print(f'cap range: {top50[0]["mcap"]/1e9:.0f}B (#{1}) … {top50[-1]["mcap"]/1e9:.1f}B (#50)')
for i, r in enumerate(top50):
    print(f'{i+1:2}. {r["ticker"]} {r["name"][:16]:16} cap={r["mcap"]/1e9:6.1f}B rev+{r["rev_pct"]:.1f}% FY{r["period_end"]}')
