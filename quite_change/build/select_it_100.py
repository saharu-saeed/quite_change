# -*- coding: utf-8 -*-
"""Select 100 IT companies for the Q4-2025 batch run.

Ranks the IT census universe by market cap and tiers them per the user's choice:
    top 40 = large, next 30 = mid, next 30 = small  (= 100 total)

Enriches Japanese names from build/_it_universe.py where available.
Output: data/quarterly/it_100_selection.json  (ticker, name, name_jp, market_cap, tier)
"""
from __future__ import annotations
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CENSUS = ROOT / 'data' / 'it_census_universe.csv'
OUT = ROOT / 'data' / 'quarterly' / 'it_100_selection.json'

# JP names from the curated universe (optional enrichment)
def load_jp_names():
    names = {}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('_it_universe', ROOT / 'build' / '_it_universe.py')
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        for t, en, jp, size in getattr(mod, 'IT_UNIVERSE', []):
            names[str(t)] = jp
    except Exception as e:
        print(f'(jp-name enrichment skipped: {e})')
    return names

def main():
    rows = list(csv.DictReader(open(CENSUS, encoding='utf-8')))
    # keep rows with a usable market cap
    def cap(r):
        try: return float(r.get('market_cap') or 0)
        except Exception: return 0.0
    rows = [r for r in rows if cap(r) > 0]
    rows.sort(key=cap, reverse=True)
    top = rows[:100]
    if len(top) < 100:
        print(f'WARNING: only {len(top)} companies with market cap available (<100)')

    jp = load_jp_names()
    sel = []
    for i, r in enumerate(top):
        tier = 'large' if i < 40 else ('mid' if i < 70 else 'small')
        t = str(r['ticker']).strip()
        sel.append({
            'ticker': t,
            'name': r.get('company_name', '').strip(),
            'name_jp': jp.get(t, r.get('manual_name_resolved') or r.get('company_name', '')).strip(),
            'market_cap': cap(r),
            'tier': tier,
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(sel, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    from collections import Counter
    c = Counter(s['tier'] for s in sel)
    print(f'Written: {OUT}')
    print(f'Selected {len(sel)} companies  |  large={c["large"]} mid={c["mid"]} small={c["small"]}')
    print(f'  largest:  {sel[0]["ticker"]} {sel[0]["name"]}  (cap {sel[0]["market_cap"]/1e12:.2f}T)')
    print(f'  #40 (large/mid cut): {sel[39]["ticker"]} {sel[39]["name"]}  (cap {sel[39]["market_cap"]/1e12:.3f}T)')
    print(f'  #70 (mid/small cut): {sel[69]["ticker"]} {sel[69]["name"]}  (cap {sel[69]["market_cap"]/1e9:.0f}B)')
    print(f'  smallest: {sel[-1]["ticker"]} {sel[-1]["name"]}  (cap {sel[-1]["market_cap"]/1e9:.0f}B)')

if __name__ == '__main__':
    main()
