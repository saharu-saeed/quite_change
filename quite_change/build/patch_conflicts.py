# -*- coding: utf-8 -*-
"""Deterministic tag-only patch of the 7 direction-conflict business tags (staged sets only).
Narratives are already written + grounded; only the tag label was direction-wrong. Sets each to
the direction-consistent tag that matches the existing narrative (no LLM). Prints 7-row before/after.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
Q = ROOT / 'data' / 'quarterly'
sys.path.insert(0, str(ROOT / 'build'))
from run_it_noweb import pick_name

# ticker -> corrected business_reason_tag (rationale in chat)
FIX = {'9984': 'other', '3825': 'other', '2121': 'other', '7860': 'other',
       '9404': 'margin_compression', '4344': 'volume_demand_growth', '3791': 'volume_demand_growth'}
LOC = {'2024': (['9984', '3825', '4344', '2121', '9404'], '_pkts_2024_mdna', 'it_q4_2024_mdna.json'),
       '2025': (['7860', '3791'], '_pkts_mdna', 'it_q4_2025_mdna.json')}

rows = []
for yr, (ts, pdir, outf) in LOC.items():
    staged = json.loads((Q / outf).read_text(encoding='utf-8'))
    for t in ts:
        p = json.loads((Q / pdir / f'{t}.json').read_text(encoding='utf-8'))
        before = staged['companies'][t]['business_reason_tag']
        staged['companies'][t]['business_reason_tag'] = FIX[t]
        nm = p['numbers']
        rows.append((yr, t, pick_name(p), before, FIX[t], nm.get('rev_pct'), nm.get('op_pct'), nm.get('net_pct')))
    (Q / outf).write_text(json.dumps(staged, ensure_ascii=False, indent=2), encoding='utf-8')

print(f'{"yr":5}{"tkr":6}{"name":20}{"before":24}-> {"after":22}{"rev":>6}{"op":>8}{"net":>8}')
for yr, t, nm, b, a, rev, op, net in rows:
    print(f'{yr:5}{t:6}{nm[:18]:20}{b:24}-> {a:22}{str(rev):>6}{str(op):>8}{str(net):>8}')
