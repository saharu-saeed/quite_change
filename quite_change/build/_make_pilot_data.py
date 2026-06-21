"""Pilot quarterly-data generator (IT sector, 6 companies, calendar-2025 quarters).

Purpose
-------
This is the PILOT input for the new "quarterly / point-in-time / 4-category" view.

Model decisions (to be confirmed with stakeholder before scale-up):
  • A "snapshot" == a CALENDAR QUARTER. For each company we take the latest tanshin
    (quarterly report) it had FILED as of that calendar quarter-end. For a Dec-FY
    company, calendar 2025 contains exactly 4 real filings (FY24 full-year in Feb,
    Q1 in May, H1 in Aug, Q3 in Nov) -> one per calendar quarter. This keeps every
    company on one shared timeline regardless of its fiscal-year end.
  • revenue_dir = standalone-quarter revenue YoY (this fiscal quarter vs the same
    fiscal quarter a year earlier), taken from the report filed in that calendar
    quarter.  R+ if YoY >= 0 else R-.
  • stock_dir  = trailing-12-month price change measured at the calendar quarter-end
    close (close at quarter-end vs close 12 months earlier).  S+ if > 0 else S-.
  • category   = {R+,R-} x {S+,S-}.
  • point-in-time rule: each cell's reasoning may use only reports filed on/before
    that snapshot quarter-end. Never the future.

All numbers below were web-researched (June 2026):
  • revenue YoY  -> stockanalysis.com quarterly financials
  • prices       -> Yahoo Finance chart API (monthly/daily closes)
Reasoning prose is grounded in those researched figures plus widely-documented
company context; in the scale-up each cell gets per-quarter source verification.
"""
from __future__ import annotations
import json, io, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OUT = Path(__file__).parent.parent / 'data' / 'quarterly' / 'pilot_IT_2025.json'
QUARTERS = ['2025Q1', '2025Q2', '2025Q3', '2025Q4']
QEND = {'2025Q1': 'Mar 2025', '2025Q2': 'Jun 2025', '2025Q3': 'Sep 2025', '2025Q4': 'Dec 2025'}

SOURCES = ['stockanalysis.com (quarterly revenue/OP)', 'Yahoo Finance (price history)']


def cat(rev_yoy, stk_yoy):
    r = 'R+' if rev_yoy >= 0 else 'R-'
    s = 'S+' if stk_yoy > 0 else 'S-'
    return f'{r}x{s}'


# Each company: fixed meta + per-quarter [report_label, filed, rev_yoy, op_dir, op_note,
# stk_prev, stk_now, reasoning_en, reasoning_jp]
RAW = {
    '3994': {
        'name': 'Money Forward', 'fy_end': 'Nov',
        'q': {
            '2025Q1': ['FY11/2024 full-year (period end Nov 30 2024)', '2025-01', 21.5, 'down', 'Operating loss by design (growth investment)', 4269, 4005,
                'FY11/2024 results confirm the familiar Money Forward shape: revenue up ~21% YoY on Business-SaaS + Home-SaaS ARR growth, but still an operating loss as the company keeps spending on acquisition and headcount. Over the trailing year the stock has drifted about -6%, the market discounting the persistent losses despite top-line strength. Classic revenue-up / stock-down divergence.',
                'FY11/2024本決算は同社らしい構図を確認。ビジネス・ホーム両SaaSのARR成長で売上は前年比約+21%だが、獲得・人員投資を続けるため営業赤字が継続。株価は過去1年で約-6%と、トップライン好調にもかかわらず赤字継続を市場が織り込み。典型的な「増収・株安」の乖離。'],
            '2025Q2': ['FY11/2025 Q1 (period end Feb 28 2025)', '2025-04', 22.7, 'down', 'Loss narrowing but still negative', 4589, 4905,
                'Q1 FY11/2025 keeps revenue compounding at ~+23% YoY and management signals the operating loss is on a narrowing path. The stock has now turned positive over the trailing year (~+7%), an early sign the market is starting to reward the growth-with-improving-economics story rather than punish the losses.',
                'FY11/2025 Q1も売上は前年比約+23%で複利成長し、経営陣は営業赤字の縮小路線を示唆。株価は過去1年でプラス(約+7%)に転換し、赤字を罰するより「採算改善を伴う成長」を市場が評価し始めた初期サイン。'],
            '2025Q3': ['FY11/2025 Q2 / H1 (period end May 31 2025)', '2025-07', 11.7, 'down', 'Loss narrowing', 4709, 5987,
                'H1 standalone-quarter revenue decelerated to ~+12% YoY (mix/comparison effect) but the re-rating accelerated: the stock is up ~+27% over the trailing year. The market is now firmly in "reward" mode, looking through the softer single-quarter print to the ARR trajectory and the narrowing loss.',
                '上期の単四半期売上は構成・比較要因で前年比約+12%へ減速したが、株価の見直しは加速し過去1年で約+27%。市場は単四半期の弱さを越えてARRの軌道と赤字縮小を評価する「リワード」モードに明確に移行。'],
            '2025Q4': ['FY11/2025 Q3 (period end Aug 31 2025)', '2025-10', 23.0, 'down', 'Loss narrowing', 4323, 3903,
                'Q3 revenue re-accelerated to ~+23% YoY, yet the stock gave back its gains and is down ~-10% over the trailing year as the autumn-2025 growth-stock pullback hit high-multiple SaaS hardest. Fundamentals improving, price falling — the divergence has reopened.',
                'Q3売上は前年比約+23%へ再加速したが、2025年秋の成長株調整が高マルチプルSaaSを直撃し、株価は上昇分を吐き出して過去1年で約-10%。ファンダは改善・株価は下落で、乖離が再び開いた。'],
        },
    },
    '4385': {
        'name': 'Mercari', 'fy_end': 'Jun',
        'q': {
            '2025Q1': ['FY6/2025 H1 (period end Dec 31 2024)', '2025-02', 2.3, 'up', 'Core OP positive; US still a drag', 2392.5, 2355,
                'H1 FY6/2025 shows the marketplace maturing: standalone-quarter revenue grew only ~+2% YoY as Japan GMV plateaus and the US business remains a drag. The stock is roughly flat-to-down (~-2%) over the trailing year. Low-growth, flat price.',
                'FY6/2025上期はマーケットプレイスの成熟を示し、国内GMV頭打ちと米国事業の重しで単四半期売上は前年比約+2%に留まる。株価は過去1年で概ね横ばい〜小幅安(約-2%)。低成長・株価横ばい。'],
            '2025Q2': ['FY6/2025 Q3 (period end Mar 31 2025)', '2025-05', 1.5, 'down', 'OP pressured', 2235, 2674,
                'Q3 revenue growth stayed muted (~+1.5% YoY) and operating profit was pressured, but the stock rallied ~+20% over the trailing year — driven by fintech (Mercoin/Mercard) optimism and broad market recovery rather than the soft top line. Price leading fundamentals.',
                'Q3も売上成長は鈍く(前年比約+1.5%)営業利益は圧迫されたが、株価は過去1年で約+20%上昇。軟調なトップラインではなくフィンテック(メルコイン/メルカード)期待と地合い回復が主因。株価が業績を先行。'],
            '2025Q3': ['FY6/2025 full-year (period end Jun 30 2025)', '2025-08', 4.4, 'up', 'Core OP up', 1947.5, 2276,
                'Full-year FY6/2025 closed with revenue +4% YoY and improving core operating profit. The stock is up ~+17% over the trailing year, confirming the re-rating: modest growth but better profitability is enough for the market.',
                'FY6/2025本決算は売上前年比+4%、コア営業利益も改善で着地。株価は過去1年で約+17%上昇し見直しを確認。緩やかな成長でも採算改善があれば市場には十分。'],
            '2025Q4': ['FY6/2026 Q1 (period end Sep 30 2025)', '2025-11', 2.9, 'up', 'Core OP up', 3730, 3428,
                'Q1 FY6/2026 revenue +2.9% YoY with continued OP improvement, but the stock fell ~-8% over the trailing year as the late-2025 pullback hit it after a strong run. Improving profitability, weaker price.',
                'FY6/2026 Q1は売上前年比+2.9%、営業利益改善が継続するも、好調な上昇の後に2025年末の調整が直撃し株価は過去1年で約-8%下落。採算改善・株価軟調。'],
        },
    },
    '3697': {
        'name': 'SHIFT', 'fy_end': 'Aug',
        'q': {
            '2025Q1': ['FY8/2025 Q1 (period end Nov 30 2024)', '2025-01', 20.3, 'up', 'OP up', 1838.67, 1673,
                'Q1 FY8/2025 revenue grew ~+20% YoY with OP up — the software-QA growth engine still running. But the stock is down ~-9% over the trailing year, still digesting the 2024 de-rating after years of premium multiples. Growth intact, multiple compressing.',
                'FY8/2025 Q1は売上前年比約+20%・営業増益で、ソフトウェア品質保証の成長エンジンは健在。一方、株価は過去1年で約-9%と、長年のプレミアム評価の反動である2024年のディレーティングを消化中。成長は維持・マルチプル収縮。'],
            '2025Q2': ['FY8/2025 Q2 (period end Feb 28 2025)', '2025-04', 15.7, 'down', 'OP down (hiring/margin)', 1311, 1530,
                'Q2 revenue +16% YoY but OP declined on aggressive hiring and margin investment. Despite the profit dip the stock rose ~+17% over the trailing year off oversold lows. Market looking past the margin dip to durable demand.',
                'Q2は売上前年比+16%だが、積極採用と原価投資で営業減益。利益の落ち込みにもかかわらず株価は売られ過ぎ水準から過去1年で約+17%上昇。市場は一時的な減益を越えて底堅い需要を評価。'],
            '2025Q3': ['FY8/2025 Q3 (period end May 31 2025)', '2025-07', 16.9, 'up', 'OP up', 911, 969,
                'Q3 revenue +17% YoY and OP back up; the stock is up ~+6% over the trailing year. Steady compounding, modest re-rating — the cleanest "growth rewarded" quarter of the year for SHIFT.',
                'Q3は売上前年比+17%・営業増益に復帰、株価も過去1年で約+6%。着実な複利成長と緩やかな見直しで、SHIFTにとって年内最もきれいな「成長が報われた」四半期。'],
            '2025Q4': ['FY8/2025 full-year (period end Aug 31 2025)', '2025-10', 16.7, 'down', 'OP down in Q4 standalone', 1250, 702,
                'Full-year revenue +17% but Q4 standalone OP fell, and the stock collapsed ~-44% over the trailing year on guidance disappointment plus the autumn growth-stock rout. The starkest revenue-up / stock-down divergence in the pilot.',
                '通期売上+17%も第4四半期単独の営業減益となり、ガイダンス失望と秋の成長株急落で株価は過去1年で約-44%急落。本パイロットで最も顕著な「増収・株安」の乖離。'],
        },
    },
    '2121': {
        'name': 'MIXI', 'fy_end': 'Mar',
        'q': {
            '2025Q1': ['FY3/2025 Q3 (period end Dec 31 2024)', '2025-02', 5.6, 'up', 'OP up', 2535, 3170,
                'Q3 FY3/2025 revenue +5.6% YoY with OP up, helped by the sports/betting (TIPSTAR) and new ventures offsetting the mature Monster Strike base. The stock is up ~+25% over the trailing year — growth and price aligned.',
                'FY3/2025 Q3は売上前年比+5.6%・営業増益。成熟したモンスト基盤をスポーツ/投票(TIPSTAR)や新規事業が補完。株価は過去1年で約+25%上昇し、成長と株価が一致。'],
            '2025Q2': ['FY3/2025 full-year (Q4 standalone, period end Mar 31 2025)', '2025-05', -1.0, 'up', 'OP up full-year', 3170, 3275,
                'The FY3/2025 full-year report shows the standalone Jan-Mar quarter dipped ~-1% YoY (revenue DOWN) as Monster Strike events lapped tough comps — yet the stock is still up ~+3% over the trailing year on full-year profit strength and buybacks. Revenue-down but stock-up.',
                'FY3/2025本決算では、モンストイベントの反動で1〜3月単四半期が前年比約-1%(減収)。一方、通期の利益堅調と自社株買いで株価は過去1年で約+3%上昇。減収だが株高。'],
            '2025Q3': ['FY3/2026 Q1 (period end Jun 30 2025)', '2025-08', 3.0, 'down', 'OP down', 2727, 2727,
                'Q1 FY3/2026 revenue returned to growth (~+3% YoY) but OP slipped on new-business spend, and the stock is essentially flat-to-down over the trailing year (~0%). Revenue up, price stalled.',
                'FY3/2026 Q1は売上が前年比約+3%で成長に復帰も、新規事業費で営業減益。株価は過去1年で概ね横ばい〜小幅安(約0%)。増収だが株価は足踏み。'],
            '2025Q4': ['FY3/2026 Q2 / H1 (period end Sep 30 2025)', '2025-11', 11.4, 'up', 'OP up', 2667, 2717,
                'H1 standalone-quarter revenue accelerated to ~+11% YoY with OP up, and the stock is up ~+2% over the trailing year. Reacceleration finally showing, price modestly following.',
                '上期の単四半期売上は前年比約+11%へ加速し営業増益、株価も過去1年で約+2%。再加速がようやく顕在化し、株価も小幅に追随。'],
        },
    },
    '3923': {
        'name': 'RAKUS', 'fy_end': 'Mar',
        'q': {
            '2025Q1': ['FY3/2025 Q3 (period end Dec 31 2024)', '2025-02', 23.3, 'up', 'OP up', 1019.25, 1000,
                'Q3 FY3/2025 revenue +23% YoY with OP up — Rakuraku Seisan and Mail Dealer keep compounding. Yet the stock is down ~-2% over the trailing year, a high-multiple SaaS name treading water. Strong growth, flat-to-down price.',
                'FY3/2025 Q3は売上前年比+23%・営業増益で、楽楽精算・メールディーラーが複利成長を継続。一方、株価は過去1年で約-2%と高マルチプルSaaSが足踏み。力強い成長・株価は横ばい〜小幅安。'],
            '2025Q2': ['FY3/2025 full-year (Q4 standalone, period end Mar 31 2025)', '2025-05', 26.4, 'up', 'OP up', 1041.25, 1158.25,
                'Full-year FY3/2025 with the Jan-Mar quarter +26% YoY and OP up; the stock turned up ~+11% over the trailing year. The compounding is being rewarded again.',
                'FY3/2025本決算は1〜3月単四半期が前年比+26%・営業増益、株価も過去1年で約+11%上昇に転換。複利成長が再び評価される。'],
            '2025Q3': ['FY3/2026 Q1 (period end Jun 30 2025)', '2025-08', 25.5, 'up', 'OP up', 1118.25, 1358,
                'Q1 FY3/2026 revenue +25.5% YoY, OP up, and the stock up ~+21% over the trailing year. Textbook clean grower with the market following.',
                'FY3/2026 Q1は売上前年比+25.5%・営業増益、株価も過去1年で約+21%上昇。市場が追随する教科書的なクリーン・グロワー。'],
            '2025Q4': ['FY3/2026 Q2 (period end Sep 30 2025)', '2025-11', 24.8, 'up', 'OP up', 929, 880.6,
                'Q2 revenue still +25% YoY with OP up, but the stock fell ~-5% over the trailing year as the autumn-2025 SaaS pullback hit even consistent compounders. Fundamentals unchanged, multiple compressed.',
                'Q2も売上前年比+25%・営業増益だが、2025年秋のSaaS調整が安定成長株にも及び株価は過去1年で約-5%下落。ファンダ不変・マルチプル収縮。'],
        },
    },
    '3765': {
        'name': 'GungHo Online Entertainment', 'fy_end': 'Dec',
        'q': {
            '2025Q1': ['FY12/2024 full-year (Q4 standalone, period end Dec 31 2024)', '2025-02', -1.3, 'down', 'OP down', 2443.5, 2920.5,
                'FY12/2024 closed with the Oct-Dec quarter ~-1% YoY (revenue DOWN) as Puzzle & Dragons matures and no new hit has scaled. Yet the stock is up ~+20% over the trailing year on heavy buybacks, a fat cash pile and dividend support. Revenue-down but stock-up.',
                'FY12/2024は主力パズドラの成熟と新規ヒット不在で10〜12月が前年比約-1%(減収)で着地。一方、大規模な自社株買い・潤沢な現金・配当下支えで株価は過去1年で約+20%上昇。減収だが株高。'],
            '2025Q2': ['FY12/2025 Q1 (period end Mar 31 2025)', '2025-05', -7.6, 'up', 'OP up', 2711.5, 2761.5,
                'Q1 FY12/2025 revenue fell ~-8% YoY (continued game-revenue decline) though OP held up on cost discipline. The stock is still marginally up ~+2% over the trailing year, capital-return support outweighing the shrinking top line. Revenue-down, stock-up.',
                'FY12/2025 Q1は売上前年比約-8%(ゲーム収益の減少が継続)もコスト規律で営業増益。株価は資本還元の下支えで過去1年なお小幅高(約+2%)。減収・株高。'],
            '2025Q3': ['FY12/2025 Q2 / H1 (period end Jun 30 2025)', '2025-08', -4.0, 'down', 'OP down', 3081, 2706,
                'H1 standalone-quarter revenue still down ~-4% YoY and OP turned down; the buyback story finally cracked and the stock is down ~-12% over the trailing year. Revenue-down AND stock-down — the market stopped paying for the cash pile.',
                '上期の単四半期売上はなお前年比約-4%・営業減益に転じ、自社株買い相場がついに崩れ株価は過去1年で約-12%下落。減収かつ株安 — 市場は現金の山に対価を払わなくなった。'],
            '2025Q4': ['FY12/2025 Q3 (period end Sep 30 2025)', '2025-11', 0.8, 'down', 'OP down', 3334, 2625,
                'Q3 revenue ticked back to ~+1% YoY (a marginal return to growth) but OP stayed down and the stock fell further, ~-21% over the trailing year. Top line stabilising, but the market remains unconvinced. Revenue-up / stock-down.',
                'Q3は売上が前年比約+1%へ小幅プラス転換(限界的な成長復帰)も営業減益が続き、株価はさらに下落して過去1年で約-21%。トップラインは下げ止まりつつあるが市場は依然懐疑的。増収・株安。'],
        },
    },
}


def main():
    companies = {}
    for tk, info in RAW.items():
        snaps = {}
        for q in QUARTERS:
            (label, filed, rev_yoy, op_dir, op_note, stk_prev, stk_now, ren, rjp) = info['q'][q]
            stk_yoy = round((stk_now / stk_prev - 1) * 100, 1)
            snaps[q] = {
                'report_label': label,
                'filed_approx': filed,
                'snapshot_quarter_end': QEND[q],
                'revenue_yoy_pct': rev_yoy,
                'revenue_dir': 'up' if rev_yoy >= 0 else 'down',
                'op_dir': op_dir,
                'op_note': op_note,
                'stock_close': stk_now,
                'stock_close_prev_year': stk_prev,
                'stock_yoy_pct': stk_yoy,
                'stock_dir': 'up' if stk_yoy > 0 else 'down',
                'category': cat(rev_yoy, stk_yoy),
                'reasoning_en': ren,
                'reasoning_jp': rjp,
                'sources': SOURCES,
            }
        companies[tk] = {
            'ticker': tk, 'name': info['name'], 'sector': 'IT',
            'fy_end': info['fy_end'], 'snapshots': snaps,
        }

    out = {
        '_meta': {
            'generated': '2026-06-13',
            'pilot': True,
            'sector': 'IT',
            'quarters': QUARTERS,
            'definitions': {
                'snapshot': 'Calendar quarter. Each company shows the latest tanshin it had filed as of that calendar quarter-end.',
                'revenue_dir': 'Standalone-quarter revenue YoY from the latest filed report; R+ if >=0 else R-.',
                'stock_dir': 'Trailing-12-month price change at the calendar quarter-end close; S+ if >0 else S-.',
                'categories': ['R+xS+', 'R+xS-', 'R-xS+', 'R-xS-'],
                'point_in_time_rule': 'Reasoning uses only reports filed on/before the snapshot quarter-end. Never the future.',
            },
            'pilot_companies': [f"{tk} {RAW[tk]['name']}" for tk in RAW],
        },
        'companies': companies,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)

    # console summary
    print(f'Wrote {OUT}')
    for q in QUARTERS:
        counts = {}
        for tk in companies:
            c = companies[tk]['snapshots'][q]['category']
            counts[c] = counts.get(c, 0) + 1
        print(f'  {q}: ' + ', '.join(f'{k}={v}' for k, v in sorted(counts.items())))


if __name__ == '__main__':
    main()
