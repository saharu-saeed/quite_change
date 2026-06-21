"""Combined '2025 Q4' view builder (non-IT sectors) — UNIFIED-VIEW style.

Reads data/quarterly/q4_2025_nonIT.json and emits deliverables/quarterly/VIEW_2025Q4.html.

Structure mirrors UNIFIED_VIEW.html:
  4 category sections (R+×S-, R+×S+, R-×S+, R-×S-)
    -> within each, companies are grouped into REASON BUCKETS (collapsible, title + note)
       -> each company card shows the full 4-section lighter-prompt narrative
          (bold headers, EN/日本語 toggle), tags (rev/op/net %, stock YoY, biz class) + sources.

Point-in-time: every card uses the FY2025 report + earlier years only (never FY2026).
Usage:  python build/build_q4_2025_view.py
"""
from __future__ import annotations
import sys, io, json, html, re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = Path(__file__).parent
ROOT = HERE.parent
OUT = ROOT / 'deliverables' / 'quarterly' / 'VIEW_2025Q4.html'
DATA_PATH = ROOT / 'data' / 'quarterly' / 'q4_2025_nonIT.json'

CATEGORIES = [
    ('R+xS-', 'focus', 'R+ × S-', '売上↑ / 株価↓', 'Revenue up, stock down',   '本命 / Focus — overlooked'),
    ('R+xS+', 'up',    'R+ × S+', '売上↑ / 株価↑', 'Revenue up, stock up',     'Working as expected'),
    ('R-xS+', 'rdown', 'R- × S+', '売上↓ / 株価↑', 'Revenue down, stock up',   'Stock up despite shrinking sales'),
    ('R-xS-', 'down',  'R- × S-', '売上↓ / 株価↓', 'Revenue down, stock down', 'Both falling'),
]
CAT_JP = {'R+xS-': '売上↑ / 株価↓ — 見落とされ', 'R+xS+': '売上↑ / 株価↑ — 想定通り',
          'R-xS+': '売上↓ / 株価↑ — 減収でも株高', 'R-xS-': '売上↓ / 株価↓ — 両方下落'}
SECTOR_JP = {'Marine': '海運', 'Mining': '鉱業', 'AirTransport': '空運', 'Petroleum': '石油・石炭',
             'AgriFishery': '水産・農林', 'LandTransport': '陸運', 'IT': '情報・通信'}

_BOLD = re.compile(r'\*\*(.+?)\*\*')


def esc(s):
    return html.escape(str(s)) if s is not None else ''


def esc_bold(s):
    """HTML-escape, then turn **x** into <b>x</b> and newlines into <br><br>."""
    return _BOLD.sub(r'<b>\1</b>', esc(s)).replace('\n\n', '<br><br>').replace('\n', '<br>')


def arrow(d):
    return '↑' if d == 'up' else ('↓' if d == 'down' else '→')


def render_card(c):
    rev_e, op_e, net_e = arrow(c['revenue_dir']), arrow(c['op_dir']), arrow(c['net_dir'])
    stk_cls = 'pos' if c['stock_dir'] == 'up' else 'neg'
    sec = c['sector']
    src = ' · '.join(c.get('sources', []))
    gr_en = esc_bold(c['en_summary'])
    gr_jp = esc_bold(c['jp_summary'])
    return f'''
    <div class="company-row collapsed" data-sector="{esc(sec)}" onclick="toggleCompany(this, event)">
      <div class="company-head">
        <span class="ticker">{esc(c['ticker'])}</span>
        <span class="company-name">{esc(c['name'])}</span>
        <span class="company-meta">
          <span class="badge sector" data-en="{esc(sec)}" data-jp="{esc(SECTOR_JP.get(sec, sec))}">{esc(sec)}</span>
          <span class="badge fy">{esc(c.get('fy_label',''))}</span>
        </span>
        <span class="expand-icon">▸</span>
      </div>
      <div class="report-meta" data-en="FY2025 report announced {esc(c.get('announce_date',''))} · stock measured to ~2 weeks after"
           data-jp="FY2025決算 発表日 {esc(c.get('announce_date',''))} · 株価は発表から約2週間後で測定">FY2025 report announced {esc(c.get('announce_date',''))} · stock measured to ~2 weeks after</div>
      <div class="company-data">
        <span class="data-item"><span class="data-label" data-en="Revenue (FY):" data-jp="売上(通期):">Revenue (FY):</span> {rev_e} {esc(c.get('rev_pct',''))}</span>
        <span class="data-item"><span class="data-label" data-en="Op profit:" data-jp="営業利益:">Op profit:</span> {op_e} {esc(c.get('op_pct',''))}</span>
        <span class="data-item"><span class="data-label" data-en="Net profit:" data-jp="純利益:">Net profit:</span> {net_e} {esc(c.get('net_pct',''))}</span>
        <span class="data-item"><span class="data-label" data-en="Stock 2wk after report:" data-jp="株価(決算後2週間):">Stock 2wk after report:</span> <b class="{stk_cls}">{esc(c.get('stock_2w_estimate',''))}</b></span>
      </div>
      <div class="biz-tag" data-en="Type: {esc(c.get('biz_classification',''))}" data-jp="分類: {esc(c.get('biz_classification',''))}">分類: {esc(c.get('biz_classification',''))}</div>
      <div class="company-body">
        <div class="genuine-research">
          <div class="genuine-header">
            <span class="genuine-label" data-en="Research (lighter-prompt web search · point-in-time)" data-jp="リサーチ(ライタープロンプトWeb検索 · ポイントインタイム)">Research (lighter-prompt web search · point-in-time)</span>
            <span class="genuine-source" title="{esc(src)}">📚 {esc(src)}</span>
          </div>
          <div class="genuine-body" data-genuine-en="{gr_en}" data-genuine-jp="{gr_jp}">{gr_en}</div>
        </div>
      </div>
    </div>'''


def render_bucket(bucket_key, label, cards):
    note_en = esc(label.get('note', '')).replace('\n', '<br><br>')
    note_jp = esc(label.get('note_jp', '')).replace('\n', '<br><br>')
    return f'''
    <details class="reason-bucket" open>
      <summary>
        <span class="bucket-toggle-icon">▸</span>
        <span class="bucket-title" data-title-en="{esc(label.get('title',bucket_key))}" data-title-jp="{esc(label.get('title_jp',bucket_key))}">{esc(label.get('title',bucket_key))}</span>
        <span class="bucket-count">{len(cards)} <span data-en="names" data-jp="社">names</span></span>
      </summary>
      <div class="bucket-note" data-note-en="{note_en}" data-note-jp="{note_jp}">{esc(label.get('note',''))}</div>
      <div class="bucket-cards">{''.join(cards)}</div>
    </details>'''


def render_section(cat_key, css_cls, en_title, jp_sub, en_sub, badge, by_bucket, buckets_meta):
    n = sum(len(v) for v in by_bucket.values())
    if not by_bucket:
        inner = ('<p class="empty-note" data-en="No companies in this category." '
                 'data-jp="該当企業はありません。">No companies in this category.</p>')
    else:
        ordered = sorted(by_bucket.keys(), key=lambda k: buckets_meta.get(k, {}).get('order', 99))
        inner = ''.join(render_bucket(bk, buckets_meta.get(bk, {'title': bk, 'title_jp': bk}), by_bucket[bk]) for bk in ordered)
    return f'''
    <details class="cat-section cat-{css_cls}" {'open' if n else ''}>
      <summary>
        <span class="cat-toggle">▸</span>
        <span class="cat-title">{esc(en_title)}</span>
        <span class="cat-sub" data-en="{esc(en_sub)}" data-jp="{esc(jp_sub)}">{esc(en_sub)}</span>
        <span class="cat-badge" data-en="{esc(badge)}" data-jp="{esc(CAT_JP[cat_key])}">{esc(badge)}</span>
        <span class="cat-count">{n}</span>
      </summary>
      <div class="cat-cards">{inner}</div>
    </details>'''


STYLES = '''
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Helvetica, Arial, "Hiragino Sans", "Meiryo", sans-serif; margin: 0; color: #1a1a1a; background: #f7f7f5; line-height: 1.55; }
.container { max-width: 1080px; margin: 0 auto; padding: 24px; }
header.page-header { background: #fff; border-bottom: 1px solid #e0e0e0; padding: 22px 24px; position: relative; }
.page-header h1 { margin: 0 0 4px; font-size: 20px; font-weight: 700; }
.page-header .subtitle { color: #555; font-size: 13px; margin: 4px 0 0; }
.page-header .pit-note { color: #2f5377; font-size: 12px; margin: 8px 0 0; background:#eef3f8; border-left:3px solid #2f5377; padding:6px 10px; border-radius:3px; display:inline-block; }
.lang-toggle { position: absolute; top: 22px; right: 22px; display: flex; gap: 4px; }
.lang-btn { padding: 4px 10px; font-size: 12px; border: 1px solid #ccc; background: #fff; cursor: pointer; border-radius: 3px; }
.lang-btn.active { background: #1f7a4a; color: #fff; border-color: #1f7a4a; }

.filter-row { background:#fff; border:1px solid #e0e0e0; border-radius:8px; padding:12px 16px; margin:18px 0; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.filter-row label { font-size:13px; font-weight:600; color:#333; }
.filter-row select { font-size:13px; padding:6px 12px; border:1px solid #ccc; border-radius:4px; background:#fff; }

.legend { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:14px 0 6px; }
.legend .lg { font-size:11.5px; padding:8px 10px; border-radius:6px; border:1px solid #e0e0e0; }
.legend .lg b { display:block; font-size:13px; margin-bottom:2px; }
.lg.cat-focus { background:#f0f8f3; border-color:#cfe6d8; } .lg.cat-focus b { color:#1f7a4a; }
.lg.cat-up    { background:#eef6fb; border-color:#d2e4ef; } .lg.cat-up b { color:#2f5377; }
.lg.cat-rdown { background:#fdf6ec; border-color:#ecdcbf; } .lg.cat-rdown b { color:#9a6b1f; }
.lg.cat-down  { background:#fdf2f2; border-color:#ecd5d5; } .lg.cat-down b { color:#a83b3b; }
@media (max-width:720px){ .legend { grid-template-columns:repeat(2,1fr); } }

.cat-section { background:#fff; border:1px solid #e0e0e0; border-radius:8px; margin:14px 0; padding:4px 16px 8px; border-left:5px solid #ccc; }
.cat-section.cat-focus { border-left-color:#1f7a4a; }
.cat-section.cat-up { border-left-color:#2f5377; }
.cat-section.cat-rdown { border-left-color:#d4a017; }
.cat-section.cat-down { border-left-color:#a83b3b; }
.cat-section > summary { cursor:pointer; list-style:none; display:flex; align-items:center; gap:10px; padding:12px 0; font-weight:700; user-select:none; }
.cat-section > summary::-webkit-details-marker { display:none; }
.cat-toggle { font-size:12px; color:#888; transition:transform .15s; min-width:12px; }
.cat-section[open] > summary .cat-toggle { transform:rotate(90deg); }
.cat-title { font-size:16px; }
.cat-section.cat-focus .cat-title { color:#1f7a4a; }
.cat-section.cat-up .cat-title { color:#2f5377; }
.cat-section.cat-rdown .cat-title { color:#9a6b1f; }
.cat-section.cat-down .cat-title { color:#a83b3b; }
.cat-sub { font-size:12.5px; color:#777; font-weight:600; }
.cat-badge { font-size:11px; color:#666; background:#f0f0f0; border-radius:3px; padding:1px 8px; font-weight:600; }
.cat-count { margin-left:auto; background:#f0f0f0; border-radius:9px; padding:1px 10px; font-size:12px; color:#555; }
.cat-cards { padding:4px 0 8px; }

/* Reason buckets (same look as unified view) */
.reason-bucket { background:#fbfbf9; border:1px solid #e6e6e1; border-radius:6px; padding:10px 14px; margin:10px 0; }
.reason-bucket > summary { cursor:pointer; font-size:14.5px; font-weight:700; color:#1a1a1a; display:flex; align-items:center; gap:10px; padding:6px 0; list-style:none; user-select:none; }
.reason-bucket > summary::-webkit-details-marker { display:none; }
.bucket-toggle-icon { font-size:12px; color:#1f7a4a; transition:transform .15s; min-width:14px; }
.reason-bucket[open] > summary .bucket-toggle-icon { transform:rotate(90deg); }
.bucket-title { color:#1f7a4a; flex:1; }
.bucket-count { background:#eee; border-radius:9px; padding:1px 8px; font-size:11px; color:#555; }
.bucket-note { font-size:12.5px; color:#555; padding:10px 8px 12px; line-height:1.65; background:#fafaf5; border-left:3px solid #d4a017; margin:8px 0 12px; border-radius:3px; }
.bucket-cards { padding-top:2px; }

.company-row { background:#fff; border:1px solid #e0e0e0; border-radius:6px; padding:14px 16px; margin:10px 0; transition:background .15s,border-color .15s; cursor:pointer; }
.company-row:hover { background:#f0f8f3; border-color:#1f7a4a; }
.company-row:not(.collapsed) { cursor:default; }
.company-row:not(.collapsed) .company-body { cursor:text; }
.company-head { display:flex; align-items:baseline; gap:12px; user-select:none; }
.expand-icon { font-size:12px; color:#999; transition:transform .15s; margin-left:auto; }
.company-row:not(.collapsed) .expand-icon { transform:rotate(90deg); }
.ticker { font-family:monospace; font-size:13px; color:#777; }
.company-name { font-size:16px; font-weight:700; }
.company-meta { display:inline-flex; gap:6px; }
.badge { font-size:10.5px; padding:1px 6px; border-radius:3px; background:#ececec; color:#555; font-weight:600; }
.badge.sector { background:#e6f0f8; color:#2f5377; }
.badge.fy { background:#eef0f4; color:#54618a; }
.company-data { display:flex; gap:16px; flex-wrap:wrap; font-size:12.5px; color:#555; margin:8px 0 2px; }
.data-label { color:#888; font-weight:600; margin-right:4px; }
.company-data b.pos { color:#1f7a4a; } .company-data b.neg { color:#a83b3b; }
.report-meta { font-size:11px; color:#8a8a8a; margin:6px 0 2px; }
.biz-tag { font-size:11.5px; color:#777; margin:6px 0 2px; font-style:italic; }
.company-row.collapsed .company-body { display:none; }
.company-body { padding-top:10px; }
.genuine-research { background:#f0f8f3; border-left:4px solid #1f7a4a; padding:12px 14px; border-radius:4px; }
.genuine-header { display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap; margin-bottom:8px; font-size:11.5px; color:#555; }
.genuine-label { font-weight:700; color:#1f7a4a; }
.genuine-source { font-size:10px; color:#999; }
.genuine-body { font-size:13px; line-height:1.75; color:#1a1a1a; }
.genuine-body b { color:#1f7a4a; }
.empty-note { padding:14px; color:#999; font-style:italic; font-size:13px; }
.hidden-by-filter { display:none !important; }
footer { text-align:center; color:#aaa; font-size:11px; padding:20px; }
'''

JS = '''
let LANG='en';
function applyI18n(){
  document.querySelectorAll('[data-en]').forEach(el=>{
    const v=el.getAttribute('data-'+LANG); if(v!==null) el.textContent=v;
  });
  document.querySelectorAll('.bucket-title[data-title-en]').forEach(el=>{
    const v=el.getAttribute('data-title-'+LANG); if(v!==null) el.textContent=v;
  });
  document.querySelectorAll('.bucket-note[data-note-en]').forEach(el=>{
    const v=el.getAttribute('data-note-'+LANG); if(v!==null) el.innerHTML=v;
  });
  document.querySelectorAll('.genuine-body[data-genuine-en]').forEach(el=>{
    const v=el.getAttribute('data-genuine-'+LANG); if(v!==null) el.innerHTML=v;
  });
  document.querySelectorAll('select option[data-en]').forEach(opt=>{
    const v=opt.getAttribute('data-'+LANG); if(v!==null) opt.textContent=v;
  });
  document.documentElement.setAttribute('lang',LANG);
}
function setLang(lang){ LANG=lang; document.querySelectorAll('.lang-btn').forEach(b=>b.classList.toggle('active', b.dataset.lang===lang)); applyI18n(); }
function toggleCompany(row, ev){
  if(ev&&ev.target&&ev.target.closest('.company-body')) return;
  if(window.getSelection&&window.getSelection().toString().length>0) return;
  row.classList.toggle('collapsed');
}
function filterSector(sel){
  const v=sel.value;
  document.querySelectorAll('.company-row').forEach(r=>{ r.classList.toggle('hidden-by-filter', v!=='all'&&r.dataset.sector!==v); });
  document.querySelectorAll('.reason-bucket').forEach(b=>{
    const vis=b.querySelectorAll('.company-row:not(.hidden-by-filter)').length;
    b.style.display = vis? '' : 'none';
  });
  document.querySelectorAll('.cat-section').forEach(sec=>{
    const vis=sec.querySelectorAll('.company-row:not(.hidden-by-filter)').length;
    const c=sec.querySelector('.cat-count'); if(c) c.textContent=vis;
  });
}
document.addEventListener('DOMContentLoaded',()=>{ applyI18n(); });
'''


def main():
    with open(DATA_PATH, encoding='utf-8') as fp:
        data = json.load(fp)
    companies = data['companies']
    meta = data['_meta']
    buckets_meta = data.get('buckets', {})

    # category -> bucket -> [cards]
    grid = {c[0]: {} for c in CATEGORIES}
    for c in sorted(companies.values(), key=lambda x: (x['sector'], x['ticker'])):
        grid.setdefault(c['category'], {}).setdefault(c['bucket'], []).append(render_card(c))

    sections = ''.join(
        render_section(k, css, t, js, es, b, grid.get(k, {}), buckets_meta)
        for (k, css, t, js, es, b) in CATEGORIES)

    legend = ''.join(
        f'<div class="lg cat-{css}"><b>{esc(t)}</b><span data-en="{esc(es)}" data-jp="{esc(js)}">{esc(es)}</span></div>'
        for (k, css, t, js, es, b) in CATEGORIES)

    sectors = meta.get('sectors_included', [])
    sec_opts = '<option value="all" data-en="All sectors" data-jp="全セクター">All sectors</option>' + ''.join(
        f'<option value="{esc(s)}" data-en="{esc(s)}" data-jp="{esc(SECTOR_JP.get(s,s))}">{esc(s)}</option>' for s in sectors)
    total = len(companies)
    sec_list = ', '.join(sectors)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>2025 Q4 (FY2025) — 4-Category View · Non-IT</title>
<style>{STYLES}</style>
</head>
<body>
<header class="page-header">
  <div class="lang-toggle">
    <button class="lang-btn active" data-lang="en" onclick="setLang('en')">EN</button>
    <button class="lang-btn" data-lang="jp" onclick="setLang('jp')">日本語</button>
  </div>
  <h1 data-en="2025 Q4 Report (FY2025) — 4-Category View · Non-IT sectors"
      data-jp="2025 Q4決算(FY2025) — 4カテゴリービュー · 非IT業種">2025 Q4 Report (FY2025) — 4-Category View · Non-IT sectors</h1>
  <p class="subtitle" data-en="{total} companies · {esc(sec_list)} · grouped into reason buckets · &quot;2025 Q4&quot; = the FY2025 full-year report"
     data-jp="{total}社 · {esc(sec_list)} · 理由バケット別 · 「2025 Q4」= FY2025通期決算">{total} companies · {esc(sec_list)} · grouped into reason buckets</p>
  <p class="pit-note" data-en="Stock = the market's reaction to the report: close on the announcement date vs ~2 weeks later. Point-in-time: narratives use only the FY2025 report + earlier — never a later report. Click a company for the full research."
     data-jp="株価 = 決算への市場の反応: 発表日の終値 vs 約2週間後。ポイントインタイム: 解説はFY2025決算とそれ以前のみを使用し、後の決算は参照しません。企業をクリックで詳細リサーチ。">Stock = the market's reaction to the report (announcement-date close vs ~2 weeks later). Point-in-time: narratives use only the FY2025 report + earlier. Click a company for the full research.</p>
</header>
<div class="container">
  <div class="filter-row">
    <label data-en="Filter by sector:" data-jp="業種で絞り込み:">Filter by sector:</label>
    <select onchange="filterSector(this)">{sec_opts}</select>
  </div>
  <div class="legend">{legend}</div>
  {sections}
  <footer data-en="Non-IT build · revenue YoY from FY2025 filings, stock change over the fiscal year · narratives via the lighter prompt · IT added later"
          data-jp="非IT版 · 売上前年比はFY2025決算、株価は通期騰落 · ナラティブはライタープロンプト · ITは後日追加">Non-IT build</footer>
</div>
<script>{JS}</script>
</body>
</html>''', encoding='utf-8')

    counts = {k: sum(len(v) for v in grid.get(k, {}).values()) for k, *_ in CATEGORIES}
    print(f'Wrote {OUT}  ({total} companies)')
    print('  ' + ', '.join(f'{k}={counts[k]}' for k, *_ in CATEGORIES))


if __name__ == '__main__':
    main()
