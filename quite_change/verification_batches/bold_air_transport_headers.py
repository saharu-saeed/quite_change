# -*- coding: utf-8 -*-
"""Normalize section headers in air transport entries to use **bold:** markdown
so the HTML builder renders them as <b>...</b>. The new lighter prompt produced
【会社概要】 brackets in JP and ALL-CAPS plain headers in EN — neither bolds."""
import json, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

PATH = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data\company_research_air_transport_sector.json")

# JP: replace 【X】 (with optional surrounding whitespace) with **X:** at line start
JP_REPLACEMENTS = [
    (r'【会社概要】\s*', '**会社概要:** '),
    (r'【業績の動き】\s*', '**業績の動き:** '),
    (r'【業績が動いた理由】\s*', '**業績が動いた理由:** '),
    (r'【株価が動いた理由】\s*', '**株価が動いた理由:** '),
]

# EN: canonical bold form matching other sectors. Handle multiple variants the
# model produced ("WHAT THE COMPANY DOES" / "Company Overview" / "How the business has been doing" / etc).
EN_REPLACEMENTS = [
    # Company overview variants
    (r'(?m)^\s*WHAT THE COMPANY DOES:?\s*\n', '**Company overview:** '),
    (r'(?m)^\s*Company Overview:?\s*\n', '**Company overview:** '),

    # Recent numbers / business performance variants
    (r'(?m)^\s*RECENT NUMBERS:?\s*\n', '**How did business move?** '),
    (r'(?m)^\s*HOW THE BUSINESS RECENTLY DID:?\s*\n', '**How did business move?** '),
    (r'(?m)^\s*Recent Financial Performance:?\s*\n', '**How did business move?** '),
    (r'(?m)^\s*Financial Performance[^\n]*\n', '**How did business move?** '),

    # Why business moved variants
    (r'(?m)^\s*WHY THE BUSINESS MOVED:?\s*\n', '**Why did business move this way?** '),
    (r'(?m)^\s*WHY THE BUSINESS MOVED THAT WAY:?\s*\n', '**Why did business move this way?** '),
    (r'(?m)^\s*Why Business Results Moved This Way:?\s*\n', '**Why did business move this way?** '),
    (r'(?m)^\s*Why the Business Moved:?\s*\n', '**Why did business move this way?** '),

    # Why stock moved variants
    (r'(?m)^\s*WHY THE STOCK MOVED:?\s*\n', '**Why did the stock move this way?** '),
    (r'(?m)^\s*WHY THE STOCK MOVED OVER THE PAST YEAR:?\s*\n', '**Why did the stock move this way?** '),
    (r'(?m)^\s*Why the Stock Moved Over the Past Year:?\s*\n', '**Why did the stock move this way?** '),
    (r'(?m)^\s*Why the Stock Has Moved:?\s*\n', '**Why did the stock move this way?** '),
    (r'(?m)^\s*Why the Stock Moved:?\s*\n', '**Why did the stock move this way?** '),
]

def normalize(text: str, patterns: list) -> str:
    if not text:
        return text
    for pat, replacement in patterns:
        text = re.sub(pat, replacement, text)
    return text

data = json.loads(PATH.read_text(encoding='utf-8'))
changed = 0
for ticker, entry in data.items():
    if ticker == '_meta':
        continue
    jp_before = entry.get('jp_summary', '')
    en_before = entry.get('en_summary', '')
    jp_after = normalize(jp_before, JP_REPLACEMENTS)
    en_after = normalize(en_before, EN_REPLACEMENTS)
    if jp_after != jp_before or en_after != en_before:
        entry['jp_summary'] = jp_after
        entry['en_summary'] = en_after
        changed += 1
        # Audit: did we replace all 4 JP headers?
        jp_bolds = jp_after.count('**会社概要:**') + jp_after.count('**業績の動き:**') + jp_after.count('**業績が動いた理由:**') + jp_after.count('**株価が動いた理由:**')
        en_bolds = en_after.count('**Company overview:**') + en_after.count('**How did business move?**') + en_after.count('**Why did business move this way?**') + en_after.count('**Why did the stock move this way?**')
        print(f"  {ticker} ({entry.get('name','?')}): JP bold headers = {jp_bolds}/4, EN bold headers = {en_bolds}/4")

PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
json.loads(PATH.read_text(encoding='utf-8'))  # validate
print(f"\nUpdated {changed} entries with bold section headers.")
