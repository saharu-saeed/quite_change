import os, sys, json, time, sqlite3
sys.path.insert(0, 'build')
os.environ.pop('JIJI_ONLY', None)   # use f.irbank (this is the f.irbank recovery)
import build_flash_db as bf
c = sqlite3.connect(bf.FR / 'index.db', timeout=60)   # busy-wait, safe alongside the FY2022 run
TG = json.load(open('data/quarterly/_all_it_targets.json', encoding='utf-8')) \
   + json.load(open('data/quarterly/_all_it_targets_2023.json', encoding='utf-8')) \
   + json.load(open('data/quarterly/_all_it_targets_2022.json', encoding='utf-8'))
todo = [(x['ticker'], x['fy'], x['period_end'], x['name']) for x in TG
        if not bf.already_good(c, x['ticker'], x['fy'])]
print(f'f.irbank recovery (FIXED disclosure-date path): {len(todo)} not-yet-ok across 2022-2025')
rec = 0
for t, fy, pe, name in todo:
    try:
        st, dt, n = bf.process(c, t, fy, pe, name)
        if st == 'ok':
            rec += 1; print(f'  RECOVERED {t} FY{fy}')
    except Exception as e:
        print(f'  {t} FY{fy} err {str(e)[:30]}')
    time.sleep(1.5)
print(f'\nrecovered {rec}/{len(todo)} via f.irbank')
for fy in ['2022','2023','2024','2025']:
    ok = c.execute("SELECT COUNT(*) FROM reports WHERE fy=? AND authoritative=1 AND status='ok'", (fy,)).fetchone()[0]
    print(f'  FY{fy} ok now: {ok}')
