# -*- coding: utf-8 -*-
"""Inject the card-display fields (rev_dir, op_dir, net_dir, stock_yoy_estimate,
biz_classification) into the 4 air transport entries. The new lighter prompt doesn't
generate these scalar tags — the data is all in the jp_summary prose. We hand-extract
based on each company's actual FY3/2026 numbers."""

import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

PATH = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data\company_research_air_transport_sector.json")

# Hand-extracted from each company's prose. Numbers traceable to the verification
# audit trail in notes for each entry.
CARD_FIELDS = {
    "9201": {  # JAL
        "rev_dir": "up",   # +9.1%
        "op_dir": "up",    # EBIT +26.4%
        "net_dir": "up",   # +28.6%
        "stock_yoy_estimate": "-20% from peak",
        "biz_classification": "フルサービス大手 / Full-service major (international + cargo)",
    },
    "9202": {  # ANA Holdings
        "rev_dir": "up",   # +12.3%
        "op_dir": "up",    # +10.6%
        "net_dir": "up",   # +10.5%
        "stock_yoy_estimate": "-17% from peak",
        "biz_classification": "フルサービス大手 / Full-service major (international + cargo + LCC)",
    },
    "9204": {  # Skymark
        "rev_dir": "up",   # +1.4%
        "op_dir": "down",  # -1.4%
        "net_dir": "down", # -24%
        "stock_yoy_estimate": "-68% since IPO",
        "biz_classification": "中堅国内航空 / Mid-tier domestic carrier",
    },
    "9206": {  # Star Flyer
        "rev_dir": "up",   # +4.4%
        "op_dir": "up",    # +12.9%
        "net_dir": "down", # -77.4% (forex loss)
        "stock_yoy_estimate": "-23% from 52-wk high",
        "biz_classification": "プレミアム・リージョナル / Premium regional",
    },
}

data = json.loads(PATH.read_text(encoding='utf-8'))
updated = 0
for ticker, fields in CARD_FIELDS.items():
    if ticker not in data:
        print(f"  {ticker}: NOT FOUND in file (skipped)")
        continue
    entry = data[ticker]
    for k, v in fields.items():
        entry[k] = v
    updated += 1
    print(f"  {ticker}: added {len(fields)} fields ({entry.get('name','?')})")

PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
json.loads(PATH.read_text(encoding='utf-8'))  # validate
print(f"\nUpdated {updated} entries.")
