# -*- coding: utf-8 -*-
"""Robustly collect a finished batch (results file is large due to embedded web content).

Streams .results() and ACCUMULATES by custom_id across multiple passes; a mid-stream
network drop just ends that pass, and the next pass picks up the ones still missing.
Saves progress after every pass, so partial results are never lost. Keeps only the
final structured JSON (drops the bulky web-tool blocks).
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
import anthropic

ROOT = Path(__file__).parent.parent
OUT = ROOT / 'data' / 'quarterly' / 'it_q4_2025.json'
BATCH_ID_FILE = ROOT / 'data' / 'quarterly' / '_batch_id.txt'

def env(k):
    for p in [ROOT.parent / '.env', ROOT / '.env']:
        if p.exists():
            for l in p.read_text(encoding='utf-8').splitlines():
                if l.strip().startswith(k + '='):
                    return l.split('=', 1)[1].strip().strip('"').strip("'")
    return ''
KEY = env('ANTHROPIC_API_KEY')

def extract_json(txt):
    try:
        return json.loads(txt)
    except Exception:
        pass
    m = re.search(r'\{.*\}', txt, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None

def main():
    bid = sys.argv[1] if len(sys.argv) > 1 else BATCH_ID_FILE.read_text().strip()
    c = anthropic.Anthropic(api_key=KEY, max_retries=0)
    # resume from any prior partial save
    companies = {}
    if OUT.exists():
        try:
            companies = json.load(open(OUT, encoding='utf-8')).get('companies', {})
        except Exception:
            companies = {}
    bad = {}
    PASSES = 10
    for p in range(1, PASSES + 1):
        before = len(companies)
        try:
            for res in c.messages.batches.results(bid):
                cid = res.custom_id
                if cid in companies:
                    continue
                if res.result.type != 'succeeded':
                    bad[cid] = res.result.type; continue
                txt = ''.join(b.text for b in res.result.message.content if b.type == 'text')
                obj = extract_json(txt)
                if obj:
                    companies[cid] = obj; bad.pop(cid, None)
                else:
                    bad[cid] = 'unparseable'
        except Exception as e:
            print(f'  pass {p}: stream dropped ({type(e).__name__}) after +{len(companies)-before}')
        # save progress every pass
        json.dump({'companies': companies}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'pass {p}: collected {len(companies)}/99  (bad={len(bad)})', flush=True)
        if len(companies) >= 99 or (len(companies) + len(bad)) >= 99:
            break
        time.sleep(3)
    print(f'\nSaved {len(companies)} companies -> {OUT}')
    if bad:
        print('PROBLEM:', bad)

if __name__ == '__main__':
    main()
