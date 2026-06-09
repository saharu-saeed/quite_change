# -*- coding: utf-8 -*-
"""Replace Japanese 「」 quotes with English '..' in EN summaries only.
JP summaries keep 「」 (natural Japanese punctuation)."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data")
FILES = [
    "company_research_2025.json",
    "company_research_land_transport_sector.json",
    "company_research_marine_sector.json",
    "company_research_mining_sector.json",
    "company_research_petroleum_sector.json",
]

def convert_en_quotes(text: str) -> str:
    """Replace paired 「」 with paired straight double quotes in alternating fashion."""
    if not text:
        return text
    result = []
    open_state = True
    for ch in text:
        if ch == '「':
            result.append('"')
            open_state = False
        elif ch == '」':
            result.append('"')
            open_state = True
        else:
            result.append(ch)
    return ''.join(result)

total_changed = 0
for fname in FILES:
    path = BASE / fname
    data = json.loads(path.read_text(encoding='utf-8'))
    changed_in_file = 0
    for ticker, entry in data.items():
        if ticker == '_meta':
            continue
        en = entry.get('en_summary', '')
        if '「' in en or '」' in en:
            new_en = convert_en_quotes(en)
            entry['en_summary'] = new_en
            changed_in_file += 1
    if changed_in_file > 0:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        json.loads(path.read_text(encoding='utf-8'))  # validate
    print(f"{fname[:45]:45s}: changed {changed_in_file} EN entries")
    total_changed += changed_in_file

print(f"\nTotal EN entries with 「」 replaced: {total_changed}")
print("JP summaries left untouched (「」 is natural Japanese punctuation).")
