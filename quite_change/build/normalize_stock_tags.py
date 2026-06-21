# -*- coding: utf-8 -*-
"""RULING 1 — deterministic stock-tag normalization (no LLM/no key).

Direction/with-market classification is pure Tier-2 data, so we apply it exactly:
  • |absolute move| ≤ 1%                         → muted_no_reaction (barely moved)
  • |absolute move| > 1% AND |relative| ≤ REL_NEAR → other  (moved WITH the market;
                                                    a market-beta move, not company-specific)
  • else                                          → keep the LLM's company-specific tag
REL_NEAR = 2.0% (relative-to-TOPIX "near zero" band).

Only the bucket-DIRECTION question is decided here; the company-specific sub-tag
(rerating_on_growth / consensus_miss / capital_return_surprise / …) is left to the LLM.
Reports exactly which companies changed.
"""
from __future__ import annotations
import json, glob
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / 'data' / 'quarterly' / 'it_q4_2025.json'
PKT = ROOT / 'data' / 'quarterly' / '_pkts'
REL_NEAR = 1.0  # relative-to-TOPIX band counting as "moved WITH the market"
                # (±2% was too wide — swept in genuine outperformers like Sakura +1.97% rel)

def main():
    d = json.loads(OUT.read_text(encoding='utf-8'))
    comps = d['companies']
    pk = {Path(f).stem: json.loads(Path(f).read_text(encoding='utf-8')) for f in glob.glob(str(PKT / '*.json'))}
    changes = []
    for t, c in comps.items():
        pr = (pk.get(t, {}) or {}).get('prices', {}) or {}
        ab = pr.get('pct_change'); rel = pr.get('relative_pct')
        if ab is None:
            continue
        cur = c.get('stock_reason_tag')
        new = cur
        if abs(ab) <= 1.0:
            new = 'muted_no_reaction'
        elif rel is not None and abs(rel) <= REL_NEAR:
            new = 'other'   # moved with the market (market-beta), not company-specific
        if new != cur:
            c['stock_reason_tag'] = new
            changes.append((t, pk.get(t, {}).get('name', t), f'{ab:+.2f}%', f'rel{rel:+.2f}%' if rel is not None else 'rel?', cur, '→', new))
    OUT.write_text(json.dumps({'companies': comps}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'RULING 1 applied (REL_NEAR=±{REL_NEAR}%). Changed {len(changes)} companies:')
    for ch in changes:
        print('   ', ch)

if __name__ == '__main__':
    main()
