# -*- coding: utf-8 -*-
"""Normalize all 83 IT entries to use **bold:** section headers matching other sectors."""
import json, sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

IT_PATH = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data\company_research_2025.json")

# Map any variant of section header → canonical bold-markdown form
JP_HEADERS = [
    # 会社概要
    (r'【会社概要】\s*', '**会社概要:** '),
    (r'\*\*会社概要\*\*(?![:：])\s*', '**会社概要:** '),
    (r'\*\*会社概要:\*\*\s*', '**会社概要:** '),
    (r'\*\*会社概要：\*\*\s*', '**会社概要:** '),
    # 業績の動き
    (r'【業績の動き】\s*', '**業績の動き:** '),
    (r'\*\*業績の動き\*\*(?![:：])\s*', '**業績の動き:** '),
    (r'\*\*業績の動き:\*\*\s*', '**業績の動き:** '),
    (r'\*\*業績の動き：\*\*\s*', '**業績の動き:** '),
    # なぜ業績がこう動いたのか
    (r'【なぜ業績がこう動いたのか】\s*', '**なぜ業績がこう動いたのか:** '),
    (r'\*\*なぜ業績がこう動いたのか\*\*(?![:：])\s*', '**なぜ業績がこう動いたのか:** '),
    (r'\*\*なぜ業績がこう動いたのか:\*\*\s*', '**なぜ業績がこう動いたのか:** '),
    (r'\*\*なぜ業績がこう動いたのか：\*\*\s*', '**なぜ業績がこう動いたのか:** '),
    # なぜ株価がこう動いたのか
    (r'【なぜ株価がこう動いたのか】\s*', '**なぜ株価がこう動いたのか:** '),
    (r'\*\*なぜ株価がこう動いたのか\*\*(?![:：])\s*', '**なぜ株価がこう動いたのか:** '),
    (r'\*\*なぜ株価がこう動いたのか:\*\*\s*', '**なぜ株価がこう動いたのか:** '),
    (r'\*\*なぜ株価がこう動いたのか：\*\*\s*', '**なぜ株価がこう動いたのか:** '),
    # UNVERIFIED tag
    (r'【UNVERIFIED】\s*', '**UNVERIFIED:** '),
]

EN_HEADERS = [
    # Company overview variants
    (r'\[Company Overview\]\s*', '**Company overview:** '),
    (r'\[Company overview\]\s*', '**Company overview:** '),
    (r'\[company overview\]\s*', '**Company overview:** '),
    # How/Business Movement variants
    (r'\[How did business move\]\s*', '**How did business move?** '),
    (r'\[How Business Moved\]\s*', '**How did business move?** '),
    (r'\[How business moved\]\s*', '**How did business move?** '),
    (r'\[Business Movement\]\s*', '**How did business move?** '),
    (r'\[Earnings Movement\]\s*', '**How did business move?** '),
    (r'\[Earnings movement\]\s*', '**How did business move?** '),
    # Why earnings/business moved
    (r'\[Why did business move this way\]\s*', '**Why did business move this way?** '),
    (r'\[Why business moved this way\]\s*', '**Why did business move this way?** '),
    (r'\[Why business moved\]\s*', '**Why did business move this way?** '),
    (r'\[Why Business Moved\]\s*', '**Why did business move this way?** '),
    (r'\[Why earnings moved this way\]\s*', '**Why did business move this way?** '),
    (r'\[Why earnings moved\]\s*', '**Why did business move this way?** '),
    (r'\[Why Earnings Moved\]\s*', '**Why did business move this way?** '),
    # Why stock moved
    (r'\[Why did the stock move this way\]\s*', '**Why did the stock move this way?** '),
    (r'\[Why the stock moved this way\]\s*', '**Why did the stock move this way?** '),
    (r'\[Why the stock moved\]\s*', '**Why did the stock move this way?** '),
    (r'\[Why the Stock Moved\]\s*', '**Why did the stock move this way?** '),
    (r'\[Why Stock Moved\]\s*', '**Why did the stock move this way?** '),
    (r'\[Why stock moved\]\s*', '**Why did the stock move this way?** '),
    # UNVERIFIED tag
    (r'\[UNVERIFIED\]\s*', '**UNVERIFIED:** '),
]

def normalize(text: str, patterns: list) -> str:
    if not text:
        return text
    for pat, replacement in patterns:
        text = re.sub(pat, replacement, text)
    return text

data = json.loads(IT_PATH.read_text(encoding='utf-8'))
changed = 0
for ticker, entry in data.items():
    if ticker == '_meta':
        continue
    jp_before = entry.get('jp_summary', '')
    en_before = entry.get('en_summary', '')
    jp_after = normalize(jp_before, JP_HEADERS)
    en_after = normalize(en_before, EN_HEADERS)
    if jp_after != jp_before or en_after != en_before:
        entry['jp_summary'] = jp_after
        entry['en_summary'] = en_after
        changed += 1

IT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
json.loads(IT_PATH.read_text(encoding='utf-8'))  # validate
print(f"Normalized {changed}/{len(data)-1} IT entries (excl. _meta)")

# Quick audit: any remaining brackets?
import re as _re
for ticker, entry in data.items():
    if ticker == '_meta':
        continue
    jp = entry.get('jp_summary', '')
    en = entry.get('en_summary', '')
    if '【' in jp or '】' in jp:
        print(f"  {ticker} JP still has 【】")
    leftover = _re.findall(r'\[(?:Company|How|Why|Earnings|Business|UNVERIFIED)[^\]]*\]', en)
    if leftover:
        print(f"  {ticker} EN still has brackets: {leftover[:3]}")
print("Done.")
