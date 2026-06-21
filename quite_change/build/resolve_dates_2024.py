# -*- coding: utf-8 -*-
"""Resolve 2024-fiscal-year period-end + announce date for the SAME 100 IT companies.

Point-in-time: targets the annual report for the fiscal year ENDING IN CALENDAR 2024
(March-FYE -> 2024-03-31 announced ~May 2024; Dec-FYE -> 2024-12-31 announced ~Feb 2025).
Reuses the validated resolver helpers; only the target year changes. No 2025 data is used.
"""
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location('rd', ROOT / 'build' / 'resolve_dates.py')
rd = importlib.util.module_from_spec(spec); spec.loader.exec_module(rd)

SEL = ROOT / 'data' / 'quarterly' / 'it_100_selection.json'
OUT = ROOT / 'data' / 'quarterly' / 'it_100_dates_2024.json'

def period_end_2024(ticker):
    try:
        d = rd.tf.api(f'/companies/{ticker}/financials?from_fy=2021&to_fy=2025&limit=40')
    except Exception:
        return None
    annual = [r for r in d.get('data', []) if r.get('period_end') and not r.get('fiscal_quarter')
              and '2024-01-01' <= r['period_end'] <= '2024-12-31']
    if annual:
        return annual[0]['period_end']
    any24 = [r for r in d.get('data', []) if r.get('period_end', '')[:4] == '2024']
    return any24[0]['period_end'] if any24 else None

def main():
    sel = json.load(open(SEL, encoding='utf-8'))
    out, n_web, n_unres, n_nope = [], 0, 0, 0
    for s in sel:
        t = s['ticker']
        pe = period_end_2024(t)
        rec = {**s, 'period_end': pe, 'announce': None, 'date_source': None}
        if not pe:
            rec['date_source'] = 'no_period_end'; n_nope += 1; out.append(rec)
            print(f'  {t} {s["name"][:22]:22} NO 2024 period_end'); continue
        a = rd.resolve_announce(t, s.get('name_jp') or s['name'], pe)
        if a:
            rec['announce'] = a; rec['date_source'] = 'web'; n_web += 1
        else:
            rec['date_source'] = 'UNRESOLVED'; n_unres += 1
        out.append(rec)
        print(f'  {t} {s["name"][:22]:22} pe={pe} announce={rec["announce"]} [{rec["date_source"]}]')
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\nWritten: {OUT}')
    print(f'web={n_web}  UNRESOLVED={n_unres}  no_period_end={n_nope}  total={len(out)}')

if __name__ == '__main__':
    main()
