# -*- coding: utf-8 -*-
"""Apply 決算短信 grounding (from _grounding_results/y{YEAR}_*.json produced by the grounding
agents) to the packets, doing four things in one pass:
  1. GROUNDING: compose tanshin_text from results+guidance+capital_return+oneoff so the
     re-run can recover guidance_disappointment + capital_return_surprise. Set primary src.
  2. DATE CROSS-CHECK: the 決算短信 cover_date is authoritative; if it differs from the
     current announce_date (in-window), re-window (re-fetch prices + TOPIX-relative).
  3. RESTATED RE-SCREEN: for restated companies, parse the ORIGINAL rev/op/net % from the
     report and store as _pit_override (so R± screens on original, not restated, numbers).
  4. Report R± sign changes (companies leaving the revenue-up set).

Usage: PKTDIR_NAME=_pkts_2024 python build/apply_grounding.py 2024
"""
from __future__ import annotations
import json, os, re, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from research import tempest_fetch as tf
sys.path.insert(0, str(ROOT / 'build'))
from prefetch_tanshin import is_primary_source
import importlib.util
spec = importlib.util.spec_from_file_location('t2', ROOT / 'build' / 'add_tier2.py')
t2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t2)

YEAR = sys.argv[1]
PKTDIR = ROOT / 'data' / 'quarterly' / os.environ.get('PKTDIR_NAME', '_pkts')
RESDIR = ROOT / 'data' / 'quarterly' / '_grounding_results'

def load_grounding():
    g = {}
    for f in sorted(glob.glob(str(RESDIR / f'y{YEAR}_*.json'))):
        for r in json.loads(Path(f).read_text(encoding='utf-8')):
            if r.get('found') and r.get('t'):
                g[r['t']] = r
    return g

def compose(r):
    parts = []
    for label, key in [('当期実績', 'results'), ('翌期業績予想', 'guidance'),
                       ('配当・自己株式（資本還元）', 'capital_return'), ('一過性損益', 'oneoff')]:
        v = (r.get(key) or '').strip()
        if v:
            parts.append(f'【{label}】{v}')
    return '\n'.join(parts)

def parse_pct(text, *kws):
    """Best-effort: first signed % appearing right after any keyword."""
    for kw in kws:
        m = re.search(kw + r'[^%＋\-0-9]{0,12}([+\-＋▲△]?\s?\d+\.?\d*)\s?[%％]', text)
        if m:
            s = m.group(1).replace('＋', '').replace('△', '-').replace('▲', '-').replace(' ', '')
            try: return float(s)
            except ValueError: pass
    return None

def in_window(d, pe):
    try: dt = datetime.strptime(d, '%Y-%m-%d'); p = datetime.strptime(pe, '%Y-%m-%d')
    except Exception: return False
    return p + timedelta(days=5) <= dt <= p + timedelta(days=130)

def main():
    g = load_grounding()
    grounded = rewindowed = overrides = signflip = nonprimary = 0
    flips, signflips = [], []
    for f in sorted(PKTDIR.glob('*.json')):
        pkt = json.loads(f.read_text(encoding='utf-8')); t = pkt['ticker']; pe = pkt['period_end']
        r = g.get(t)
        if not r:
            continue
        # 1. grounding
        txt = compose(r)
        if txt and r.get('src') and is_primary_source(r['src']):
            pkt['tanshin_text'] = txt; pkt['tanshin_source_url'] = r['src']; grounded += 1
        elif r.get('src') and not is_primary_source(r['src']):
            nonprimary += 1
        # 3. restated override (original numbers)
        if (pkt.get('numbers') or {}).get('restated'):
            res = r.get('results', '')
            ov = {'rev_pct': parse_pct(res, '売上高', '売上収益', '営業収益'),
                  'op_pct': parse_pct(res, '営業利益'),
                  'net_pct': parse_pct(res, '純利益', '当期利益')}
            ov = {k: v for k, v in ov.items() if v is not None}
            if ov:
                old_rev = pkt['numbers'].get('rev_pct')
                pkt['numbers']['_pit_override'] = ov; overrides += 1
                nr = ov.get('rev_pct')
                if nr is not None and old_rev is not None and (nr > 0) != (old_rev > 0):
                    signflip += 1; signflips.append((t, old_rev, nr))
        # 2. cover-date cross-check
        cd = r.get('cover_date')
        if cd and in_window(cd, pe) and cd != pkt.get('announce_date'):
            old = pkt.get('announce_date'); old_dir = (pkt.get('prices', {}) or {}).get('stock_dir')
            try:
                prices = tf.fetch_prices(t, cd)
                mkt = t2.topix_move(prices['p0_date'], prices['p1_date']); rel, mt = t2.classify(prices['pct_change'], mkt)
                prices['market_pct'] = mkt; prices['relative_pct'] = rel; prices['move_type'] = mt
                pkt['announce_date'] = cd; pkt['announce_date_doc'] = cd; pkt['prices'] = prices
                rewindowed += 1
                if old_dir and prices['stock_dir'] != old_dir:
                    flips.append((t, old, cd, old_dir, prices['stock_dir'], prices['pct_change']))
            except Exception as e:
                print(f'  {t} cover-date rewindow FAIL {e}')
        f.write_text(json.dumps(pkt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'== apply_grounding {YEAR} ==')
    print(f'grounded(決算短信)={grounded}  cover-date rewindows={rewindowed}  restated overrides={overrides}  non-primary-skipped={nonprimary}')
    print(f'cover-date S± flips: {flips}')
    print(f'restated R± SIGN changes: {signflips}')
    missing = [p.stem for p in PKTDIR.glob('*.json') if p.stem not in g]
    print(f'NOT grounded ({len(missing)}): {missing}')

if __name__ == '__main__':
    main()
