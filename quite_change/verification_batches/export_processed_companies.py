# -*- coding: utf-8 -*-
"""Export a single flat JSON file listing every processed company across the
7 sectors, with ticker / name / category (R+xS- or R+xS+) / sector tag."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change")
DATA = ROOT / 'data'
BUILD = ROOT / 'build'

# Make IT module importable
sys.path.insert(0, str(BUILD))

# === Non-IT sectors: load directly from JSON files ===
NON_IT_FILES = {
    'LandTransport':  'company_research_land_transport_sector.json',
    'Mining':         'company_research_mining_sector.json',
    'Petroleum':      'company_research_petroleum_sector.json',
    'Marine':         'company_research_marine_sector.json',
    'AirTransport':   'company_research_air_transport_sector.json',
    'AgriFishery':    'company_research_agri_fishery_sector.json',
}

rows = []

for sector, fname in NON_IT_FILES.items():
    data = json.loads((DATA / fname).read_text(encoding='utf-8'))
    for ticker, entry in data.items():
        if ticker == '_meta' or not isinstance(entry, dict):
            continue
        rows.append({
            'ticker':   ticker,
            'name':     entry.get('name', '?'),
            'category': entry.get('tab', 'R+'),
            'sector':   sector,
        })

# === IT sector: import build_view module which exposes buckets_s_minus/plus ===
import build_view as it_mod

# it_mod.buckets_s_minus = { bucket_key: [record, ...] }
# it_mod.buckets_s_plus  = { bucket_key: [record, ...] }
# Each record is a dict with at least 'code' and 'name' (let's introspect to be safe)
for category, bucket_dict in [('R+xS-', it_mod.buckets_s_minus),
                               ('R+xS+', it_mod.buckets_s_plus)]:
    for bucket_key, recs in bucket_dict.items():
        for r in recs:
            # records have keys like 'code', 'name' — handle either
            ticker = r.get('code') or r.get('ticker') or '?'
            name = r.get('name', '?')
            rows.append({
                'ticker':   str(ticker),
                'name':     name,
                'category': category,
                'sector':   'IT',
            })

# Sort by sector then category then ticker for deterministic output
rows.sort(key=lambda r: (r['sector'], r['category'], r['ticker']))

# Tally summary
from collections import Counter
sector_counts = Counter(r['sector'] for r in rows)
cat_counts = Counter((r['sector'], r['category']) for r in rows)

OUT = ROOT / 'deliverables' / 'processed_companies.json'
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps({
    '_meta': {
        'generated': '2026-06-07',
        'total_companies': len(rows),
        'sectors_covered': list(NON_IT_FILES.keys()) + ['IT'],
        'sector_counts': dict(sector_counts),
        'category_counts': {f'{s}/{c}': n for (s, c), n in sorted(cat_counts.items())},
        'description': "Flat list of every R+ company processed across 7 TOPIX-33 sectors. Each entry has ticker, name, category (R+xS- = revenue up, stock down; R+xS+ = revenue up, stock up), and sector tag.",
    },
    'companies': rows,
}, ensure_ascii=False, indent=2), encoding='utf-8')

print(f"Wrote {OUT.relative_to(ROOT)}")
print(f"Total companies: {len(rows)}")
print()
print("Per-sector breakdown:")
for sector in list(NON_IT_FILES.keys()) + ['IT']:
    s_minus = cat_counts.get((sector, 'R+xS-'), 0)
    s_plus = cat_counts.get((sector, 'R+xS+'), 0)
    other = sector_counts[sector] - s_minus - s_plus
    extra = f" (+{other} other)" if other else ""
    print(f"  {sector:15s}: {sector_counts[sector]:3d} total  =  R+xS- {s_minus:3d}  +  R+xS+ {s_plus:3d}{extra}")
