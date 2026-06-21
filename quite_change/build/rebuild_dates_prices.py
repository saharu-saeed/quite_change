# -*- coding: utf-8 -*-
"""Apply the authoritative announce date (from the 決算短信 cover, set by prefetch as
announce_date_doc) and rebuild the stock window: re-fetch P0→P1 prices and the TOPIX-1306
relative move on the CORRECTED window. Fixes the resolve_dates min()-bug stock windows.

Only touches packets where announce_date_doc disagrees with announce_date. Prints every
change so a wrong-window → S± flip is visible. PIT-clean (historical prices only).
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from research import tempest_fetch as tf
import importlib.util
spec = importlib.util.spec_from_file_location('t2', ROOT / 'build' / 'add_tier2.py')
t2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t2)

PKTDIR = ROOT / 'data' / 'quarterly' / os.environ.get('PKTDIR_NAME', '_pkts')

def main():
    changed = flips = 0
    for f in sorted(PKTDIR.glob('*.json')):
        pkt = json.loads(f.read_text(encoding='utf-8'))
        adoc = pkt.get('announce_date_doc')
        old = pkt.get('announce_date')
        if not adoc or adoc == old:
            continue
        old_dir = (pkt.get('prices', {}) or {}).get('stock_dir')
        # rebuild prices on the corrected window, then Tier-2 relative move
        try:
            prices = tf.fetch_prices(pkt['ticker'], adoc)
        except Exception as e:
            print(f'  {pkt["ticker"]:5} price refetch FAILED ({e}) — left as-is'); continue
        mkt = t2.topix_move(prices['p0_date'], prices['p1_date'])
        rel, mt = t2.classify(prices['pct_change'], mkt)
        prices['market_pct'] = mkt; prices['relative_pct'] = rel; prices['move_type'] = mt
        pkt['announce_date'] = adoc; pkt['prices'] = prices
        f.write_text(json.dumps(pkt, ensure_ascii=False, indent=2), encoding='utf-8')
        changed += 1
        flip = old_dir and prices['stock_dir'] != old_dir
        flips += bool(flip)
        print(f'  {pkt["ticker"]:5} announce {old}->{adoc}  stock_dir {old_dir}->{prices["stock_dir"]}'
              f'{"  ⚠️S±FLIP" if flip else ""}  ({prices["pct_change"]}% rel={rel})')
    print(f'\nrebuilt windows={changed}  S±-direction flips={flips}')

if __name__ == '__main__':
    main()
