# -*- coding: utf-8 -*-
"""Render the IT Q4 (Phase-1, 29 companies) into an EXACT structural copy of UNIFIED_VIEW.html.

Reuses UNIFIED_VIEW.html's <style> and <script> blocks verbatim, then rebuilds the body
(header + EN/JP toggle + sector pane + reason-buckets + company cards) grouped by
business_reason_tag. Stock is pending (Phase-2 not run), so cards show "Stock: pending".
"""
from __future__ import annotations
import json, html, re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / 'deliverables' / 'UNIFIED_VIEW.html'
# optional CLI: build_it_q4_reasonview.py [input.json] [output.html]
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'quarterly' / 'it_q4_2025.json'
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'deliverables' / 'quarterly' / 'VIEW_IT_2025Q4_phase1.html'

def esc(s): return html.escape(str(s)) if s is not None else ''

# ── pull verbatim <style> and <script> from UNIFIED_VIEW.html ──
src = SRC.read_text(encoding='utf-8')
style_block = src[src.index('<style>'):src.index('</style>') + len('</style>')]
# the single <script>...</script> that holds I18N + JS
js_start = src.index('<script>', src.index('</style>'))
js_block = src[js_start:src.index('</script>', js_start) + len('</script>')]
# default to Japanese (narratives are JP); make 日本語 the active button
js_block = js_block.replace("let LANG = 'en';", "let LANG = 'jp';")

# ── bilingual labels for each business_reason_tag bucket ──
TAG_LABELS = {
    'one-off_cost_rolloff': ('Prior-year one-off cost rolled off → profit rebounded',
        '前期の一過性費用が剥落し、利益が反発した',
        'Profit jumped not because the business suddenly strengthened, but because an unusual one-time charge from the prior year (an impairment, a provision) did not repeat. Headline growth overstates the repeatable improvement.',
        '本業が急に強くなったのではなく、前期にあった特殊な一時費用（減損・引当等）が今期はなくなった反動で利益が伸びたグループ。表面の増益率は実力以上に大きく出る点に注意。'),
    'one_off_gain': ('Current-year one-off gain inflated profit',
        '当期の一過性利益が利益を押し上げた',
        'Reported profit was lifted this year by a one-off gain (asset/stake sale, special gain) — not by core-business improvement. The "profit" overstates underlying earning power.',
        '資産・子会社株式の売却益などの一過性利益で当期の利益が押し上げられたグループ。本業の改善ではなく、利益の質に注意が必要。'),
    'one_off_loss': ('Current-year one-off loss depressed profit',
        '当期の一過性損失が利益を押し下げた',
        'Profit fell on a one-off loss (impairment, special/legal/scandal charge), not core-business deterioration. The underlying business may be healthier than the headline.',
        '減損・特別損失・不祥事関連費用などの一過性損失で利益が押し下げられたグループ。本業の悪化ではなく、見かけより実態は健全な場合がある。'),
    'one_off_gain_rolloff': ('Prior-year gain gone → profit fell (high base)',
        '前期の一過性利益が剥落し、利益が減少した（高基準の反動）',
        'Net fell only because a one-off gain in the prior year did not repeat — the business itself grew. A base effect, not deterioration.',
        '前期に一過性の利益（売却益等）があり、その反動で今期の純利益が減ったグループ。本業はむしろ成長しており、見かけの減益は前期比較上の要因。'),
    'margin_expansion': ('Genuine margin expansion (no one-off)',
        '構造的なマージン拡大（一過性要因なし）',
        'After confirming no one-off was hiding in the numbers, profit grew faster than revenue on a genuine mix shift, pricing, or cost efficiency. Quality earnings.',
        '一過性要因がないことを確認した上で、高採算事業の構成比上昇・単価改善・コスト効率化により、売上以上に利益が伸びたグループ。質の高い増益。'),
    'margin_compression': ('Margin compression (cost/price/investment)',
        'マージン悪化（コスト増・価格競争・先行投資）',
        'Profit lagged revenue on rising costs, price competition, or up-front investment. Operating quality softened.',
        'コスト増・価格競争・先行投資により、売上の伸びに利益がついていかなかったグループ。収益性が低下。'),
    'volume_demand_growth': ('Volume / demand growth',
        '数量・需要の伸びによる増収増益',
        'Revenue and profit both grew on higher volume, demand, or contract count — the cleanest form of organic growth.',
        '数量・需要・契約数の伸びにより素直に増収増益となったグループ。最もシンプルな本業成長。'),
    'price_arpu_growth': ('Price / ARPU growth',
        '単価・ARPUの上昇による増益',
        'Profit grew on higher unit price / ARPU / price hikes flowing through.',
        '単価・ARPU・値上げの浸透により利益が伸びたグループ。'),
    'fx_headwind': ('FX headwind depressed profit',
        '為替の逆風（為替差損）で利益が減少',
        'A foreign-exchange loss (or strong yen) pulled profit down, often at the non-operating line — the operating business held up.',
        '為替差損・円高など為替の逆風で（多くは営業外で）利益が押し下げられたグループ。営業段階の本業は底堅いことが多い。'),
    'fx_tailwind': ('FX tailwind lifted profit',
        '為替の追い風（円安）で利益が増加',
        'A weak yen / FX gain was a dominant driver of higher profit.',
        '円安・為替差益が利益増加の主因となったグループ。'),
    'm&a_consolidation': ('M&A / consolidation scale-up',
        'M&A・新規連結による規模拡大',
        'Revenue and profit scaled up on M&A, new consolidation, or subsidiary acquisition.',
        'M&A・新規連結・子会社化により規模が拡大したグループ。'),
    'cyclical_recovery': ('Cyclical / market recovery',
        '市況・サイクルの回復',
        'A market or industry-cycle recovery was the dominant driver.',
        '市況・業界サイクルの回復が主因のグループ。'),
    'other': ('Other / does not fit a single tag',
        'その他（単一タグに当てはまらない）',
        'Individual circumstances that do not fit one clean tag — see the card detail.',
        '個別事情により単一タグに当てはまらないグループ。各カードの詳細を参照。'),
}
TAG_ORDER = ['volume_demand_growth','margin_expansion','price_arpu_growth','m&a_consolidation',
             'cyclical_recovery','fx_tailwind','one-off_cost_rolloff','one_off_gain',
             'margin_compression','fx_headwind','one_off_loss','one_off_gain_rolloff','other']

def genuine_body(c):
    # four clear headings, each with its plain-language text
    secs = [
        ('会社について', 'About the Company', c.get('overview')),
        ('業績について（今期の結果）', 'About the Business (this year)', c.get('how_business_moved')),
        ('業績が動いた理由', 'Why the Business Moved This Way', c.get('why_business_moved')),
        ('株価が動いた理由', 'Why the Stock Moved This Way', c.get('why_stock_moved')),
    ]
    parts = []
    for jp_head, en_head, txt in secs:
        if txt:
            parts.append(f"<div class='rsec'><div class='rhead'>{jp_head}</div><div class='rtext'>{esc(txt)}</div></div>")
    extras = []
    if c.get('one_off_note'): extras.append(f"一過性メモ: {esc(c['one_off_note'])}")
    if c.get('guidance_op_jp'): extras.append(f"翌期ガイダンス: {esc(c['guidance_op_jp'])}")
    if c.get('unverified'): extras.append(f"未確認: {esc(c['unverified'])}")
    if extras:
        parts.append("<div class='rsec rmeta'>" + '<br>'.join(extras) + "</div>")
    return ''.join(parts)

def card(c):
    src_hint = (c.get('sources') or ['—'])[0]
    body = genuine_body(c)
    rev = esc(c.get('rev_pct','')); op = esc(c.get('op_pct','')); net = esc(c.get('net_pct',''))
    flag = c.get('REVIEW_FLAG')
    flag_html = f'<div class="source-thin">⚠ REVIEW: {esc(flag)}</div>' if flag else ''
    return f'''
    <div class="company-row collapsed" onclick="toggleCompany(this, event)">
      <div class="company-head">
        <span class="ticker">{esc(c.get('ticker'))}</span>
        <span class="company-name">{esc(c.get('name_jp') or c.get('name'))}</span>
        <span class="company-meta">
          <span class="badge sub">{esc(c.get('fy_label',''))}</span>
          <span class="badge size">{esc(c.get('size',''))}</span>
        </span>
        <span class="expand-icon">▸</span>
      </div>
      <div class="company-data">
        <span class="data-item"><span class="data-label" data-i18n="card.revenue">Revenue:</span> {rev}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.op">Op profit:</span> {op}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.net">Net profit:</span> {net}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.stock">Stock:</span> <b>pending</b></span>
      </div>
      <div class="biz-tag">分類: {esc(c.get('biz_classification',''))} · tag: {esc(c.get('business_reason_tag',''))} · {esc(c.get('category_provisional',''))}</div>
      <div class="company-body">
        {flag_html}
        <div class="genuine-research">
          <div class="genuine-header">
            <span class="genuine-label" data-i18n="card.genuineLabel">Genuine research</span>
            <span class="genuine-source" title="{esc(src_hint)}">📚 {esc(src_hint)[:110]}…</span>
          </div>
          <div class="genuine-body" data-genuine-en="{body}" data-genuine-jp="{body}">{body}</div>
        </div>
      </div>
    </div>'''

def bucket(tag, cards):
    t_en, t_jp, n_en, n_jp = TAG_LABELS.get(tag, (tag, tag, '', ''))
    return f'''
    <details class="reason-bucket">
      <summary>
        <span class="bucket-toggle-icon">▸</span>
        <span class="bucket-title" data-title-en="{esc(t_en)}" data-title-jp="{esc(t_jp)}">{esc(t_jp)}</span>
        <span class="bucket-count">{len(cards)} names</span>
      </summary>
      <div class="bucket-note" data-note-en="{esc(n_en)}" data-note-jp="{esc(n_jp)}">{esc(n_jp)}</div>
      <div class="bucket-cards">{''.join(cards)}</div>
    </details>'''

def main():
    data = json.loads(DATA.read_text(encoding='utf-8'))
    comps = data['companies']
    groups = {}
    for c in comps.values():
        groups.setdefault(c.get('business_reason_tag','other'), []).append(c)
    buckets_html = []
    for tag in sorted(groups, key=lambda k: TAG_ORDER.index(k) if k in TAG_ORDER else 99):
        cards = [card(c) for c in sorted(groups[tag], key=lambda x: x['ticker'])]
        buckets_html.append(bucket(tag, cards))

    n = len(comps)
    body = f'''<body>
<header class="page-header">
  <h1 data-i18n="page.title">IT Q4 FY2025 — Reason View (Phase-1)</h1>
  <div class="subtitle">情報・通信業 · {n}/100社 (Phase-1 partial) · 株価検証待ち (stock pending, Phase-2 not run) · reason-bucket grouping</div>
  <div class="lang-toggle">
    <button class="lang-btn" data-lang="en">EN</button>
    <button class="lang-btn active" data-lang="jp">日本語</button>
  </div>
  <div class="top-controls">
    <label data-i18n="sector.label">Sector:</label>
    <select id="sector-select">
      <option value="IT" data-en="Information &amp; Communication (情報・通信業)" data-jp="情報・通信業" selected>情報・通信業</option>
    </select>
  </div>
</header>
<div class="container">
  <div class="sector-pane" data-sector="IT" style="display: block;">
    <div class="sector-stats-block">
      <div class="stats-header"><span class="stats-topix-name">TOPIX-33業種: 情報・通信業 (Information &amp; Communication)</span></div>
      <div class="stats-counts">
        <div class="stat-cell"><span class="stat-label">対象ユニバース</span><span class="stat-value">100</span></div>
        <div class="stat-cell stat-qualifying"><span class="stat-label">Phase-1完了</span><span class="stat-value">{n}</span></div>
        <div class="stat-cell stat-excluded"><span class="stat-label">残り</span><span class="stat-value">{100-n}</span></div>
        <div class="stat-cell stat-delisted"><span class="stat-label">株価検証</span><span class="stat-value">pending</span></div>
      </div>
      <div class="stats-math-note">Phase-1 = 数値・業績理由・タグのみ。株価方向(S+/S-)とPhase-2の株価理由は未実行のため、ここでは business_reason_tag でグループ化しています。</div>
    </div>
    <div class="tabs" role="tablist">
      <button class="tab active" data-tab="reason-IT" role="tab">
        業績が動いた理由でグループ化 (by business reason)<span class="tab-count">{n}</span>
      </button>
    </div>
    <div class="tab-content tab-reason-IT" data-active="true">
      {''.join(buckets_html)}
    </div>
  </div>
</div>
{js_block}
</body>
</html>'''

    out_html = f'''<!DOCTYPE html>
<html lang="jp">
<head>
<meta charset="utf-8">
<title>IT Q4 FY2025 — Reason View (Phase-1, {n}社)</title>
{style_block}
<style>
.rsec {{ margin: 10px 0; }}
.rhead {{ font-size: 12.5px; font-weight: 700; color: #1f7a4a; margin-bottom: 3px; }}
.rtext {{ font-size: 13px; line-height: 1.7; color: #1a1a1a; }}
.rmeta {{ font-size: 11.5px; color: #777; border-top: 1px dashed #ddd; padding-top: 8px; }}
.rmeta .rhead {{ display:none; }}
</style>
</head>
{body}'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out_html, encoding='utf-8')
    print(f'Written: {OUT}')
    print(f'Companies: {n} · buckets: {len(buckets_html)}')
    for tag in sorted(groups, key=lambda k: TAG_ORDER.index(k) if k in TAG_ORDER else 99):
        print(f'  {len(groups[tag]):2d}  {tag}')

if __name__ == '__main__':
    main()
