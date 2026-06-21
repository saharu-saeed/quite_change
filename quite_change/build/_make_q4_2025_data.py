"""Data generator for the '2025 Q4' view (non-IT) — UNIFIED-VIEW style, 2-WEEK stock metric.

"2025 Q4 report" == the FY2025 full-year report (fiscal year that ENDED in 2025):
  March end -> FY3/2025 ; December end -> FY12/2025.

STOCK DIRECTION = the market's reaction to THIS report: the close on the earnings-announcement
date (pre-news baseline; JP tanshin release after the 15:00 close) vs the close ~2 weeks later.
S+ if up over those two weeks, else S-. (Senior's instruction: 「一旦決算から2週間くらい」.)
REVENUE DIRECTION = revenue stated in the FY2025 report, YoY vs FY2024. R+ if >=0 else R-.

Narrative = the full FOUR-SECTION "lighter prompt", written qualitatively and plainly like
deliverables/UNIFIED_VIEW.html (the "why did the stock move" section uses numbered reasons).
Companies grouped into REASON BUCKETS (title = the shared driver). Point-in-time: narratives use
the FY2025 report (incl. the guidance issued WITH it) + earlier years only — never a later report.

Universe = the FULL listed TOPIX-33 sector (incl. previously-excluded R- names), delisted/TOB
excluded. Numbers + the 2-week reaction freshly web-researched June 2026.
"""
from __future__ import annotations
import json, io, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
OUT = Path(__file__).parent.parent / 'data' / 'quarterly' / 'q4_2025_nonIT.json'
SRC = ['stockanalysis.com (FY2025 financials)', 'Yahoo Finance (daily closes around announcement)', 'company tanshin / Nikkei / kabutan / logmi']


def cat(rev_yoy, stk_yoy):
    return ('R+' if rev_yoy >= 0 else 'R-') + 'x' + ('S+' if stk_yoy > 0 else 'S-')


def S(ov, biz, whybiz, whystk):
    return (f"**Company overview:** {ov}\n\n**How did business move?** {biz}\n\n"
            f"**Why did business move this way?** {whybiz}\n\n**Why did the stock move this way?** {whystk}")


def SJ(ov, biz, whybiz, whystk):
    return (f"**会社概要:** {ov}\n\n**業績の動き:** {biz}\n\n"
            f"**業績が動いた理由:** {whybiz}\n\n**株価が動いた理由:** {whystk}")


BUCKETS = {
    'good_results_cautious_outlook': {'order': 2,
        'title': 'Strong results — but a cautious commodity-price outlook in the same report capped the stock',
        'title_jp': '好決算 — でも同じ決算の慎重な市況見通しが株価の重し',
        'note': ('Revenue and profit rose strongly in FY2025, but the very same report paired those good '
                 'actuals with a cautious outlook for the year ahead (lower assumed oil / gas prices). The '
                 'market looked through the strong past year to the softer guidance, so the report did not '
                 'lift the stock.'),
        'note_jp': ('FY2025は増収増益と好調だったが、同じ決算が翌期の慎重な見通し(原油・ガス価格の前提引き下げ)'
                    'を伴った。市場は好調だった過年度を越えて弱いガイダンスを見たため、決算は株価を押し上げなかった。')},
    'resource_cycle_rewarded': {'order': 4,
        'title': 'Riding the resource / metals up-cycle — the report was rewarded',
        'title_jp': '資源・金属の上昇局面に乗る — 決算が評価された',
        'note': ('Resource-linked names whose revenue rode higher ore and metal prices. When the FY2025 '
                 'results landed, the market rewarded the rising top line and headline profit — even where '
                 'the bottom-line gain leaned on one-off items.'),
        'note_jp': ('鉱石・金属価格の上昇に売上が連動した資源関連。FY2025決算が出ると、利益増が一過性要因に'
                    '頼る部分があっても、市場は伸びるトップラインと表面上の利益を評価した。')},
    'shrank_but_big_returns': {'order': 6,
        'title': 'Revenue shrank — but profit growth and heavy shareholder returns won the market over',
        'title_jp': '減収 — でも増益と手厚い株主還元で市場を味方に',
        'note': ('Revenue fell (a business in transition, or lower commodity prices), yet when the FY2025 '
                 'report landed the stock ROSE over the next two weeks. Profit improved and the companies '
                 'announced strong shareholder returns (higher dividends, buybacks), and the market looked '
                 'past the shrinking top line.'),
        'note_jp': ('売上は減少(事業転換中、または市況下落)だが、FY2025決算後の2週間で株価は上昇。利益が改善し'
                    '手厚い株主還元(増配・自社株買い)を打ち出したため、市場は縮小するトップラインを越えて評価した。')},
    'commodity_prices_fell': {'order': 7,
        'title': 'Falling commodity prices (and, in one case, a dividend cut) sent the report and the stock down',
        'title_jp': '市況下落(一部は減配も) — 決算も株価も下押し',
        'note': ('Falling commodity prices pulled revenue and profit down together, and the FY2025 report '
                 'disappointed: the stock fell over the two weeks after the announcement — made worse, for '
                 'one name, by a dividend cut.'),
        'note_jp': ('市況下落で売上も利益も同時に減少し、FY2025決算は失望を招いた。発表後の2週間で株価は下落し、'
                    '一部銘柄は減配がさらに重しとなった。')},
    'record_revenue_dividend_rewarded': {'order': 8,
        'title': 'Record revenue and a dividend hike — the market liked the report',
        'title_jp': '過去最高の売上＋増配 — 市場は決算を好感',
        'note': ('Revenue hit a record and the company raised its dividend. Even where profit dipped, the '
                 'strong top line plus higher shareholder returns led the market to take the report well, and '
                 'the stock rose in the two weeks after the announcement.'),
        'note_jp': ('売上が過去最高を更新し増配。利益が小幅に落ちても、力強いトップラインと株主還元の増加で'
                    '市場は決算を好感し、発表後2週間で株価は上昇した。')},
    'weak_profit_mild_relief': {'order': 9,
        'title': 'Weak profit, but no fresh negative — a small relief bounce',
        'title_jp': '減益も新たな悪材料なし — 小幅な安心感の戻り',
        'note': ('Profit fell, but the weakness had already been disclosed in the earlier quarter, so the '
                 'full-year report held no fresh negative. With expectations already low and the share price '
                 'depressed, the stock managed only a small bounce.'),
        'note_jp': ('減益だが、その弱さは前の四半期で既に開示済みで、通期決算に新たな悪材料はなかった。'
                    '期待が既に低く株価も低迷していたため、株価は小幅に戻したのみ。')},
    'good_results_sold_off': {'order': 10,
        'title': 'Solid results, but the market sold the report',
        'title_jp': '好決算 — でも市場は売りで反応',
        'note': ('Revenue and profit rose, yet the stock fell sharply in the two weeks after the report — soft '
                 'next-year guidance and/or a thin, illiquid float drove a sell-the-news reaction.'),
        'note_jp': ('増収増益でも、発表後2週間で株価は急落。翌期の弱いガイダンスや、薄く流動性の低い浮動株が'
                    '「材料出尽くし」の売りを招いた。')},
    'refining_profit_sold': {'order': 11,
        'title': 'Revenue up, but refining profit fell from a peak — the report was sold',
        'title_jp': '増収も精製益がピークから減少 — 決算は売られた',
        'note': ('Revenue held up or rose, but operating/net profit fell as refining margins and '
                 'inventory-valuation gains normalized from an unusually strong prior year. In the two weeks '
                 'after the report the stock fell — even shareholder returns could not offset the profit drop.'),
        'note_jp': ('売上は維持〜増加でも、精製マージンと在庫評価益が好調だった前期から正常化し営業・純利益が減少。'
                    '決算後2週間で株価は下落し、株主還元でも減益を相殺できなかった。')},
    'steady_specialty_rewarded': {'order': 12,
        'title': 'Steady specialty / infrastructure grower — the report was rewarded',
        'title_jp': '安定した専門・インフラ成長 — 決算が評価された',
        'note': ('Non-refining names with steady, less commodity-driven demand (road-paving materials, '
                 'metalworking fluids, specialty lubricants, branded lubricants). Revenue and operating profit '
                 'grew and dividends rose, and the market rewarded the report in the two weeks after.'),
        'note_jp': ('精製に依存しない、市況に左右されにくい安定需要の銘柄(道路舗装材・金属加工油・特殊潤滑油・'
                    'ブランド潤滑油)。増収・営業増益と増配を受け、市場は決算後2週間で株価を評価した。')},
    'down_but_recovery_guidance': {'order': 13,
        'title': 'Revenue down — but V-shaped recovery guidance lifted the (thin) stock',
        'title_jp': '減収 — でもV字回復ガイダンスが(薄商いの)株価を押し上げた',
        'note': ('Revenue and profit fell this year, but the same report guided a sharp recovery next year. '
                 'In a thinly-traded small-cap that was enough to send the stock sharply higher in the two '
                 'weeks after the report (large % swings on low liquidity).'),
        'note_jp': ('今期は減収減益だが、同じ決算が翌期の大幅な回復を見込んだ。薄商いの小型株では、これが発表後'
                    '2週間で株価を急騰させるのに十分だった(流動性が低く変動率が大きい)。')},
    'shipping_upcycle_rewarded': {'order': 14,
        'title': 'Shipping up-cycle — revenue up and the report was rewarded',
        'title_jp': '海運の上昇局面 — 増収で決算が評価された',
        'note': ('FY3/2025 was the peak of the freight up-cycle (Red Sea-driven container rates, firm '
                 'bulk/tanker markets). These lines posted higher revenue and strong profits — most also '
                 'raised dividends — and in the two weeks after each report the market rewarded them, even '
                 'where the same report guided the next year lower.'),
        'note_jp': ('FY3/2025は運賃上昇局面のピーク(紅海問題によるコンテナ運賃高、底堅いばら積み・タンカー市況)。'
                    '各社は増収・好業績で多くが増配も実施し、決算後2週間で市場はこれを評価した — 同じ決算が翌期の'
                    '減益を見込んでいても。')},
    'shipping_revenue_up_but_sold': {'order': 15,
        'title': 'Revenue up in the up-cycle — but the report was sold',
        'title_jp': '上昇局面で増収 — でも決算は売られた',
        'note': ('These shipping names also grew revenue, but their reports were sold over the next two weeks, '
                 'each for a different reason: weak forward guidance plus a dividend cut (Iino); a "buy the '
                 'rumor, sell the news" give-back after the stock had run up, in a thin small-cap (Kuribayashi); '
                 'or a dividend cut from plan plus an impairment despite a profit surge (Inui).'),
        'note_jp': ('これらの海運株も増収だったが、決算後2週間で売られた — 理由はそれぞれ異なる: 弱い翌期見通しと'
                    '減配(飯野)、株価が先回りで上昇した後の「材料出尽くし」の反落(薄商いの小型株、栗林)、'
                    '利益急増にもかかわらず計画比の減配＋減損(乾)。')},
    'agri_priced_up_but_sold': {'order': 16,
        'title': 'Food prices up — revenue rose, but the report was sold',
        'title_jp': '食品の値上げで増収 — でも決算は売られた',
        'note': ('FY2025 was the peak of food-price inflation: seafood, eggs and seeds all became more '
                 'expensive, so these companies passed costs through and grew revenue (most also raised '
                 'dividends). But over the next two weeks the reports were sold — either because the same '
                 'report guided the next year lower (Maruha Nichiro: FY26 operating profit -11%; Sakata: '
                 'recurring -11%), or because the good news was already priced in after a run-up (Kyokuyo). '
                 'Classic "buy the rumor, sell the news" across the food shelf.'),
        'note_jp': ('FY2025は食品インフレのピーク: 水産物・卵・種苗が軒並み値上がりし、各社はコスト転嫁で増収(多くが'
                    '増配も)。だが決算後2週間で売られた — 同じ決算が翌期の減益を見込んだか(マルハニチロ: 翌期営業益'
                    '-11%、サカタ: 経常-11%)、あるいは事前の上昇で好材料が織り込み済みだったため(極洋)。食品株'
                    '全般の典型的な「材料出尽くし」。')},
    'agri_revenue_up_profit_fell': {'order': 17,
        'title': 'Revenue up, but profit actually fell — and the stock was sold',
        'title_jp': '増収でも実は減益 — そして売られた',
        'note': ('Here revenue rose, but profit went the other way: higher input costs and one-off factors '
                 'squeezed earnings (Yukiguni: operating profit -14%; Akikawa: operating profit slipped to a '
                 'small loss). With profit falling, the market sold the report over the next two weeks.'),
        'note_jp': ('ここでは増収でも利益は逆方向: 原価高や一過性要因で利益が圧迫された(ユキグニ: 営業益-14%、'
                    '秋川牧園: 営業益が小幅赤字に転落)。減益のため、市場は決算後2週間で売った。')},
    'agri_strong_profit_thin_float': {'order': 18,
        'title': 'Strong profit growth — but a thin float gave the gains back',
        'title_jp': '大幅増益 — でも薄商いで上げ分を戻した',
        'note': ('Profit grew strongly and the dividend was raised, but the stock is small and thinly traded, '
                 'so the post-result pop faded back to roughly flat over two weeks (Axyz).'),
        'note_jp': ('大幅増益かつ増配だったが、小型で出来高が薄いため、決算後の上昇は2週間でほぼ横ばいに戻った'
                    '(アクシーズ)。')},
    'agri_mushroom_recovery_rewarded': {'order': 19,
        'title': 'Profit recovery rewarded',
        'title_jp': '利益回復が評価された',
        'note': ('Mushroom selling prices and margins recovered, so operating profit more than doubled — and '
                 'over the two weeks after the report the market rewarded the turnaround, even though the same '
                 'report guided the next year lower (Hokuto).'),
        'note_jp': ('きのこの販売価格・採算が回復し営業利益が倍以上に — 決算後2週間で市場はこの回復を評価した、'
                    '同じ決算が翌期の減益を見込んでいても(ホクト)。')},
    'agri_microcap_drift_up': {'order': 20,
        'title': 'Tiny grower — losses narrowing, thin year-end drift up',
        'title_jp': '小型の生産者 — 赤字縮小、薄商いの年末上昇',
        'note': ('A very small seedling grower with revenue up slightly and losses narrowing; the modest '
                 'two-week rise is largely thin-float, year-end small-cap drift rather than a strong reaction '
                 '(Berg Earth).'),
        'note_jp': ('小幅増収で赤字が縮小した極小型の苗生産者。2週間の小幅上昇は、強い反応というより薄商いの年末'
                    '小型株の地合いによるところが大きい(ベルグアース)。')},
    'agri_volume_down_margins_up': {'order': 21,
        'title': 'Revenue down on volume — but margins up, so the report was bought',
        'title_jp': '数量減で減収 — でも採算改善で買われた',
        'note': ('Revenue fell because volumes dropped, but better pricing/mix lifted operating and net profit, '
                 'so the report was modestly bought over the next two weeks (Hob — strawberries).'),
        'note_jp': ('数量減で減収となったが、価格・構成の改善で営業・純利益が増加したため、決算後2週間で小幅に'
                    '買われた(ホーブ — いちご)。')},
}


C = {}

C['1515'] = dict(name='Nittetsu Mining', sector='Mining', fy_label='FY3/2025', bucket='resource_cycle_rewarded',
    announce_date='2025-05-12', stk_p0=1330, stk_p1=1448,
    rev_pct='+17.9%', op_pct='-8.2%', net_pct='+36.6%', rev_yoy=17.9, op_dir='down', net_dir='up',
    biz_class='石灰石鉱業・金属資源投資 / Limestone mining & metal resource investment',
    en=S(
        "Nittetsu Mining (1515) is Japan's largest miner of limestone — the rock that is an essential raw material for making steel and cement. Founded in 1939 to supply limestone to the Nippon Steel group, it still digs limestone from domestic quarries, but over the decades it has built a far more diversified company on top of that base: it invests in overseas copper and gold mines (in Chile and Brazil), owns and rents real estate in Tokyo, makes building materials, and runs an industrial-waste recycling business. So its profit is a mix of steady domestic mining, swingy overseas metal prices, and stable property income.",
        "For FY3/2025 revenue rose +17.9% to about ¥197bn, but operating profit fell -8.2% while net profit jumped +36.6% to ¥9.0bn — so the top line and the final profit both looked strong, yet the underlying operating profit slipped, an unusual split. For FY3/2026 the company itself guided to a softer year, with lower revenue and operating profit.",
        "The +18% revenue came from higher prices for limestone and ore and in the environmental (recycling) segment. But operating profit fell because the metals side struggled: the copper-smelting business was hit by unfavourable currency moves, and the Atacama copper mine in Chile produced less ore — so the day-to-day operating engine got a little weaker. The reason net profit still jumped +37% is that the gains came from outside normal operations: Nittetsu booked one-off profits from selling cross-shareholdings (shares it held in other companies) and received insurance money after a fire. In other words, the big jump in the final profit was driven by one-time items, not by the core business getting stronger.",
        "In the two weeks after the May 12 results the stock rose about +9% (¥1,330 → ¥1,448). Two main reasons. 1. The headline net-profit jump (+37%) looks impressive at a glance, and many investors react first to the final profit line — so the immediate read of the report was positive. 2. As a company tied to copper and resource prices, Nittetsu benefits when investors feel optimistic about metals, and its resource-plus-property mix gives it a feeling of solidity. Investors largely looked past the dip in operating profit and the fact that the net-profit gain was one-off — the report read as 'a resource company having a good year,' and the stock was rewarded."),
    jp=SJ(
        "日鉄鉱業(1515)は、鉄やセメントを作るのに欠かせない原料『石灰石』で国内最大の鉱業会社です。1939年に新日鉄グループへ石灰石を供給するために設立され、今も国内の鉱山で石灰石を採掘していますが、長年かけてその土台の上に多角的な事業を築いてきました。海外(チリ・ブラジル)の銅・金鉱山への投資、東京の不動産賃貸、建材、産業廃棄物リサイクルなどです。つまり利益は、安定した国内鉱業＋変動の大きい海外金属価格＋安定した不動産収入の組み合わせから生まれます。",
        "FY3/2025は売上が+17.9%の約1,970億円に増加した一方、営業利益は-8.2%と減少、最終の純利益は+36.6%の90億円へ大きく増えました — 売上と最終利益は強く見えるのに本業の営業利益は落ちる、という珍しい構図です。FY3/2026は会社自身が減収・営業減益の慎重な見通しを示しました。",
        "+18%の増収は、石灰石・鉱石や環境(リサイクル)部門の価格上昇によるものです。営業利益が減ったのは金属側の不振が理由で、銅の製錬事業が不利な為替変動に見舞われ、チリのアタカマ銅鉱山の生産量も減りました — 日々の本業エンジンが少し弱まったのです。それでも純利益が+37%伸びたのは、利益が通常の本業の外から来たためです。政策保有株(他社の株式)の売却益という一過性の利益を計上し、さらに火災に伴う保険金を受け取りました。要するに最終利益の大幅増は本業の強さではなく、一時的な要因によるものでした。",
        "5月12日の決算後の2週間で株価は約+9%上昇しました(¥1,330→¥1,448)。理由は主に2つ。1. 純利益+37%という見出しは一見すると立派で、多くの投資家はまず最終利益に反応するため、決算の第一印象は良好でした。2. 銅や資源価格に連動する会社として、投資家が金属に強気なときに恩恵を受けやすく、資源＋不動産の構成が『堅さ』の印象を与えます。営業利益の減少や、純利益増が一過性である点を投資家はおおむね見過ごし、決算は『資源会社が良い年を過ごした』と読まれて株価は評価されました。"))

C['1662'] = dict(name='Japan Petroleum Exploration (JAPEX)', sector='Mining', fy_label='FY3/2025', bucket='good_results_cautious_outlook',
    announce_date='2025-05-13', stk_p0=1009, stk_p1=990,
    rev_pct='+19.4%', op_pct='+12.2%', net_pct='+51.2%', rev_yoy=19.4, op_dir='up', net_dir='up',
    biz_class='石油・天然ガスE&P / Oil & gas E&P (domestic + overseas)',
    en=S(
        "Japan Petroleum Exploration — JAPEX (1662) — is Japan's second-largest oil and gas exploration and production (E&P) company, after INPEX. It searches for, develops and produces crude oil and natural gas both in Japan and overseas, and it also owns and operates a domestic natural-gas pipeline and supply network (mainly in Hokkaido, Tohoku and Niigata). On top of that it has overseas projects (such as Canadian oil sands) and energy infrastructure and electricity interests. In short: a domestic energy producer whose fortunes rise and fall with oil and gas prices, but with a steadier pipeline and infrastructure layer underneath.",
        "FY3/2025 (announced May 13) looked strong on the headline: revenue +19.4% to ¥389.1bn, operating profit +12.2% to ¥62.0bn, and net profit +51.2% to ¥81.2bn. But recurring profit — the line before one-off items — actually fell -6.7% to ¥64.2bn, so the eye-catching net-profit jump did not come from the core business. The report also paired this with cautious FY3/2026 guidance, with recurring profit guided down sharply (around -44%) on lower assumed oil and gas prices.",
        "Revenue and operating profit rose because the company sold more oil and gas and the price environment during the year was favourable — though recurring profit, the line before one-off items, actually slipped about -7% as non-operating income softened. The much larger +51% jump in net profit was then driven mainly by a one-off: a special gain of roughly ¥42bn from selling part of its long-held INPEX shares (a policy-shareholding reduction the company had already flagged in a November 2024 upward revision). So the core profit trend was flat-to-down, and the headline net-profit surge was largely a one-time share-sale gain rather than stronger operations.",
        "Despite the strong-looking results, in the two weeks after the May 13 announcement the stock slipped about -2% (¥1,009 → ¥990). 1. The same release guided the next year DOWN — lower assumed oil and gas prices, with revenue guided off about -15% — and markets price the future, not the past. 2. Investors also recognised that the eye-catching +51% net-profit jump was mostly a one-off gain from selling INPEX shares, not a sustainable improvement in the core business, so it did not justify paying more. 3. As an E&P producer whose profit tracks oil and gas prices, a softer price outlook reads straight through to lower expected future profit. The good headline simply was not the kind of growth the market pays up for."),
    jp=SJ(
        "石油資源開発 — JAPEX(1662) — は、INPEXに次ぐ国内2位の石油・天然ガスの探鉱・開発・生産(E&P)会社です。国内外で原油・天然ガスを探し、開発し、生産するほか、国内(主に北海道・東北・新潟)の天然ガスのパイプラインと供給網を保有・運営しています。さらに海外プロジェクト(カナダのオイルサンド等)やエネルギーインフラ・電力事業も持ちます。要するに、業績が石油・ガス価格に左右される国内エネルギー生産者でありながら、その下にパイプライン・インフラという安定した層を抱える会社です。",
        "FY3/2025(5月13日発表)は見出しは好調でした — 売上+19.4%の3,891億円、営業利益+12.2%の620億円、純利益+51.2%の812億円。ただし一過性を除く経常利益は-6.7%の642億円と実は減少しており、目を引く純利益増は本業由来ではありません。さらに同じ決算は、原油・ガス価格の前提引き下げでFY3/2026の経常利益を大幅減(約-44%)とする慎重な見通しを伴いました。",
        "売上と営業利益が伸びたのは、石油・ガスの販売数量が増え、期中の価格環境も良好だったためです — ただし一過性項目を除く経常利益は、営業外収益の軟化で実は約-7%減少しました。純利益が+51%と大きく伸びた主因は一過性で、長く保有してきたINPEX株の一部売却による約420億円の特別利益(2024年11月の上方修正で既に示されていた政策保有株の縮減)です。つまり本業の利益基調は横ばい〜減少で、見出しの純利益急増は本業の強化ではなく、一度きりの株式売却益が大半でした。",
        "好調に見える決算にもかかわらず、5月13日の発表後の2週間で株価は約-2%下落しました(¥1,009→¥990)。1. 同じ決算が翌期の見通しを引き下げました — 原油・ガス価格の前提を下げ、売上は約-15%の減収見通し — 市場は過去ではなく将来を織り込みます。2. 投資家は、目を引く純利益+51%が主にINPEX株売却の一過性益であり、本業の持続的な改善ではないと見抜いたため、買い上がる理由になりませんでした。3. 利益が石油・ガス価格に連動するE&P生産者にとって、価格見通しの軟化はそのまま将来利益の低下に直結します。好調な見出しは、市場が対価を払う種類の成長ではなかったのです。"))

C['1518'] = dict(name='Mitsui Matsushima Holdings', sector='Mining', fy_label='FY3/2025', bucket='shrank_but_big_returns',
    announce_date='2025-05-13', stk_p0=831, stk_p1=974,
    rev_pct='-21.8%', op_pct='-70%', net_pct='-42.8%', rev_yoy=-21.8, op_dir='down', net_dir='down',
    biz_class='産業用製品・金融・生活消費財 / Industrial products, financial & consumer (former coal)',
    en=S(
        "Mitsui Matsushima Holdings (1518) is a Fukuoka company best described as a 'former coal company.' Founded in 1913, for over a century it supplied Japan's energy by mining coal in Nagasaki and Australia. As the world turned toward decarbonization it deliberately wound that down — closing its Australian mines and fully exiting coal by FY3/2024. Today it is reinventing itself around three new pillars: industrial products (selling machinery and equipment), financial services (leasing and factoring), and consumer goods. So it is a company in the middle of a big transformation, using the cash it earned in the coal years to build a new, non-coal future.",
        "FY3/2025 (announced May 13) looked weak on the surface: revenue fell -21.8% to ¥60.6bn, operating profit dropped -69.7% to ¥7.6bn, and net profit fell -42.8% to ¥8.6bn. But the shareholder-return news ran the other way: the company raised the full-year dividend from ¥100 to ¥130 (guiding ¥230 for next year) and set up a share buyback of up to ¥1bn / 300,000 shares.",
        "The drop is almost entirely the after-effect of leaving coal. During the 2022–23 energy crisis coal prices spiked and Mitsui Matsushima earned enormous profits; once it exited that business, those outsized coal earnings disappeared, so the year-on-year comparison looks ugly. The newer pillars (industrial products, finance, consumer goods) plus a few small acquisitions are growing, but are still far too small to replace the coal windfall. The company also booked some one-off gains from selling cross-shareholdings and an overseas subsidiary, which softened the fall. So this was not a business breaking down — it was the expected hangover after a deliberate exit from a boom business.",
        "Even with profit down sharply, in the two weeks after the May 13 results the stock jumped about +17% (¥831 → ¥974) — rising nearly 20% within just two trading days. Three reasons. 1. The real draw was shareholder returns: the company raised its dividend from ¥100 to ¥130 and guided to ¥230 next year, and announced a new share buyback — a clear signal it intends to keep handing its coal-era cash pile back to shareholders. 2. Investors had already expected the coal-exit profit drop, so the weak earnings were effectively 'old news,' while the generous payout was the new, positive surprise. 3. With a cash-rich balance sheet and a management team focused on shareholder value, the market treats the company as a capital-return story rather than an earnings-decline story — so the report was cheered, not punished."),
    jp=SJ(
        "三井松島ホールディングス(1518)は、福岡の『元・石炭会社』と呼ぶのが分かりやすい会社です。1913年創業で、長崎や豪州で石炭を採掘し、100年以上にわたり日本のエネルギーを支えてきました。脱炭素の流れの中でそれを意図的に縮小し、豪州炭鉱を閉山してFY3/2024で石炭から完全撤退。今は3つの新しい柱 — 産業用製品(機械・設備の販売)、金融サービス(リース・ファクタリング)、生活消費財 — で再生を図っています。つまり、石炭時代に稼いだ資金を使って『脱・石炭』の新しい未来を築こうとしている、転換の途上にある会社です。",
        "FY3/2025(5月13日発表)は表面上は弱く見えました — 売上-21.8%の606億円、営業利益-69.7%の76億円、純利益-42.8%の86億円。しかし株主還元は逆方向で、年間配当を¥100→¥130へ増配(翌期は¥230を計画)し、最大10億円・30万株の自社株買いも設定しました。",
        "この減少はほぼすべて、石炭から抜けたことの反動です。2022-23年のエネルギー危機で石炭価格が高騰し、三井松島は巨額の利益を上げました。その事業から撤退したため、その並外れた石炭利益が消え、前年比は見栄えが悪くなったのです。新しい柱(産業用製品・金融・生活消費財)と小規模買収は成長していますが、石炭の特需を埋めるにはまだ小さすぎます。会社は政策保有株や海外子会社の売却益という一時的な利益も計上し、減少を和らげました。つまり事業が壊れたのではなく、ブーム事業から意図的に撤退した後の『想定された二日酔い』です。",
        "利益が大きく減ったにもかかわらず、5月13日の決算後の2週間で株価は約+17%上昇しました(¥831→¥974) — わずか2営業日でほぼ+20%上げました。理由は3つ。1. 本当の魅力は株主還元でした。配当を¥100から¥130へ増配し、翌期は¥230を計画、さらに新規の自社株買いも発表 — 石炭時代の現金を株主に還元し続ける明確な意思表示です。2. 投資家は石炭撤退による減益をすでに織り込んでおり、弱い利益は実質『既知』、一方で手厚い還元が新しいポジティブな驚きでした。3. 現金が潤沢なバランスシートと株主価値を重視する経営陣により、市場はこの会社を『減益ストーリー』ではなく『資本還元ストーリー』として扱います — だから決算は罰されず、好感されたのです。"))

C['1663'] = dict(name='K&O Energy Group', sector='Mining', fy_label='FY12/2025', bucket='shrank_but_big_returns',
    announce_date='2026-02-13', stk_p0=4775, stk_p1=5320,
    rev_pct='-1.2%', op_pct='+20.1%', net_pct='+35.9%', rev_yoy=-1.2, op_dir='up', net_dir='up',
    biz_class='天然ガス採掘・ヨウ素事業 / Natural gas extraction & iodine',
    en=S(
        "K&O Energy Group (1663) is an unusual energy company based in Chiba. It was formed in 2009 by merging a natural-gas explorer (Kanto Natural Gas Development — the 'K') with a city-gas supplier (Otaki Gas — the 'O'). It does two main things: it pumps natural gas from a gas field off the Chiba coast and supplies city gas to homes and businesses; and it extracts and refines iodine from underground brine. Iodine is a globally traded commodity used in medicines, LCD screens and chemicals — and Japan is the world's #2 producer — so this gives K&O a valuable second earnings engine alongside gas.",
        "For FY12/2025 (announced Feb 13, 2026) revenue was roughly flat-to-down (about -1.2% to ¥91.4bn), but profits grew strongly: operating profit +20.1% to ¥10.6bn, recurring profit +19.0% to ¥11.6bn, and net profit +35.9% to ¥8.4bn (helped by compensation income from a facility relocation). The company raised the annual dividend to ¥54 and guided ¥60 for next year.",
        "The slight dip in revenue came from lower natural-gas prices being passed through to customers. But profit rose because of iodine: iodine prices were higher and the company sold more of it — volumes rose about +4.5% to roughly 1,800 tons — and that high-margin business lifted operating profit. Net profit jumped even more than operating profit thanks to one-off compensation income the company received in connection with relocating a facility. So the story is 'gas revenue softer, but iodine doing the heavy lifting on profit.'",
        "In the two weeks after the February 13 results the stock rose strongly — to about ¥5,320 from roughly ¥4,775 (about +11%). Reasons. 1. The market liked the quality of the profit growth: it was driven by the iodine business, which is more of a genuine commodity earner than the regulated, pass-through city-gas business. 2. The company raised its dividend (to ¥54 for the year, with ¥60 guided next year), directly rewarding shareholders. 3. Investors looked straight past the tiny revenue dip — because it was just lower gas prices being passed through, not a sign of weaker demand — and focused on the +36% jump in final profit and the higher payout. So a 'lower revenue' headline was actually received as a strong, well-rewarded report."),
    jp=SJ(
        "K&Oエナジーグループ(1663)は、千葉を拠点とする少し変わったエネルギー会社です。2009年に天然ガスの探鉱会社(関東天然瓦斯開発 — 『K』)と都市ガス供給会社(大多喜ガス — 『O』)が合併して誕生しました。主に2つのことを行います。千葉沖のガス田から天然ガスを採掘して家庭・企業に都市ガスを供給すること、そして地下のかん水からヨウ素を採取・精製することです。ヨウ素は医薬・液晶パネル・化学に使われる国際商品で、日本は世界2位の生産国 — そのためガスと並ぶ貴重な第2の収益源になっています。",
        "FY12/2025(2026年2月13日発表)は売上がほぼ横ばい〜小幅減(約-1.2%の914億円)でしたが、利益は力強く成長 — 営業利益+20.1%の106億円、経常利益+19.0%の116億円、純利益+35.9%の84億円(設備移転に伴う補償金も寄与)。年間配当を¥54へ引き上げ、翌期は¥60を計画しました。",
        "売上の小幅な減少は、天然ガス価格の低下が顧客への料金に転嫁されたためです。一方で利益が伸びたのはヨウ素のおかげで、ヨウ素価格が上昇し販売量も増え(約+4.5%、約1,800トン)、この高採算事業が営業利益を押し上げました。純利益が営業利益以上に伸びたのは、設備移転に伴って受け取った一時的な補償金が効いたためです。つまり『ガス収入は軟調でも、利益はヨウ素が牽引』という構図です。",
        "2月13日の決算後の2週間で株価は大きく上昇 — 約¥4,775から¥5,320へ(約+11%)。理由は3つ。1. 利益成長の『質』が好まれました。規制された転嫁型の都市ガスではなく、本来の商品で稼ぐヨウ素事業が牽引したためです。2. 会社が増配(年間¥54、翌期は¥60を計画)を行い、株主に直接報いました。3. 投資家はごく小幅な減収を完全に見過ごしました — それは需要減ではなく単にガス価格の転嫁によるものだからで、むしろ純利益+36%と増配に注目しました。つまり『減収』の見出しは、実際には力強く報われる好決算として受け止められたのです。"))

C['1514'] = dict(name='Sumiseki Holdings', sector='Mining', fy_label='FY3/2025', bucket='commodity_prices_fell',
    announce_date='2025-05-15', stk_p0=745, stk_p1=659,
    rev_pct='-28.8%', op_pct='swung to +¥48m', net_pct='-44%', rev_yoy=-28.8, op_dir='up', net_dir='down',
    biz_class='石炭輸入・資源投資 / Coal import & resource investment',
    en=S(
        "Sumiseki Holdings (1514) is a coal and resources company with Meiji-era roots, founded in 1893 (originally 'Sumitomo Coal Mining'). After Japan's domestic coal mines closed, it reshaped itself into three operating businesses: importing and selling Australian coal to Japanese steel and power companies, making advanced materials such as ceramics, and producing crushed stone for construction. But the key thing to understand is its unusual profit structure: most of its recurring and net profit comes not from those operating businesses but from dividend income on its stake in the Australian Wambo coal mine (in New South Wales), received through an entity called Wanbo. So Sumiseki's bottom line depends less on its own trading and more on how much that Australian mine pays out.",
        "FY3/2025 (announced May 15) was a sharp down year at the bottom line. Revenue fell about -28.8% to ¥10.3bn. Operating profit — from the small coal-trading, materials and crushed-stone businesses — actually swung to a tiny ¥48m profit, a turnaround from a prior-year operating loss. But recurring profit fell -41.9% to ¥4.71bn and net profit -44.3% to ¥4.2bn. The damage was below the operating line — in the non-operating mine-dividend income — not in the operating business itself.",
        "The driver sits in non-operating income. Dividend income from the Australian Wambo mine (received via Wanbo) fell by about ¥3.56bn, because coking-coal prices came down from their earlier peaks and demand softened. Because Sumiseki's recurring and net profit lean so heavily on that mine dividend rather than on its operating businesses, the drop in coal prices fed almost directly into the big falls in recurring and net profit — even though the operating businesses themselves actually improved enough to turn a small profit. That is the flip side of its unusual structure: the day-to-day business can be fine while the bottom line falls with coal prices.",
        "The results were announced after the close on May 15; the stock closed at ¥745 that day and then fell about -12% over the next two weeks to ¥659 (down roughly -9% the very next day). Three reasons. 1. The profit collapse disappointed — recurring and net profit both down more than -40% on the shrinking mine dividend was a clear negative. 2. Sumiseki is held heavily by income-focused investors who own it for the dividend; with earnings down and the dividend outlook cautious, they had less reason to stay and sold. 3. The long-term picture for coal is bleak — with global decarbonization, coking-coal demand and the Wambo mine dividend are likely to keep shrinking, which undermines Sumiseki's main profit source. A very strong balance sheet (equity ratio around 96%) limits bankruptcy risk, but it does not fix the structural fragility of depending on a falling coal-mine dividend."),
    jp=SJ(
        "住石ホールディングス(1514)は明治期にルーツを持つ石炭・資源会社で、1893年創業(元は『住友石炭鉱業』)です。国内炭鉱が閉山した後、3つの本業に姿を変えました — 豪州炭を輸入して日本の鉄鋼・電力会社に販売する事業、セラミックなどの先端素材、建設用の砕石です。しかし最も重要なのはその独特な利益構造です。経常利益・純利益の大半は、これらの本業ではなく、豪州ニューサウスウェールズ州のワンボ(Wambo)炭鉱への出資から得る受取配当(ワンボ社経由)に依存します。つまり住石の最終損益は、自社の取引よりも『その豪州鉱山がいくら配当を払うか』に左右されます。",
        "FY3/2025(5月15日発表)は最終損益で急激な減益の一年でした。売上は約-28.8%の103億円。営業利益(小規模な石炭取引・素材・砕石)は実は¥48百万のわずかな黒字に転換し前期の営業赤字から改善。しかし経常利益は-41.9%の47.1億円、純利益は-44.3%の42億円。痛手は営業利益ではなく、その下の営業外の鉱山配当収入で生じました。",
        "要因は営業外収益にあります。豪州ワンボ(Wambo)鉱山からの受取配当(ワンボ社経由)が約35.6億円減少しました — 原料炭価格が以前の高値から下落し需要も鈍化したためです。住石の経常・純利益は本業よりこの鉱山配当に大きく依存するため、石炭安がほぼそのまま経常・純利益の大幅減につながりました — 本業自体はわずかな黒字に改善したにもかかわらずです。これは独特な構造の裏返しで、日々の事業は順調でも、石炭価格とともに最終損益が落ち込み得るのです。",
        "決算は5月15日の引け後に発表され、当日終値は¥745、その後2週間で約-12%下落して¥659となりました(翌日だけで約-9%)。理由は3つ。1. 減益が失望を招きました — 鉱山配当の縮小で経常・純利益がともに-40%超の減益は明確なマイナスでした。2. 住石は配当目的で保有する利回り重視の投資家が多く、減益と慎重な配当見通しの下では留まる理由が乏しく売却しました。3. 石炭の長期見通しは暗く — 世界の脱炭素で原料炭需要とワンボ鉱山配当は今後も縮小しそうで、住石の主たる収益源を揺るがします。非常に高い自己資本比率(約96%)は倒産リスクを抑えますが、『減少する石炭鉱山配当に依存する』という構造的な脆さは解消しません。"))

C['1605'] = dict(name='INPEX', sector='Mining', fy_label='FY12/2025', bucket='commodity_prices_fell',
    announce_date='2026-02-12', stk_p0=3845, stk_p1=3708,
    rev_pct='-11.2%', op_pct='-10.7%', net_pct='-7.8%', rev_yoy=-11.2, op_dir='down', net_dir='down',
    biz_class='石油・天然ガスE&P大手 / Major oil & gas E&P',
    en=S(
        "INPEX (1605) is Japan's largest oil and gas exploration and production company, and one of the country's most strategically important energy companies — the Japanese government even holds a special 'golden share.' It explores for, develops and produces crude oil and natural gas all over the world; its flagship is the giant Ichthys LNG project in Australia. Because it is a 'pure' producer of oil and gas, its earnings rise and fall almost directly with global energy prices.",
        "For FY12/2025 (announced Feb 12, 2026) revenue fell -11.2% to ¥2.01tn, operating profit about -11% to ¥1,135bn, and net profit -7.8% to ¥394bn — a clear down year, though still hugely profitable in absolute terms. Alongside the results INPEX expanded its buyback (raising the limit by ¥200bn to ¥1tn) and guided FY12/2026 net profit down a further ~16% on softer oil and gas prices.",
        "The decline is almost entirely about price. Crude-oil and natural-gas prices fell back as the energy-price spike of the previous couple of years normalized. Since INPEX simply produces and sells oil and gas, lower prices flow straight through to lower revenue and profit — there is no big downstream or retail business to cushion it. So this was a 'commodity-price down-cycle' year rather than any company-specific problem.",
        "In the two weeks after the February 12 results the stock fell about -4% (roughly ¥3,845 → ¥3,708). It actually popped to ¥3,998 the day after the report before reversing. Reasons. 1. The headline was a profit decline, and management guided to a further ~16% drop in profit the next year on continued softer oil and gas prices — so the market was staring at two down years in a row. 2. INPEX did keep returning cash through a large buyback, which is why the stock first jumped — but the weaker earnings outlook outweighed it, and the initial gain faded. 3. With profits tied directly to energy prices and the price outlook soft, investors had little reason to pay up, so the report ultimately pushed the stock down."),
    jp=SJ(
        "INPEX(1605)は国内最大の石油・天然ガスの探鉱・開発・生産(E&P)会社で、日本で最も戦略的に重要なエネルギー企業の一つです — 政府が特別な『黄金株』を保有しているほどです。世界各地で原油・天然ガスを探鉱・開発・生産し、代表は豪州の巨大なイクシスLNGプロジェクトです。石油・ガスの『純粋な』生産者であるため、利益は世界のエネルギー価格にほぼ直接連動して増減します。",
        "FY12/2025(2026年2月12日発表)は売上-11.2%の2.01兆円、営業利益は約-11%の1兆1,354億円、純利益-7.8%の3,940億円 — 明確な減益の一年ですが、絶対額では依然として極めて高水準です。決算と併せてINPEXは自社株買いを拡大(上限を200億円積み増し1兆円へ)し、FY12/2026は価格軟化でさらに約-16%の純利益減を見込みました。",
        "この減少はほぼすべて価格の問題です。原油・天然ガス価格が、過去2年ほどのエネルギー価格高騰から正常化して下がりました。INPEXは石油・ガスを生産して売るだけなので、価格の低下がそのまま売上・利益の減少に直結します — 緩衝材となる大きな川下・小売事業がないためです。つまり、これは会社固有の問題ではなく『市況の下降局面』の年でした。",
        "2月12日の決算後の2週間で株価は約-4%下落しました(おおむね¥3,845→¥3,708)。実は決算翌日に¥3,998へ一旦上昇した後に反落しています。理由は3つ。1. 見出しは減益で、しかも経営陣は価格軟化の継続を前提に翌期もさらに約-16%の減益を見込みました — 市場は2年連続の減益を見ることになったのです。2. INPEXは大規模な自社株買いで資本還元を続けており、これが株価が最初に跳ねた理由ですが、弱い利益見通しがそれを上回り、初動の上げは消えました。3. 利益が直接エネルギー価格に連動し、その価格見通しも軟調なため、投資家が買い上がる理由は乏しく、決算は最終的に株価を押し下げました。"))

# ===== AirTransport =====
C['9201'] = dict(name='Japan Airlines (JAL)', sector='AirTransport', fy_label='FY3/2025', bucket='record_revenue_dividend_rewarded',
    announce_date='2025-05-02', stk_p0=2629.5, stk_p1=2800.0,
    rev_pct='+11.6%', op_pct='EBIT +18.7%', net_pct='+12.0%', rev_yoy=11.6, op_dir='up', net_dir='up',
    biz_class='フルサービス大手 / Full-service major',
    en=S(
        "Japan Airlines (JAL, 9201) is one of Japan's two dominant full-service carriers, flying domestic and international routes, with budget arms ZIPAIR and Spring Japan plus a sizeable cargo and mileage business. It went bankrupt in 2010 and relisted in 2012, and has run a lean, restructured cost base ever since.",
        "FY3/2025 (announced May 2) was a record year. Revenue rose +11.6% to ¥1,844.0bn — the highest since relisting. EBIT (JAL's headline profit measure) rose +18.7% to ¥172.4bn and net profit +12.0% to ¥107.0bn. The full-year dividend was raised to ¥86 (from ¥80). And JAL guided FY3/2026 up again: revenue ¥1,977.0bn (+7.2%), EBIT ¥200bn (+16%), net profit ¥115.0bn (+7.4%), with the dividend lifted to ¥92.",
        "JAL is a full-service carrier whose earnings ride the recovery in air travel. Inbound tourism into Japan and international passenger demand both kept climbing strongly through the year, lifting passenger revenue, while cargo and the mileage/lifestyle businesses added to the top line. Crucially, the lean cost base and structural reforms built after the 2010 bankruptcy — a disciplined mix of premium full-service, the ZIPAIR/Spring Japan budget arms, and cargo — meant higher revenue flowed efficiently down to profit rather than being eaten by costs. Every segment posted higher revenue and profit. In short: a still-recovering travel market plus a genuinely lean post-bankruptcy cost structure delivered a record year across the board.",
        "In the two weeks after the May 2 results the stock rose about +6.5% (¥2,629.5 → ¥2,800.0). 1. The headline was unambiguously strong — a post-relisting record on revenue and a +12% net-profit gain. 2. JAL raised the dividend to ¥86 and guided the next year up again (revenue +7.2%, EBIT +16%, net +7.4%, dividend ¥92) — positive forward guidance in a sector otherwise worried about fuel costs. 3. With buybacks part of its stated return policy, the market read the report as a clean 'growth + returns' story and bought it."),
    jp=SJ(
        "日本航空(JAL、9201)は日本の二大フルサービス航空の一角で、国内線・国際線を運航し、LCCのZIPAIR・スプリングジャパンに加え相応の貨物・マイル事業も持ちます。2010年に経営破綻し2012年に再上場、以来、筋肉質に再構築したコスト体質で運営しています。",
        "FY3/2025(5月2日発表)は記録的な一年でした。売上は+11.6%の1兆8,440億円と再上場後で最高。EBIT(JALの中心的な利益指標)は+18.7%の1,724億円、純利益は+12.0%の1,070億円。年間配当は¥80から¥86へ増配。さらにFY3/2026も増益見通し — 売上1兆9,770億円(+7.2%)、EBIT2,000億円(+16%)、純利益1,150億円(+7.4%)、配当は¥92へ増配を示しました。",
        "JALは航空需要の回復に業績が連動するフルサービス航空です。訪日インバウンドと国際線旅客の需要がいずれも年間を通じて力強く伸び、旅客収入を押し上げ、貨物やマイル・生活関連事業もトップラインに上乗せしました。重要なのは、2010年の破綻後に築いた筋肉質なコスト構造と構造改革 — プレミアムなフルサービス、ZIPAIR/スプリングジャパンのLCC、貨物の規律ある組み合わせ — により、増収がコストに食われず効率よく利益へ落ちたことです。全セグメントが増収増益。要するに、回復途上の旅行市場と、本当に筋肉質な破綻後コスト構造が、全面的な記録的決算をもたらしました。",
        "5月2日の決算後の2週間で株価は約+6.5%上昇しました(¥2,629.5→¥2,800.0)。1. 見出しが明確に強い — 再上場後最高の売上と純利益+12%。2. 配当を¥86へ増配し、翌期も増益見通し(売上+7.2%、EBIT+16%、純利益+7.4%、配当¥92)の前向きガイダンス — 燃料費を警戒するセクターでの安心材料。3. 自社株買いを還元方針に掲げており、市場は『成長＋還元』のきれいな決算と読んで買いで反応しました。"))

C['9202'] = dict(name='ANA Holdings', sector='AirTransport', fy_label='FY3/2025', bucket='record_revenue_dividend_rewarded',
    announce_date='2025-04-30', stk_p0=2736.0, stk_p1=2868.5,
    rev_pct='+10.0%', op_pct='-5.4%', net_pct='-2.6%', rev_yoy=10.0, op_dir='down', net_dir='down',
    biz_class='フルサービス大手 / Full-service major',
    en=S(
        "ANA Holdings (9202) is Japan's largest airline group — full-service ANA plus budget brands Peach and AirJapan, and a cargo arm — a three-tier premium / budget / cargo structure.",
        "FY3/2025 (announced April 30) set a revenue record: revenue +10.0% to ¥2,261.8bn. But operating profit slipped -5.4% to ¥196.6bn and net profit -2.6% to ¥153.0bn — revenue up, profit down. ANA raised the full-year dividend by ¥10 to ¥60. Its FY3/2026 guidance was cautious, with recurring profit guided about -13%.",
        "ANA is the larger of the two full-service groups, with a more international and cargo-heavy mix. Passenger demand kept climbing — which is why revenue hit a record — but unlike JAL, ANA's profit slipped, because its costs rose faster than that revenue. Higher jet-fuel prices, increased labour costs, and a weak yen (which inflates the dollar-denominated fuel and overseas costs that loom large for a more international carrier) together squeezed margins. So the extra passengers and fares showed up in the top line, but not in the bottom line. In short: record travel revenue, but a heavier, more fuel- and FX-exposed cost base meant profit edged down despite the strong demand.",
        "In the two weeks after the April 30 results the stock rose about +4.8% (¥2,736.0 → ¥2,868.5). 1. Revenue hit a record and the ¥10 dividend increase (to ¥60) signalled confidence and rewarded holders. 2. The profit dip was modest and broadly expected, so it was not a negative surprise. 3. Even with cautious next-year guidance (recurring ~-13% on fuel), the dividend hike plus the record top line was enough for a modest positive reaction."),
    jp=SJ(
        "ANAホールディングス(9202)は日本最大の航空グループで、フルサービスのANAに加え、LCCのPeach・AirJapan、貨物事業を擁するプレミアム/LCC/貨物の三層構造です。",
        "FY3/2025(4月30日発表)は売上が過去最高を更新 — 売上+10.0%の2兆2,618億円。一方、営業利益は-5.4%の1,966億円、純利益は-2.6%の1,530億円と増収減益。年間配当は¥10増配し¥60に。FY3/2026の見通しは慎重で、経常利益は約-13%の見込みとしました。",
        "ANAは2つのフルサービス・グループのうち規模が大きく、国際線・貨物の比重が高い構成です。旅客需要は伸び続け — だから売上は過去最高 — でしたが、JALと異なり利益は減少しました。コストが売上以上に増えたためです。燃料価格の上昇、人件費増、そして円安(国際色の強いキャリアで大きいドル建ての燃料・海外費用を膨らませる)が重なってマージンを圧迫。増えた旅客・運賃はトップラインには表れても、最終損益には届きませんでした。要するに、過去最高の旅行収入でも、より重く燃料・為替に敏感なコスト構造のため、強い需要にもかかわらず利益は小幅減となりました。",
        "4月30日の決算後の2週間で株価は約+4.8%上昇しました(¥2,736.0→¥2,868.5)。1. 売上が過去最高を更新し、¥10の増配(¥60へ)が自信を示し株主に報いました。2. 減益は小幅で概ね想定通りで、悪材料の驚きではありませんでした。3. 翌期の慎重な見通し(燃料で経常約-13%)があっても、増配と過去最高の売上で小幅な上昇には十分でした。"))

C['9204'] = dict(name='Skymark Airlines', sector='AirTransport', fy_label='FY3/2025', bucket='weak_profit_mild_relief',
    announce_date='2025-05-15', stk_p0=509.0, stk_p1=520.0,
    rev_pct='+3.3%', op_pct='-61%', net_pct='-28%', rev_yoy=3.3, op_dir='down', net_dir='down',
    biz_class='中堅国内航空 / Mid-tier domestic carrier',
    en=S(
        "Skymark Airlines (9204) is Japan's #3 carrier, flying domestic routes from Haneda and positioned awkwardly between full-service and ultra-low-cost. It went bankrupt in 2015 and relisted on the TSE Growth market in December 2022 with backing from Integral and ANA.",
        "FY3/2025 (announced May 15) was revenue-up, profit-down. Revenue rose about +3-4% to roughly ¥107.5bn, but operating profit fell about -61% to ¥1.83bn, recurring profit dropped to ¥0.76bn, and net profit fell about -28% (EPS ¥36.14 vs ¥49.93 a year earlier) — dragged by a weak seasonal fourth quarter (Jan-Mar), with the recurring line hit hardest by foreign-exchange losses.",
        "Skymark sits awkwardly between full-service and ultra-low-cost, flying mostly domestic trunk routes from Haneda — a position that gives it little pricing power and thin margins to begin with. Passenger numbers grew only modestly, and that small gain was overwhelmed by higher jet-fuel costs and intensifying competition on those domestic routes. Because its margins were thin to start with, the cost pressure cut deep — especially in the seasonally weak January–March fourth quarter, which dragged the full-year result down. In short: a small revenue gain could not withstand fuel-cost and competition pressure on an already thin-margin, stuck-in-the-middle business model.",
        "In the two weeks after the May 15 results the stock edged up about +2.2% (¥509 → ¥520) — essentially flat-to-slightly-up. 1. The weak profit was no surprise: the nine-month (Q3) numbers back in February had already shown the profit collapse, so the full-year report told the market little new. 2. With expectations already low, the absence of a fresh negative was enough for a small relief bounce. 3. At a depressed price (~¥500, well below its 2022 relisting level), there was limited room to fall on already-known bad news. (The 2-week move is small and partly noise.)"),
    jp=SJ(
        "スカイマーク(9204)は羽田発着の国内線を運航する国内3位で、フルサービスと超低コストの中間という難しい立ち位置です。2015年に経営破綻し、インテグラルとANAの支援で2022年12月に東証グロースへ再上場しました。",
        "FY3/2025(5月15日発表)は増収・減益でした。売上は約+3〜4%の約1,075億円ですが、営業利益は約-61%の18.3億円、経常利益は7.6億円へ減少、純利益は約-28%(EPS ¥36.14 vs 前期¥49.93)。季節的に弱い第4四半期(1〜3月)と為替が重しで、特に経常利益は為替差損が直撃しました。",
        "スカイマークはフルサービスと超低コストの中間という難しい立ち位置で、主に羽田発着の国内幹線を飛びます — 価格決定力が乏しく、もともとマージンが薄い立場です。旅客数の伸びは小幅にとどまり、その小さな増加を、燃料費の上昇と国内路線での競争激化が上回りました。もとよりマージンが薄いため、コスト圧力が深く食い込み — 特に季節的に弱い1〜3月の第4四半期が通期を押し下げました。要するに、わずかな増収では、すでに薄利の『中間的な』ビジネスモデルにかかる燃料費と競争の圧力に耐えられませんでした。",
        "5月15日の決算後の2週間で株価は約+2.2%の小幅高(¥509→¥520) — ほぼ横ばい〜小幅高です。1. 減益は驚きではなく、2月の9か月(Q3)時点で既に利益の落ち込みが示されており、通期決算に新味はほぼありませんでした。2. 期待が既に低く、新たな悪材料がなかったことが小幅な安心感の戻りにつながりました。3. 株価は低迷(約¥500、2022年再上場時を大きく下回る)で、既知の悪材料で下げる余地も限られていました。(2週間の値動きは小さく一部はノイズです。)"))

C['9206'] = dict(name='Star Flyer', sector='AirTransport', fy_label='FY3/2025', bucket='good_results_sold_off',
    announce_date='2025-04-30', stk_p0=2650.0, stk_p1=2222.0,
    rev_pct='+7.2%', op_pct='recovered (¥1.23bn)', net_pct='+110.9%', rev_yoy=7.2, op_dir='up', net_dir='up',
    biz_class='プレミアム・リージョナル / Premium regional',
    en=S(
        "Star Flyer (9206) is a small Kitakyushu-based regional carrier (a fleet of Airbus A320s on a handful of Haneda routes) with a deliberately premium feel — black leather seats, extra legroom. ANA owns about 14% and code-shares its routes. It is a very small, thinly-traded stock.",
        "FY3/2025 (announced April 30) was 増収増益 (higher sales and profit): revenue +7.2% to ¥42.9bn, operating profit recovered strongly to ¥1.23bn, and net profit more than doubled (+110.9%) to ¥1.92bn, helped by a record load factor of 79.6%. For FY3/2026, however, the company guided operating profit higher (+74.7% to ¥2.15bn) but net profit slightly DOWN (-8.5% to ¥1.76bn).",
        "Star Flyer is a tiny premium-regional carrier — a handful of Airbus A320s on Haneda-linked routes, with ANA as a ~14% shareholder and code-share partner. Its earnings turn heavily on how full the planes are: with mostly fixed costs (aircraft, crew, slots), each extra passenger drops almost straight to profit. This year a record load factor of 79.6% lifted revenue, and that operating leverage turned a barely-profitable prior year into a solid recovery — operating profit rebounding to ¥1.23bn and net profit more than doubling to ¥1.92bn. In short: a record load factor, amplified by high operating leverage, drove a strong earnings recovery off a low base.",
        "Despite the good results, the stock fell about -16% in the two weeks after the April 30 report (¥2,650 → ¥2,222), dropping the day after the announcement. 1. The next-year net-profit guidance was actually DOWN (-8.5%), which undercut the strong FY2025 headline — and the market prices the future. 2. It is a very small, thinly-traded stock that had risen into the result, so it saw a sharp 'sell-the-news' pullback amplified by low liquidity. 3. Sector-wide worries about rising fuel costs weighed on the most fuel-sensitive small carrier. (Note: no single disclosure fully explains the size of the drop; this is the most likely combination.)"),
    jp=SJ(
        "スターフライヤー(9206)は北九州を拠点とする小型の地方航空(羽田発着の数路線でA320を運航)で、黒革シートと広い座席間隔のプレミアム志向です。ANAが約14%を保有し路線をコードシェア。非常に小型で流動性の低い銘柄です。",
        "FY3/2025(4月30日発表)は増収増益でした — 売上+7.2%の429億円、営業利益は12.3億円へ大きく回復、純利益は搭乗率79.6%(過去最高)も寄与し倍増以上(+110.9%)の19.2億円。ただしFY3/2026は、営業利益は増益(+74.7%の21.5億円)を見込む一方、純利益は小幅減(-8.5%の17.6億円)の見通しを示しました。",
        "スターフライヤーは超小型のプレミアム・リージョナル航空 — 羽田接続路線でA320を数機運航し、ANAが約14%を保有しコードシェアします。業績は搭乗率に大きく左右され、コストの多く(機材・乗員・発着枠)が固定費のため、増えた旅客はほぼそのまま利益になります。今期は搭乗率が過去最高の79.6%となって売上を押し上げ、この営業レバレッジがほぼ均衡だった前期を確かな回復へ — 営業利益は12.3億円へ回復、純利益は倍増以上の19.2億円。要するに、過去最高の搭乗率が高い営業レバレッジで増幅され、低い基準からの力強い業績回復を生みました。",
        "好決算にもかかわらず、4月30日の決算後の2週間で株価は約-16%下落しました(¥2,650→¥2,222)。発表翌日から下げています。1. 翌期の純利益ガイダンスが実は減益(-8.5%)で、強いFY2025の見出しを打ち消しました — 市場は将来を織り込みます。2. 非常に小型で流動性が低く、決算に向けて上昇していたため、流動性の低さで増幅された『材料出尽くし』の売りが出ました。3. 燃料費上昇というセクター共通の懸念が、最も燃料に敏感な小型キャリアに重くのしかかりました。(注:下落幅のすべてを単一の開示で説明はできず、これらの複合が最も妥当です。)"))

# ===== Petroleum & Coal Products =====
C['5020'] = dict(name='ENEOS Holdings', sector='Petroleum', fy_label='FY3/2025', bucket='commodity_prices_fell',
    announce_date='2025-05-12', stk_p0=712.4, stk_p1=675.5,
    rev_pct='-11.1%', op_pct='-34.6%', net_pct='-21.5%', rev_yoy=-11.1, op_dir='down', net_dir='down',
    biz_class='石油精製・販売最大手 / Largest oil refiner & distributor',
    en=S(
        "ENEOS Holdings (5020) is Japan's largest oil refiner and distributor — about 50% of the country's gas stations — plus JX Metals (copper and electronic materials, separately listed as JX Advanced Metals in March 2025) and overseas oil-and-gas exploration.",
        "FY3/2025 (IFRS, announced May 12) was a clear step down. Revenue fell -11.1% to ¥12.32tn, operating profit -34.6% to ¥262.6bn, and net profit -21.5% to ¥226.1bn. It wasn't all weak — the functional-materials and copper side (JX Metals) grew, with that segment's revenue +13% to ¥347bn — but the huge refining and marketing core set the overall direction. ENEOS also kept a large share-buyback programme running as part of its shareholder-return policy.",
        "The swing is almost entirely about the oil cycle. Crude-oil prices were lower than the year before, which mechanically pulls down ENEOS's reported revenue because it sells fuel priced off crude. More importantly, the refining 'margin' — the gap between what it pays for crude and what it sells refined products for — narrowed from an unusually strong prior year, and the inventory-valuation gains that had flattered FY2024 (when crude is rising, the cheaper oil already sitting in tanks shows a paper profit) reversed this year. Because refining is by far ENEOS's biggest business, that margin normalization dominated, even though copper and electronic-materials demand (EV-related) and overseas oil-field income helped at the edges. In short: a normal commodity down-cycle year — lower crude dragged revenue down, and thinner refining margins plus reversing inventory effects cut profit.",
        "In the two weeks after the May 12 results the stock fell about -5% (¥712.4 → ¥675.5; ENEOS released mid-session, so the prior close is the pre-news baseline). 1. The headline was a -35% profit drop on the refining cycle. 2. A softer crude / refining-margin outlook offered little reason to buy. 3. Even a very large buyback programme and the March-2025 JX Metals listing could not offset the earnings decline, so the report was sold."),
    jp=SJ(
        "ENEOSホールディングス(5020)は国内最大の石油精製・販売会社(給油所シェア約50%)で、加えてJX金属(銅・電子材料、2025年3月にJX Advanced Metalsとして分離上場)と海外石油・ガス開発を持ちます。",
        "FY3/2025(IFRS、5月12日発表)は明確な一段の減益でした。売上-11.1%の12.32兆円、営業利益-34.6%の2,626億円、純利益-21.5%の2,261億円。すべてが弱かったわけではなく、機能材・銅(JX金属)側は成長し同セグメント売上は+13%の3,470億円 — ですが巨大な精製・販売中核が全体の方向を決めました。ENEOSは還元方針の一環で大規模な自社株買いも継続。",
        "変動はほぼ石油サイクルの問題です。原油価格が前年より低く、原油連動で売る燃料の計上売上が機械的に下がります。さらに重要なのは精製『マージン』(原油の仕入と製品の販売価格の差)が異例に強かった前年から縮小し、FY2024を押し上げた在庫評価益(原油上昇時にタンク内の安い在庫が含み益になる)が今期は反転したこと。精製がENEOS最大の事業のため、このマージン正常化が支配的で、銅・電子材料(EV関連)や海外油田収入は端で補うにとどまりました。要するに、通常の市況下降局面 — 原油安が売上を押し下げ、精製マージンの縮小と在庫影響の反転が利益を削りました。",
        "5月12日の決算後の2週間で株価は約-5%下落(¥712.4→¥675.5、ENEOSは場中発表のため前日終値を発表前の基準とする)。1. 見出しは精製サイクルによる-35%の減益。2. 原油・精製マージンの軟調な見通しで買う理由に乏しい。3. 大規模な自社株買いや2025年3月のJX金属上場でも減益を相殺できず、決算は売られました。"))

C['5019'] = dict(name='Idemitsu Kosan', sector='Petroleum', fy_label='FY3/2025', bucket='refining_profit_sold',
    announce_date='2025-05-13', stk_p0=931.0, stk_p1=852.5,
    rev_pct='+5.4%', op_pct='-53.1%', net_pct='-54.5%', rev_yoy=5.4, op_dir='down', net_dir='down',
    biz_class='石油精製・販売 / Oil refiner & distributor (+ high-functional materials)',
    en=S(
        "Idemitsu Kosan (5019) is Japan's #2 oil refiner and distributor (~30% of gas stations), with a distinctive High-Functional Materials arm — OLED blue-emitter materials, lithium-battery materials and overseas lubricants.",
        "FY3/2025 (announced May 13) was 'revenue up, profit sharply down.' Revenue rose +5.4% to ¥9.19tn, but operating profit roughly halved (-53.1%) to ¥162.2bn, recurring profit fell to ¥214.8bn, and net profit dropped -54.5% to ¥104bn. The dividend was ¥36 (on a post-split basis). So the top line grew while the bottom line was cut in half — an unusually wide split that is worth unpacking.",
        "Like ENEOS, Idemitsu is mostly a refiner, so the same forces hit it. Revenue edged up on volumes and pricing, but the prior year (FY2024) had been exceptionally strong, helped by big inventory-valuation gains while crude was rising. This year crude prices were softer, refining margins narrowed, and those earlier inventory gains reversed — so profit fell by more than half even as sales grew. Its High-Functional Materials arm (OLED blue-emitter materials, lithium-battery materials, overseas lubricants) is a genuine growth engine, but it is still far too small to offset a halving of the refining profit. In short: a very strong prior-year base plus a softer refining environment halved profit, while the materials business cushioned only modestly.",
        "In the two weeks after the May 13 results the stock fell about -8% (¥931 → ¥852.5). 1. The day after the report it dropped ~-8% on the halved profit. 2. The refining environment was clearly cooling from its peak. 3. Even with shareholder returns, the scale of the profit collapse dominated and investors sold."),
    jp=SJ(
        "出光興産(5019)は国内2位の石油精製・販売会社(給油所シェア約30%)で、OLEDの青色発光材料、リチウム電池材料、海外潤滑油などの高機能材料部門が独自の柱です。",
        "FY3/2025(5月13日発表)は『増収・大幅減益』でした。売上は+5.4%の9.19兆円ですが、営業利益はほぼ半減(-53.1%)の1,622億円、経常利益は2,148億円、純利益-54.5%の1,040億円。配当は¥36(株式分割後)。トップラインは伸びたのに最終利益は半減という、異例に大きな乖離です。",
        "ENEOS同様、出光も中核は精製のため、同じ力が働きました。数量・価格で売上は小幅増でしたが、前期(FY2024)は原油上昇局面の大きな在庫評価益で異例に好調でした。今期は原油安で精製マージンが縮小し、その在庫評価益も反転 — 増収でも利益は半分以下に。高機能材料部門(OLED青色発光材料、リチウム電池材料、海外潤滑油)は本物の成長エンジンですが、精製利益の半減を埋めるにはまだ小さすぎます。要するに、非常に強い前年ベースと精製環境の軟化が利益を半減させ、材料事業は小幅に緩和したにとどまりました。",
        "5月13日の決算後の2週間で株価は約-8%下落(¥931→¥852.5)。1. 決算翌日に利益半減を嫌気し約-8%下落。2. 精製環境がピークから明確に冷え込み。3. 株主還元があっても減益の規模が支配的で、投資家は売りました。"))

C['5021'] = dict(name='Cosmo Energy Holdings', sector='Petroleum', fy_label='FY3/2025', bucket='refining_profit_sold',
    announce_date='2025-05-13', stk_p0=3081.0, stk_p1=3032.5,
    rev_pct='+2.6%', op_pct='-14.1%', net_pct='-29.7%', rev_yoy=2.6, op_dir='down', net_dir='down',
    biz_class='石油精製・販売・再エネ / Oil refiner + wind power',
    en=S(
        "Cosmo Energy Holdings (5021) is a mid-tier energy group with three pillars: oil refining and distribution (Cosmo-brand stations), petroleum exploration, and renewable energy (Cosmo Eco Power, wind-led).",
        "FY3/2025 (announced May 13) was again revenue-up, profit-down. Revenue rose +2.6%, but operating profit fell -14% to ¥128.2bn and net profit -30% to ¥57.7bn. Capital returns were notably generous: an ¥18bn buyback, and the dividend raised ¥30 to ¥330 (the dividend floor was also lifted to ¥330), taking the total return ratio to about 58% (excluding inventory effects).",
        "Cosmo is a mid-sized refiner with two extra legs — petroleum exploration and renewable energy (Cosmo Eco Power, wind-led). The profit fall came from the refining core: just like its bigger peers, Cosmo saw refining margins soften and the prior year's inventory-valuation gains fade, so profit dropped even though revenue ticked up. The exploration and wind-power businesses provided a genuine cushion — part of why the decline (operating profit -14%) was milder than Idemitsu's halving — but they could not fully offset the weaker refining result. In short: the same refining-margin normalization that hit the whole sector, partly softened by Cosmo's exploration and renewables, and wrapped in an unusually generous capital-return package.",
        "In the two weeks after the May 13 results the stock fell only about -2% (¥3,081 → ¥3,032.5). 1. Profit was clearly down. 2. But the generous capital return (¥330 dividend, ¥18bn buyback, ~58% total return) cushioned the reaction. 3. The net decline, while real, was milder than peers' — so the report was sold only mildly."),
    jp=SJ(
        "コスモエネルギーホールディングス(5021)は、石油精製・販売(コスモブランドの給油所)、石油開発、再生可能エネルギー(コスモエコパワー=風力中心)の3本柱を持つ中堅エネルギーグループです。",
        "FY3/2025(5月13日発表)も増収・減益でした。売上は+2.6%ですが、営業利益-14%の1,282億円、純利益-30%の577億円。資本還元はとりわけ手厚く、180億円の自社株買いと¥30増配の¥330(下限配当も¥330へ引き上げ)で、在庫影響を除く総還元性向は約58%。",
        "コスモは精製を中核に、石油開発と再生可能エネルギー(コスモエコパワー=風力中心)の2つの脚を持つ中堅です。減益は精製中核から来ました — 大手同様、精製マージンが軟化し前年の在庫評価益も剥落したため、増収でも利益は減少。石油開発・風力は実質的な下支えとなり(営業利益-14%と、出光の半減より穏やかだった一因)、それでも精製の弱さを完全には相殺できませんでした。要するに、セクター全体を襲った精製マージンの正常化が主因で、コスモの開発・再エネが一部和らげ、異例に手厚い還元で包まれた決算でした。",
        "5月13日の決算後の2週間で株価は約-2%の小幅下落(¥3,081→¥3,032.5)。1. 利益は明確に減少。2. ただ手厚い還元(¥330配当、180億円自社株買い、総還元性向約58%)が反応を和らげた。3. 純利益の減少は同業より穏やかで、決算は小幅な売りにとどまりました。"))

C['5009'] = dict(name='Fuji Kosan', sector='Petroleum', fy_label='FY3/2025', bucket='refining_profit_sold',
    announce_date='2025-05-15', stk_2w=-4.0, stk_approx=True,
    rev_pct='+10.4%', op_pct='-12.3%', net_pct='+18.1%', rev_yoy=10.4, op_dir='down', net_dir='up',
    biz_class='石油多角化 / Diversified energy',
    en=S(
        "Fuji Kosan (5009) is a small/mid-cap energy company that began as a petroleum-products distributor and diversified into five segments — petroleum, used-oil recycling, environmental energy, rental and home LPG — making it less crude-price-driven than the majors. (It moved to a holding company, Fuji Unite Holdings, on Oct 1, 2025 — after this report.)",
        "FY3/2025 (announced May 15) was a genuinely mixed picture. Revenue rose +10.4% to ¥68.3bn, but operating profit fell -12.4% and recurring profit -13.0% to ¥0.82bn — while net profit actually rose +18.1% to ¥0.72bn, lifted by one-off gains. (The company later moved to a holding-company structure, Fuji Unite Holdings, on Oct 1, 2025 — after this report.)",
        "Fuji Kosan is a small, diversified energy distributor — petroleum products plus used-oil recycling, environmental energy, rental and home LPG — which makes it less directly exposed to crude prices than the big refiners. Revenue grew on fuel volumes and pricing, but day-to-day operating and recurring profit slipped as costs rose faster than the gross margin. The reason the final net profit still rose is one-off: the company booked extraordinary gains from selling idle assets and a power-plant interest, which lifted the bottom line above the operating trend. In short: a growing top line but softer operating profit, with the headline net-profit rise flattered by one-time asset-sale gains rather than the core business improving.",
        "In the two weeks after the May 15 results the stock fell (≈ -4%, approximate). 1. The recurring-profit decline (-13%) disappointed. 2. The stock printed a year-to-date low (¥1,180) the very next day. 3. It traded down with a soft petroleum tape. (Exact 2-week close is approximate: the ticker was later removed from data feeds when Fuji Kosan delisted in the Oct-2025 holding-company reorg; the direction is firmly negative, anchored on the documented day-after YTD low.)"),
    jp=SJ(
        "富士興産(5009)は、石油製品販売を起点に、石油・廃油リサイクル・環境エネルギー・レンタル・家庭用LPGの5事業へ多角化した中小型エネルギー会社で、大手より原油価格に左右されにくい構造です。(2025年10月1日に持株会社「富士ユナイトHD」へ移行 — 本決算より後。)",
        "FY3/2025(5月15日発表)は実にまちまちな内容でした。売上は+10.4%の683億円ですが、営業利益-12.4%、経常利益-13.0%の8.2億円 — 一方で純利益は一過性益に支えられ+18.1%の7.2億円。(同社は本決算後の2025年10月1日に持株会社『富士ユナイトHD』へ移行。)",
        "富士興産は小型で多角化したエネルギー流通会社 — 石油製品に加え、廃油リサイクル・環境エネルギー・レンタル・家庭用LPG — で、大手精製会社ほど原油価格に直接さらされません。燃料の数量・価格で売上は伸びましたが、コストが粗利を上回って増えたため、日々の営業・経常利益は低下。最終の純利益が増えたのは一過性の理由で、遊休資産や発電所持分の売却による特別利益を計上し、本業のトレンドを上回りました。要するに、トップラインは成長も営業利益は軟化し、見出しの純利益増は本業改善ではなく一度きりの資産売却益に化粧されたものでした。",
        "5月15日の決算後の2週間で株価は下落(約-4%、概算)。1. 経常利益の減少(-13%)を嫌気。2. 翌日に年初来安値(¥1,180)を付けた。3. 軟調な石油株地合いとともに下落。(2週間後の正確な終値は概算: 2025年10月の持株会社化に伴う上場廃止で後にデータ配信から銘柄が削除されたため。方向は、開示された翌日の年初来安値に基づき明確に下落。)"))

C['5011'] = dict(name='Nichireki Group', sector='Petroleum', fy_label='FY3/2025', bucket='steady_specialty_rewarded',
    announce_date='2025-05-12', stk_p0=2450.0, stk_p1=2506.0,
    rev_pct='+2.6%', op_pct='+4.1%', net_pct='+8.0%', rev_yoy=2.6, op_dir='up', net_dir='up',
    biz_class='アスファルト・道路舗装 / Asphalt products & road paving',
    en=S(
        "Nichireki Group (5011) is Japan's largest maker of asphalt-applied products (emulsions, modified asphalt, waterproofing, paving materials) plus a road-paving construction arm — the quiet backbone of the country's road infrastructure. Customers include the transport ministry, local governments and the NEXCO expressway operators.",
        "FY3/2025 (announced May 12) was steady and all-up. Revenue rose +2.6%, operating profit +4.1%, recurring profit +4%, and net profit +8%, and the company raised the dividend by ¥5. The growth is modest, but every line moved the right way — and it extends a multi-year revenue-growth streak.",
        "Nichireki is the quiet backbone of Japan's roads: it makes asphalt emulsions, modified asphalt and paving materials, and also does the paving construction itself, selling mainly to the transport ministry, local governments and the NEXCO expressway operators. Its demand is driven by public-works budgets and ongoing road maintenance, which were stable, so volumes and prices held firm across both its materials and construction segments. Because there is no big commodity swing in this kind of business, profit simply grew in line with that steady demand rather than lurching around. In short: dependable public-works and expressway-maintenance demand produced reliable, modest growth across the whole income statement.",
        "In the two weeks after the May 12 results the stock rose about +2.3% (¥2,450 → ¥2,506). 1. An all-up report plus a dividend increase was cleanly positive. 2. The defensive, infrastructure-linked earnings appeal in an otherwise weak petroleum tape. 3. A steady, low-drama name got a modest, well-deserved bump."),
    jp=SJ(
        "ニチレキグループ(5011)はアスファルト応用製品(乳剤・改質アスファルト・防水・舗装材)で国内最大手、加えて道路舗装工事も行う、道路インフラの「縁の下の力持ち」です。顧客は国交省・自治体・NEXCO各社。",
        "FY3/2025(5月12日発表)は着実に全面増益でした。売上+2.6%、営業利益+4.1%、経常利益+4%、純利益+8%、配当も¥5増配。伸びは緩やかですが全ての利益が正しい方向に動き、複数年の増収基調を延長しました。",
        "ニチレキは日本の道路の『縁の下の力持ち』です — アスファルト乳剤・改質アスファルト・舗装材を作り、舗装工事も自ら手がけ、主な顧客は国交省・自治体・NEXCO各社。需要は公共工事予算と道路の維持補修に左右され、それが安定していたため、材料・工事の両セグメントで数量・価格が底堅く推移しました。この種の事業には大きな市況変動がないため、利益は乱高下せず安定需要に沿って増加。要するに、底堅い公共工事・高速道路維持の需要が、損益計算書全体で信頼できる緩やかな成長を生みました。",
        "5月12日の決算後の2週間で株価は約+2.3%上昇(¥2,450→¥2,506)。1. 全面増益＋増配で明確にポジティブ。2. 軟調な石油株地合いの中でのディフェンシブなインフラ収益の魅力。3. 安定した手堅い銘柄が、相応の小幅高となりました。"))

C['5013'] = dict(name='Yushiro Chemical Industry', sector='Petroleum', fy_label='FY3/2025', bucket='steady_specialty_rewarded',
    announce_date='2025-05-14', stk_p0=1943.0, stk_p1=2011.0,
    rev_pct='+4.8%', op_pct='+40.1%', net_pct='+43.4%', rev_yoy=4.8, op_dir='up', net_dir='up',
    biz_class='金属加工油・潤滑油 / Metalworking fluids & lubricants',
    en=S(
        "Yushiro Chemical Industry (5013) makes metalworking fluids and lubricants — cutting and grinding oils used in auto and industrial manufacturing — sold in Japan and across Asia.",
        "FY3/2025 (announced May 14) revenue rose +4.8% to ¥55.5bn, operating profit +40.1% to ¥5.07bn, and net profit +43.4% to ¥4.3bn (recurring profit +31.7%). The dividend was raised ¥28 to ¥98 — a second straight large hike, pushing the yield to roughly 6%.",
        "Yushiro makes metalworking fluids — the cutting and grinding oils used in auto and industrial manufacturing — sold in Japan and across Asia. Demand for these fluids held up and the company's pricing plus cost control widened margins, so operating profit grew far faster (+40%) than revenue (+5%) — strong operating leverage, where a small sales gain turns into a big profit gain because much of the cost base is fixed. Net profit rose even more, helped by gains below the operating line. (Note: Yushiro only became R- in the LATER FY3/2026, after it deconsolidated a Chinese joint venture — that is a future event, not part of this report.) In short: steady metalworking-fluid demand plus margin gains produced big operating leverage, and a large dividend hike rewarded shareholders on top.",
        "In the two weeks after the May 14 results the stock rose about +3.5% (¥1,943 → ¥2,011). 1. An all-up report. 2. The large dividend hike to ¥98 (a ~6% yield) was the standout, a clear shareholder-return signal. 3. The market rewarded the combination of growth and yield."),
    jp=SJ(
        "ユシロ化学工業(5013)は金属加工油・潤滑油(自動車・産業の製造で使う切削油・研削油)を製造し、日本とアジアで販売しています。",
        "FY3/2025(5月14日発表)は売上+4.8%の555億円、営業利益+40.1%の50.7億円、純利益+43.4%の43億円(経常利益+31.7%)。配当は¥28増配の¥98 — 2期連続の大幅増配で、利回りは約6%に。",
        "ユシロは金属加工油 — 自動車・産業の製造で使う切削油・研削油 — を作り、日本とアジアで販売しています。これらの油の需要が底堅く、価格とコスト管理でマージンが拡大したため、営業利益は売上(+5%)をはるかに上回る+40%で成長 — コストの多くが固定費のため、わずかな増収が大きな増益に変わる『営業レバレッジ』が効きました。純利益は営業外の利益でさらに増加。(注: ユシロがR-になったのは中国JVを連結除外した翌FY3/2026で、本決算とは別の将来の出来事です。)要するに、底堅い金属加工油の需要とマージン改善が大きな営業レバレッジを生み、さらに大幅増配が株主に報いました。",
        "5月14日の決算後の2週間で株価は約+3.5%上昇(¥1,943→¥2,011)。1. 全面増益。2. ¥98への大幅増配(利回り約6%)が際立ち、明確な株主還元シグナル。3. 成長と利回りの組み合わせを市場が評価しました。"))

C['5018'] = dict(name='MORESCO', sector='Petroleum', fy_label='FY2/2025', bucket='steady_specialty_rewarded',
    announce_date='2025-04-11', stk_p0=1122.0, stk_p1=1180.0,
    rev_pct='+7.8%', op_pct='+20.1%', net_pct='-21.0%', rev_yoy=7.8, op_dir='up', net_dir='down',
    biz_class='特殊潤滑油・合成油 / Specialty lubricants & synthetic oils',
    en=S(
        "MORESCO (5018) is a Kobe specialty-chemicals maker — ultra-thin HDD-disk lubricants (a critical hard-drive material), automotive synthetic oils and ATF, industrial synthetic oils, and lithium-battery materials — all niche, high-value-add products. Its fiscal year ends in February.",
        "FY ended February 2025 (announced April 11) was revenue-up, operating-profit-up, but net-down. Revenue rose +7.8% and operating profit +20.1%, while net profit fell -21% to ¥1.01bn. So the underlying business clearly strengthened, even though the very bottom line dipped.",
        "MORESCO is a Kobe specialty-chemicals maker, and its niches are unusual: ultra-thin lubricants coated onto hard-disk-drive platters (a critical HDD material), automotive synthetic oils and ATF, industrial synthetic oils, and lithium-battery materials. Demand for these specialty lubricants and adhesives rose, and that lifted both revenue and operating profit by healthy amounts. The only reason the final net profit fell is a base effect: the previous year had unusually large one-off gains, and this year carried higher tax and other items — so a genuinely stronger operating result still printed a lower net number. In short: the core specialty-chemicals business grew solidly (operating profit +20%); the net-profit dip is a one-off comparison, not a real deterioration.",
        "In the two weeks after the April 11 results the stock rose about +5.2% (¥1,122 → ¥1,180). 1. The strong operating-profit growth (+20%) was the headline the market focused on. 2. Revenue + operating momentum signalled the core business is healthy. 3. The headline net dip was looked through as a one-off base effect."),
    jp=SJ(
        "MORESCO(5018)は神戸の特殊化学品メーカー — 極薄HDDディスク用潤滑油(HDD製造の重要材料)、自動車用合成油・ATF、工業用合成油、リチウム電池材料などニッチ高付加価値品。決算期は2月。",
        "2025年2月期(4月11日発表)は増収・営業増益・最終減益でした。売上+7.8%、営業利益+20.1%、一方で純利益は-21%の10.1億円。最終損益は落ちたものの、本業は明確に強くなりました。",
        "MORESCOは神戸の特殊化学品メーカーで、そのニッチは独特です — HDDのディスク表面に塗る極薄潤滑油(HDDの重要材料)、自動車用合成油・ATF、工業用合成油、リチウム電池材料。これら特殊潤滑油・接着剤の需要が伸び、売上と営業利益をしっかり押し上げました。最終純利益が減った唯一の理由はベース効果で、前期に異例の大きな一過性益があったうえ、今期は税・その他の負担が増えたため — 本当に強い営業実績でも純利益は低く出ました。要するに、中核の特殊化学品事業は堅調に成長(営業利益+20%)し、純利益減は一過性の比較であって実態の悪化ではありません。",
        "4月11日の決算後の2週間で株価は約+5.2%上昇(¥1,122→¥1,180)。1. 力強い営業増益(+20%)が市場の注目した見出し。2. 売上＋営業の勢いが本業の健全さを示した。3. 見出しの純利益減は一過性のベース効果として見越されました。"))

C['5015'] = dict(name='BP Castrol K.K.', sector='Petroleum', fy_label='FY12/2025', bucket='steady_specialty_rewarded',
    announce_date='2026-02-09', stk_p0=943.0, stk_p1=999.0,
    rev_pct='~+12%', op_pct='recurring +16.1%', net_pct='up', rev_yoy=12.0, op_dir='up', net_dir='up',
    biz_class='潤滑油 / Lubricants (BP Castrol Japan)',
    en=S(
        "BP Castrol K.K. (5015) is the Japan arm of BP's global Castrol automotive-lubricants brand — engine oils, ATF, grease and industrial lubricants — with brand value built on decades of F1, MotoGP and WRC sponsorship. Its fiscal year ends in December.",
        "FY12/2025 (announced Feb 9, 2026) revenue rose ~+12% (a fifth straight year of growth) and recurring profit +16.1% to ¥1.64bn — beating the company's own ¥1.57bn plan — with the dividend raised ¥2. A third straight year of profit growth.",
        "BP Castrol K.K. is the Japan arm of BP's global Castrol lubricants brand, with brand strength built on decades of F1, MotoGP and WRC sponsorship. Firm demand for lubricants together with pricing kept both revenue and profit growing. Crucially, this is a steady, brand-led consumer and industrial business rather than a bet on crude-oil prices, so its earnings are far less volatile than the refiners' — which is exactly why it could grow profit in the same year the big refiners saw theirs fall. In short: a defensive, brand-driven lubricants business delivered another year of steady growth and a profit beat, decoupled from the refining cycle.",
        "In the two weeks after the Feb 9 results the stock rose about +6% (¥943 → ¥999; noon release, so the prior close is the baseline). 1. Recurring profit beat the plan (+16%). 2. The steady multi-year growth plus a dividend increase rewarded holders. 3. A defensive, brand-led name stood out against the volatile refiners."),
    jp=SJ(
        "ビーピー・カストロール(5015)はBPの世界的潤滑油ブランド「カストロール」の日本法人 — エンジンオイル・ATF・グリース・工業用潤滑油 — で、F1/MotoGP/WRCのスポンサーで数十年かけてブランド価値を築いています。決算期は12月。",
        "FY12/2025(2026年2月9日発表)は売上が約+12%(5期連続増収)、経常利益+16.1%の16.4億円と会社計画(15.7億円)を上回り、¥2の増配。3期連続の増益です。",
        "ビーピー・カストロールはBPの世界的潤滑油ブランド『カストロール』の日本法人で、F1/MotoGP/WRCのスポンサーで数十年かけて築いたブランド力が強みです。潤滑油の底堅い需要と価格が、売上と利益をともに成長させました。重要なのは、これが原油価格に賭けるのではなくブランド主導の安定した消費・産業ビジネスである点で、精製各社より利益のブレがはるかに小さく — だからこそ大手精製が減益となった同じ年に増益を実現できました。要するに、精製サイクルから切り離された、ディフェンシブでブランド主導の潤滑油事業が、もう一年の着実な成長と計画超過の増益を達成しました。",
        "2月9日の決算後の2週間で株価は約+6%上昇(¥943→¥999、場中発表のため前日終値が基準)。1. 経常利益が計画を上回った(+16%)。2. 安定した複数年の成長＋増配が株主に報いた。3. 変動の大きい精製株の中で、ディフェンシブなブランド銘柄が際立ちました。"))

C['5010'] = dict(name='Nippon Seiro', sector='Petroleum', fy_label='FY12/2025', bucket='down_but_recovery_guidance',
    announce_date='2026-02-16', stk_p0=260.0, stk_p1=318.0,
    rev_pct='down*', op_pct='recurring -59.6%', net_pct='-61%', rev_yoy=-10.3, op_dir='down', net_dir='down',
    biz_class='石油ワックス / Petroleum wax specialist',
    en=S(
        "Nippon Seiro (5010) is Japan's specialist maker of petroleum wax — paraffin and microcrystalline waxes used in candles, packaging, cosmetics and industrial applications. Its fiscal year ends in December.",
        "FY12/2025 (announced Feb 16, 2026) was a sharp down year: revenue fell (sources differ on the magnitude — roughly -10% to -29% on a possible fiscal-transition basis), recurring profit -59.6% to ¥0.68bn and net profit about -61%. But the company guided FY12/2026 recurring profit to rebound +91% (≈¥1.3bn) — a V-shaped recovery.",
        "Nippon Seiro is Japan's specialist maker of petroleum wax — the paraffin and microcrystalline waxes used in candles, packaging, cosmetics and many industrial products. This year, demand and margins for wax were weak, and there was no repeat of the prior year's one-off benefits, so profit fell heavily. One housekeeping point: the company has a December fiscal year-end (an earlier project note that called it March-end was wrong), and its reporting appears to span a fiscal-year change, which is why sources disagree on the precise revenue rate — but the direction is unambiguously down. In short: a weak year for wax demand and margins drove a steep profit decline, even as management projected a strong rebound the following year.",
        "In the two weeks after the Feb 16 results the stock surged about +22% (¥260 → ¥318). 1. The standout was the FY2026 guidance — a V-shaped +91% recovery in recurring profit. 2. This is a very small, thinly-traded micro-cap (~¥200-300), so the recovery story produced outsized percentage swings. 3. The market looked straight past the weak past year to the rebound. (Note: low liquidity makes the magnitude volatile; revenue % is flagged.)"),
    jp=SJ(
        "日本精蝋(5010)は石油ワックス(パラフィン・マイクロクリスタリンワックス、ロウソク・包装・化粧品・工業用途)の専門メーカーです。決算期は12月。",
        "FY12/2025(2026年2月16日発表)は急減益の一年: 売上は減少(減少率はソースにより差があり、会計期間変更の可能性もあり概ね-10〜-29%)、経常利益-59.6%の6.8億円、純利益約-61%。一方、会社はFY12/2026の経常利益を+91%(約13億円)へV字回復する見通しを示しました。",
        "日本精蝋は石油ワックス — ロウソク・包装・化粧品・多くの工業用途に使うパラフィン・マイクロクリスタリンワックス — の専門メーカーです。今期はワックスの需要とマージンが弱く、前年の一過性メリットの再現もなかったため、利益は大きく減少しました。整理として、同社は12月決算(以前のプロジェクト注記が3月決算としていたのは誤り)で、報告が会計期間の変更を跨ぐとみられるため、売上の正確な率はソースにより食い違います — ただし方向は明確に減少。要するに、ワックス需要とマージンの弱い一年が急減益を招き、一方で経営陣は翌期の力強い回復を見込みました。",
        "2月16日の決算後の2週間で株価は約+22%急騰(¥260→¥318)。1. 際立ったのはFY2026ガイダンス — 経常利益+91%のV字回復。2. 非常に小型で薄商いの銘柄(約¥200〜300)のため、回復ストーリーが大きな変動率を生んだ。3. 市場は弱い過年度を越えて回復を評価。(注: 流動性が低く変動率は大きい。売上%はフラグ付き。)"))

# ===== Marine / Shipping =====
C['9101'] = dict(name='Nippon Yusen (NYK)', sector='Marine', fy_label='FY3/2025', bucket='shipping_upcycle_rewarded',
    announce_date='2025-05-08', stk_p0=4892, stk_p1=5242,
    rev_pct='+8.4%', op_pct='+20.7%', net_pct='+109%', rev_yoy=8.4, op_dir='up', net_dir='up',
    biz_class='総合海運大手 / Major diversified shipping line',
    en=S(
        "Nippon Yusen (NYK, 9101) is Japan's largest shipping company and one of the big-three lines. It is a comprehensive ocean-and-logistics group: container shipping through its roughly one-third stake in the ONE alliance, plus car carriers, dry bulk, LNG and energy transport, and logistics. Founded in 1885, it is core trade infrastructure. Simply put: a global ocean-logistics conglomerate whose profit swings with container freight rates.",
        "FY3/2025 (announced May 8) was a banner year: revenue +8.4% to ¥2,588.7bn, operating profit +20.7% to ¥210.8bn, recurring profit +87.8% to ¥490.9bn, and net profit +109% to ¥477.7bn, with the dividend raised to ¥325. For the next year (FY3/2026) the company guided recurring profit down sharply (around -48%) and a dividend cut.",
        "The container up-cycle did the heavy lifting. Red Sea diversions since late 2023 kept ships on longer routes and freight rates high, so the profit NYK books from its ONE container stake — which flows in below the operating line, into recurring and net profit — roughly doubled, while operating profit rose a more modest ~21%. Car carriers and LNG added steady earnings. In short: the ONE container boom nearly doubled recurring and net profit.",
        "In the two weeks after the May 8 results the stock rose about +7.2% (¥4,892 → ¥5,242). 1. The headline was a blowout — net profit +109% and recurring +88%. 2. The dividend was raised to ¥325, rewarding holders. 3. Even though the same report guided the next year sharply lower (recurring ~-48%, a dividend cut), the market focused on the record current-year cash and bought it."),
    jp=SJ(
        "日本郵船(NYK、9101)は国内最大の海運会社で、海運大手3社の一角です。コンテナ船(ONEアライアンスに約3分の1出資)に加え、自動車船、ばら積み船、LNG・エネルギー輸送、物流を擁する総合海運・物流グループ。1885年創業で、貿易インフラの中核。要するに、コンテナ運賃で利益が変動する世界的な海運・物流コングロマリットです。",
        "FY3/2025(5月8日発表)は記録的な一年: 売上+8.4%の2兆5,887億円、営業利益+20.7%の2,108億円、経常利益+87.8%の4,909億円、純利益+109%の4,777億円、配当は¥325へ増配。翌期(FY3/2026)は経常利益の大幅減(約-48%)と減配を見込みました。",
        "牽引役はコンテナの上昇局面。2023年末以降の紅海迂回で船が長い航路を取り運賃が高止まりし、NYKがONEから計上する利益(営業利益の下、経常・純利益に入る)がほぼ倍増、一方で営業利益は約+21%と控えめでした。自動車船・LNGも安定収益を上乗せ。要するに、ONEのコンテナ好況が経常・純利益をほぼ倍増させました。",
        "5月8日の決算後の2週間で株価は約+7.2%上昇(¥4,892→¥5,242)。1. 純利益+109%・経常+88%という圧巻の見出し。2. 配当を¥325へ増配し株主に還元。3. 同じ決算が翌期の大幅減(経常約-48%、減配)を示しても、市場は当期の記録的な現金に注目して買いました。"))

C['9107'] = dict(name='Kawasaki Kisen (K-Line)', sector='Marine', fy_label='FY3/2025', bucket='shipping_upcycle_rewarded',
    announce_date='2025-05-07', stk_p0=1946, stk_p1=2133,
    rev_pct='+9.4%', op_pct='+22.2%', net_pct='+199%', rev_yoy=9.4, op_dir='up', net_dir='up',
    biz_class='総合海運大手 / Major diversified shipping line',
    en=S(
        "Kawasaki Kisen (K-Line, 9107) is the third of Japan's big-three shipping lines — container shipping via its roughly 31% stake in the ONE alliance, plus car carriers, dry bulk and LNG/energy. Simply put: a freight-cycle play whose earnings are dominated by its ONE container stake.",
        "FY3/2025 (announced May 7) was extraordinary: revenue +9.4% to ¥1,047.9bn, operating profit +22.2% to ¥102.9bn, recurring profit +132% to ¥308.1bn, and net profit +199% to ¥305.4bn — close to a triple. The dividend was ¥100, with ¥100 also planned for the next two years.",
        "As with NYK, the ONE container alliance is the engine: the Red Sea-driven freight boom sent ONE's profit — booked below K-Line's operating line — sharply higher, so recurring and net jumped far more than operating profit. K-Line's smaller earnings base makes those percentage swings even bigger than peers'. In short: ONE's container-boom earnings nearly tripled K-Line's net profit.",
        "In the two weeks after the May 7 results the stock rose about +9.6% (¥1,946 → ¥2,133). 1. Net profit nearly tripled (+199%) — a powerful headline. 2. The steady ¥100 dividend, backed by K-Line's record of large buybacks, reinforced a strong capital-return story. 3. The market rewarded the cash-machine year — the best 2-week reaction in the sector."),
    jp=SJ(
        "川崎汽船(K-Line、9107)は海運大手3社の3番手 — コンテナ船(ONEに約31%出資)に加え、自動車船、ばら積み船、LNG・エネルギー。要するに、ONEのコンテナ持分が利益を左右する運賃サイクル銘柄です。",
        "FY3/2025(5月7日発表)は驚異的: 売上+9.4%の1兆479億円、営業利益+22.2%の1,029億円、経常利益+132%の3,081億円、純利益+199%の3,054億円とほぼ3倍。配当¥100、翌2期も¥100を計画。",
        "NYK同様、エンジンはONEコンテナ連合。紅海起因の運賃好況でONEの利益(K-Lineの営業利益の下に計上)が急増し、経常・純利益が営業利益を大きく上回って伸びました。利益ベースが小さいK-Lineは変動率がさらに大きくなります。要するに、ONEのコンテナ好況が純利益をほぼ3倍にしました。",
        "5月7日の決算後の2週間で株価は約+9.6%上昇(¥1,946→¥2,133)。1. 純利益ほぼ3倍(+199%)の強力な見出し。2. 安定した¥100配当と、大型自社株買いの実績が強い還元ストーリーを補強。3. 市場はこの『キャッシュマシン』の年を評価 — セクターで最良の2週間反応。"))

C['9104'] = dict(name='Mitsui O.S.K. Lines (MOL)', sector='Marine', fy_label='FY3/2025', bucket='shipping_upcycle_rewarded',
    announce_date='2025-04-30', stk_p0=4739, stk_p1=5003,
    rev_pct='+9.1%', op_pct='+46.3%', net_pct='+62.6%', rev_yoy=9.1, op_dir='up', net_dir='up',
    biz_class='総合海運大手 / Major diversified shipping line',
    en=S(
        "Mitsui O.S.K. Lines (MOL, 9104) is one of the big-three, deliberately balanced between volatile container shipping (its ONE stake) and stable, long-term LNG-carrier and car-carrier contracts, with dry bulk, ferries and real estate alongside. Simply put: a diversified ocean-logistics group balancing swingy container earnings with stable energy and long-term contracts.",
        "FY3/2025 (announced April 30) was strong across the board: revenue +9.1% to ¥1,775.5bn, operating profit +46.3% to ¥150.9bn, recurring profit +62.1% to ¥419.7bn, and net profit +62.6% to ¥425.5bn, with a year-end dividend of ¥180.",
        "The container up-cycle lifted MOL's ONE earnings (which sit in recurring and net profit), while the long-term LNG and car-carrier contracts added their usual steady profit. Recurring and net profit jumped about +62% — strong, though less than NYK's or K-Line's because MOL is the most diversified and least container-dependent of the three. In short: the up-cycle drove a big profit jump, moderated by MOL's stabler, less container-levered mix.",
        "In the two weeks after the April 30 results the stock rose about +5.6% (¥4,739 → ¥5,003). 1. Profit jumped ~62% with a healthy dividend. 2. The gain was a bit smaller than NYK's or K-Line's — MOL's lower container leverage made for a less explosive headline. 3. A sub-1x PBR and cyclical-peak caution kept the re-rating modest."),
    jp=SJ(
        "商船三井(MOL、9104)は大手3社の一角で、変動の大きいコンテナ船(ONE持分)と、安定したLNG船・自動車船の長期契約を意図的に組み合わせ、ばら積み船・フェリー・不動産も持ちます。要するに、変動するコンテナ収益と安定したエネルギー・長期契約を均衡させる多角的な海運・物流グループです。",
        "FY3/2025(4月30日発表)は全面的に好調: 売上+9.1%の1兆7,755億円、営業利益+46.3%の1,509億円、経常利益+62.1%の4,197億円、純利益+62.6%の4,255億円、期末配当¥180。",
        "コンテナ上昇局面がMOLのONE利益(経常・純利益に計上)を押し上げ、LNG船・自動車船の長期契約が安定収益を上乗せ。経常・純利益は約+62%と力強いものの、MOLは3社で最も多角化しコンテナ依存が低いためNYK・K-Lineより伸びは小さめ。要するに、上昇局面が大幅増益を生み、MOLの安定的でコンテナ依存の低い構成がそれを和らげました。",
        "4月30日の決算後の2週間で株価は約+5.6%上昇(¥4,739→¥5,003)。1. 利益が約+62%増、健全な配当。2. 上げ幅はNYK・K-Lineよりやや小さく — コンテナ・レバレッジが低い分、見出しの派手さに欠けた。3. PBR1倍割れとシクリカルのピーク警戒が再評価を抑えました。"))

C['9110'] = dict(name='NS United Kaiun', sector='Marine', fy_label='FY3/2025', bucket='shipping_upcycle_rewarded',
    announce_date='2025-04-30', stk_p0=3765, stk_p1=3835,
    rev_pct='+6.1%', op_pct='-6.4%', net_pct='+3.5%', rev_yoy=6.1, op_dir='down', net_dir='up',
    biz_class='ばら積み海運(日本製鉄系) / Dry-bulk shipping (Nippon Steel group)',
    en=S(
        "NS United Kaiun (9110) is a dry-bulk shipping specialist in the Nippon Steel group — it carries iron ore, coal and other raw materials for steelmaking, plus a tramper and coastal bulk business. Simply put: the Nippon Steel group's dedicated bulk carrier, with earnings tied to steel-raw-material volumes and dry-bulk freight rates.",
        "FY3/2025 (announced April 30) revenue rose +6.1% to ¥247.4bn, but operating profit slipped -6.4% to ¥20.2bn and recurring profit -14.3% to ¥19.0bn, while net profit edged up +3.5% to ¥18.6bn. The dividend was a high ¥240 (¥115 interim + ¥125 year-end).",
        "Revenue rose on firm raw-material shipping volumes and bulk rates, but operating and recurring profit eased against a strong prior-year base and higher costs; net profit still rose slightly on non-operating items. In short: a solid bulk year — revenue up, but operating/recurring profit down modestly from a high base.",
        "In the two weeks after the April 30 results the stock rose about +1.9% (¥3,765 → ¥3,835). 1. Revenue up plus a high ¥240 dividend was taken positively. 2. The profit dips were already broadly expected. 3. But as a steel-tied bulk name facing a softer freight outlook, the reaction was muted — the mildest of the sector's gainers."),
    jp=SJ(
        "NSユナイテッド海運(9110)は日本製鉄グループのばら積み海運専業 — 製鉄向けの鉄鉱石・石炭などの原料を輸送し、不定期船・内航ばら積みも手がけます。要するに、製鉄原料の輸送量とばら積み運賃に業績が連動する、日本製鉄グループ専属のバルカーです。",
        "FY3/2025(4月30日発表)は売上+6.1%の2,474億円も、営業利益-6.4%の202億円、経常利益-14.3%の190億円、一方で純利益は+3.5%の186億円。配当は高水準の¥240(中間¥115＋期末¥125)。",
        "原料輸送量とばら積み運賃の底堅さで増収も、好調だった前年ベースとコスト増で営業・経常利益は低下。純利益は営業外項目で小幅増。要するに、増収の手堅いばら積みの年ながら、高いベースから営業・経常利益は小幅減でした。",
        "4月30日の決算後の2週間で株価は約+1.9%上昇(¥3,765→¥3,835)。1. 増収と高い¥240配当を好感。2. 利益の小幅減は概ね織り込み済み。3. ただ製鉄連動のばら積みで運賃見通しが軟調なため反応は限定的 — セクターの上昇組で最も穏やか。"))

C['9115'] = dict(name='Meiji Kaiun (Meikai Group)', sector='Marine', fy_label='FY3/2025', bucket='shipping_upcycle_rewarded',
    announce_date='2025-05-15', stk_p0=631, stk_p1=690,
    rev_pct='+3.9%', op_pct='-3.4%', net_pct='-45.8%', rev_yoy=3.9, op_dir='down', net_dir='down',
    biz_class='船舶保有・不動産 / Ship-owner & real estate',
    en=S(
        "Meiji Kaiun (Meikai Group, 9115) is a ship-owning and chartering company — it owns vessels and charters them to operators including the big lines — with sizeable Tokyo real-estate and hotel businesses alongside. Simply put: a ship-owner/lessor plus property and hotels, earning charter income (often via equity-method ship investments) and rents.",
        "FY3/2025 (announced May 15) revenue rose +3.9% to ¥67.5bn and operating profit slipped -3.4% to ¥11.0bn, but recurring profit jumped +56.5% to ¥9.13bn — while net profit fell -45.8% to ¥2.81bn. The dividend was held at ¥5. (The company is changing its fiscal year-end, so period comparisons are somewhat irregular.)",
        "Recurring profit surged because income from the company's equity-method ship investments rose with the strong charter market; revenue and operating profit moved only modestly. Net profit fell only because the prior year had included a large one-off special gain that did not repeat. In short: strong recurring profit from ship-investment income, while the net drop is a one-off base effect, not weakness.",
        "In the two weeks after the May 15 results the stock rose about +9.4% (¥631 → ¥690). 1. The +56% recurring-profit jump was the headline that mattered. 2. The asset-backed story — owned ships plus Tokyo property — supports the value case. 3. The market looked past the optically weak net figure (a one-off base effect) and re-rated the shares."),
    jp=SJ(
        "明治海運(明海グループ、9115)は船舶保有・貸船会社 — 自社で船を保有し大手などのオペレーターに貸し出します — に、東京の不動産・ホテル事業を併せ持ちます。要するに、船主・リース業＋不動産・ホテルで、貸船収入(多くは持分法の船舶投資経由)と賃料を稼ぐ会社です。",
        "FY3/2025(5月15日発表)は売上+3.9%の675億円、営業利益-3.4%の110億円、一方で経常利益は+56.5%の91.3億円へ急増 — ただし純利益は-45.8%の28.1億円。配当は¥5据え置き。(会計年度末を変更中のため期間比較はやや変則的。)",
        "経常利益が急増したのは、好調な用船市況で持分法の船舶投資からの利益が伸びたため。売上・営業利益の動きは小幅。純利益が減ったのは、前年に大きな一過性の特別利益があり今年は不在だったからだけです。要するに、船舶投資による経常利益は力強く、純利益減は一過性のベース効果で実態の悪化ではありません。",
        "5月15日の決算後の2週間で株価は約+9.4%上昇(¥631→¥690)。1. 経常利益+56%の急増が効いた見出し。2. 自社保有船＋東京不動産という資産backedのバリュー・ストーリーが支え。3. 市場は見かけの弱い純利益(一過性のベース効果)を見越して株を再評価しました。"))

C['9130'] = dict(name='Kyoei Tanker', sector='Marine', fy_label='FY3/2025', bucket='shipping_upcycle_rewarded',
    announce_date='2025-05-13', stk_p0=952, stk_p1=985,
    rev_pct='+6.9%', op_pct='turned positive', net_pct='+248%', rev_yoy=6.9, op_dir='up', net_dir='up',
    biz_class='タンカー専業(NYK系) / Specialty tanker (NYK group)',
    en=S(
        "Kyoei Tanker (9130) is a mid-tier specialty tanker operator — very large crude carriers (VLCC) and LPG carriers (VLGC) — and a Nippon Yusen (NYK) group company (NYK owns about 30%), serving customers including NYK and Cosmo Oil. Simply put: a small NYK-group tanker company moving crude oil and LPG, with a tightly-held share float.",
        "FY3/2025 revenue rose +6.9% to ¥15.16bn, operating profit recovered to ¥1.37bn (from a ¥1.24bn loss the year before), recurring profit jumped to ¥1.03bn (+452%), and net profit rose to ¥5.11bn (from ¥1.47bn) — the net inflated by a large one-off vessel-sale gain. The dividend was doubled to ¥40 (from ¥20).",
        "Firmer tanker charter rates — helped by Chinese crude-stockpiling demand — turned the core operation back to an operating profit, and a vessel sale produced a large one-off gain that lifted net profit well above the operating line. In short: a genuine tanker-rate turnaround plus a one-off vessel-sale gain, with the dividend doubled on the back of it.",
        "In the two weeks after the results the stock rose about +3.5% (¥952 → ¥985). 1. The operating turnaround plus the doubled dividend (¥20 → ¥40) were clear positives. 2. Firmer tanker-rate sentiment helped. 3. But the tightly-held float (~30% held by NYK) and small size kept the move modest. (Exact announcement date ~mid-May; the 2-week reaction is positive across the plausible window.)"),
    jp=SJ(
        "共栄タンカー(9130)は中堅の専業タンカー会社 — VLCC(大型原油船)とVLGC(大型LPG船) — で、日本郵船(NYK)グループ(NYKが約30%保有)。主要顧客にNYKやコスモ石油。要するに、原油・LPGを運ぶ小型のNYK系タンカー会社で、浮動株が少ない銘柄です。",
        "FY3/2025は売上+6.9%の151.6億円、営業利益は前期の-12.4億円の赤字から+13.7億円へ回復、経常利益は+452%の10.3億円、純利益は前期14.7億円から51.1億円へ急増 — 純利益は大きな一過性の船舶売却益で膨らみました。配当は¥20→¥40へ倍増。",
        "中国の原油備蓄需要に支えられタンカー運賃が底堅くなり本業が営業黒字に復帰、加えて船舶売却の大きな一過性益が純利益を営業利益より大きく押し上げました。要するに、タンカー運賃の黒字転換＋一過性の船舶売却益で、それを背景に増配(倍増)も実施しました。",
        "決算後の2週間で株価は約+3.5%上昇(¥952→¥985)。1. 黒字転換＋配当倍増(¥20→¥40)が明確な好材料。2. タンカー運賃の地合い改善も追い風。3. ただNYKが約30%保有し浮動株が薄く、規模も小さいため動きは限定的。(正確な発表日は5月中旬頃、2週間反応は妥当な範囲で一貫してプラス。)"))

C['9119'] = dict(name='Iino Kaiun (Iino Lines)', sector='Marine', fy_label='FY3/2025', bucket='shipping_revenue_up_but_sold',
    announce_date='2025-05-08', stk_p0=1024, stk_p1=978,
    rev_pct='+2.8%', op_pct='-10.3%', net_pct='-7.0%', rev_yoy=2.8, op_dir='down', net_dir='down',
    biz_class='タンカー・不動産 / Tankers & real estate',
    en=S(
        "Iino Kaiun (Iino Lines, 9119) is a shipping-plus-real-estate company — ocean transport of chemicals, LPG/ammonia and oil products via specialized tankers, alongside a real-estate arm anchored by the landmark Iino Building in Tokyo. Simply put: a specialty-tanker operator with a stable Tokyo office-property business underneath.",
        "FY3/2025 (announced May 8) revenue rose +2.8% to ¥141.9bn, but operating profit fell -10.3% to ¥17.1bn, recurring profit -20.3% to ¥17.4bn, and net profit -7.0% to ¥18.4bn. The report paired this with cautious FY3/2026 guidance — recurring profit guided down sharply and a dividend cut.",
        "Revenue edged up, but shipping margins normalized from an unusually strong prior year, so profit fell across the board; the steady real-estate arm gave ballast. In short: revenue up but profit down off a high base — and, more importantly, a weak forward outlook.",
        "In the two weeks after the May 8 results the stock fell about -4.5% (¥1,024 → ¥978). 1. Profit was down and, more importantly, the FY3/2026 guidance was notably weak — a sharp recurring downgrade plus a dividend cut signalled a clearly tougher year ahead. 2. The market prices the future, not the in-line past year. 3. The stable real-estate value cushioned the fall to a moderate -4.5%."),
    jp=SJ(
        "飯野海運(飯野ライン、9119)は海運＋不動産の会社 — 化学品・LPG/アンモニア・石油製品を専用タンカーで輸送し、東京のランドマーク『飯野ビルディング』を中核とする不動産事業も持ちます。要するに、安定した東京のオフィス不動産事業を下に抱える専業タンカー会社です。",
        "FY3/2025(5月8日発表)は売上+2.8%の1,419億円も、営業利益-10.3%の171億円、経常利益-20.3%の174億円、純利益-7.0%の184億円。同じ決算が翌期(FY3/2026)の慎重な見通し — 経常利益の大幅減と減配 — を伴いました。",
        "売上は小幅増も、海運マージンが異例に強かった前年から正常化し利益は全般に低下。安定した不動産事業が下支え。要するに、増収でも高いベースから減益 — そして何より弱い先行きでした。",
        "5月8日の決算後の2週間で株価は約-4.5%下落(¥1,024→¥978)。1. 減益に加え、より重要なのはFY3/2026ガイダンスが明確に弱かったこと — 経常の大幅下方と減配が、厳しい翌年を示唆。2. 市場は横ばいの過去ではなく将来を織り込む。3. 安定した不動産価値が下げを-4.5%程度に和らげました。"))

C['9171'] = dict(name='Kuribayashi Shosen', sector='Marine', fy_label='FY3/2025', bucket='shipping_revenue_up_but_sold',
    announce_date='2025-05-09', stk_p0=1122, stk_p1=1080,
    rev_pct='+8.6%', op_pct='+76.5%', net_pct='+20.3%', rev_yoy=8.6, op_dir='up', net_dir='up',
    biz_class='内航RoRo海運 / Coastal RoRo shipping',
    en=S(
        "Kuribayashi Shosen (9171) is a long-established coastal RoRo (roll-on/roll-off) shipping company linking Hokkaido and Honshu — carrying paper, steel, building materials and vehicles — with side businesses in Hokkaido hotels and real estate. Simply put: a domestic coastal-cargo line shuttling freight between Hokkaido and the main islands.",
        "FY3/2025 (announced May 9) was strongly all-up: revenue +8.6% to ¥53.1bn, operating profit +76.5% to ¥2.71bn, recurring profit +60.2% to ¥3.30bn, and net profit +20.3% to ¥2.01bn. The company also doubled its dividend, to ¥25 from ¥12.",
        "The Hokkaido-Honshu coastal RoRo core grew cargo volumes (construction materials, general cargo, vehicles, plus new wood-pellet cargo) and ran its ships more efficiently; because shipping costs are largely fixed, modest revenue growth turned into a big profit jump. In short: a genuinely strong, all-up year for the coastal RoRo business, capped by a doubled dividend.",
        "Despite the all-up results and doubled dividend, the stock fell about -3.7% (¥1,122 → ¥1,080) in the two weeks after the May 9 report. 1. The shares had already run up about 10% into the announcement (to ¥1,280 on May 8), so the good news was largely priced in — a classic 'buy the rumor, sell the news.' 2. As a tiny, thinly-traded small-cap with little analyst coverage, it had no fresh buyers to sustain the rally. 3. So even a strong report and a dividend hike could not prevent a give-back."),
    jp=SJ(
        "栗林商船(9171)は北海道と本州を結ぶ内航RoRo(自走で積み下ろし)海運の老舗 — 紙・鉄鋼・建材・車両を運び、北海道のホテル・不動産も副事業に持ちます。要するに、北海道と本州の間で貨物を輸送する内航海運会社です。",
        "FY3/2025(5月9日発表)は力強い全面増益: 売上+8.6%の531億円、営業利益+76.5%の27.1億円、経常利益+60.2%の33.0億円、純利益+20.3%の20.1億円。配当も¥12→¥25へ倍増しました。",
        "北海道-本州間の内航RoRo中核が貨物量(建材・一般貨物・車両、加えて木質ペレットの新規貨物)を伸ばし、配船も効率化。海運は固定費中心のため、小幅な増収が大きな増益につながりました。要するに、内航RoRoの力強い全面増益の年で、配当倍増で締めくくられました。",
        "全面増益と配当倍増にもかかわらず、5月9日の決算後の2週間で株価は約-3.7%下落(¥1,122→¥1,080)。1. 株価は発表に向けて約10%上昇(5月8日に¥1,280)しており、好材料はほぼ織り込み済み — 典型的な『材料出尽くし』。2. 極めて小型で出来高が薄くカバーも乏しいため、上昇を支える新規の買いがなかった。3. 強い決算と増配でも、反落を防げませんでした。"))

C['9308'] = dict(name='Inui Kisen (Inui Global Logistics)', sector='Marine', fy_label='FY3/2025', bucket='shipping_revenue_up_but_sold',
    announce_date='2025-05-13', stk_p0=1328, stk_p1=1217,
    rev_pct='+7.7%', op_pct='+118%', net_pct='+321%', rev_yoy=7.7, op_dir='up', net_dir='up',
    biz_class='ばら積み海運・不動産 / Dry-bulk shipping & real estate',
    en=S(
        "Inui Kisen (Inui Global Logistics, 9308) is a dry-bulk shipping company (Handysize/Handymax bulk carriers) that also runs a substantial Tokyo real-estate business and holds a large investment-securities portfolio. Simply put: a small dry-bulk operator with significant property and investment assets on the side.",
        "FY3/2025 (announced May 13) revenue rose +7.7% to ¥31.8bn, operating profit +118% to ¥3.66bn, recurring profit +100% to ¥3.84bn, and net profit jumped +321% to ¥5.02bn. But the company took a ¥2.49bn impairment loss, and set the dividend at ¥76 — cut from the ¥111.89 it had originally planned for the year.",
        "Firmer dry-bulk freight rates plus real-estate and investment income drove revenue and profit up strongly; the impairment was a one-off write-down on specific assets. In short: a strong profit-recovery year, marred by an asset impairment and a dividend set well below the company's earlier plan.",
        "In the two weeks after the May 13 results the stock fell about -8.4% (¥1,328 → ¥1,217) — the sector's weakest reaction. 1. The dividend was cut from the ¥111.89 the company had earlier guided to ¥76, disappointing income-focused holders of this high-yield small-cap. 2. The ¥2.49bn impairment raised questions despite the headline profit surge. 3. So even with revenue and profit sharply up, the report was sold."),
    jp=SJ(
        "乾汽船(乾グローバルロジスティクス、9308)はばら積み海運会社(ハンディサイズ/ハンディマックスのバルカー)で、東京の不動産事業と大きな投資有価証券ポートフォリオも持ちます。要するに、不動産・投資資産を相当持つ小型のばら積み海運会社です。",
        "FY3/2025(5月13日発表)は売上+7.7%の318億円、営業利益+118%の36.6億円、経常利益+100%の38.4億円、純利益は+321%の50.2億円へ急増。ただし24.9億円の減損損失を計上し、配当は当初計画の¥111.89から¥76へ引き下げました。",
        "ばら積み運賃の底堅さに不動産・投資収益が加わり売上・利益が大きく増加。減損は特定資産の一過性の評価減です。要するに、力強い利益回復の年ながら、資産の減損と、会社の当初計画を大きく下回る配当が水を差しました。",
        "5月13日の決算後の2週間で株価は約-8.4%下落(¥1,328→¥1,217) — セクター最弱の反応。1. 配当が当初計画の¥111.89から¥76へ引き下げられ、高配当狙いの小型株保有者を失望させた。2. 24.9億円の減損が、見出しの利益急増にもかかわらず疑問を呼んだ。3. 売上・利益が大きく増えても、決算は売られました。"))

# ===== Fishery, Agriculture & Forestry =====
C['1301'] = dict(name='Kyokuyo', sector='AgriFishery', fy_label='FY3/2025', bucket='agri_priced_up_but_sold',
    announce_date='2025-05-12', stk_p0=4325, stk_p1=4320,
    rev_pct='+15.7%', op_pct='+25.8%', net_pct='+13.5%', rev_yoy=15.7, op_dir='up', net_dir='up',
    biz_class='水産大手 / Major seafood company',
    en=S(
        "Kyokuyo (1301, founded 1937, TSE Prime) is one of Japan's major seafood companies. Its core business (~60% of sales) sources, processes and distributes a wide range of seafood — tuna, salmon, shrimp, cod roe, crab — from global markets to Japanese buyers, alongside a fresh-fish segment for supermarkets, a frozen prepared-food segment (simmered/grilled fish, snacks) and a cold-chain logistics arm. Simply put: a seafood trader-and-processor whose profit rides global fish prices.",
        "FY3/2025 (announced May 12) was a record: revenue +15.7% to ¥302.7bn, operating profit +25.8% to ¥11.08bn, recurring profit +22.6% to ¥10.86bn, and net profit +13.5% to ¥6.74bn — a sixth straight record. The dividend was raised ¥30 to ¥130, and for FY3/2026 the company guided recurring profit up about +15% with a further ¥20 dividend hike.",
        "Revenue jumped because seafood prices surged globally — salmon, crab and cod roe all got more expensive, inflating the top line — while disciplined sourcing and the higher-margin processed-food range lifted profit. In short: a price-driven record year, with both revenue and profit up and guidance pointing higher again.",
        "Despite the record and the upbeat guidance, the stock was roughly flat (¥4,325 → ¥4,320, -0.1%) in the two weeks after the report. 1. The shares had already run up hard into the print (from ~¥4,120 to ¥4,645 on results day), so the good news was largely priced in. 2. After spiking on the day, it gave the gain back — a textbook 'buy the rumor, sell the news.' 3. With the cyclical seafood-price tailwind seen as near its peak, buyers were unwilling to chase it higher."),
    jp=SJ(
        "極洋(1301、1937年創業、東証プライム)は日本の水産大手。中核(売上の約6割)はマグロ・サーモン・エビ・タラコ・カニなどを世界中から調達・加工し国内に販売する水産事業で、スーパー向けの生鮮事業、煮魚・焼魚・珍味などの食品事業、コールドチェーンの物流事業を併せ持ちます。要するに、世界の魚価で利益が動く水産商社兼加工会社です。",
        "FY3/2025(5月12日発表)は過去最高: 売上+15.7%の3,027億円、営業利益+25.8%の110.8億円、経常利益+22.6%の108.6億円、純利益+13.5%の67.4億円と6期連続の最高益。配当は¥30増の¥130、翌期(FY3/2026)は経常約+15%増とさらに¥20増配を見込みました。",
        "増収は世界的な魚価上昇が主因 — サーモン・カニ・タラコが軒並み値上がりし売上が膨らみ、規律ある調達と利益率の高い加工食品が利益を押し上げました。要するに、価格主導の記録的な年で、増収増益かつ見通しも再び上向き。",
        "記録的決算と強気の見通しにもかかわらず、決算後2週間で株価はほぼ横ばい(¥4,325→¥4,320、-0.1%)。1. 発表前に株価が大きく上昇(約¥4,120→決算日¥4,645)しており、好材料はほぼ織り込み済み。2. 当日急騰後に上げ分を戻す典型的な「材料出尽くし」。3. 魚価の追い風はピーク近辺とみられ、買い上がる動きは乏しかった。"))

C['1332'] = dict(name='Nissui', sector='AgriFishery', fy_label='FY3/2025', bucket='agri_priced_up_but_sold',
    announce_date='2025-05-14', stk_p0=857.8, stk_p1=838.3,
    rev_pct='+6.6%', op_pct='+7.1%', net_pct='+6.4%', rev_yoy=6.6, op_dir='up', net_dir='up',
    biz_class='水産大手 / Major seafood company',
    en=S(
        "Nissui (1332, formerly Nippon Suisan) is one of Japan's big-three seafood companies — global fishing and aquaculture, marine-products trading, processed and frozen foods (a leading chilled-foods brand at home), and a fine-chemicals arm making EPA/DHA from fish oil. Simply put: a vertically-integrated seafood and food group, from the catch to the supermarket shelf.",
        "FY3/2025 (announced May 14) set records: revenue +6.6% to ¥886.1bn, operating profit +7.1% to ¥31.78bn, recurring profit +10.4% to ¥35.30bn, and net profit +6.4% to ¥25.38bn. The dividend was raised ¥4 to ¥28. Management's initial FY3/2026 guidance was for only modest further growth.",
        "Profit rose because the chilled and frozen-food businesses passed rising raw-material costs through into prices while volumes held, and aquaculture earnings firmed. In short: a steady, all-up record year driven by price pass-through and stable demand.",
        "Even so the stock fell about -2.3% (¥857.8 → ¥838.3) in the two weeks after the report. 1. The results were good but broadly in line — no upside surprise to chase. 2. The initial FY3/2026 guidance pointed to only modest growth, a step down from FY2025's pace, which read as cautious. 3. With the food-inflation tailwind maturing, the market took profits rather than re-rating the shares higher."),
    jp=SJ(
        "ニッスイ(1332、旧・日本水産)は日本の水産大手3社の一角 — 世界での漁業・養殖、水産物商事、加工・冷凍食品(国内有数のチルド食品ブランド)、魚油からEPA/DHAを作るファインケミカル事業を持ちます。要するに、漁獲から食卓まで垂直統合した水産・食品グループです。",
        "FY3/2025(5月14日発表)は最高益更新: 売上+6.6%の8,861億円、営業利益+7.1%の317.8億円、経常利益+10.4%の353.0億円、純利益+6.4%の253.8億円。配当は¥4増の¥28。会社の当初FY3/2026見通しは小幅な伸びにとどまりました。",
        "増益は、チルド・冷凍食品が原料高を価格転嫁しつつ数量を維持し、養殖事業も底堅かったため。要するに、価格転嫁と安定需要に支えられた、堅実な全面増益の記録的な年。",
        "それでも決算後2週間で株価は約-2.3%下落(¥857.8→¥838.3)。1. 好決算だが概ね想定線で、買い上がる上振れがなかった。2. 当初のFY3/2026見通しが小幅な伸びにとどまり、FY2025の勢いからは減速で慎重と受け取られた。3. 食品インフレの追い風が成熟し、市場は再評価より利益確定に動いた。"))

C['1333'] = dict(name='Maruha Nichiro', sector='AgriFishery', fy_label='FY3/2025', bucket='agri_priced_up_but_sold',
    announce_date='2025-05-12', stk_p0=1098.33, stk_p1=1005.33,
    rev_pct='+4.7%', op_pct='+14.5%', net_pct='+11.6%', rev_yoy=4.7, op_dir='up', net_dir='up',
    biz_class='水産最大手 / Japan\'s largest seafood company',
    en=S(
        "Maruha Nichiro (1333, later renamed Umios in 2026) is Japan's largest seafood company — global fishing and aquaculture (it is a major bluefin-tuna and salmon farmer), marine-products trading, processed and frozen foods, and overseas operations including a European seafood business and Thai pet-food. Simply put: the country's biggest catch-to-shelf seafood group, now with sizeable overseas arms.",
        "FY3/2025 (announced May 12) was a record: revenue +4.7% to ¥1,078.6bn, operating profit +14.5% to ¥30.38bn (its highest since the 2014 merger), recurring profit +3.7% to ¥32.25bn, and net profit +11.6% to ¥23.26bn, with a raised dividend. But the same report guided FY3/2026 operating profit DOWN about -11% to ¥27.0bn.",
        "FY2025 profit rose on price pass-through and a strong domestic seafood business. For FY2026, though, management planned a ¥5bn one-off 'corporate transformation' cost, and flagged that European cost inflation could not be fully passed on and that Thai pet-food costs were rising — so it guided profit lower. In short: a record year, but paired with a guided step-down for the year ahead.",
        "The stock fell about -8.5% (¥1,098 → ¥1,005) in the two weeks after the report — the sector's sharpest drop. 1. The headline guidance for FY3/2026 operating profit -11% disappointed a market that had bid the shares up. 2. The ¥5bn transformation charge and European/Thai cost warnings raised margin worries. 3. The earnings 'decision score' was strongly negative, and holders sold the day after results — a clear sell-the-news on a guided-down outlook."),
    jp=SJ(
        "マルハニチロ(1333、2026年にUmiosへ社名変更)は日本最大の水産会社 — 世界での漁業・養殖(クロマグロ・サーモン養殖の大手)、水産物商事、加工・冷凍食品、欧州の水産事業やタイのペットフードなど海外事業も持ちます。要するに、漁獲から食卓まで国内最大の水産グループで、海外事業も相当規模です。",
        "FY3/2025(5月12日発表)は過去最高: 売上+4.7%の1兆786億円、営業利益+14.5%の303.8億円(2014年の経営統合以降で最高)、経常利益+3.7%の322.5億円、純利益+11.6%の232.6億円で増配。ただし同じ決算が翌期(FY3/2026)の営業利益を約-11%減の270億円と見込みました。",
        "FY2025の増益は価格転嫁と国内水産の好調が主因。一方FY2026は、50億円の一過性「企業変革費用」を計画し、欧州のコスト高を完全には転嫁できないリスクとタイのペットフードのコスト上昇を織り込んで減益見通しとしました。要するに、記録的な年ながら翌期は計画的な減益とセットでした。",
        "決算後2週間で株価は約-8.5%下落(¥1,098→¥1,005) — セクター最大の下げ。1. FY3/2026営業益-11%の見出しが、買い上がっていた市場を失望させた。2. 50億円の変革費用と欧州・タイのコスト警告がマージン懸念を呼んだ。3. 決算スコアは大きくマイナスで、発表翌日に売られた — 減益見通しに対する明確な「材料出尽くし」。"))

C['1375'] = dict(name='Yukiguni Factory', sector='AgriFishery', fy_label='FY3/2025', bucket='agri_revenue_up_profit_fell',
    announce_date='2025-05-09', stk_p0=1129, stk_p1=1068,
    rev_pct='+11.9%', op_pct='-13.6%', net_pct='+11.3%', rev_yoy=11.9, op_dir='down', net_dir='up',
    biz_class='きのこ生産(まいたけ) / Mushroom producer (maitake)',
    en=S(
        "Yukiguni Factory (1375, formerly Yukiguni Maitake) is one of Japan's largest cultivated-mushroom producers — maitake, eringi (king oyster) and bunashimeji — grown in climate-controlled factories, mainly in Niigata. Simply put: a factory mushroom grower whose margins hinge on selling prices versus energy and packaging costs.",
        "FY3/2025 (announced May 9) saw revenue +11.9% to ¥53.14bn, but operating profit FELL -13.6% to ¥2.42bn even as net profit rose +11.3% to ¥1.50bn. The dividend was raised to ¥15 (from ¥11).",
        "Revenue grew on higher mushroom volumes and prices, but operating profit fell because energy, packaging and raw-material costs rose faster than prices, squeezing the cultivation margin; net profit still rose thanks to non-operating items. In short: top-line growth, but a cost squeeze pushed the core operating profit down.",
        "The stock fell about -5.4% (¥1,129 → ¥1,068) in the two weeks after the report. 1. The headline that mattered was the operating-profit decline — investors read the cost squeeze as the real signal, not the higher revenue. 2. A mushroom grower's earnings live and die on the price-vs-cost spread, and that spread narrowed. 3. With margins under pressure, the market sold the report."),
    jp=SJ(
        "ユキグニファクトリー(1375、旧・雪国まいたけ)は国内最大級の菌床きのこ生産者 — まいたけ・エリンギ・ぶなしめじを空調管理された工場(主に新潟)で生産します。要するに、販売価格と電気・包装コストの差で採算が決まる工場型きのこ生産者です。",
        "FY3/2025(5月9日発表)は売上+11.9%の531.4億円も、営業利益は-13.6%の24.2億円へ減少、一方で純利益は+11.3%の15.0億円。配当は¥11→¥15へ増配。",
        "増収はきのこの数量・価格上昇によるが、電気・包装・原材料コストが価格以上に上昇し栽培採算を圧迫したため営業利益は減少。純利益は営業外項目で増加。要するに、増収でもコスト増が本業の営業利益を押し下げました。",
        "決算後2週間で株価は約-5.4%下落(¥1,129→¥1,068)。1. 効いた見出しは営業減益 — 投資家は増収よりコスト圧迫を実態シグナルと読んだ。2. きのこ生産は価格対コストの差で利益が決まり、その差が縮小した。3. マージン悪化で市場は決算を売った。"))

C['1376'] = dict(name='Kaneko Seeds', sector='AgriFishery', fy_label='FY5/2025', bucket='agri_priced_up_but_sold',
    announce_date='2025-07-11', stk_p0=1386, stk_p1=1376,
    rev_pct='+4.7%', op_pct='+2.2%', net_pct='+1.9%', rev_yoy=4.7, op_dir='up', net_dir='up',
    biz_class='種苗・農業資材 / Seeds & farm supplies',
    en=S(
        "Kaneko Seeds (1376, Gunma, May fiscal year-end) is a seed and agricultural-materials company — it breeds and sells vegetable, flower and rice seeds, and distributes farm chemicals, fertilizers and gardening supplies through a nationwide network. Simply put: a seed breeder and farm-supply distributor serving Japan's growers.",
        "FY5/2025 (announced July 11) revenue rose +4.7% to ¥64.5bn, operating profit +2.2% to ¥1.51bn, recurring profit +6.1% to ¥1.67bn, and net profit +1.9% to ¥1.20bn. The dividend was raised ¥5 to ¥38.",
        "Revenue grew as seed, fertilizer and farm-chemical prices rose with input inflation, but profit barely moved because the distribution side runs on thin margins and the same input costs squeezed them. In short: steady, modest, price-driven growth with little change in already-thin margins.",
        "The stock was roughly flat-to-down (-0.7%, ¥1,386 → ¥1,376) over the two weeks after the report. 1. The results were in line and unexciting — small profit growth on thin margins. 2. There was no dividend or guidance surprise large enough to move a quietly-traded value name. 3. With nothing new to chase, the shares simply drifted slightly lower."),
    jp=SJ(
        "カネコ種苗(1376、群馬、5月決算)は種苗・農業資材の会社 — 野菜・花・稲の種子を育種・販売し、農薬・肥料・園芸資材を全国網で流通させます。要するに、日本の生産者向けの種苗育種＋農業資材の流通会社です。",
        "FY5/2025(7月11日発表)は売上+4.7%の645億円、営業利益+2.2%の15.1億円、経常利益+6.1%の16.7億円、純利益+1.9%の12.0億円。配当は¥5増の¥38。",
        "増収は種子・肥料・農薬の価格が投入インフレで上昇したため。ただし流通事業は薄利で、同じコスト高が採算を圧迫し利益はほぼ横ばい。要するに、価格主導の小幅で堅実な成長で、もともと薄いマージンに大きな変化はなし。",
        "決算後2週間で株価はほぼ横ばい〜小幅安(-0.7%、¥1,386→¥1,376)。1. 想定線で地味な内容 — 薄利での小幅増益。2. 静かなバリュー株を動かすほどの配当・見通しのサプライズがなかった。3. 追う材料がなく、株価は小幅に下げただけ。"))

C['1377'] = dict(name='Sakata Seed', sector='AgriFishery', fy_label='FY5/2025', bucket='agri_priced_up_but_sold',
    announce_date='2025-07-14', stk_p0=3510, stk_p1=3360,
    rev_pct='+4.8%', op_pct='+16.8%', net_pct='-39.9%', rev_yoy=4.8, op_dir='up', net_dir='down',
    biz_class='種苗大手(世界展開) / Global vegetable & flower seed company',
    en=S(
        "Sakata Seed (1377, May fiscal year-end) is a global vegetable- and flower-seed breeder — a world leader in broccoli and several other vegetable seeds — selling its varieties worldwide, with more than half of sales from overseas. Simply put: a Japanese seed-breeding company with a genuinely global, high-value seed business.",
        "FY5/2025 (announced July 14) revenue rose +4.8% to ¥92.9bn and operating profit +16.8% to ¥12.26bn (recurring +10.7% to ¥12.31bn), but net profit FELL -39.9% to ¥9.71bn. The dividend was raised ¥10 to ¥75. The same report guided FY5/2026 recurring profit down about -11%.",
        "The core seed business was strong — operating profit grew solidly on firm overseas vegetable-seed demand and a weak yen. Net profit fell only because the prior year had included a large one-off gain (asset/investment-related) that did not repeat — a base effect, not operational weakness. In short: a strong operating year, with the optically-ugly net drop being a one-off comparison.",
        "The stock fell about -4.3% (¥3,510 → ¥3,360) in the two weeks after the report. 1. The headline net profit -40% looked alarming at a glance, even though it was a base effect. 2. More substantively, the same report guided FY5/2026 recurring profit down about -11%, signalling a softer year ahead. 3. After a steady run, holders sold the combination of an ugly headline and a guided-down outlook."),
    jp=SJ(
        "サカタのタネ(1377、5月決算)は世界展開する野菜・花の種苗育種大手 — ブロッコリーなど複数の野菜種子で世界トップ級で、売上の半分超を海外で稼ぎます。要するに、真にグローバルな高付加価値の種子事業を持つ日本の育種会社です。",
        "FY5/2025(7月14日発表)は売上+4.8%の929億円、営業利益+16.8%の122.6億円(経常+10.7%の123.1億円)も、純利益は-39.9%の97.1億円へ減少。配当は¥10増の¥75。同じ決算が翌期(FY5/2026)の経常を約-11%減と見込みました。",
        "本業の種子事業は好調 — 海外の野菜種子需要と円安で営業利益は堅調に増加。純利益が減ったのは、前年に大きな一過性益(資産・投資関連)があり今年は不在だったため — 実態悪化ではなくベース効果。要するに、本業は強い一年で、見かけの純利益減は一過性の比較によるもの。",
        "決算後2週間で株価は約-4.3%下落(¥3,510→¥3,360)。1. 純利益-40%の見出しは一見不安(実際はベース効果)。2. より本質的に、同じ決算が翌期経常を約-11%減と見込み、減速を示唆。3. 堅調な上昇の後、悪い見出しと減益見通しの組み合わせで売られた。"))

C['1379'] = dict(name='Hokuto', sector='AgriFishery', fy_label='FY3/2025', bucket='agri_mushroom_recovery_rewarded',
    announce_date='2025-05-14', stk_p0=1737, stk_p1=1792,
    rev_pct='+4.6%', op_pct='+108.4%', net_pct='+26.0%', rev_yoy=4.6, op_dir='up', net_dir='up',
    biz_class='きのこ最大手 / World\'s largest mushroom producer',
    en=S(
        "Hokuto (1379, Nagano) is the world's largest cultivated-mushroom producer — bunashimeji, eringi and maitake grown in climate-controlled factories — and also sells the cultivation equipment and packaging for the industry. Simply put: a factory mushroom grower whose profit swings on the spread between mushroom selling prices and energy/material costs.",
        "FY3/2025 (announced May 14) revenue rose +4.6% to ¥83.1bn, and operating profit MORE THAN DOUBLED, +108% to ¥6.63bn, with recurring profit +47.5% to ¥6.95bn and net profit +26.0% to ¥4.44bn. The dividend was held at ¥50, and the same report guided FY3/2026 recurring profit down about -33%.",
        "Operating profit doubled because mushroom selling prices recovered while the energy and packaging costs that had crushed the prior year eased — the price-vs-cost spread swung sharply back in Hokuto's favour. In short: a textbook margin-recovery year, with operating profit rebounding off a depressed base.",
        "The stock rose about +3.2% (¥1,737 → ¥1,792) in the two weeks after the report. 1. Operating profit doubling was a powerful, clear-cut turnaround headline. 2. The market rewarded the margin recovery even though the same report guided FY3/2026 lower — investors treated the FY2025 rebound as the signal. 3. The gain was measured rather than explosive, reflecting that guided-down next year."),
    jp=SJ(
        "ホクト(1379、長野)は世界最大の菌床きのこ生産者 — ぶなしめじ・エリンギ・まいたけを空調管理工場で生産し、業界向けの栽培設備・包装資材も販売します。要するに、きのこの販売価格と電気・資材コストの差で利益が動く工場型きのこ生産者です。",
        "FY3/2025(5月14日発表)は売上+4.6%の831億円、営業利益は倍以上の+108%の66.3億円、経常+47.5%の69.5億円、純利益+26.0%の44.4億円。配当は¥50据え置き、同じ決算が翌期(FY3/2026)の経常を約-33%減と見込みました。",
        "営業利益が倍増したのは、きのこの販売価格が回復する一方、前年に採算を潰した電気・包装コストが和らぎ、価格対コストの差が大きく好転したため。要するに、低かったベースから営業利益が反発した、典型的なマージン回復の年。",
        "決算後2週間で株価は約+3.2%上昇(¥1,737→¥1,792)。1. 営業利益倍増という明快な回復の見出し。2. 同じ決算が翌期を減益と見込んでも、市場はマージン回復を評価 — FY2025の反発をシグナルと捉えた。3. 翌期減益見通しを反映し、上げは急騰ではなく緩やか。"))

C['1380'] = dict(name='Akikawa Bokuen', sector='AgriFishery', fy_label='FY3/2025', bucket='agri_revenue_up_profit_fell',
    announce_date='2025-05-14', stk_p0=982, stk_p1=981,
    rev_pct='+7.6%', op_pct='to a loss', net_pct='-71.4%', rev_yoy=7.6, op_dir='down', net_dir='down',
    biz_class='安全食品の一貫生産 / Integrated safe-food producer',
    en=S(
        "Akikawa Bokuen (1380, Yamaguchi) is an integrated 'safe-food' producer — it raises chickens and produces eggs and milk, makes processed and frozen foods with a focus on additive-light, organic-leaning products, and sells direct to households via a farm-to-home delivery business. Simply put: a small integrated farm-and-food company built around a clean-label, direct-to-consumer brand.",
        "FY3/2025 (announced May 14) revenue rose +7.6% to ¥7.96bn, but profitability collapsed: operating profit slipped to a small loss (from +¥12m), recurring profit -66% to ¥52m, and net profit -71% to ¥28m. The dividend was held at ¥10 — a payout ratio above 100%.",
        "Revenue grew on higher prices and steady demand for its clean-label foods, but feed, energy and logistics costs rose sharply while the company kept investing in production and distribution — so margins were wiped out even as sales grew. In short: revenue up, but a cost-and-investment squeeze pushed the core business into a loss.",
        "The stock was essentially flat (-0.1%, ¥982 → ¥981) over the two weeks after the report. 1. The profit collapse was largely already known from an earlier guidance cut, so it was not a fresh shock. 2. As a tiny, thinly-traded stock with a loyal retail holder base, it had neither aggressive sellers nor buyers. 3. With the bad news priced and no catalyst, the shares simply went nowhere."),
    jp=SJ(
        "秋川牧園(1380、山口)は安全食品の一貫生産者 — 鶏の飼育や鶏卵・牛乳の生産、無添加・有機志向の加工・冷凍食品の製造、家庭への直販(産直宅配)まで手がけます。要するに、クリーンラベルの直販ブランドを軸にした小型の一貫農業・食品会社です。",
        "FY3/2025(5月14日発表)は売上+7.6%の79.6億円も、採算は崩落: 営業利益は小幅赤字に転落(前年+1,200万円)、経常-66%の5,200万円、純利益-71%の2,800万円。配当は¥10据え置きで配当性向は100%超。",
        "増収はクリーンラベル食品の価格上昇と安定需要によるが、飼料・電気・物流コストが急上昇し、生産・流通への投資も続けたため、増収でもマージンが消失。要するに、増収でもコストと投資の圧迫で本業が赤字に転落しました。",
        "決算後2週間で株価はほぼ横ばい(-0.1%、¥982→¥981)。1. 利益の崩落は事前の下方修正で概ね既知で、新たなショックではなかった。2. 極小型で出来高が薄く固定的な個人株主が中心のため、積極的な売りも買いもなかった。3. 悪材料は織り込み済みで触媒もなく、株価は動かなかった。"))

C['1381'] = dict(name='Axyz', sector='AgriFishery', fy_label='FY6/2025', bucket='agri_strong_profit_thin_float',
    announce_date='2025-08-08', stk_p0=3100, stk_p1=3080,
    rev_pct='+2.3%', op_pct='+35.1%', net_pct='+38.8%', rev_yoy=2.3, op_dir='up', net_dir='up',
    biz_class='鶏肉の一貫生産 / Integrated poultry producer',
    en=S(
        "Axyz (1381, Kagoshima, June fiscal year-end) is an integrated broiler-chicken producer — it runs breeding, feed, farming and processing in one chain and supplies chicken to retailers and food-service customers. Simply put: a vertically-integrated chicken company whose margins turn on poultry prices versus feed costs.",
        "FY6/2025 (announced Aug 8) revenue rose +2.3% to ¥26.4bn, while profit jumped: operating profit +35.1% to ¥2.12bn, recurring profit +22.0% to ¥2.17bn, and net profit +38.8% to ¥1.72bn. The dividend was raised ¥14 to ¥112.5.",
        "Profit surged because chicken selling prices stayed firm while feed-grain costs eased from their peak, widening the margin — a small revenue rise translated into a big profit jump thanks to that spread. In short: a strong margin-driven profit year for the integrated chicken business.",
        "Despite the strong results and dividend hike, the stock ended roughly flat-to-down (-0.6%, ¥3,100 → ¥3,080) over the two weeks after the report. 1. The shares popped on results day, then drifted back. 2. Axyz is a small, thinly-traded stock with little analyst coverage, so there were few fresh buyers to sustain a rally. 3. With the good news quickly absorbed by a thin float, the move faded to flat."),
    jp=SJ(
        "アクシーズ(1381、鹿児島、6月決算)は鶏肉(ブロイラー)の一貫生産者 — 種鶏・飼料・飼育・加工を一気通貫で行い、小売・外食に鶏肉を供給します。要するに、鶏肉価格と飼料コストの差で採算が決まる垂直統合の鶏肉会社です。",
        "FY6/2025(8月8日発表)は売上+2.3%の264億円、利益は急増: 営業利益+35.1%の21.2億円、経常+22.0%の21.7億円、純利益+38.8%の17.2億円。配当は¥14増の¥112.5。",
        "増益は、鶏肉の販売価格が底堅い一方で飼料穀物コストがピークから和らぎマージンが拡大したため — その差により、小幅増収が大幅増益につながりました。要するに、一貫鶏肉事業のマージン主導の力強い増益の年。",
        "好決算と増配にもかかわらず、決算後2週間でほぼ横ばい〜小幅安(-0.6%、¥3,100→¥3,080)。1. 決算日に上昇後、上げ分を戻した。2. 小型で出来高が薄くカバーも乏しいため、上昇を支える新規買いが少なかった。3. 好材料が薄い浮動株にすぐ吸収され、横ばいに収束した。"))

C['1382'] = dict(name='Hob', sector='AgriFishery', fy_label='FY6/2025', bucket='agri_volume_down_margins_up',
    announce_date='2025-08-07', stk_p0=1781, stk_p1=1800,
    rev_pct='-4.2%', op_pct='+16.4%', net_pct='+23.5%', rev_yoy=-4.2, op_dir='up', net_dir='up',
    biz_class='いちごの育種・生産・流通 / Strawberry breeding & distribution',
    en=S(
        "Hob (1382, Hokkaido, June fiscal year-end) is a strawberry specialist — it breeds, grows, distributes and sells fresh strawberries and supplies strawberry seedlings to growers, best known for the 'Sachinoka' variety. Simply put: a vertically-integrated strawberry company, from seedling to store shelf.",
        "FY6/2025 (announced Aug 7) revenue FELL -4.2% to ¥2.41bn, but profit rose: operating profit +16.4% to ¥381m, recurring profit +3.6% to ¥395m, and net profit +23.5% to ¥247m. The dividend was held at ¥50.",
        "Revenue fell because strawberry shipment volumes dropped (weather and crop conditions), but higher selling prices and a better product mix more than offset the volume loss at the margin line, so profit rose even as the top line shrank. In short: less fruit sold, but each sale more profitable — revenue down, profit up.",
        "The stock rose about +1.1% (¥1,781 → ¥1,800) in the two weeks after the report. 1. The market looked through the revenue dip to the improved profit and margins. 2. A higher-quality, higher-price strawberry mix is a healthier earnings story than chasing volume. 3. As a small, stable-dividend name, the modest profit beat was enough for a quiet move up."),
    jp=SJ(
        "ホーブ(1382、北海道、6月決算)はいちご専業 — いちごの育種・生産・流通・販売を行い、生産者向けに苗も供給します。「さちのか」などの品種で知られます。要するに、苗から店頭まで垂直統合したいちご会社です。",
        "FY6/2025(8月7日発表)は売上-4.2%の24.1億円と減収も、利益は増加: 営業利益+16.4%の3.81億円、経常+3.6%の3.95億円、純利益+23.5%の2.47億円。配当は¥50据え置き。",
        "減収はいちごの出荷数量の減少(天候・作柄)によるが、販売価格の上昇と構成改善が数量減を採算面で上回り、減収でも増益となりました。要するに、販売量は減ったが1件あたりの採算が改善 — 減収増益。",
        "決算後2週間で株価は約+1.1%上昇(¥1,781→¥1,800)。1. 市場は減収を見越し、改善した利益とマージンに注目。2. 高品質・高価格のいちご構成は、数量を追うより健全な収益ストーリー。3. 小型で安定配当の銘柄として、小幅な利益上振れで静かに上昇した。"))

C['1383'] = dict(name='Berg Earth', sector='AgriFishery', fy_label='FY10/2025', bucket='agri_microcap_drift_up',
    announce_date='2025-12-15', stk_p0=3015, stk_p1=3165,
    rev_pct='+2.9%', op_pct='small loss', net_pct='+21.0%', rev_yoy=2.9, op_dir='down', net_dir='up',
    biz_class='野菜苗(接ぎ木苗)生産 / Vegetable-seedling (grafted) grower',
    en=S(
        "Berg Earth (1383, Ehime, October fiscal year-end) is a vegetable-seedling grower specializing in grafted seedlings (tomato, cucumber, eggplant and other fruit-vegetables) supplied to commercial farms nationwide. Simply put: a small grower of the young grafted plants that vegetable farmers transplant into their fields.",
        "FY10/2025 (announced Dec 15) revenue rose +2.9% to ¥7.30bn, but the core operation stayed in the red: operating profit was a small loss (-¥33m) and recurring profit a loss (-¥29m); net profit was a small positive ¥48m (+21%). The dividend was held at ¥10.",
        "Revenue edged up on firm seedling demand, but high energy and material costs kept the cultivation operation just below break-even; the small net profit came from non-operating items. In short: revenue up and losses narrowing, but the core business is still around break-even.",
        "The stock rose about +5.0% (¥3,015 → ¥3,165) in the two weeks after the report. 1. Narrowing losses and a small net profit were taken as gradual improvement. 2. But Berg Earth is a very small, thinly-traded micro-cap, so the move owes as much to thin-float, year-end small-cap drift as to the report itself. 3. The rise is best read as modest and low-conviction rather than a strong endorsement."),
    jp=SJ(
        "ベルグアース(1383、愛媛、10月決算)は野菜苗(接ぎ木苗)の生産者 — トマト・きゅうり・なすなど果菜類の接ぎ木苗を全国の生産農家に供給します。要するに、農家が畑に植える若い接ぎ木の苗を作る小型の生産者です。",
        "FY10/2025(12月15日発表)は売上+2.9%の73.0億円も、本業は赤字継続: 営業利益は小幅赤字(-3,300万円)、経常も赤字(-2,900万円)、純利益は小幅黒字の4,800万円(+21%)。配当は¥10据え置き。",
        "増収は苗需要の底堅さによるが、電気・資材コスト高で栽培事業は損益分岐点をわずかに下回ったまま。小幅な純利益は営業外項目による。要するに、増収・赤字縮小だが本業はなお損益分岐点近辺。",
        "決算後2週間で株価は約+5.0%上昇(¥3,015→¥3,165)。1. 赤字縮小と小幅黒字が緩やかな改善と受け取られた。2. ただし極小型で出来高が薄く、上昇は決算自体より薄商いの年末小型株の地合いによるところが大きい。3. 強い評価というより小幅で低確信の上昇と読むのが妥当。"))

C['1384'] = dict(name='Hokuryo', sector='AgriFishery', fy_label='FY3/2025', bucket='agri_priced_up_but_sold',
    announce_date='2025-05-14', stk_p0=1455, stk_p1=1444,
    rev_pct='+2.6%', op_pct='-14.3%', net_pct='+31.7%', rev_yoy=2.6, op_dir='down', net_dir='up',
    biz_class='鶏卵の生産・販売 / Egg producer',
    en=S(
        "Hokuryo (1384, Sapporo) is one of Hokkaido's leading egg producers — it runs large-scale layer farms and produces and sells chicken eggs, mainly across Hokkaido and northern Japan. Simply put: a regional egg company whose margins ride egg prices versus feed costs.",
        "FY3/2025 (announced May 14) revenue rose +2.6% to ¥19.40bn, but operating profit FELL -14.3% to ¥1.925bn and recurring profit -13.6% to ¥2.00bn, while net profit rose +31.7% to ¥2.18bn. The dividend was sharply raised, to ¥70 from ¥40.",
        "Revenue grew modestly on firm egg prices, but operating profit fell as feed and energy costs rose and egg prices came off their bird-flu-driven highs; net profit rose only on non-operating/special items. In short: a softer core year (operating profit down) masked by a higher headline net profit.",
        "Despite the big dividend hike, the stock slipped about -0.8% (¥1,455 → ¥1,444) over the two weeks after the report. 1. The operating-profit decline was the substantive signal, and it outweighed the higher net figure. 2. With egg prices normalizing off their peak, the market saw a softer earnings trajectory ahead. 3. The dividend increase cushioned the fall but could not turn it positive — a mild sell on a weaker core."),
    jp=SJ(
        "ホクリヨウ(1384、札幌)は北海道有数の鶏卵生産者 — 大規模採卵養鶏場を運営し、主に北海道・北日本で鶏卵を生産・販売します。要するに、卵価と飼料コストの差で採算が決まる地域の鶏卵会社です。",
        "FY3/2025(5月14日発表)は売上+2.6%の194.0億円も、営業利益は-14.3%の19.25億円、経常-13.6%の20.0億円へ減少、一方で純利益は+31.7%の21.8億円。配当は¥40→¥70へ大幅増配。",
        "増収は卵価の底堅さによるが、飼料・電気コストの上昇と、鳥インフル高騰からの卵価反落で営業利益は減少。純利益は営業外・特別項目で増加。要するに、本業はやや軟調(営業減益)で、見かけの純利益増がそれを覆い隠した形。",
        "大幅増配にもかかわらず、決算後2週間で株価は約-0.8%下落(¥1,455→¥1,444)。1. 営業減益が本質的なシグナルで、純利益増を上回った。2. 卵価がピークから正常化し、市場は先行きの収益鈍化を見た。3. 増配が下げを和らげたがプラスには転じず — 本業軟調への小幅な売り。"))


# ===== Merge LandTransport (defined in separate module for size) =====
from _landtransport_data import LAND_BUCKETS as _LAND_BUCKETS, C as _C_LAND
BUCKETS.update(_LAND_BUCKETS)
C.update(_C_LAND)


def main():
    companies = {}
    sectors = []
    for tk, r in C.items():
        if r['sector'] not in sectors:
            sectors.append(r['sector'])
        p0, p1 = r.get('stk_p0'), r.get('stk_p1')
        if r.get('stk_2w') is not None:
            stk2w = r['stk_2w']
        else:
            stk2w = round((p1 / p0 - 1) * 100, 1)
        approx = r.get('stk_approx', False)
        rev_yoy = r['rev_yoy']
        companies[tk] = {
            'ticker': tk, 'name': r['name'], 'sector': r['sector'], 'fy_label': r['fy_label'], 'bucket': r['bucket'],
            'announce_date': r['announce_date'],
            'rev_pct': r['rev_pct'], 'op_pct': r['op_pct'], 'net_pct': r['net_pct'],
            'revenue_yoy_pct': rev_yoy, 'revenue_dir': 'up' if rev_yoy >= 0 else 'down',
            'op_dir': r['op_dir'], 'net_dir': r['net_dir'],
            'stock_p0': p0, 'stock_p1': p1, 'stock_2w_pct': stk2w,
            'stock_dir': 'up' if stk2w > 0 else 'down',
            'stock_2w_estimate': f'{stk2w:+.1f}% (2 wks after report{", approx" if approx else ""})',
            'biz_classification': r['biz_class'], 'category': cat(rev_yoy, stk2w),
            'en_summary': r['en'], 'jp_summary': r['jp'], 'sources': SRC,
        }

    out = {
        '_meta': {
            'report': '2025Q4', 'report_definition': 'FY2025 full-year report (fiscal year ending in 2025).',
            'revenue_basis': 'Revenue stated in the FY2025 report, YoY vs FY2024. R+ if >=0 else R-.',
            'stock_basis': 'Market reaction to the report: close on the earnings-announcement date vs close ~2 weeks later. S+ if >0 else S-.',
            'point_in_time_rule': 'Narratives use the FY2025 report (incl. its forward guidance) + earlier years only. Never a later report.',
            'narrative_format': '4-section lighter prompt, written qualitatively like UNIFIED_VIEW; stock section uses numbered reasons. Reason buckets (title = the shared driver).',
            'categories': ['R+xS+', 'R+xS-', 'R-xS+', 'R-xS-'], 'sectors_included': sectors,
            'scope': 'Full listed TOPIX-33 sector (incl. previously-excluded R- names); delisted/TOB excluded. Mining first.',
            'generated': '2026-06-13',
        },
        'buckets': BUCKETS, 'companies': companies,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    print(f'Wrote {OUT}  ({len(companies)} companies, sectors: {", ".join(sectors)})')
    for tk, c in companies.items():
        print(f'  {tk} {c["name"]:34} {c["category"]}  rev {c["rev_pct"]:>6}  stock2w {c["stock_2w_pct"]:+.1f}%  ({len(c["en_summary"])} chars EN)')


if __name__ == '__main__':
    main()
