# -*- coding: utf-8 -*-
"""Recover the `tab` field (R+xS- vs R+xS+) that Option C inadvertently stripped from
non-IT sector entries. Inference is text-based: scan jp_summary's stock-direction
language to classify.

The IT file uses a different loader path (build_view module) and is unaffected.
"""
import json, sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data")
FILES = [
    "company_research_land_transport_sector.json",
    "company_research_marine_sector.json",
    "company_research_mining_sector.json",
    "company_research_petroleum_sector.json",
    "company_research_air_transport_sector.json",
]

# Stock-direction keyword patterns
S_MINUS_PATTERNS = [
    r'下落', r'急落', r'続落', r'大幅安', r'安値', r'急降', r'下げ',
    r'マイナス', r'失望売り', r'下方修正', r'\-\d+%', r'年初来安値',
    r'sell', r'plunge', r'decline', r'fell', r'crashed', r'tumbled',
    r'52週安値', r'下値',
]
S_PLUS_PATTERNS = [
    r'上昇', r'急騰', r'続伸', r'高値', r'反発', r'プラス',
    r'上方修正', r'\+\d+%', r'年初来高値', r'回復',
    r'rally', r'rose', r'surged', r'gained', r'climbed', r'jumped', r'recovered',
    r'52週高値',
]

def classify_tab(jp_text: str, en_text: str = '') -> str:
    """Return 'R+xS-' or 'R+xS+' based on stock-direction keyword counts."""
    combined = (jp_text or '') + ' ' + (en_text or '')
    # Focus on the stock-section if delimiter present (more accurate)
    stock_section = combined
    for delim in ['株価が動いた理由', 'なぜ株価がこう動いたのか', 'WHY THE STOCK', 'Why the stock', 'Why did the stock']:
        if delim in combined:
            stock_section = combined.split(delim, 1)[1]
            break

    minus_score = sum(len(re.findall(p, stock_section, re.IGNORECASE)) for p in S_MINUS_PATTERNS)
    plus_score = sum(len(re.findall(p, stock_section, re.IGNORECASE)) for p in S_PLUS_PATTERNS)

    # If both sides have signals, lean toward whichever is stronger.
    # If exact tie or zero on both, default to R+xS- (conservative — flags for review).
    if plus_score > minus_score:
        return 'R+xS+'
    return 'R+xS-'

total_classified = 0
for fname in FILES:
    path = BASE / fname
    if not path.exists():
        print(f"{fname[:50]:50s}: SKIPPED (file not found)")
        continue
    data = json.loads(path.read_text(encoding='utf-8'))
    minus_count = plus_count = 0
    file_changes = 0

    for ticker, entry in data.items():
        if ticker == '_meta' or not isinstance(entry, dict):
            continue
        if 'tab' in entry:
            # Already has tab — count but don't overwrite
            if entry['tab'] == 'R+xS-': minus_count += 1
            elif entry['tab'] == 'R+xS+': plus_count += 1
            continue
        tab = classify_tab(entry.get('jp_summary', ''), entry.get('en_summary', ''))
        entry['tab'] = tab
        # Also set a default bucket so render_oil_company_card has a value
        entry.setdefault('bucket', 'other_grower')
        if tab == 'R+xS-': minus_count += 1
        else: plus_count += 1
        file_changes += 1

    if file_changes > 0:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        json.loads(path.read_text(encoding='utf-8'))  # validate

    print(f"{fname[:50]:50s}: classified {file_changes:3d} new, total R+xS-={minus_count:3d} | R+xS+={plus_count:3d}")
    total_classified += file_changes

print(f"\nTotal tab classifications added: {total_classified}")
print("IT file unchanged (uses build_view module loader, not affected by Option C).")
