"""IT sector Japanese-only quarterly view builder.

Reads data/quarterly/it_{quarter}_2025.json and emits deliverables/quarterly/VIEW_IT_2025{QUARTER}.html.
Japanese-only frontend (no EN toggle — saves tokens on generation side).

Usage:
  python build/build_it_quarterly_view.py Q4   # → VIEW_IT_2025Q4.html
  python build/build_it_quarterly_view.py Q3   # → VIEW_IT_2025Q3.html
  python build/build_it_quarterly_view.py Q2   # → VIEW_IT_2025Q2.html
  python build/build_it_quarterly_view.py Q1   # → VIEW_IT_2025Q1.html
"""
from __future__ import annotations
import sys, io, json, html, re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = Path(__file__).parent
ROOT = HERE.parent

QUARTER = sys.argv[1].upper() if len(sys.argv) > 1 else 'Q4'
OUT = ROOT / 'deliverables' / 'quarterly' / f'VIEW_IT_2025{QUARTER}.html'
DATA_PATH = ROOT / 'data' / 'quarterly' / f'it_{QUARTER.lower()}_2025.json'

CATEGORIES = [
    ('R+xS-', 'focus', 'R+ × S-', '売上↑ / 株価↓ — 見落とされ'),
    ('R+xS+', 'up',    'R+ × S+', '売上↑ / 株価↑ — 想定通り'),
    ('R-xS+', 'rdown', 'R- × S+', '売上↓ / 株価↑ — 減収でも株高'),
    ('R-xS-', 'down',  'R- × S-', '売上↓ / 株価↓ — 両方下落'),
]

QUARTER_DESC = {
    'Q4': '通期（FY-ending-2025）',
    'Q3': '第3四半期（累計9ヶ月）',
    'Q2': '第2四半期（累計6ヶ月・中間期）',
    'Q1': '第1四半期（累計3ヶ月）',
}

SIZE_JP = {'large': '大型（L）', 'mid': '中型（M）', 'small': '小型（S）'}

_BOLD = re.compile(r'\*\*(.+?)\*\*')


def esc(s):
    return html.escape(str(s)) if s is not None else ''


def esc_bold(s):
    return _BOLD.sub(r'<b>\1</b>', esc(s)).replace('\n\n', '<br><br>').replace('\n', '<br>')


def arrow(d):
    return '↑' if d == 'up' else ('↓' if d == 'down' else '→')


def render_card(c):
    rev_e = arrow(c.get('revenue_dir', ''))
    op_e  = arrow(c.get('op_dir', ''))
    net_e = arrow(c.get('net_dir', ''))
    stk_cls = 'pos' if c.get('stock_dir') == 'up' else 'neg'
    sz = c.get('size', '')
    sz_label = SIZE_JP.get(sz, sz)
    src = ' · '.join(c.get('sources', []))
    gr_jp = esc_bold(c.get('jp_summary', ''))

    announce = esc(c.get('announce_date', ''))
    fy = esc(c.get('fy_label', ''))

    return f'''
    <div class="company-row collapsed" data-size="{esc(sz)}" onclick="toggleCompany(this, event)">
      <div class="company-head">
        <span class="ticker">{esc(c["ticker"])}</span>
        <span class="company-name">{esc(c["name"])}</span>
        <span class="company-meta">
          <span class="badge size">{esc(sz_label)}</span>
          <span class="badge fy">{fy}</span>
        </span>
        <span class="expand-icon">▸</span>
      </div>
      <div class="report-meta">発表日 {announce}　株価は発表後約2週間の変化で測定</div>
      <div class="company-data">
        <span class="data-item"><span class="data-label">売上(累計):</span> {rev_e} {esc(c.get("rev_pct",""))}</span>
        <span class="data-item"><span class="data-label">営業利益:</span> {op_e} {esc(c.get("op_pct",""))}</span>
        <span class="data-item"><span class="data-label">純利益:</span> {net_e} {esc(c.get("net_pct",""))}</span>
        <span class="data-item"><span class="data-label">株価（決算後2週間）:</span> <b class="{stk_cls}">{esc(c.get("stock_2w_estimate",""))}</b></span>
      </div>
      <div class="biz-tag">分類: {esc(c.get("biz_classification",""))}</div>
      <div class="company-body">
        <div class="genuine-research">
          <div class="genuine-header">
            <span class="genuine-label">リサーチ（軽量プロンプト・ポイントインタイム）</span>
            <span class="genuine-source" title="{esc(src)}">📚 {esc(src)}</span>
          </div>
          <div class="genuine-body">{gr_jp}</div>
        </div>
      </div>
    </div>'''


def render_bucket(bucket_key, label, cards):
    note_jp = esc(label.get('note_jp', '')).replace('\n', '<br><br>')
    return f'''
    <details class="reason-bucket" open>
      <summary>
        <span class="bucket-toggle-icon">▸</span>
        <span class="bucket-title">{esc(label.get("title_jp", bucket_key))}</span>
        <span class="bucket-count">{len(cards)}社</span>
      </summary>
      <div class="bucket-note">{note_jp}</div>
      <div class="bucket-cards">{''.join(cards)}</div>
    </details>'''


def render_section(cat_key, css_cls, cat_label, cat_jp, by_bucket, buckets_meta):
    n = sum(len(v) for v in by_bucket.values())
    if not by_bucket:
        inner = '<p class="empty-note">該当企業はありません。</p>'
    else:
        ordered = sorted(by_bucket.keys(), key=lambda k: buckets_meta.get(k, {}).get('order', 99))
        inner = ''.join(render_bucket(bk, buckets_meta.get(bk, {'title_jp': bk}), by_bucket[bk]) for bk in ordered)
    return f'''
    <details class="cat-section cat-{css_cls}" {'open' if n else ''}>
      <summary>
        <span class="cat-toggle">▸</span>
        <span class="cat-title">{esc(cat_label)}</span>
        <span class="cat-sub">{esc(cat_jp)}</span>
        <span class="cat-count">{n}</span>
      </summary>
      <div class="cat-cards">{inner}</div>
    </details>'''


STYLES = '''
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", "Meiryo", sans-serif; margin: 0; color: #1a1a1a; background: #f7f7f5; line-height: 1.55; }
.container { max-width: 1080px; margin: 0 auto; padding: 24px; }
header.page-header { background: #fff; border-bottom: 1px solid #e0e0e0; padding: 22px 24px; }
.page-header h1 { margin: 0 0 4px; font-size: 20px; font-weight: 700; }
.page-header .subtitle { color: #555; font-size: 13px; margin: 4px 0 0; }
.page-header .pit-note { color: #2f5377; font-size: 12px; margin: 8px 0 0; background:#eef3f8; border-left:3px solid #2f5377; padding:6px 10px; border-radius:3px; display:inline-block; }

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
.cat-count { margin-left:auto; background:#f0f0f0; border-radius:9px; padding:1px 10px; font-size:12px; color:#555; }
.cat-cards { padding:4px 0 8px; }

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
.badge.size { background:#f8eee6; color:#774b2f; }
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
function toggleCompany(row, ev){
  if(ev&&ev.target&&ev.target.closest('.company-body')) return;
  if(window.getSelection&&window.getSelection().toString().length>0) return;
  row.classList.toggle('collapsed');
}
function filterSize(sel){
  const v=sel.value;
  document.querySelectorAll('.company-row').forEach(r=>{
    r.classList.toggle('hidden-by-filter', v!=='all'&&r.dataset.size!==v);
  });
  document.querySelectorAll('.reason-bucket').forEach(b=>{
    const vis=b.querySelectorAll('.company-row:not(.hidden-by-filter)').length;
    b.style.display = vis? '' : 'none';
  });
  document.querySelectorAll('.cat-section').forEach(sec=>{
    const vis=sec.querySelectorAll('.company-row:not(.hidden-by-filter)').length;
    const c=sec.querySelector('.cat-count'); if(c) c.textContent=vis;
  });
}
'''


def main():
    if not DATA_PATH.exists():
        print(f'[ERROR] Data file not found: {DATA_PATH}', file=sys.stderr)
        sys.exit(1)

    with open(DATA_PATH, encoding='utf-8') as fp:
        data = json.load(fp)

    companies = data['companies']
    meta = data.get('_meta', {})
    buckets_meta = data.get('buckets', {})

    grid = {c[0]: {} for c in CATEGORIES}
    for c in sorted(companies.values(), key=lambda x: (x.get('size', ''), x['ticker'])):
        grid.setdefault(c['category'], {}).setdefault(c['bucket'], []).append(render_card(c))

    sections = ''.join(
        render_section(k, css, k, jp_sub, grid.get(k, {}), buckets_meta)
        for (k, css, _, jp_sub) in CATEGORIES)

    legend = ''.join(
        f'<div class="lg cat-{css}"><b>{esc(k)}</b><span>{esc(jp_sub)}</span></div>'
        for (k, css, _, jp_sub) in CATEGORIES)

    total = len(companies)
    q_desc = QUARTER_DESC.get(QUARTER, QUARTER)

    size_opts = '<option value="all">全規模</option><option value="large">大型（L）30社</option><option value="mid">中型（M）30社</option><option value="small">小型（S）40社</option>'

    rplus_s_minus = sum(1 for c in companies.values() if c.get('category') == 'R+xS-')
    rplus_s_plus  = sum(1 for c in companies.values() if c.get('category') == 'R+xS+')
    rminus_s_plus = sum(1 for c in companies.values() if c.get('category') == 'R-xS+')
    rminus_s_minus= sum(1 for c in companies.values() if c.get('category') == 'R-xS-')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IT 2025 {QUARTER} — 4カテゴリービュー（日本語）</title>
<style>{STYLES}</style>
</head>
<body>
<header class="page-header">
  <h1>IT業種 2025 {QUARTER} — 4カテゴリービュー</h1>
  <p class="subtitle">{total}社 · 大型30 / 中型30 / 小型40 · {esc(q_desc)} · 理由バケット別</p>
  <p class="subtitle">R+×S-={rplus_s_minus} / R+×S+={rplus_s_plus} / R-×S+={rminus_s_plus} / R-×S-={rminus_s_minus}</p>
  <p class="pit-note">株価 = 決算発表への市場の反応（発表日終値 vs 約2週間後終値）。ポイントインタイム: 解説は当該期決算とそれ以前のみ参照。企業名クリックで詳細表示。</p>
</header>
<div class="container">
  <div class="filter-row">
    <label>規模で絞り込み:</label>
    <select onchange="filterSize(this)">{size_opts}</select>
  </div>
  <div class="legend">{legend}</div>
  {sections}
  <footer>IT業種 · 2025 {QUARTER} · 日本語専用ビュー · ナラティブはライタープロンプト · ポイントインタイム</footer>
</div>
<script>{JS}</script>
</body>
</html>''', encoding='utf-8')

    print(f'Wrote {OUT}  ({total} companies)')
    print(f'  R+xS-={rplus_s_minus}, R+xS+={rplus_s_plus}, R-xS+={rminus_s_plus}, R-xS-={rminus_s_minus}')


if __name__ == '__main__':
    main()
