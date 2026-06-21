# -*- coding: utf-8 -*-
"""Build a Tempest data packet for each of the resolved IT companies (FREE, no LLM).

Reads data/quarterly/it_100_dates.json (ticker, announce, period_end, tier, name_jp),
calls research.tempest_fetch.build_packet for each → data/quarterly/_pkts/{ticker}.json.

Each packet carries the EXACT numbers (rev/op/net % with PIT override), the VERIFIED
P0/P1 stock direction, and 有報 MD&A / one-off excerpts as bonus grounding. The batch
model reads the announce-date 決算短信 itself via web tools; these packets supply the
hard, verified numbers + stock move so the LLM never guesses them.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from research import tempest_fetch as tf  # noqa: E402

import os
DATES = ROOT / 'data' / 'quarterly' / os.environ.get('DATES_FILE', 'it_100_dates.json')
PKTDIR = ROOT / 'data' / 'quarterly' / os.environ.get('PKTDIR_NAME', '_pkts')

def main():
    recs = [r for r in json.load(open(DATES, encoding='utf-8')) if r.get('announce') and r.get('period_end')]
    PKTDIR.mkdir(parents=True, exist_ok=True)
    force = '--force' in sys.argv
    ok = skip = fail = 0
    bad_prices = []
    for i, r in enumerate(recs, 1):
        t = r['ticker']; out = PKTDIR / f'{t}.json'
        if out.exists() and not force:
            skip += 1; continue
        try:
            pkt = tf.build_packet(t, r['announce'], r['period_end'])
            pkt['tier'] = r['tier']; pkt['name_jp'] = r.get('name_jp'); pkt['name'] = r.get('name')
            pkt['announce_date'] = r['announce']
            json.dump(pkt, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            pr = pkt.get('prices', {})
            if not pr.get('stock_dir'):
                bad_prices.append(t)
            ok += 1
            print(f'  [{i}/{len(recs)}] {t} {str(r.get("name"))[:22]:22} '
                  f'rev={pkt["numbers"].get("rev_pct")} stock={pr.get("pct_change")}({pr.get("stock_dir")})')
        except Exception as e:
            fail += 1; print(f'  [{i}/{len(recs)}] {t} FAILED: {e}')
        time.sleep(0.1)
    print(f'\nbuilt={ok} skipped(cached)={skip} failed={fail}')
    if bad_prices:
        print(f'NO stock direction (check announce date): {bad_prices}')

if __name__ == '__main__':
    main()
