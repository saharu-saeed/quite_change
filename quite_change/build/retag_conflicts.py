# -*- coding: utf-8 -*-
"""Targeted re-tag of the 7 direction-conflict business tags (staged sets only).
Re-runs each with a direction-corrective hint: the business tag MUST match the actual net%/op%
direction; for multi-one-off holding/investment companies where no single tag is honest, use
'other' + put the offsetting story in the narrative. Keeps committed stock fields. Prints the
7-row before/after and re-checks direction-consistency. Updates it_q4_*_mdna.json in place.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
Q = ROOT / 'data' / 'quarterly'
sys.path.insert(0, str(ROOT / 'build'))
from run_it_noweb import prompt, pick_name
from run_it_batch import _env, MODEL, SCHEMA
import anthropic
c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))

CONFLICTS = {'2024': (['9984', '3825', '4344', '2121', '9404'], '_pkts_2024_mdna', 'it_q4_2024.json', 'it_q4_2024_mdna.json'),
             '2025': (['7860', '3791'], '_pkts_mdna', 'it_q4_2025.json', 'it_q4_2025_mdna.json')}
NET_DOWN = {'one_off_loss', 'one_off_gain_rolloff'}; NET_UP = {'one_off_gain', 'one-off_cost_rolloff'}
OP_DOWN = {'margin_compression'}; OP_UP = {'margin_expansion'}

def consistent(tag, opp, netp):
    if tag in NET_DOWN and netp is not None and netp > 1: return False
    if tag in NET_UP and netp is not None and netp < -1: return False
    if tag in OP_DOWN and opp is not None and opp > 1: return False
    if tag in OP_UP and opp is not None and opp < -1: return False
    return True

def main():
    rows = []
    for year, (tickers, pdir, oldf, newf) in CONFLICTS.items():
        staged = json.loads((Q / newf).read_text(encoding='utf-8'))
        committed = json.loads((Q / oldf).read_text(encoding='utf-8'))['companies']
        for t in tickers:
            p = json.loads((Q / pdir / f'{t}.json').read_text(encoding='utf-8'))
            nm_ = p['numbers']; opp, netp = nm_.get('op_pct'), nm_.get('net_pct')
            before = staged['companies'][t]['business_reason_tag']
            hint = (f"\n\n⚠️【方向補正・最優先】当社の前年比：営業利益 {opp}% / 純利益 {netp}%。"
                    f"business_reason_tag は必ずこの利益方向と整合させること（利益増ならgain/expansion系、利益減ならloss/compression系、"
                    f"増収主因なら volume/price/m&a/cyclical/fx）。\n"
                    f"⚠️ 複数の大型一過性損益が相殺し、単一の機械的タグでは業績を正直に説明できない投資・持株会社の場合は "
                    f"business_reason_tag='other' とし、相殺の内訳（例：評価損 vs デリバティブ益）を why_business_moved に明記すること。")
            m = c.messages.create(model=MODEL, max_tokens=5500,
                messages=[{'role': 'user', 'content': prompt(p) + hint}],
                output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}})
            cc = json.loads(''.join(b.text for b in m.content if b.type == 'text'))
            # keep committed stock fields (same merge rule)
            old = committed.get(t)
            if old:
                cc['stock_reason_tag'] = old.get('stock_reason_tag', cc.get('stock_reason_tag'))
                if old.get('why_stock_moved'): cc['why_stock_moved'] = old['why_stock_moved']
            staged['companies'][t] = cc
            after = cc['business_reason_tag']
            rows.append((year, t, pick_name(p), before, after, opp, netp, consistent(after, opp, netp)))
        (Q / newf).write_text(json.dumps(staged, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{"yr":5}{"tkr":6}{"name":16}{"before":24}{"after":22}{"op%":>7}{"net%":>7}  ok')
    for yr, t, nm, b, a, opp, netp, ok in rows:
        print(f'{yr:5}{t:6}{nm[:14]:16}{b:24}{a:22}{str(opp):>7}{str(netp):>7}  {"YES" if ok else "STILL-CONFLICT"}')

if __name__ == '__main__':
    main()
