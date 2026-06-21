# -*- coding: utf-8 -*-
"""Translate the Japanese card narratives to English so the EN toggle works.

The pipeline produces Japanese-only summaries; this adds English versions of the
4-part narrative + the grounding/event evidence as *_en fields on each company in
it_q4_{year}.staged.json. Bedrock, no web. Resumable (skips companies already
translated). Committed files untouched.

  python build/translate_narratives.py --limit 3   # smoke test
  python build/translate_narratives.py             # full (both years)
  python build/translate_narratives.py --year 2024
"""
from __future__ import annotations
import os, sys, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT.parent / '.env', override=True)
sys.path.insert(0, str(ROOT / 'build'))
sys.stdout.reconfigure(encoding='utf-8')
from anthropic import AnthropicBedrock

YEARS = ['2024', '2025']
FIELDS = ['overview', 'about_business', 'why_business_moved', 'why_stock_moved']
EVID = ['bucket_grounding', 'event_quote']

SCHEMA = {
    'type': 'object',
    'properties': {
        'overview_en': {'type': 'string'},
        'about_business_en': {'type': 'string'},
        'why_business_moved_en': {'type': 'string'},
        'why_stock_moved_en': {'type': 'string'},
        'bucket_grounding_en': {'type': 'string'},
        'event_quote_en': {'type': 'string'},
    },
    'required': ['overview_en', 'about_business_en', 'why_business_moved_en', 'why_stock_moved_en'],
    'additionalProperties': False,
}


def make_prompt(c):
    parts = [f"Translate these Japanese equity-research snippets for {c.get('ticker')} into natural, "
             f"plain English for a general reader. Keep every number / percentage / company & product "
             f"name exact. Do not add or omit facts. Keep each section about the same length.\n"]
    for f in FIELDS:
        parts.append(f"[{f}]\n{(c.get(f) or '').strip()}\n")
    for f in EVID:
        v = (c.get(f) or '').strip()
        if v:
            parts.append(f"[{f}]\n{v}\n")
    parts.append("\nReturn JSON with keys: overview_en, about_business_en, why_business_moved_en, "
                 "why_stock_moved_en, bucket_grounding_en, event_quote_en (use '' for any input that was empty).")
    return "\n".join(parts)


def translate(client, model, c):
    msg = client.messages.create(
        model=model, max_tokens=2500,
        messages=[{'role': 'user', 'content': make_prompt(c)}],
        output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}},
    )
    return json.loads(''.join(b.text for b in msg.content if b.type == 'text'))


def main():
    args = sys.argv[1:]
    limit = int(args[args.index('--limit') + 1]) if '--limit' in args else None
    one_year = args[args.index('--year') + 1] if '--year' in args else None
    model = os.environ['BEDROCK_MODEL_ID']
    client = AnthropicBedrock(
        aws_region=os.environ['AWS_REGION'], aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        aws_session_token=os.environ.get('AWS_SESSION_TOKEN') or None)

    for year in ([one_year] if one_year else YEARS):
        p = ROOT / 'data' / 'quarterly' / f'it_q4_{year}.staged.json'
        data = json.loads(p.read_text(encoding='utf-8'))
        comps = data['companies']
        todo = [c for c in comps.values()
                if c.get('specific_bucket') and c.get('overview') and not c.get('overview_en')]
        if limit:
            todo = todo[:limit]
        print(f'[{year}] translating {len(todo)} companies...', flush=True)
        done = 0
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(translate, client, model, c): c['ticker'] for c in todo}
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    r = fut.result()
                    comps[t].update({k: v for k, v in r.items() if v})
                    done += 1
                    if done % 20 == 0:
                        print(f'  [{year}] {done}/{len(todo)}', flush=True)
                except Exception as e:
                    print(f'  {t}: ERROR {e}', flush=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'[{year}] translated {done}, written (committed untouched).', flush=True)


if __name__ == '__main__':
    main()
