# -*- coding: utf-8 -*-
"""FREE shape re-derive (no LLM, no price refetch).

Recomputes path_shape for every company from the ALREADY-STORED path_pct in the staged
files, using the FIXED classifier (stockside_pass._features_from_cum). Only path_shape is
rewritten; path_pct (the real series) and all LLM-written prose are untouched.

  python build/rederive_shapes.py            # all 4 years
  python build/rederive_shapes.py --dry      # report only
"""
from __future__ import annotations
import sys, json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')
from stockside_pass import _features_from_cum   # single source of truth for the shape logic

YEARS = ['2022', '2023', '2024', '2025']


def main():
    dry = '--dry' in sys.argv
    for y in YEARS:
        sp = ROOT / 'data' / 'quarterly' / f'it_q4_{y}.staged.json'
        if not sp.exists():
            print(f'[{y}] no staged file, skip'); continue
        data = json.loads(sp.read_text(encoding='utf-8'))
        comps = data['companies']
        before = Counter(c.get('path_shape') for c in comps.values())
        changed = []
        for t, c in comps.items():
            cum = c.get('path_pct')
            if not cum or len(cum) < 4:
                continue
            new_shape = _features_from_cum(cum)['shape']
            old_shape = c.get('path_shape')
            if new_shape != old_shape:
                changed.append((t, old_shape, new_shape))
                c['path_shape'] = new_shape
        after = Counter(c.get('path_shape') for c in comps.values())
        print(f'\n[{y}] {len(changed)} shape changes (of {len(comps)} companies)')
        for t, o, n in sorted(changed, key=lambda x: x[2]):
            print(f'   {t}  {o} -> {n}')
        print(f'[{y}] dist before: {dict(before)}')
        print(f'[{y}] dist after : {dict(after)}')
        if not dry:
            sp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'[{y}] written.')
        else:
            print(f'[{y}] --dry: not written.')


if __name__ == '__main__':
    main()
