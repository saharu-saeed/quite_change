"""Oil sector view builder — sector-specific R+ classification with filter toggle.

Differences from build_view.py (the IT-sector engine):
- Loads sector_config.json to know which filter modes are available
- Each company entry has multiple filter tags (rev_dir, op_dir, etc.)
- HTML includes a filter dropdown above the tabs
- HTML includes a collapsible 'Why this filter?' panel with plain-language explanation
- The filter is applied client-side via JavaScript (no rebuild on toggle)

Same as build_view.py:
- R+×S- / R+×S+ tab structure
- Language toggle (EN / 日本語)
- Bucket organization
- Genuine research green block per company
- Source-prose toggle

This is the prototype for sector-specific deliverables. Later this logic will be
unified into a single multi-sector view (one HTML with sector dropdown + filter dropdown).
"""
from __future__ import annotations
import json, sys, io, html
from pathlib import Path
# Reconfigure stdout for utf-8 — only when run as a script (mirrors build_view.py).
if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

HERE = Path(__file__).parent              # build/
ROOT = HERE.parent                        # quite_change/
DATA = ROOT / 'data'                      # data/
DELIVERABLES = ROOT / 'deliverables'      # deliverables/

# Load sector config
with open(DATA / 'sector_config.json', encoding='utf-8') as fp:
    sector_config = json.load(fp)

# Load oil-sector data
with open(DATA / 'company_research_oil_sector.json', encoding='utf-8') as fp:
    oil_data_raw = json.load(fp)
oil_meta = oil_data_raw.get('_meta', {})
oil_companies = {k: v for k, v in oil_data_raw.items() if k != '_meta'}

SECTOR_CFG = sector_config['Oil']

# ───── HTML helpers ─────

def esc(s): return html.escape(str(s)) if s is not None else ''

import re as _re_md
_BOLD_RE = _re_md.compile(r'\*\*(.+?)\*\*')
def esc_with_bold(s):
    return _BOLD_RE.sub(r'<b>\1</b>', esc(s))


def render_company_card(ticker: str, c: dict) -> str:
    """Render one company card — same structure as IT-sector cards."""
    name = c.get('name', '?')
    rev = c.get('rev_dir', '?')
    op = c.get('op_dir', '?')
    netd = c.get('net_dir', '?')
    stock_dir = c.get('stock_dir', '?')
    stock_yoy = c.get('stock_yoy_estimate', '')
    biz = c.get('biz_classification', '')
    qualifies = c.get('filter_qualifies', [])
    bucket = c.get('bucket', '?')

    gr_jp = c.get('jp_summary', '')
    gr_en = c.get('en_summary', '')
    src = c.get('source_hint', '')

    # Tags (rev / op / net direction + filter membership)
    dir_emoji = {'up': '↑', 'down': '↓', 'flat': '→'}
    rev_emoji = dir_emoji.get(rev, '?')
    op_emoji = dir_emoji.get(op, '?')
    net_emoji = dir_emoji.get(netd, '?')

    # Hidden attribute marking which filters this card belongs to (JS uses this)
    qualifies_attr = ','.join(qualifies)

    return f'''
    <div class="company-row" data-filters="{esc(qualifies_attr)}">
      <div class="company-head">
        <span class="ticker">{esc(ticker)}</span>
        <span class="company-name">{esc(name)}</span>
      </div>
      <div class="company-data">
        <span class="data-item"><span class="data-label" data-i18n="card.revenue">売上:</span> {rev_emoji} {esc(rev)}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.op">営業利益:</span> {op_emoji} {esc(op)}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.net">純利益:</span> {net_emoji} {esc(netd)}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.stock">株価:</span> <b>{esc(stock_yoy)}</b></span>
      </div>
      <div class="biz-tag">分類: {esc(biz)} · バケット: {esc(bucket)}</div>
      <div class="genuine-research">
        <div class="genuine-header">
          <span class="genuine-label" data-i18n="card.genuineLabel">本物の調査 (combined-prompt verification)</span>
          <span class="genuine-source" title="{esc(src)}">📚 {esc(src)[:80]}…</span>
        </div>
        <div class="genuine-body" data-genuine-en="{esc_with_bold(gr_en)}" data-genuine-jp="{esc_with_bold(gr_jp)}">{esc_with_bold(gr_en)}</div>
      </div>
    </div>
    '''

# ───── Filter explanation panel ─────

def render_filter_panel() -> str:
    """Render the 'Why this filter?' collapsible panel — one expandable section per filter."""
    explanations = SECTOR_CFG['filter_explanations']
    sections = []
    for filter_key, exp in explanations.items():
        label_en = exp.get('label_en', filter_key)
        label_jp = exp.get('label_jp', filter_key)
        long_en = exp.get('long_en', '')
        long_jp = exp.get('long_jp', '')
        sections.append(f'''
        <details class="filter-explanation" data-filter="{esc(filter_key)}">
          <summary>
            <span class="filter-exp-label" data-en="Why use {esc(label_en)}?" data-jp="なぜ「{esc(label_jp)}」を使う?">
              Why use {esc(label_en)}?
            </span>
          </summary>
          <div class="filter-exp-body" data-en="{esc(long_en).replace(chr(10),'<br><br>')}" data-jp="{esc(long_jp).replace(chr(10),'<br><br>')}">
            {esc(long_en).replace(chr(10), '<br><br>')}
          </div>
        </details>
        ''')
    return '\n'.join(sections)


# ───── Tab content ─────

def render_tab_content(tab_name: str) -> str:
    """Render all companies for a given tab (R+xS- or R+xS+)."""
    cards = []
    for ticker, c in oil_companies.items():
        if c.get('tab') == tab_name:
            cards.append(render_company_card(ticker, c))
    if not cards:
        return f'<p class="empty-note">No companies in this tab under the current filter.</p>'
    return '\n'.join(cards)


# ───── HTML / CSS / JS ─────

STYLES = '''
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Helvetica, Arial, "Hiragino Sans", "Meiryo", sans-serif; margin: 0; padding: 0; color: #1a1a1a; background: #f7f7f5; line-height: 1.55; }
.container { max-width: 1080px; margin: 0 auto; padding: 24px; }
header.page-header { background: #fff; border-bottom: 1px solid #e0e0e0; padding: 22px 24px; }
.page-header h1 { margin: 0 0 4px; font-size: 20px; font-weight: 700; }
.page-header .subtitle { color: #555; font-size: 13px; margin: 4px 0 0; }

/* Filter controls */
.filter-row { background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 14px 18px; margin: 16px 0; }
.filter-row label { font-size: 13px; font-weight: 600; color: #333; margin-right: 8px; }
.filter-row select { font-size: 13px; padding: 6px 12px; border: 1px solid #ccc; border-radius: 4px; background: #fff; }
.filter-row .filter-note { font-size: 12px; color: #777; margin-top: 8px; }

/* Filter explanations */
.filter-explanations-block { background: #fdf6e3; border-left: 4px solid #d4a017; padding: 14px 18px; margin: 12px 0; border-radius: 4px; }
.filter-explanations-block h3 { margin: 0 0 8px; font-size: 14px; color: #555; }
.filter-explanation { margin: 8px 0; }
.filter-explanation > summary { cursor: pointer; font-size: 13px; font-weight: 600; color: #1f7a4a; padding: 6px 0; }
.filter-explanation > summary:hover { color: #155a35; }
.filter-exp-body { font-size: 13px; color: #333; line-height: 1.7; padding: 10px 0 4px 8px; border-left: 2px solid #d4a017; }

/* Tabs */
.tabs { display: flex; gap: 0; margin: 16px 0 0; border-bottom: 2px solid #e0e0e0; }
.tab { padding: 10px 18px; cursor: pointer; font-size: 14px; font-weight: 600; color: #888; border-bottom: 3px solid transparent; margin-bottom: -2px; }
.tab.active { color: #1f7a4a; border-bottom-color: #1f7a4a; }
.tab-content { display: none; padding: 18px 0; }
.tab-content[data-active="true"] { display: block; }

/* Company cards */
.company-row { background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px 18px; margin: 12px 0; }
.company-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px; }
.ticker { font-family: monospace; font-size: 13px; color: #777; }
.company-name { font-size: 16px; font-weight: 700; }
.company-data { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12.5px; color: #555; margin-bottom: 8px; }
.data-label { color: #888; font-weight: 600; }
.biz-tag { font-size: 11.5px; color: #777; margin-bottom: 10px; font-style: italic; }
.genuine-research { background: #f0f8f3; border-left: 4px solid #1f7a4a; padding: 12px 14px; border-radius: 4px; }
.genuine-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; font-size: 11.5px; color: #555; }
.genuine-label { font-weight: 700; color: #1f7a4a; }
.genuine-source { font-size: 10.5px; color: #999; }
.genuine-body { font-size: 13px; line-height: 1.7; color: #1a1a1a; white-space: pre-wrap; }
.genuine-body b { color: #1f7a4a; }

.empty-note { padding: 20px; color: #888; font-style: italic; }

/* Language toggle */
.lang-toggle { position: absolute; top: 22px; right: 22px; display: flex; gap: 4px; }
.lang-btn { padding: 4px 10px; font-size: 12px; border: 1px solid #ccc; background: #fff; cursor: pointer; border-radius: 3px; }
.lang-btn.active { background: #1f7a4a; color: #fff; border-color: #1f7a4a; }
'''

JS = '''
const I18N = {
  en: {
    'page.title': 'Oil Sector — R+ Classification View (FY3/2026)',
    'page.subtitle': '2026-06-04 · Latest available reports · Filter-configurable (operating-profit-based default for commodity sectors)',
    'filter.label': 'Filter mode:',
    'filter.note': 'Filter is sector-specific. For oil, operating-profit-up captures business performance better than revenue-up because revenue moves with crude oil prices.',
    'explanations.heading': 'Why these filter options?',
    'tab.sMinus': 'R+ × S- — Revenue (or profit) up, stock down',
    'tab.sPlus': 'R+ × S+ — Revenue (or profit) up, stock up',
    'card.revenue': 'Revenue:',
    'card.op': 'Op profit:',
    'card.net': 'Net profit:',
    'card.stock': 'Stock:',
    'card.genuineLabel': 'Genuine research (combined-prompt verification)'
  },
  jp: {
    'page.title': '石油セクター — R+分類ビュー(2026年3月期)',
    'page.subtitle': '2026-06-04 · 最新の利用可能なレポート · フィルター設定可能(コモディティセクターでは営業利益ベースがデフォルト)',
    'filter.label': 'フィルターモード:',
    'filter.note': 'フィルターはセクター固有です。石油セクターでは、売上は原油価格と連動して動くため、営業利益ベースの方が事業パフォーマンスをより良く捉えます。',
    'explanations.heading': 'なぜこれらのフィルターオプションなのか?',
    'tab.sMinus': 'R+ × S- — 売上(または利益)↑、株価↓',
    'tab.sPlus': 'R+ × S+ — 売上(または利益)↑、株価↑',
    'card.revenue': '売上:',
    'card.op': '営業利益:',
    'card.net': '純利益:',
    'card.stock': '株価:',
    'card.genuineLabel': '本物の調査 (combined-prompt verification)'
  }
};
let LANG = 'en';
let CURRENT_FILTER = '営業利益○';  // default for oil

function applyI18n() {
  const dict = I18N[LANG];
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key] != null) el.textContent = dict[key];
  });
  // Filter explanation labels and bodies
  document.querySelectorAll('.filter-exp-label').forEach(el => {
    const v = el.getAttribute('data-' + LANG);
    if (v != null) el.textContent = v;
  });
  document.querySelectorAll('.filter-exp-body').forEach(el => {
    const v = el.getAttribute('data-' + LANG);
    if (v != null) el.innerHTML = v;
  });
  // Genuine research body
  document.querySelectorAll('.genuine-body[data-genuine-en]').forEach(el => {
    const v = el.getAttribute('data-genuine-' + LANG);
    if (v != null) el.innerHTML = v;
  });
  document.documentElement.setAttribute('lang', LANG);
}

function setLang(lang) {
  LANG = lang;
  document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
  applyI18n();
}

function applyFilter(filter) {
  CURRENT_FILTER = filter;
  // Show/hide cards based on whether they qualify under this filter
  document.querySelectorAll('.company-row').forEach(row => {
    const qualifies = (row.getAttribute('data-filters') || '').split(',');
    const visible = (filter === '両方') ? qualifies.length > 0 : qualifies.includes(filter);
    row.style.display = visible ? '' : 'none';
  });
}

function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.setAttribute('data-active', 'false'));
  document.querySelector('.tab[data-tab="' + name + '"]').classList.add('active');
  document.querySelector('.tab-content.tab-' + name).setAttribute('data-active', 'true');
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => showTab(t.getAttribute('data-tab')));
  });
  document.querySelectorAll('.lang-btn').forEach(b => {
    b.addEventListener('click', () => setLang(b.dataset.lang));
  });
  const filterSelect = document.getElementById('filter-select');
  if (filterSelect) {
    filterSelect.addEventListener('change', e => applyFilter(e.target.value));
  }
  applyI18n();
  applyFilter(CURRENT_FILTER);
});
'''

# Build filter dropdown options
filter_options_html = ''
for filt in SECTOR_CFG['available_filters']:
    exp = SECTOR_CFG['filter_explanations'].get(filt, {})
    label_en = exp.get('label_en', filt)
    selected = ' selected' if filt == SECTOR_CFG['default_filter'] else ''
    filter_options_html += f'<option value="{esc(filt)}"{selected}>{esc(label_en)}</option>\n'

# Build the HTML doc
s_minus_content = render_tab_content('R+xS-')
s_plus_content = render_tab_content('R+xS+')
filter_panel = render_filter_panel()

doc = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Oil Sector — R+ Classification View</title>
<style>{STYLES}</style>
</head>
<body>
<header class="page-header" style="position: relative;">
  <h1 data-i18n="page.title">Oil Sector — R+ Classification View (FY3/2026)</h1>
  <div class="subtitle" data-i18n="page.subtitle">2026-06-04 · Latest available reports · Filter-configurable</div>
  <div class="lang-toggle">
    <button class="lang-btn active" data-lang="en">EN</button>
    <button class="lang-btn" data-lang="jp">日本語</button>
  </div>
</header>

<div class="container">

  <!-- Filter dropdown -->
  <div class="filter-row">
    <label for="filter-select" data-i18n="filter.label">Filter mode:</label>
    <select id="filter-select">
      {filter_options_html}
    </select>
    <div class="filter-note" data-i18n="filter.note">
      Filter is sector-specific. For oil, operating-profit-up captures business performance better than revenue-up because revenue moves with crude oil prices.
    </div>
  </div>

  <!-- Filter explanations -->
  <div class="filter-explanations-block">
    <h3 data-i18n="explanations.heading">Why these filter options?</h3>
    {filter_panel}
  </div>

  <!-- Tabs -->
  <div class="tabs">
    <div class="tab active" data-tab="s-minus">
      <span data-i18n="tab.sMinus">R+ × S- — Profit up, stock down</span>
    </div>
    <div class="tab" data-tab="s-plus">
      <span data-i18n="tab.sPlus">R+ × S+ — Profit up, stock up</span>
    </div>
  </div>

  <div class="tab-content tab-s-minus" data-active="true">
    {s_minus_content}
  </div>
  <div class="tab-content tab-s-plus" data-active="false">
    {s_plus_content}
  </div>

</div>

<script>{JS}</script>
</body>
</html>
'''

def write_outputs():
    """Write standalone oil-sector HTML + console summary. Only when run as a script."""
    DELIVERABLES.mkdir(exist_ok=True)
    out_html = DELIVERABLES / 'OIL_SECTOR_2026_view.html'
    out_html.write_text(doc, encoding='utf-8')
    print(f'Wrote deliverables/{out_html.name} ({len(doc):,} bytes)')

    # Print classification summary
    print('\n=== Oil Sector Classification Summary ===')
    print(f'Default filter: {SECTOR_CFG["default_filter"]}')
    print(f'Available filters: {", ".join(SECTOR_CFG["available_filters"])}')
    print()
    for tab_name in ['R+xS+', 'R+xS-']:
        tab_companies = [(k, c) for k, c in oil_companies.items() if c.get('tab') == tab_name]
        print(f'  [{len(tab_companies)}] {tab_name}')
        for ticker, c in tab_companies:
            filters = '/'.join(c.get('filter_qualifies', []))
            print(f'    {ticker} {c.get("name","?")[:30]:30s}  rev:{c.get("rev_dir","?"):4s} op:{c.get("op_dir","?"):4s} stock:{c.get("stock_dir","?"):4s}  qualifies:[{filters}]')


if __name__ == '__main__':
    write_outputs()
