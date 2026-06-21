# -*- coding: utf-8 -*-
"""Render the STAGED 26-bucket classification into the HTML bucket view.

PROVISIONAL structural proposal for 中町氏 (revert-cheap):
  R±×S× quadrant  →  specific_bucket (primary business reason)
  with guidance_overlay AND event_overlay shown as chips on each card.
Reads it_q4_{year}.staged.json (NOT committed) + packets for numbers/prices.

  python build/build_specific_view.py 2025
  python build/build_specific_view.py 2024
"""
from __future__ import annotations
import json, html, sys, glob
from pathlib import Path

ROOT = Path(__file__).parent.parent
# Committed CSS/JS chrome (extracted from UNIFIED_VIEW.html) so the renderer is
# self-contained — no HTML deliverable needs to ship to run the pipeline.
SRC = Path(__file__).parent / 'view_chrome.tmpl'
YEAR = sys.argv[1] if len(sys.argv) > 1 else '2025'
_PKT = {'2022': '_pkts_2022_mdna', '2023': '_pkts_2023_mdna', '2024': '_pkts_2024_mdna', '2025': '_pkts_mdna'}
PKTDIR = ROOT / 'data' / 'quarterly' / _PKT[YEAR]
STAGED = ROOT / 'data' / 'quarterly' / f'it_q4_{YEAR}.staged.json'
OUT = ROOT / 'deliverables' / 'quarterly' / f'VIEW_IT_{YEAR}Q4_SPECIFIC_provisional.html'


def esc(s): return html.escape(str(s)) if s is not None else ''


src = SRC.read_text(encoding='utf-8')
style_block = src[src.index('<style>'):src.index('</style>') + len('</style>')]
js_start = src.index('<script>', src.index('</style>'))
js_block = src[js_start:src.index('</script>', js_start) + len('</script>')].replace("let LANG = 'en';", "let LANG = 'jp';")

CATS = {
    'RpSp': ('R+ × S+ — 増収(増益)・株高', True, 'up'),
    'RpSm': ('R+ × S− — 増収(増益)・株安（overlooked候補の母集団）', True, 'down'),
    'RmSp': ('R− × S+ — 減収(減益)・株高', False, 'up'),
    'RmSm': ('R− × S− — 減収(減益)・株安', False, 'down'),
    'flat': ('S0 — 株価ほぼ変わらず', None, 'flat'),
}
CAT_ORDER = ['RpSp', 'RpSm', 'RmSp', 'RmSm', 'flat']

# specific_bucket → (en, ja)
LABELS = {
    'saas_arr_expansion': ('SaaS / ARR expansion', 'SaaS・ARR拡大'),
    'margin_compression_cost_investment': ('Margin compression (cost/investment)', '費用先行・コスト増でマージン圧迫'),
    'margin_expansion': ('Margin expansion', '採算改善・営業レバレッジ'),
    'one_off_loss': ('One-off loss', '一過性損失（減損・評価損等）'),
    'one_off_cost_rolloff': ('Prior-year cost roll-off', '前期一過性コストの剥落'),
    'm_and_a_consolidation': ('M&A consolidation', 'M&A連結効果'),
    'cloud_migration_growth': ('Cloud migration growth', 'クラウド移行・クラウド成長'),
    'price_arpu_improvement': ('Price / ARPU improvement', '価格改定・ARPU向上'),
    'public_sector_it_demand': ('Public-sector IT demand', '官公庁・公共IT需要'),
    'ip_content_hit_title': ('IP / content hit', 'IP・映画・アニメのヒット'),
    'one_off_gain': ('One-off gain', '一過性利益（売却益・評価益）'),
    'new_game_title_launch': ('New game-title launch', '新規ゲーム投入・新作ヒット'),
    'manufacturing_plm_it_demand': ('Manufacturing / PLM IT demand', '製造業向けIT・PLM需要'),
    'cyclical_recovery_post_covid': ('Cyclical / post-COVID recovery', 'コロナ後の需要正常化'),
    'tv_ad_revenue_structural_decline': ('TV-ad structural decline', '地上波TV広告の構造的減少'),
    'invoice_electronic_ledger_demand': ('Invoice / e-ledger demand', 'インボイス・電帳法特需'),
    'cybersecurity_investment_demand': ('Cybersecurity demand', 'サイバーセキュリティ投資需要'),
    'game_title_prior_year_high_base_rolloff': ('Prior-year big-title roll-off', '前期大型タイトルの反動減'),
    'existing_game_title_decline': ('Existing game-title decline', '既存ゲームの自然減'),
    'inbound_tourism_demand': ('Inbound tourism demand', 'インバウンド需要'),
    'sap_erp_renewal_demand': ('SAP / ERP 2027 renewal demand', 'SAP・ERP更改(2027)需要'),
    'no_report_reason_found': ('No report reason — overlooked candidate', '決算に理由なし — overlooked候補'),
    'other': ('Other', 'その他'),
}
GUID = {'disappointment': ('guidance: weak', 'ガイダンス弱'), 'raise': ('guidance: raise', 'ガイダンス強気')}
EVT = {'contract_win': ('event: contract win', '受注獲得'), 'contract_loss_churn': ('event: loss/churn', '失注・解約')}

# Curated PLAIN-LANGUAGE one-liner per bucket (fixed, bilingual, NOT per-company).
# This is the human-readable "main reason at a glance" — describes the state, no forecasts.
ONELINER = {
    'saas_arr_expansion': ('Recurring subscription revenue (SaaS/ARR) grew as the customer base expanded.',
                           'サブスク型（SaaS・ARR）の継続収益が、顧客基盤の拡大とともに積み上がった。'),
    'margin_compression_cost_investment': ('Revenue held up, but profit margins narrowed as the company spent more on cost and investment.',
                           '増収は続いたが、コスト増・先行投資で利益率が縮み、利益が伸び悩んだ。'),
    'margin_expansion': ('Profit grew faster than sales as the business became more efficient (margin improvement).',
                           '同じ規模でも採算が改善し、売上以上に利益が伸びた（マージン改善）。'),
    'one_off_loss': ('A one-time loss (such as an impairment or write-down) weighed on results this period.',
                           '今期は一過性の損失（減損・評価損など）が利益を押し下げた。'),
    'one_off_cost_rolloff': ('Profit improved mainly because last year’s one-time costs dropped out.',
                           '前期にあった一過性コストが剥落し、その反動で利益が改善した。'),
    'm_and_a_consolidation': ('Sales rose mainly because an acquired business was newly consolidated.',
                           'M&Aで取得した事業が新たに連結され、主に増収につながった。'),
    'cloud_migration_growth': ('Sales rose as customers moved onto the company’s cloud services.',
                           '顧客のクラウド移行が進み、クラウドサービスの売上が伸びた。'),
    'price_arpu_improvement': ('Revenue rose on higher prices / more spend per customer (ARPU).',
                           '価格改定や顧客単価（ARPU）の上昇で増収となった。'),
    'public_sector_it_demand': ('Government and public-sector IT demand drove the growth.',
                           '官公庁・自治体など公共分野のIT需要が成長をけん引した。'),
    'ip_content_hit_title': ('A hit film / anime / IP title lifted results.',
                           '映画・アニメなどIPのヒット作が業績を押し上げた。'),
    'one_off_gain': ('A one-time gain (such as an asset sale) lifted profit this period.',
                           '今期は一過性の利益（資産売却益など）が利益を押し上げた。'),
    'new_game_title_launch': ('A new game title (or major release) drove the growth.',
                           '新規ゲームタイトル（大型新作）の投入が成長をけん引した。'),
    'manufacturing_plm_it_demand': ('Demand for manufacturing IT / PLM (design, EV/CASE) drove the growth.',
                           '製造業向けIT・PLM（設計、EV/CASE対応）の需要が成長をけん引した。'),
    'cyclical_recovery_post_covid': ('Demand normalized as conditions recovered after COVID.',
                           'コロナ後に需要が正常化し、景気回復が業績を押し上げた。'),
    'tv_ad_revenue_structural_decline': ('Terrestrial TV-advertising revenue kept shrinking structurally.',
                           '地上波テレビ広告の収入が構造的に縮小し続けた。'),
    'invoice_electronic_ledger_demand': ('Special demand from the invoice / e-bookkeeping rules drove sales.',
                           'インボイス制度・電帳法対応の特需が売上をけん引した。'),
    'cybersecurity_investment_demand': ('Demand for the company’s cybersecurity products drove the growth.',
                           'サイバーセキュリティ製品への投資需要が成長をけん引した。'),
    'game_title_prior_year_high_base_rolloff': ('Results fell against last year’s big game-title boost (reaction decline).',
                           '前期の大型タイトルの反動で、今期は減収・減益となった。'),
    'existing_game_title_decline': ('Revenue from existing games declined naturally over their life cycle.',
                           '既存ゲームがライフサイクルに沿って自然に減収となった。'),
    'inbound_tourism_demand': ('Rising inbound tourism lifted demand.',
                           '訪日外国人（インバウンド）需要の増加が業績を押し上げた。'),
    'sap_erp_renewal_demand': ('Demand for SAP / ERP renewals (the 2027 deadline) drove sales.',
                           'SAP・ERP更改（2027年問題）への対応需要が売上をけん引した。'),
    'no_report_reason_found': ('Fundamentals improved but the stock didn’t follow — and the report names no reason for the drop (overlooked candidate).',
                           '業績は改善したのに株価が追随せず、決算書類にも下落の理由が見当たらない（overlooked候補）。'),
    'other': ('An individual situation that doesn’t fit one standard bucket — see the company’s detail.',
                           '標準バケットに当てはまらない個別事情（各社の詳細を参照）。'),
}
GUID_LINE = {'raise': ('The company also raised its earnings outlook.', 'あわせて翌期の業績見通しを上方修正・強気とした。'),
             'disappointment': ('Its next-year guidance was weak / disappointing.', '一方で翌期ガイダンスは弱く、失望を招いた。')}
EVT_LINE = {'contract_win': ('Won a major new contract.', '大型の新規受注・契約を獲得した。'),
            'contract_loss_churn': ('Lost a major contract or saw notable churn.', '大口の失注・解約（チャーン）が発生した。')}

# ── DIVERGENT-QUADRANT stock-reason-led headings (R+S− and R−S+) ──
# Here business≠stock, so the heading must say WHY THE STOCK MOVED, not the (positive) business
# reason. Each: (short_en, short_ja, oneliner_en, oneliner_ja).
STOCK_DIV = {
 'sd_weak_guidance': ('Weak guidance → stock fell', '弱いガイダンスで株安',
    'Revenue rose, but the stock fell because the next-year guidance was weak/disappointing.',
    '増収でも、翌期ガイダンスが弱く失望され、株価が下落した。'),
 'sd_margin_squeeze': ('Margin squeeze → derated', '採算悪化（増収減益）で株安',
    'Revenue grew but profit was squeezed, so the market derated the stock.',
    '増収でも利益率が悪化（増収減益）し、採算悪化を嫌気して株価が下落した。'),
 'sd_oneoff_inflated': ('Growth was one-off → market unconvinced', '増収が一過性で株安',
    'The market judged the growth to be one-off rather than underlying, so the stock fell.',
    '増収は一過性によるものと市場が見抜き、株価は追随せず下落した。'),
 'sd_missed_expectations': ('Below expectations → fell (vs own-plan: TBC)', '期待未達で株安（自社計画比は要確認）',
    'Results came in below what the market expected, so the stock fell. (Whether it missed the company’s OWN plan is to be confirmed by the deterministic check.)',
    '当期実績が市場の期待に届かず株価が下落した。（自社計画比での裏付けは確定チェック待ち）'),
 'sd_no_report_reason': ('OVERLOOKED candidate — fundamentals not yet in the price', '見過ごされ候補 — 株価が実態に未追随',
    'Solid results but the stock fell, with no reason in the report — an overlooked candidate (price not yet caught up to fundamentals).',
    '好業績でも株価が下落し、決算に下落理由なし — 株価が実態に未追随の「見過ごされ候補」。'),
 'su_guidance_raise': ('Strong guidance → stock rose', '強気ガイダンスで株高',
    'Current results were weak, but a strong next-year outlook lifted the stock.',
    '当期は減収・減益でも、翌期見通しが強く、株価が上昇した。'),
 'su_turnaround_hope': ('Recovery hope → stock rose', '回復期待で株高（市場先行）',
    'The market looked past the weak results to a recovery and lifted the stock.',
    '当期の弱さは織り込み済みで、市場は回復を先取りして株価を押し上げた。'),
 'su_no_report_reason': ('No report reason → market-driven (enrichment)', '決算に理由なし — 市場要因（enrichment候補）',
    'Weak results, yet the stock rose and the report names no reason — market-driven (enrichment population).',
    '減収・減益でも株価が上昇。決算に理由がなく、市場要因とみられる（enrichment候補）。'),
}

def stock_div_key(c, cat):
    """Stock-reason-led bucket key for the divergent quadrants (R+S−, R−S+); else None."""
    bk = c.get('specific_bucket'); g = c.get('guidance_overlay'); st = c.get('stock_reason_tag')
    if cat == 'RpSm':          # revenue up, stock DOWN → why did it fall?
        if g == 'disappointment': return 'sd_weak_guidance'
        if bk == 'margin_compression_cost_investment': return 'sd_margin_squeeze'
        if bk == 'one_off_gain': return 'sd_oneoff_inflated'
        if st == 'consensus_miss': return 'sd_missed_expectations'
        return 'sd_no_report_reason'
    if cat == 'RmSp':          # revenue down, stock UP → why did it rise?
        if g == 'raise': return 'su_guidance_raise'
        if st == 'rerating_on_growth' or bk in ('one_off_loss', 'one_off_cost_rolloff', 'margin_compression_cost_investment'):
            return 'su_turnaround_hope'
        return 'su_no_report_reason'
    return None


def load_pkt(t):
    p = PKTDIR / f'{t}.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def num(pkt):
    n = pkt.get('numbers', {}) or {}
    ov = n.get('_pit_override') or {}
    pick = lambda k: ov.get(k) if ov.get(k) is not None else n.get(k)
    return pick('rev_pct'), pick('op_pct'), pick('net_pct')


def category_of(rev, net, sd):
    if sd == 'flat':
        return 'flat'
    biz_up = (rev if rev is not None else (net or 0)) > 0 or (net or 0) > 0
    return ('RpSp' if sd == 'up' else 'RpSm') if biz_up else ('RmSp' if sd == 'up' else 'RmSm')


def pct(v): return ('+' if (v or 0) > 0 else '') + f'{v}%' if v is not None else '—'


def chips(c):
    out = []
    g = c.get('guidance_overlay')
    if g in GUID:
        cls = 'chip-guid-weak' if g == 'disappointment' else 'chip-guid-raise'
        out.append(f'<span class="ov-chip {cls}" data-en="{GUID[g][0]}" data-jp="{GUID[g][1]}">{GUID[g][1]}</span>')
    e = c.get('event_overlay')
    if e in EVT:
        out.append(f'<span class="ov-chip chip-event" data-en="{EVT[e][0]}" data-jp="{EVT[e][1]}">{EVT[e][1]}</span>')
    return ' '.join(out)


def card(c, pkt, head=None, biz_ctx=None):
    rev, op, net = num(pkt)
    sp = (pkt.get('prices', {}) or {}).get('pct_change')
    sp_txt = (('+' if (sp or 0) > 0 else '') + f'{sp}%') if sp is not None else '—'
    name = pkt.get('name_jp') or pkt.get('name') or c.get('ticker')
    SECS = [('会社について', 'About the company', 'overview'),
            ('業績について', 'Results this period', 'about_business'),
            ('業績が動いた理由', 'Why the business moved', 'why_business_moved'),
            ('株価が動いた理由', 'Why the stock moved', 'why_stock_moved')]
    body_parts = []
    for jp_h, en_h, field in SECS:
        jt = c.get(field)
        if not jt:
            continue
        et = c.get(field + '_en') or jt        # English (falls back to JP until translated)
        body_parts.append(
            f"<div class='rsec'>"
            f"<div class='rhead' data-en=\"{esc(en_h)}\" data-jp=\"{esc(jp_h)}\">{esc(jp_h)}</div>"
            f"<div class='rtext' data-en=\"{esc(et)}\" data-jp=\"{esc(jt)}\">{esc(jt)}</div></div>")
    body = ''.join(body_parts)

    # ── HEADLINE ──
    bk = c.get('specific_bucket')
    ov = ''
    if head:   # DIVERGENT quadrant: headline = WHY THE STOCK MOVED; business reason as context
        head_en, head_jp = head
        head_line = f"<div class='reason-line' data-en=\"{esc(head_en)}\" data-jp=\"{esc(head_jp)}\">{esc(head_jp)}</div>"
        if biz_ctx:
            ce, cj = biz_ctx
            ov += f"<div class='reason-ov' data-en=\"＋ business: {esc(ce)}\" data-jp=\"＋ 事業の背景: {esc(cj)}\">＋ 事業の背景: {esc(cj)}</div>"
    else:      # ALIGNED quadrant: business one-liner is the headline (it is also the stock reason)
        en1, jp1 = ONELINER.get(bk, (bk, bk))
        head_line = f"<div class='reason-line' data-en=\"{esc(en1)}\" data-jp=\"{esc(jp1)}\">{esc(jp1)}</div>"
        g = c.get('guidance_overlay')
        if g in GUID_LINE:
            ov += f"<div class='reason-ov' data-en=\"＋ {esc(GUID_LINE[g][0])}\" data-jp=\"＋ {esc(GUID_LINE[g][1])}\">＋ {esc(GUID_LINE[g][1])}</div>"
    e = c.get('event_overlay')
    if e in EVT_LINE:
        ov += f"<div class='reason-ov' data-en=\"＋ {esc(EVT_LINE[e][0])}\" data-jp=\"＋ {esc(EVT_LINE[e][1])}\">＋ {esc(EVT_LINE[e][1])}</div>"
    # evidence: the company's own 短信 quote, right under the headline
    gq = c.get('bucket_grounding') or ''
    ev_block = ''
    if gq:
        gq_en = c.get('bucket_grounding_en') or gq
        ev_block += (f"<div class='reason-evidence' data-en=\"{esc('Evidence (earnings report): ' + gq_en[:240])}\" "
                     f"data-jp=\"{esc('根拠（決算短信）: ' + gq[:240])}\">根拠（決算短信）: {esc(gq[:220])}</div>")
    eq = c.get('event_quote') or ''
    if eq:
        eq_en = c.get('event_quote_en') or eq
        ev_block += (f"<div class='reason-evidence' data-en=\"{esc('Event evidence: ' + eq_en[:180])}\" "
                     f"data-jp=\"{esc('イベント根拠: ' + eq[:160])}\">イベント根拠: {esc(eq[:160])}</div>")
    mech = f"<div class='mech-tag'>{esc(bk)} · {esc(c.get('business_reason_tag',''))}×{esc(c.get('stock_reason_tag',''))}</div>"
    return f'''
    <div class="company-row collapsed" onclick="toggleCompany(this, event)">
      <div class="company-head">
        <span class="ticker">{esc(c.get('ticker'))}</span>
        <span class="company-name">{esc(name)}</span>
        <span class="company-meta">{chips(c)}
          <span class="badge sub">FY末 {esc(pkt.get('period_end',''))}</span>
          <span class="badge size">発表 {esc(pkt.get('announce_date',''))}</span>
        </span>
        <span class="expand-icon">▸</span>
      </div>
      <div class="company-data">
        <span class="data-item"><span class="data-label">Revenue:</span> {esc(pct(rev))}</span>
        <span class="data-item"><span class="data-label">Op:</span> {esc(pct(op))}</span>
        <span class="data-item"><span class="data-label">Net:</span> {esc(pct(net))}</span>
        <span class="data-item"><span class="data-label">Stock:</span> <b>{esc(sp_txt)}</b></span>
      </div>
      <div class="reason-block">{head_line}{ov}{ev_block}{mech}</div>
      <div class="company-body"><div class="genuine-research"><div class="genuine-body">{body}</div></div></div>
    </div>'''


def main():
    comps = json.loads(STAGED.read_text(encoding='utf-8'))['companies']
    groups = {k: {} for k in CATS}
    for c in comps.values():
        if not c.get('specific_bucket'):
            continue
        pkt = load_pkt(c['ticker'])
        rev, op, net = num(pkt)
        sd = (pkt.get('prices', {}) or {}).get('stock_dir', 'flat')
        cat = category_of(rev, net, sd)
        sdk = stock_div_key(c, cat)   # divergent quadrants → group by the STOCK reason
        if sdk:
            groups[cat].setdefault(sdk, []).append(
                card(c, pkt, head=(STOCK_DIV[sdk][2], STOCK_DIV[sdk][3]), biz_ctx=ONELINER.get(c['specific_bucket'])))
        else:
            groups[cat].setdefault(c['specific_bucket'], []).append(card(c, pkt))

    present = [k for k in CAT_ORDER if groups[k]]
    tabs, panes = [], []
    for i, k in enumerate(present):
        total = sum(len(v) for v in groups[k].values())
        active = ' active' if i == 0 else ''
        code = CATS[k][0].split(' — ')[0]
        tabs.append(f'<button class="tab{active}" data-cat="{k}" onclick="showCat(this)">'
                    f'<span class="tab-code">{esc(code)}</span> <span class="tab-desc">{esc(CATS[k][0])}</span>'
                    f'<span class="tab-count">{total}</span></button>')
        # sort buckets by size desc within quadrant
        bks = sorted(groups[k].items(), key=lambda kv: -len(kv[1]))
        buckets_html = ''
        for bkey, cards in bks:
            if bkey in STOCK_DIV:                                    # divergent quadrant: stock-reason heading
                short_en, short_ja, en1, jp1 = STOCK_DIV[bkey]
            else:
                short_en, short_ja = LABELS.get(bkey, (bkey, bkey))  # short label → small chip
                en1, jp1 = ONELINER.get(bkey, (short_en, short_ja))  # plain one-liner → the heading
            buckets_html += (f'<details class="reason-bucket"><summary>'
                             f'<span class="bucket-toggle-icon">▸</span>'
                             f'<span class="bucket-title" data-title-en="{esc(en1)}" data-title-jp="{esc(jp1)}">{esc(jp1)}</span>'
                             f'<span class="bucket-shorttag">{esc(short_ja)}</span>'
                             f'<span class="bucket-count">{len(cards)} 件</span></summary>'
                             f'<div class="bucket-cards">{"".join(cards)}</div></details>')
        panes.append(f'<div class="cat-pane" data-cat="{k}" style="display:{ "block" if i==0 else "none"};">{buckets_html}</div>')

    banner_jp = ('⚠️ PROVISIONAL — 構造提案（中町氏の承認待ち）。コミットなし・取り消し容易。'
                 '【整合の象限（R+S+ / R−S−）】事業理由（specific_bucket）が見出し＝株価理由も兼ねる。'
                 '【乖離の象限（R+S− / R−S+）】見出しは「なぜ株価が動いたか」（弱いガイダンス／採算悪化／一過性／'
                 '期待未達※自社計画比は確定チェック待ち／決算に理由なし＝enrichment候補）で、事業理由は背景に表示。'
                 'ガイダンス・イベントは"重ね(overlay)"。backlog_shiftは0件で不採用。')
    banner_en = ('⚠️ PROVISIONAL — structural proposal, awaiting senior approval. Nothing committed, easily reverted. '
                 'ALIGNED quadrants (R+S+/R−S−): the business reason is the heading (it is also the stock reason). '
                 'DIVERGENT quadrants (R+S−/R−S+): the heading is WHY THE STOCK MOVED (weak guidance / margin squeeze / '
                 'one-off-inflated / below-expectations[vs own-plan: TBC] / no-report-reason = enrichment candidate), '
                 'with the business reason shown as context. Guidance & events are overlays; backlog_shift dropped (0).')
    banner = (f'<div class="provo-banner" data-en="{esc(banner_en)}" data-jp="{esc(banner_jp)}" '
              'style="background:#fff5e6;border:1px solid #e6a23c;border-radius:8px;padding:10px 14px;'
              f'margin:10px 0;font-size:13px;color:#8a5a00;font-weight:600;">{esc(banner_jp)}</div>')
    tab_js = '''<script>
function showCat(b){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));b.classList.add('active');
var k=b.getAttribute('data-cat');document.querySelectorAll('.cat-pane').forEach(p=>{p.style.display=p.getAttribute('data-cat')===k?'block':'none';});}
// Comprehensive EN/JP swap: every element carrying both data-en and data-jp (headlines,
// section headers, narratives, evidence, chips, header) plus bucket-title (data-title-*).
function setLangFull(lang){
  document.querySelectorAll('[data-en][data-jp]').forEach(function(el){
    var v=el.getAttribute('data-'+lang); if(v!=null) el.textContent=v;
  });
  document.querySelectorAll('.bucket-title[data-title-en]').forEach(function(el){
    var v=el.getAttribute('data-title-'+lang); if(v!=null) el.textContent=v;
  });
  document.querySelectorAll('.lang-btn').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-lang')===lang);
  });
  document.documentElement.setAttribute('lang', lang);
}
document.addEventListener('DOMContentLoaded',function(){
  document.querySelectorAll('.lang-btn').forEach(function(b){
    b.addEventListener('click',function(){ setLangFull(b.getAttribute('data-lang')); });
  });
});
</script>'''
    body = f'''<body>
<header class="page-header">
  <h1 data-en="IT {YEAR} Q4 — 26-bucket specific-reason view (PROVISIONAL)" data-jp="IT {YEAR} Q4 — 26バケット具体理由ビュー（PROVISIONAL）">IT {YEAR} Q4 — 26バケット具体理由ビュー（PROVISIONAL）</h1>
  <div class="subtitle" data-en="Information &amp; Communication · FY{YEAR} full-year · {len(comps)} companies · stock move verified (Tempest) · R±×S× × specific_bucket × overlay (guidance/event)" data-jp="情報・通信業 · {YEAR}年 通期 · {len(comps)}社 · 株価検証済み(Tempest) · R±×S× × specific_bucket × overlay(guidance/event)">情報・通信業 · {YEAR}年 通期 · {len(comps)}社 · 株価検証済み(Tempest) · R±×S× × specific_bucket × overlay(guidance/event)</div>
  <div class="lang-toggle"><button class="lang-btn" data-lang="en">EN</button><button class="lang-btn active" data-lang="jp">日本語</button></div>
</header>
<div class="container"><div class="sector-pane" style="display:block;">{banner}
  <div class="tabs" role="tablist">{''.join(tabs)}</div>
  <div class="tab-content" data-active="true">{''.join(panes)}</div>
</div></div>
{js_block}
{tab_js}
</body></html>'''
    out_html = f'''<!DOCTYPE html><html lang="jp"><head><meta charset="utf-8">
<title>IT {YEAR} Q4 specific-bucket (provisional)</title>{style_block}
<style>
.rsec{{margin:10px 0;}} .rhead{{font-size:12.5px;font-weight:700;color:#1f7a4a;margin-bottom:3px;}}
.rtext{{font-size:13px;line-height:1.7;color:#1a1a1a;}} .rmeta{{font-size:11.5px;color:#777;border-top:1px dashed #ddd;padding-top:8px;}}
.rmeta .rhead{{display:none;}} .tab-code{{font-weight:800;color:#1f7a4a;margin-right:6px;}} .tab-desc{{font-size:12px;color:#555;}}
.ov-chip{{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:10px;margin-right:4px;font-weight:700;}}
.chip-guid-weak{{background:#fde2e2;color:#a33;}} .chip-guid-raise{{background:#e2f3e8;color:#1f7a4a;}}
.chip-event{{background:#e8eefc;color:#3355bb;}}
.reason-block{{margin:4px 0 2px;padding:8px 10px;background:#f6f9f7;border-left:3px solid #1f7a4a;border-radius:4px;}}
.reason-line{{font-size:14px;font-weight:700;color:#16314a;line-height:1.5;}}
.reason-ov{{font-size:12.5px;color:#3a6;margin-top:3px;font-weight:600;}}
.reason-evidence{{font-size:11.5px;color:#667;margin-top:6px;line-height:1.55;border-top:1px dashed #dde;padding-top:5px;}}
.mech-tag{{font-size:10px;color:#aab;margin-top:5px;font-family:monospace;}}
.reason-bucket > summary .bucket-title{{font-size:14.5px;font-weight:700;color:#16314a;line-height:1.5;white-space:normal;}}
.bucket-shorttag{{display:inline-block;font-size:10.5px;color:#789;background:#eef2f5;border-radius:9px;padding:1px 8px;margin-left:8px;font-weight:600;vertical-align:middle;}}
</style></head>{body}'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out_html, encoding='utf-8')
    print(f'Written: {OUT.name} ({len(comps)} companies, {len(present)} quadrants)')


if __name__ == '__main__':
    main()
