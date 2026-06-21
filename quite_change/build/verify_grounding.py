# -*- coding: utf-8 -*-
"""Pre-run grounding gate (Fix D). Asserts, per packet:
  • tanshin source (if present) is a PRIMARY document, never a live aggregator page;
  • a restated/missing-numbers company HAS a primary tanshin (else its numbers can't be
    grounded point-in-time → must be flagged, not silently storytold);
  • announce_date matches the doc-derived date where we have one.
Prints a clean PASS or an itemized list of problems. Run before any LLM re-run.
"""
from __future__ import annotations
import json, os, sys, glob
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from prefetch_tanshin import is_primary_source

PKTDIR = ROOT / 'data' / 'quarterly' / os.environ.get('PKTDIR_NAME', '_pkts')

def main():
    agg, restated_nogrnd, date_mismatch, fallback = [], [], [], []
    n = 0
    for f in sorted(glob.glob(str(PKTDIR / '*.json'))):
        p = json.loads(Path(f).read_text(encoding='utf-8')); n += 1
        t = p['ticker']; src = p.get('tanshin_source_url', ''); has_tan = bool(p.get('tanshin_text'))
        nums = p.get('numbers', {}) or {}
        if has_tan and not is_primary_source(src):
            agg.append((t, src[:55]))
        if not has_tan:
            fallback.append(t)
        # restated/missing numbers are groundable if we have a primary tanshin OR the
        # ORIGINAL (non-amended) 有報 why_text (fetch_why_text selects is_amendment=False →
        # as-originally-reported = announce-date figures), OR a vetted override.
        groundable = (has_tan and is_primary_source(src)) or bool(p.get('why_text')) or nums.get('_pit_override')
        if p.get('needs_tanshin') and not groundable:
            restated_nogrnd.append((t, p.get('needs_tanshin_reason')))
        ad, adoc = p.get('announce_date'), p.get('announce_date_doc')
        if adoc and ad != adoc:
            date_mismatch.append((t, ad, adoc))
    print(f'== grounding verify ({PKTDIR.name}, {n} packets) ==')
    print(f'aggregator sources still present : {len(agg)} {"✓" if not agg else "✗"}')
    for x in agg: print('   AGG:', x)
    print(f'restated/missing w/o primary tanshin (ungroundable numbers): {len(restated_nogrnd)} {"✓" if not restated_nogrnd else "✗ FLAG"}')
    for x in restated_nogrnd: print('   NUM:', x)
    print(f'announce_date ≠ doc-derived (should be 0 after rebuild): {len(date_mismatch)}')
    for x in date_mismatch[:30]: print('   DATE:', x)
    print(f'有報-fallback (no tanshin, prose from 有報): {len(fallback)}  {fallback}')
    ok = not agg and not restated_nogrnd and not date_mismatch
    print('\nRESULT:', 'PASS ✓' if ok else 'NEEDS FIX ✗')

if __name__ == '__main__':
    main()
