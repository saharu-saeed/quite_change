"""2025 reason-grouped classification view (Nakamachi 2026-06-04 brief).

Reshape of existing 2025 classifications — no re-classification, no new
logic. Filters to 2025 only, keeps only R+ (revenue-up) companies,
splits by S+/S-, groups by reason bucket. R+×S- foregrounded.

Definition (per Nakamachi):
- R+ = revenue up YoY (loose — includes 業績◎ all-up AND 業績=mixed
  records where rev is up but profit is down; the profit picture goes
  into the reason text, not into the filter)
- S+ = stock up >5% YoY; S- = stock down or flat
- R- (revenue down) is filtered out of the view (data preserved)
"""
from __future__ import annotations
import json, glob, sys, io, csv, html
from pathlib import Path
from collections import defaultdict

# Reconfigure stdout for utf-8 — only when run as a script, not on import.
# On import (e.g. by build_unified_view.py) the parent process / unified runner
# handles encoding; modifying sys.stdout here would break stdout for the importer.
if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ───── Path layout ─────
# Directory structure (relative to this script's grandparent = project root):
#   <project_root>/
#     build/build_view.py                ← THIS FILE
#     data/
#       company_research_2025.json       ← per-company JP+EN narratives
#       it_census_universe.csv           ← ticker → name / sub_type / size_band
#       parser_outputs/parser_output_*.json  ← fixture data for each company
#     deliverables/
#       R_PLUS_2025_view.html            ← output (regenerated)
#       R_PLUS_2025_view.csv             ← output (regenerated)
HERE = Path(__file__).parent                    # build/
ROOT = HERE.parent                              # project root (quite_change/)
DATA = ROOT / 'data'                            # data/
PARSER_OUTPUTS = DATA / 'parser_outputs'        # data/parser_outputs/
DELIVERABLES = ROOT / 'deliverables'            # deliverables/

TARGET_YEAR = 2025

# ───── Genuine company-specific research from JP web searches ─────
# Per-company JP web-search summaries with EN+JP versions and source attribution.
genuine_research: dict[str, dict] = {}
try:
    with open(DATA / 'company_research_2025.json', encoding='utf-8') as fp:
        _raw = json.load(fp)
    for tk, v in _raw.items():
        if tk == '_meta': continue
        genuine_research[tk] = v
except FileNotFoundError:
    pass

# ───── Load census (for sub_type and proper company names) ─────
sub_type_by_ticker: dict[str, str] = {}
size_by_ticker: dict[str, str] = {}
name_by_ticker: dict[str, str] = {}
try:
    with open(DATA / 'it_census_universe.csv', encoding='utf-8') as fp:
        for r in csv.DictReader(fp):
            sub_type_by_ticker[r['ticker']] = r.get('sub_type', '')
            size_by_ticker[r['ticker']] = r.get('size_band', '')
            name_by_ticker[r['ticker']] = r.get('company_name', '')
except FileNotFoundError:
    pass

# Override for batch-1b/batch-1a names where the census CSV ships with
# placeholder text ("name missing — Phase 2 acquisition loop will resolve")
NAME_OVERRIDES = {
    '3653': 'Morpho Inc.',
    '3911': 'Aiming Inc.',
    '3914': 'JIG-SAW株式会社',
    '3915': 'TerraSky Co., Ltd.',
    '3998': 'SuRaLa Net Co., Ltd.',
    '4180': 'Appier Group, Inc.',
    '3762': 'TechMatrix Corporation',
    '3697': 'SHIFT Inc.',
    '3923': 'RAKUS Co., Ltd.',
    '4071': 'Plus Alpha Consulting Co., Ltd.',
    '4165': 'PLAID, Inc.',
    '4194': 'Visional, Inc.',
    '4478': 'freee K.K.',
}
for t, name in NAME_OVERRIDES.items():
    cur = name_by_ticker.get(t, '')
    if not cur or 'name missing' in cur or 'Phase 2' in cur:
        name_by_ticker[t] = name

# Fresh-fetch override (per existing convention)
preferred_map = {
    '3994': 'parser_output_moneyforward_fresh.json',
    '9684': 'parser_output_squareenix_fresh.json',
    '4443': 'parser_output_sansan_fresh.json',
}

all_files = sorted(PARSER_OUTPUTS.glob('parser_output_*.json'))
file_by_ticker: dict[str, Path] = {}
for f in all_files:
    if '_fresh' in f.name or '_tmp_' in f.name: continue
    try: d = json.loads(f.read_text(encoding='utf-8'))
    except Exception: continue
    if not d.get('records'): continue
    ticker = d['records'][0].get('ticker')
    if ticker and ticker not in file_by_ticker:
        file_by_ticker[ticker] = f
for ticker, fname in preferred_map.items():
    p = PARSER_OUTPUTS / fname
    if p.exists():
        file_by_ticker[ticker] = p

# Collect all records + arcs
all_records: list[dict] = []
arcs: dict[str, list[tuple[int, str]]] = defaultdict(list)
for ticker, fp in sorted(file_by_ticker.items()):
    d = json.loads(fp.read_text(encoding='utf-8'))
    if not d.get('records'): continue
    fixture_name = d['records'][0].get('name', '')
    for r in d['records']:
        rec = {
            'ticker': ticker,
            'name': name_by_ticker.get(ticker, fixture_name),
            'year': r.get('year'),
            'biz': r.get('業績'),
            'stk': r.get('株価'),
            'quadrant': r.get('quadrant'),
            'sub_type': sub_type_by_ticker.get(ticker, ''),
            'size': size_by_ticker.get(ticker, ''),
            'rev_dir': r.get('revenue_dir'),
            'op_dir': r.get('op_dir'),
            'net_dir': r.get('net_dir'),
            'stock_yoy_pct': r.get('stock_yoy_pct'),
            'op_abs': r.get('op_abs'),
            'net_abs': r.get('net_abs'),
            'rawExplanation': r.get('rawExplanation', ''),
        }
        all_records.append(rec)
        arcs[ticker].append((rec['year'], rec['quadrant'] or 'unclassified'))
for t in arcs:
    arcs[t] = sorted(arcs[t])

total_tickers_in_library = len(file_by_ticker)


# ───── R+ / S+ direction logic ─────

def r_direction(rec):
    """Returns 'plus', 'minus', or 'unknown'.

    R+ = revenue up (loose) per Nakamachi spec:
      - revenue_dir == 'up' → R+ (clean)
      - 業績 == ◎ → R+ (all-three-up implies rev up)
      - 業績 == 'mixed' AND rev_dir != 'down' → R+ (profit-compression case)
      - revenue_dir == 'down' → R- (drop)
      - 業績 == ✕ AND rev_dir != 'up' → R- (drop)
      - else unknown (conservative — drop)
    """
    rd = rec.get('rev_dir')
    biz = rec.get('biz')
    if rd == 'up':
        return 'plus'
    if rd == 'down':
        return 'minus'
    # rev_dir is None, 'mixed', or 'unknown' — fall back to biz_sign
    if biz == '◎':
        return 'plus'
    if biz == 'mixed' and rd != 'down':
        return 'plus'  # profit-compression case: rev typically up, profit down
    if biz == '✕':
        return 'minus'
    return 'unknown'


def s_direction(rec):
    """S+ = stock up >5% YoY. S- = stock down or flat (anything else)."""
    yoy = rec.get('stock_yoy_pct')
    if yoy is not None:
        return 'plus' if yoy > 5 else 'minus'
    # Fall back to 株価 sign
    stk = rec.get('stk')
    if stk == '◎':
        return 'plus'
    if stk == '✕':
        return 'minus'
    # Default conservative — "stock not catching up" = S- per Nakamachi's framing
    return 'minus'


# ───── Reason bucket classifier (relabel of existing factor patterns) ─────

# Ticker-specific overrides splitting the previously-undifferentiated "Other"
# buckets into clean sub-patterns. These names require company-knowledge
# (read from Round 2 verification + green-block research), not pure rule-data
# — so we map them explicitly here. Applied BEFORE the generic rule classifier
# so the override takes precedence over fallback rules like biz=='mixed'.
TICKER_OVERRIDE_S_MINUS = {
    # Loss-making / thin-margin SaaS de-rated as the market stopped paying for growth-at-any-cost
    '3994': 'saas_derated',          # Money Forward
    '4478': 'saas_derated',          # freee
    '4483': 'saas_derated',          # JMDC
    '4180': 'saas_derated',          # Appier Group
    # Orphan — strong fundamentals but no analyst coverage
    '4475': 'orphan_no_coverage',    # HENNGE
    '4776': 'orphan_no_coverage',    # Cybozu
    '3762': 'orphan_no_coverage',    # TechMatrix
    '6055': 'orphan_no_coverage',    # JAPAN MATERIAL
    # AI disrupted — generative AI is eating the core business model
    '4490': 'ai_disrupted',          # VisasQ
    '4382': 'ai_disrupted',          # HEROZ
    '9759': 'ai_disrupted',          # NSD (AI as threat, not tailwind)
    # Mature giant drifting — stuck between growth and defensive style boxes
    '2121': 'mature_giant',          # MIXI
    '2371': 'mature_giant',          # Kakaku.com
    '4689': 'mature_giant',          # LY Corporation
    # Special situation — one-off corporate / commodity / market-structure event
    '3915': 'special_situation',     # TerraSky (quantum-JV)
    '3825': 'special_situation',     # Remixpoint (crypto/energy volatility)
    '4176': 'special_situation',     # coconala (market-liquidity)
    '4264': 'special_situation',     # Secure (company-specific)
    '4704': 'special_situation',     # Trend Micro (MBO speculation)
}

TICKER_OVERRIDE_S_PLUS = {
    # Activist / corporate-action catalyst — stock moves on who-is-buying, not earnings
    '4676': 'activist_corporate_action',         # Fuji Media (Dalton Investments)
    '9984': 'activist_corporate_action',         # SoftBank Group (OpenAI value crystallization)
    # Profitability inflection — market just started believing in durable margins
    '3923': 'profitability_inflection',          # Rakus (OP margin tripled 7.8% → 26.7%)
    '3853': 'profitability_inflection',          # Asteria (Warp + JPYC, 30% OP margin)
    '8056': 'profitability_inflection',          # BIPROGY (AI productivity doubling)
    # Inbound / demographic tailwind
    '3660': 'inbound_demographic_tailwind',      # istyle (@cosme inbound)
    '3989': 'inbound_demographic_tailwind',      # Sharing Tech (aging society)
    '4431': 'inbound_demographic_tailwind',      # Smaregi (inbound + cashless)
    # Sector-specific tailwind (content / IP / defense)
    '9602': 'sector_specific_tailwind',          # Toho (国宝 film hit)
    '9413': 'sector_specific_tailwind',          # TV Tokyo (anime overseas)
    '9412': 'sector_specific_tailwind',          # SKY Perfect JSAT (Defense Ministry)
}


def reason_bucket(rec, s_dir):
    """Map (record's pattern context, S direction) → reason bucket label.

    Logic order:
    1. Ticker-specific override (if the company has a documented sub-pattern, use it).
    2. Pure-data rules on the record's arc + directional fields.
    3. Safety-net fallback ('other_*') — should not fire if overrides cover all names.
    """
    ticker = rec['ticker']; year = rec['year']

    # Step 1 — ticker-specific override (takes precedence over generic rules)
    if s_dir == 'minus' and ticker in TICKER_OVERRIDE_S_MINUS:
        return TICKER_OVERRIDE_S_MINUS[ticker]
    if s_dir == 'plus' and ticker in TICKER_OVERRIDE_S_PLUS:
        return TICKER_OVERRIDE_S_PLUS[ticker]

    # Step 2 — pure-data rules
    arc = arcs.get(ticker, [])
    arc_qs = {y: q for y, q in arc}
    prior = [arc_qs.get(year - i) for i in range(1, 5)]
    biz = rec.get('biz')
    rev_up = rec.get('rev_dir') == 'up'
    op_up = rec.get('op_dir') == 'up'
    net_up = rec.get('net_dir') == 'up'
    all_up = rev_up and op_up and net_up
    yoy = rec.get('stock_yoy_pct')

    if s_dir == 'minus':
        # R+×S- buckets
        # Mixed records (rev up + profit down): "profit-compression"
        if biz == 'mixed':
            return 'profit_compressed'
        # Durably overlooked: 3+ consec Q2
        consec_q2 = 0
        for p in prior:
            if p == 'Q2': consec_q2 += 1
            else: break
        if consec_q2 >= 2:  # 2 priors + this year = 3+ consec Q2
            return 'durably_overlooked'
        # All-up grower with stock collapsed
        if all_up and yoy is not None and yoy < -30:
            return 'all_up_stock_fell'
        # Step 3 safety net — should not fire if overrides cover all names
        return 'other_under_recognized'
    else:
        # R+×S+ buckets
        consec_q1 = 0
        for p in prior:
            if p == 'Q1': consec_q1 += 1
            else: break
        had_decline = any(p in ('Q3', 'Q4') for p in prior[:2])
        if consec_q1 >= 3:
            return 'sustained_compounder'
        if had_decline:
            return 'recovery_caught_up'
        if all_up and yoy is not None and yoy > 30:
            return 'acceleration_rerating'
        if all_up:
            return 'clean_grower'
        # Step 3 safety net — should not fire if overrides cover all names
        return 'other_grower'


# Reason bucket → display label and short description (with JP translations).
# Notes intentionally use plain language so a reader can understand the pattern in one read.
BUCKET_LABELS = {
    # R+×S- (foreground)
    'durably_overlooked': {
        'title': 'Durably overlooked — multiple business-up years, stock not catching up',
        'title_jp': '持続的に見落とされている — 複数年の業績成長、株価が追いついていない',
        'note': (
            'In plain terms: these companies have grown their business steadily for 3 or more years in a row, but the stock price still has not reflected it. '
            'Rule used: 2 or more prior years tagged "Q2" (business UP, stock DOWN) — which means at least 3 consecutive years of the same mismatch.\n\n'
            'Why this matters: if the market overlooks growth once it could be noise — but overlooking it 3 years running suggests something structural. '
            'Often these are small or mid caps without good analyst coverage, or names sitting in a sector that institutional investors have rotated away from. '
            'If the structural reason resolves (broker coverage starts, sector re-rates, governance improves) the stock can re-rate sharply.\n\n'
            'This is the strongest "asymmetric upside" signal in the four R+×S- groups.'
        ),
        'note_jp': (
            '簡単に言うと:これらの企業は3年以上連続で業績(売上・利益)が伸びているのに、株価がそれを反映していません。'
            '使用ルール:過去2年以上「Q2」タグ(業績↑・株価↓)が続いている = 少なくとも3年連続で同じミスマッチが発生しているということ。\n\n'
            'なぜ重要か:市場が成長を1年見落とすのはノイズかもしれませんが、3年連続で見落とすなら構造的な理由が考えられます。'
            '多くはアナリストのカバレッジが乏しい中小型株や、機関投資家が資金を引き上げたセクターに属する企業です。'
            'もしその構造的な理由が解消すれば(証券会社のカバレッジ開始、セクター再評価、ガバナンス改善など)、株価は急速に再評価される可能性があります。\n\n'
            'R+×S- の4グループの中で最も強い『非対称な上昇余地』のシグナルです。'
        ),
        'order': 1,
    },
    'all_up_stock_fell': {
        'title': 'All financials up, stock still fell — clean mismatch or profit-taking sell-off',
        'title_jp': '全財務指標が上昇、株価は下落 — 純粋なミスマッチまたは利確売り',
        'note': (
            'In plain terms: revenue grew, operating profit grew, AND net profit grew — but the stock STILL fell 30% or more in the year. '
            'Rule used: rev_dir=up, op_dir=up, net_dir=up, AND stock YoY < -30%.\n\n'
            'Why this matters: there is no operational excuse — the gap between fundamentals and price is unusually clean. '
            'The most common explanations are (a) profit-taking after a prior rally that took the stock too far ahead of earnings, '
            '(b) a one-off event scare (regulation rumor, key-person resignation, accounting noise) that did NOT actually affect the business, or '
            '(c) sector rotation pulling capital out indiscriminately.\n\n'
            'These can be the cleanest mean-reversion opportunities — IF you can confirm the scare or rotation is the real cause and the underlying business is still on track.'
        ),
        'note_jp': (
            '簡単に言うと:売上が伸び、営業利益も伸び、純利益も伸びました — それでも株価は年間30%以上下落しました。'
            '使用ルール:売上方向=上昇、営業利益方向=上昇、純利益方向=上昇、かつ株価前年比 < -30%。\n\n'
            'なぜ重要か:業績面での言い訳が見当たらず、ファンダメンタルズと株価のギャップが特にクリーン。'
            '最もよくある理由は (a) 過去の上昇で株価が業績を大きく先取りした後の利確売り、'
            '(b) 一過性のイベント懸念(規制の噂・キーパーソン辞任・会計ノイズなど)が実態に影響していないケース、'
            '(c) セクター・ローテーションによる無差別な資金引き上げ — のいずれか。\n\n'
            '最もクリーンな平均回帰の機会になり得ます — ただし懸念やローテーションが本当の原因で、原業績が依然順調であることを確認する必要があります。'
        ),
        'order': 2,
    },
    'profit_compressed': {
        'title': 'Revenue up, profit compressed — derated on margins, potentially recoverable',
        'title_jp': '売上↑・利益圧縮 — マージンでデレーティング、回復可能性あり',
        'note': (
            'In plain terms: revenue keeps growing, but operating margins have been squeezed. '
            'Rule used: 業績 sign = "mixed" (= revenue up, but operating profit OR net profit down).\n\n'
            'Why this matters: the squeeze is usually one of four things — '
            '(a) up-front investment (R&D, marketing, hiring) that depresses current profit but builds future revenue, '
            '(b) input-cost inflation (wages, materials, energy), '
            '(c) pricing pressure from competition, or '
            '(d) FX / one-off impairments. '
            'The market has marked the multiple DOWN because earnings look weaker, but the business still has top-line momentum.\n\n'
            'What to watch: the margin trend in the next 2-3 quarters. If management has a credible cost or pricing plan, margin recovery often triggers a sharp re-rating because both EPS and the multiple rise together. '
            'This is the "patient money" cohort — recovery typically takes 1-2 years.'
        ),
        'note_jp': (
            '簡単に言うと:売上は伸び続けているものの、営業利益率が圧縮されています。'
            '使用ルール:業績符号 = 「mixed(まちまち)」 = 売上は上昇だが、営業利益または純利益のいずれかが下落。\n\n'
            'なぜ重要か:利益圧縮の原因は通常4つのうちのいずれか — '
            '(a) 先行投資(研究開発・マーケティング・採用)が当期利益を圧迫しつつも将来の売上を構築している、'
            '(b) 投入コストのインフレ(賃金・原材料・エネルギー)、'
            '(c) 競合からの価格圧力、'
            '(d) 為替・一過性の減損。'
            '市場は利益が弱く見えるため評価倍率を下げましたが、トップライン(売上)のモメンタムは健在です。\n\n'
            '注視点:今後2-3四半期のマージン推移。経営側に信頼できるコスト・価格戦略があれば、マージン回復がEPSと評価倍率の双方を同時に押し上げ、急速な再評価につながることが多いです。'
            '『辛抱強い資金(patient money)』向けのコホート — 回復には通常1-2年かかります。'
        ),
        'order': 3,
    },
    'macro_derating': {
        'title': 'Macro derating — fundamentals fine, stock fell with the sector',
        'title_jp': 'マクロ・デレーティング — ファンダメンタルズは健全、セクターと共に株価下落',
        'note': (
            'In plain terms: the company itself is fine — but the entire sector got marked down by something outside the company\'s control. '
            'Typical macro causes: a sudden rate shock (2022-style), regulatory change affecting the sector, theme rotation (e.g. money leaving growth, flowing into value), or geopolitical risk concentrated in the sector.\n\n'
            'Why this matters: the mismatch is NOT company-specific. The sector dragged the stock down with it, even though the underlying business is performing. '
            'These names typically re-rate when the macro cause reverses or fades — but timing is hard to call because it depends on macro conditions, not company actions.\n\n'
            'Note: this bucket is reserved for sector-wide derating events. In the 2025 single-year view it does not actively fire because 2025 was not a macro-shock year for Japanese IT-cohort.'
        ),
        'note_jp': (
            '簡単に言うと:企業自体は健全 — しかしセクター全体が、企業のコントロール外の要因で評価を下げられました。'
            '典型的なマクロ要因:急な金利ショック(2022年型)、セクターに影響する規制変更、テーマ・ローテーション(例:資金がグロースから流出してバリューに流入)、セクター集中型の地政学リスクなど。\n\n'
            'なぜ重要か:ミスマッチは企業固有のものではありません。原業績は順調にもかかわらず、セクター全体が株価を引き下げています。'
            'これらの銘柄は通常、マクロ要因が逆転または消えた時に再評価されます — ただしタイミング予測は難しく、企業のアクションではなくマクロ環境次第。\n\n'
            '注記:このバケットはセクター全体のデレーティング・イベント用に予約されています。2025年単年ビューでは、2025年が日本IT銘柄群にとってマクロ・ショック年ではなかったため、実際には発火していません。'
        ),
        'order': 4,
    },
    # NEW R+×S- sub-buckets (split from the previous "Other under-recognized")
    'saas_derated': {
        'title': 'Loss-making SaaS de-rated — market stopped paying for "growth-at-any-cost"',
        'title_jp': '赤字SaaSが評価切り下げ — 市場が『成長至上主義』を止めた',
        'note': (
            'In plain terms: high-PER SaaS companies that grew revenue strongly but kept posting losses or thin margins. '
            'The market stopped tolerating "growth at any cost" and rotated capital out of the cohort. '
            'Examples in this bucket: Money Forward, freee, JMDC, Appier Group.\n\n'
            'Rule used: ticker-specific override for documented loss-making / thin-margin SaaS names.\n\n'
            'Why this matters: this is a cohort-wide derating, not company-specific failure. '
            'Industry commentary even labels it "SaaSの死" (the death of SaaS) — investors shifted from "growth-only" to "Rule of 40" '
            '(revenue growth + operating margin ≥ 40%) as the new bar. '
            'If these companies pivot to profitability or hit the Rule of 40 milestone, the cohort can re-rate together.\n\n'
            'What to watch: management language shifting from growth-only to profitability, the first quarter of sustained GAAP profit, '
            'and broker upgrades that follow a clean margin print.'
        ),
        'note_jp': (
            '簡単に言うと:売上は強く伸びたものの赤字や薄利を続けた高PER SaaS企業群。'
            '市場が『成長至上主義』の評価を止め、コホート全体から資金を引き上げました。'
            'このバケットの例:マネーフォワード、freee、JMDC、Appier Group。\n\n'
            '使用ルール:既知の赤字／薄利SaaS銘柄をティッカー単位で振り分け。\n\n'
            'なぜ重要か:これはコホート全体のデレーティングであり、個社の失敗ではありません。'
            '業界では『SaaSの死』と表現する声もあり、投資家は『成長一辺倒』から『Rule of 40』'
            '(売上成長率＋営業利益率 ≥ 40%)を新基準としています。'
            'もしこれらの企業が黒字化に転じる、もしくは Rule of 40 を達成すれば、コホート全体が再評価される可能性があります。\n\n'
            '注視点:経営陣の発言が『成長一辺倒』から『収益性』へ移るか、GAAP黒字の最初の四半期、そしてマージン発表後の証券会社の格上げ。'
        ),
        'order': 4,
    },
    'orphan_no_coverage': {
        'title': 'Orphan — strong fundamentals but no analyst coverage',
        'title_jp': '孤児株 — 業績は健全だがアナリスト・カバレッジなし',
        'note': (
            'In plain terms: companies whose business is performing well — but almost no broker covers them and institutional ownership is near zero. '
            'The stock drifts because there is simply nobody telling the story to capital allocators. '
            'Examples in this bucket: HENNGE, Cybozu, TechMatrix, JAPAN MATERIAL.\n\n'
            'Rule used: ticker-specific override for names with documented coverage gaps and small institutional ownership.\n\n'
            'Why this matters: about 70% of TSE-listed companies have ZERO analyst coverage (industry stat). '
            'When growth is durable but nobody writes about it, the stock can stay cheap for years. '
            'But the trigger is mechanical — when ONE broker initiates coverage with a Buy, the pool of potential buyers expands overnight and the stock can re-rate sharply.\n\n'
            'What to watch: new broker initiations, IR-activity ramp-up (English presentations, overseas NDRs), '
            'TSE PBR-improvement disclosure progress, and any change in cross-shareholding that could free up float.'
        ),
        'note_jp': (
            '簡単に言うと:業績は順調なのに、ほぼどの証券会社にもカバーされておらず、機関投資家保有もゼロに近い企業群。'
            '物語を機関投資家に伝える人がいないため、株価は漂流し続けます。'
            'このバケットの例:HENNGE、サイボウズ、テックマトリックス、JAPAN MATERIAL。\n\n'
            '使用ルール:カバレッジギャップが確認されている銘柄をティッカー単位で振り分け。\n\n'
            'なぜ重要か:東証上場企業の約70%はアナリスト・カバレッジがゼロ(業界統計)。'
            '持続的成長があっても、誰も書かなければ株価は何年も割安のまま。'
            'しかしトリガーは機械的 — 1社のアナリストが買い推奨でカバレッジを開始するだけで、買い手の母集団が一夜にして拡大し、株価が急速に再評価されることがあります。\n\n'
            '注視点:新規証券会社のカバレッジ開始、IR活動の活発化(英語IR、海外NDR)、東証PBR改善開示の進展、政策保有解消による浮動株増加。'
        ),
        'order': 5,
    },
    'ai_disrupted': {
        'title': 'AI disrupted — business model directly threatened by generative AI',
        'title_jp': 'AI破壊 — 生成AIにビジネスモデルが直接脅かされている',
        'note': (
            'In plain terms: companies whose core business is being eaten by generative AI. '
            'Not "AI will help them" — "AI will replace what they do." '
            'Examples in this bucket: VisasQ (expert-consulting platform competing with AI search), HEROZ (legacy AI software leapfrogged by LLMs), '
            'NSD (person-month SI where AI compresses the engineer-hour cost they bill).\n\n'
            'Rule used: ticker-specific override for names where Round 2 verification documented AI as a structural threat to the business model.\n\n'
            'Why this matters: the derating is not a temporary glitch — it is the market re-pricing the long-term TAM (total addressable market) of these businesses. '
            'These stocks can stay cheap for years unless the company successfully pivots to "AI-augmented" services or finds a defensible niche '
            '(proprietary data moats, regulated industry barriers, etc.).\n\n'
            'What to watch: explicit AI-strategy pivots from management, partnerships with AI infrastructure players (OpenAI, Anthropic, hyperscalers), '
            'and the competitive response (price cuts, service redesign, new product launches).'
        ),
        'note_jp': (
            '簡単に言うと:中核ビジネスが生成AIに食われている企業群。'
            '『AIが助けてくれる』ではなく『AIが自分たちの仕事を置き換える』立場。'
            'このバケットの例:ビザスク(AI検索と競合するエキスパート・コンサル・プラットフォーム)、HEROZ(LLMに追い越された旧世代AIソフトウェア)、'
            'NSD(AIにより請求エンジニア工数が圧縮されている準委任型SI)。\n\n'
            '使用ルール:Round 2 検証でAIが構造的脅威と確認された銘柄をティッカー単位で振り分け。\n\n'
            'なぜ重要か:このデレーティングは一時的な揺らぎではなく、市場がこれらの企業の長期TAM(獲得可能な市場規模)を見直しているもの。'
            '『AIに補強される』サービスへの転換に成功するか、防御可能なニッチ(独自データの堀、規制業種の参入障壁など)を見つけない限り、株価は何年も割安のまま。\n\n'
            '注視点:経営陣の明確なAI戦略転換、AIインフラ事業者(OpenAI、Anthropic、ハイパースケーラー)との提携、競争対応(値下げ、サービス再設計、新製品投入)。'
        ),
        'order': 6,
    },
    'mature_giant': {
        'title': 'Mature giant drifting — too slow for growth money, not safe enough for defensive money',
        'title_jp': '成熟巨人の漂流 — グロース資金には遅く、ディフェンシブ資金には不十分',
        'note': (
            'In plain terms: big established companies that grew revenue but the stock barely moved — or drifted lower. '
            'They are too slow for growth-seeking capital (revenue +3-5% is uninspiring) but they may not be defensive enough — '
            'earnings still swing with the consumer / ad / tech cycle. '
            'Examples in this bucket: MIXI, Kakaku.com, LY Corporation.\n\n'
            'Rule used: ticker-specific override for names whose stock-business gap reflects being "stuck in the middle" of investor style boxes.\n\n'
            'Why this matters: these are often "good but not great" investments. '
            'They generate cash, pay dividends, and rarely make headlines — but capital allocators have nowhere to put them in their style buckets, so they drift. '
            'A meaningful catalyst (buyback acceleration, special dividend, business split, M&A, activist arrival) can move them out of this zone.\n\n'
            'What to watch: TSE PBR-improvement disclosures, capital allocation policy changes, '
            'and any signal that the company is reframing itself for one specific investor style (yield / value / growth).'
        ),
        'note_jp': (
            '簡単に言うと:売上は伸びたものの株価がほぼ動かなかった、あるいは下方漂流した大型確立企業群。'
            '成長重視の資金にとってはペースが遅く(売上+3〜5%は物足りない)、それでいてディフェンシブとも言い切れない — 利益は消費・広告・テクノロジー景気と共に揺れます。'
            'このバケットの例:MIXI、価格.com、LYコーポレーション。\n\n'
            '使用ルール:スタイル・ボックスのいずれにも明確に収まらない銘柄をティッカー単位で振り分け。\n\n'
            'なぜ重要か:これらは『良いけど突出はしない』投資対象になりがち。'
            'キャッシュフローを生み、配当も払い、ニュースもあまりないが、機関投資家のスタイル分類で居場所がなく漂流します。'
            '意味ある触媒(自社株買い加速、特別配当、事業分割、M&A、アクティビスト参入)があれば、このゾーンから抜け出せます。\n\n'
            '注視点:東証PBR改善開示、資本配分方針の変更、特定の投資家スタイル(配当／バリュー／グロース)に合わせた企業のリフレーミング。'
        ),
        'order': 7,
    },
    'special_situation': {
        'title': 'Special situation — one-off corporate, commodity, or market-structure event',
        'title_jp': '特殊状況 — 一過性のコーポレート・商品・市場構造イベント',
        'note': (
            'In plain terms: the company grew revenue but the stock fell because of a specific one-time event — not a broad pattern. '
            'Examples in this bucket: TerraSky (a quantum-computing JV the market is still digesting), Remixpoint (crypto/energy price volatility wagging the tail), '
            'coconala (market-microstructure liquidity collapse), Secure (company-specific operational issues), Trend Micro (MBO speculation reversal).\n\n'
            'Rule used: ticker-specific override for names with documented one-off drivers.\n\n'
            'Why this matters: these are NOT pattern trades — they are event trades. '
            'Each name needs an individual deep dive into the specific event, its expected resolution timeline, and whether the impact is reversible. '
            'Do NOT treat them as a group thesis.\n\n'
            'What to watch: the event-specific resolution timeline per name '
            '(JV milestones for TerraSky, commodity prices for Remixpoint, MBO process steps for Trend Micro, daily liquidity tape for coconala).'
        ),
        'note_jp': (
            '簡単に言うと:売上は伸びたものの、広いパターンではなく特定の一過性イベントを理由に株価が下落した銘柄群。'
            'このバケットの例:テラスカイ(市場が消化中の量子コンピューティングJV発表)、Remixpoint(暗号資産／エネルギー価格の変動が業績を揺らす)、'
            'ココナラ(市場マイクロ構造での流動性崩壊)、Secure(個社の運営問題)、トレンドマイクロ(MBO期待の反転)。\n\n'
            '使用ルール:一過性ドライバーが確認されている銘柄をティッカー単位で振り分け。\n\n'
            'なぜ重要か:これらはパターン・トレードではなく、イベント・トレード。'
            '各銘柄ごとに、具体的なイベント・予想される解決タイムライン・影響の可逆性を個別に深掘りする必要があります。'
            'グループ・テーゼとして扱ってはいけません。\n\n'
            '注視点:銘柄ごとのイベント解決タイムライン'
            '(テラスカイのJVマイルストーン、Remixpointの商品価格、トレンドマイクロのMBOプロセス、ココナラの日次出来高動向)。'
        ),
        'order': 8,
    },
    # Safety net (should have 0 names if overrides are complete; left for defense)
    'other_under_recognized': {
        'title': 'Other under-recognized',
        'title_jp': 'その他の見落とし候補',
        'note': (
            'Safety-net bucket. Should not normally render — if it does, it means a new ticker entered the R+×S- universe without a sub-bucket override.'
        ),
        'note_jp': (
            'セーフティネット・バケット。通常表示されないはず — 表示される場合は、新規ティッカーがサブバケット・オーバーライドなしでR+×S-ユニバースに入った可能性があります。'
        ),
        'order': 99,
    },
    # R+×S+ (secondary)
    'sustained_compounder': {
        'title': 'Sustained compounder',
        'title_jp': '持続的コンパウンダー(複利成長企業)',
        'note': (
            'In plain terms: this company has put up "all-three-up" results (revenue, operating profit, net profit all up) for 3 or more years in a row, AND the stock has tracked that compounding growth each year. '
            'Rule used: 3 or more consecutive Q1 years (Q1 = all-three-up + stock-up).\n\n'
            'Why this matters: the market has clearly recognized the quality of durable growth, and rewards it consistently. '
            'These names typically trade at premium multiples (high PER), but the multiple is justified by the consistency. '
            'The downside is concentrated in moments where the streak might break — disappointment after long success can trigger sharp corrections.\n\n'
            'What to watch: any signal that the multi-year growth streak is slowing (single-quarter miss, guidance cut, key customer loss). '
            'As long as the streak continues, the simple decision is to hold and watch the compounding.'
        ),
        'note_jp': (
            '簡単に言うと:これらの企業は3年以上連続で『売上・営業利益・純利益すべて上昇』という結果を出しており、株価もその複利成長を毎年追っています。'
            '使用ルール:3年以上連続のQ1(Q1 = 全3指標↑+株価↑)。\n\n'
            'なぜ重要か:市場が持続的な質の高い成長を明確に認識し、継続的に評価しています。'
            'これらの銘柄は通常プレミアム評価(高PER)で取引されますが、その倍率は『継続性』によって正当化されています。'
            'リスクは、連続記録が途切れる瞬間に集中する点 — 長期成功後の失望は急落を招きやすい。\n\n'
            '注視点:多年連続成長が鈍化する兆候(単四半期未達、ガイダンス引き下げ、主要顧客喪失など)。'
            '記録が続く限り、シンプルな判断は『保有して複利を見守る』ことです。'
        ),
        'order': 1,
    },
    'recovery_caught_up': {
        'title': 'Recovery caught up',
        'title_jp': '回復に市場が追いついた',
        'note': (
            'In plain terms: the company had a soft year recently (revenue or profit fell), and this year it has turned and grown again — and the stock has confirmed the turnaround. '
            'Rule used: prior 1-2 years had a Q3 or Q4 tag (decline year), current year is Q1 (all-up).\n\n'
            'Why this matters: the pattern is "V-recovery validated by the market." '
            'These companies are often coming out of an investment cycle (R&D harvest, capex commissioning), a product transition (new platform launching), or post-restructuring. '
            'The market has now priced the recovery in, which means much of the easy gains may be behind.\n\n'
            'What to watch: whether the recovery sustains for a second year (= candidate for the sustained-compounder bucket next year), or fades back into mixed results. '
            'These names sit between "early-stage compounders" and "one-year bounces."'
        ),
        'note_jp': (
            '簡単に言うと:企業は最近に減速期(売上または利益の減少)を経験し、今年再び反転・成長しました — そして株価がそのターンアラウンドを確認しています。'
            '使用ルール:過去1-2年にQ3またはQ4タグ(減速年)、当年はQ1(全項目↑)。\n\n'
            'なぜ重要か:『V字回復が市場に確認された』パターンです。'
            'これらの企業は通常、投資サイクル明け(R&D投資の回収開始、設備投資の稼働)、製品移行期(新プラットフォーム立ち上げ)、リストラ後の回復期にあります。'
            '市場は既に回復を織り込んでおり、大幅な値上がりはおおむね背後に終わった可能性があります。\n\n'
            '注視点:回復が2年目も続くか(= 翌年は持続的コンパウンダー候補)、それともまちまちの結果に戻るか。'
            'これらの銘柄は『初期段階コンパウンダー』と『1年限りの反発』の中間に位置します。'
        ),
        'order': 2,
    },
    'acceleration_rerating': {
        'title': 'Acceleration + re-rating',
        'title_jp': '加速＋再評価',
        'note': (
            'In plain terms: all three financials (revenue, operating profit, net profit) are up AND the stock has surged 30% or more in a year. '
            'Rule used: rev_dir=up, op_dir=up, net_dir=up, AND stock YoY > +30%.\n\n'
            'Why this matters: the market has NOT just followed the business — it has actively re-rated the company. '
            'There is usually a specific catalyst behind the re-rating: AI exposure (the stock is suddenly a "play" on a hot theme), activist pressure forcing capital return, '
            'a new product cycle (game release, drug approval), a major dividend hike or buyback announcement, M&A speculation, or a strategic partnership.\n\n'
            'What to watch: these are high-conviction stories but also higher risk — '
            'if the catalyst fails to deliver (AI hype cools, activist proposal rejected, product disappoints), the re-rating can unwind quickly. '
            'Verify which specific catalyst is driving the stock and whether it has staying power.'
        ),
        'note_jp': (
            '簡単に言うと:売上・営業利益・純利益のすべてが上昇し、加えて株価が年間30%以上急騰しています。'
            '使用ルール:売上方向=上昇、営業利益方向=上昇、純利益方向=上昇、かつ株価前年比 > +30%。\n\n'
            'なぜ重要か:市場は単に業績を追随しているのではなく、企業を能動的に再評価しています。'
            '通常、明確な触媒があります:AI関連(突如『AIのプレイ銘柄』として注目される)、アクティビスト圧力による資本還元強要、'
            '新製品サイクル(ゲーム発売・薬の承認)、大幅な増配や自社株買い発表、M&A思惑、戦略的提携など。\n\n'
            '注視点:これらは高信念ストーリーですが、リスクも高い — '
            '触媒が期待通りに進まなければ(AIブーム冷却、アクティビスト提案否決、製品失望など)、再評価が急速に巻き戻る可能性があります。'
            'どの具体的な触媒が株価を動かしているか、その持続力を必ず確認してください。'
        ),
        'order': 3,
    },
    'clean_grower': {
        'title': 'Clean grower, market followed',
        'title_jp': 'クリーングロワー、市場が追随',
        'note': (
            'In plain terms: all-three-up business with the stock moving moderately up too — no surprises, no drama. '
            'Rule used: all three financials up, stock up but NOT by 30%+, and no multi-year compounder streak yet.\n\n'
            'Why this matters: steady, predictable growth where the stock follows earnings WITHOUT significant re-rating. '
            'These are typically established mid or large caps with stable competitive positions, mature business models, and dependable shareholder return policies. '
            'The "boring is beautiful" cohort — they rarely make headlines but they reliably deliver.\n\n'
            'What to watch: any change in capital allocation (large M&A, big new investment), or a slowdown in revenue/profit growth that could turn this into a "profit_compressed" pattern next year. '
            'Good base allocations and dividend portfolios; not high-conviction trades.'
        ),
        'note_jp': (
            '簡単に言うと:全3指標(売上・営業・純)が上がり、株価もそれに合わせて控えめに上昇 — サプライズも事件もありません。'
            '使用ルール:全3指標↑、株価↑だが+30%未満、多年連続のコンパウンダー記録には未到達。\n\n'
            'なぜ重要か:再評価を伴わずに業績に追随する安定的・予測可能な成長です。'
            'これらは通常、安定した競争ポジション・成熟したビジネスモデル・信頼できる株主還元方針を持つ中型・大型の確立企業です。'
            '『退屈こそ美しい』コホート — 大きな見出しにはならないものの、確実に業績を出してきます。\n\n'
            '注視点:資本配分の変化(大型M&A・大規模新規投資)、または来年『profit_compressed』パターンに変わり得る売上・利益成長の鈍化。'
            'ベース・ポートフォリオや配当ポートフォリオに適した銘柄群で、高信念トレードではありません。'
        ),
        'order': 4,
    },
    # NEW R+×S+ sub-buckets (split from the previous "Other")
    'activist_corporate_action': {
        'title': 'Activist or corporate-action catalyst',
        'title_jp': 'アクティビスト／コーポレート・アクション主導',
        'note': (
            'In plain terms: the stock surged not because earnings drove it, but because of a specific corporate event — '
            'an activist fund disclosing a stake, a major capital crystallization, or a structural change in capital allocation. '
            'Examples in this bucket: Fuji Media (+113%, Dalton Investments at 7.51%), SoftBank Group (+91.6%, OpenAI value unlock with ¥2.16 trillion valuation gain).\n\n'
            'Rule used: ticker-specific override for names where Round 2 verification documented an activist / corporate-action event as the dominant 2025 driver.\n\n'
            'Why this matters: these stocks moved on who-is-buying, not on what-the-business-did. '
            'Value crystallization is real — but the catalyst is event-specific and can stall if negotiations fail, governance pushes back, or the event resolves below expectations. '
            'These are typically bigger and faster moves than earnings-driven re-ratings, but also more reversible.\n\n'
            'What to watch: shareholder-meeting outcomes, AGM vote results, governance-committee changes, and the next monetization event '
            '(IPO of a subsidiary, sale of an asset, big buyback announcement).'
        ),
        'note_jp': (
            '簡単に言うと:株価が急騰したのは業績が原動力だったからではなく、特定のコーポレート・イベントが原因 — '
            'アクティビスト・ファンドの大量保有報告、大規模な資本顕在化、または資本配分の構造的変化、など。'
            'このバケットの例:フジ・メディア(+113%、ダルトン・インベストメンツ 7.51%)、ソフトバンクG(+91.6%、OpenAI評価益¥2.16兆円計上)。\n\n'
            '使用ルール:Round 2 検証で2025年の主要ドライバーがアクティビスト／コーポレート・アクション・イベントだった銘柄をティッカー単位で振り分け。\n\n'
            'なぜ重要か:これらの株価は『誰が買っているか』で動いており、『ビジネスが何をしたか』では動いていません。'
            '価値顕在化は本物 — ただし触媒はイベント特有で、交渉が失敗したり、ガバナンスが反発したり、結果が期待を下回ったりすると失速する可能性があります。'
            '業績主導の再評価より大きく速い動きですが、巻き戻りも起こりやすい点に注意。\n\n'
            '注視点:株主総会結果、議決権行使結果、ガバナンス委員会の変更、次の収益化イベント(子会社IPO、資産売却、大型自社株買い発表)。'
        ),
        'order': 5,
    },
    'profitability_inflection': {
        'title': 'Profitability inflection — market just started believing in durable margin expansion',
        'title_jp': '収益性の変曲点 — 市場が持続的なマージン拡大を信じ始めた',
        'note': (
            'In plain terms: companies where the market just shifted its view from "growing but not yet profitable enough" to "now durably profitable, and margins are still expanding." '
            'Examples in this bucket: Rakus (OP margin tripled from 7.8% → 26.7% over 3 years), Asteria (30% OP margin + JPYC stable-coin catalyst), '
            'BIPROGY (plan to double system-development productivity through AI by 2030, ¥100bn+ incremental revenue expected).\n\n'
            'Rule used: ticker-specific override for names where the documented 2025 driver was a multi-year margin / profitability inflection becoming visible to the market.\n\n'
            'Why this matters: profitability inflection is one of the most powerful re-rating engines. '
            'EPS rises AND the multiple expands at the same time, so the stock can compound much faster than either alone. '
            'But the inflection has to be DURABLE — if margins are inflating because of one-time cost cuts (rather than mix shift, scale benefits, or pricing power), the re-rating reverses.\n\n'
            'What to watch: the next 2-3 quarters of margin trend, the SOURCE of margin gains (mix shift / scale / pricing vs. one-time cost cuts), '
            'and whether the company can keep raising prices without losing customers.'
        ),
        'note_jp': (
            '簡単に言うと:市場の見方が『成長中だが収益性が足りない』から『いまや持続的に黒字、しかもマージンが拡大中』へ転換した企業群。'
            'このバケットの例:ラクス(3年で営業利益率を7.8%→26.7%へ3倍化)、アステリア(営業利益率30%+JPYCステーブルコイン触媒)、'
            'BIPROGY(2030年までにAI活用でシステム開発生産性2倍、¥100億円超の増収効果見込み)。\n\n'
            '使用ルール:2025年の主要ドライバーが多年にわたるマージン／収益性の変曲点が市場に可視化された銘柄をティッカー単位で振り分け。\n\n'
            'なぜ重要か:収益性の変曲点は最強の再評価エンジンの1つ。'
            'EPSが上昇すると同時に評価倍率も拡大するため、株価はどちらか一方より遥かに速く複利成長します。'
            'ただし変曲点は『持続的』である必要がある — 一時的なコストカット由来のマージン拡大(構成比シフト・規模効果・価格決定力ではなく)なら、再評価は巻き戻されます。\n\n'
            '注視点:今後2-3四半期のマージン推移、マージン拡大の出所(構成比シフト／規模／価格 vs 一時的コストカット)、顧客を失わずに値上げを続けられるか。'
        ),
        'order': 6,
    },
    'inbound_demographic_tailwind': {
        'title': 'Inbound / demographic tailwind',
        'title_jp': 'インバウンド／人口動態の追い風',
        'note': (
            'In plain terms: companies riding a long-duration consumer / population shift in Japan. '
            'Examples in this bucket: istyle (@cosme captures inbound tourist spending on Japanese cosmetics), '
            'Sharing Technology (rides the aging-society demand for life-services — Japan aging rate going from 29.3% in 2024 to 38.7% by 2070), '
            'Smaregi (rides the inbound tourism + cashless-payment shift through cloud POS for restaurants and retail).\n\n'
            'Rule used: ticker-specific override for names whose Round 2-documented 2025 driver was a structural demographic / inbound theme.\n\n'
            'Why this matters: these tailwinds are durable on a decade scale — demographics and consumer-behavior shifts do not reverse quickly. '
            'But there is geopolitical / FX risk (inbound flows depend on yen weakness and travel policy stability), '
            'and competitive intensity can squeeze margins as more players chase the same growth.\n\n'
            'What to watch: monthly tourist-arrival stats (JNTO data), JPY exchange rate (yen weakness is the inbound multiplier), '
            'and demographic data points like single-household ratios and elderly-spending shares.'
        ),
        'note_jp': (
            '簡単に言うと:日本における長期の消費者／人口動態シフトに乗っている企業群。'
            'このバケットの例:アイスタイル(@cosmeは訪日外国人の化粧品消費を取り込む)、'
            'シェアリングテクノロジー(高齢化社会の生活サービス需要に乗る — 日本の高齢化率は2024年29.3% → 2070年38.7%)、'
            'スマレジ(飲食・小売向けクラウドPOSを通じてインバウンドとキャッシュレスシフトを取り込む)。\n\n'
            '使用ルール:Round 2 で2025年の主要ドライバーが構造的な人口動態／インバウンド・テーマだった銘柄をティッカー単位で振り分け。\n\n'
            'なぜ重要か:これらの追い風は10年単位で持続 — 人口動態と消費者行動シフトは急には逆転しません。'
            'ただし地政学リスク／為替リスクあり(インバウンド・フローは円安と入国政策の安定性に依存)、'
            '同じ成長を追う競合が増えるとマージンが圧縮される可能性も。\n\n'
            '注視点:月次訪日外国人客数(JNTOデータ)、円ドル為替(円安はインバウンドの乗数)、'
            '独居世帯比率や高齢者支出シェアなどの人口動態データ。'
        ),
        'order': 7,
    },
    'sector_specific_tailwind': {
        'title': 'Sector-specific tailwind — content/IP/defense category re-rating',
        'title_jp': 'セクター固有の追い風 — コンテンツ／IP／防衛カテゴリーの再評価',
        'note': (
            'In plain terms: companies riding a category-level tailwind that the market is actively re-pricing. '
            'Examples in this bucket: Toho (rode a single mega-hit film 国宝 — 2025\'s No.1 box-office with ¥5.6 billion gross in 38 days), '
            'TV Tokyo (rode the global re-rating of anime IP via overseas streaming — Crunchyroll, Netflix, Prime Video license fees rising), '
            'SKY Perfect JSAT (rode Japan\'s defense-spending ramp — Defense Ministry satellite constellation contract + SpaceX launch contracts doubling capacity).\n\n'
            'Rule used: ticker-specific override for names whose Round 2-documented 2025 driver was a specific sector / category tailwind.\n\n'
            'Why this matters: these tailwinds are typically multi-year — the defense budget is targeted at 2% of GDP through FY27, '
            'the anime overseas market keeps growing, and mega-hit films validate IP-driven re-rating. '
            'But the company needs to be BEST-IN-CLASS in its niche to keep capturing the tailwind; weaker players in the same category may underperform.\n\n'
            'What to watch: budget cycles (defense procurement schedules), streaming-platform license-fee trends (anime), '
            'and the next IP / property catalyst (film slate, sequel announcements, new IP acquisitions).'
        ),
        'note_jp': (
            '簡単に言うと:市場が能動的に再評価しているカテゴリーレベルの追い風に乗っている企業群。'
            'このバケットの例:東宝(単独の大ヒット映画『国宝』に乗る — 2025年興行収入No.1、38日間で56億円)、'
            'テレ東(海外配信 — Crunchyroll、Netflix、Prime Video の権料上昇 — を経由したアニメIPのグローバル再評価に乗る)、'
            'スカパーJSAT(日本の防衛費増額に乗る — 防衛省衛星コンステレーション契約 + SpaceX打ち上げ契約で容量倍増)。\n\n'
            '使用ルール:Round 2 で2025年の主要ドライバーが特定のセクター／カテゴリー追い風だった銘柄をティッカー単位で振り分け。\n\n'
            'なぜ重要か:これらの追い風は通常複数年に及ぶ — 防衛予算はFY27までにGDP比2%目標、海外アニメ市場は成長を続け、大ヒット映画はIP主導の再評価を裏付けます。'
            'ただし、企業は自分のニッチで『ベスト・イン・クラス』である必要があり、同カテゴリーの劣後プレイヤーはアンダーパフォームする可能性があります。\n\n'
            '注視点:予算サイクル(防衛調達スケジュール)、配信プラットフォーム権料トレンド(アニメ)、次のIP／プロパティ触媒(映画ラインナップ、続編発表、新規IP取得)。'
        ),
        'order': 8,
    },
    # Safety net (should have 0 names if overrides are complete; left for defense)
    'other_grower': {
        'title': 'Other',
        'title_jp': 'その他',
        'note': (
            'Safety-net bucket. Should not normally render — if it does, it means a new ticker entered the R+×S+ universe without a sub-bucket override.'
        ),
        'note_jp': (
            'セーフティネット・バケット。通常表示されないはず — 表示される場合は、新規ティッカーがサブバケット・オーバーライドなしでR+×S+ユニバースに入った可能性があります。'
        ),
        'order': 99,
    },
}


# ───── One-line reason generator ─────

def one_line_reason(rec, bucket, s_dir):
    """Compact single-sentence reason — for S- buckets, NAMES THE GAP
    explicitly (revenue grew because X, stock fell/stayed flat because Y).
    The disconnect is the under-recognition thesis. References specific
    numbers where available, falls back to arc context where not."""
    name = rec['name']; ticker = rec['ticker']
    yoy = rec.get('stock_yoy_pct')
    yoy_str = f'{yoy:+.1f}%' if yoy is not None else 'flat/—'

    # SAKURA internet special-case (per Nakamachi guidance — frame as
    # AI-bubble normalization, not "fresh under-recognition")
    if ticker == '3778':
        return ('<b>Gap framing:</b> FY3/2025 fundamentals grew sharply (rev +44%, OP +369%, '
                'NP +351%) on Sakura Cloud / generative-AI demand — BUT the stock fell ' + yoy_str
                + ' YoY because the generative-AI-cloud narrative cooled off the 2023-2024 '
                'mania peak. The gap is sector-narrative cooling, not a fresh business '
                'mismatch the analyst hasn\'t seen.')

    # Generic reason builders by bucket
    arc = arcs.get(ticker, [])
    arc_qs = {y: q for y, q in arc}
    prior_q2_count = 0
    for i in range(1, 5):
        if arc_qs.get(rec['year'] - i) == 'Q2': prior_q2_count += 1
        else: break
    years_in_q2 = prior_q2_count + 1  # include current year

    if bucket == 'durably_overlooked':
        return (f'<b>Gap framing:</b> Revenue compounded each year for the past {years_in_q2} '
                f'years on durable business execution, BUT the stock has failed to re-rate ('
                f'2025 stock {yoy_str} YoY) — the gap is that the market\'s residual derating '
                f'stance from prior years hasn\'t broken despite multi-year consistent growth. '
                f'Durability of the mismatch is what makes it worth attention.')
    if bucket == 'all_up_stock_fell':
        return (f'<b>Gap framing:</b> Revenue, operating profit, and net profit ALL grew '
                f'sharply in 2025 (clean three-line acceleration), BUT the stock fell '
                f'{yoy_str} YoY — the gap is a clean directional disconnect at material size. '
                f'Either the market is pricing in a non-financial concern (governance, '
                f'accounting, sector risk) the headline numbers don\'t show, or the market '
                f'simply hasn\'t caught up yet.')
    if bucket == 'profit_compressed':
        # For mixed records — rev up + profit down
        margin_phr = []
        if rec.get('op_dir') == 'down': margin_phr.append('OP down')
        if rec.get('net_dir') == 'down': margin_phr.append('NP down')
        margin_text = ' and '.join(margin_phr) if margin_phr else 'profit lines under pressure'
        return (f'<b>Gap framing:</b> Revenue kept growing in 2025 on continued demand for '
                f'the core business, BUT the stock derated {yoy_str} YoY because operating '
                f'margins compressed ({margin_text}). The gap is the market pricing in the '
                f'margin pressure ahead of any margin recovery — recoverable if margins '
                f'normalize, harder to break if the compression is structural.')
    if bucket == 'other_under_recognized':
        had_q1 = any(arc_qs.get(rec['year'] - i) == 'Q1' for i in range(1, 3))
        if had_q1:
            return (f'<b>Gap framing:</b> Was in Q1 (business and stock both up) in the prior '
                    f'1-2 years, and 2025 business kept growing — BUT the stock derated for the '
                    f'first time ({yoy_str} YoY). The gap is a fresh sentiment reset on a '
                    f'previously-following compounder; next year\'s data clarifies whether '
                    f'it\'s a one-year blip or the start of a multi-year mismatch.')
        # Mostly flat-stock cases (between -5% and +5% YoY) on growing business
        is_flat = yoy is not None and abs(yoy) <= 5
        if is_flat:
            return (f'<b>Gap framing:</b> Revenue grew in 2025 on steady business execution, '
                    f'BUT the stock stayed essentially flat ({yoy_str} YoY) — the gap isn\'t '
                    f'a sharp derating, more a quiet under-noticing: business kept executing, '
                    f'market simply didn\'t reward it with multiple expansion. The thesis is '
                    f'"why is this name not catching a bid?" rather than "why did it sell off?"')
        return (f'<b>Gap framing:</b> Revenue grew in 2025 but the stock fell {yoy_str} YoY '
                f'with no cleaner sub-bucket fit and limited arc context. Worth a manual look '
                f'at company-specific drivers — the gap could be macro residual, sector '
                f'rotation, or company-specific concern the financials don\'t show yet.')
    if bucket == 'sustained_compounder':
        consec_q1 = 0
        for i in range(1, 5):
            if arc_qs.get(rec['year'] - i) == 'Q1': consec_q1 += 1
            else: break
        return (f'{consec_q1 + 1}-year sustained-grower template — business and stock both up '
                f'each year. 2025 stock {yoy_str} YoY. Market is following the fundamentals.')
    if bucket == 'recovery_caught_up':
        return (f'Prior decline turned this year — business and stock both up in 2025. Stock '
                f'{yoy_str} YoY confirmed the inflection. Fresh recovery; whether it extends is '
                f'the predictive question.')
    if bucket == 'acceleration_rerating':
        return (f'All three financials up + stock {yoy_str} YoY (sharp re-rating). Strong '
                f'momentum confirmed by the market in 2025.')
    if bucket == 'clean_grower':
        return (f'All-three-up business with stock up {yoy_str} YoY — solid steady-grower '
                f'alignment in 2025. No mismatch to investigate.')
    if bucket == 'other_grower':
        return (f'Q1 in 2025 (business and stock both up) but doesn\'t match a cleaner sub-bucket. '
                f'Stock {yoy_str} YoY.')
    return f'2025: stock {yoy_str}; bucket={bucket}.'


def one_line_reason_jp(rec, bucket, s_dir):
    """JP version of one_line_reason — same logic, Japanese prose.
    Bucket-level templated framing only (the genuine reason is in the
    source prose; this is just a label)."""
    name = rec['name']; ticker = rec['ticker']
    yoy = rec.get('stock_yoy_pct')
    yoy_str = f'{yoy:+.1f}%' if yoy is not None else 'データなし'

    if ticker == '3778':
        return ('<b>ギャップ枠組み：</b>FY3/2025のファンダメンタルズは大幅成長（売上+44%、'
                'OP+369%、NP+351%）— Sakura Cloud／生成AI需要が牽引。しかし株価は' + yoy_str
                + 'と下落 — 生成AIクラウドのナラティブが2023-2024年のマニア・ピークから'
                '冷却したため。ギャップはセクターナラティブの冷却であり、'
                'アナリストが見落としている新しい業績ミスマッチではない。')

    arc = arcs.get(ticker, [])
    arc_qs = {y: q for y, q in arc}
    prior_q2_count = 0
    for i in range(1, 5):
        if arc_qs.get(rec['year'] - i) == 'Q2': prior_q2_count += 1
        else: break
    years_in_q2 = prior_q2_count + 1

    if bucket == 'durably_overlooked':
        return (f'<b>ギャップ枠組み：</b>過去{years_in_q2}年間、業績は持続的な事業執行で'
                f'毎年成長したが、株価は再評価されていない（2025年株価{yoy_str} YoY）— '
                f'ギャップは、過去年からの市場の残存デレーティング・スタンスが、'
                f'複数年の一貫した成長にもかかわらず崩れていないこと。'
                f'ミスマッチの持続性こそが注目に値する理由。')
    if bucket == 'all_up_stock_fell':
        return (f'<b>ギャップ枠組み：</b>2025年は売上・営業利益・純利益すべてが大幅成長'
                f'（クリーンな3指標加速）— しかし株価は{yoy_str} YoY下落 — ギャップは、'
                f'材料的な規模でのクリーンな方向性の食い違い。市場が見出し数字に現れない'
                f'非財務的懸念（ガバナンス、会計、セクターリスク）を織り込んでいるか、'
                f'単に市場が追いついていないか。')
    if bucket == 'profit_compressed':
        margin_phr = []
        if rec.get('op_dir') == 'down': margin_phr.append('OP↓')
        if rec.get('net_dir') == 'down': margin_phr.append('NP↓')
        margin_text = '・'.join(margin_phr) if margin_phr else '利益ライン圧迫'
        return (f'<b>ギャップ枠組み：</b>2025年は本業の継続需要で売上は成長し続けたが、'
                f'株価は{yoy_str} YoYでデレーティング — 営業マージンが圧縮したため'
                f'（{margin_text}）。ギャップは、マージン回復より先に市場が'
                f'マージン圧迫を織り込んでいること — マージンが正常化すれば回復可能、'
                f'圧縮が構造的なら破るのは難しい。')
    if bucket == 'other_under_recognized':
        had_q1 = any(arc_qs.get(rec['year'] - i) == 'Q1' for i in range(1, 3))
        if had_q1:
            return (f'<b>ギャップ枠組み：</b>直前1-2年はQ1（業績・株価ともに↑）、'
                    f'2025年も業績は成長を続けた — しかし株価は初めてデレーティング'
                    f'（{yoy_str} YoY）。ギャップは、過去追随していたコンパウンダーの'
                    f'新鮮なセンチメント・リセット — 来年のデータで「1年限りのブリップ」か'
                    f'「多年ミスマッチの始まり」か判明する。')
        is_flat = yoy is not None and abs(yoy) <= 5
        if is_flat:
            return (f'<b>ギャップ枠組み：</b>2025年は安定した事業執行で売上は成長したが、'
                    f'株価はほぼ横ばい（{yoy_str} YoY） — ギャップは鋭いデレーティングではなく、'
                    f'静かな見落とし：業績は執行し続けたが、市場が単にマルチプル拡大で'
                    f'報いなかった。テーゼは「なぜ売り込まれたか」ではなく'
                    f'「なぜこの銘柄が買われていないのか」。')
        return (f'<b>ギャップ枠組み：</b>2025年は売上が成長したが、株価は{yoy_str} YoYで'
                f'下落 — シャープなサブバケットに合わず、アーク文脈も限定的。'
                f'企業固有のドライバーを手動で確認する価値あり — ギャップはマクロ残留、'
                f'セクターローテーション、または財務がまだ見せていない企業固有懸念の'
                f'可能性。')
    if bucket == 'sustained_compounder':
        consec_q1 = 0
        for i in range(1, 5):
            if arc_qs.get(rec['year'] - i) == 'Q1': consec_q1 += 1
            else: break
        return (f'{consec_q1 + 1}年連続の持続的グロワー・テンプレート — 業績・株価ともに'
                f'毎年上昇。2025年株価{yoy_str} YoY。市場はファンダメンタルズを追随している。')
    if bucket == 'recovery_caught_up':
        return (f'直前の減速年から今年反転 — 2025年は業績・株価ともに上昇。株価{yoy_str} YoYが'
                f'変曲点を確認。新鮮な回復；持続性は予測課題。')
    if bucket == 'acceleration_rerating':
        return (f'全3指標↑＋株価{yoy_str} YoY（シャープな再評価）。2025年に市場が確認した'
                f'強いモメンタム。')
    if bucket == 'clean_grower':
        return (f'全3指標↑＋株価{yoy_str} YoY — 2025年は安定した整合性、調査すべき'
                f'ミスマッチなし。')
    if bucket == 'other_grower':
        return (f'2025年Q1（業績・株価ともに↑）だが、よりクリーンなサブバケットに合わない。'
                f'株価{yoy_str} YoY。')
    return f'2025年：株価{yoy_str}；バケット={bucket}。'


# ───── Filter to 2025, drop R-, group ─────

records_2025 = [r for r in all_records if r['year'] == TARGET_YEAR]
r_plus_records = []
r_minus_count = 0
r_unknown_count = 0
for r in records_2025:
    rd = r_direction(r)
    if rd == 'plus':
        r_plus_records.append(r)
    elif rd == 'minus':
        r_minus_count += 1
    else:
        r_unknown_count += 1

# Sort each record into (S direction, reason bucket)
buckets_s_minus: dict[str, list[dict]] = defaultdict(list)
buckets_s_plus: dict[str, list[dict]] = defaultdict(list)
for r in r_plus_records:
    sd = s_direction(r)
    bucket = reason_bucket(r, sd)
    reason_text = one_line_reason(r, bucket, sd)
    reason_text_jp = one_line_reason_jp(r, bucket, sd)
    r['_bucket'] = bucket
    r['_reason_text'] = reason_text
    r['_reason_text_jp'] = reason_text_jp
    r['_s_dir'] = sd
    if sd == 'minus':
        buckets_s_minus[bucket].append(r)
    else:
        buckets_s_plus[bucket].append(r)


# ───── Render HTML ─────

def esc(s): return html.escape(str(s)) if s is not None else ''

# Convert **bold** markdown to <b>bold</b> AFTER escaping. Safe because
# we escape first (so any < > & in the source are neutralised), then only
# replace the **...** pairs we know are intentional.
import re as _re_md
_BOLD_RE = _re_md.compile(r'\*\*(.+?)\*\*')
def esc_with_bold(s):
    return _BOLD_RE.sub(r'<b>\1</b>', esc(s))


# ── Source-prose JP translator ─────────────────────────────────────────
# The rawExplanation in fixture files follows a structured English template like:
#   "*2025:* stock ¥1070 (4-7) – ¥1709 (11-12); close ¥1621 (+28.7% YoY).
#    FY3/2025 rev ¥69540M (+8.7%), OP ¥10190M (+13.2%), NP ¥7450M (+14.6%).
#    業績 ◎ / 株価 ◎.
#
#    <<CANONICAL FY2025>>
#    業績_sign: ◎
#    株価_sign: ◎
#    revenue_dir: up
#    ..."
# Translate the English structure to Japanese via regex. The CANONICAL block
# already uses 業績_/株価_ which are JP — we only need to localise English
# label keys and direction values.
_RE_HEADER = _re_md.compile(
    r'\*(\d{4}):\*\s+stock\s+¥([\d.,]+)\s+\((\d{1,2})-(\d{1,2})\)\s*[–\-]\s*¥([\d.,]+)\s+\((\d{1,2})-(\d{1,2})\);\s*close\s+¥([\d.,]+)\s+\(([+\-][\d.]+)%\s+YoY\)\.'
)
_RE_FY = _re_md.compile(
    r'FY(\d{1,2})/(\d{4})\s+rev\s+¥([\d.,]+)M\s+\(([+\-][\d.]+)%\),\s*OP\s+¥([\d.,]+)M\s+\(([+\-][\d.]+)%\),\s*NP\s+¥([\d.,]+)M\s+\(([+\-][\d.]+)%\)'
)
_DIR_LABEL_MAP = {
    'revenue_dir': '売上方向',
    'op_dir': '営業利益方向',
    'net_dir': '純利益方向',
    'stock_high_date': '株価最高値日',
    'stock_high_price': '株価最高値',
    'stock_low_date': '株価最安値日',
    'stock_low_price': '株価最安値',
    'stock_yoy_pct': '株価前年比%',
    'biz_evidence_points': '業績根拠ポイント',
    'stock_evidence_points': '株価根拠ポイント',
    'op_abs': '営業利益絶対値',
    'net_abs': '純利益絶対値',
    'rev_abs': '売上絶対値',
}
_DIR_VAL_MAP = {
    ': up': ': 上昇',
    ': down': ': 下落',
    ': flat': ': 横ばい',
    ': mixed': ': まちまち',
    ': unclassified': ': 未分類',
    ': unknown': ': 不明',
    ': n/a': ': データなし',
    ': none': ': なし',
}

# Sub-type slug → Japanese label
_SUBTYPE_JP = {
    'SaaS': 'SaaS',
    'SI_IT_services': 'SI・ITサービス',
    'SI': 'SI',
    'IT_services': 'ITサービス',
    'content_games': 'コンテンツ・ゲーム',
    'content_consumer': 'コンテンツ・消費者向け',
    'content': 'コンテンツ',
    'games': 'ゲーム',
    'consumer': '消費者向け',
    'platform': 'プラットフォーム',
    'internet_platform': 'インターネット・プラットフォーム',
    'internet': 'インターネット',
    'telecom': '通信',
    'media': 'メディア',
    'broadcaster': '放送局',
    'fintech': 'フィンテック',
    'ecommerce': 'EC',
    'hr_tech': 'HRテック',
    'edutech': '教育テック',
    'healthtech': 'ヘルステック',
    'think_tank': 'シンクタンク',
    'satellite': '衛星通信',
    'film_ip': '映画・IP',
    'other': 'その他',
    'unknown': '不明',
}

# Size slug → Japanese label
_SIZE_JP = {
    'small': '小型',
    'mid': '中型',
    'large': '大型',
    'mega': '超大型',
    'unknown': '不明',
}

# Direction (rev_dir/op_dir/net_dir) standalone value → Japanese label
_DIR_VALUE_JP = {
    'up': '上昇',
    'down': '下落',
    'flat': '横ばい',
    'mixed': 'まちまち',
    'unknown': '不明',
    'unclassified': '未分類',
    'n/a': 'データなし',
    'none': 'なし',
    '': 'データなし',
    None: 'データなし',
}

# Extra phrase mapping for common business-narrative English used in fixture rawExplanation.
# Translations are deliberately concise so the result reads naturally in Japanese.
_PHRASE_MAP = [
    # Quarterly / period markers
    ('FY8/', 'FY8月期/'), ('FY3/', 'FY3月期/'), ('FY12/', 'FY12月期/'),
    ('FY6/', 'FY6月期/'), ('FY9/', 'FY9月期/'), ('FY1/', 'FY1月期/'),
    ('FY4/', 'FY4月期/'), ('FY7/', 'FY7月期/'), ('FY2/', 'FY2月期/'),
    ('FY11/', 'FY11月期/'), ('FY10/', 'FY10月期/'), ('FY5/', 'FY5月期/'),
    # Common business phrases
    ('operating profit', '営業利益'),
    ('operating margin', '営業利益率'),
    ('net profit', '純利益'),
    ('revenue', '売上'),
    ('Revenue', '売上'),
    ('the stock', '株価'),
    ('The stock', '株価'),
    ('stock price', '株価'),
    ('share price', '株価'),
    ('fell', '下落し'),
    ('rose', '上昇し'),
    ('jumped', '急騰し'),
    ('plunged', '急落し'),
    ('cratered', '暴落し'),
    ('missing expectations', '市場予想に届かず'),
    ('beat expectations', '市場予想を上回り'),
    ('upward revision', '上方修正'),
    ('downward revision', '下方修正'),
    ('guidance', 'ガイダンス'),
    ('full year', '通期'),
    ('first quarter', '第1四半期'),
    ('second quarter', '第2四半期'),
    ('third quarter', '第3四半期'),
    ('fourth quarter', '第4四半期'),
    ('quarterly', '四半期'),
    ('YoY', '前年比'),
    ('YTD', '年初来'),
    ('institutional investors', '機関投資家'),
    ('retail investors', '個人投資家'),
    ('M&A', 'M&A'),
    ('acquisition', '買収'),
    ('subsidiary', '子会社'),
    ('shareholder return', '株主還元'),
    ('share buyback', '自社株買い'),
    ('dividend hike', '増配'),
    ('dividend cut', '減配'),
    ('margin compression', 'マージン圧縮'),
    ('margin expansion', 'マージン拡大'),
    ('analyst', 'アナリスト'),
    ('broker', '証券会社'),
    ('downgrade', '格下げ'),
    ('upgrade', '格上げ'),
    ('target price', '目標株価'),
    ('competition', '競合'),
    ('competitor', '競合他社'),
    ('macro', 'マクロ'),
    ('macroeconomic', 'マクロ経済'),
    ('still growing', 'まだ成長を続けている'),
    ('still flat', '横ばいのまま'),
    ('the year', 'その年'),
    ('this year', '今年'),
    ('last year', '前年'),
    ('the market', '市場'),
    ('despite', 'にもかかわらず'),
    ('because', 'のため'),
    ('roughly', 'おおよそ'),
    ('approximately', '約'),
    ('over six months', '6カ月で'),
    ('trailing-year high', '直近1年高値'),
    ('all-time high', '史上最高値'),
    ('low', '安値'),
    ('high', '高値'),
    ('close', '終値'),
    ('inverse split-signal', '逆の分割シグナル'),
    ('split-signal', '分割シグナル'),
    ('front-loaded', '先行投入された'),
    ('strategic investment', '戦略投資'),
    ('AI investment', 'AI投資'),
    ('SG&A', '販管費'),
    ('deliberate margin compression', '意図的なマージン圧縮'),
    ('profit DOWN', '利益DOWN'),
    ('profit UP', '利益UP'),
    ('Q1', '第1四半期'),
    ('Q2', '第2四半期'),
    ('Q3', '第3四半期'),
    ('Q4', '第4四半期'),
    (' bn', '十億'),  # ¥2.8bn -> ¥2.8十億 (rough)
    (' billion', '十億'),
    (' million', '百万'),
]

_JP_SOURCE_PREFIX = (
    '※ 以下は fixture 作成時の構造化データから自動生成した日本語要約です。'
    '完全な最新解説は上の緑色のブロック『本物の調査』をご参照ください。\n\n'
)

# Regex patterns to extract STRUCTURED data from the rawExplanation header.
# This is used by the JP translator to GENERATE a clean Japanese narrative from
# the extracted facts, rather than attempting word-by-word translation of the
# original English narrative (which produced mixed-language output).
_RE_YEAR_ANNOT = _re_md.compile(r'\*(\d{4})(?:\s*\(([^)]+)\))?:\*')
_RE_STOCK_RANGE = _re_md.compile(
    r'stock\s+¥([\d.,]+)\s+\((\d{1,2})-(\d{1,2})\)\s*[–\-]\s*¥([\d.,]+)\s+\((\d{1,2})-(\d{1,2})\)'
)
_RE_CLOSE = _re_md.compile(r'close\s+¥([\d.,]+)\s+\(([+\-][\d.]+|n/a)%?\s*YoY\)')
_RE_FY_NUM = _re_md.compile(
    r'FY(\d{1,2})/(\d{4})\s+rev\s+¥([\d.,]+)M\s+\(([+\-][\d.]+)%\),\s*OP\s+¥([\d.,]+)M\s+\(([+\-][\d.]+)%\),\s*NP\s+¥([\d.,]+)M\s+\(([+\-][\d.]+)%\)'
)
_RE_BIZ_STOCK_SIGN = _re_md.compile(r'業績\s*([◎○△✕✗xX])\s*/\s*株価\s*([◎○△✕✗xXuncla\s]+?)(?:\.|$)')
_RE_CANONICAL = _re_md.compile(r'<<CANONICAL FY(\d{4})>>([\s\S]*?)(?=<<|$)')

def _sign_jp(sign: str) -> str:
    """Convert a status sign (◎/○/△/✕) or word ('mixed'/'unknown') to a brief JP gloss."""
    s = (sign or '').strip()
    mapping = {
        '◎': '◎(良好)',
        '○': '○(順調)',
        '△': '△(まちまち)',
        '✕': '✕(不調)',
        '✗': '✕(不調)',
        'x': '✕(不調)',
        'X': '✕(不調)',
    }
    if s in mapping:
        return mapping[s]
    low = s.lower()
    if 'unclassified' in low or 'uncla' in low:
        return '未分類'
    if low == 'mixed':
        return 'まちまち'
    if low == 'unknown' or low == 'n/a' or low == '':
        return 'データなし'
    if low == 'up':
        return '上昇'
    if low == 'down':
        return '下落'
    if low == 'flat':
        return '横ばい'
    return s

def translate_raw_to_jp(raw_text: str) -> str:
    """Generate a clean Japanese summary of the fixture rawExplanation by
    extracting structured data points (year, stock range, FY financials,
    classification signs) and rebuilding a Japanese narrative from scratch.
    This avoids the mixed-language output that came from attempting word-by-word
    translation of the original English narrative."""
    if not raw_text:
        return raw_text

    parts: list[str] = []

    # Year + optional annotation
    m_year = _RE_YEAR_ANNOT.search(raw_text)
    year = m_year.group(1) if m_year else None
    annot = m_year.group(2) if (m_year and m_year.group(2)) else None
    if year:
        line = f'**{year}年:**'
        if annot:
            line += f' ({annot})'
        parts.append(line)

    # Stock range + close
    m_range = _RE_STOCK_RANGE.search(raw_text)
    m_close = _RE_CLOSE.search(raw_text)
    if m_range and m_close:
        low = m_range.group(1)
        low_m, low_d = m_range.group(2), m_range.group(3)
        high = m_range.group(4)
        high_m, high_d = m_range.group(5), m_range.group(6)
        close_px = m_close.group(1)
        yoy = m_close.group(2)
        yoy_label = f'前年比{yoy}%' if yoy != 'n/a' else '前年比データなし'
        parts.append(
            f'株価レンジは ¥{low} ({low_m}月{low_d}日) ～ ¥{high} ({high_m}月{high_d}日)、'
            f'年間終値 ¥{close_px} ({yoy_label})。'
        )

    # FY financials
    m_fy = _RE_FY_NUM.search(raw_text)
    if m_fy:
        fy_m = m_fy.group(1)
        fy_y = m_fy.group(2)
        rev_v, rev_p = m_fy.group(3), m_fy.group(4)
        op_v, op_p = m_fy.group(5), m_fy.group(6)
        np_v, np_p = m_fy.group(7), m_fy.group(8)
        parts.append(
            f'{fy_y}年{fy_m}月期決算: 売上 ¥{rev_v}百万円({rev_p}%)、'
            f'営業利益 ¥{op_v}百万円({op_p}%)、純利益 ¥{np_v}百万円({np_p}%)。'
        )

    # Business / stock signs
    m_signs = _RE_BIZ_STOCK_SIGN.search(raw_text)
    if m_signs:
        biz = _sign_jp(m_signs.group(1))
        stk = _sign_jp(m_signs.group(2))
        parts.append(f'分類: 業績 {biz} / 株価 {stk}。')

    # CANONICAL data block — append as structured-data appendix, all keys in JP
    m_canon = _RE_CANONICAL.search(raw_text)
    if m_canon:
        canon_year = m_canon.group(1)
        canon_body = m_canon.group(2).strip()
        # Convert each line of the canonical block to JP
        translated_lines: list[str] = []
        for line in canon_body.split('\n'):
            line = line.strip()
            if not line:
                continue
            translated = line
            translated = translated.replace('業績_sign:', '業績符号:')
            translated = translated.replace('株価_sign:', '株価符号:')
            for en_key, jp_key in _DIR_LABEL_MAP.items():
                translated = translated.replace(f'{en_key}:', f'{jp_key}:')
            for en_val, jp_val in _DIR_VAL_MAP.items():
                translated = translated.replace(en_val, jp_val)
            # Handle "biz_evidence_points: 3" style → keep number
            translated_lines.append(translated)
        if translated_lines:
            parts.append(f'\n**確定データ FY{canon_year}:**\n' + '\n'.join(translated_lines))

    if not parts:
        # Fallback: if nothing could be extracted, return a brief explanatory note
        return _JP_SOURCE_PREFIX + '(構造化データを抽出できませんでした。元の英語版データは EN モードでご確認ください。)'

    return _JP_SOURCE_PREFIX + '\n'.join(parts)


def build_jp_source_summary(r: dict) -> str:
    """Build a CLEAN Japanese summary of the company-year's source prose
    using the record's already-extracted structured fields (no English residue).

    Uses the metadata that every record has: year, rev/op/net direction,
    stock_yoy_pct, op_abs, net_abs, sub_type, size — plus extracts the
    structured template parts from rawExplanation if present."""
    parts: list[str] = []
    yr = r.get('year')
    if yr:
        parts.append(f'**{yr}年:**')

    raw = (r.get('rawExplanation') or '')

    # Stock range + close (from raw if present)
    m_range = _RE_STOCK_RANGE.search(raw)
    m_close = _RE_CLOSE.search(raw)
    if m_range and m_close:
        low = m_range.group(1)
        high = m_range.group(4)
        low_m, low_d = m_range.group(2), m_range.group(3)
        high_m, high_d = m_range.group(5), m_range.group(6)
        close_px = m_close.group(1)
        yoy = m_close.group(2)
        yoy_label = f'前年比{yoy}%' if yoy != 'n/a' else '前年比データなし'
        parts.append(
            f'株価レンジは ¥{low} ({low_m}月{low_d}日) ～ ¥{high} ({high_m}月{high_d}日)、'
            f'年間終値 ¥{close_px} ({yoy_label})。'
        )
    else:
        # Fall back to the stock_yoy_pct field which is always present
        yoy_v = r.get('stock_yoy_pct')
        if yoy_v is not None:
            parts.append(f'株価は通年で前年比 {yoy_v:+.1f}%。')

    # FY financials (from raw if present)
    m_fy = _RE_FY_NUM.search(raw)
    if m_fy:
        fy_m = m_fy.group(1)
        fy_y = m_fy.group(2)
        rev_v, rev_p = m_fy.group(3), m_fy.group(4)
        op_v, op_p = m_fy.group(5), m_fy.group(6)
        np_v, np_p = m_fy.group(7), m_fy.group(8)
        parts.append(
            f'{fy_y}年{fy_m}月期決算: 売上 ¥{rev_v}百万円({rev_p}%)、'
            f'営業利益 ¥{op_v}百万円({op_p}%)、純利益 ¥{np_v}百万円({np_p}%)。'
        )
    else:
        # Fall back to direction fields — fully localised, no English residue
        rev_d = _DIR_VALUE_JP.get((r.get('rev_dir') or '').lower() if r.get('rev_dir') else None,
                                   r.get('rev_dir') or 'データなし')
        op_d = _DIR_VALUE_JP.get((r.get('op_dir') or '').lower() if r.get('op_dir') else None,
                                  r.get('op_dir') or 'データなし')
        np_d = _DIR_VALUE_JP.get((r.get('net_dir') or '').lower() if r.get('net_dir') else None,
                                  r.get('net_dir') or 'データなし')
        parts.append(
            f'業績方向: 売上 {rev_d}、営業利益 {op_d}、純利益 {np_d}。'
        )
        # If abs values are present add them
        op_abs = r.get('op_abs')
        np_abs = r.get('net_abs')
        if op_abs is not None or np_abs is not None:
            abs_parts = []
            if op_abs is not None: abs_parts.append(f'営業利益 約{op_abs}百万円')
            if np_abs is not None: abs_parts.append(f'純利益 約{np_abs}百万円')
            parts.append(f'絶対値レベル: {" / ".join(abs_parts)}。')

    # Business / stock signs
    biz_jp = _sign_jp(r.get('biz') or '')
    stk_jp = _sign_jp(r.get('stk') or '')
    if biz_jp or stk_jp:
        parts.append(f'分類シグナル: 業績 {biz_jp} / 株価 {stk_jp}。')

    # Sub-type and size badges — fully localised
    sub_type = r.get('sub_type') or ''
    size = r.get('size') or ''
    if sub_type or size:
        bits = []
        if sub_type:
            sub_jp = _SUBTYPE_JP.get(sub_type, sub_type)
            bits.append(f'サブ分類「{sub_jp}」')
        if size:
            size_jp = _SIZE_JP.get(size, size)
            bits.append(f'規模「{size_jp}」')
        parts.append(f'メタ情報: {" ・ ".join(bits)}。')

    # CANONICAL block translation (if present in raw)
    m_canon = _RE_CANONICAL.search(raw)
    if m_canon:
        canon_year = m_canon.group(1)
        canon_body = m_canon.group(2).strip()
        translated_lines: list[str] = []
        for line in canon_body.split('\n'):
            line = line.strip()
            if not line:
                continue
            translated = line
            translated = translated.replace('業績_sign:', '業績符号:')
            translated = translated.replace('株価_sign:', '株価符号:')
            for en_key, jp_key in _DIR_LABEL_MAP.items():
                translated = translated.replace(f'{en_key}:', f'{jp_key}:')
            for en_val, jp_val in _DIR_VAL_MAP.items():
                translated = translated.replace(en_val, jp_val)
            translated_lines.append(translated)
        if translated_lines:
            parts.append(f'\n**確定データ FY{canon_year}:**\n' + '\n'.join(translated_lines))

    return _JP_SOURCE_PREFIX + '\n'.join(parts)


def render_record(r):
    yoy = r.get('stock_yoy_pct')
    yoy_str = f'{yoy:+.1f}%' if yoy is not None else 'n/a'
    rd = r.get('rev_dir') or 'n/a'
    raw_prose = (r.get('rawExplanation') or '').strip()
    has_raw = len(raw_prose) > 80  # threshold for "actual prose exists"
    raw_display_en = esc(raw_prose).replace('\n', '<br>')
    raw_display_jp = esc(build_jp_source_summary(r)).replace('\n', '<br>')
    if not has_raw:
        source_block = ('<div class="source-thin" data-i18n="card.sourceThin">'
                        '⚠ Source prose for this company-year is thin — specific business '
                        'catalyst not documented at fixture-author time. Sahal should '
                        'source-check before treating as analysis.</div>')
    else:
        # Embed BOTH the English original and the JP translation as data attributes.
        # JS applyI18n swaps the rendered HTML based on current LANG.
        source_block = (
            '<details class="source-prose">'
            '<summary><span data-i18n="card.sourceLabel">Source prose (fixture rawExplanation)</span></summary>'
            f'<div class="source-prose-body" data-source-en="{raw_display_en}" data-source-jp="{raw_display_jp}">{raw_display_en}</div>'
            '</details>'
        )

    # ── Genuine research block (per-company JP web search) ──
    # This is the PRIMARY reason content per Sahal's 2026-06-04 spec.
    # The bucket-templated "Pattern" line is demoted below it.
    gr = genuine_research.get(r['ticker'])
    if gr:
        gr_jp = gr.get('jp_summary') or ''
        gr_en = gr.get('en_summary') or ''
        gr_src = gr.get('source_hint') or ''
        genuine_block = f'''
      <div class="genuine-research">
        <div class="genuine-header">
          <span class="genuine-label" data-i18n="card.genuineLabel">Genuine research (JP web search per company)</span>
          <span class="genuine-source" title="{esc(gr_src)}">📚 {esc(gr_src)}</span>
        </div>
        <div class="genuine-body" data-genuine-en="{esc_with_bold(gr_en)}" data-genuine-jp="{esc_with_bold(gr_jp)}">{esc_with_bold(gr_en)}</div>
      </div>'''
    else:
        genuine_block = ('<div class="genuine-missing" data-i18n="card.genuineMissing">'
                         '⚠ Per-company web-search research not yet completed for this ticker. '
                         'Pattern line below is bucket-templated.</div>')

    return f'''
    <div class="company-row">
      <div class="company-head">
        <span class="ticker">{esc(r['ticker'])}</span>
        <span class="company-name">{esc(r['name'])}</span>
        <span class="company-meta">
          <span class="badge sub">{esc(r['sub_type'])}</span>
          <span class="badge size">{esc(r['size'])}</span>
        </span>
      </div>
      <div class="company-data">
        <span class="data-item"><span class="data-label" data-i18n="card.revenue">Revenue:</span> {esc(rd)}</span>
        <span class="data-item"><span class="data-label" data-i18n="card.stockYoy">Stock 2025 YoY:</span> <b>{esc(yoy_str)}</b></span>
      </div>
      {genuine_block}
      <details class="pattern-collapse">
        <summary><span data-i18n="card.patternLabel">Pattern (bucket-templated label):</span></summary>
        <div class="reason-text"><span class="reason-pattern-text" data-pattern-en="{esc(r['_reason_text'])}" data-pattern-jp="{esc(r['_reason_text_jp'])}">{r['_reason_text']}</span></div>
      </details>
      {source_block}
    </div>
    '''

def render_bucket(bucket_key, recs, group_class):
    """Each reason bucket = collapsible <details>, closed by default."""
    if not recs: return ''
    label = BUCKET_LABELS[bucket_key]
    # Don't lead with SAKURA internet (3778) in any bucket
    recs_sorted = sorted(recs, key=lambda x: (x['ticker'] == '3778', x['ticker']))
    cards = ''.join(render_record(r) for r in recs_sorted)
    # Embed both EN and JP titles via data-attributes; JS swaps based on lang
    return f'''
    <details class="reason-bucket">
      <summary>
        <span class="bucket-title" data-title-en="{esc(label['title'])}" data-title-jp="{esc(label['title_jp'])}">{esc(label['title'])}</span>
        <span class="bucket-count">{len(recs)} names</span>
      </summary>
      <div class="bucket-note" data-note-en="{esc(label['note'])}" data-note-jp="{esc(label['note_jp'])}">{esc(label['note'])}</div>
      <div class="bucket-cards">{cards}</div>
    </details>
    '''

def render_tab_content(buckets, group_class, total_n, is_active):
    """Tab content panel — contains all reason buckets for one group."""
    if not buckets and total_n == 0:
        return f'<div class="tab-content {group_class}" data-active="{"true" if is_active else "false"}"><p class="empty-note">No records in this group.</p></div>'
    bucket_keys = sorted(buckets.keys(), key=lambda k: BUCKET_LABELS[k]['order'])
    sections = ''.join(render_bucket(bk, buckets[bk], group_class) for bk in bucket_keys)
    return f'<div class="tab-content {group_class}" data-active="{"true" if is_active else "false"}">{sections}</div>'

total_minus = sum(len(v) for v in buckets_s_minus.values())
total_plus = sum(len(v) for v in buckets_s_plus.values())

# R+×S- first (default-active), R+×S+ second (secondary) — per Nakamachi
# 2026-06-04: S- is the 本命 (the prize); S+ is "obvious to anyone."
s_minus_content = render_tab_content(buckets_s_minus, 'tab-s-minus', total_minus, is_active=True)
s_plus_content  = render_tab_content(buckets_s_plus, 'tab-s-plus', total_plus, is_active=False)

STYLES = '''
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Helvetica, Arial, "Hiragino Sans", "Meiryo", sans-serif; margin: 0; padding: 0; color: #1a1a1a; background: #f7f7f5; line-height: 1.55; }
.container { max-width: 1080px; margin: 0 auto; padding: 24px; }
header.page-header { background: #fff; border-bottom: 1px solid #e0e0e0; padding: 22px 24px; }
.page-header h1 { margin: 0 0 4px; font-size: 20px; font-weight: 700; }
.page-header .subtitle { color: #555; font-size: 13px; margin: 4px 0 0; }
.coverage { background: #fffaf0; border-left: 4px solid #d4a017; padding: 12px 16px; margin: 16px 0; border-radius: 4px; font-size: 12.5px; color: #555; }
.coverage b { color: #1a1a1a; }

/* Tabs — R+×S- (the prize/本命) is first and default-active; R+×S+ secondary. */
.tabs {
  display: flex;
  gap: 0;
  margin: 16px 0 0;
  border-bottom: 2px solid #e0e0e0;
  position: sticky;
  top: 0;
  background: #f7f7f5;
  z-index: 10;
  padding: 12px 0 0;
}
.tab {
  border: none;
  background: transparent;
  padding: 14px 22px;
  font-size: 15px;
  font-weight: 700;
  color: #777;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  font-family: inherit;
  transition: color 0.1s ease, border-color 0.1s ease;
  text-align: left;
}
.tab:hover { color: #1a1a1a; }
.tab.active.s-minus { color: #1f7a4a; border-bottom-color: #1f7a4a; }
.tab.active.s-plus  { color: #555; border-bottom-color: #888; }
.tab-jp { font-size: 11px; color: #888; font-weight: 500; margin-left: 8px; }
.tab.active .tab-jp { color: inherit; opacity: 0.85; }
.tab-count { font-size: 11.5px; color: #999; font-weight: 600; margin-left: 6px; font-family: "SF Mono", Menlo, Consolas, monospace; }
.tab-focus-note {
  background: #d6efd6;
  color: #1f7a4a;
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 2px 8px;
  border-radius: 3px;
  margin-left: 8px;
}

.tab-content { display: none; padding: 12px 0 0; }
.tab-content[data-active="true"] { display: block; }

/* Reason bucket — collapsed by default; click summary to expand */
.reason-bucket {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 5px;
  margin: 10px 0;
}
.reason-bucket > summary {
  padding: 14px 18px;
  cursor: pointer;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}
.reason-bucket > summary::-webkit-details-marker { display: none; }
.reason-bucket > summary::before {
  content: '▸';
  color: #888;
  font-size: 11px;
  margin-right: 4px;
}
.reason-bucket[open] > summary::before {
  content: '▾';
  color: #1f7a4a;
}
.bucket-title { font-size: 14.5px; font-weight: 700; color: #1a1a1a; }
.bucket-count { font-size: 11px; color: #888; font-weight: 600; font-family: "SF Mono", Menlo, Consolas, monospace; }
.bucket-note { font-size: 12px; color: #666; margin: 0 18px 12px; font-style: italic; padding-bottom: 4px; border-bottom: 1px dashed #f0f0f0; }
.bucket-cards { padding: 4px 18px 16px; display: flex; flex-direction: column; gap: 10px; }
.company-row { background: #fafafa; padding: 12px 14px; border-radius: 4px; border: 1px solid #ececec; }
.company-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.ticker { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px; color: #888; }
.company-name { font-weight: 700; font-size: 14px; }
.company-meta { margin-left: auto; display: flex; gap: 5px; }
.badge { display: inline-block; font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 3px; background: #ececec; color: #555; letter-spacing: 0.03em; }
.badge.size { font-family: "SF Mono", Menlo, Consolas, monospace; text-transform: uppercase; }
.company-data { margin: 6px 0; display: flex; gap: 16px; font-size: 11.5px; color: #555; }
.data-item { font-family: "SF Mono", Menlo, Consolas, monospace; }
.data-label { color: #888; font-weight: 600; }
.reason-text { margin-top: 6px; font-size: 12.5px; color: #333; line-height: 1.6; }
.reason-text b { color: #1f7a4a; font-weight: 700; }
.reason-label { display: inline-block; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-right: 5px; vertical-align: 1px; }
.empty-note { padding: 20px; color: #888; font-style: italic; }

/* Source prose toggle — shows the actual rawExplanation prose for the
   company-year from the fixture. The prose was written when the fixture
   was authored, based on actual financial data + contextual research
   per company. */
.source-prose { margin-top: 8px; }
.source-prose > summary {
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  color: #555;
  padding: 4px 8px;
  background: #ececec;
  border-radius: 3px;
  display: inline-block;
  list-style: none;
  user-select: none;
}
.source-prose > summary::-webkit-details-marker { display: none; }
.source-prose > summary::before { content: '▸ '; color: #888; }
.source-prose[open] > summary::before { content: '▾ '; color: #1f7a4a; }
.source-prose > summary:hover { background: #d6efd6; color: #1f7a4a; }
.source-prose-body {
  margin-top: 6px;
  padding: 10px 12px;
  background: #fcfcf8;
  border-left: 3px solid #d4a017;
  border-radius: 3px;
  font-size: 11.5px;
  line-height: 1.65;
  color: #333;
  white-space: pre-wrap;
}
.source-thin {
  margin-top: 6px;
  padding: 6px 10px;
  background: #fff3cd;
  border-left: 3px solid #d4a017;
  border-radius: 3px;
  font-size: 11.5px;
  color: #8a6a1a;
  font-style: italic;
}

/* Language toggle — top-right of header */
.lang-switch {
  position: absolute;
  top: 22px;
  right: 24px;
  display: inline-flex;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  overflow: hidden;
}
.lang-btn {
  border: none;
  background: transparent;
  padding: 6px 12px;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  color: #555;
  font-family: inherit;
}
.lang-btn:hover { background: #f0f0f0; color: #1a1a1a; }
.lang-btn.active { background: #1a1a1a; color: #fff; }
header.page-header { position: relative; }

/* Genuine research (per-company JP web search) — the PRIMARY reason content.
   Visually distinct from the bucket-templated Pattern line beneath. */
.genuine-research {
  margin-top: 8px;
  padding: 10px 12px;
  background: #eaf6ee;
  border-left: 4px solid #1f7a4a;
  border-radius: 3px;
}
.genuine-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 5px;
  flex-wrap: wrap;
}
.genuine-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #1f7a4a;
}
.genuine-source {
  font-size: 9.5px;
  color: #5a7d68;
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-weight: 500;
  text-align: right;
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.genuine-body {
  font-size: 12.5px;
  color: #1a3a26;
  line-height: 1.75;
}
.genuine-body b {
  display: inline;
  color: #0d4d2a;
  font-weight: 700;
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-right: 2px;
}
.genuine-missing {
  margin-top: 8px;
  padding: 6px 10px;
  background: #fff3cd;
  border-left: 3px solid #d4a017;
  border-radius: 3px;
  font-size: 11px;
  color: #8a6a1a;
  font-style: italic;
}
/* Bucket-templated Pattern line — demoted to a collapsible secondary block
   beneath the genuine research. */
.pattern-collapse { margin-top: 8px; }
.pattern-collapse > summary {
  cursor: pointer;
  font-size: 10.5px;
  font-weight: 600;
  color: #888;
  padding: 3px 8px;
  background: #f0f0f0;
  border-radius: 3px;
  display: inline-block;
  list-style: none;
  user-select: none;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.pattern-collapse > summary::-webkit-details-marker { display: none; }
.pattern-collapse > summary::before { content: '▸ '; color: #aaa; }
.pattern-collapse[open] > summary::before { content: '▾ '; color: #888; }
.pattern-collapse > summary:hover { background: #e6e6e6; color: #1a1a1a; }
.pattern-collapse .reason-text {
  margin-top: 6px;
  padding: 8px 12px;
  background: #fafafa;
  border-left: 2px solid #ccc;
  border-radius: 3px;
  font-size: 11.5px;
  color: #555;
  line-height: 1.55;
}
.pattern-collapse .reason-text b { color: #555; font-weight: 700; }

/* Honesty note about reason sourcing */
.honesty-note {
  background: #fffaf0;
  border-left: 4px solid #d4a017;
  padding: 10px 14px;
  margin: 12px 0;
  border-radius: 3px;
  font-size: 11.5px;
  color: #555;
  line-height: 1.55;
}
.honesty-note b { color: #1a1a1a; }
'''

JS = '''
const I18N = {
  en: {
    'page.title': '2025 R+ Classification — Reason-grouped view',
    'page.subtitle': '2026-06-04 · Single-year (2025) classification · R+ (revenue-up) only · R- excluded from view (data preserved)',
    'tab.sMinus': 'R+ × S- — Revenue up, stock down',
    'tab.sPlus':  'R+ × S+ — Revenue up, stock up',
    'tab.focus': '本命 / Focus',
    'card.revenue': 'Revenue:',
    'card.stockYoy': 'Stock 2025 YoY:',
    'card.patternLabel': 'Pattern (bucket-templated label):',
    'card.sourceLabel': 'Source prose (fixture rawExplanation)',
    'card.sourceThin': '⚠ Source prose for this company-year is thin — specific business catalyst not documented at fixture-author time. Sahal should source-check before treating as analysis.',
    'card.genuineLabel': 'Genuine research (per-company JP web search)',
    'card.genuineMissing': '⚠ Per-company web-search research not yet completed for this ticker. Pattern line below is bucket-templated.',
    'honesty.title': 'On the reason text — what\\'s genuine vs templated:',
    'honesty.body': 'Each company card now shows three layers. (1) <b>Genuine research</b> (green block, primary) — a source-grounded summary from a per-company JP web search using the prompt <i>「証券コードが[code]の直近の決算のデータを調べるのとそれが伸びたないしは下がった理由と株価にどういう影響が出たかを教えて」</i>. This is the actual recent-earnings + driver + stock-impact narrative for that specific company, aggregated across the most recent 1-3 years of disclosures. (2) <b>Pattern</b> (small gray collapsed line) — the bucket-templated framing showing which reason group the company landed in. (3) <b>Source prose</b> (click to expand) — the original rawExplanation from the fixture (financial numbers from irbank.net, stock from nikkei.com).',
    'group.title.minus': 'R+×S- (revenue up, stock down)',
    'group.title.plus':  'R+×S+ (revenue up, stock up)',
  },
  jp: {
    'page.title': '2025年 R+ 企業分類 — 理由別グループ表示',
    'page.subtitle': '2026-06-04 · 単年（2025年）分類 · R+（業績↑）のみ · R-（業績↓）はビューから除外（データは保持）',
    'tab.sMinus': 'R+ × S- — 業績↑・株価↓',
    'tab.sPlus':  'R+ × S+ — 業績↑・株価↑',
    'tab.focus': '本命',
    'card.revenue': '売上：',
    'card.stockYoy': '2025年株価YoY：',
    'card.patternLabel': 'パターン（バケット・テンプレートラベル）：',
    'card.sourceLabel': '元の説明文（fixture rawExplanation）',
    'card.sourceThin': '⚠ この銘柄・年の元の説明文が薄い — 具体的な事業カタリストが fixture 作成時点で文書化されていません。分析として扱う前に Sahal が出典確認すべきです。',
    'card.genuineLabel': '本物の調査（企業ごとのJP Web検索）',
    'card.genuineMissing': '⚠ この銘柄の企業別Web検索調査は未完了。下のパターン行はバケット・テンプレート。',
    'honesty.title': '理由テキストについて — 本物とテンプレートの違い：',
    'honesty.body': '各カンパニーカードは3レイヤー構成です。(1) <b>本物の調査（Genuine research）</b>（緑のブロック、主役）— 企業ごとに次のJPプロンプトでWeb検索した結果の出典付き要約：<i>「証券コードが[code]の直近の決算のデータを調べるのとそれが伸びたないしは下がった理由と株価にどういう影響が出たかを教えて」</i>。各社固有の直近決算＋成長／下落要因＋株価インパクトのナラティブで、直近1-3年の開示を集約しています。(2) <b>パターン</b>（小さなグレーの折り畳み行）— その企業がどの理由グループに着地したかを示すバケット・テンプレート。(3) <b>元の説明文（Source prose）</b>（クリックで展開）— fixture 作成時の rawExplanation 原文（財務数値は irbank.net、株価は nikkei.com 由来）。',
    'group.title.minus': 'R+×S-（業績↑・株価↓）',
    'group.title.plus':  'R+×S+（業績↑・株価↑）',
  },
};
let LANG = 'en';

function applyI18n() {
  const dict = I18N[LANG];
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key] != null) el.textContent = dict[key];
  });
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    const key = el.getAttribute('data-i18n-html');
    if (dict[key] != null) el.innerHTML = dict[key];
  });
  // Bucket titles and notes — swap from per-element data attributes
  document.querySelectorAll('.bucket-title[data-title-en]').forEach(el => {
    const v = el.getAttribute('data-title-' + LANG);
    if (v != null) el.textContent = v;
  });
  document.querySelectorAll('.bucket-note[data-note-en]').forEach(el => {
    const v = el.getAttribute('data-note-' + LANG);
    if (v != null) el.textContent = v;
  });
  // Per-card Pattern reason text — each card stores both languages
  document.querySelectorAll('.reason-pattern-text[data-pattern-en]').forEach(el => {
    const v = el.getAttribute('data-pattern-' + LANG);
    if (v != null) el.innerHTML = v;
  });
  // Per-card Genuine research body — swap JP/EN summary (innerHTML so <b> renders)
  document.querySelectorAll('.genuine-body[data-genuine-en]').forEach(el => {
    const v = el.getAttribute('data-genuine-' + LANG);
    if (v != null) el.innerHTML = v;
  });
  // Per-card Source prose body — swap JP-translated / EN-original content
  document.querySelectorAll('.source-prose-body[data-source-en]').forEach(el => {
    const v = el.getAttribute('data-source-' + LANG);
    if (v != null) el.innerHTML = v;
  });
  document.documentElement.setAttribute('lang', LANG);
}

function setLang(lang) {
  LANG = lang;
  document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
  applyI18n();
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
  applyI18n();
});
'''

doc = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>2025 R+ Classification — by Reason</title>
<style>{STYLES}</style>
</head>
<body>
<header class="page-header">
  <h1 data-i18n="page.title">2025 R+ Classification — Reason-grouped view</h1>
  <div class="subtitle" data-i18n="page.subtitle">2026-06-04 · Single-year (2025) classification · R+ (revenue-up) only · R- excluded from view (data preserved)</div>
  <div class="lang-switch">
    <button class="lang-btn active" data-lang="en">EN</button>
    <button class="lang-btn" data-lang="jp">日本語</button>
  </div>
</header>

<div class="container">
  <div class="coverage">
    <b>Coverage:</b> {total_tickers_in_library} companies in classification library (IT census target: 122). 2025 records → <b>{total_minus + total_plus} R+ (revenue-up)</b> · {r_minus_count} R- (revenue-down, excluded) · {r_unknown_count} unclassified.<br>
    <b>R+ split:</b> <b>{total_minus} in R+×S- (revenue up, stock down) — 本命 / primary focus</b> · {total_plus} in R+×S+ (secondary).
  </div>

  <div class="honesty-note">
    <b data-i18n="honesty.title">On the reason text — what's genuine vs templated:</b><br>
    <span data-i18n-html="honesty.body">Each company card now shows three layers. (1) <b>Genuine research</b> (green block, primary) — a source-grounded summary from a per-company JP web search using the prompt <i>「証券コードが[code]の直近の決算のデータを調べるのとそれが伸びたないしは下がった理由と株価にどういう影響が出たかを教えて」</i>. This is the actual recent-earnings + driver + stock-impact narrative for that specific company, aggregated across the most recent 1-3 years of disclosures. (2) <b>Pattern</b> (small gray collapsed line) — the bucket-templated framing showing which reason group the company landed in. (3) <b>Source prose</b> (click to expand) — the original rawExplanation from the fixture (financial numbers from irbank.net, stock from nikkei.com).</span>
  </div>

  <div class="tabs" role="tablist">
    <button class="tab active s-minus" data-tab="s-minus" role="tab">
      <span data-i18n="tab.sMinus">R+ × S- — Revenue up, stock down</span>
      <span class="tab-count">{total_minus}</span>
      <span class="tab-focus-note" data-i18n="tab.focus">本命 / Focus</span>
    </button>
    <button class="tab s-plus" data-tab="s-plus" role="tab">
      <span data-i18n="tab.sPlus">R+ × S+ — Revenue up, stock up</span>
      <span class="tab-count">{total_plus}</span>
    </button>
  </div>

  {s_minus_content}
  {s_plus_content}
</div>

<script>{JS}</script>
</body>
</html>
'''

# Stripping helpers + CSV path (always defined for importers)
import re as _re
_TAG_RE = _re.compile(r'<[^>]+>')
def _strip_tags(s):
    return _TAG_RE.sub('', s or '').strip()
csv_out = DELIVERABLES / 'R_PLUS_2025_view.csv'


def write_outputs():
    """Write standalone HTML + CSV + console summary. Called only when run as a script.
    When this module is imported (e.g. by build_unified_view.py), this is NOT called,
    so importing has no side effects on the filesystem."""
    DELIVERABLES.mkdir(exist_ok=True)
    out_html = DELIVERABLES / 'R_PLUS_2025_view.html'
    out_html.write_text(doc, encoding='utf-8')
    print(f'Wrote deliverables/{out_html.name} ({len(doc):,} bytes)')

    # CSV
    _write_csv()
    _print_console_summary()


def _write_csv():
    with open(csv_out, 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp)
        w.writerow(['name', 'ticker', 'group', 'reason_label', 'revenue_dir', 'stock_pct_yoy',
                    'genuine_research_en', 'genuine_research_jp', 'genuine_source_hint',
                    'one_line_reason_templated', 'sub_type', 'size', 'year'])
        for bucket, recs in buckets_s_minus.items():
            for r in recs:
                yoy = r.get('stock_yoy_pct')
                gr = genuine_research.get(r['ticker'], {}) or {}
                w.writerow([
                    r['name'], r['ticker'], 'R+ x S-',
                    BUCKET_LABELS[bucket]['title'],
                    r.get('rev_dir') or '',
                    f'{yoy:+.1f}' if yoy is not None else '',
                    gr.get('en_summary', ''),
                    gr.get('jp_summary', ''),
                    gr.get('source_hint', ''),
                    _strip_tags(r['_reason_text']),
                    r['sub_type'], r['size'], TARGET_YEAR,
                ])
        for bucket, recs in buckets_s_plus.items():
            for r in recs:
                yoy = r.get('stock_yoy_pct')
                gr = genuine_research.get(r['ticker'], {}) or {}
                w.writerow([
                    r['name'], r['ticker'], 'R+ x S+',
                    BUCKET_LABELS[bucket]['title'],
                    r.get('rev_dir') or '',
                    f'{yoy:+.1f}' if yoy is not None else '',
                    gr.get('en_summary', ''),
                    gr.get('jp_summary', ''),
                    gr.get('source_hint', ''),
                    _strip_tags(r['_reason_text']),
                    r['sub_type'], r['size'], TARGET_YEAR,
                ])
    print(f'Wrote {csv_out.name}')


def _print_console_summary():
    print()
    print('=== R+×S- (foregrounded) ===')
    for bk in sorted(buckets_s_minus.keys(), key=lambda k: BUCKET_LABELS[k]['order']):
        print(f'  [{len(buckets_s_minus[bk])}] {BUCKET_LABELS[bk]["title"]}')
        for r in sorted(buckets_s_minus[bk], key=lambda x: x['ticker']):
            yoy = r.get('stock_yoy_pct')
            yoy_str = f'{yoy:+.1f}%' if yoy is not None else 'n/a'
            print(f'      {r["ticker"]} {r["name"]} (stock {yoy_str})')
    print()
    print('=== R+×S+ (secondary) ===')
    for bk in sorted(buckets_s_plus.keys(), key=lambda k: BUCKET_LABELS[k]['order']):
        print(f'  [{len(buckets_s_plus[bk])}] {BUCKET_LABELS[bk]["title"]}')
    print()
    print(f'Total R+: {total_minus + total_plus} ({total_minus} S- + {total_plus} S+)')
    print(f'Dropped R-: {r_minus_count}')
    print(f'Unclassified (dropped): {r_unknown_count}')


# ───── Entry point ─────
if __name__ == '__main__':
    write_outputs()
