# -*- coding: utf-8 -*-
"""Reconcile web-resolved announce dates (from _datefix_results/y{YEAR}_*.json) into the
packets, then rebuild the stock window. Per ticker:
  • gather all candidate dates from every batch (cross-agent), + any existing
    announce_date_doc (authoritative cover-date) as a strong vote;
  • resolve = the cover-date if present, else the modal candidate;
  • validate it falls after period_end within [pe+5, pe+130] days;
  • apply: set announce_date, re-fetch P0->P1 prices + TOPIX-relative, flag S± flips.
Reports gaps (no candidate), conflicts (agents disagree), and out-of-window rejects.

Usage: PKTDIR_NAME=_pkts_2024 python build/reconcile_dates.py 2024
"""
from __future__ import annotations
import json, os, sys, glob
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from research import tempest_fetch as tf
import importlib.util
spec = importlib.util.spec_from_file_location('t2', ROOT / 'build' / 'add_tier2.py')
t2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t2)

YEAR = sys.argv[1]
PKTDIR = ROOT / 'data' / 'quarterly' / os.environ.get('PKTDIR_NAME', '_pkts')
RESDIR = ROOT / 'data' / 'quarterly' / '_datefix_results'

def gather():
    cand = {}
    for f in sorted(glob.glob(str(RESDIR / f'y{YEAR}_*.json'))):
        for r in json.loads(Path(f).read_text(encoding='utf-8')):
            d = r.get('announce_date')
            if d:
                cand.setdefault(r['t'], []).append(d)
    return cand

def in_window(d, pe):
    dt = datetime.strptime(d, '%Y-%m-%d'); p = datetime.strptime(pe, '%Y-%m-%d')
    return p + timedelta(days=5) <= dt <= p + timedelta(days=130)

def main():
    cand = gather()
    changed = flips = gaps = conflicts = oow = 0
    gap_list, conflict_list, flip_list = [], [], []
    for f in sorted(PKTDIR.glob('*.json')):
        pkt = json.loads(f.read_text(encoding='utf-8')); t = pkt['ticker']; pe = pkt['period_end']
        votes = list(cand.get(t, []))
        doc = pkt.get('announce_date_doc')
        if doc:
            votes = [doc, doc] + votes  # cover-date wins ties
        votes = [v for v in votes if in_window(v, pe)]
        if not votes:
            gaps += 1; gap_list.append(t); continue
        tally = Counter(votes); resolved, _ = tally.most_common(1)[0]
        distinct = set(v for v in cand.get(t, []) if in_window(v, pe))
        if len(distinct) > 1:
            conflicts += 1; conflict_list.append((t, dict(Counter(cand.get(t, [])))))
        old = pkt.get('announce_date'); old_dir = (pkt.get('prices', {}) or {}).get('stock_dir')
        if resolved == old:
            continue
        try:
            prices = tf.fetch_prices(t, resolved)
        except Exception as e:
            print(f'  {t} price refetch FAIL {e}'); continue
        mkt = t2.topix_move(prices['p0_date'], prices['p1_date'])
        rel, mt = t2.classify(prices['pct_change'], mkt)
        prices['market_pct'] = mkt; prices['relative_pct'] = rel; prices['move_type'] = mt
        pkt['announce_date'] = resolved; pkt['announce_date_doc'] = resolved; pkt['prices'] = prices
        f.write_text(json.dumps(pkt, ensure_ascii=False, indent=2), encoding='utf-8')
        changed += 1
        if old_dir and prices['stock_dir'] != old_dir:
            flips += 1; flip_list.append((t, old, resolved, old_dir, prices['stock_dir'], prices['pct_change']))
    print(f'== reconcile {YEAR} ({PKTDIR.name}) ==')
    print(f'applied={changed}  S±flips={flips}  gaps(no valid date)={gaps}  conflicts(agents disagree)={conflicts}')
    print('\nS± FLIPS:'); [print(f'  {t}: {o}->{n}  {od}->{nd} ({p}%)') for t,o,n,od,nd,p in flip_list]
    print('\nGAPS (need targeted fill):', gap_list)
    print('\nCONFLICTS (review):'); [print(f'  {t}: {v}') for t,v in conflict_list]

if __name__ == '__main__':
    main()
