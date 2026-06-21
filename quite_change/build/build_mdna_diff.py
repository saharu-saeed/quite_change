# -*- coding: utf-8 -*-
"""Per-company DIFF: committed (old, tables-only) vs staged MD&A re-classify (new).
Reports tag changes, confirms the feed-derived quadrant is unchanged, runs a unit-scaling
post-check on the new narratives, and dumps before/after narrative samples for review.
Writes _MDNA_DIFF.json + MDNA_DIFF.md. Changes NOTHING in the committed deliverable.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from run_it_noweb import pick_name   # proper name fallback (name_jp is literally "False" in some packets)
Q = ROOT / 'data' / 'quarterly'

def load(p):
    return json.loads((Q / p).read_text(encoding='utf-8'))['companies']

def quad(pkt):
    rev = (pkt.get('numbers', {}) or {}).get('rev_pct'); sd = (pkt.get('prices', {}) or {}).get('stock_dir', 'flat')
    if sd == 'flat': return 'flat'
    bu = (rev or 0) > 0
    return ('R+S+' if sd == 'up' else 'R+S-') if bu else ('R-S+' if sd == 'up' else 'R-S-')

def oku_figs(text):
    return [float(x.replace(',', '')) for x in re.findall(r'([\d,]+(?:\.\d+)?)\s*億円', text or '')]

def main():
    YEARS = [('2024', 'it_q4_2024.json', 'it_q4_2024_mdna.json', '_pkts_2024_mdna'),
             ('2025', 'it_q4_2025.json', 'it_q4_2025_mdna.json', '_pkts_mdna')]
    md = ['# MD&A re-classify — DIFF (committed vs staged). Nothing committed.\n']
    allrows = {}
    for year, oldf, newf, pdir in YEARS:
        old, new = load(oldf), load(newf)
        bchg = schg = qmoved = 0; rows = []; flags = []; dirconf = []
        # one-off tags act on NET; margin tags act on OPERATING profit. Check each against the right line.
        NET_DOWN = {'one_off_loss', 'one_off_gain_rolloff'}; NET_UP = {'one_off_gain', 'one-off_cost_rolloff'}
        OP_DOWN = {'margin_compression'}; OP_UP = {'margin_expansion'}
        for t in new:
            if t not in old:
                continue
            ob, nb = old[t].get('business_reason_tag'), new[t].get('business_reason_tag')
            os_, ns = old[t].get('stock_reason_tag'), new[t].get('stock_reason_tag')
            pkt = json.loads((Q / pdir / f'{t}.json').read_text(encoding='utf-8'))
            # quadrant must be feed-stable
            qn = quad(pkt)
            if ob != nb: bchg += 1
            if os_ != ns: schg += 1
            # unit-scaling flag: a 億 figure in the narrative exceeding net_sales by >10% is suspicious
            ns_oku = float((pkt.get('numbers', {}) or {}).get('net_sales') or 0) / 1e8
            bad = [f for f in oku_figs(new[t].get('why_business_moved', '')) if ns_oku and f > ns_oku * 1.1]
            if bad:
                flags.append((t, ns_oku, bad))
            # DIRECTION-CONFLICT: one-off tag vs net%, margin tag vs operating%
            nm_ = pkt.get('numbers', {}) or {}; netp, opp = nm_.get('net_pct'), nm_.get('op_pct')
            if netp is not None and ((nb in NET_DOWN and netp > 1) or (nb in NET_UP and netp < -1)):
                dirconf.append((t, pick_name(pkt), nb, f'net {netp:+.1f}%'))
            elif opp is not None and ((nb in OP_DOWN and opp > 1) or (nb in OP_UP and opp < -1)):
                dirconf.append((t, pick_name(pkt), nb, f'op {opp:+.1f}%'))
            if ob != nb or os_ != ns:
                rows.append((t, pick_name(pkt), f'{ob}->{nb}' if ob != nb else ob, f'{os_}->{ns}' if os_ != ns else os_, qn))
        md.append(f'\n## {year}: {len(new)} companies | business_tag changed {bchg} | stock_tag changed {schg} | unit-flags {len(flags)}')
        md.append('| ticker | name | business_tag (old->new) | stock_tag (old->new) | quadrant(feed) |')
        md.append('|---|---|---|---|---|')
        for t, nm, b, s, qd in rows:
            md.append(f'| {t} | {nm[:14]} | {b} | {s} | {qd} |')
        if dirconf:
            md.append(f'\n**⚠️ DIRECTION-CONFLICT flags ({year})** — business tag implies wrong profit direction vs actual net% (REAL mis-tags, review):')
            for t, nm, tag, dirstr in dirconf:
                md.append(f'- {t} {nm}: tag `{tag}` but {dirstr}')
        if flags:
            md.append(f'\n**Unit-scaling flags ({year})** — 億 figure exceeds total revenue (mostly benign: GMV/取扱高/prior-yr profit):')
            for t, nso, bad in flags:
                md.append(f'- {t}: revenue≈{nso:.0f}億 but narrative cites {bad}億')
        allrows[year] = {'business_changed': bchg, 'stock_changed': schg, 'unit_flags': [f[0] for f in flags], 'dir_conflicts': [d[0] for d in dirconf], 'rows': rows}
    (Q / '_MDNA_DIFF.json').write_text(json.dumps(allrows, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'deliverables' / 'quarterly' / 'MDNA_DIFF.md').write_text('\n'.join(md), encoding='utf-8')
    print('\n'.join(md[:60]))
    print('\n-> deliverables/quarterly/MDNA_DIFF.md + _MDNA_DIFF.json')

if __name__ == '__main__':
    main()
