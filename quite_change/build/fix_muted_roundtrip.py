# -*- coding: utf-8 -*-
"""FREE muted-label honesty fix (no LLM, no price refetch).

A company tagged `muted_no_reaction` because its 2-week NET landed within ±1% can still have
swung violently intra-window and round-tripped back to flat (e.g. 4733 OBC −10.8%→+0.9%,
4483 JMDC −20.2%→−0.4%). The stored prose for those calls it "無反応 / 微動 / didn't move /
priced in" — which is false. This pass, deterministically and only for those round-tripped
cards:
  • flags c['muted_round_trip'] = True (+ the dominant excursion / day / shape),
  • REPLACES why_stock_moved / _en with an honest, price-only statement: net is flat, but it
    moved ±X% intra-window before round-tripping; the cause of the swing/recovery is NOT in the
    report (rail: shape/timing = fact from prices; cause needs the filing; never invented).

The tag stays muted_no_reaction (the 2-week NET genuinely is flat — quadrant/stats unchanged).
Only the round-trip subset's prose is rewritten; genuinely-quiet muted cards are untouched.

  python build/fix_muted_roundtrip.py            # all 4 years
  python build/fix_muted_roundtrip.py --dry
"""
from __future__ import annotations
import sys, json
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.stdout.reconfigure(encoding='utf-8')
YEARS = ['2022', '2023', '2024', '2025']
PKT = {'2022': '_pkts_2022_mdna', '2023': '_pkts_2023_mdna', '2024': '_pkts_2024_mdna', '2025': '_pkts_mdna'}


def packet_rel(year, ticker):
    """relative_pct (vs TOPIX) lives in the packet prices, not the staged record."""
    p = ROOT / 'data' / 'quarterly' / PKT[year] / f'{ticker}.json'
    if not p.exists():
        return None
    try:
        return (json.loads(p.read_text(encoding='utf-8')).get('prices', {}) or {}).get('relative_pct')
    except Exception:
        return None

RANGE_MIN = 4.0   # max-min over the window
EXC_MIN = 4.0     # dominant one-way excursion depth


def rewrite(net, exc, day, shape, rel):
    dirj = '下落' if exc < 0 else '上昇'
    dire = 'down' if exc < 0 else 'up'
    relj = f"同期間の対TOPIX相対騰落率は{rel:+.1f}%。" if rel is not None else ""
    rele = f" It was {rel:+.1f}% versus TOPIX over the same window." if rel is not None else ""
    jp = (f"決算発表後の14営業日で株価はネット{net:+.1f}%とほぼ横ばいに着地した。"
          f"ただし終値だけを見ると無反応に見えるが、期中には一時{exc:+.1f}%（{day}営業日目付近）まで{dirj}しており、"
          f"実際には大きく動いてから元の水準へ往復した（往復型のフラット、決算直後に動いて以後戻した）。"
          f"{relj}"
          "戻り（往復）の主因は決算短信に明示がなく、後日の市場・需給要因による可能性があり、"
          "決算発表への直接反応とは断定できない。")
    en = (f"Over the 14 trading days after the earnings announcement the stock netted {net:+.1f}% — essentially flat at the close. "
          f"The flat endpoint is misleading, however: intra-window it moved as much as {exc:+.1f}% ({dire}, around day {day}) "
          f"before round-tripping back to roughly where it started (a flat-by-round-trip, not a quiet tape)."
          f"{rele} "
          "The cause of the swing and recovery is not stated in the earnings report, so it may reflect later "
          "market / supply-demand factors rather than a direct reaction to the results.")
    return jp, en


def main():
    dry = '--dry' in sys.argv
    for y in YEARS:
        sp = ROOT / 'data' / 'quarterly' / f'it_q4_{y}.staged.json'
        if not sp.exists():
            print(f'[{y}] no staged file, skip'); continue
        data = json.loads(sp.read_text(encoding='utf-8'))
        comps = data['companies']
        fixed = []
        for t, c in comps.items():
            if c.get('stock_reason_tag') != 'muted_no_reaction':
                continue
            pp = c.get('path_pct')
            if not pp or len(pp) < 4:
                continue
            mx, mn = max(pp), min(pp)
            rng = mx - mn
            exc_depth = max(abs(mn), abs(mx))
            if rng < RANGE_MIN or exc_depth < EXC_MIN:
                continue  # genuinely quiet → leave as-is
            # dominant excursion (the bigger one-way move) + the day it happened
            if abs(mn) >= abs(mx):
                exc, day = round(mn, 1), pp.index(mn)
            else:
                exc, day = round(mx, 1), pp.index(mx)
            net = round(pp[-1], 1)
            rel = packet_rel(y, t)
            jp, en = rewrite(net, exc, day, c.get('path_shape'), rel)
            c['muted_round_trip'] = True
            c['round_trip_excursion'] = {'exc': exc, 'day': day, 'shape': c.get('path_shape')}
            c['why_stock_moved'] = jp
            c['why_stock_moved_en'] = en
            fixed.append((t, net, exc, day))
        print(f'\n[{y}] {len(fixed)} muted round-trip cards relabeled honestly')
        for t, net, exc, day in sorted(fixed, key=lambda x: x[2]):
            print(f'   {t}: net{net:+} but {exc:+}% intra-window (day {day})')
        if not dry:
            sp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'[{y}] written.')
        else:
            print(f'[{y}] --dry: not written.')


if __name__ == '__main__':
    main()
