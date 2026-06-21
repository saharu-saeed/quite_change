# -*- coding: utf-8 -*-
"""Resolve fiscal period-end + tanshin announce date for the 100 selected IT companies.

Strategy (point-in-time correct, mostly free):
  • period_end : deterministic from Tempest financials — the ANNUAL row whose
                 period_end falls in calendar 2025 (handles March/Dec/other FYE).
  • announce   : (1) reuse KNOWN dates (11 validated set + phase-1 it_q4_2025.json),
                 (2) else web-search (Tavily) for the FY tanshin date,
                 (3) VALIDATE: must be a trading day in Tempest prices and fall in
                     the plausible window [period_end+15, period_end+80] days.
                 Anything not confidently validated is left as null (manual review) —
                 we never guess an announce date (would mis-set the stock window).

Output: data/quarterly/it_100_dates.json
"""
from __future__ import annotations
import json, re, sys, urllib.request, urllib.error
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from research import tempest_fetch as tf  # noqa: E402

SEL = ROOT / 'data' / 'quarterly' / 'it_100_selection.json'
PHASE1 = ROOT / 'data' / 'quarterly' / 'it_q4_2025.json'
OUT = ROOT / 'data' / 'quarterly' / 'it_100_dates.json'

# Tavily key from repo .env
def _env(key):
    for p in [ROOT.parent / '.env', ROOT / '.env']:
        if p.exists():
            for line in p.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line and not line.startswith('#') and line.split('=', 1)[0].strip() == key:
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''
TAVILY = _env('TAVILY_API_KEY')

# 11 validated announce dates (from the known-answer set)
KNOWN = {
    '9433': '2025-05-14', '3778': '2025-04-28', '4307': '2025-04-24', '3659': '2026-02-12',
    '3994': '2026-01-14', '4689': '2025-05-07', '9602': '2025-04-14', '4676': '2025-05-16',
    '9468': '2025-05-08', '4385': '2025-08-05', '9984': '2025-05-13',
}

def load_phase1_known():
    out = {}
    if PHASE1.exists():
        try:
            d = json.load(open(PHASE1, encoding='utf-8'))
            for t, c in d.get('companies', {}).items():
                a = c.get('announce_date')
                if a and re.match(r'\d{4}-\d{2}-\d{2}', str(a)):
                    out[str(t)] = a[:10]
        except Exception as e:
            print(f'(phase-1 load skipped: {e})')
    return out

def period_end_2025(ticker):
    """Annual row whose period_end is in calendar 2025."""
    try:
        d = tf.api(f'/companies/{ticker}/financials?from_fy=2023&to_fy=2026&limit=40')
    except Exception:
        return None
    annual = [r for r in d.get('data', [])
              if r.get('period_end') and not r.get('fiscal_quarter')
              and '2025-01-01' <= r['period_end'] <= '2025-12-31']
    if annual:
        return annual[0]['period_end']
    # fallback: any 2025 period_end
    any25 = [r for r in d.get('data', []) if r.get('period_end', '')[:4] == '2025']
    return any25[0]['period_end'] if any25 else None

def price_calendar(ticker, around):
    """Sorted trading dates available within ~100 days of `around`."""
    a = datetime.strptime(around, '%Y-%m-%d')
    frm = (a - timedelta(days=10)).strftime('%Y-%m-%d')
    to = (a + timedelta(days=20)).strftime('%Y-%m-%d')
    try:
        d = tf.api(f'/companies/{ticker}/prices?from={frm}&to={to}&limit=200')
        return sorted({r['date'] for r in d.get('data', [])})
    except Exception:
        return []

def validate(ticker, cand, period_end):
    """Return the validated announce date (snap to trading day on/before) or None."""
    pe = datetime.strptime(period_end, '%Y-%m-%d')
    lo, hi = pe + timedelta(days=15), pe + timedelta(days=80)
    dt = datetime.strptime(cand, '%Y-%m-%d')
    if not (lo <= dt <= hi):
        return None
    cal = price_calendar(ticker, cand)
    if not cal:
        return None
    if cand in cal:
        return cand
    prior = [x for x in cal if x <= cand]
    return prior[-1] if prior else None

DATE_RE = re.compile(r'(20\d{2})[年\-/\.](\d{1,2})[月\-/\.](\d{1,2})')

def tavily_dates(query):
    if not TAVILY:
        return []
    body = json.dumps({'api_key': TAVILY, 'query': query, 'max_results': 5,
                       'search_depth': 'basic'}).encode()
    req = urllib.request.Request('https://api.tavily.com/search', data=body,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
    except Exception as e:
        print(f'    (tavily err: {e})'); return []
    blob = ' '.join([d.get('answer') or ''] + [x.get('content', '') + ' ' + x.get('title', '')
                                               for x in d.get('results', [])])
    out = []
    for y, m, day in DATE_RE.findall(blob):
        try:
            out.append(datetime(int(y), int(m), int(day)).strftime('%Y-%m-%d'))
        except ValueError:
            pass
    return out

def resolve_announce(ticker, name, period_end):
    pe = datetime.strptime(period_end, '%Y-%m-%d')
    # ticker code + 適時開示 anchors the search on the right fiscal year's disclosure
    queries = [
        f'{name} {ticker} {pe.year}年{pe.month}月期 決算 発表 適時開示',
        f'{name} {ticker} {pe.year}年{pe.month}月期 通期 決算短信',
    ]
    cands = set()
    for q in queries:
        for c in tavily_dates(q):
            v = validate(ticker, c, period_end)
            if v:
                cands.add(v)
        if cands:
            break
    if not cands:
        return None
    # the tanshin is the FIRST earnings disclosure in the post-FYE window
    return min(cands)

def main():
    sel = json.load(open(SEL, encoding='utf-8'))
    known = dict(KNOWN); known.update(load_phase1_known())
    print(f'known announce dates available: {len(known)}')

    out, n_known, n_web, n_unres, n_nope = [], 0, 0, 0, 0
    for s in sel:
        t = s['ticker']
        pe = period_end_2025(t)
        rec = {**s, 'period_end': pe, 'announce': None, 'date_source': None}
        if not pe:
            rec['date_source'] = 'no_period_end'; n_nope += 1
            out.append(rec); print(f'  {t} {s["name"][:24]:24} : NO period_end'); continue
        if t in known and validate(t, known[t], pe):
            rec['announce'] = validate(t, known[t], pe); rec['date_source'] = 'known'; n_known += 1
        else:
            a = resolve_announce(t, s['name_jp'] or s['name'], pe)
            if a:
                rec['announce'] = a; rec['date_source'] = 'web'; n_web += 1
            else:
                rec['date_source'] = 'UNRESOLVED'; n_unres += 1
        out.append(rec)
        tag = rec['date_source']
        print(f'  {t} {s["name"][:24]:24} pe={pe} announce={rec["announce"]} [{tag}]')

    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\nWritten: {OUT}')
    print(f'known={n_known}  web={n_web}  UNRESOLVED={n_unres}  no_period_end={n_nope}  total={len(out)}')
    if n_unres or n_nope:
        print('\nNeeds manual announce date:')
        for r in out:
            if r['date_source'] in ('UNRESOLVED', 'no_period_end'):
                print(f'  {r["ticker"]} {r["name"]} (pe={r["period_end"]})')

if __name__ == '__main__':
    main()
