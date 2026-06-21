# -*- coding: utf-8 -*-
"""Tier 2 — market-relative stock move (FREE, PIT-clean, no LLM/no Anthropic key).

For each company, compares its verified P0->P1 move to TOPIX (ETF 1306) over the EXACT
same window. Adds to the packet:
    market_pct       : TOPIX move over [p0_date, p1_date]
    relative_pct     : company_pct - market_pct
    move_type        : 'company_specific' | 'with_market' | 'against_market'
This lets the model tell a company-specific miss from a sector-wide drift — the sharpest
free signal for the stock reasoning. All point-in-time clean (same historical window).
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from research import tempest_fetch as tf  # noqa

ROOT = Path(__file__).parent.parent
import os
PKTDIR = ROOT / 'data' / 'quarterly' / os.environ.get('PKTDIR_NAME', '_pkts')
TOPIX = '1306'  # NEXT FUNDS TOPIX ETF — proxy for the broad market

def topix_move(p0d, p1d):
    d = tf.api(f'/companies/{TOPIX}/prices?from={p0d}&to={p1d}&limit=60')
    rows = {r['date']: float(r['close']) for r in d.get('data', [])}
    if not rows:
        return None
    asc = sorted(rows)
    s = p0d if p0d in rows else next((x for x in asc if x >= p0d), None)
    e = p1d if p1d in rows else next((x for x in reversed(asc) if x <= p1d), None)
    if not s or not e or s == e:
        return None
    return round((rows[e] - rows[s]) / rows[s] * 100, 2)

def classify(comp, mkt):
    if mkt is None:
        return None, None
    rel = round(comp - mkt, 2)
    # same direction & comparable size -> moved with the market
    if (comp >= 0) == (mkt >= 0) and abs(rel) <= 1.5:
        mt = 'with_market'
    elif (comp >= 0) != (mkt >= 0) and abs(mkt) > 1.0:
        mt = 'against_market'
    else:
        mt = 'company_specific'
    return rel, mt

def main():
    force = '--force' in sys.argv
    ok = skip = 0
    for f in sorted(PKTDIR.glob('*.json')):
        pkt = json.loads(f.read_text(encoding='utf-8'))
        pr = pkt.get('prices', {})
        if pr.get('market_pct') is not None and not force:
            skip += 1; continue
        p0d, p1d, cpct = pr.get('p0_date'), pr.get('p1_date'), pr.get('pct_change')
        if not (p0d and p1d and cpct is not None):
            continue
        mkt = topix_move(p0d, p1d)
        rel, mt = classify(cpct, mkt)
        pr['market_pct'] = mkt; pr['relative_pct'] = rel; pr['move_type'] = mt
        pkt['prices'] = pr
        f.write_text(json.dumps(pkt, ensure_ascii=False, indent=2), encoding='utf-8')
        ok += 1
        print(f'  {pkt["ticker"]:5} stock={cpct:+.2f}%  TOPIX={mkt}  rel={rel}  [{mt}]')
    print(f'\nupdated={ok} skipped={skip}')

if __name__ == '__main__':
    main()
