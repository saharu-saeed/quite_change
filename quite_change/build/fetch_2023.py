# -*- coding: utf-8 -*-
"""Expand the flash-report DB to 2023 for the full IT universe, and retry the
2024/2025 misses. Reuses build_flash_db.process() verbatim (same download w/
mirror-fallback, pdf extract, identity/doctype gates, atomic writes, SQLite,
resume). Free (irbank /tdnet + jiji mirror). Nothing classified, no LLM.

  python build/fetch_2023.py --limit 3     # smoke test (3 companies)
  python build/fetch_2023.py --misses      # only retry 2024/2025 misses
  python build/fetch_2023.py               # full: retry misses + all-IT 2023
Resumable: skips any ticker that already has {fy}_tanshin.txt.
"""
from __future__ import annotations
import json, sys, time
sys.path.insert(0, 'build')
sys.stdout.reconfigure(encoding='utf-8')
import build_flash_db as bdb

ROOT, FR = bdb.ROOT, bdb.FR
MISSES = {'2024': ['3681', '3788', '3841', '4011', '4169', '4387', '4751', '9408', '9753'],
          '2025': ['3661', '3769', '3909', '3932', '4051', '4284', '4335', '4392', '4644', '4689', '4813', '9605']}


def has_txt(ticker, fy):
    return (FR / ticker / f'{fy}_tanshin.txt').exists()


def shift_back(pe):           # 2024-03-31 -> 2023-03-31 (fiscal month is stable)
    return str(int(pe[:4]) - 1) + pe[4:]


def main():
    args = sys.argv[1:]
    limit = int(args[args.index('--limit') + 1]) if '--limit' in args else None
    misses_only = '--misses' in args
    retry_misses = misses_only or '--retry-misses' in args   # opt-in: slow + mostly unrecoverable
    tg = json.loads((ROOT / 'data' / 'quarterly' / '_all_it_targets.json').read_text(encoding='utf-8'))
    by_ticker_2024 = {x['ticker']: x for x in tg if x['fy'] == '2024'}
    c = bdb.db_init()

    # ── Part A: retry 2024/2025 misses (opt-in) ──
    rec = 0
    if not retry_misses:
        print('=== skipping 2024/2025 miss-retry (opt-in via --retry-misses; they are delayed/delisted '
              'or mirror-404, not recoverable on this free path) ===', flush=True)
    for fy, tickers in (MISSES.items() if retry_misses else []):
        for t in tickers:
            x = next((r for r in tg if r['ticker'] == t and r['fy'] == fy), None)
            if not x:
                print(f'  {fy} {t}: not in targets'); continue
            if has_txt(t, fy):
                print(f'  {fy} {t}: already have txt (recovered earlier)'); rec += 1; continue
            try:
                st, secs, n = bdb.process(c, t, fy, x['period_end'], x['name'])
            except Exception as e:
                st = f'error:{type(e).__name__}'
            if st == 'ok':
                rec += 1
            print(f'  {fy} {t} {x["name"][:12]}: {st}', flush=True)
            time.sleep(bdb.DELAY)
    print(f'misses recovered/now-present: {rec}', flush=True)
    if misses_only:
        return

    # ── Part B: 2023 for the full IT universe ──
    print('\n=== fetch 2023 (all IT universe) ===', flush=True)
    tickers = sorted(by_ticker_2024)
    if limit:
        tickers = tickers[:limit]
    ok = miss404 = delayed = other = skip = 0
    for i, t in enumerate(tickers, 1):
        if has_txt(t, '2023'):
            skip += 1; ok += 1; continue
        x = by_ticker_2024[t]
        try:
            st, secs, n = bdb.process(c, t, '2023', shift_back(x['period_end']), x['name'])
        except Exception as e:
            st = f'error:{type(e).__name__}'
        if st == 'ok':
            ok += 1
        elif 'download_404' in str(st):
            miss404 += 1
        elif 'delayed' in str(st) or 'unlisted' in str(st):
            delayed += 1
        else:
            other += 1
        if i % 25 == 0 or limit:
            print(f'  [{i}/{len(tickers)}] {t}: {st} | ok={ok} 404={miss404} delayed={delayed} other={other}', flush=True)
        time.sleep(bdb.DELAY)
    print(f'\n2023 DONE: ok={ok} (skip-existing={skip}) download_404={miss404} '
          f'delayed/unlisted={delayed} other={other} of {len(tickers)}', flush=True)


if __name__ == '__main__':
    main()
