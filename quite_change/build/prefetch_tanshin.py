# -*- coding: utf-8 -*-
"""Tier 1 — pre-fetch the announce-date 決算短信 text per company (FREE via Tavily, no key).

Tavily advanced search + include_raw_content returns the tanshin's text directly (guidance
業績予想, 対前期/対計画, 配当, 自己株式). We VALIDATE it's the right document by requiring the
fiscal period string + the company's actual net_sales figure (from Tempest) to appear in
the text — a strong PIT check that it's THIS period's announce-date report, not a later one.

Adds pkt['tanshin_text'] + pkt['tanshin_source_url'] on success; leaves them unset on
failure (the runner then falls back to the 有報 why_text). Reports the success rate.
"""
from __future__ import annotations
import importlib.util, json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
import os
PKTDIR = ROOT / 'data' / 'quarterly' / os.environ.get('PKTDIR_NAME', '_pkts')
spec = importlib.util.spec_from_file_location('rd', ROOT / 'build' / 'resolve_dates.py')
rd = importlib.util.module_from_spec(spec); spec.loader.exec_module(rd)
TAVILY = rd.TAVILY

def tavily(query, include_domains=None):
    b = {'api_key': TAVILY, 'query': query, 'max_results': 10,
         'search_depth': 'advanced', 'include_raw_content': True}
    if include_domains:
        b['include_domains'] = include_domains
    req = urllib.request.Request('https://api.tavily.com/search',
                                 data=json.dumps(b).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f'    tavily err: {e}'); return {}

# ── PRIMARY-SOURCE GATE (the future-leak fix) ──
# Aggregators serve LIVE pages = today's data → leak future figures into an old quarter
# (the MIXI ¥125 FY2027-dividend bug). Accept ONLY the actual 決算短信 PDF or a known
# TDnet/IR PDF host; reject every live HTML aggregator page.
# NOTE: aggregators = sites that *paraphrase* into HTML summary pages — never the source doc.
# Do NOT list ticker+date PDF MIRRORS here: f.irbank.net/pdf/… serves the ACTUAL TDnet 短信 PDF
# (small caps included). Blocking 'irbank' wholesale rejected the single best free backfill source
# — fixed: only irbank's HTML summary pages are non-primary (they fail the .pdf check anyway).
AGGREGATORS = ('minkabu', 'kabutan', 'kabuyoho', 'the-shashi', 'kessannote',
               'logmi', 'fisco', 'biggo', 'matsui', 'buffett-code', 'simplywall', 'ullet',
               'moomoo', 'investing.com', 'traders.co.jp', 'nikkei.com', 'reuters',
               'bloomberg', 'shikiho', 'kabuyoku', 'stockclip', 'quick.co.jp')
PRIMARY_HOSTS = ('irpocket', 'xj-storage', 'release.tdnet.info', 'eir-parts', 'swcms',
                 'edinet-fsa', 'disclosure.edinet', 'fse.or.jp', 'ssl4.eir-parts',
                 'equity.jiji.com/storage', 'finance-frontend', 'f.irbank.net')  # TDnet-PDF mirrors

def is_primary_source(url):
    u = (url or '').lower()
    if not u:
        return False
    if any(a in u for a in AGGREGATORS):
        return False
    if u.endswith('.pdf'):
        return True
    if any(h in u for h in PRIMARY_HOSTS):
        return True
    return False  # unknown HTML page → reject (could be a live/aggregated page)

def announce_date_from_doc(rc, period_end):
    """The 決算短信 cover prints its disclosure date at the top. Return the earliest full
    date on the cover that falls in the post-FYE window [pe+10, pe+95] — that's the
    announcement date (record/AGM dates fall outside or later). None if not found."""
    from datetime import datetime, timedelta
    pe = datetime.strptime(period_end, '%Y-%m-%d')
    lo, hi = pe + timedelta(days=10), pe + timedelta(days=95)
    best = None
    for y, m, d in re.findall(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', rc[:2500]):
        try:
            dt = datetime(int(y), int(m), int(d))
        except ValueError:
            continue
        if lo <= dt <= hi and (best is None or dt < best):
            best = dt
    return best.strftime('%Y-%m-%d') if best else None

def net_sales_digits(pkt):
    """Leading digits of net_sales (millions) for a loose match in the doc text."""
    n = pkt.get('numbers', {}) or {}
    ns = n.get('net_sales')
    if not ns:
        return None
    try:
        mil = int(float(ns) / 1_000_000)  # to millions (tanshin reports in 百万円)
        return str(mil)[:4]  # first 4 significant digits (commas vary)
    except Exception:
        return None

def focus(text, period_str, max_chars=7000):
    """Pull windows around the results/guidance/dividend/one-off sections."""
    terms = ['経営成績', '業績予想', '対前期', '対前年', '配当', '自己株式', '減損', '特別損', '売却益', '為替差',
             '後発事象', '自己株式の取得', '取得する', '消却', '株主還元', '増配', '特別配当']  # capital-return cues
    out, seen = [], set()
    for term in terms:
        i = text.find(term)
        if i >= 0:
            w = text[max(0, i - 200):i + 400]
            key = w[:60]
            if key not in seen:
                seen.add(key); out.append(w)
    blob = '\n…\n'.join(out)
    return blob[:max_chars] if blob else text[:max_chars]

def has_real_content(rc, pkt):
    """Reject index/chrome pages: must carry an actual results table, not just links."""
    nsd = net_sales_digits(pkt)
    if nsd and nsd in rc.replace(',', ''):
        return True  # the exact net_sales figure appears -> real report content
    return ('百万円' in rc or '百万円未満' in rc) and ('対前期' in rc or '増減率' in rc or '連結経営成績' in rc)

def is_fy1_doc(rc, yr, mo):
    """True if the doc's CURRENT/headline period is FY+1 (i.e. we grabbed next year's tanshin,
    which carries the target year only as a prior-year column). The FY+1 tanshin announces
    'YYYY+1年M月期 決算短信'."""
    fy1 = f'{int(yr)+1}年{mo}月期'
    # FY+1 appears next to 決算短信 / as the announced period -> it's the FY+1 report
    return (f'{fy1}　決算短信' in rc or f'{fy1} 決算短信' in rc or f'{fy1}決算短信' in rc
            or f'{fy1}（' in rc or f'{fy1}(' in rc)

def identity_ok(rc, x, pkt):
    """HARD GATE — the doc must actually be THIS company (avoid wrong-company web hits).
    Require the 4-digit ticker (often 'コード番号 XXXX') OR a distinctive name token to appear."""
    t = pkt['ticker']
    url = (x.get('url') or '')
    if t in rc or t in url:
        return True
    name = (pkt.get('name') or '') + ' ' + (pkt.get('name_jp') or '')
    import re as _re
    for tok in _re.findall(r'[A-Za-z]{4,}|[ぁ-んァ-ヶ一-龠]{3,}', name):
        if tok.lower() in {'false', 'true', 'none', 'inc', 'corporation', 'holdings',
                           'ltd', 'company', 'group', 'co', 'ホールディングス', '株式会社'}:
            continue
        if tok in rc:
            return True
    return False

def best_result(results, pkt):
    pe = pkt['period_end']; yr, mo = pe[:4], int(pe[5:7])
    period_str = f'{yr}年{mo}月期'
    nsd = net_sales_digits(pkt)
    restated = bool(pkt.get('numbers', {}).get('_pit_override'))
    ranked = []
    for x in results:
        rc = x.get('raw_content') or ''
        if len(rc) < 1500:
            continue
        if not is_primary_source(x.get('url')):    # HARD GATE — primary 決算短信 PDF only (no live aggregators)
            continue
        if not has_real_content(rc, pkt):          # HARD GATE — no index/chrome pages
            continue
        if not identity_ok(rc, x, pkt):            # HARD GATE — must be THIS company
            continue
        ns_match = bool(nsd and nsd in rc.replace(',', ''))
        # HARD GATE 2 — reject the FY+1 document (the date-attribution bug).
        # Allow only if the doc actually carries the TARGET year's net_sales as evidence
        # it's the right report (restated names can't digit-match, so keep them).
        if is_fy1_doc(rc, yr, mo) and not ns_match and not restated:
            continue
        score = 2
        if period_str in rc: score += 3
        if '業績予想' in rc: score += 2
        if ns_match: score += 5                     # current-year net_sales = strongest PIT proof
        url = (x.get('url') or '').lower()
        if url.endswith('.pdf') or 'irpocket' in url or '/pdf/' in url: score += 1
        if is_fy1_doc(rc, yr, mo): score -= 5       # still penalize FY+1-ish docs
        ranked.append((score, x, rc, period_str))
    ranked.sort(key=lambda t: -t[0])
    return ranked[0] if ranked else None

def main():
    targets = sys.argv[1:]
    force = '--force' in targets
    targets = [t for t in targets if not t.startswith('--')]
    files = [PKTDIR / f'{t}.json' for t in targets] if targets else sorted(PKTDIR.glob('*.json'))
    ok = fb = 0
    for f in files:
        pkt = json.loads(f.read_text(encoding='utf-8'))
        t = pkt['ticker']
        if pkt.get('tanshin_text') and not force:
            ok += 1; continue
        name = pkt.get('name_jp') or pkt.get('name') or t
        pe = pkt['period_end']; fy = f'{pe[:4]}年{int(pe[5:7])}月期'
        queries = [f'{name} {t} {fy} 決算短信 PDF', f'{name} {t} {fy} 決算短信',
                   f'{name} {fy} 通期 連結経営成績 業績予想']
        br = None
        for q in queries:
            d = tavily(q)
            br = best_result(d.get('results', []), pkt)
            if br:
                break
        if not br:  # recover coverage: TDnet/IR mirrors host EVERY company's 決算短信 PDF
            MIRRORS = ['equity.jiji.com', 'release.tdnet.info', 'contents.xj-storage.jp',
                       'pdf.irpocket.com', 'ssl4.eir-parts.net', 'data.swcms.net',
                       'finance-frontend-pc-dist.west.edge.storage-yahoo.jp']
            for q in [f'{name} {t} {fy} 決算短信', f'{t} {fy} 通期 決算短信']:
                d = tavily(q, include_domains=MIRRORS)
                br = best_result(d.get('results', []), pkt)
                if br:
                    break
        if br:
            score, x, rc, period_str = br
            pkt['tanshin_text'] = focus(rc, period_str)
            pkt['tanshin_source_url'] = x.get('url')
            adoc = announce_date_from_doc(rc, pe)   # authoritative 決算短信 date from the cover
            if adoc:
                pkt['announce_date_doc'] = adoc
            f.write_text(json.dumps(pkt, ensure_ascii=False, indent=2), encoding='utf-8')
            ok += 1
            flag = '' if not adoc else (f' date={adoc}' + ('' if adoc == pkt.get('announce_date') else f'≠{pkt.get("announce_date")}!'))
            print(f'  {t:5} {name[:18]:18} TANSHIN ok (score {score}){flag} {x.get("url","")[:42]}')
        else:
            # clear any junk so the runner falls back to 有報, not an index page
            if pkt.pop('tanshin_text', None) is not None:
                pkt.pop('tanshin_source_url', None)
                f.write_text(json.dumps(pkt, ensure_ascii=False, indent=2), encoding='utf-8')
            fb += 1
            print(f'  {t:5} {name[:18]:18} -> FALLBACK to 有報 (no valid tanshin)')
    total = ok + fb
    print(f'\ntanshin fetched={ok}  fallback={fb}  (success rate {ok}/{total} = {100*ok//max(total,1)}%)')

if __name__ == '__main__':
    main()
