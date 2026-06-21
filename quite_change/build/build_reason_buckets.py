# -*- coding: utf-8 -*-
"""Render hybrid output into UNIFIED_VIEW.html style — grouped into R±×S± category tabs,
then into human-readable REASON BUCKETS (same reason → same bucket, friendly headline).

The hybrid agent emits raw machine tags (business_reason_tag × stock_reason_tag). This
renderer rolls those tag-pairs up into named buckets like
  "Revenue up, profit compressed — derated on margins, potentially recoverable"
exactly the way deliverables/UNIFIED_VIEW.html presents them.

Usage:
    python build/build_reason_buckets.py [input.json] [output.html]
Joins each company with its Tempest packet (data/quarterly/_pkts/{ticker}.json) to get
the revenue/profit direction and the verified stock move.
"""
from __future__ import annotations
import json, html, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / 'deliverables' / 'UNIFIED_VIEW.html'
import os
PKT = ROOT / 'data' / 'quarterly' / os.environ.get('PKTDIR_NAME', '_pkts')
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'quarterly' / 'it_hybrid_guardcheck.json'
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'deliverables' / 'quarterly' / 'VIEW_REASON_BUCKETS.html'
import re as _re
_ym = _re.search(r'(20\d{2})', DATA.stem)
YEAR = _ym.group(1) if _ym else ''
PERIOD = f'{YEAR} Q4' if YEAR else 'Q4'  # full-year (通期) results, the Q4-quarter view

def esc(s): return html.escape(str(s)) if s is not None else ''

# ── reuse UNIFIED_VIEW.html's <style> + <script> verbatim ──
src = SRC.read_text(encoding='utf-8')
style_block = src[src.index('<style>'):src.index('</style>') + len('</style>')]
js_start = src.index('<script>', src.index('</style>'))
js_block = src[js_start:src.index('</script>', js_start) + len('</script>')]
js_block = js_block.replace("let LANG = 'en';", "let LANG = 'jp';")

# ── R±×S± categories ──────────────────────────────────────────────────────────
CATS = {
    'RpSm': ('R+ × S- — Revenue (or profit) up, stock down', '増収（増益）・株安', True,  'down'),
    'RpSp': ('R+ × S+ — Revenue (or profit) up, stock up',   '増収（増益）・株高', True,  'up'),
    'RmSm': ('R- × S- — Revenue (or profit) down, stock down','減収（減益）・株安', False, 'down'),
    'RmSp': ('R- × S+ — Revenue (or profit) down, stock up',  '減収（減益）・株高', False, 'up'),
    'flat': ('S0 — Stock roughly flat', '株価ほぼ変わらず', None, 'flat'),
}
CAT_ORDER = ['RpSp', 'RpSm', 'RmSp', 'RmSm', 'flat']

# ── BUCKET RULES — map (business_reason_tag, stock_reason_tag) → human headline ──
# Each rule: (predicate, bucket_key, headline_en, headline_jp, note_en, note_jp)
# Evaluated in order; first match wins, so put the most specific rules first.
def _is(*tags): return lambda b, s: s in tags
def _b(*tags):  return lambda b, s: b in tags

ONE_OFF = {'one_off_gain', 'one_off_loss', 'one-off_cost_rolloff', 'one_off_gain_rolloff', 'm&a_consolidation'}

RULES = [
    # ----- stock DOWN buckets -----
    (lambda b, s: s == 'no_coverage_overlooked',
     'overlooked', 'No report reason found — overlooked candidate (fundamentals up, stock lagged)',
     '決算に株価下落の理由が見当たらない — 見過ごされ候補（業績改善・株価は出遅れ）',
     'The business kept improving and the filing gives no cause for the stock lagging — a state, not a prediction. Flagged for enrichment, not a forecast of recovery.',
     '業績は改善しているのに、決算書類に株価出遅れの理由が見当たらないグループ。これは「現状」の記述であって将来予測ではない（エンリッチメント対象としてフラグ／反発の予測はしない）。'),
    (lambda b, s: b == 'margin_compression',
     'margin_comp', 'Revenue up, profit compressed — derated on margins',
     '増収も利益率は悪化 — マージンで株価評価が下がった',
     'Sales grew but profit lagged on costs / price competition / up-front investment, so the market derated it. (Describes the state; no forecast of recovery.)',
     '増収でも、コスト増・価格競争・先行投資で利益率が悪化し株価評価が下がったグループ。（現状の記述であり、回復の予測はしない。）'),
    (lambda b, s: s == 'consensus_miss',
     'miss', 'Result missed expectations — stock fell on the print',
     '実績が市場の期待に届かず株価下落',
     'The reported result fell short of what the market expected, so the stock sold off on the print (the stock fell against a flat/up market).',
     '当期の実績が市場の期待に届かず、発表を受けて株価が下落したグループ（市場が横ばい〜上昇の中での下落）。'),
    (lambda b, s: s == 'guidance_disappointment',
     'guidance', 'This year fine, outlook disappointed — weak guidance',
     '今期は堅調も見通しが失望 — 弱いガイダンス',
     'The result itself held up, but next-year guidance disappointed the market.',
     '今期実績は堅調でも、翌期の見通し（ガイダンス）が市場予想を下回り失望されたグループ。'),
    (lambda b, s: s == 'valuation_too_high',
     'valuation', 'Priced for perfection — valuation reset',
     '高すぎた評価の調整 — バリュエーション・リセット',
     'Expectations were already very high; even a decent result could not justify the multiple, so it derated.',
     'すでに期待が高すぎて、まずまずの実績でも株価水準を正当化できず調整したグループ。'),
    (lambda b, s: s == 'sector_narrative_cooling',
     'sector', 'Sector story cooled — theme rotated out',
     'セクターのテーマが沈静化 — 物色が離れた',
     'A cooling sector/theme narrative, more than company news, drove the stock down.',
     '個社の材料というより、セクター・テーマの熱が冷め物色が離れたことで下落したグループ。'),
    # ----- stock UP buckets -----
    (lambda b, s: s == 'capital_return_surprise',
     'capreturn', 'Big capital return — buyback / dividend surprise',
     '大型還元サプライズ — 自社株買い・増配',
     'A large buyback or dividend surprise dominated the stock move.',
     '大型の自社株買い・増配サプライズが株価上昇の主因となったグループ。'),
    (lambda b, s: s == 'rerating_on_growth',
     'rerating', 'Re-rated on growth — market paid up for the story',
     '成長を評価して上昇 — リレーティング',
     'The market re-rated the stock higher on a credible growth story.',
     '信頼できる成長ストーリーを評価して株価が上方に評価し直された（リレーティング）グループ。'),
    # ----- catch-all special situations (any direction) -----
    (lambda b, s: b in ONE_OFF,
     'special', 'Special situation — one-off corporate or accounting event',
     '特殊要因 — 一過性の企業・会計イベント',
     'A one-off item (sale, impairment, M&A, base effect) is the dominant driver — read the card for specifics.',
     '売却・減損・M&A・前期反動などの一過性要因が主因のグループ。詳細は各カードを参照。'),
]
DEFAULT_BUCKET = ('other', 'Other — individual situation',
                  'その他 — 個別事情',
                  'Does not fit a single clean bucket — see the card detail.',
                  '単一のバケットに当てはまらない個別事情のグループ。各カードの詳細を参照。')

def bucket_for(b, s):
    for pred, key, en, jp, ne, nj in RULES:
        if pred(b, s):
            return key, en, jp, ne, nj
    return DEFAULT_BUCKET

def load_pkt(ticker):
    p = PKT / f'{ticker}.json'
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {}

def num(pkt):
    n = pkt.get('numbers', {}) or {}
    ov = n.get('_pit_override') or {}
    pick = lambda k: ov.get(k) if ov.get(k) is not None else n.get(k)
    return pick('rev_pct'), pick('op_pct'), pick('net_pct')

def category_of(rev, net, stock_dir):
    if stock_dir == 'flat': return 'flat'
    biz_up = (rev if rev is not None else (net or 0)) > 0 or (net or 0) > 0
    if biz_up:  return 'RpSp' if stock_dir == 'up' else 'RpSm'
    return 'RmSp' if stock_dir == 'up' else 'RmSm'

def pct(v): return ('+' if (v or 0) > 0 else '') + f'{v}%' if v is not None else '—'

def net_display(pkt, net_pct):
    """A % is meaningless across a profit<->loss sign swing — show 黒字→赤字 / 赤字→黒字 instead."""
    n = pkt.get('numbers', {}) or {}
    cur = n.get('profit')
    try:
        cur = float(cur)
    except (TypeError, ValueError):
        return pct(net_pct)
    if net_pct is not None and net_pct != -100:
        prior = cur / (1 + net_pct / 100)
        if (cur < 0) != (prior < 0):  # sign flipped between years
            return '黒字→赤字 (loss)' if cur < 0 else '赤字→黒字 (profit)'
    return pct(net_pct)

def card(c, pkt):
    rev, op, net = num(pkt)
    prices = pkt.get('prices', {}) or {}
    sp = prices.get('pct_change')
    sp_txt = (('+' if (sp or 0) > 0 else '') + f'{sp}%') if sp is not None else '—'
    name = (pkt.get('name_official_jp') or pkt.get('name_official')
            or pkt.get('name') or c.get('name') or c.get('ticker'))
    body_secs = [
        ('会社について', c.get('overview')),
        ('業績について（今期の結果）', c.get('about_business') or c.get('how_business_moved')),
        ('業績が動いた理由', c.get('why_business_moved')),
        ('株価が動いた理由', c.get('why_stock_moved')),
    ]
    body = ''.join(
        f"<div class='rsec'><div class='rhead'>{esc(h)}</div><div class='rtext'>{esc(t)}</div></div>"
        for h, t in body_secs if t)
    cat = c.get('cited_catalyst')
    if cat:
        body += f"<div class='rsec rmeta'>カタリスト: {esc(cat)}（{esc(c.get('catalyst_source_date',''))}）</div>"
    src_hint = (c.get('sources') or ['—'])[0]
    fym = (pkt.get('period_end', '') or '')[5:7]
    return f'''
    <div class="company-row collapsed" data-fym="{esc(fym)}" onclick="toggleCompany(this, event)">
      <div class="company-head">
        <span class="ticker">{esc(c.get('ticker'))}</span>
        <span class="company-name">{esc(name)}</span>
        <span class="company-meta">
          <span class="badge sub" title="決算期末（この報告が対象とする業務年度の最終日）">FY末 {esc(pkt.get('period_end',''))}</span>
          <span class="badge size" title="決算発表日（市場が反応した日。株価P0はこの日）">発表 {esc(pkt.get('announce_date',''))}</span>
        </span>
        <span class="expand-icon">▸</span>
      </div>
      <div class="company-data">
        <span class="data-item"><span class="data-label">Revenue:</span> {esc(pct(rev))}</span>
        <span class="data-item"><span class="data-label">Op profit:</span> {esc(pct(op))}</span>
        <span class="data-item"><span class="data-label">Net profit:</span> {esc(net_display(pkt, net))}</span>
        <span class="data-item"><span class="data-label">Stock:</span> <b>{esc(sp_txt)}</b></span>
      </div>
      <div class="biz-tag">tag: {esc(c.get('business_reason_tag',''))} × {esc(c.get('stock_reason_tag',''))}</div>
      <div class="company-body">
        <div class="genuine-research">
          <div class="genuine-header">
            <span class="genuine-label">Genuine research</span>
            <span class="genuine-source" title="{esc(src_hint)}">📚 {esc(src_hint)[:110]}</span>
          </div>
          <div class="genuine-body">{body}</div>
        </div>
      </div>
    </div>'''

def render_bucket(bk, cards_html):
    key, en, jp, ne, nj = bk
    return f'''
    <details class="reason-bucket">
      <summary>
        <span class="bucket-toggle-icon">▸</span>
        <span class="bucket-title" data-title-en="{esc(en)}" data-title-jp="{esc(jp)}">{esc(jp)}</span>
        <span class="bucket-count">{len(cards_html)} 件</span>
      </summary>
      <div class="bucket-note" data-note-en="{esc(ne)}" data-note-jp="{esc(nj)}">{esc(nj)}</div>
      <div class="bucket-cards">{''.join(cards_html)}</div>
    </details>'''

def main():
    data = json.loads(DATA.read_text(encoding='utf-8'))
    comps = data['companies']
    # group: category -> bucket_key -> (bucket_meta, [cards])
    cat_groups = {k: {} for k in CATS}
    for c in comps.values():
        pkt = load_pkt(c['ticker'])
        rev, op, net = num(pkt)
        stock_dir = (pkt.get('prices', {}) or {}).get('stock_dir', 'flat')
        cat = category_of(rev, net, stock_dir)
        bk = bucket_for(c.get('business_reason_tag', ''), c.get('stock_reason_tag', ''))
        key = bk[0]
        cat_groups[cat].setdefault(key, (bk, []))[1].append(card(c, pkt))

    n = len(comps)
    # build tabs + panes
    tabs, panes = [], []
    present = [k for k in CAT_ORDER if cat_groups[k]]
    for i, k in enumerate(present):
        en_title, jp_title, _, _ = CATS[k]
        code = en_title.split(' — ')[0]   # e.g. "R+ × S+"  (always shown, language-independent)
        desc = en_title.split(' — ', 1)[1] if ' — ' in en_title else en_title
        total = sum(len(v[1]) for v in cat_groups[k].values())
        active = ' active' if i == 0 else ''
        tabs.append(
            f'<button class="tab{active}" data-cat="{k}" onclick="showCat(this)">'
            f'<span class="tab-code">{esc(code)}</span> '
            f'<span class="tab-desc" data-title-en="{esc(desc)}" data-title-jp="{esc(jp_title)}">{esc(jp_title)}</span>'
            f'<span class="tab-count">{total}</span></button>')
        buckets_html = ''.join(render_bucket(meta, cards) for meta, cards in cat_groups[k].values())
        panes.append(f'<div class="cat-pane" data-cat="{k}" style="display:{ "block" if i==0 else "none"};">{buckets_html}</div>')

    # ── fiscal-year-end filter (front-end only; counts shown per option) ──
    from collections import Counter as _Counter
    MONTHNM = {'01': '1月', '02': '2月', '03': '3月', '04': '4月', '05': '5月', '06': '6月',
               '07': '7月', '08': '8月', '09': '9月', '10': '10月', '11': '11月', '12': '12月'}
    fym_counts = _Counter()
    for c in comps.values():
        pe = load_pkt(c['ticker']).get('period_end', '')
        if len(pe) >= 7:
            fym_counts[pe[5:7]] += 1
    fil = [f'<button class="fyf active" data-fym="all" onclick="filterFY(this)">全て ({n})</button>']
    for m, cnt in sorted(fym_counts.items()):
        fil.append(f'<button class="fyf" data-fym="{m}" onclick="filterFY(this)">{MONTHNM[m]}末 ({cnt})</button>')
    filter_bar = ('<div class="fy-filter"><span class="fy-label">決算期末で絞り込み（同じ決算期＝同じ発表時期・同じ相場環境）:</span>'
                  + ''.join(fil) + '</div>')

    tab_js = '''<script>
function showCat(btn){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  var k=btn.getAttribute('data-cat');
  document.querySelectorAll('.cat-pane').forEach(p=>{p.style.display = p.getAttribute('data-cat')===k ? 'block':'none';});
}
function filterFY(btn){
  document.querySelectorAll('.fyf').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  var m=btn.getAttribute('data-fym');
  document.querySelectorAll('.company-row').forEach(function(r){
    r.style.display = (m==='all' || r.getAttribute('data-fym')===m) ? '' : 'none';
  });
  document.querySelectorAll('.reason-bucket').forEach(function(bk){
    var rows=bk.querySelectorAll('.company-row');
    var vis=Array.prototype.filter.call(rows,function(r){return r.style.display!=='none';}).length;
    bk.style.display = vis ? '' : 'none';
    var bc=bk.querySelector('.bucket-count'); if(bc) bc.textContent = vis+' 件';
  });
  document.querySelectorAll('.tab').forEach(function(t){
    var k=t.getAttribute('data-cat');
    var pane=document.querySelector('.cat-pane[data-cat="'+k+'"]');
    var vis=pane?Array.prototype.filter.call(pane.querySelectorAll('.company-row'),function(r){return r.style.display!=='none';}).length:0;
    var cnt=t.querySelector('.tab-count'); if(cnt) cnt.textContent = vis;
    t.style.opacity = vis ? '1' : '0.4';
  });
}
</script>'''

    body = f'''<body>
<header class="page-header">
  <h1>IT Sector · {PERIOD} Reports — Reason View（情報・通信業 {YEAR}年 Q4 決算）</h1>
  <div class="subtitle">情報・通信業 · {PERIOD}（通期決算）· {n}社 · 株価検証済み (Tempest) · R±×S× × 理由バケット</div>
  <div class="lang-toggle">
    <button class="lang-btn" data-lang="en">EN</button>
    <button class="lang-btn active" data-lang="jp">日本語</button>
  </div>
</header>
<div class="container">
  <div class="sector-pane" style="display:block;">
    {filter_bar}
    <div class="tabs" role="tablist">{''.join(tabs)}</div>
    <div class="tab-content" data-active="true">{''.join(panes)}</div>
  </div>
</div>
{js_block}
{tab_js}
</body>
</html>'''

    out_html = f'''<!DOCTYPE html>
<html lang="jp"><head><meta charset="utf-8">
<title>IT {PERIOD} Reason View — {n}社</title>
{style_block}
<style>
.rsec {{ margin: 10px 0; }}
.rhead {{ font-size: 12.5px; font-weight: 700; color: #1f7a4a; margin-bottom: 3px; }}
.rtext {{ font-size: 13px; line-height: 1.7; color: #1a1a1a; }}
.rmeta {{ font-size: 11.5px; color: #777; border-top: 1px dashed #ddd; padding-top: 8px; }}
.rmeta .rhead {{ display:none; }}
.cat-pane {{ margin-top: 8px; }}
.tab-code {{ font-weight: 800; font-size: 14px; color: #1f7a4a; margin-right: 6px; letter-spacing: .3px; }}
.tab-desc {{ font-size: 12px; color: #555; }}
.fy-filter {{ margin: 6px 0 12px; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }}
.fy-label {{ font-size: 12px; color: #555; margin-right: 6px; }}
.fyf {{ font-size: 12px; padding: 4px 10px; border: 1px solid #cfd8d3; background: #fff; border-radius: 14px;
        cursor: pointer; color: #1a1a1a; }}
.fyf:hover {{ background: #f0f5f2; }}
.fyf.active {{ background: #1f7a4a; color: #fff; border-color: #1f7a4a; font-weight: 700; }}
</style></head>
{body}'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out_html, encoding='utf-8')
    print(f'Written: {OUT}')
    print(f'Companies: {n}')
    for k in present:
        print(f'  [{k}] {CATS[k][0]}')
        for meta, cards in cat_groups[k].values():
            print(f'      {len(cards):2d}  {meta[1]}')

if __name__ == '__main__':
    main()
