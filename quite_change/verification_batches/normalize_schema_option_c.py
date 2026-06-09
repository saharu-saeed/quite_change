# -*- coding: utf-8 -*-
"""Option C: normalize schema of existing 5 sector files to match new lighter-prompt format.

Changes per company entry:
- Keep `name`, `jp_summary`, `en_summary` UNCHANGED (prose is preserved).
- Move `source_hint` text into `notes` field (preserved as audit trail context).
- Add empty `sources` array (old files had no URLs, just text hints).
- Drop the old `source_hint` key.

The `_meta` block is left untouched.

Result: all entries have schema { name, jp_summary, en_summary, sources, notes }
matching the new lighter-prompt output shape.
"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data")
FILES = [
    "company_research_2025.json",                  # IT
    "company_research_land_transport_sector.json", # Land Transport
    "company_research_marine_sector.json",         # Marine
    "company_research_mining_sector.json",         # Mining
    "company_research_petroleum_sector.json",      # Petroleum
]

total_normalized = 0
for fname in FILES:
    path = BASE / fname
    data = json.loads(path.read_text(encoding='utf-8'))
    changed_in_file = 0

    for ticker, entry in data.items():
        if ticker == '_meta':
            continue
        if not isinstance(entry, dict):
            continue

        # Already in new format? skip
        if 'sources' in entry and 'notes' in entry and 'source_hint' not in entry:
            continue

        # Build the normalized entry (preserve prose, normalize schema)
        old_hint = entry.get('source_hint', '')
        notes_text = f"Original source_hint: {old_hint}" if old_hint else ""

        new_entry = {
            'name': entry.get('name', ''),
            'jp_summary': entry.get('jp_summary', ''),
            'en_summary': entry.get('en_summary', ''),
            'sources': [],
            'notes': notes_text,
        }
        data[ticker] = new_entry
        changed_in_file += 1

    if changed_in_file > 0:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        # Validate
        json.loads(path.read_text(encoding='utf-8'))

    print(f"{fname[:48]:48s}: normalized {changed_in_file} entries")
    total_normalized += changed_in_file

print(f"\nTotal entries normalized to new schema: {total_normalized}")
print("Prose (jp_summary, en_summary) preserved exactly. Schema now matches new lighter-prompt output.")
