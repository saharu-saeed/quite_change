# -*- coding: utf-8 -*-
"""Authenticity proof: the independent feed (Tempest) net_sales must appear VERBATIM inside the
retrieved mirror PDF — two unrelated sources agreeing => the document is the genuine official filing.
Auto-picks 5 'ok' reports spanning the cap range (2 largest + 1 median + 2 smallest net_sales).
Outputs a verification table. Flags any mismatch loudly.
"""
from __future__ import annotations
import io, json, sqlite3, sys
from pathlib import Path
import pdfplumber
ROOT = Path(__file__).parent.parent
FR = ROOT / 'data' / 'flash_reports'
PKT = {'2024': ROOT / 'data' / 'quarterly' / '_pkts_2024', '2025': ROOT / 'data' / 'quarterly' / '_pkts'}

def net_sales(ticker, fy):
    p = json.loads((PKT[fy] / f'{ticker}.json').read_text(encoding='utf-8'))
    ns = (p.get('numbers', {}) or {}).get('net_sales')
    return int(float(ns)) if ns else None

def find_verbatim(pdf_path, value_yen):
    """Search each page for the net_sales figure in 百万円 (comma + plain forms). Return page no or None."""
    mil = int(value_yen / 1_000_000)
    forms = [f'{mil:,}', str(mil)]
    with pdfplumber.open(ROOT / pdf_path) as pdf:
        for i, pg in enumerate(pdf.pages[:4], 1):
            txt = (pg.extract_text() or '').replace(' ', '')
            for fm in forms:
                if fm.replace(',', '') in txt.replace(',', ''):
                    return i, fm
    return None, None

def main():
    c = sqlite3.connect(FR / 'index.db')
    rows = c.execute("SELECT ticker, company_name, fiscal_year_end, fy, cover_date, tdnet_doc_id, file_path "
                     "FROM reports WHERE status='ok' AND authoritative=1").fetchall()
    enr = []
    for t, nm, pe, fy, cd, docid, fp in rows:
        ns = net_sales(t, fy)
        if ns: enr.append((ns, t, nm, pe, fy, cd, docid, fp))
    enr.sort()
    pick = [enr[0], enr[1], enr[len(enr)//2], enr[-2], enr[-1]] if len(enr) >= 5 else enr  # 2 smallest + median + 2 largest
    print(f'{"ticker":7}{"company":16}{"cover_date":12}{"feed net_sales(百万)":>20}  found  page  verdict')
    rep = []
    for ns, t, nm, pe, fy, cd, docid, fp in pick:
        page, fm = find_verbatim(fp, ns)
        found = page is not None
        verdict = 'GENUINE' if found else '*** MISMATCH ***'
        print(f'{t:7}{(nm or "")[:14]:16}{str(cd):12}{ns//1_000_000:>20,}  {"Y" if found else "N":5} {str(page):5} {verdict}  [{docid}]')
        rep.append({'ticker': t, 'company': nm, 'fy': fy, 'cover_date': cd, 'feed_net_sales_mil': ns // 1_000_000,
                    'found_verbatim': found, 'page': page, 'tdnet_doc_id': docid, 'verdict': verdict})
    (FR / '_authenticity_sample.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8')
    bad = [r for r in rep if not r['found_verbatim']]
    print(f'\n{len(rep)-len(bad)}/{len(rep)} GENUINE (feed figure found verbatim in mirror PDF).' +
          (f'  ⚠️ {len(bad)} MISMATCH: {[r["ticker"] for r in bad]}' if bad else '  No mismatches.'))

if __name__ == '__main__':
    main()
