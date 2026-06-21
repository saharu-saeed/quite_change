# -*- coding: utf-8 -*-
"""Classify a cohort packet dir on Bedrock SYNC (Anthropic key is out of credits).
Uses the EXACT committed prompt + SCHEMA (run_it_noweb / run_it_batch) so 2023/2022 are
methodologically identical to the committed 2024/2025 (clean 4-year comparison).
Tracks real token cost and HARD-STOPS before BUDGET_USD. Resumable. Output matches the
committed it_q4_2024.json shape (schema output keyed by ticker).

Usage:
  PKTDIR_NAME=_pkts_2023_mdna OUT_FILE=it_q4_2023.json BUDGET_USD=13 \
    python build/run_cohort_bedrock.py 2023
"""
from __future__ import annotations
import os, sys, json
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT.parent / '.env', override=True)         # new_quick/.env
os.environ.pop('ANTHROPIC_API_KEY', None)                # force Bedrock (dead Anthropic key)
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))

from run_it_noweb import prompt                           # identical committed prompt
from run_it_batch import SCHEMA
from anthropic import AnthropicBedrock

PIN, POUT = 3.0 / 1e6, 15.0 / 1e6                          # Bedrock Sonnet sync pricing
BUDGET = float(os.environ.get('BUDGET_USD', '13'))
MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-6')
fy = sys.argv[1]
PKTDIR = ROOT / 'data' / 'quarterly' / os.environ['PKTDIR_NAME']
OUT = ROOT / 'data' / 'quarterly' / os.environ['OUT_FILE']
LIMIT = int(os.environ['LIMIT']) if os.environ.get('LIMIT') else None

client = AnthropicBedrock(
    aws_region=os.environ.get('AWS_REGION', 'us-east-1'),
    aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_key=os.environ['AWS_SECRET_ACCESS_KEY'])

companies = json.load(open(OUT, encoding='utf-8')).get('companies', {}) if OUT.exists() else {}
pkts = sorted(PKTDIR.glob('*.json'))
tin = tout = 0; cost = 0.0; done = 0
print(f'FY{fy}: {len(pkts)} packets | budget ${BUDGET} | model {MODEL_ID}')
for f in pkts:
    pkt = json.loads(f.read_text(encoding='utf-8')); t = pkt['ticker']
    if t in companies: continue
    if not pkt.get('prices', {}).get('stock_dir'): continue
    if cost + 0.07 > BUDGET:
        print(f'  *** HARD-STOP at ${cost:.2f} (budget ${BUDGET}) — {len(companies)} done, rest unprocessed ***'); break
    try:
        msg = client.messages.create(
            model=MODEL_ID, max_tokens=5500, temperature=0,
            messages=[{'role': 'user', 'content': prompt(pkt)}],
            output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}})
    except Exception as e:
        print(f'  {t}: ERR {str(e)[:70]}'); continue
    u = msg.usage; tin += u.input_tokens; tout += u.output_tokens
    cost = tin * PIN + tout * POUT
    try:
        data = json.loads(msg.content[0].text)
    except Exception:
        data = {'ticker': t, 'parse_error': msg.content[0].text[:200]}
    data['ticker'] = t
    companies[t] = data; done += 1
    if done % 10 == 0:
        print(f'  {done} done | ${cost:.2f} | last {t}')
        json.dump({'companies': companies}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    if LIMIT and done >= LIMIT: break
json.dump({'companies': companies}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'FY{fy} DONE: {len(companies)} classified this/total | in {tin} out {tout} | COST ${cost:.2f} -> {OUT.name}')
