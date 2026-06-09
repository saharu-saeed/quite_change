"""Unified multi-sector view builder.

Imports build_view (IT) and build_oil_view (Oil) as modules — uses their already-classified
data structures to render a single HTML with:
  • sector dropdown at top
  • per-sector filter dropdown
  • per-sector 'why this filter?' explanation panel
  • R+×S- / R+×S+ tabs (same as before)
  • bucket organization within IT tabs (same as before)
  • company-name CLICK TOGGLE — click name to expand/collapse the green research block
  • EN / 日本語 language toggle

Both source scripts are importable thanks to their `if __name__ == '__main__':` guards —
importing them does NOT overwrite their standalone HTML outputs.
"""
from __future__ import annotations
import sys, io, json, html
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Make sibling modules importable
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

# Importing this triggers IT data loading + classification (but NOT file write)
import build_view as it_mod

# Sector JSON loaders (direct loads — no separate build scripts needed)
import json as _json
def _load_sector_json(fname):
    with open(Path(__file__).parent.parent / 'data' / fname, encoding='utf-8') as fp:
        raw = _json.load(fp)
    meta = raw.pop('_meta', {})
    return meta, raw

mining_meta, mining_companies = _load_sector_json('company_research_mining_sector.json')
petroleum_meta, petroleum_companies = _load_sector_json('company_research_petroleum_sector.json')
marine_meta, marine_companies = _load_sector_json('company_research_marine_sector.json')
land_meta, land_companies = _load_sector_json('company_research_land_transport_sector.json')
air_meta, air_companies = _load_sector_json('company_research_air_transport_sector.json')
agri_meta, agri_companies = _load_sector_json('company_research_agri_fishery_sector.json')

ROOT = HERE.parent
DATA = ROOT / 'data'
DELIVERABLES = ROOT / 'deliverables'

with open(DATA / 'sector_config.json', encoding='utf-8') as fp:
    sector_config = json.load(fp)


# ───── Generic helpers ─────

def esc(s): return html.escape(str(s)) if s is not None else ''

import re as _re_md
_BOLD_RE = _re_md.compile(r'\*\*(.+?)\*\*')
def esc_with_bold(s):
    return _BOLD_RE.sub(r'<b>\1</b>', esc(s))


# ───── Sector statistics transparency block ─────

def render_sector_stats_block(sector_cfg: dict, stats: dict) -> str:
    """Render the professional 'Sector statistics' block shown at the top of each sector pane.

    Shows: TOPIX-33 sector name + universe count + considered + qualifying + excluded list.
    Designed to be clean and readable — collapsible 'excluded names' list for detail."""
    name_en = sector_cfg.get('sector_name_en', '')
    name_jp = sector_cfg.get('sector_name_jp', '')
    topix_name_full = sector_cfg.get('topix33_official_name', f'{name_jp} ({name_en})')
    # For EN display: bilingual; for JP display: JP-only (drop the English parenthetical)
    topix_name_en = topix_name_full
    topix_name_jp = name_jp or topix_name_full

    total = stats.get('total_listed_in_topix33_sector', '—')
    considered = stats.get('considered_in_this_analysis', '—')
    qualifying = stats.get('qualifying_as_R_plus', '—')
    excluded = stats.get('excluded', []) or []
    smaller_note = stats.get('smaller_unlisted_or_not_covered', '')

    # Classify excluded entries: currently-listed R- vs historical (delisted/TOB)
    # so the math adds up: Total = Qualifying + R-(current). Delisted/TOB shown separately.
    rminus_current = []
    delisted = []
    for e in excluded:
        reason = (e.get('reason', '') or '').upper()
        if reason.startswith('DELISTED') or 'TOB' in reason.split()[:3] or 'DELISTED' in reason.split()[:2]:
            delisted.append(e)
        else:
            rminus_current.append(e)
    rminus_count = len(rminus_current)
    delisted_count = len(delisted)
    excluded_count = len(excluded)

    excluded_items_html = ''
    if excluded:
        items = []
        for e in rminus_current + delisted:
            tk = esc(e.get('ticker', '?'))
            nm = esc(e.get('name', '?'))
            rs = esc(e.get('reason', ''))
            items.append(f'<li><b>{tk}</b> {nm} — <span class="excl-reason">{rs}</span></li>')
        excluded_items_html = f'''
        <details class="excluded-list">
          <summary>
            <span data-en="Show {excluded_count} excluded companies" data-jp="除外された{excluded_count}社を表示">
              Show {excluded_count} excluded companies
            </span>
          </summary>
          <ul class="excl-items">{''.join(items)}</ul>
          {f'<p class="excl-smaller">{esc(smaller_note)}</p>' if smaller_note else ''}
        </details>
        '''

    # Math check note (rendered if the numbers don't reconcile)
    math_note = ''
    try:
        if isinstance(total, int) and isinstance(qualifying, int):
            if qualifying + rminus_count == total:
                math_note_text_en = f'Math: {qualifying} R+ + {rminus_count} R- = {total} currently listed. {delisted_count} delisted/TOB shown separately.'
                math_note_text_jp = f'内訳: R+ {qualifying} + R- {rminus_count} = 現上場 {total}社。 上場廃止/TOB {delisted_count}社は別途表示。'
                math_note = f'<div class="stats-math-note" data-en="{math_note_text_en}" data-jp="{math_note_text_jp}">{math_note_text_en}</div>'
    except Exception:
        pass

    return f'''
    <div class="sector-stats-block">
      <div class="stats-header">
        <span class="stats-topix-name" data-en="TOPIX-33 sector: {esc(topix_name_en)}" data-jp="TOPIX-33業種: {esc(topix_name_jp)}">
          TOPIX-33 sector: {esc(topix_name_en)}
        </span>
      </div>
      <div class="stats-counts">
        <div class="stat-cell">
          <span class="stat-label" data-en="Total listed in sector" data-jp="セクターの上場企業数">Total listed in sector</span>
          <span class="stat-value">{total}</span>
        </div>
        <div class="stat-cell stat-qualifying">
          <span class="stat-label" data-en="Qualifying as R+" data-jp="R+として該当">Qualifying as R+</span>
          <span class="stat-value">{qualifying}</span>
        </div>
        <div class="stat-cell stat-excluded">
          <span class="stat-label" data-en="R- (currently listed)" data-jp="R-(現在上場中)">R- (currently listed)</span>
          <span class="stat-value">{rminus_count}</span>
        </div>
        <div class="stat-cell stat-delisted">
          <span class="stat-label" data-en="Delisted / TOB (historical)" data-jp="上場廃止・TOB(過去)">Delisted / TOB (historical)</span>
          <span class="stat-value">{delisted_count}</span>
        </div>
      </div>
      {math_note}
      {excluded_items_html}
    </div>
    '''


# ───── IT sector pane content ─────
# Uses build_view's already-populated data structures + render functions.

def render_it_company_card(r: dict) -> str:
    """Render one IT-sector company card with click-to-toggle on the name.

    The basic data (ticker, name, revenue / stock direction) is always visible.
    The green 'Genuine research' block + Pattern + Source prose is hidden by default,
    revealed when the user clicks the company name.
    """
    yoy = r.get('stock_yoy_pct')
    yoy_str = f'{yoy:+.1f}%' if yoy is not None else 'n/a'
    rd = r.get('rev_dir') or 'n/a'

    gr = it_mod.genuine_research.get(r['ticker'], {}) or {}
    gr_jp = gr.get('jp_summary') or ''
    gr_en = gr.get('en_summary') or ''
    gr_src = gr.get('source_hint') or ''

    raw_prose = (r.get('rawExplanation') or '').strip()
    has_raw = len(raw_prose) > 80
    raw_display_en = esc(raw_prose).replace('\n', '<br>')
    raw_display_jp = esc(it_mod.build_jp_source_summary(r)).replace('\n', '<br>')

    # Hidden body — shown when user clicks the name
    if gr_en or gr_jp:
        genuine_block = f'''
      <div class="genuine-research">
        <div class="genuine-header">
          <span class="genuine-label" data-i18n="card.genuineLabel">Genuine research (JP web search per company)</span>
          <span class="genuine-source" title="{esc(gr_src)}">📚 {esc(gr_src)[:120]}…</span>
        </div>
        <div class="genuine-body" data-genuine-en="{esc_with_bold(gr_en)}" data-genuine-jp="{esc_with_bold(gr_jp)}">{esc_with_bold(gr_en)}</div>
      </div>'''
    else:
        genuine_block = ('<div class="genuine-missing" data-i18n="card.genuineMissing">'
                         '⚠ Per-company web-search research not yet completed for this ticker.</div>')

    pattern_block = f'''
      <details class="pattern-collapse">
        <summary><span data-i18n="card.patternLabel">Pattern (bucket-templated):</span></summary>
        <div class="reason-text"><span class="reason-pattern-text" data-pattern-en="{esc(r.get('_reason_text',''))}" data-pattern-jp="{esc(r.get('_reason_text_jp',''))}">{r.get('_reason_text','')}</span></div>
      </details>'''

    if has_raw:
        source_block = (
            '<details class="source-prose">'
            '<summary><span data-i18n="card.sourceLabel">Source prose (fixture rawExplanation)</span></summary>'
            f'<div class="source-prose-body" data-source-en="{raw_display_en}" data-source-jp="{raw_display_jp}">{raw_display_en}</div>'
            '</details>'
        )
    else:
        source_block = ('<div class="source-thin" data-i18n="card.sourceThin">'
                        '⚠ Source prose for this company-year is thin.</div>')

    # Whole card click-to-toggle (clicks inside .company-body are ignored — see JS)
    return f'''
    <div class="company-row collapsed" onclick="toggleCompany(this, event)">
      <div class="company-head">
        <span class="ticker">{esc(r['ticker'])}</span>
        <span class="company-name">{esc(r['name'])}</span>
        <span class="company-meta">
          <span class="badge sub">{esc(r.get('sub_type',''))}</span>
          <span class="badge size">{esc(r.get('size',''))}</span>
        </span>
        <span class="expand-icon">▸</span>
      </div>
      <div class="company-data">
        <span class="data-item"><span class="data-label" data-i18n="card.revenue">Revenue:</span> {esc(rd)}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.stockYoy">Stock 2025 YoY:</span> <b>{esc(yoy_str)}</b></span>
      </div>
      <div class="company-body">
        {genuine_block}
        {pattern_block}
        {source_block}
      </div>
    </div>
    '''


def render_it_bucket(bucket_key: str, recs: list, group_class: str) -> str:
    if not recs:
        return ''
    label = it_mod.BUCKET_LABELS[bucket_key]
    recs_sorted = sorted(recs, key=lambda x: (x['ticker'] == '3778', x['ticker']))
    cards = ''.join(render_it_company_card(r) for r in recs_sorted)
    return f'''
    <details class="reason-bucket">
      <summary>
        <span class="bucket-toggle-icon">▸</span>
        <span class="bucket-title" data-title-en="{esc(label['title'])}" data-title-jp="{esc(label['title_jp'])}">{esc(label['title'])}</span>
        <span class="bucket-count">{len(recs)} names</span>
      </summary>
      <div class="bucket-note" data-note-en="{esc(label['note'])}" data-note-jp="{esc(label['note_jp'])}">{esc(label['note'])}</div>
      <div class="bucket-cards">{cards}</div>
    </details>
    '''


def render_it_tab(buckets: dict, group_class: str) -> str:
    if not buckets:
        return '<p class="empty-note">No records in this group.</p>'
    keys = sorted(buckets.keys(), key=lambda k: it_mod.BUCKET_LABELS[k]['order'])
    return ''.join(render_it_bucket(bk, buckets[bk], group_class) for bk in keys)


def build_it_sector_pane() -> str:
    s_minus_inner = render_it_tab(it_mod.buckets_s_minus, 'tab-s-minus')
    s_plus_inner = render_it_tab(it_mod.buckets_s_plus, 'tab-s-plus')
    total_minus = sum(len(v) for v in it_mod.buckets_s_minus.values())
    total_plus = sum(len(v) for v in it_mod.buckets_s_plus.values())

    # IT sector filter explanation
    it_cfg = sector_config['IT']
    exp = it_cfg['filter_explanations']['売上○']
    why_panel = f'''
      <details class="filter-explanation">
        <summary>
          <span data-en="Why use {esc(exp['label_en'])}?" data-jp="なぜ「{esc(exp['label_jp'])}」を使う?">
            Why use {esc(exp['label_en'])}?
          </span>
        </summary>
        <div class="filter-exp-body" data-en="{esc(exp['long_en']).replace(chr(10), '<br><br>')}" data-jp="{esc(exp['long_jp']).replace(chr(10), '<br><br>')}">
          {esc(exp['long_en']).replace(chr(10), '<br><br>')}
        </div>
      </details>'''

    # IT filter options (single option, but needs JP translation)
    it_filter_label_en = it_cfg['filter_explanations']['売上○']['label_en']
    it_filter_label_jp = it_cfg['filter_explanations']['売上○']['label_jp']

    # IT sector statistics (computed live from build_view module data)
    it_stats = {
        'total_listed_in_topix33_sector': 600,
        'considered_in_this_analysis': 122,
        'qualifying_as_R_plus': total_minus + total_plus,
        'excluded': [],  # excluded list is captured aggregated; not enumerated here
        'smaller_unlisted_or_not_covered': f'~{600-122} smaller IT/Info-Comm companies not in the curated 122-company census. Of the 122: {total_minus + total_plus} R+, ~14 R-, ~2 unclassified.'
    }
    it_cfg_for_stats = {
        'sector_name_en': 'Information & Communication',
        'sector_name_jp': '情報・通信業',
        'topix33_official_name': '情報・通信業 (Information & Communication)'
    }
    stats_block = render_sector_stats_block(it_cfg_for_stats, it_stats)

    return f'''
    <div class="sector-pane" data-sector="IT" style="display: block;">

      {stats_block}

      <div class="filter-row">
        <label data-i18n="filter.label">Filter mode:</label>
        <select class="sector-filter" data-sector="IT">
          <option value="売上○" data-en="{esc(it_filter_label_en)}" data-jp="{esc(it_filter_label_jp)}" selected>{esc(it_filter_label_en)}</option>
        </select>
        <div class="filter-note" data-i18n="filter.note.IT">
          For IT sector, revenue growth = business growth. No alternative filter needed.
        </div>
      </div>

      <div class="filter-explanations-block">
        <h3 data-i18n="explanations.heading">Why these filter options?</h3>
        {why_panel}
      </div>

      <div class="tabs" role="tablist">
        <button class="tab s-minus active" data-tab="s-minus-IT" role="tab">
          <span data-i18n="tab.sMinus">R+ × S- — Revenue up, stock down</span>
          <span class="tab-count">{total_minus}</span>
          <span class="tab-focus-note" data-i18n="tab.focus">本命 / Focus</span>
        </button>
        <button class="tab s-plus" data-tab="s-plus-IT" role="tab">
          <span data-i18n="tab.sPlus">R+ × S+ — Revenue up, stock up</span>
          <span class="tab-count">{total_plus}</span>
        </button>
      </div>

      <div class="tab-content tab-s-minus-IT" data-active="true">
        {s_minus_inner}
      </div>
      <div class="tab-content tab-s-plus-IT" data-active="false">
        {s_plus_inner}
      </div>
    </div>
    '''


# ───── Bucket labels for non-IT sectors ─────
# Imports IT's BUCKET_LABELS vocabulary + adds 3 new buckets specific to commodity / cyclical patterns
# that don't fit IT's framing (rev-down/OP-up is the opposite of IT's profit_compressed).

# Bucket labels generated by Sonnet categorization (2026-06-07) for non-IT sectors.
# 17 keys covering Land Transport (6), Mining (3), Petroleum (4), Marine (2), Air Transport (2).
_SECTOR_BUCKETS_2026 = {
    # === Land Transportation (6) ===
    'inbound_tourism_play': {
        'title': 'Inbound tourism beneficiaries',
        'title_jp': 'インバウンド需要の直接受益',
        'note': 'Railways, leisure operators, taxis, and buses whose core earnings and stock story is driven by the surge in foreign tourists — via unique route monopolies (KIX-Namba, Narita Skyliner, Hakone, Arashiyama, Mt. Fuji, Kyoto/Osaka Golden Route), the Osaka-Kansai Expo, and premium tourism experiences that foreign visitors cannot bypass.',
        'note_jp': '訪日外国人観光客の急増・大阪万博・インバウンドゴールデンルートを直接享受できる独占的路線・観光地を持つ鉄道、バス、タクシー、レジャー企業。弱円＋インバウンド回復が構造的な業績ドライバー。',
        'order': 1,
    },
    'logistics_rate_hike_winner': {
        'title': 'Logistics 2024-Problem rate-hike winners',
        'title_jp': '2024年問題・運賃改定の恩恵銘柄',
        'note': 'Freight truckers, LTL carriers, parcel operators, and 3PL providers whose earnings and stock recovered sharply because the 2024 driver-hour regulations forced industrywide rate increases; EC-market growth and manufacturer 3PL-outsourcing also provide structural volume tailwinds.',
        'note_jp': '2024年問題(ドライバー労働時間規制)を背景とした運賃改定の浸透と、EC物流・3PL外部委託需要の拡大が業績回復の主因。特積み・宅配・3PL・総合物流に広く恩恵。',
        'order': 2,
    },
    'redevelopment_play': {
        'title': 'Station / urban redevelopment story',
        'title_jp': '駅前・都市再開発が主テーマの銘柄',
        'note': 'Private railways whose dominant investor thesis is a major station-area or urban real-estate redevelopment — either as a long-term re-rating catalyst (Shinjuku Southwest, Shinagawa/Takanawa, Umekita, Fukuoka Tenjin) or as a near-term overhang when the project is delayed or shelved (Shibuya 7-year delay, Nagoya station effective shelving).',
        'note_jp': '大規模な駅前・都市再開発プロジェクトが株価の主要テーマ。再開発の進捗が株価上昇のカタリスト(京急・京王・相鉄・西鉄)になる一方、東急の渋谷7年延期・名鉄の名駅再開発白紙化のように株価下落の要因にもなるグループ。',
        'order': 3,
    },
    'auto_logistics_specialist': {
        'title': 'Auto & specialty logistics specialists',
        'title_jp': '自動車・特殊物流スペシャリスト',
        'note': 'Companies whose business is built around finished-vehicle transport, auto-parts logistics, or moving-industry consolidation — benefiting from automotive production recovery after the chip shortage, 2024-Problem rate hikes in car-carrier pricing, and growing market share through M&A-driven industry consolidation.',
        'note_jp': '完成車輸送・自動車部品物流・引越業界を専門とする企業。半導体不足解消後の国内自動車生産回復、キャリアカー運賃改定、引越業界の寡占化進行が共通の業績ドライバー。',
        'order': 4,
    },
    'one_off_profit_collapse': {
        'title': 'Profit hit by specific one-off event',
        'title_jp': '特定の一過性要因で利益が急減した銘柄',
        'note': 'Companies where net profit fell sharply — not from core-business deterioration — but from a clearly named one-off: reversal of a prior-year sale-and-leaseback gain, a large-property liquidation base effect, equity-method investee softening after an activist retreat, or a full MBO/delisting transaction dominating the share-price narrative.',
        'note_jp': '本業は堅調でも、前期の大型資産売却益の反動減・のれん減損・持分法投資損益悪化・MBO上場廃止など特定の一過性要因により純利益が急減した銘柄。表面数字と本業実態の乖離に注意が必要なグループ。',
        'order': 5,
    },
    'regional_quiet_compounder': {
        'title': 'Regional quiet compounder',
        'title_jp': '地域密着型・静かな成長銘柄',
        'note': 'Small-to-mid regional players — bus operators, specialized industrial-logistics niche players, small truckers, and regional holding companies — growing steadily through fare revisions, stable long-term contracts, and local market dominance, without a single high-profile catalyst driving the stock.',
        'note_jp': '地方バス・特殊産業物流・中堅トラック・地域インフラなど、派手な触媒はなく運賃改定・長期契約・地域独占によって着実に成長する中小型銘柄。特定のビッグテーマではなく安定配当と業績積み上げが評価軸。',
        'order': 6,
    },
    # === Mining (3) ===
    'investment_income_driven': {
        'title': 'Investment-income driven',
        'title_jp': '投資収益依存型',
        'note': 'These companies earn their headline profit primarily from returns on minority stakes in overseas mines or diversified investment assets, not from their own operating volumes. When commodity prices shift, dividend income and mine-investment returns swing sharply, disconnecting earnings from the core business.',
        'note_jp': 'これらの企業は、自社の販売量ではなく、海外鉱山への少数出資や分散投資資産からの収益(配当金・投資利益)が利益の大部分を占める構造を持つ。商品価格が変動すると、投資収益が大きく振れ、コア事業の好不調とは切り離されて業績が動く。',
        'order': 1,
    },
    'post_coal_reinvention': {
        'title': 'Post-coal business reinvention',
        'title_jp': '脱炭素転換・事業再構築型',
        'note': 'This company proactively exited coal to adapt to the decarbonization era, and is now growing through M&A of entirely new business segments. Its profit expansion is driven by acquired subsidiaries rather than legacy resources.',
        'note_jp': '脱炭素の潮流に対応するために自ら石炭事業から撤退し、M&Aにより全く新しい事業セグメントを構築して成長している。利益拡大の原動力は既存の資源事業ではなく、買収子会社の貢献にある。',
        'order': 2,
    },
    'niche_commodity_operator': {
        'title': 'Niche commodity growth operator',
        'title_jp': 'ニッチ商品・成長オペレーター型',
        'note': 'This company is an active operator of a niche, globally-demanded commodity (iodine) whose price and volume are rising on structural demand trends. Growth is organic — driven by capacity expansion and favorable pricing — not by acquisitions or passive investment income.',
        'note_jp': '世界的な需要拡大が続くニッチ商品(ヨウ素)を自社で採掘・精製・販売するオペレーター型企業。成長はM&Aや受動的投資収益によるものではなく、設備投資による生産能力拡大と販売価格上昇という有機的な事業成長に基づく。',
        'order': 3,
    },
    # === Petroleum (4) ===
    'major_refiner': {
        'title': 'Major refiners — crude-driven',
        'title_jp': '大手精製・原油価格連動型',
        'note': "Japan's three large-scale oil refiners whose earnings rise and fall primarily with crude-oil prices and inventory valuation time-lag effects; all are simultaneously building adjacent growth axes (renewables, high-functional materials) to reduce that dependency.",
        'note_jp': '原油価格の変動と在庫評価のタイムラグ効果で業績が大きく左右される大手石油精製・販売3社。いずれも依存度低減のため再生可能エネルギーや高機能材料など隣接事業の育成を進めている。',
        'order': 1,
    },
    'specialty_lubricant': {
        'title': 'Specialty lubricants — niche moat',
        'title_jp': '特殊潤滑油・ニッチ競争優位型',
        'note': 'Premium lubricant makers whose growth comes from brand strength or dominant niche market share rather than refining volume; margins are structurally protected from commodity-price competition.',
        'note_jp': 'ブランド力または独占的なニッチ市場シェアを背景に、精製規模ではなく高付加価値・プレミアム価格で成長する潤滑油メーカー。コモディティ価格競争とは切り離された構造的な収益性を持つ。',
        'order': 2,
    },
    'diversified_small_energy': {
        'title': 'Diversified small energy — portfolio pivot',
        'title_jp': '多角化小型エネルギー・事業転換型',
        'note': 'A small-cap energy company actively reorienting its revenue mix away from petroleum toward recycling, environmental energy, and other non-oil segments to counteract the secular decline in domestic gasoline demand.',
        'note_jp': '国内ガソリン需要の長期的な減少に対応するため、リサイクルや環境エネルギーなど石油以外のセグメントへ積極的に収益構成を転換している小型エネルギー会社。',
        'order': 3,
    },
    'infra_asphalt': {
        'title': 'Infrastructure asphalt & road paving',
        'title_jp': 'インフラ向けアスファルト・道路舗装型',
        'note': 'A specialist in asphalt products and road-paving construction whose customers are central and local government plus expressway operators; demand is driven by the national resilience program and aging-road renewal rather than consumer fuel demand or crude prices.',
        'note_jp': '主要顧客が国・自治体・NEXCO等の道路関係機関であり、国土強靱化計画や老朽道路の更新需要に支えられたアスファルト製品・道路舗装の専門企業。消費者向け燃料需要や原油価格とは異なる需要ドライバーを持つ。',
        'order': 4,
    },
    # === Marine (2) ===
    'profit_compressed_international': {
        'title': 'International shipping — revenue resilient, profit compressed',
        'title_jp': '国際海運：増収・利益圧縮型',
        'note': 'Both companies operate in international ocean shipping (diversified/tanker) and share the dominant FY3/2026 pattern: revenue held up or grew modestly while operating profit fell sharply, driven by rate-cycle declines and sustained cost inflation. Both trade at sub-1x PBR and lean on long-term contract segments as a buffer.',
        'note_jp': 'いずれも国際海運(総合・タンカー)に属し、FY3/2026の共通パターン「売上維持・利益大幅減」を体現。運賃市況の下落とコスト高止まりが利益を二重に圧迫しており、PBR1倍割れの割安バリュー株として長期契約収益が下値を支える構造が共通している。',
        'order': 1,
    },
    'domestic_modal_shift_rerating': {
        'title': 'Domestic coastal shipping — modal-shift tailwind & re-rating',
        'title_jp': '内航海運：モーダルシフト追い風・資本効率再評価型',
        'note': 'Kuribayashi Shosen operates domestic coastal RoRo routes (Hokkaido–Honshu), largely insulated from international rate cycles. Its story is driven by government-mandated modal-shift policy (truck-to-ship), stable cargo demand, and a stock re-rating triggered by capital-efficiency improvements via policy-stock sales.',
        'note_jp': '栗林商船は北海道-本州間の内航RoRo専業で、国際海運の運賃サイクルの影響を受けにくい。2024年問題を背景にしたモーダルシフト政策の構造的追い風と、政策保有株売却による資本効率改善が株価再評価の主因となっており、国際海運2社とは異なる成長ストーリーを持つ。',
        'order': 2,
    },
    # === Fishery / Agriculture / Forestry (5) ===
    'seafood_majors_aqua_pricing': {
        'title': 'Seafood majors — aquaculture turnaround + record earnings',
        'title_jp': '水産大手 — 養殖回復＋過去最高益',
        'note': 'Nissui and Maruha Nichiro both delivered post-merger or all-time-record operating profits driven by domestic aquaculture turning profitable (yellowtail/mackerel prices up + survival rates better), strong overseas expansion (Chilean salmon, North American processing), and large dividend hikes. Both stocks re-rated as the market recognized durable earnings improvement.',
        'note_jp': 'ニッスイとマルハニチロは、国内養殖の収益化(ブリ・サバ等の単価上昇＋生存率改善)、海外事業の伸長(チリのサーモン養殖、北米加工事業)、そして大幅増配が重なり、統合後または史上最高益を達成。業績の構造的改善が認識され、株価が再評価された。',
        'order': 1,
    },
    'seafood_value_unrecognized': {
        'title': 'Seafood mid-cap — revenue up on price, profit & stock squeezed',
        'title_jp': '水産中堅 — 価格主導の増収、利益・株価は圧迫',
        'note': "Kyokuyo's revenue grew double-digits because seafood market prices rose globally, but volumes declined as consumers cut back on more expensive fish. Operating profit fell and the company cut full-year guidance, sending the stock down 21% from its February 2026 peak. A classic 'revenue up, profit & stock down' pattern in a commodity-sensitive sector.",
        'note_jp': '極洋は世界的な水産物価格上昇で売上が二桁増となったが、消費者の買い控えで販売量が減少し利益率が悪化。営業利益は減益、通期予想を下方修正し、株価は2026年2月の高値から▲21%下落。コモディティ感応セクターでの「増収減益・株価安」の典型パターン。',
        'order': 2,
    },
    'seed_agri_input_recovery': {
        'title': 'Seed & agricultural-input recovery',
        'title_jp': '種苗・農材の回復',
        'note': "Kaneko Seeds and Sakata Seed both posted record operating profits as agricultural materials demand normalized post-COVID, premium-variety mix improved margins, and (for Sakata) overseas vegetable seed sales benefited from climate change driving farmer demand for heat-resistant and disease-resistant varieties. Both have low PBR; one (Sakata) executed a self-tender offer to absorb a major shareholder's sale.",
        'note_jp': 'カネコ種苗とサカタのタネは、農材需要の正常化、高付加価値品種への構成シフト、(サカタは)耐暑性・耐病性品種への海外需要拡大により営業利益が過去最高。両社ともPBR割安で、サカタは大株主の売却を吸収する自社株TOBを実施。',
        'order': 3,
    },
    'domestic_food_shortage_beneficiary': {
        'title': 'Domestic food-shortage beneficiaries',
        'title_jp': '国内食料供給逼迫の恩恵',
        'note': "Hokuto (mushrooms) and Axyz (poultry) both benefited from supply shortfalls elsewhere in the food chain that pushed domestic prices higher. For Hokuto, 2024 vegetable shortages drove shoppers toward stable factory-grown mushrooms; for Axyz, avian flu disruptions abroad raised domestic chicken prices while feed costs fell. Both saw sharp profit jumps, though Hokuto's market viewed FY2025 as one-off while Axyz's stock rose 57% on durable margin expansion.",
        'note_jp': 'ホクト(きのこ)とアクシーズ(鶏肉)は、食料供給網の他部分での供給不足が国内価格を押し上げたことで利益が急増。ホクトは2024年の野菜不足で消費者がきのこに移行し単価上昇。アクシーズは海外鳥インフルエンザで輸入鶏肉が絞られ国内価格が上昇、同時に飼料コストも低下。両社とも利益が急増したが、ホクトはFY2025を一過性と見なされる一方、アクシーズは持続的なマージン拡大として株価が+57%上昇。',
        'order': 4,
    },
    'organic_subscription_microcap_recovery': {
        'title': 'Organic-subscription micro-cap recovery (with caveats)',
        'title_jp': 'オーガニック宅配・マイクロキャップの回復(留保あり)',
        'note': "Akikawa Bokuen swung back to operating profit (¥-3M loss → ¥+143M profit) and ordinary profit rose 261% as price hikes finally flowed through and Chinese subsidiary contribution added scale. However, net profit fell 25% due to a ¥143M impairment write-down on direct-sales and Chinese subsidiary assets, and FY2027 guidance points to profit declining again. Thinly traded ¥4.2B market-cap stock with no analyst coverage.",
        'note_jp': '秋川牧園は値上げ浸透と中国子会社の連結化で営業利益が黒字転換(▲3百万円→＋143百万円)、経常利益が+261%増。しかし純利益は直販事業・中国子会社の資産減損1.43億円により▲25%減。翌期も減益見通し。時価総額42億円の薄商い小型株でアナリストカバレッジなし。',
        'order': 5,
    },
    # === Air Transport (2) ===
    'major_record_fuel_cliff': {
        'title': 'Major carriers: record year, fuel-cost cliff ahead',
        'title_jp': '大手：最高益の翌期に燃料費急騰で大幅減益',
        'note': 'Both JAL and ANA delivered record or all-time-high FY2026 profits on the back of inbound tourism, trans-Pacific business travel, and an air cargo boom, only to guide for roughly 20–43% profit declines in FY2027 due to surging jet fuel costs tied to Middle East tensions. Their stocks rose to 52-week highs on the strong results, then sold off sharply when the cautious forward guidance and analyst downgrades arrived.',
        'note_jp': 'JALとANAはともにインバウンド需要・ビジネス渡航・航空貨物の好調を背景にFY2026で過去最高水準の利益を達成したが、中東情勢悪化に伴う航空燃料費の急騰により翌FY2027の純利益はそれぞれ約20〜43%の大幅減益を予想。好決算と同時に出た保守的なガイダンスと相次ぐアナリスト格下げが株価急落を招いた。',
        'order': 1,
    },
    'mid_tier_structural_squeeze': {
        'title': 'Mid-tier carriers: squeezed margins, structural pressure',
        'title_jp': '中堅航空：構造的コスト圧迫で収益力が低下',
        'note': 'Skymark and Star Flyer both grew revenue but saw net profit fall materially — Skymark trapped between major-carrier price wars and LCC competition that eroded load factors despite fare hikes, and Star Flyer hit by large yen-weakness forex losses on dollar-denominated aircraft leases that wiped out operating gains at the bottom line. Both carry thin operating margins with little buffer against cost shocks, and both have guided for further profit compression in FY2027.',
        'note_jp': 'スカイマークとスターフライヤーはともに増収を達成したものの、最終利益は大幅に減少した。スカイマークは大手のタイムセール攻勢とLCCとの挟み打ちで搭乗率が低下し、スターフライヤーはドル建て機材リースに起因する為替差損が営業利益をほぼ相殺した。両社とも薄い営業利益率でコスト耐性が低く、FY2027もさらなる減益を予想している。',
        'order': 2,
    },
}

_EXTRA_BUCKETS = {
    # R+×S- (foreground) — commodity / cyclical patterns NOT in IT's vocabulary
    'commodity_low_base_caveat': {
        'title': 'Commodity low-base OP recovery — flagged caveat (underlying business still soft)',
        'title_jp': '商品市況低水準からの営業利益回復 — 注意フラグ(原業績はまだ軟調)',
        'note': (
            'In plain terms: operating profit jumped triple-digit percent YoY, but the prior year\'s OP was so small that the growth rate is a math illusion, '
            'not a real business turnaround. Revenue is usually still declining, dividend income is often falling, and the stock is reflecting the underlying weakness.\n\n'
            'Rule used: OP up sharply (often +100% or more) under the sector\'s 営業利益○ filter, BUT revenue is flat-to-down AND there are other warning signs '
            '(net profit declining, dividend cut announced, stock falling).\n\n'
            'Why this matters: under a strict OP-based screen rule, these names qualify as R+ — but treating them as genuine R+ winners would be misleading. '
            'They are listed here for methodological transparency (so the filter applies the same rule to every company), with the caveat that the OP gain is '
            'a base effect rather than a quality signal. The real business is often shrinking; what the OP recovery captures is "less bad than last year."\n\n'
            'What to watch: whether revenue stabilizes in the next 2-3 quarters. If revenue keeps falling while OP keeps growing off a tiny base, the company is '
            'shrinking with margin expansion — typically a value trap. If revenue turns, then OP growth becomes meaningful.'
        ),
        'note_jp': (
            '簡単に言うと:営業利益はYoY 3桁%増だが、前期の営業利益が極めて小さかったための『計算上の幻』で、実際の業績反転ではないケース。'
            '売上はまだ減少傾向、受取配当金など他の利益源も減少していることが多く、株価は原業績の弱さを反映しています。\n\n'
            '使用ルール:営業利益が大幅増(しばしば+100%超)でセクターの営業利益○フィルターには該当するが、売上は横ばい〜減少、'
            '他の警戒シグナル(純利益減益、減配発表、株価下落)が併存しているケース。\n\n'
            'なぜ重要か:厳密にOPベースの判定ルールを適用すれば、これらの銘柄はR+として該当 — しかし真のR+勝者として扱うと誤解を招きます。'
            '方法論の透明性のために掲載(同じルールを全企業に適用)、ただしOP増加は『質的な改善』ではなく『前期が低水準だった結果のベース効果』である点を明記。'
            '実体ビジネスはむしろ縮小しており、OP回復が捉えているのは『去年より傷が浅い』状態であることが多い。\n\n'
            '注視点:今後2-3四半期で売上が安定するか。売上減が続く中でOPだけが小さなベースから伸びるなら、収益体質の縮小型『マージン拡大』 — 典型的なバリュー・トラップ。'
            '売上が反転すれば、OP成長は意味を持ち始めます。'
        ),
        'order': 10,
    },
    'quality_improvement_pivot': {
        'title': 'Quality-improvement pivot — revenue intentionally shrank, profit grew structurally',
        'title_jp': '質的改善ピボット — 売上を意図的に縮小、利益は構造的に成長',
        'note': (
            'In plain terms: revenue went DOWN but operating profit went UP — and this was DELIBERATE. The company exited low-margin contracts, '
            'cleaned up an underperforming segment, raised prices and accepted volume loss, or pruned a problem product line. The result: smaller '
            'top line, healthier margins, cleaner balance sheet.\n\n'
            'Rule used: rev_dir=down, op_dir=up, with a documented intentional cleanup / mix shift driving the gap (not commodity-cycle effects, '
            'not a one-time gain — a structural pivot management owns).\n\n'
            'Why this matters: this is the opposite of "profit_compressed" — instead of revenue masking a profit problem, profit improvement is being '
            'masked by revenue contraction. The market often misreads this as a struggling business when it is actually a healthier one. Once revenue '
            'stabilizes (typically 1-2 years), profit growth from the smaller-but-better base becomes the clear narrative and re-rating tends to follow.\n\n'
            'What to watch: did management explicitly call out the contract cleanup / pricing action in disclosure? Are operating margins continuing to '
            'expand after the cleanup? Has revenue stabilized? If all three, the pivot is real and durable.'
        ),
        'note_jp': (
            '簡単に言うと:売上は減少したが営業利益は増加 — しかも『意図的に』。低採算契約からの撤退、不採算セグメントの整理、値上げと数量減の受け入れ、'
            '問題商品の刈り込み、などの結果。トップラインは縮小するが、マージンは健全化し、バランスシートも改善します。\n\n'
            '使用ルール:売上方向=減、営業利益方向=増、で意図的な整理／構成比シフトがギャップの原因と確認されている(コモディティ・サイクル効果でも、一過性益でもなく、'
            '経営側が能動的に行ったピボット)。\n\n'
            'なぜ重要か:これは「profit_compressed」の正反対 — 売上が利益の問題を隠すのではなく、売上の縮小が利益改善を隠している構造です。'
            '市場は『縮小する苦しいビジネス』と誤読しがちですが、実態は『より健全なビジネス』。売上が安定化(通常1-2年)すれば、'
            '『小さくなったがより質の高い』ベースからの利益成長が明確なストーリーとなり、再評価が続くことが多い。\n\n'
            '注視点:経営は契約整理／価格決定を開示で明示しているか?整理後も営業利益率は拡大し続けているか?売上は安定化したか?'
            'この3つが揃えば、ピボットは本物で持続的。'
        ),
        'order': 11,
    },
    # R+×S+ (secondary) — commodity / cyclical winner
    'commodity_cycle_winner': {
        'title': 'Commodity-cycle winner — revenue moves with prices, OP improves on margin / inventory / mix',
        'title_jp': 'コモディティ・サイクル勝者 — 売上は価格連動、営業利益はマージン／在庫評価益／構成比で改善',
        'note': (
            'In plain terms: revenue may be down or flat because the commodity price (crude oil, gas, container rates, ore prices) declined — but operating profit '
            'improved on factors INSIDE management\'s control: inventory time-lag gains, refining or processing margin expansion, downstream demand strength, '
            'or a richer product mix. The "boring" top line hides a quality earnings story.\n\n'
            'Rule used: commodity-sector company where revenue direction is down-or-flat but OP is up. Sector default filter is 営業利益○ (operating-profit-up) precisely '
            'because top line distortion from commodity prices is structural — OP is the cleaner signal of business performance.\n\n'
            'Why this matters: under a strict revenue rule (売上○), these companies look like value traps. But under the operating-profit rule, they show as '
            'genuine R+ winners with improving business quality. Inventory-effect OP can be cyclical, but margin expansion, mix shift, and downstream pricing power '
            'are more durable. Many of Japan\'s strongest commodity-sector cash returners (refiners, gas utilities, diversified resources) live here.\n\n'
            'What to watch: whether OP growth is driven by transient inventory gains (which reverse as commodity prices stabilize) vs. genuine margin / mix / pricing '
            'improvement. Companies announcing buybacks, dividend hikes, or PBR-improvement plans from this cohort tend to re-rate.'
        ),
        'note_jp': (
            '簡単に言うと:売上はコモディティ価格(原油・ガス・コンテナ運賃・鉱物価格)の下落で減少 or 横ばいに見えるが、営業利益は経営側がコントロールできる要因 — '
            '在庫評価益のタイムラグ効果、精製／加工マージンの拡大、下流需要の強さ、製品構成比の改善 — で改善している。退屈に見えるトップラインの背後に質的な利益ストーリーが隠れている。\n\n'
            '使用ルール:コモディティ・セクター企業で売上方向は減〜横ばいだが営業利益は上昇。'
            'セクターのデフォルトフィルターが営業利益○である理由は構造的 — トップラインがコモディティ価格で歪むため、OPの方が事業パフォーマンスを正しく捉える。\n\n'
            'なぜ重要か:厳密な売上ルール(売上○)で見れば、これらの企業はバリュー・トラップに見える。'
            'しかし営業利益ルールでは『事業の質が改善している真のR+勝者』として表面化。'
            '在庫評価益によるOP増はサイクル的だが、マージン拡大・構成比シフト・下流の価格決定力はより持続的。'
            '日本のコモディティ・セクターで最強のキャッシュ還元企業(精製・ガス公益・多角化資源)の多くがここに属する。\n\n'
            '注視点:OP成長は一過性の在庫評価益主導か(価格安定化で巻き戻り)、それともマージン／構成比／価格決定力の改善主導か。'
            'このコホートで自社株買い・増配・PBR改善計画を発表する企業は再評価されやすい。'
        ),
        'order': 9,
    },
}


def _build_unified_bucket_labels():
    """Combine IT BUCKET_LABELS with the 3 new commodity-pattern buckets."""
    combined = dict(it_mod.BUCKET_LABELS)  # shallow copy of IT's labels
    # Existing legacy bucket keys used by old Petroleum entries — alias them to canonical labels.
    if 'commodity_profit_cycle_winner' not in combined:
        combined['commodity_profit_cycle_winner'] = _EXTRA_BUCKETS['commodity_cycle_winner']
    if 'profit_grew_stock_overhang' not in combined:
        # Map to a custom variant of profit_compressed but for stocks where profit grew yet stock is overhanging
        combined['profit_grew_stock_overhang'] = {
            'title': 'Profit grew but stock has overhang — earnings improving, market still cautious',
            'title_jp': '利益は成長、株価は重し — 業績改善も市場は警戒継続',
            'note': (
                'In plain terms: operating profit grew, the company is in better shape than a year ago, but the stock is flat or has only modestly recovered. '
                'There is a specific overhang the market is digesting — sector-wide concern, regulatory risk, large policy-shareholder selling, key-person succession question, '
                'or governance dispute. Once the overhang lifts, re-rating tends to be sharp.\n\n'
                'Rule used: OP up, but stock performance lagging vs. peers, with an identifiable specific overhang in the price.\n\n'
                'Why this matters: the gap between business reality and stock price is real but is being actively held open by one specific (often visible) reason. '
                'Knowing the reason gives you a roadmap — once the reason resolves (policy holding sold down, regulator clears, succession announced), the rerating happens quickly.\n\n'
                'What to watch: the specific overhang itself. For each name in this bucket, the analyst note should call out exactly which event needs to resolve.'
            ),
            'note_jp': (
                '簡単に言うと:営業利益は成長し、企業は1年前より良い状態だが、株価は横ばい or 控えめな回復にとどまる。'
                '市場が消化中の特定の重し — セクター全体への懸念、規制リスク、政策保有株主の大量売却、後継者問題、ガバナンス紛争など — がある。'
                'この重しが取れれば、再評価は急速に進むことが多い。\n\n'
                '使用ルール:営業利益↑だが株価のパフォーマンスがピア比で劣後、価格に識別可能な特定の重しがある。\n\n'
                'なぜ重要か:ビジネス実態と株価のギャップは本物だが、特定の(しばしば可視化されている)1つの理由で能動的に維持されている。'
                'その理由を知ることが羅針盤になる — 理由が解消(政策保有売り終了、規制が片付く、後継者発表)すれば、再評価は速く進む。\n\n'
                '注視点:特定の重しそれ自体。このバケットの各銘柄について、アナリストノートは『どのイベントが解消する必要があるか』を明示すべき。'
            ),
            'order': 10,
        }
    if 'diversification_winner' not in combined:
        combined['diversification_winner'] = {
            'title': 'Diversification winner — multi-segment small-cap with quality improving across the board',
            'title_jp': '多角化勝者 — マルチセグメントの中小型株、全体的に質的改善',
            'note': (
                'In plain terms: a small-cap company with multiple business segments, where the non-core segments have grown to the point where they support '
                'overall revenue + profit growth — reducing dependence on the legacy core business and improving earnings quality. Often these are former single-segment '
                'companies that diversified intentionally over a decade.\n\n'
                'Rule used: small/mid-cap company in a commodity or cyclical sector with multi-segment business mix and revenue+OP both growing, where the structural '
                'story is "diversification has reached a tipping point."\n\n'
                'Why this matters: institutional investors often under-cover small-caps in commodity sectors. When diversification reaches a meaningful share of revenue '
                'and proves durable, the multiple gap vs. peers narrows. These are slow re-rating stories — quality first, multiple second — but the asymmetry can be large.\n\n'
                'What to watch: segment-mix disclosure (what % of OP comes from non-core), the durability of non-core segment margins, and whether broker coverage starts.'
            ),
            'note_jp': (
                '簡単に言うと:複数の事業セグメントを持つ中小型株で、非中核事業が成長して全体の売上+利益成長を支えるレベルに到達 — '
                '従来のコア事業への依存度が下がり、収益の質も改善。多くは10年単位で意図的に多角化を進めてきた『元・単一事業』企業。\n\n'
                '使用ルール:コモディティ／景気循環セクターの中小型株で、複数セグメントの事業ミックス+売上・営業利益とも成長、'
                '構造ストーリーが『多角化が転換点に達した』ケース。\n\n'
                'なぜ重要か:機関投資家はコモディティ・セクターの中小型株を見落としがち。多角化が売上の意味あるシェアに達し、持続性が証明されると、ピア比でのバリュエーション差が縮まる。'
                '質的改善→倍率拡大の順で進む遅い再評価ストーリーだが、非対称性は大きい。\n\n'
                '注視点:セグメント・ミックスの開示(非中核の利益シェア%)、非中核セグメントのマージン持続性、証券会社のカバレッジ開始有無。'
            ),
            'order': 11,
        }
    # Add new ones
    for k, v in _EXTRA_BUCKETS.items():
        if k not in combined:
            combined[k] = v
    # Add the 17 sector-specific buckets generated from the 2026-06 Sonnet categorization pass
    for k, v in _SECTOR_BUCKETS_2026.items():
        if k not in combined:
            combined[k] = v
    return combined


UNIFIED_BUCKET_LABELS = _build_unified_bucket_labels()


def render_bucket_group(bucket_key: str, cards: list, sector_key: str) -> str:
    """Render a bucket group as a clickable toggle button. Closed by default —
    click summary to reveal the list of company cards inside."""
    label = UNIFIED_BUCKET_LABELS.get(bucket_key, {
        'title': bucket_key.replace('_', ' ').title(),
        'title_jp': bucket_key,
        'note': '',
        'note_jp': '',
        'order': 99,
    })
    title_en = label['title']
    title_jp = label['title_jp']
    note_en = label['note'].replace('\n', '<br><br>')
    note_jp = label['note_jp'].replace('\n', '<br><br>')
    return f'''
    <details class="reason-bucket">
      <summary>
        <span class="bucket-toggle-icon">▸</span>
        <span class="bucket-title" data-title-en="{esc(title_en)}" data-title-jp="{esc(title_jp)}">{esc(title_en)}</span>
        <span class="bucket-count">{len(cards)} names</span>
      </summary>
      <div class="bucket-note" data-note-en="{esc(note_en)}" data-note-jp="{esc(note_jp)}">{esc(label['note'])}</div>
      <div class="bucket-cards">{''.join(cards)}</div>
    </details>
    '''


def group_cards_by_bucket(companies: dict, tab_filter: str, sector_key: str) -> str:
    """Group companies by their `bucket` field. Render each group with title + note + cards.
    tab_filter is 'R+xS-' or 'R+xS+'. Companies without matching tab are skipped."""
    groups = {}  # bucket_key -> list of cards
    for ticker, c in companies.items():
        if c.get('tab') != tab_filter:
            continue
        bucket = c.get('bucket') or 'other_grower'
        card = render_oil_company_card(ticker, c)
        groups.setdefault(bucket, []).append(card)
    if not groups:
        return ''
    # Sort buckets by their 'order' field if available
    sorted_buckets = sorted(groups.keys(), key=lambda k: UNIFIED_BUCKET_LABELS.get(k, {}).get('order', 99))
    return ''.join(render_bucket_group(bk, groups[bk], sector_key) for bk in sorted_buckets)


# ───── Simpler-sector pane content (no buckets — used for Mining, Petroleum, Marine, Land Transport) ─────

def render_oil_company_card(ticker: str, c: dict) -> str:
    name = c.get('name', '?')
    rev_dir = c.get('rev_dir', '?')
    op_dir = c.get('op_dir', '?')
    net_dir = c.get('net_dir', '?')
    rev_pct = c.get('rev_pct', '')
    op_pct = c.get('op_pct', '')
    net_pct = c.get('net_pct', '')
    stock_yoy = c.get('stock_yoy_estimate', '')
    biz = c.get('biz_classification', '')
    qualifies = c.get('filter_qualifies', [])

    gr_jp = c.get('jp_summary', '')
    gr_en = c.get('en_summary', '')
    src = c.get('source_hint', '') or c.get('notes', '')

    dir_emoji = {'up': '↑', 'down': '↓', 'flat': '→'}
    rev_e = dir_emoji.get(rev_dir, '?')
    op_e = dir_emoji.get(op_dir, '?')
    net_e = dir_emoji.get(net_dir, '?')

    # Prefer % string for display; fall back to up/down/flat label if % missing
    rev_display = rev_pct if rev_pct else rev_dir
    op_display = op_pct if op_pct else op_dir
    net_display = net_pct if net_pct else net_dir

    qualifies_attr = ','.join(qualifies)

    return f'''
    <div class="company-row collapsed" data-filters="{esc(qualifies_attr)}" onclick="toggleCompany(this, event)">
      <div class="company-head">
        <span class="ticker">{esc(ticker)}</span>
        <span class="company-name">{esc(name)}</span>
        <span class="expand-icon">▸</span>
      </div>
      <div class="company-data">
        <span class="data-item"><span class="data-label" data-i18n="card.revenue">Revenue:</span> {rev_e} {esc(rev_display)}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.op">Op profit:</span> {op_e} {esc(op_display)}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.net">Net profit:</span> {net_e} {esc(net_display)}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.stock">Stock:</span> <b>{esc(stock_yoy)}</b></span>
      </div>
      <div class="biz-tag">分類: {esc(biz)}</div>
      <div class="company-body">
        <div class="genuine-research">
          <div class="genuine-header">
            <span class="genuine-label" data-i18n="card.genuineLabel">Genuine research (combined-prompt verification)</span>
            <span class="genuine-source" title="{esc(src)}">📚 {esc(src)[:120]}…</span>
          </div>
          <div class="genuine-body" data-genuine-en="{esc_with_bold(gr_en)}" data-genuine-jp="{esc_with_bold(gr_jp)}">{esc_with_bold(gr_en)}</div>
        </div>
      </div>
    </div>
    '''


def _build_simple_sector_pane(sector_key: str, companies: dict, meta: dict, filter_note_i18n_key: str, filter_note_default_text: str) -> str:
    """Generic builder for sectors that use the simpler card layout (no IT-style buckets).

    Used by Mining, Petroleum, Marine, Land Transport.
    Renders: sector-statistics block (transparency) + filter dropdown + 'why' panels + tabs + cards.
    """
    cfg = sector_config[sector_key]

    # Filter options (with data-en/data-jp for language toggle)
    filter_options = []
    for filt in cfg['available_filters']:
        exp = cfg['filter_explanations'].get(filt, {})
        label_en = exp.get('label_en', filt)
        label_jp = exp.get('label_jp', filt)
        selected = ' selected' if filt == cfg['default_filter'] else ''
        filter_options.append(f'<option value="{esc(filt)}" data-en="{esc(label_en)}" data-jp="{esc(label_jp)}"{selected}>{esc(label_en)}</option>')

    # 'Why this filter?' panels (one per filter mode)
    why_panels = []
    for filt, exp in cfg['filter_explanations'].items():
        label_en = exp.get('label_en', filt)
        label_jp = exp.get('label_jp', filt)
        long_en = exp.get('long_en', '')
        long_jp = exp.get('long_jp', '')
        why_panels.append(f'''
        <details class="filter-explanation" data-filter="{esc(filt)}">
          <summary>
            <span data-en="Why use {esc(label_en)}?" data-jp="なぜ「{esc(label_jp)}」を使う?">
              Why use {esc(label_en)}?
            </span>
          </summary>
          <div class="filter-exp-body" data-en="{esc(long_en).replace(chr(10),'<br><br>')}" data-jp="{esc(long_jp).replace(chr(10),'<br><br>')}">
            {esc(long_en).replace(chr(10), '<br><br>')}
          </div>
        </details>
        ''')

    # Company cards grouped by bucket within each tab
    s_minus_count = sum(1 for c in companies.values() if c.get('tab') == 'R+xS-')
    s_plus_count = sum(1 for c in companies.values() if c.get('tab') == 'R+xS+')

    s_minus_inner = group_cards_by_bucket(companies, 'R+xS-', sector_key) or '<p class="empty-note">No companies qualifying as R+×S- under the current filter for this sector this year.</p>'
    s_plus_inner = group_cards_by_bucket(companies, 'R+xS+', sector_key) or '<p class="empty-note">No companies qualifying as R+×S+ under the current filter for this sector this year.</p>'

    # Sector statistics transparency block
    stats = meta.get('sector_statistics', {})
    stats_block = render_sector_stats_block(cfg, stats)

    # Override the cards count variables to use the bucket-aware counts
    s_minus_cards = [None] * s_minus_count
    s_plus_cards = [None] * s_plus_count

    return f'''
    <div class="sector-pane" data-sector="{esc(sector_key)}" style="display: none;">

      {stats_block}

      <div class="filter-row">
        <label data-i18n="filter.label">Filter mode:</label>
        <select class="sector-filter" data-sector="{esc(sector_key)}">
          {''.join(filter_options)}
        </select>
        <div class="filter-note" data-i18n="{esc(filter_note_i18n_key)}">
          {esc(filter_note_default_text)}
        </div>
      </div>

      <div class="filter-explanations-block">
        <h3 data-i18n="explanations.heading">Why these filter options?</h3>
        {''.join(why_panels)}
      </div>

      <div class="tabs" role="tablist">
        <button class="tab s-minus active" data-tab="s-minus-{esc(sector_key)}" role="tab">
          <span data-i18n="tab.sMinus">R+ × S- — Revenue (or profit) up, stock down</span>
          <span class="tab-count">{len(s_minus_cards)}</span>
        </button>
        <button class="tab s-plus" data-tab="s-plus-{esc(sector_key)}" role="tab">
          <span data-i18n="tab.sPlus">R+ × S+ — Revenue (or profit) up, stock up</span>
          <span class="tab-count">{len(s_plus_cards)}</span>
        </button>
      </div>

      <div class="tab-content tab-s-minus-{esc(sector_key)}" data-active="true">
        {s_minus_inner}
      </div>
      <div class="tab-content tab-s-plus-{esc(sector_key)}" data-active="false">
        {s_plus_inner}
      </div>
    </div>
    '''


def build_mining_sector_pane() -> str:
    """Mining (鉱業) — TOPIX-33. INPEX + JAPEX only. 0 R+ this year (both R-)."""
    return _build_simple_sector_pane(
        'Mining',
        mining_companies,
        mining_meta,
        'filter.note.Mining',
        'For mining (oil & gas exploration), operating-profit-up best captures business performance — revenue moves with crude oil & gas prices.'
    )


def build_petroleum_sector_pane() -> str:
    """Petroleum / Oil & Coal Products (石油・石炭製品) — TOPIX-33. Refiners + lubricants."""
    return _build_simple_sector_pane(
        'Petroleum',
        petroleum_companies,
        petroleum_meta,
        'filter.note.Petroleum',
        'For petroleum refining, operating-profit-up captures business performance better than revenue-up because revenue moves with crude oil prices.'
    )


def build_air_transport_sector_pane() -> str:
    """Air Transportation (空運業) — TOPIX-33. JAL + ANA + Skymark + Star Flyer (4 listed)."""
    return _build_simple_sector_pane(
        'AirTransport',
        air_companies,
        air_meta,
        'filter.note.AirTransport',
        'For air transportation, revenue-up captures business quality — passenger volume × fare + cargo. FY3/2026 all 4 listed carriers were R+; FY3/2027 profit guidance weak across the sector on fuel-cost shock.'
    )


def build_agri_fishery_sector_pane() -> str:
    """Fishery, Agriculture & Forestry (水産・農林業) — TOPIX-33. 8 covered: seafood majors, seeds, mushrooms, poultry, organic."""
    return _build_simple_sector_pane(
        'AgriFishery',
        agri_companies,
        agri_meta,
        'filter.note.AgriFishery',
        'For Fishery / Agriculture / Forestry, revenue-up captures real business growth — volume × price for each segment. All 8 covered companies were R+ in the latest FY.'
    )


# ───── Marine sector pane content ─────

def render_marine_company_card(ticker: str, c: dict) -> str:
    """Same card layout as oil — marine uses the same simpler structure (no buckets)."""
    return render_oil_company_card(ticker, c)


def build_marine_sector_pane() -> str:
    """Build the marine sector pane with filter dropdown + why panel + non-qualifying-majors note."""
    marine_cfg = sector_config['Marine']

    # Filter options
    filter_options = []
    for filt in marine_cfg['available_filters']:
        exp = marine_cfg['filter_explanations'].get(filt, {})
        label_en = exp.get('label_en', filt)
        label_jp = exp.get('label_jp', filt)
        selected = ' selected' if filt == marine_cfg['default_filter'] else ''
        filter_options.append(f'<option value="{esc(filt)}" data-en="{esc(label_en)}" data-jp="{esc(label_jp)}"{selected}>{esc(label_en)}</option>')

    # Why panels
    why_panels = []
    for filt, exp in marine_cfg['filter_explanations'].items():
        label_en = exp.get('label_en', filt)
        label_jp = exp.get('label_jp', filt)
        long_en = exp.get('long_en', '')
        long_jp = exp.get('long_jp', '')
        why_panels.append(f'''
        <details class="filter-explanation" data-filter="{esc(filt)}">
          <summary>
            <span data-en="Why use {esc(label_en)}?" data-jp="なぜ「{esc(label_jp)}」を使う?">
              Why use {esc(label_en)}?
            </span>
          </summary>
          <div class="filter-exp-body" data-en="{esc(long_en).replace(chr(10),'<br><br>')}" data-jp="{esc(long_jp).replace(chr(10),'<br><br>')}">
            {esc(long_en).replace(chr(10), '<br><br>')}
          </div>
        </details>
        ''')

    # Cards grouped by bucket within each tab
    s_minus_count = sum(1 for c in marine_companies.values() if c.get('tab') == 'R+xS-')
    s_plus_count = sum(1 for c in marine_companies.values() if c.get('tab') == 'R+xS+')
    s_minus_inner = group_cards_by_bucket(marine_companies, 'R+xS-', 'Marine') or '<p class="empty-note">No companies in this tab under the current filter.</p>'
    s_plus_inner = group_cards_by_bucket(marine_companies, 'R+xS+', 'Marine') or '<p class="empty-note">No companies in this tab under the current filter.</p>'
    s_minus_cards = [None] * s_minus_count
    s_plus_cards = [None] * s_plus_count

    # Non-qualifying majors note — transparency about what's excluded
    non_qual = marine_meta.get('non_qualifying_majors', {})
    non_qual_items_en = []
    non_qual_items_jp = []
    for tk, note in non_qual.items():
        non_qual_items_en.append(f'<li><b>{esc(tk)}</b>: {esc(note)}</li>')
        # Same for JP — note text is mixed JP/EN; render as-is
        non_qual_items_jp.append(f'<li><b>{esc(tk)}</b>: {esc(note)}</li>')

    non_qual_block = ''
    if non_qual_items_en:
        non_qual_block = f'''
        <details class="non-qualifying-block">
          <summary>
            <span data-en="Non-qualifying marine majors (R-) — transparency note" data-jp="該当しない海運大手(R-) — 透明性ノート">
              Non-qualifying marine majors (R-) — transparency note
            </span>
          </summary>
          <div class="non-qual-body">
            <p data-i18n="marine.nonqual.intro">The following marine sector majors are R- (revenue down) under all filter modes this year, hence excluded from the R+ cards above. Listed here for transparency:</p>
            <ul>
              {''.join(non_qual_items_en)}
            </ul>
          </div>
        </details>
        '''

    # Sector statistics transparency block
    marine_stats = marine_meta.get('sector_statistics', {})
    stats_block = render_sector_stats_block(marine_cfg, marine_stats)

    return f'''
    <div class="sector-pane" data-sector="Marine" style="display: none;">

      {stats_block}

      <div class="filter-row">
        <label data-i18n="filter.label">Filter mode:</label>
        <select class="sector-filter" data-sector="Marine">
          {''.join(filter_options)}
        </select>
        <div class="filter-note" data-i18n="filter.note.Marine">
          For marine FY3/2026 — container rate fall caused all majors' operating profit to decline. The active default is 売上○ (only MOL qualifies). Would normally default to 営業利益○ when container rates recover.
        </div>
      </div>

      <div class="filter-explanations-block">
        <h3 data-i18n="explanations.heading">Why these filter options?</h3>
        {''.join(why_panels)}
      </div>

      {non_qual_block}

      <div class="tabs" role="tablist">
        <button class="tab s-minus active" data-tab="s-minus-Marine" role="tab">
          <span data-i18n="tab.sMinus">R+ × S- — Revenue (or profit) up, stock down</span>
          <span class="tab-count">{len(s_minus_cards)}</span>
        </button>
        <button class="tab s-plus" data-tab="s-plus-Marine" role="tab">
          <span data-i18n="tab.sPlus">R+ × S+ — Revenue (or profit) up, stock up</span>
          <span class="tab-count">{len(s_plus_cards)}</span>
        </button>
      </div>

      <div class="tab-content tab-s-minus-Marine" data-active="true">
        {s_minus_inner}
      </div>
      <div class="tab-content tab-s-plus-Marine" data-active="false">
        {s_plus_inner}
      </div>
    </div>
    '''


# ───── Land Transport sector pane content ─────

def render_land_company_card(ticker: str, c: dict) -> str:
    """Same simpler card layout as marine/oil — no buckets."""
    return render_oil_company_card(ticker, c)


def build_land_transport_sector_pane() -> str:
    """Build the Land Transport pane — 売上○ only filter (revenue-driven sector)."""
    land_cfg = sector_config['LandTransport']

    # Filter options (just one for land transport)
    filter_options = []
    for filt in land_cfg['available_filters']:
        exp = land_cfg['filter_explanations'].get(filt, {})
        label_en = exp.get('label_en', filt)
        label_jp = exp.get('label_jp', filt)
        selected = ' selected' if filt == land_cfg['default_filter'] else ''
        filter_options.append(f'<option value="{esc(filt)}" data-en="{esc(label_en)}" data-jp="{esc(label_jp)}"{selected}>{esc(label_en)}</option>')

    # Why panel
    why_panels = []
    for filt, exp in land_cfg['filter_explanations'].items():
        label_en = exp.get('label_en', filt)
        label_jp = exp.get('label_jp', filt)
        long_en = exp.get('long_en', '')
        long_jp = exp.get('long_jp', '')
        why_panels.append(f'''
        <details class="filter-explanation" data-filter="{esc(filt)}">
          <summary>
            <span data-en="Why use {esc(label_en)}?" data-jp="なぜ「{esc(label_jp)}」を使う?">
              Why use {esc(label_en)}?
            </span>
          </summary>
          <div class="filter-exp-body" data-en="{esc(long_en).replace(chr(10),'<br><br>')}" data-jp="{esc(long_jp).replace(chr(10),'<br><br>')}">
            {esc(long_en).replace(chr(10), '<br><br>')}
          </div>
        </details>
        ''')

    # Cards grouped by bucket within each tab
    s_minus_count = sum(1 for c in land_companies.values() if c.get('tab') == 'R+xS-')
    s_plus_count = sum(1 for c in land_companies.values() if c.get('tab') == 'R+xS+')
    s_minus_inner = group_cards_by_bucket(land_companies, 'R+xS-', 'LandTransport') or '<p class="empty-note">No companies in this tab under the current filter.</p>'
    s_plus_inner = group_cards_by_bucket(land_companies, 'R+xS+', 'LandTransport') or '<p class="empty-note">No companies in this tab under the current filter.</p>'
    s_minus_cards = [None] * s_minus_count
    s_plus_cards = [None] * s_plus_count

    # Sector statistics transparency block
    land_stats = land_meta.get('sector_statistics', {})
    stats_block = render_sector_stats_block(land_cfg, land_stats)

    return f'''
    <div class="sector-pane" data-sector="LandTransport" style="display: none;">

      {stats_block}

      <div class="filter-row">
        <label data-i18n="filter.label">Filter mode:</label>
        <select class="sector-filter" data-sector="LandTransport">
          {''.join(filter_options)}
        </select>
        <div class="filter-note" data-i18n="filter.note.LandTransport">
          For Land Transportation, revenue captures real business quality — fare/parcel volume growth. Strong FY3/2026: JR Big 3 + private railways + logistics all growing.
        </div>
      </div>

      <div class="filter-explanations-block">
        <h3 data-i18n="explanations.heading">Why these filter options?</h3>
        {''.join(why_panels)}
      </div>

      <div class="tabs" role="tablist">
        <button class="tab s-minus active" data-tab="s-minus-LandTransport" role="tab">
          <span data-i18n="tab.sMinus">R+ × S- — Revenue up, stock down</span>
          <span class="tab-count">{len(s_minus_cards)}</span>
        </button>
        <button class="tab s-plus" data-tab="s-plus-LandTransport" role="tab">
          <span data-i18n="tab.sPlus">R+ × S+ — Revenue up, stock up</span>
          <span class="tab-count">{len(s_plus_cards)}</span>
        </button>
      </div>

      <div class="tab-content tab-s-minus-LandTransport" data-active="true">
        {s_minus_inner}
      </div>
      <div class="tab-content tab-s-plus-LandTransport" data-active="false">
        {s_plus_inner}
      </div>
    </div>
    '''


# ───── Unified CSS + JS ─────

UNIFIED_STYLES = '''
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Helvetica, Arial, "Hiragino Sans", "Meiryo", sans-serif; margin: 0; padding: 0; color: #1a1a1a; background: #f7f7f5; line-height: 1.55; }
.container { max-width: 1080px; margin: 0 auto; padding: 24px; }
header.page-header { background: #fff; border-bottom: 1px solid #e0e0e0; padding: 22px 24px; position: relative; }
.page-header h1 { margin: 0 0 4px; font-size: 20px; font-weight: 700; }
.page-header .subtitle { color: #555; font-size: 13px; margin: 4px 0 0; }

/* Top-level controls */
.top-controls { display: flex; gap: 16px; align-items: center; margin-top: 12px; flex-wrap: wrap; }
.top-controls label { font-size: 13px; font-weight: 600; color: #333; }
.top-controls select { font-size: 13px; padding: 5px 10px; border: 1px solid #ccc; border-radius: 4px; background: #fff; }

/* Filter row */
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
.tab { padding: 10px 18px; cursor: pointer; font-size: 14px; font-weight: 600; color: #888; border-bottom: 3px solid transparent; margin-bottom: -2px; background: none; border-left: none; border-right: none; border-top: none; }
.tab.active { color: #1f7a4a; border-bottom-color: #1f7a4a; }
.tab.s-minus.active { color: #1f7a4a; border-bottom-color: #1f7a4a; }
.tab-count { background: #f0f0f0; border-radius: 9px; padding: 1px 8px; font-size: 11px; margin-left: 6px; color: #555; }
.tab-focus-note { background: #d4f7e0; color: #1f7a4a; border-radius: 3px; padding: 1px 6px; font-size: 11px; margin-left: 6px; font-weight: 700; }
.tab-content { display: none; padding: 18px 0; }
.tab-content[data-active="true"] { display: block; }

/* Buckets — clickable toggle buttons. Closed by default; click to expand to show deep
   explanation + the list of company cards inside. */
.reason-bucket { background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px 16px; margin: 12px 0; transition: border-color 0.15s, box-shadow 0.15s; }
.reason-bucket:hover { border-color: #1f7a4a; box-shadow: 0 1px 4px rgba(31, 122, 74, 0.08); }
.reason-bucket > summary { cursor: pointer; font-size: 15px; font-weight: 700; color: #1a1a1a; display: flex; align-items: center; gap: 10px; padding: 6px 0; list-style: none; user-select: none; }
.reason-bucket > summary::-webkit-details-marker { display: none; }
.reason-bucket > summary::marker { display: none; }
.bucket-toggle-icon { font-size: 12px; color: #1f7a4a; transition: transform 0.15s; display: inline-block; min-width: 14px; }
.reason-bucket[open] > summary .bucket-toggle-icon { transform: rotate(90deg); }
.bucket-title { color: #1f7a4a; flex: 1; }
.reason-bucket:hover .bucket-title { color: #155a35; }
.bucket-count { background: #f0f0f0; border-radius: 9px; padding: 1px 8px; font-size: 11px; color: #555; }
.bucket-note { font-size: 13px; color: #555; padding: 10px 8px 12px 8px; line-height: 1.65; background: #fafaf5; border-left: 3px solid #d4a017; margin: 8px 0 12px; border-radius: 3px; white-space: pre-wrap; }
.bucket-cards { padding-top: 4px; }

/* Company cards — WHOLE card is click-to-toggle when collapsed */
.company-row { background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px 18px; margin: 10px 0; transition: background 0.15s, border-color 0.15s; cursor: pointer; }
.company-row:hover { background: #f0f8f3; border-color: #1f7a4a; }
/* When expanded, only the head/data area shows the pointer feel; the body is
   read-only content where text selection is fine */
.company-row:not(.collapsed) { cursor: default; }
.company-row:not(.collapsed) .company-head,
.company-row:not(.collapsed) .company-data,
.company-row:not(.collapsed) .biz-tag { cursor: pointer; }
.company-row:not(.collapsed) .company-body { cursor: text; }
.company-head { display: flex; align-items: baseline; gap: 12px; user-select: none; }
.expand-icon { font-size: 12px; color: #999; transition: transform 0.15s; margin-left: auto; }
.company-row:not(.collapsed) .expand-icon { transform: rotate(90deg); }
.ticker { font-family: monospace; font-size: 13px; color: #777; }
.company-name { font-size: 16px; font-weight: 700; }
.company-meta { display: inline-flex; gap: 6px; margin-left: 6px; }
.badge { font-size: 10.5px; padding: 1px 6px; border-radius: 3px; background: #ececec; color: #555; font-weight: 600; }
.badge.sub { background: #e6f0f8; color: #2f5377; }
.badge.size { background: #f8eee6; color: #774b2f; }
.company-data { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12.5px; color: #555; margin: 8px 0; }
.data-label { color: #888; font-weight: 600; }
.biz-tag { font-size: 11.5px; color: #777; margin: 6px 0 8px; font-style: italic; }

/* Hidden by default — shown when company is expanded */
.company-row.collapsed .company-body { display: none; }
.company-body { padding-top: 10px; }
.company-body > * { margin-top: 8px; }

/* Genuine research green block */
.genuine-research { background: #f0f8f3; border-left: 4px solid #1f7a4a; padding: 12px 14px; border-radius: 4px; }
.genuine-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; font-size: 11.5px; color: #555; flex-wrap: wrap; gap: 8px; }
.genuine-label { font-weight: 700; color: #1f7a4a; }
.genuine-source { font-size: 10.5px; color: #999; }
.genuine-body { font-size: 13px; line-height: 1.7; color: #1a1a1a; white-space: pre-wrap; }
.genuine-body b { color: #1f7a4a; }

/* Pattern + source prose collapsibles */
.pattern-collapse, .source-prose { margin-top: 8px; }
.pattern-collapse > summary, .source-prose > summary {
  cursor: pointer; font-size: 11px; font-weight: 600; color: #555; padding: 4px 8px;
  background: #ececec; border-radius: 3px; display: inline-block;
}
.reason-text { padding: 8px; font-size: 12px; color: #444; line-height: 1.7; }
.reason-pattern-text b { color: #1f7a4a; font-weight: 700; }
.source-prose-body { padding: 10px; font-size: 12px; color: #555; line-height: 1.7; background: #fafafa; border-radius: 3px; }
.source-thin, .genuine-missing { padding: 8px; font-size: 12px; color: #c2541b; background: #fdf6f0; border-radius: 3px; }

.empty-note { padding: 20px; color: #888; font-style: italic; }

/* Non-qualifying majors transparency block (marine, etc.) */
.non-qualifying-block { background: #fafafa; border-left: 4px solid #aaa; padding: 12px 16px; margin: 12px 0; border-radius: 4px; }
.non-qualifying-block > summary { cursor: pointer; font-size: 13px; font-weight: 600; color: #555; padding: 4px 0; }
.non-qual-body { font-size: 12.5px; color: #555; padding: 10px 8px 4px 8px; line-height: 1.7; }
.non-qual-body ul { padding-left: 20px; margin: 8px 0; }
.non-qual-body li { margin-bottom: 6px; }

/* Sector statistics transparency block (top of each sector pane) */
.sector-stats-block {
  background: #fff;
  border: 1px solid #d8d8d8;
  border-left: 4px solid #2f5377;
  border-radius: 6px;
  padding: 16px 20px;
  margin: 16px 0 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.sector-stats-block .stats-header {
  font-size: 12px;
  font-weight: 700;
  color: #2f5377;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ececec;
}
.sector-stats-block .stats-counts {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 10px;
}
.sector-stats-block .stat-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 5px;
  border: 1px solid #ececec;
}
.sector-stats-block .stat-cell.stat-qualifying { background: #f0f8f3; border-color: #d2e9dc; }
.sector-stats-block .stat-cell.stat-excluded { background: #fdf4f4; border-color: #ecd5d5; }
.sector-stats-block .stat-cell.stat-delisted { background: #f5f5f5; border-color: #e0e0e0; }
.sector-stats-block .stat-cell.stat-delisted .stat-value { color: #999; }
.sector-stats-block .stats-math-note {
  font-size: 11px;
  color: #666;
  font-style: italic;
  margin: 8px 0 4px;
  padding: 6px 10px;
  background: #f8f9fa;
  border-left: 3px solid #c0c0c0;
  border-radius: 3px;
}
.sector-stats-block .stat-label {
  font-size: 11px;
  color: #777;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.sector-stats-block .stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a1a;
  line-height: 1.2;
}
.sector-stats-block .stat-qualifying .stat-value { color: #1f7a4a; }
.sector-stats-block .stat-excluded .stat-value { color: #888; }
.sector-stats-block .excluded-list {
  margin-top: 8px;
  border-top: 1px solid #ececec;
  padding-top: 10px;
}
.sector-stats-block .excluded-list > summary {
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  color: #555;
  padding: 4px 0;
}
.sector-stats-block .excluded-list > summary:hover { color: #1a1a1a; }
.sector-stats-block .excl-items {
  list-style: none;
  padding: 8px 0 0 0;
  margin: 0;
}
.sector-stats-block .excl-items li {
  padding: 6px 10px;
  font-size: 12.5px;
  color: #555;
  border-left: 2px solid #d8d8d8;
  margin: 4px 0;
  background: #fafafa;
  border-radius: 0 3px 3px 0;
}
.sector-stats-block .excl-items li b { color: #1a1a1a; font-family: monospace; margin-right: 4px; }
.sector-stats-block .excl-reason { color: #777; font-style: italic; }
.sector-stats-block .excl-smaller { font-size: 11.5px; color: #888; padding: 8px 0 0; margin: 6px 0 0; border-top: 1px dashed #e0e0e0; font-style: italic; }
@media (max-width: 720px) {
  .sector-stats-block .stats-counts { grid-template-columns: repeat(2, 1fr); }
}

/* Language toggle */
.lang-toggle { position: absolute; top: 22px; right: 22px; display: flex; gap: 4px; }
.lang-btn { padding: 4px 10px; font-size: 12px; border: 1px solid #ccc; background: #fff; cursor: pointer; border-radius: 3px; }
.lang-btn.active { background: #1f7a4a; color: #fff; border-color: #1f7a4a; }

/* ── Methodology pane ── */
.methodology-pane { max-width: 980px; margin: 0 auto; padding: 8px 4px; }
.methodology-intro h2 { font-size: 22px; margin: 4px 0 12px 0; color: #1f3a5c; }
.meth-lede { font-size: 14.5px; line-height: 1.65; color: #334; background: #f6f8fc; border-left: 4px solid #3a6db0; padding: 14px 18px; border-radius: 4px; margin: 0 0 22px 0; }
.meth-section { background: #fff; border: 1px solid #d8deea; border-radius: 6px; margin-bottom: 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
.meth-section > summary { padding: 14px 20px; font-size: 15.5px; font-weight: 600; color: #1f3a5c; cursor: pointer; list-style: none; user-select: none; }
.meth-section > summary::-webkit-details-marker { display: none; }
.meth-section > summary::before { content: '▸ '; color: #6a7a95; margin-right: 4px; transition: transform 0.15s; display: inline-block; }
.meth-section[open] > summary::before { content: '▾ '; }
.meth-section > summary:hover { background: #f3f6fb; }
.meth-section > *:not(summary) { padding: 0 22px 18px 22px; }
.meth-diagram { font-family: 'Cascadia Mono', 'Consolas', 'Courier New', monospace; font-size: 12px; line-height: 1.4; background: #fafbfd; border: 1px solid #e8ecf3; border-radius: 4px; padding: 14px 16px; overflow-x: auto; color: #2a3a52; margin: 8px 0; }
.meth-prompt { font-family: 'Cascadia Mono', 'Consolas', 'Courier New', monospace; font-size: 12.5px; line-height: 1.55; background: #fef9e7; border: 1px solid #e8dca0; border-radius: 4px; padding: 14px 18px; overflow-x: auto; white-space: pre-wrap; color: #2b2818; margin: 6px 0; }
/* Show only the prompt matching the current page language */
html[lang="en"] .meth-prompt[data-lang="jp"] { display: none; }
html[lang="jp"] .meth-prompt[data-lang="en"] { display: none; }
.meth-output-schema { font-family: 'Cascadia Mono', 'Consolas', 'Courier New', monospace; font-size: 12.5px; line-height: 1.55; background: #f0f7ee; border: 1px solid #c5d9bf; border-radius: 4px; padding: 14px 18px; overflow-x: auto; color: #1f3a1f; margin: 6px 0; }
.meth-explain { font-size: 14px; line-height: 1.65; color: #334; }
.meth-explain p { margin: 8px 0 12px 0; }
.meth-explain code { background: #f0f3f8; padding: 1px 5px; border-radius: 3px; font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 12.5px; color: #444; }
.meth-steps, .meth-controls, .meth-cost { font-size: 14px; line-height: 1.7; color: #334; margin: 4px 0 0 8px; padding-left: 22px; }
.meth-steps li, .meth-controls li, .meth-cost li { margin-bottom: 8px; }
.meth-controls li { padding-left: 4px; }

'''

UNIFIED_JS = '''
const I18N = {
  en: {
    'page.title': 'R+ Classification View — Multi-Sector (FY3/2026)',
    'page.subtitle': '2026-06-05 · 5 TOPIX-33 sectors · per-sector filter + transparency block',
    'sector.label': 'Sector:',
    'filter.label': 'Filter mode:',
    'filter.note.IT': 'For IT sector, revenue growth = business growth. No alternative filter needed.',
    'filter.note.LandTransport': 'For Land Transportation, revenue captures real business quality — fare/parcel volume growth. Strong FY3/2026: JR Big 3 + private railways + logistics all growing.',
    'filter.note.Mining': 'For mining (oil & gas exploration), operating-profit-up best captures business performance — revenue moves with crude oil & gas prices.',
    'filter.note.Petroleum': 'For petroleum refining, operating-profit-up captures business performance better than revenue-up because revenue moves with crude oil prices.',
    'filter.note.Marine': 'For marine FY3/2026 — container rate fall caused all majors\\' operating profit to decline. The active default is 売上○ (only MOL qualifies). Would normally default to 営業利益○ when container rates recover.',
    'marine.nonqual.intro': 'The following marine sector majors are R- (revenue down) under all filter modes this year, hence excluded from the R+ cards above. Listed here for transparency:',
    'explanations.heading': 'Why these filter options?',
    'tab.sMinus': 'R+ × S- — Revenue (or profit) up, stock down',
    'tab.sPlus': 'R+ × S+ — Revenue (or profit) up, stock up',
    'tab.focus': '本命 / Focus',
    'card.revenue': 'Revenue:',
    'card.op': 'Op profit:',
    'card.net': 'Net profit:',
    'card.stock': 'Stock:',
    'card.stockYoy': 'Stock 2025 YoY:',
    'card.genuineLabel': 'Genuine research (combined-prompt verification)',
    'card.patternLabel': 'Pattern (bucket-templated):',
    'card.sourceLabel': 'Source prose (fixture rawExplanation)',
    'card.sourceThin': '⚠ Source prose for this company-year is thin.',
    'card.genuineMissing': '⚠ Per-company web-search research not yet completed for this ticker.'
  },
  jp: {
    'page.title': 'R+分類ビュー — マルチセクター (2026年3月期)',
    'page.subtitle': '2026-06-05 · TOPIX-33の5セクター · セクター別フィルター + 透明性ブロック',
    'sector.label': 'セクター:',
    'filter.label': 'フィルターモード:',
    'filter.note.IT': '情報・通信業セクターでは売上成長＝事業成長。代替フィルターは不要。',
    'filter.note.LandTransport': '陸運業セクターでは売上が事業の質を捉える — 運賃・宅配個数の成長。2026年3月期は強い年:JR Big 3+大手私鉄+物流が全て成長。',
    'filter.note.Mining': '鉱業(石油・ガス開発)では、売上は原油・ガス価格と連動して動くため、営業利益ベースの方が事業パフォーマンスをより良く捉えます。',
    'filter.note.Petroleum': '石油・石炭製品(石油精製)では、売上は原油価格と連動して動くため、営業利益ベースの方が事業パフォーマンスをより良く捉えます。',
    'filter.note.Marine': '2026年3月期の海運セクター — コンテナ運賃下落で大手全社が営業利益減益。アクティブなデフォルトは『売上○』(該当はMOLのみ)。コンテナ運賃回復時は通常『営業利益○』がデフォルト。',
    'marine.nonqual.intro': '以下の海運大手は今年は全フィルターモードでR-(売上減)であり、上のR+カードからは除外されています。透明性のためにここに記載:',
    'explanations.heading': 'なぜこれらのフィルターオプションなのか?',
    'tab.sMinus': 'R+ × S- — 売上(または利益)↑、株価↓',
    'tab.sPlus': 'R+ × S+ — 売上(または利益)↑、株価↑',
    'tab.focus': '本命 / 注力',
    'card.revenue': '売上:',
    'card.op': '営業利益:',
    'card.net': '純利益:',
    'card.stock': '株価:',
    'card.stockYoy': '株価2025年前年比:',
    'card.genuineLabel': '本物の調査 (combined-prompt verification)',
    'card.patternLabel': 'パターン (バケット・テンプレート):',
    'card.sourceLabel': '元の説明文 (fixture rawExplanation)',
    'card.sourceThin': '⚠ この企業年度の元説明文は薄いです。',
    'card.genuineMissing': '⚠ この銘柄の企業別Web検索調査は未完了。'
  }
};
let LANG = 'en';
let CURRENT_SECTOR = 'IT';
let CURRENT_FILTER = {IT: '売上○', LandTransport: '売上○', Mining: '営業利益○', Petroleum: '営業利益○', Marine: '売上○'};

function applyI18n() {
  const dict = I18N[LANG];
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key] != null) el.textContent = dict[key];
  });
  // Filter explanation labels and bodies (dual-language data attrs)
  document.querySelectorAll('.filter-explanation > summary > span[data-en]').forEach(el => {
    const v = el.getAttribute('data-' + LANG);
    if (v != null) el.textContent = v;
  });
  document.querySelectorAll('.filter-exp-body[data-en]').forEach(el => {
    const v = el.getAttribute('data-' + LANG);
    if (v != null) el.innerHTML = v;
  });
  // Bucket title + note
  document.querySelectorAll('.bucket-title[data-title-en]').forEach(el => {
    const v = el.getAttribute('data-title-' + LANG);
    if (v != null) el.textContent = v;
  });
  document.querySelectorAll('.bucket-note[data-note-en]').forEach(el => {
    const v = el.getAttribute('data-note-' + LANG);
    if (v != null) el.textContent = v;
  });
  // Pattern text
  document.querySelectorAll('.reason-pattern-text[data-pattern-en]').forEach(el => {
    const v = el.getAttribute('data-pattern-' + LANG);
    if (v != null) el.innerHTML = v;
  });
  // Genuine research body
  document.querySelectorAll('.genuine-body[data-genuine-en]').forEach(el => {
    const v = el.getAttribute('data-genuine-' + LANG);
    if (v != null) el.innerHTML = v;
  });
  // Source prose body
  document.querySelectorAll('.source-prose-body[data-source-en]').forEach(el => {
    const v = el.getAttribute('data-source-' + LANG);
    if (v != null) el.innerHTML = v;
  });
  // Select <option> elements with data-en/data-jp — translate display text
  document.querySelectorAll('select option[data-en]').forEach(opt => {
    const v = opt.getAttribute('data-' + LANG);
    if (v != null) opt.textContent = v;
  });
  // Sector-statistics block: TOPIX name + 4 stat labels + excluded-list summary + math note
  document.querySelectorAll('.stats-topix-name[data-en], .stat-label[data-en], .excluded-list > summary > span[data-en], .stats-math-note[data-en]').forEach(el => {
    const v = el.getAttribute('data-' + LANG);
    if (v != null) el.textContent = v;
  });
  // Methodology pane: lede paragraph (innerHTML supports inline tags) + section summaries + step lists
  document.querySelectorAll('.methodology-pane h2[data-en], .meth-section > summary > span[data-en]').forEach(el => {
    const v = el.getAttribute('data-' + LANG);
    if (v != null) el.textContent = v;
  });
  document.querySelectorAll('.meth-lede[data-en], .meth-explain p[data-en], .meth-steps li[data-en], .meth-controls li[data-en], .meth-cost li[data-en]').forEach(el => {
    const v = el.getAttribute('data-' + LANG);
    if (v != null) el.innerHTML = v;
  });
  document.documentElement.setAttribute('lang', LANG);
}

function setLang(lang) {
  LANG = lang;
  document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
  applyI18n();
}

function setSector(sector) {
  CURRENT_SECTOR = sector;
  document.querySelectorAll('.sector-pane').forEach(pane => {
    pane.style.display = (pane.getAttribute('data-sector') === sector) ? 'block' : 'none';
  });
}

function applyFilter(sector, filter) {
  CURRENT_FILTER[sector] = filter;
  const pane = document.querySelector('.sector-pane[data-sector="' + sector + '"]');
  if (!pane) return;
  // For oil sector cards, filter by data-filters attribute. For IT, all visible (no filter).
  // If data-filters is empty/missing, treat the card as qualifying for all filters
  // (the new lighter-prompt entries don't always emit filter_qualifies).
  pane.querySelectorAll('.company-row[data-filters]').forEach(row => {
    const raw = row.getAttribute('data-filters') || '';
    if (!raw) { row.style.display = ''; return; }
    const quals = raw.split(',');
    const visible = (filter === '両方') ? quals.length > 0 : quals.includes(filter);
    row.style.display = visible ? '' : 'none';
  });
}

function showTabInSector(tabName) {
  // tabName looks like 's-minus-IT' or 's-plus-Oil'
  const sector = tabName.split('-').pop();
  const pane = document.querySelector('.sector-pane[data-sector="' + sector + '"]');
  if (!pane) return;
  pane.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  pane.querySelectorAll('.tab-content').forEach(c => c.setAttribute('data-active', 'false'));
  pane.querySelector('.tab[data-tab="' + tabName + '"]').classList.add('active');
  pane.querySelector('.tab-content.tab-' + tabName).setAttribute('data-active', 'true');
}

function toggleCompany(rowEl, event) {
  // Don't toggle if the click was inside the expanded body (so user can read,
  // click <details> toggles, select text, etc. without collapsing the card)
  if (event && event.target && event.target.closest('.company-body')) return;
  // Don't toggle if user is selecting text
  if (window.getSelection && window.getSelection().toString().length > 0) return;
  rowEl.classList.toggle('collapsed');
}

document.addEventListener('DOMContentLoaded', () => {
  // Sector dropdown
  const sectorSelect = document.getElementById('sector-select');
  if (sectorSelect) sectorSelect.addEventListener('change', e => setSector(e.target.value));

  // Per-sector filter dropdowns
  document.querySelectorAll('.sector-filter').forEach(sel => {
    const sec = sel.getAttribute('data-sector');
    sel.addEventListener('change', e => applyFilter(sec, e.target.value));
  });

  // Tabs (each tab knows which sector it's in via data-tab name suffix)
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => showTabInSector(t.getAttribute('data-tab')));
  });

  // Language toggle
  document.querySelectorAll('.lang-btn').forEach(b => {
    b.addEventListener('click', () => setLang(b.dataset.lang));
  });

  applyI18n();
  // Apply initial filter for each sector
  Object.entries(CURRENT_FILTER).forEach(([sector, filter]) => applyFilter(sector, filter));
});
'''


# ───── Unified HTML assembly ─────

it_pane = build_it_sector_pane()
land_pane = build_land_transport_sector_pane()
mining_pane = build_mining_sector_pane()
petroleum_pane = build_petroleum_sector_pane()
marine_pane = build_marine_sector_pane()
air_pane = build_air_transport_sector_pane()
agri_pane = build_agri_fishery_sector_pane()


# ───── Methodology pane (NEW): shows the pipeline transparently for reviewers ─────

def build_methodology_pane() -> str:
    """A self-contained 'How we built this' pane. Bilingual, with collapsible sections so
    the reader can drill into any layer (input prompt, middle steps, output, quality controls,
    a worked example, cost). Designed for non-technical senior reviewers."""

    # The actual locked prompt — shown verbatim (Japanese output only)
    locked_prompt_en = '''You're helping someone quickly understand a Japanese listed company and why
its business and stock have moved. Write the way you'd explain it to a
smart colleague who has never heard of this company and is reading this
once — plain, clear, easy to get on the first read. No finance jargon.
Whenever you give a number, add a few words on what it means (big or
small? good, bad, or normal?). Keep each section to a short paragraph
or two — tight and readable, not a wall of text.

Research stock code {code} ({company_name}) using web search.

For the NUMBERS, use the most recent report. But for the REASONS, look
wider — the real cause is often a trend or chain of events over the
past several quarters or the past year.

Searching tip — useful Japanese terms when hunting for catalysts:
レーティング / 格上げ / 格下げ / 目標株価 / TOB / M&A /
業績予想修正 / 上方修正 / 下方修正 / 適時開示

Cover these four sections, in plain Japanese. Each section MUST start with its
header wrapped in **bold:** markdown so the renderer displays it as bold —
write the headers EXACTLY like this:

  **会社概要:** [What the company actually does.]
  **業績の動き:** [Latest results and guidance, numbers explained plainly.]
  **業績が動いた理由:** [WHY business moved that way.]
  **株価が動いた理由:** [WHY the stock moved over the past year.]

(Do NOT use 【会社概要】 brackets, ALL-CAPS headers, or plain headers without
**...**  — only `**Header:**` will render as bold in the HTML view.)

EXPLAIN, don't just NAME: after each reason, add a short "because…"
linking cause to effect in plain everyday terms.

Two limits, so "explaining" never becomes "making things up":
- General common-sense logic is fine (how tariffs work, what PBR<1
  means, etc.) — that's general knowledge.
- Do NOT invent company-specific facts or motives unless a source
  says so. If you don't know the mechanism, explain only the general
  logic and stop.

VERIFICATION PASS — MANDATORY BEFORE OUTPUT:
1. Re-read each headline number against the source you cited.
2. Pull a SECOND source for the most consequential numbers (latest FY
   actuals, dividend, current stock price). If they MATCH, use the
   number. If they DISAGREE, write BOTH in notes and use the more
   authoritative source (IR > Nikkei > Yahoo Finance > aggregator).
3. Disambiguate measures with multiple valid definitions (e.g.
   passenger count: total / domestic / international). State which.
4. Flag any specific claim (named broker action, named M&A, dated
   event) you can't point to a source for. Either remove or move to
   notes as "unverified."
5. Label each headline number in notes with fiscal-year scope:
   "Revenue ¥X — FY2026 actual, source: [URL]" etc.

Two rules: Use the web for everything. Only give a reason if a source
actually says it. If you can't find why, say so plainly — never invent.

ALSO output these compact tags (used for the card display in the UI):
- rev_dir:             "up" | "down" | "flat"   — revenue direction YoY
- op_dir:              "up" | "down" | "flat"   — operating profit direction YoY
- net_dir:             "up" | "down" | "flat"   — net profit direction YoY
- stock_yoy_estimate:  short string like "-20% from peak" or "+5% YoY"
                       — direction & rough magnitude of the past-12-month stock move
- biz_classification:  short bilingual label like
                       "フルサービス大手 / Full-service major"
                       — what kind of business this is, in one phrase

Output strict JSON:
{ jp_summary, rev_dir, op_dir, net_dir, stock_yoy_estimate,
  biz_classification, sources, notes }
(Japanese summary only — no English summary is produced.)'''

    locked_prompt_jp = '''あなたは、日本の上場企業について、その事業と株価がなぜ動いたかを誰かに
素早く理解してもらう手助けをしています。この企業を初めて聞く頭の良い同
僚に、一度読むだけで分かるように説明する書き方をしてください — 平易で明
瞭、初見で頭に入る文章にすること。金融専門用語は使わない。数字を出すた
びに、それが何を意味するかを短く添えること(大きいか小さいか? 良いか悪
いか普通か?)。各セクションは短い段落1〜2つ — 読みやすくコンパクトに、
文章の壁にならないように。

証券コード {code}({company_name})をWeb検索でリサーチしてください。

数値は最新の決算レポートを使用すること。ただし「理由」についてはもっと
広く見ること — 真の原因は過去数四半期や過去1年にわたるトレンドや出来事
の連鎖にあることが多いから。

検索ヒント — 触媒(カタリスト)を探す際に有用な日本語キーワード:
レーティング / 格上げ / 格下げ / 目標株価 / TOB / M&A /
業績予想修正 / 上方修正 / 下方修正 / 適時開示

以下の4つのセクションを、平易な日本語でカバーしてください。各セクション
は必ず **bold:** マークダウンでヘッダーをラップすること(レンダラーが太字
として表示するため) — ヘッダーは正確に下記の形式で記述すること:

  **会社概要:** [この会社が実際に何をしているか]
  **業績の動き:** [直近の決算と現在のガイダンス、数字を平易に説明]
  **業績が動いた理由:** [事業がなぜそう動いたか]
  **株価が動いた理由:** [株価が過去1年でなぜ動いたか]

(【会社概要】の角括弧、ALL-CAPS、**...**なしの平文ヘッダーは使用しない
こと — `**Header:**` 形式のみがHTMLビューで太字レンダリングされます。)

「説明する」のであって「名前を挙げる」だけではない: 各理由の後に、原因
と結果を結ぶ「なぜなら…」を1〜2文で短く付け加えること。

「説明」が「捏造」にならないための2つの制限:
- 一般的・常識的なロジック(関税の仕組み、PBR<1の意味など)はOK —
  これは一般知識であり、企業固有の主張ではない。
- ソースが明示していない限り、企業固有の事実や動機を捏造しないこと。
  メカニズムが分からない場合は、一般ロジックのみ説明して止めること。

検証パス(MANDATORY、出力前に必ず実施):
1. 述べる各主要数値を、引用ソースに対して再読確認すること。
2. 最も重要な数値(直近FY実績、配当、現在の株価)について、2つ目の
   独立ソースを引いて確認すること。一致すればその数値を使用; 不一致
   なら両方の数値をnotesに記入し、より権威のあるソース
   (IR > 日経 > Yahoo Finance > アグリゲーター)を本文で使用すること。
3. 複数の有効な定義がある指標を明確化(例: 旅客数 — 全体/国内/国際の
   どれか)。どれを指しているか明示すること。
4. 特定の主張(名指しの証券会社アクション、名指しのM&A、日付付き
   イベント)で、ソースを指せないものはnotesに「unverified」として
   移動するか削除すること。
5. 各主要数値をnotesで会計年度スコープと共にラベル付け:
   「売上 ¥X — FY2026実績、ソース: [URL]」など。

2つの重要なルール: 何でもWebで調べること。ソースが実際に言っている
理由のみを述べること。もしなぜか分からない場合は、平易にそう言うこと
— 決して捏造しないこと。

以下のコンパクトタグも出力すること(UIのカード表示で使用):
- rev_dir:             "up" | "down" | "flat"   — 売上の前年同期比方向
- op_dir:              "up" | "down" | "flat"   — 営業利益の前年同期比方向
- net_dir:             "up" | "down" | "flat"   — 純利益の前年同期比方向
- stock_yoy_estimate:  「-20% from peak」「+5% YoY」のような短い文字列
                       — 過去12か月の株価動向の方向と概略の大きさ
- biz_classification:  「フルサービス大手 / Full-service major」のような
                       短い日英ラベル — どのような事業かを一言で

厳密JSONで出力:
{ jp_summary, rev_dir, op_dir, net_dir, stock_yoy_estimate,
  biz_classification, sources, notes }
(日本語要約のみ — 英語要約は生成しません)'''

    # Pipeline at-a-glance — simple text-based diagram
    pipeline_diagram = '''
┌─────────────────────────────────────────────────────────────────┐
│  1. INPUT                                                       │
│  ────────                                                       │
│  • Stock code (e.g. 9201)                                       │
│  • Locked prompt template (see "Input prompt" below)            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. MIDDLE STEPS  (~6 minutes per company, runs unattended)     │
│  ─────────────                                                  │
│  a) Claude Sonnet 4.6 reads the prompt                          │
│  b) Searches the web 5–10 times (Japanese sources)              │
│  c) Reads 3–5 pages in detail (IR, Nikkei, kabutan, irbank…)    │
│  d) Drafts the 4-section summary in plain Japanese              │
│  e) VERIFICATION PASS — checks every headline number against    │
│     a second independent source. Disagreements logged in notes. │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. OUTPUT                                                      │
│  ─────────                                                      │
│  • jp_summary           — 4 sections, plain Japanese            │
│  • rev_dir / op_dir /                                           │
│    net_dir              — "up" / "down" / "flat" tags           │
│  • stock_yoy_estimate   — e.g. "-20% from peak"                 │
│  • biz_classification   — e.g. "フルサービス大手 / Full-service │
│                                  major"                         │
│  • sources              — every URL the model actually used     │
│  • notes                — verification audit trail              │
└─────────────────────────────────────────────────────────────────┘
'''

    # Worked example: JAL (9201) — show before-and-after a verification step
    return f'''
    <div class="sector-pane methodology-pane" data-sector="Methodology" style="display: none;">

      <div class="methodology-intro">
        <h2 data-en="How we built this view" data-jp="このビューの作り方">How we built this view</h2>
        <p class="meth-lede"
           data-en="For each company, an AI model (Claude Sonnet 4.6) is given one carefully-worded prompt and access to the web. It searches Japanese sources, reads the most relevant pages, drafts a plain-language summary in Japanese, then runs a self-verification pass against a second source before producing the final result. Every URL it used is recorded; every number it claims is labeled with its fiscal-year scope; anything it could not confirm is honestly flagged. The whole pipeline is designed so that a reviewer can audit any output by reading the notes field and following the source URLs."
           data-jp="各企業について、AIモデル（Claude Sonnet 4.6）に注意深く作成された1つのプロンプトとWebアクセスを与えます。日本語ソースを検索し、最も関連性の高いページを読み、日本語で平易な説明を作成し、最終結果を出す前に2つ目のソースに対して自己検証パスを実行します。使用したすべてのURLが記録され、主張するすべての数字には会計年度のラベルが付き、確認できなかったものは正直にフラグが立てられます。レビュアーはnotesフィールドを読みソースURLをたどることで、すべての出力を監査できます。">
          For each company, an AI model (Claude Sonnet 4.6) is given one carefully-worded prompt and access to the web. It searches Japanese sources, reads the most relevant pages, drafts a plain-language summary in Japanese, then runs a self-verification pass against a second source before producing the final result. Every URL it used is recorded; every number it claims is labeled with its fiscal-year scope; anything it could not confirm is honestly flagged. The whole pipeline is designed so that a reviewer can audit any output by reading the notes field and following the source URLs.
        </p>
      </div>

      <details class="meth-section" open>
        <summary>
          <span data-en="📊 Pipeline at a glance" data-jp="📊 全体の流れ">📊 Pipeline at a glance</span>
        </summary>
        <pre class="meth-diagram">{esc(pipeline_diagram)}</pre>
      </details>

      <details class="meth-section">
        <summary>
          <span data-en="📝 The input prompt (locked, identical for every company)"
                data-jp="📝 入力プロンプト（固定。全社で同一）">📝 The input prompt (locked, identical for every company)</span>
        </summary>
        <p class="meth-explain"
           data-en="This is the EXACT text given to the model. {{code}} and {{company_name}} are the only things that change per company — everything else is byte-identical across every run. That's what makes the pipeline reproducible: same prompt + same model = comparable outputs across all 2,900 companies."
           data-jp="これがモデルに与える正確なテキストです。{{code}}と{{company_name}}だけが企業ごとに変わり、それ以外は実行ごとにバイト単位で同一です。これによりパイプラインの再現性が保たれます：同じプロンプト＋同じモデル＝2,900社全体で比較可能な出力。">
          This is the EXACT text given to the model. <code>{{code}}</code> and <code>{{company_name}}</code>
          are the only things that change per company — everything else is byte-identical across every run.
        </p>
        <pre class="meth-prompt" data-lang="en">{esc(locked_prompt_en)}</pre>
        <pre class="meth-prompt" data-lang="jp">{esc(locked_prompt_jp)}</pre>
      </details>

      <details class="meth-section">
        <summary>
          <span data-en="🔍 What happens in the middle (the AI's research process)"
                data-jp="🔍 中間ステップ（AIのリサーチ・プロセス）">🔍 What happens in the middle (the AI's research process)</span>
        </summary>
        <div class="meth-explain">
          <p data-en="The AI doesn't just answer from memory — it actively researches each company on the live web. A typical run looks like this:"
             data-jp="AIは記憶から答えるのではなく、Web上で各企業を能動的にリサーチします。典型的な実行は以下の通り：">
            The AI doesn't just answer from memory — it actively researches each company on the live web. A typical run looks like this:
          </p>
          <ol class="meth-steps">
            <li data-en="<b>Search the web (5–10 times)</b> — primarily Japanese sources. Targets include kabutan, Nikkei, Yahoo Finance Japan, irbank, IR pages, traders.co.jp, gamebiz."
                data-jp="<b>Web検索（5〜10回）</b> — 主に日本語ソース。対象：kabutan、日経、Yahoo Finance Japan、irbank、IRページ、traders.co.jp、gamebiz。">
              <b>Search the web (5–10 times)</b> — primarily Japanese sources. Targets include kabutan, Nikkei, Yahoo Finance Japan, irbank, IR pages, traders.co.jp, gamebiz.
            </li>
            <li data-en="<b>Open and read 3–5 pages in detail</b> — pulling specific numbers (revenue, profit, dividend, stock price) and event details (broker downgrades, M&A, scandals)."
                data-jp="<b>3〜5ページを詳細に読む</b> — 具体的な数値（売上、利益、配当、株価）とイベント詳細（証券会社の格下げ、M&A、スキャンダル）を抽出。">
              <b>Open and read 3–5 pages in detail</b> — pulling specific numbers (revenue, profit, dividend, stock price) and event details.
            </li>
            <li data-en="<b>Draft the summary in Japanese</b> — 4 sections (会社概要 / 業績の動き / 業績が動いた理由 / 株価が動いた理由) in plain language. Every reason gets a 'because…' clause linking cause to effect."
                data-jp="<b>日本語で要約を起草</b> — 平易な言葉で4セクション（会社概要 / 業績の動き / 業績が動いた理由 / 株価が動いた理由）。各理由には原因と結果を結ぶ「なぜなら…」が付きます。">
              <b>Draft the summary in Japanese</b> — 4 sections in plain language. Every reason gets a "because…" clause.
            </li>
            <li data-en="<b>Verification pass</b> — for each headline number (revenue, operating profit, net profit, dividend, current stock price), pull a SECOND source and check it matches. If sources disagree, BOTH numbers are logged in the notes field and the more authoritative one (IR &gt; Nikkei &gt; Yahoo Finance &gt; aggregator) is used in the prose."
                data-jp="<b>検証パス</b> — 各主要数値（売上、営業利益、純利益、配当、現在の株価）について、2つ目のソースを引いて一致を確認。ソースが矛盾する場合、両方の数値をnotesフィールドに記録し、より権威のあるソース（IR ＞ 日経 ＞ Yahoo ＞ アグリゲーター）を本文で使用。">
              <b>Verification pass</b> — for each headline number, pull a SECOND source and check it matches. If sources disagree, BOTH numbers go in notes and the more authoritative one is used in the prose.
            </li>
            <li data-en="<b>Output as strict JSON</b> — jp_summary (the prose) + 5 compact card tags (rev_dir, op_dir, net_dir, stock_yoy_estimate, biz_classification) + sources + notes."
                data-jp="<b>厳格なJSONとして出力</b> — jp_summary（本文）+ カード表示用の5つのコンパクトタグ（rev_dir、op_dir、net_dir、stock_yoy_estimate、biz_classification）+ sources + notes。">
              <b>Output as strict JSON</b> — jp_summary (the prose) + 5 compact card tags + sources + notes.
            </li>
          </ol>
          <p data-en="<b>Wall-clock time:</b> about 5–7 minutes per company, fully unattended. The model uses an average of ~42,000 tokens of context per run (Japanese-only output)."
             data-jp="<b>実行時間：</b>1社あたり約5〜7分、完全自動。1実行あたり平均約42,000トークンのコンテキストを使用（日本語のみ出力）。">
            <b>Wall-clock time:</b> about 5–7 minutes per company, fully unattended. ~42,000 tokens of context per run on average (Japanese-only output).
          </p>
        </div>
      </details>

      <details class="meth-section">
        <summary>
          <span data-en="📦 The output format (what each company entry contains)"
                data-jp="📦 出力フォーマット（各企業エントリーの中身）">📦 The output format</span>
        </summary>
        <div class="meth-explain">
          <p data-en="Every company in this view has this exact JSON shape, stored in a sector file (e.g. company_research_air_transport_sector.json):"
             data-jp="このビューに表示されるすべての企業は、以下のJSON構造を持ち、セクター別ファイル（例：company_research_air_transport_sector.json）に格納されます：">
            Every company has this exact JSON shape, stored per-sector:
          </p>
          <pre class="meth-output-schema">{{
  "9201": {{
    "name":               "Japan Airlines",
    "jp_summary":         "[4 sections in plain Japanese, ~1,500–2,500 chars]",
    "rev_dir":            "up",
    "op_dir":             "up",
    "net_dir":            "up",
    "stock_yoy_estimate": "-20% from peak",
    "biz_classification": "フルサービス大手 / Full-service major",
    "sources":            ["url1", "url2", ...],
    "notes":              "[verification audit trail + anything unconfirmed]"
  }}
}}</pre>
          <p data-en="<b>Why the notes field matters:</b> this is the audit trail. It labels each headline number with its fiscal-year scope and the source URL, flags anywhere two sources disagreed, and tags as 'unverified' anything the model could not confirm from a source. To check any output, a reviewer reads notes first."
             data-jp="<b>notesフィールドが重要な理由：</b>これが監査証跡です。各主要数値に会計年度の範囲とソースURLを付け、2つのソースが矛盾した箇所をフラグし、ソースから確認できなかったものを「unverified」とタグ付けします。出力を確認するには、レビュアーはまずnotesを読みます。">
            <b>Why the notes field matters:</b> this is the audit trail. Reviewer reads notes first.
          </p>
        </div>
      </details>

      <details class="meth-section">
        <summary>
          <span data-en="⚖️ Quality controls (how we prevent the AI from making things up)"
                data-jp="⚖️ 品質管理（AIが事実を捏造しないようにする仕組み）">⚖️ Quality controls</span>
        </summary>
        <ul class="meth-controls">
          <li data-en="<b>Anti-fabrication rule:</b> the prompt explicitly bans naming specific events (broker action, M&A, dated event) unless a source backs them. If no source exists, the model says so plainly instead of inventing one."
              data-jp="<b>捏造防止ルール：</b>プロンプトは、ソースが裏付けない限り、具体的なイベント（証券会社のアクション、M&A、日付付きイベント）を名指しすることを明確に禁じています。ソースがなければ、モデルは捏造する代わりに「ない」と明言します。">
            <b>Anti-fabrication rule</b> — the prompt explicitly bans naming specific events unless a source backs them.
          </li>
          <li data-en='<b>Two-source verification:</b> headline numbers (revenue, profit, dividend, current price) are checked against a SECOND independent source. Disagreements are logged in notes; the more authoritative source wins.'
              data-jp='<b>2ソース検証：</b>主要数値（売上、利益、配当、現在の株価）は2つ目の独立したソースに対して確認されます。不一致はnotesに記録され、より権威のあるソースが採用されます。'>
            <b>Two-source verification</b> — headline numbers checked against a SECOND independent source.
          </li>
          <li data-en="<b>Fiscal-year disambiguation:</b> the same metric (e.g. dividend) can refer to FY-actual vs FY-guidance vs prior-year. The notes field explicitly labels which one a number refers to."
              data-jp="<b>会計年度の明確化：</b>同じ指標（例：配当）は、FY実績／FYガイダンス／前年実績を指す可能性があります。notesフィールドはどれを指すか明示的にラベル付けします。">
            <b>Fiscal-year disambiguation</b> — notes label whether each number is FY-actual, FY-guidance, or prior-year.
          </li>
          <li data-en="<b>Measure disambiguation:</b> some metrics have multiple valid definitions (e.g. Toyota vehicle sales: ~9.6M brand-only vs ~11M Group-consolidated). The output explicitly states which measure is used."
              data-jp="<b>指標の明確化：</b>一部の指標には複数の有効な定義があります（例：トヨタの販売台数：トヨタブランドのみ約960万台 vs グループ連結約1,100万台）。出力では使用する指標を明示的に記述します。">
            <b>Measure disambiguation</b> — multi-definition metrics get an explicit which-one-we-used statement.
          </li>
          <li data-en='<b>Calibration testing:</b> the pipeline was validated on companies with KNOWN hidden catalysts (KDDI BIGLOBE ¥246B fraud, Nippon Paper NDP factory accident, Secom ¥100B buyback). Sonnet found all hidden catalysts in 9 out of 9 fresh runs.'
              data-jp='<b>キャリブレーション・テスト：</b>パイプラインは、既知の隠れた触媒（KDDI BIGLOBE 2,461億円不正、日本製紙NDP工場事故、セコム1,000億円自社株買い）を持つ企業で検証されました。Sonnetは9回の新規実行のうち9回すべてで隠れた触媒を発見しました。'>
            <b>Calibration testing</b> — pipeline validated on companies with KNOWN hidden catalysts. Sonnet caught all 9 of 9 in fresh runs.
          </li>
        </ul>
      </details>

      <details class="meth-section">
        <summary>
          <span data-en="💡 Worked example — Japan Airlines (9201)"
                data-jp="💡 実例 — 日本航空 (9201)">💡 Worked example — Japan Airlines (9201)</span>
        </summary>
        <div class="meth-explain">
          <p data-en="<b>Input given to the model:</b> the locked prompt above, with <code>{{code}}=9201</code> and <code>{{company_name}}=Japan Airlines / JAL / 日本航空</code>."
             data-jp="<b>モデルに与えた入力：</b>上記の固定プロンプト、<code>{{code}}=9201</code>と<code>{{company_name}}=Japan Airlines / JAL / 日本航空</code>を代入。">
            <b>Input given to the model:</b> the locked prompt above, with <code>{{code}}=9201</code> and <code>{{company_name}}=Japan Airlines / JAL / 日本航空</code>.
          </p>
          <p data-en="<b>What the model did (middle steps):</b>"
             data-jp="<b>モデルの行動（中間ステップ）：</b>">
            <b>What the model did (middle steps):</b>
          </p>
          <ul class="meth-steps">
            <li data-en="Searched: 'JAL FY2026 results', '日本航空 2026年3月期 決算', 'JAL FY2027 guidance fuel', 'JAL 格下げ 2026', 'JAL Iran oil price'"
                data-jp="検索：「JAL FY2026 results」「日本航空 2026年3月期 決算」「JAL FY2027 guidance fuel」「JAL 格下げ 2026」「JAL Iran oil price」">
              Searched ~7 queries in JP and EN
            </li>
            <li data-en="Fetched: AeroTime FY26 article, Traicy results page, Nikkei Asia FY27 fuel-hike article, JAL official press release, kabuka.jp.net rating page, Yahoo Finance JP AI-topics"
                data-jp="取得：AeroTime FY26記事、Traicy 決算ページ、日経Asia FY27燃料費記事、JAL公式プレスリリース、kabuka.jp.netレーティングページ、Yahoo Finance JP AI-topics">
              Fetched 6 pages in detail
            </li>
            <li data-en="Drafted the summary in Japanese — 4 sections, plain language, with 'because…' explanations after every reason"
                data-jp="日本語で要約を起草 — 4セクション、平易な言葉、各理由に「なぜなら…」を付加">
              Drafted the Japanese summary
            </li>
            <li data-en="Verification pass: confirmed Revenue ¥2,012.5B across AeroTime + Traicy + JAL press release (3 sources match). Caught a discrepancy on EBIT: AeroTime said ¥218B, Traicy said ¥144.4B. Cross-checked against JAL's own press release (¥218.0B / '2,180億円') and used ¥218B as authoritative — Traicy figure noted in notes as a likely data error."
                data-jp="検証パス：売上2兆125億円をAeroTime + Traicy + JALプレスリリースで確認（3ソース一致）。EBITで矛盾を発見：AeroTimeは2,180億円、Traicyは1,444億円。JALの公式プレスリリース（2,180億円）と照合し、2,180億円を正解として採用。Traicyの数値は、データエラーの可能性が高いとnotesに記録。">
              Verification pass caught a discrepancy and resolved it
            </li>
          </ul>
          <p data-en='<b>Output produced:</b> ~1,700-character Japanese summary + 10 source URLs + a 1,200-character verification audit trail in notes. Total wall-clock: 5.5 minutes. Total cost (if batched): ~$0.17.'
             data-jp='<b>生成された出力：</b>約1,700文字の日本語要約 + 10件のソースURL + notesに約1,200文字の検証監査証跡。総実行時間：5.5分。バッチ実行時のコスト：約$0.17。'>
            <b>Output produced:</b> ~1,700-char Japanese summary + 10 source URLs + 1,200-char verification audit trail. Wall-clock: 5.5 min. Batched cost: ~$0.17.
          </p>
        </div>
      </details>

      <details class="meth-section">
        <summary>
          <span data-en="💰 Cost &amp; scale" data-jp="💰 コストと規模">💰 Cost &amp; scale</span>
        </summary>
        <ul class="meth-cost">
          <li data-en="<b>Per company:</b> ~$0.17 batched (~$0.27 real-time)"
              data-jp="<b>1社あたり：</b>バッチ実行時約$0.17（リアルタイム約$0.27）">
            <b>Per company:</b> ~$0.17 batched (~$0.27 real-time)
          </li>
          <li data-en="<b>Cost breakdown per company (batched):</b> input tokens ~$0.06 + output tokens ~$0.045 + web search fees ~$0.065 = ~$0.17"
              data-jp="<b>1社あたりコスト内訳（バッチ）：</b>入力トークン約$0.06 + 出力トークン約$0.045 + Web検索料約$0.065 = 合計約$0.17">
            <b>Cost breakdown per company (batched):</b> input tokens ~$0.06 + output tokens ~$0.045 + web search fees ~$0.065 = ~$0.17
          </li>
          <li data-en="<b>For the full ~2,900-company R+ universe:</b> ~$490 total via Anthropic Batch API (Japanese-only output)"
              data-jp="<b>全約2,900社のR+ユニバース：</b>Anthropic Batch API経由で合計約$490（日本語のみ出力）">
            <b>For the full ~2,900-company R+ universe:</b> ~$490 total via Anthropic Batch API (Japanese-only output)
          </li>
          <li data-en="<b>Turnaround:</b> Batch API delivers within 24 hours. Real-time API delivers within ~6 minutes per company."
              data-jp="<b>納期：</b>Batch APIは24時間以内に納品。リアルタイムAPIは1社あたり約6分。">
            <b>Turnaround:</b> Batch API within 24h. Real-time API ~6 min/company.
          </li>
        </ul>
      </details>

    </div>
    '''


methodology_pane = build_methodology_pane()


doc = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>R+ Classification View — Multi-Sector</title>
<style>{UNIFIED_STYLES}</style>
</head>
<body>
<header class="page-header">
  <h1 data-i18n="page.title">R+ Classification View — Multi-Sector (FY3/2026)</h1>
  <div class="subtitle" data-i18n="page.subtitle">2026-06-05 · 5 TOPIX-33 sectors · per-sector filter + transparency block</div>
  <div class="lang-toggle">
    <button class="lang-btn active" data-lang="en">EN</button>
    <button class="lang-btn" data-lang="jp">日本語</button>
  </div>
  <div class="top-controls">
    <label for="sector-select" data-i18n="sector.label">Sector:</label>
    <select id="sector-select">
      <option value="IT" data-en="Information &amp; Communication (情報・通信業)" data-jp="情報・通信業" selected>Information &amp; Communication (情報・通信業)</option>
      <option value="LandTransport" data-en="Land Transportation (陸運業)" data-jp="陸運業">Land Transportation (陸運業)</option>
      <option value="Mining" data-en="Mining (鉱業)" data-jp="鉱業">Mining (鉱業)</option>
      <option value="Petroleum" data-en="Petroleum &amp; Coal Products (石油・石炭製品)" data-jp="石油・石炭製品">Petroleum &amp; Coal Products (石油・石炭製品)</option>
      <option value="Marine" data-en="Marine Transportation (海運業)" data-jp="海運業">Marine Transportation (海運業)</option>
      <option value="AirTransport" data-en="Air Transportation (空運業)" data-jp="空運業">Air Transportation (空運業)</option>
      <option value="AgriFishery" data-en="Fishery, Agriculture &amp; Forestry (水産・農林業)" data-jp="水産・農林業">Fishery, Agriculture &amp; Forestry (水産・農林業)</option>
      <option value="Methodology" data-en="📋 Methodology — How we built this" data-jp="📋 方法論 — どうやって作ったか">📋 Methodology — How we built this</option>
    </select>
  </div>
</header>

<div class="container">
  {it_pane}
  {land_pane}
  {mining_pane}
  {petroleum_pane}
  {marine_pane}
  {air_pane}
  {agri_pane}
  {methodology_pane}
</div>

<script>{UNIFIED_JS}</script>
</body>
</html>
'''

DELIVERABLES.mkdir(exist_ok=True)
out_html = DELIVERABLES / 'UNIFIED_VIEW.html'
out_html.write_text(doc, encoding='utf-8')
print(f'Wrote deliverables/{out_html.name} ({len(doc):,} bytes)')

# Summary
def _count_tab(companies, tab):
    return sum(1 for c in companies.values() if c.get('tab') == tab)

total_minus_it = sum(len(v) for v in it_mod.buckets_s_minus.values())
total_plus_it = sum(len(v) for v in it_mod.buckets_s_plus.values())

total_minus_mining = _count_tab(mining_companies, 'R+xS-')
total_plus_mining = _count_tab(mining_companies, 'R+xS+')
total_minus_petroleum = _count_tab(petroleum_companies, 'R+xS-')
total_plus_petroleum = _count_tab(petroleum_companies, 'R+xS+')
total_minus_marine = _count_tab(marine_companies, 'R+xS-')
total_plus_marine = _count_tab(marine_companies, 'R+xS+')
total_minus_land = _count_tab(land_companies, 'R+xS-')
total_plus_land = _count_tab(land_companies, 'R+xS+')
total_minus_air = _count_tab(air_companies, 'R+xS-')
total_plus_air = _count_tab(air_companies, 'R+xS+')
total_minus_agri = _count_tab(agri_companies, 'R+xS-')
total_plus_agri = _count_tab(agri_companies, 'R+xS+')

print(f'\nUnified view summary (7 TOPIX-33 sectors):')
print(f'  Information & Communication: {total_minus_it + total_plus_it} R+ companies ({total_minus_it} R+xS-, {total_plus_it} R+xS+) [default: 売上○]')
print(f'  Land Transportation        : {total_minus_land + total_plus_land} R+ companies ({total_minus_land} R+xS-, {total_plus_land} R+xS+) [default: 売上○]')
print(f'  Mining (鉱業)              : {total_minus_mining + total_plus_mining} R+ companies ({total_minus_mining} R+xS-, {total_plus_mining} R+xS+) [default: 営業利益○ — 0 this year, both INPEX/JAPEX are R-]')
print(f'  Petroleum (石油・石炭製品): {total_minus_petroleum + total_plus_petroleum} R+ companies ({total_minus_petroleum} R+xS-, {total_plus_petroleum} R+xS+) [default: 営業利益○]')
print(f'  Marine Transportation     : {total_minus_marine + total_plus_marine} R+ companies ({total_minus_marine} R+xS-, {total_plus_marine} R+xS+) [active default: 売上○ — 営業利益○ shows 0 this year]')
print(f'  Air Transportation        : {total_minus_air + total_plus_air} R+ companies ({total_minus_air} R+xS-, {total_plus_air} R+xS+) [default: 売上○]')
print(f'  Fishery / Agri / Forestry : {total_minus_agri + total_plus_agri} R+ companies ({total_minus_agri} R+xS-, {total_plus_agri} R+xS+) [default: 売上○]')
print(f'  Each sector pane shows: TOPIX-33 sector statistics block + filter + why-this-filter + tabs.')
