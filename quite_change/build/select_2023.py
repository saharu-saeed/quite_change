import json, sys, concurrent.futures as cf
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).parent.parent; sys.path.insert(0,str(ROOT))
from research import tempest_fetch as tf
Q=ROOT/'data'/'quarterly'
df=pd.read_excel(ROOT/'data'/'_jpx_data_j.xls')
sec=[c for c in df.columns if '33業種区分' in str(c)][0]; mk=[c for c in df.columns if '市場' in str(c)][0]
it=df[df[sec].astype(str).str.contains('情報・通信')]
cand=[(str(r['コード']).strip(),str(r['銘柄名']).strip()) for _,r in it.iterrows()
      if len(str(r['コード']).strip())==4 and str(r['コード']).strip().isdigit() and 'PRO' not in str(r[mk]) and '外国' not in str(r[mk])]
def per(c):
    t,name=c
    try:
        d=tf.api(f'/companies/{t}/financials?from_fy=2021&to_fy=2023&limit=20')
        rows=[r for r in d.get('data',[]) if r.get('period_end')]
        pe=next((r['period_end'] for r in rows if r['period_end'][:4]=='2023'),None)
        return {'ticker':t,'name':name,'fy':'2023','period_end':pe} if pe else None
    except Exception: return None
out=[]
with cf.ThreadPoolExecutor(max_workers=12) as ex:
    for r in ex.map(per,cand):
        if r: out.append(r)
(Q/'_all_it_targets_2023.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'FY2023 targets: {len(out)} companies')
