"""Quarterly / point-in-time / 4-category view builder  (PILOT).

Reads a quarterly data JSON (see _make_pilot_data.py for the schema) and emits ONE
standalone HTML file per calendar-quarter snapshot. Each file shows all covered
companies sorted into the full 2x2 grid:

    R+ x S-   (revenue up, stock down  — the "overlooked" focus)
    R+ x S+   (revenue up, stock up)
    R- x S+   (revenue down, stock up)
    R- x S-   (revenue down, stock down)

Each company card is point-in-time: the report shown is the latest one filed as of
that calendar quarter-end, and the reasoning uses only reports up to that date
(never the future). A navigation bar links the per-quarter files together so you
can flip across time and watch companies move between categories.

Usage:
    python build/build_quarterly_view.py                      # default pilot JSON
    python build/build_quarterly_view.py data/quarterly/x.json
"""
from __future__ import annotations
import sys, io, json, html
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = Path(__file__).parent
ROOT = HERE.parent
OUT_DIR = ROOT / 'deliverables' / 'quarterly'

DATA_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'quarterly' / 'pilot_IT_2025.json'

# Display order + per-category presentation metadata
CATEGORIES = [
    ('R+xS-', 'focus',   'R+ × S-', '売上↑ / 株価↓', 'Revenue up, stock down',   '本命 / Focus — the overlooked'),
    ('R+xS+', 'up',      'R+ × S+', '売上↑ / 株価↑', 'Revenue up, stock up',     'Working as expected'),
    ('R-xS+', 'rdown',   'R- × S+', '売上↓ / 株価↑', 'Revenue down, stock up',   'Stock up despite shrinking sales'),
    ('R-xS-', 'down',    'R- × S-', '売上↓ / 株価↓', 'Revenue down, stock down', 'Both falling'),
]
CAT_JP = {
    'R+xS-': '売上↑ / 株価↓ — 見落とされ',
    'R+xS+': '売上↑ / 株価↑ — 想定通り',
    'R-xS+': '売上↓ / 株価↑ — 減収でも株高',
    'R-xS-': '売上↓ / 株価↓ — 両方下落',
}


def esc(s):
    return html.escape(str(s)) if s is not None else ''


def fmt_pct(v):
    return f'{v:+.1f}%' if isinstance(v, (int, float)) else 'n/a'


def dir_arrow(d):
    return '▲' if d == 'up' else ('▼' if d == 'down' else '–')


def render_card(tk, comp, snap):
    rev = snap['revenue_yoy_pct']
    stk = snap['stock_yoy_pct']
    rev_cls = 'pos' if snap['revenue_dir'] == 'up' else 'neg'
    stk_cls = 'pos' if snap['stock_dir'] == 'up' else 'neg'
    op_cls = 'pos' if snap['op_dir'] == 'up' else ('neg' if snap['op_dir'] == 'down' else '')
    sources = ' · '.join(snap.get('sources', []))

    return f'''
    <div class="company-row collapsed" onclick="toggleCompany(this, event)">
      <div class="company-head">
        <span class="ticker">{esc(tk)}</span>
        <span class="company-name">{esc(comp['name'])}</span>
        <span class="company-meta"><span class="badge fy">FY end {esc(comp.get('fy_end',''))}</span></span>
        <span class="expand-icon">▸</span>
      </div>
      <div class="report-label" data-en="{esc('As of ' + snap['snapshot_quarter_end'] + ' · latest report: ' + snap['report_label'])}"
           data-jp="{esc(snap['snapshot_quarter_end'] + ' 時点 · 最新報告: ' + snap['report_label'])}">
        As of {esc(snap['snapshot_quarter_end'])} · latest report: {esc(snap['report_label'])}
      </div>
      <div class="company-data">
        <span class="data-item"><span class="data-label" data-en="Revenue YoY" data-jp="売上 前年比">Revenue YoY</span>
          <b class="{rev_cls}">{dir_arrow(snap['revenue_dir'])} {fmt_pct(rev)}</b></span>
        <span class="data-item"><span class="data-label" data-en="Operating profit" data-jp="営業利益">Operating profit</span>
          <b class="{op_cls}">{dir_arrow(snap['op_dir'])}</b>
          <span class="op-note" data-en="{esc(snap.get('op_note',''))}" data-jp="{esc(snap.get('op_note',''))}">{esc(snap.get('op_note',''))}</span></span>
        <span class="data-item"><span class="data-label" data-en="Stock YoY" data-jp="株価 前年比">Stock YoY</span>
          <b class="{stk_cls}">{dir_arrow(snap['stock_dir'])} {fmt_pct(stk)}</b></span>
      </div>
      <div class="company-body">
        <div class="genuine-research">
          <div class="genuine-header">
            <span class="genuine-label" data-en="Why (point-in-time — uses only reports up to this quarter)"
                  data-jp="理由(ポイントインタイム — この四半期までの報告のみ使用)">Why (point-in-time — uses only reports up to this quarter)</span>
          </div>
          <div class="genuine-body" data-en="{esc(snap['reasoning_en'])}" data-jp="{esc(snap['reasoning_jp'])}">{esc(snap['reasoning_en'])}</div>
          <div class="genuine-source">📚 {esc(sources)}</div>
        </div>
      </div>
    </div>'''


def render_category_section(cat_key, css_cls, en_title, jp_sub, en_sub, badge, cards):
    n = len(cards)
    inner = ''.join(cards) if cards else (
        '<p class="empty-note" data-en="No companies in this category for this quarter."'
        ' data-jp="この四半期にこのカテゴリーに該当する企業はありません。">'
        'No companies in this category for this quarter.</p>')
    open_attr = 'open' if cards else ''
    return f'''
    <details class="cat-section cat-{css_cls}" {open_attr}>
      <summary>
        <span class="cat-toggle">▸</span>
        <span class="cat-title">{esc(en_title)}</span>
        <span class="cat-sub" data-en="{esc(en_sub)}" data-jp="{esc(jp_sub)}">{esc(en_sub)}</span>
        <span class="cat-badge" data-en="{esc(badge)}" data-jp="{esc(CAT_JP[cat_key])}">{esc(badge)}</span>
        <span class="cat-count">{n}</span>
      </summary>
      <div class="cat-cards">{inner}</div>
    </details>'''


def render_nav(quarters, current):
    items = []
    for q in quarters:
        cls = 'navq active' if q == current else 'navq'
        href = f'VIEW_{q}.html'
        items.append(f'<a class="{cls}" href="{esc(href)}">{esc(q)}</a>')
    idx = quarters.index(current)
    prev_link = f'<a class="navarrow" href="VIEW_{quarters[idx-1]}.html">‹ Prev</a>' if idx > 0 else '<span class="navarrow disabled">‹ Prev</span>'
    next_link = f'<a class="navarrow" href="VIEW_{quarters[idx+1]}.html">Next ›</a>' if idx < len(quarters) - 1 else '<span class="navarrow disabled">Next ›</span>'
    return f'<div class="quarter-nav">{prev_link}<div class="navq-list">{"".join(items)}</div>{next_link}</div>'


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

/* Quarter navigation */
.quarter-nav { display:flex; align-items:center; justify-content:space-between; gap:12px; background:#fff; border:1px solid #e0e0e0; border-radius:8px; padding:10px 14px; margin:18px 0; flex-wrap:wrap; }
.navq-list { display:flex; gap:6px; flex-wrap:wrap; justify-content:center; flex:1; }
.navq { font-size:13px; font-weight:600; color:#555; text-decoration:none; padding:5px 12px; border-radius:5px; border:1px solid #e0e0e0; background:#fafafa; }
.navq:hover { border-color:#1f7a4a; color:#1f7a4a; }
.navq.active { background:#1f7a4a; color:#fff; border-color:#1f7a4a; }
.navarrow { font-size:13px; font-weight:600; color:#1f7a4a; text-decoration:none; padding:5px 10px; }
.navarrow.disabled { color:#bbb; }

/* Legend */
.legend { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:14px 0 6px; }
.legend .lg { font-size:11.5px; padding:8px 10px; border-radius:6px; border:1px solid #e0e0e0; }
.legend .lg b { display:block; font-size:13px; margin-bottom:2px; }
.lg.cat-focus { background:#f0f8f3; border-color:#cfe6d8; } .lg.cat-focus b { color:#1f7a4a; }
.lg.cat-up    { background:#eef6fb; border-color:#d2e4ef; } .lg.cat-up b { color:#2f5377; }
.lg.cat-rdown { background:#fdf6ec; border-color:#ecdcbf; } .lg.cat-rdown b { color:#9a6b1f; }
.lg.cat-down  { background:#fdf2f2; border-color:#ecd5d5; } .lg.cat-down b { color:#a83b3b; }
@media (max-width:720px){ .legend { grid-template-columns:repeat(2,1fr); } }

/* Category sections */
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

/* Company cards */
.company-row { background:#fff; border:1px solid #e0e0e0; border-radius:6px; padding:14px 16px; margin:10px 0; transition:background .15s,border-color .15s; cursor:pointer; }
.company-row:hover { background:#f0f8f3; border-color:#1f7a4a; }
.company-row:not(.collapsed) { cursor:default; }
.company-row:not(.collapsed) .company-body { cursor:text; }
.company-head { display:flex; align-items:baseline; gap:12px; user-select:none; }
.expand-icon { font-size:12px; color:#999; transition:transform .15s; margin-left:auto; }
.company-row:not(.collapsed) .expand-icon { transform:rotate(90deg); }
.ticker { font-family:monospace; font-size:13px; color:#777; }
.company-name { font-size:16px; font-weight:700; }
.badge { font-size:10.5px; padding:1px 6px; border-radius:3px; background:#ececec; color:#555; font-weight:600; }
.badge.fy { background:#eef0f4; color:#54618a; }
.report-label { font-size:11.5px; color:#888; margin:6px 0 2px; font-style:italic; }
.company-data { display:flex; gap:18px; flex-wrap:wrap; font-size:12.5px; color:#555; margin:8px 0 2px; }
.data-label { color:#888; font-weight:600; margin-right:5px; }
.company-data b.pos { color:#1f7a4a; } .company-data b.neg { color:#a83b3b; }
.op-note { color:#999; font-style:italic; margin-left:4px; }
.company-row.collapsed .company-body { display:none; }
.company-body { padding-top:10px; }
.genuine-research { background:#f0f8f3; border-left:4px solid #1f7a4a; padding:12px 14px; border-radius:4px; }
.genuine-header { margin-bottom:8px; font-size:11.5px; }
.genuine-label { font-weight:700; color:#1f7a4a; }
.genuine-body { font-size:13px; line-height:1.7; color:#1a1a1a; }
.genuine-source { font-size:10.5px; color:#999; margin-top:8px; }
.empty-note { padding:14px; color:#999; font-style:italic; font-size:13px; }

footer { text-align:center; color:#aaa; font-size:11px; padding:20px; }
'''

JS = '''
function setLang(lang){
  document.documentElement.setAttribute('lang', lang);
  document.querySelectorAll('.lang-btn').forEach(b=>b.classList.toggle('active', b.dataset.lang===lang));
  document.querySelectorAll('[data-en]').forEach(el=>{
    const v = lang==='jp' ? el.getAttribute('data-jp') : el.getAttribute('data-en');
    if(v!==null) el.textContent = v;
  });
}
function toggleCompany(row, ev){
  if(!row.classList.contains('collapsed') && ev.target.closest('.company-body')) return;
  row.classList.toggle('collapsed');
}
document.addEventListener('DOMContentLoaded',()=>setLang('en'));
'''


def build_one(data, quarter):
    quarters = data['_meta']['quarters']
    companies = data['companies']
    sector = data['_meta'].get('sector', '')

    # bucket companies by category for this quarter
    by_cat = {c[0]: [] for c in CATEGORIES}
    for tk, comp in companies.items():
        snap = comp['snapshots'].get(quarter)
        if not snap:
            continue
        by_cat.setdefault(snap['category'], []).append((tk, comp, snap))

    sections = []
    for cat_key, css_cls, en_title, jp_sub, en_sub, badge in CATEGORIES:
        rows = sorted(by_cat.get(cat_key, []), key=lambda x: x[0])
        cards = [render_card(tk, comp, snap) for tk, comp, snap in rows]
        sections.append(render_category_section(cat_key, css_cls, en_title, jp_sub, en_sub, badge, cards))

    legend = ''.join(
        f'<div class="lg cat-{css}"><b>{esc(t)}</b><span data-en="{esc(es)}" data-jp="{esc(js)}">{esc(es)}</span></div>'
        for (k, css, t, js, es, b) in CATEGORIES)

    qend = next((companies[tk]['snapshots'][quarter]['snapshot_quarter_end']
                 for tk in companies if quarter in companies[tk]['snapshots']), quarter)

    total = sum(len(v) for v in by_cat.values())

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(sector)} Quarterly View — {esc(quarter)}</title>
<style>{STYLES}</style>
</head>
<body>
<header class="page-header">
  <div class="lang-toggle">
    <button class="lang-btn active" data-lang="en" onclick="setLang('en')">EN</button>
    <button class="lang-btn" data-lang="jp" onclick="setLang('jp')">日本語</button>
  </div>
  <h1 data-en="{esc(sector)} — Quarterly 4-Category View ({esc(quarter)})"
      data-jp="{esc(sector)} — 四半期4カテゴリービュー ({esc(quarter)})">{esc(sector)} — Quarterly 4-Category View ({esc(quarter)})</h1>
  <p class="subtitle" data-en="Snapshot as of {esc(qend)} · {total} companies · pilot ({len(companies)} IT names)"
     data-jp="{esc(qend)} 時点のスナップショット · {total}社 · パイロット({len(companies)}社)">Snapshot as of {esc(qend)} · {total} companies · pilot ({len(companies)} IT names)</p>
  <p class="pit-note" data-en="Point-in-time: each card uses only reports filed on/before this quarter — never the future."
     data-jp="ポイントインタイム: 各カードはこの四半期までに提出された報告のみを使用し、将来の報告は一切参照しません。">Point-in-time: each card uses only reports filed on/before this quarter — never the future.</p>
</header>
<div class="container">
  {render_nav(quarters, quarter)}
  <div class="legend">{legend}</div>
  {''.join(sections)}
  {render_nav(quarters, quarter)}
  <footer data-en="Pilot build · revenue YoY from quarterly filings, stock YoY at quarter-end close · sources per card"
          data-jp="パイロット版 · 売上前年比は四半期決算、株価前年比は四半期末終値 · 出典は各カード参照">Pilot build · revenue YoY from quarterly filings, stock YoY at quarter-end close · sources per card</footer>
</div>
<script>{JS}</script>
</body>
</html>'''


def main():
    with open(DATA_PATH, encoding='utf-8') as fp:
        data = json.load(fp)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    quarters = data['_meta']['quarters']
    for q in quarters:
        out_path = OUT_DIR / f'VIEW_{q}.html'
        out_path.write_text(build_one(data, q), encoding='utf-8')
        # per-quarter category counts
        counts = {}
        for tk in data['companies']:
            snap = data['companies'][tk]['snapshots'].get(q)
            if snap:
                counts[snap['category']] = counts.get(snap['category'], 0) + 1
        print(f'Wrote {out_path}  ({", ".join(f"{k}={v}" for k,v in sorted(counts.items()))})')


if __name__ == '__main__':
    main()
