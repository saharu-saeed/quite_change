# -*- coding: utf-8 -*-
"""Build MD&A packets for the committed 95-company cohort, for a BACK-YEAR (2023/2022).
Numbers/prices/有報 from Tempest; 短信 MD&A text + announce date from the flash_reports store
we already retrieved. MD&A-prose-first (same shape as _pkts_2024_mdna), names reused from the
2024 cohort packet so the four years line up 1:1.

Usage: python build/build_cohort_packets.py 2023
"""
from __future__ import annotations
import sys, re, json, sqlite3, time
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from research.tempest_fetch import build_packet

def mdna_prose(full):
    f = re.sub(r'…{2,}[^\n]*', '', full)
    for h in ['経営成績に関する分析', '当期の経営成績の概況', '経営成績の概況', '経営成績等の概況', '当期の経営成績', '財政状態、経営成績']:
        for m in re.finditer(h, f):
            seg = f[m.start():m.start() + 4500]
            if seg.count('。') >= 3:
                return seg
    return ''

def main():
    fy = sys.argv[1]
    DST = ROOT / 'data' / 'quarterly' / f'_pkts_{fy}_mdna'; DST.mkdir(parents=True, exist_ok=True)
    base_dir = ROOT / 'data' / 'quarterly' / '_pkts_2024_mdna'
    base = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in base_dir.glob('*.json')}
    cohort = list(json.load(open(ROOT / 'data' / 'quarterly' / 'it_q4_2024.json', encoding='utf-8'))['companies'].keys())
    c = sqlite3.connect(ROOT / 'data' / 'flash_reports' / 'index.db')
    rows = c.execute(
        f"SELECT ticker,cover_date,fiscal_year_end,file_path FROM reports "
        f"WHERE fy=? AND status='ok' AND authoritative=1 AND ticker IN ({','.join('?' * len(cohort))})",
        [fy] + cohort).fetchall()
    built = skip = err = 0
    for t, cover, pe, fp in rows:
        dst = DST / f'{t}.json'
        if dst.exists(): skip += 1; continue
        try:
            pkt = build_packet(t, cover, pe)
        except Exception as e:
            err += 1; print(f'  {t}: build_packet ERR {str(e)[:40]}'); continue
        txt = ''
        try: txt = Path(fp).with_suffix('.txt').read_text(encoding='utf-8')
        except Exception: pass
        prose = mdna_prose(txt) if txt else ''
        if prose:
            pkt['tanshin_text'] = (prose + '\n\n【サマリー】\n' + txt[:1800])[:8500]
        elif txt:
            pkt['tanshin_text'] = txt[:8500]
        pkt['tanshin_source_url'] = f'flash_reports/{t}/{fy}_tanshin.pdf'
        b = base.get(t, {})
        for k in ['name_jp', 'name_official', 'name_official_jp', 'tier']:
            if b.get(k) and not pkt.get(k): pkt[k] = b[k]
        if not pkt.get('name'): pkt['name'] = b.get('name')
        dst.write_text(json.dumps(pkt, ensure_ascii=False, indent=2), encoding='utf-8')
        built += 1
        if built % 20 == 0: print(f'  ...{built} built')
        time.sleep(0.2)
    print(f'FY{fy}: built {built}, skipped {skip}, err {err} -> {DST.name}')

if __name__ == '__main__':
    main()
