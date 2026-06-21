# -*- coding: utf-8 -*-
"""Stage 2a — build the 50 test packets (ISOLATED in _pkts_2024_test50).
Per company: resolve 通期 doc-id (irbank/tdnet) → download (jiji-first, f.irbank fallback) →
pdfplumber + de-garble → cover/announce date → Tempest facts (numbers/prior-YoY) + 2-week prices
from the announce date → 短信 grounding text. Records the retrieval gates for the report.
Commits nothing to the main deliverable.
"""
from __future__ import annotations
import io, re, sys, json, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import pdfplumber
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
from research import tempest_fetch as tf
import backfill_irbank as bi

PKDIR = ROOT / 'data' / 'quarterly' / '_pkts_2024_test50'
PKDIR.mkdir(parents=True, exist_ok=True)
SEL = {r['ticker']: r for r in json.loads((ROOT / 'data' / 'quarterly' / '_test50_selection.json').read_text(encoding='utf-8'))}

def _get(url, hdr):
    return urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=45).read()

def download(docid):
    """jiji first (no referer); f.irbank fallback with polite backoff. Returns (bytes, mirror)."""
    try:
        return _get(f'https://equity.jiji.com/storage/tdnet/{docid}.pdf', {'User-Agent': 'Mozilla/5.0'}), 'jiji'
    except Exception:
        pass
    for i in range(3):
        try:
            return _get(f'https://f.irbank.net/pdf/{docid[4:12]}/{docid}.pdf',
                        {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://irbank.net/'}), 'f.irbank'
        except Exception as e:
            last = e; time.sleep(2 + 2 * i)
    raise last

def cover_date(t):
    for y, m, d in re.findall(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日', t[:800]):
        try: return datetime(int(y), int(m), int(d)).strftime('%Y-%m-%d')
        except ValueError: pass
    return None

def main():
    report = []
    for i, (t, s) in enumerate(SEL.items()):
        pe = s['period_end']; nm = s['name']
        rec = {'ticker': t, 'name': nm, 'period_end': pe, 'mcap': s['mcap'], 'rev_pct': s['rev_pct']}
        # RESUME: if already built, recompute gates from the saved packet (no re-download)
        pf = PKDIR / f'{t}.json'
        if pf.exists():
            pkt = json.loads(pf.read_text(encoding='utf-8'))
            txt = pkt.get('tanshin_text', ''); head = txt[:400]
            doctype_ok = '決算短信' in head and not any(q in head for q in ('第１四半期','第２四半期','第３四半期','四半期決算短信','中間決算短信'))
            rec.update(hit=bool(doctype_ok), identity=(t in txt[:900]), doctype_ok=doctype_ok,
                       cover_date=pkt.get('announce_date_doc'), in_window=True, mirror=pkt.get('tanshin_source_url','').split('(')[-1].rstrip(')'),
                       numbers_ok=pkt.get('tempest_numbers_ok'), pct_change=(pkt.get('prices') or {}).get('pct_change'), docid=pkt.get('tanshin_source_url',''))
            report.append(rec); print(f'{t} {nm[:14]:14} (resume)'); continue
        docid, title = bi.resolve(t, pe)
        rec['docid'] = docid or ''
        if not docid:
            rec.update(hit=False, reason='no-docid'); report.append(rec); print(f'{t} {nm[:14]:14} NO-DOCID'); continue
        try:
            data, mirror = download(docid)
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                txt = '\n'.join((p.extract_text() or '') for p in pdf.pages[:3])
        except Exception as e:
            rec.update(hit=False, reason=f'dl-fail {str(e)[:20]}'); report.append(rec); print(f'{t} {nm[:14]:14} DL-FAIL'); time.sleep(1); continue
        if '決算短信' not in txt[:300]:
            dd = re.sub(r'(.)\1{2,}', r'\1', txt)
            if '決算短信' in dd[:300]: txt = dd; rec['degarbled'] = True
        head = txt[:400]
        got = '決算短信' in head
        ident = (t in txt[:900])
        doctype_ok = got and not any(q in head for q in ('第１四半期','第２四半期','第３四半期','四半期決算短信','中間決算短信'))
        cd = cover_date(txt)
        in_win = bool(cd) and (datetime.strptime(pe,'%Y-%m-%d')+timedelta(days=5) <= datetime.strptime(cd,'%Y-%m-%d') <= datetime.strptime(pe,'%Y-%m-%d')+timedelta(days=130))
        announce = cd if (cd and in_win) else (datetime.strptime(pe,'%Y-%m-%d')+timedelta(days=45)).strftime('%Y-%m-%d')
        # Tempest facts + 2-week prices from the announce date
        pkt = tf.build_packet(t, announce, pe)
        pkt['name_jp'] = nm; pkt['name_official'] = pkt.get('name'); pkt['tier'] = 'test50'
        pkt['announce_date'] = announce; pkt['announce_date_doc'] = cd
        pkt['tanshin_text'] = txt[:8000]; pkt['tanshin_source_url'] = f'tdnet:{docid} ({mirror})'
        (PKDIR / f'{t}.json').write_text(json.dumps(pkt, ensure_ascii=False, indent=2), encoding='utf-8')
        rec.update(hit=bool(got and doctype_ok), identity=ident, doctype_ok=doctype_ok, cover_date=cd,
                   in_window=in_win, mirror=mirror, numbers_ok=pkt['tempest_numbers_ok'],
                   pct_change=(pkt.get('prices') or {}).get('pct_change'))
        report.append(rec)
        print(f'{t} {nm[:14]:14} {"HIT" if rec["hit"] else "miss":5} id={ident} 通期={doctype_ok} cd={cd} num_ok={pkt["tempest_numbers_ok"]} [{mirror}]')
        time.sleep(1)
    (ROOT / 'data' / 'quarterly' / '_test50_retrieval.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    hit = sum(1 for r in report if r.get('hit'))
    print(f'\n== Stage-2a: {hit}/{len(report)} HIT ({100*hit//len(report)}%) | packets -> _pkts_2024_test50/ | report -> _test50_retrieval.json ==')

if __name__ == '__main__':
    main()
