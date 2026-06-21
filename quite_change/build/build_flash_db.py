# -*- coding: utf-8 -*-
"""Clean flash-report retrieval into a fresh local DB (retrieval-only; no classification, no LLM).
Also the timing + structure benchmark for a future all-sector build.

Store:
  data/flash_reports/{ticker}/{fy}_tanshin.pdf   (raw, immutable)
  data/flash_reports/{ticker}/{fy}_tanshin.txt   (extracted text, separate)
  data/flash_reports/index.db                    (SQLite, one row per report)
  data/flash_reports/_runlog/run_*.log

Safety: resumable (skip doc-ids already saved), atomic writes (tmp+os.replace; index row committed
only after files on disk), per-company try/except, 訂正 dedup (keep both, latest authoritative),
run log. Universe: committed FY2024 (_pkts_2024) + FY2025 (_pkts) tickers.

Usage: python build/build_flash_db.py            # both years, resumable
"""
from __future__ import annotations
import io, os, re, sys, json, time, sqlite3, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import pdfplumber
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'build'))
import backfill_irbank as bi
from run_it_noweb import pick_name

FR = ROOT / 'data' / 'flash_reports'
DB = FR / 'index.db'
RUNLOG = FR / '_runlog'
SETS = [('2024', '_pkts_2024'), ('2025', '_pkts')]
DELAY = 0.7  # gentle rate-limit between companies (good citizen)

def db_init():
    FR.mkdir(parents=True, exist_ok=True); RUNLOG.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        ticker TEXT, company_name TEXT, fiscal_year_end TEXT, fy TEXT, cover_date TEXT,
        tdnet_doc_id TEXT UNIQUE, doc_type TEXT, source_mirror TEXT, file_path TEXT,
        gate_results TEXT, retrieval_timestamp TEXT, fetch_seconds REAL,
        delayed_flag INTEGER, is_correction INTEGER, authoritative INTEGER, status TEXT,
        PRIMARY KEY (ticker, fiscal_year_end, tdnet_doc_id))""")
    c.commit(); return c

def fetch(url, hdr):
    return urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=45).read()

def download(docid, ticker=None):
    # jiji first (transient-404 retry), then f.irbank via the REAL disclosure-date path from the
    # doc-page (f.irbank files PDFs under the disclosure date, not the doc-id date — the 403 path bug).
    for attempt in range(2):
        try:
            return fetch(f'https://equity.jiji.com/storage/tdnet/{docid}.pdf', {'User-Agent': 'Mozilla/5.0'}), 'jiji'
        except Exception:
            time.sleep(1.5)
    if os.environ.get('JIJI_ONLY'):  # f.irbank is throttling us — skip it this run (would 403 + deepen ban)
        return None, None
    firb = bi.firbank_pdf_url(ticker, docid) if ticker else f'https://f.irbank.net/pdf/{docid[4:12]}/{docid}.pdf'
    for i in range(3):
        try:
            return fetch(firb, {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://irbank.net/'}), 'f.irbank'
        except Exception:
            time.sleep(2 + 2 * i)
    return None, None

def atomic_write(path, data, mode='wb'):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, mode, encoding=(None if 'b' in mode else 'utf-8')) as f:
        f.write(data)
    os.replace(tmp, path)  # atomic on win/posix

def cover_date(t):
    for y, m, d in re.findall(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日', t[:800]):
        try: return datetime(int(y), int(m), int(d)).strftime('%Y-%m-%d')
        except ValueError: pass
    return None

def extract_text(data):
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        txt = '\n'.join((p.extract_text() or '') for p in pdf.pages[:3])
    if '決算短信' not in txt[:300]:
        dd = re.sub(r'(.)\1{2,}', r'\1', txt)
        if '決算短信' in dd[:300]:
            return dd, True
    return txt, False

def already_done(c, docid):
    r = c.execute("SELECT status FROM reports WHERE tdnet_doc_id=? AND status='ok'", (docid,)).fetchone()
    return r is not None

_Z = str.maketrans('０１２３４５６７８９', '0123456789')

def is_real_report(txt):
    """A genuine 短信 carries a results table; a 訂正 / XBRL-data *notice* does not."""
    return ('決算短信' in txt[:400] and '百万円' in txt and len(txt) > 1200
            and ('売上' in txt or '経営成績' in txt or '営業利益' in txt))

def already_good(c, ticker, fy):
    """Fast skip (no network): a real report is already stored as authoritative-ok."""
    r = c.execute("SELECT file_path FROM reports WHERE ticker=? AND fy=? AND authoritative=1 AND status='ok'", (ticker, fy)).fetchone()
    if not r or not r[0]:
        return False
    try:
        return is_real_report((ROOT / r[0]).with_suffix('.txt').read_text(encoding='utf-8'))
    except Exception:
        return False

def process(c, ticker, fy, period_end, name):
    """Returns (status, fetch_seconds, n_rows_written). Authoritative = latest REAL report —
    a 訂正/XBRL *notice* (no results table) never wins, even if it's the newest doc-id."""
    t0 = time.monotonic()
    if already_good(c, ticker, fy):                       # already have a real report -> skip
        return 'ok', time.monotonic() - t0, 1
    entries = bi.resolve_all(ticker, period_end)
    if not entries:
        return 'delayed_or_unlisted', time.monotonic() - t0, 0
    entries_sorted = sorted(entries, key=lambda e: e[1])  # ascending by doc-id (date)
    cdir = FR / ticker; cdir.mkdir(parents=True, exist_ok=True)
    fetched = []  # (docid, title, data|None, txt, is_real, mirror)
    for title, docid in entries_sorted:
        data, mirror = download(docid, ticker)
        if not data:
            fetched.append((docid, title, None, '', False, None)); continue
        try:
            txt, _ = extract_text(data)
        except Exception:
            fetched.append((docid, title, data, '', False, mirror)); continue
        fetched.append((docid, title, data, txt, is_real_report(txt), mirror))
    reals = [f for f in fetched if f[4]]
    auth_docid = reals[-1][0] if reals else entries_sorted[-1][1]   # latest REAL; else latest overall
    written = 0; final_status = 'miss'
    for docid, title, data, txt, real, mirror in fetched:
        is_corr = int('訂正' in title); is_auth = int(docid == auth_docid)
        if data is None:
            c.execute("INSERT OR REPLACE INTO reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (ticker, name, period_end, fy, None, docid, '通期', None, None,
                       json.dumps({'download': 'failed'}), datetime.now().isoformat(), None, 0,
                       is_corr, is_auth, 'miss:download_404')); c.commit()
            if is_auth: final_status = 'miss:download_404'
            continue
        suffix = f'{fy}_tanshin' + ('' if is_auth else '_corr')
        pdf_path = cdir / f'{suffix}.pdf'; txt_path = cdir / f'{suffix}.txt'
        if not txt:
            atomic_write(pdf_path, data)
            c.execute("INSERT OR REPLACE INTO reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (ticker, name, period_end, fy, None, docid, '通期', mirror, str(pdf_path.relative_to(ROOT)),
                       json.dumps({'parse': 'no text'}), datetime.now().isoformat(), None, 0, is_corr, is_auth, 'miss:parse')); c.commit()
            if is_auth: final_status = 'miss:parse'
            continue
        head = txt[:400]; got = '決算短信' in head; raw = len(txt)
        identity = ticker in txt[:1500].translate(_Z)
        quarterly = any(q in head for q in ('第１四半期', '第２四半期', '第３四半期', '四半期決算短信', '中間決算短信'))
        cd = cover_date(txt)
        gates = {'identity': identity, 'doctype_tsuki': bool(got and not quarterly), 'cover_date': bool(cd), 'readable': raw > 1000, 'real_report': real}
        if not got:        st = 'miss:image_only' if raw < 300 else 'miss:garbled'
        elif quarterly:    st = 'miss:quarterly'
        elif not real:     st = 'miss:notice'            # 訂正/XBRL notice — no results table
        elif not identity: st = 'miss:identity'
        else:              st = 'ok'
        atomic_write(pdf_path, data); atomic_write(txt_path, txt, mode='w')
        c.execute("INSERT OR REPLACE INTO reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (ticker, name, period_end, fy, cd, docid, '通期', mirror, str(pdf_path.relative_to(ROOT)),
                   json.dumps(gates), datetime.now().isoformat(), None, 0, is_corr, is_auth, st)); c.commit()
        written += 1
        if is_auth: final_status = st
    dt = time.monotonic() - t0
    c.execute("UPDATE reports SET fetch_seconds=? WHERE ticker=? AND fiscal_year_end=? AND authoritative=1", (round(dt, 2), ticker, period_end))
    c.commit()
    return final_status, dt, written

def main():
    c = db_init()
    runlog = RUNLOG / f'run_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    log = runlog.open('w', encoding='utf-8')
    def L(m):
        print(m); log.write(m + '\n'); log.flush()
    universe = []
    if len(sys.argv) > 1 and sys.argv[1] == 'all-it':
        tfile = sys.argv[2] if len(sys.argv) > 2 else '_all_it_targets.json'
        for x in json.loads((ROOT / 'data' / 'quarterly' / tfile).read_text(encoding='utf-8')):
            universe.append((x['ticker'], x['fy'], x['period_end'], x['name']))
        scope = f'ALL-IT ({tfile})'
    else:
        for fy, pdir in SETS:
            for f in sorted((ROOT / 'data' / 'quarterly' / pdir).glob('*.json')):
                p = json.loads(f.read_text(encoding='utf-8'))
                universe.append((p['ticker'], fy, p['period_end'], pick_name(p)))
        scope = 'committed IT set (95+99)'
    L(f'START {datetime.now().isoformat()} | universe {len(universe)} reports ({scope})')
    wall0 = time.monotonic()
    ok = 0; fails = []; times = []
    for i, (t, fy, pe, name) in enumerate(universe):
        try:
            st, dt, n = process(c, t, fy, pe, name)
            times.append(dt)
            if st == 'ok': ok += 1
            else: fails.append((t, fy, st))
            L(f'[{i+1}/{len(universe)}] {t} FY{fy} {name[:14]:14} {st:22} {dt:5.1f}s rows={n}')
        except Exception as e:
            fails.append((t, fy, f'EXC:{str(e)[:40]}'))
            L(f'[{i+1}/{len(universe)}] {t} FY{fy} ERROR {str(e)[:60]}')
        time.sleep(DELAY)
    # RETRY PASS — re-attempt transient misses (download_404 / exceptions) once; image_only/garbled/
    # delayed won't change, so skip them. This recovers the 4689-class flakiness at scale.
    umap = {(t, fy): (pe, name) for t, fy, pe, name in universe}
    retryable = [(t, fy) for (t, fy, st) in fails if ('download_404' in st or st.startswith('EXC'))]
    if retryable:
        L(f'\n-- retry pass over {len(retryable)} transient misses --')
        time.sleep(5)
        for t, fy in retryable:
            pe, name = umap[(t, fy)]
            try:
                st, dt, n = process(c, t, fy, pe, name)
                if st == 'ok':
                    ok += 1; fails = [f for f in fails if not (f[0] == t and f[1] == fy)]
                    L(f'  RECOVERED {t} FY{fy}')
            except Exception:
                pass
            time.sleep(DELAY)
    wall = time.monotonic() - wall0
    L(f'\nEND {datetime.now().isoformat()} | ok {ok}/{len(universe)} | wall {wall/60:.1f} min')
    if times:
        ts = sorted(times)
        L(f'fetch_seconds: avg {sum(ts)/len(ts):.1f} | median {ts[len(ts)//2]:.1f} | min {ts[0]:.1f} | max {ts[-1]:.1f}')
        per = wall / len(universe)
        L(f'wall/company (incl {DELAY}s delay): {per:.1f}s')
        est = per * 24000 / 3600
        L(f'EXTRAPOLATION ~4000 companies x 6 yrs = 24,000 reports: ~{est:.0f}h ({est/24:.1f} days) single-threaded; '
          f'~{est/8:.0f}h at 8x parallel')
    if fails:
        L(f'\nFAILURES/DELAYED ({len(fails)}):')
        for t, fy, st in fails: L(f'  {t} FY{fy}: {st}')
    # MISSES-TO-REVIEW export — tag each failure with a suggested next action for later triage
    ACTION = {
        'delayed_or_unlisted': 'no 通期 短信 on irbank/tdnet for the period — disclosure delayed OR odd-listing (NTT/broadcaster type); check manually',
        'miss:download_404': 'doc-id resolved but mirrors 404 — transient; re-run later / try alternate mirror',
        'miss:image_only': 'image-only PDF (no text layer) — needs OCR',
        'miss:garbled': 'font-garbled, de-garble failed — needs OCR/manual',
        'miss:parse': 'PDF parse error — re-fetch / inspect file',
    }
    miss_rows = []
    for t, fy, st in fails:
        pe, name = umap.get((t, fy), (None, None))
        key = st if st in ACTION else ('miss:exception' if st.startswith('EXC') else st)
        miss_rows.append({'ticker': t, 'company': name, 'fy': fy, 'period_end': pe,
                          'status': st, 'suggested_action': ACTION.get(key, 'investigate: ' + st)})
    (FR / '_misses_review.json').write_text(json.dumps(miss_rows, ensure_ascii=False, indent=2), encoding='utf-8')
    L(f'\n-> misses tagged for review: data/flash_reports/_misses_review.json ({len(miss_rows)} entries)')
    log.close()

if __name__ == '__main__':
    main()
