"""Apply single-pass combined-prompt findings to R+xS+ entries.

Methodology change: instead of "Round 1 (narrow earnings prompt) + Round 2 (structural)" =
2 searches per company, this script applies findings from ONE search per company using a
combined prompt that asks both earnings + structural questions together.

This script:
1. STRIPS the old "Round 2追加検証で確認された事項" addendum block (added by prior batched verification)
2. ADDS a new "単一検索検証(2026-06)" addendum with key verified facts from one fresh search per company

Net effect: each R+xS+ company now has one focused per-company verification, matching the
methodological standard applied to R+xS-. Saves ~50% on search cost vs the 2-round approach.
"""
import json
import re
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "company_research_2025.json"
data = json.loads(DATA.read_text(encoding="utf-8"))

# Regex to strip prior Round 2 addendum block (from previous session's batched verification)
STRIP_JP = re.compile(r"\n\n\*\*【Round 2追加検証で確認された事項】\*\*.*?(?=\n\n\*\*【|$)", re.DOTALL)
STRIP_EN = re.compile(r"\n\n\*\*\[Round 2 verification additions\]\*\*.*?(?=\n\n\*\*\[|$)", re.DOTALL)


def apply_update(code: str, jp_addendum: str, en_addendum: str, source_extra: str):
    if code not in data:
        print(f"  WARN: {code} not in data — skipping")
        return
    e = data[code]
    # Strip old Round 2 addenda
    e["jp_summary"] = STRIP_JP.sub("", e["jp_summary"]).rstrip()
    e["en_summary"] = STRIP_EN.sub("", e["en_summary"]).rstrip()
    # Append new single-pass addenda
    e["jp_summary"] += "\n\n**【単一検索検証(2026-06)で確認された事項】** " + jp_addendum
    e["en_summary"] += "\n\n**[Single-pass combined-prompt verification (2026-06)]** " + en_addendum
    e["source_hint"] = e.get("source_hint", "") + " + single-pass combined-prompt verification 2026-06: " + source_extra
    print(f"  updated {code}: {e.get('name','?')[:40]}")


# ───── Mega-caps ─────

apply_update("9984",
    "**売上¥7兆7,987億円(+7.7%)、純利益¥5兆23億円(+333.7%)** で確定。OpenAI評価益¥2兆1,567億円計上が主要因。成長ドライバーは(1) Armロイヤリティー拡大(AIデータセンター需要)、(2) PayPay上場後も連結子会社として手数料・金利収入が拡大、(3) OpenAI保有比率11%(投資予約分含む)で2025年4月にOpenAI株担保の~100億ドル融資を模索と報道。ROE/ROAは目安を上回る水準で改善中。リスクは有利子負債増加とOpenAI評価変動による損益振れ。",
    "**Revenue ¥7.7987 trillion (+7.7%), net profit ¥5.0023 trillion (+333.7%)** confirmed. OpenAI valuation gain ¥2.1567 trillion is the driver. Growth axes: (1) Arm royalty expansion (AI datacenter demand), (2) PayPay listed but stays a consolidated subsidiary, lifting fee+interest income, (3) OpenAI stake 11% (incl subscription); April 2025 reports of exploring ~$10B loan collateralized by OpenAI shares. ROE/ROA above-benchmark and improving. Risks: rising interest-bearing debt; earnings swings from OpenAI valuation volatility.",
    "Yahoo Finance 9984 + kabutan 9984 + Nikkei 9984"
)

apply_update("4307",
    "**売上¥8,147億円(+6.5%)だが豪州・北米子会社のれん減損で営業利益¥582.73億円(-56.8%)に大幅減益**。27年3月期予想は純利益¥1,190億円(+7.8倍)で2期ぶり過去最高益更新見通し。成長ドライバーは金融向け開発・運用需要+クラウド基盤サービス。**中期目標ROE25%**を掲げ、PER 24.58倍/ROE予27.43%で市場期待を反映。継続課金型運用とBPOがリカーリング収益基盤。",
    "**Revenue ¥814.7 billion (+6.5%) but operating profit collapsed to ¥58.27 billion (-56.8%) on Australia/N. America subsidiary goodwill impairment**. FY27 guidance: net profit ¥119 billion (+7.8x) — record-high. Growth drivers: financial-sector development/operations + cloud-infrastructure services. **Mid-term ROE target 25%**, PER 24.58x / forecast ROE 27.43% reflect high market expectations. Recurring revenue and BPO are stable base.",
    "kabutan 4307 + minkabu 4307 + Astris MRI report"
)

apply_update("9433",
    "**売上¥6.072兆円(+4.1%)、営業¥1.099兆円、純利益¥707.1億円(+7.9%)**。ビジネスセグメント+8.7%(¥1.528兆円)/+12.2%(¥263.9億円)が成長エンジン。CAGR 2022-2025: 金融30.4%/ビジネス11.3%。**24期連続増配**、FY26 ¥80/株、FY27予定¥84(25期連続)。配当利回り3.32%(プライム平均2.09%超)。長期株価は2002年¥287.5→2026年5月¥2,529.5の8.8倍上昇。中期計画『Power-to-Connect 2028』で営業利益CAGR 5%・3年間¥1.2兆円AI/低遅延網投資。",
    "**Revenue ¥6.072 trillion (+4.1%), OP ¥1.099 trillion, NP ¥707.1 billion (+7.9%)**. Business segment +8.7% (¥1.528 trillion) / +12.2% (¥263.9 billion) is the engine. CAGR 2022-2025: Finance 30.4%, Business 11.3%. **24 consecutive years of dividend hikes**, FY26 ¥80/share, FY27 plan ¥84 (25th year). Yield 3.32% vs TSE Prime average 2.09%. Long-run stock: ¥287.5 (Mar 2002) → ¥2,529.5 (May 2026) = 8.8x in 24 years. Mid-term plan 'Power-to-Connect 2028': 5% OP CAGR, ¥1.2 trillion 3-year AI / low-latency network capex.",
    "Diamond ZAi 9433 dividend article + KDDI IR + Nikkei 9433"
)

apply_update("9434",
    "**売上¥7兆387億円(+7.6%)、営業¥1兆426億円(+5.4%)、純利益¥5,508億円(+4.7%)で過去最高**。全セグメント増収、特にディストリビューション・ファイナンス事業が高成長。AI投資積極化方針。次期も増収増益予想。**注意点**: 配当は5期連続で¥8.60据え置きで増配ストーリーではない(配当利回り3.96-3.97%、配当性向78.3%)。市場の通信→AI/防衛/グロース株への資金回転リスクが構造的逆風。",
    "**Revenue ¥7.0387 trillion (+7.6%), OP ¥1.0426 trillion (+5.4%), NP ¥550.8 billion (+4.7%) — record high**. All segments grew, especially Distribution and Finance. AI investment focus. Next year growth expected. **Caveat**: Dividend has been FLAT at ¥8.60 for 5 years (NOT a dividend grower); yield 3.96-3.97%, payout 78.3%. Structural headwind: capital rotating out of telecom into AI / defense / growth stocks.",
    "Yahoo Finance 9434 + kabutan 9434 + Nikkei 9434"
)

# ───── Content/gaming ─────

apply_update("9697",
    "**売上¥1,953億円(+15.2%)、営業¥752億円(+14.5%)、純利益¥545億円(+12.7%) — 11期連続増益**。デジタル販売比率約83%、営業利益率38-39%。リピート作比率2015年50%→2023年70%超。海外売上比率約80%、世界230以上の国・地域展開。営業利益は10年で5倍。**モンスターハンターワイルズ発売3日間で800万本**。ジェフリーズが買い評価維持。次の3年で年24%成長見込み(市場は10%予想)、PER30倍前後。注意点: Wilds販売想定下振れで株価が¥4,800台ATH→¥4,000台に下落の動き。",
    "**Revenue ¥195.3 billion (+15.2%), OP ¥75.2 billion (+14.5%), NP ¥54.5 billion (+12.7%) — 11 consecutive years of profit growth**. Digital sales ratio ~83%, OP margin 38-39%. Repeat-title share: 50% (2015) → over 70% (2023). Overseas revenue ~80%, 230+ countries. OP 5x over 10 years. **Monster Hunter Wilds: 8 million units in 3 days**. Jeffries maintains Buy. Market expects 10% growth, company tracking 24% — PER ~30x. Caveat: Wilds sales below expectations triggered drop from ¥4,800 ATH to ¥4,000 range.",
    "kabutan 9697 + Nikkei 9697 + president.jp Capcom strategy article"
)

apply_update("4751",
    "**売上¥8,740億円(+9.1%、28期連続増収)、営業¥717億円(+78.9%)、純利益+大幅増**。ゲーム事業: 売上¥2,167.1億円(+10.6%)、営業¥600.6億円(**+96.5%**) — Shadowverse Worlds Beyond + SDガンダムG Generation Eternal大型ヒット。**ABEMAは10年ぶり黒字化**(売上¥2,315億円+15.7%、営業¥72億円)。広告事業: 売上¥4,612億円(+6.1%、大型顧客離脱で営業-14%)。**ジェフリーズが格上げホールド→バイ、目標¥1,000→¥1,330**。日経225採用銘柄でETFフロー影響大。",
    "**Revenue ¥874 billion (+9.1%, 28 consec years revenue growth), OP ¥71.7 billion (+78.9%), net profit up sharply**. Game segment: revenue ¥216.71 billion (+10.6%), OP ¥60.06 billion (**+96.5%**) — Shadowverse Worlds Beyond + SD Gundam G Generation Eternal big hits. **ABEMA / Media segment first profitability in 10 years** (revenue ¥231.5 billion +15.7%, OP ¥7.2 billion). Ad segment: revenue ¥461.2 billion (+6.1%, OP -14% on large client loss). **Jefferies upgrade Hold → Buy, target ¥1,000 → ¥1,330**. Nikkei 225 constituent — ETF flow impact.",
    "minkabu 4751 + gamebiz 4751 + jp.investing.com 4751"
)

apply_update("4385",
    "**FY6/2026 Q2: 売上¥1,062.55億円(+12.8%)、営業¥197.79億円(+73.3%)**。Q3累計: 売上¥1,672.91億円(+16.1%)、営業¥345.18億円(+69.7%) — 増益加速。日本GMV+11.0%、米国GMV+10.0%、Fintech債権残高¥3,281億円(+45.0%)。営業利益2期連続増益、コスト管理徹底+ROE上昇傾向。通期予想上方修正で機関投資家買い増し。",
    "**FY6/2026 H1: Revenue ¥106.255 billion (+12.8%), OP ¥19.779 billion (+73.3%)**. Q3 YTD: revenue ¥167.291 billion (+16.1%), OP ¥34.518 billion (+69.7%) — profit acceleration. Japan GMV +11.0%, US GMV +10.0%, Fintech credit balance ¥328.1 billion (+45.0%). 2 consecutive years of OP growth + thorough cost control + ROE uptrend. Upward guidance revision triggered institutional buying.",
    "kabutan 4385 + Mercari IR + moneyworld 4385"
)

apply_update("9684",
    "**FY3/2026: 売上-8.3%減収、営業+34.9%、経常+57.5%、純利益+21.3%**(減損処理後の利益急回復)。Q3累計: 売上¥2,154.55億円(-13.3%)、営業¥463.87億円(+39.0%)。デジタルエンタメ収益性改善+ライツ・プロパティ事業好調が利益けん引。**警戒材料**: 27年3月期予想は経常-24.0%減益の¥490億円 — 反動減リスクあり。",
    "**FY3/2026: Revenue -8.3%, OP +34.9%, ordinary +57.5%, net +21.3%** (post-impairment profit recovery). Q3 YTD: revenue ¥215.455 billion (-13.3%), OP ¥46.387 billion (+39.0%). Digital Entertainment profitability + Rights / Property segment strength drove profit. **Caution**: FY27 guidance ordinary profit -24.0% to ¥49 billion — reaction-decline risk.",
    "minkabu 9684 + Yahoo Finance 9684 + kabutan 9684"
)

# ───── Film / IP / VTuber / Activist ─────

apply_update("9602",
    "**売上¥3,606.63億円(+15.2%)、営業¥678.89億円(+5.0%)、経常¥701.40億円(+8.8%)、純利益¥517.69億円(+19.4%)で過去最高**。映画事業: 営業収入¥1,826億円(+30.6%)、営業利益¥373億円(+30.3%)。映画興行入場者¥4,900万人(+27.6%)、配給収入¥1,399億円(歴代最高)。**主要ヒット作**: 劇場版『鬼滅の刃』無限城編第一章 + 国宝(2025年No.1 興収¥56億円)+ 名探偵コナン + チェンソーマン。**戦略的取組**: ワーナー・ブラザース日本配給契約(2026年開始)、¥50億円TOHO-ONE顧客データ基盤、¥130億円自己株取得(750万株)。アナリスト平均目標¥1,864円(強気買い4、買い1、中立4)。IP・アニメ事業利益2032年に対FY25比+200%目標。",
    "**Revenue ¥360.66 billion (+15.2%), OP ¥67.89 billion (+5.0%), ordinary ¥70.14 billion (+8.8%), NP ¥51.77 billion (+19.4%) — record**. Film segment: revenue ¥182.6 billion (+30.6%), OP ¥37.3 billion (+30.3%). Cinema admissions ¥49M (+27.6%), distribution revenue ¥139.9 billion (historic record). **Major hits**: Demon Slayer Infinity Castle Chapter 1 + Kokuhō (2025 No.1, ¥5.6B box office) + Detective Conan + Chainsaw Man. **Strategic moves**: Warner Bros. JPN distribution deal (from 2026), ¥5 billion TOHO-ONE customer data base, ¥13 billion buyback (7.5M shares). Analyst target ¥1,864 (4 strong-buy, 1 buy, 4 neutral). IP/anime profit target +200% by 2032 vs FY25.",
    "gamebiz 9602 + kabutan 9602 + Toho IR + Nikkei 9602"
)

apply_update("9605",
    "**売上¥1,853.33億円(+3.0%)、営業¥360.96億円(+2.7%)**。Q3累計: 売上¥1,363.47億円(+4.6%)、営業¥277.77億円(+9.6%) — 興行関連事業+33.0%増収が牽引。海外版権事業(東映アニメーション)+円安基調が業績押し上げ。**自己資本比率59.4%(+2.3pp)**、財務基盤強固。東映アニメ業績予想上方修正、配当¥41→¥44に増額。中期計画『VISION2030』4戦略エンジン(スタジオ/IP/地域/顧客接点)、2031年売上¥2,000億円目標。注意点: FY27は増収減益予想 — 映画興行の当たり外れリスクは構造的。",
    "**Revenue ¥185.33 billion (+3.0%), OP ¥36.10 billion (+2.7%)**. Q3 YTD: revenue ¥136.35 billion (+4.6%), OP ¥27.78 billion (+9.6%) — Exhibition +33.0% driving growth. Toei Animation overseas IP licensing + yen weakness lifted earnings. **Equity ratio 59.4% (+2.3 pp)**, solid finances. Toei Animation upward revision, dividend ¥41 → ¥44. Mid-term 'VISION 2030' 4 strategic engines (Studio/IP/Region/Customer Touch), FY3/2031 revenue ¥200 billion target. Caveat: FY27 guidance shows revenue growth + profit decline — film-hit volatility is structural.",
    "Yahoo Finance 9605 + Nikkei Toei Animation upward revision + branc.jp Toei Animation mid-term"
)

apply_update("5032",
    "**Q3累計: 売上¥420.2億円(+45.4%)、営業¥169.09億円(+54.2%)**。FY4/2025通期: 売上¥428.77億円(+34.0%)、営業¥162.80億円(+31.7%)で過去最高。Q4単独: 売上¥139.7億円(+60.2%)、営業¥53.1億円(+60.0%)歴代最高四半期。**コマース事業65%が主役**: 売上¥278.42億円(+47.0%)、年間グッズ施策190件(+32.9%)。**ANYCOLOR ID 169万(2023年93万→1.82倍)**、女性ファン71%。**営業利益率38.0%維持**。中期計画FY27目標: 売上¥600億円・営業¥240億円(対FY24比+88%/+94%)。配当¥70→¥75増配。**注意点**: 2025年12月Q2発表で売上は上振れだが利益は棚卸資産評価損で下方修正の『ねじれ』が株価急落のトリガー。国内大手証券目標¥6,100→¥6,600、米系証券『買い』。",
    "**Q3 YTD: revenue ¥42.02 billion (+45.4%), OP ¥16.91 billion (+54.2%)**. FY4/2025 full: revenue ¥42.88 billion (+34.0%), OP ¥16.28 billion (+31.7%) — record. Q4 alone: revenue ¥13.97 billion (+60.2%), OP ¥5.31 billion (+60.0%) — record quarter. **Commerce 65% of revenue is the main driver**: revenue ¥27.84 billion (+47.0%), 190 merchandise campaigns (+32.9%). **ANYCOLOR ID 1.69M (FY23 0.93M = 1.82x)**, female fans 71%. **OP margin 38.0% sustained**. Mid-term FY27: revenue ¥60 billion / OP ¥24 billion (+88% / +94% vs FY24). Dividend ¥70 → ¥75. **Caveat**: Dec 2025 Q2 showed revenue upside but profit DOWN-revised due to inventory write-down — the 'twist' that triggered sharp stock drop. Domestic broker target ¥6,100 → ¥6,600; US broker 'Buy'.",
    "Yahoo Finance 5032 + LIMO 5032 article + Nikkei 5032 + ANYCOLOR IR"
)

apply_update("4676",
    "**売上¥5,518.65億円(+0.2%)、営業損失¥87.66億円、経常損失¥28.07億円**(メディア・コンテンツ事業の広告収入急減)。一方、純利益¥64.99億円で前年から¥266.33億円増(特別利益による)。FY27予想は地上波広告回復+コンテンツ伸長+都市開発・観光+インバウンドで増収増益見通し。**重要な活動家動向**: **SBIHD保有比率を4月20日に6.20%→7.10%に増加**(報道) — Dalton Investments(7.51%)とともに需給材料。**FY27配当¥200/株、配当性向50%目途**で1株当たり配当増加方針。自己資本比率56.8%→37.3%に低下(短期借入¥2,083.72億円増+自己株取得で純資産減)。",
    "**Revenue ¥551.87 billion (+0.2%), operating loss ¥8.77 billion, ordinary loss ¥2.81 billion** (Media / Content segment ad revenue collapse). But net profit ¥6.50 billion (+¥26.6 billion YoY thanks to extraordinary items). FY27 guidance: revenue recovery + content growth + urban development / tourism + inbound = revenue & profit growth. **Key activist move**: **SBIHD raised stake from 6.20% to 7.10% on April 20** (reported) — joins Dalton Investments (7.51%) as fund-flow material. **FY27 dividend ¥200/share, 50% payout-ratio target** — per-share dividend growth policy. Equity ratio dropped from 56.8% to 37.3% (short-term borrowings +¥208.37 billion + buyback shrinking net assets).",
    "Yahoo Finance 4676 + kabuyoho 4676 + Nikkei Fuji Media SBIHD report"
)

# ───── Broadcasters ─────

apply_update("9401",
    "**FY3/2026: 売上¥4,248.5億円、営業¥247.5億円**で過去最高。3年間で株価+221%、直近1年+41%。Q1 FY26: 営業¥81億円(+31.3%)、純利益¥177億円(+23.1%)。配信広告+地上波広告+YARUKIスイッチグループ+StylingLifeブランドが牽引。中期計画営業利益目標¥240億円を1年前倒し達成、FY26予想を売上¥4,400億円・営業¥260億円に上方修正。**3年間の総株主還元¥1,050億円方針**(増配継続)、WACUL(SaaSデジタルマーケ)¥39億円買収でDX強化。アナリスト3名買い・売りなし。市場は『放送局からグロース志向メディア企業』として再評価中。",
    "**FY3/2026: Revenue ¥424.85 billion, OP ¥24.75 billion** — record. Stock up 221% over 3 years, +41% past year. Q1 FY26: OP ¥8.1 billion (+31.3%), NP ¥17.7 billion (+23.1%). Streaming+terrestrial ad + YARUKI Switch Group + StylingLife brands drove growth. Mid-term plan OP target ¥24 billion achieved 1 year early; FY26 raised to ¥440 billion / ¥26 billion. **3-year total shareholder returns ¥105 billion** (continued dividend hikes), WACUL (SaaS digital marketing) acquired for ¥3.9 billion strengthens DX. 3 analyst Buys, no Sells. Market is re-rating TBS as 'growth-oriented media' rather than declining broadcaster.",
    "globeandmail 9401 + Marketscreener TBS + ad-hoc-news 9401"
)

apply_update("9404",
    "**売上¥4,844億円、営業¥693億円**で増収増益達成。スポット収入+デジタル広告+コンテンツ制作・興行収入が好調。**公式中長期戦略『グローバルコンテンツ企業への変革』**を掲げる。事業構成: コンテンツ・メディア+ウェルネス+不動産関連。過去12四半期は業績改善傾向で純利益率・営業利益率・売上・EPS全て上向き、自己資本比率高水準維持+有利子負債縮小で安定性増強。注意点: FY27は先行投資等で減益予想。",
    "**Revenue ¥484.4 billion, OP ¥69.3 billion** — growth in both. Strong spot ads + digital ads + content production/box-office. **Official mid-long-term strategy: 'transformation into a global content company.'** Segments: Content/Media + Wellness + Real Estate. 12 consecutive quarters of improving fundamentals; net/OP margins, revenue, EPS all uptrending; equity ratio high + interest-bearing debt declining. Caveat: FY27 profit decline guided due to upfront investment.",
    "Yahoo Finance 9404 + minkabu 9404 + Nikkei smartchart 9404"
)

apply_update("9409",
    "**Q3累計: 売上¥2,543.92億円(+6.9%)、営業¥231.89億円(+76.8%)**で大幅増収増益。**スポット収入¥801.21億円(+17.8%)**が中核ドライバー、インターネット事業売上¥259.30億円(+18.7%)も好調。通期予想据置(売上¥3,360億円+3.7%、営業¥240億円+21.8%)。**FY3/2026配当¥70(+¥10増配)**で株主還元強化。直近2期連続増収、前期増益率59.71%。ROE上昇傾向で資本効率改善。事業構成: テレビ放送中核+インターネット事業(動画配信)成長牽引。",
    "**Q3 YTD: Revenue ¥254.39 billion (+6.9%), OP ¥23.19 billion (+76.8%)** — sharp growth. **Spot ads ¥80.12 billion (+17.8%)** is the core driver; Internet business revenue ¥25.93 billion (+18.7%) also strong. Full-year guidance held (revenue ¥336 billion +3.7%, OP ¥24 billion +21.8%). **FY3/2026 dividend ¥70 (+¥10)** — stronger shareholder returns. 2 consecutive years of revenue growth, prior-year OP +59.71%. Rising ROE = capital-efficiency improvement. Mix: TV broadcasting core + Internet (streaming) leading growth.",
    "minkabu 9409 + Yahoo Finance 9409 + matsui 9409"
)

apply_update("9413",
    "**売上¥1,649.15億円(+5.8%)、営業¥114.02億円(+46.4%)、純利益¥77億円(+27.61%)**で過去最高更新。**自己資本比率68.9%**。成長エンジン『アニメ・配信』では『NARUTO/BORUTO』海外ゲームロイヤリティ収入好調でセグメント利益1.5倍に。放送事業CM単価引上げも奏功。中期計画でCaaS(コンテンツ・アズ・ア・サービス)戦略+グローバルIPメディア化を推進。FY28予想: 売上¥1,650億円、営業¥115億円。PER予15.7倍、PBR実1.12倍、配当利回り予2.21%。",
    "**Revenue ¥164.92 billion (+5.8%), OP ¥11.40 billion (+46.4%), NP ¥7.7 billion (+27.61%)** — record. **Equity ratio 68.9%**. Growth engine 'Anime/Distribution' — NARUTO/BORUTO overseas game royalty income drove segment profit 1.5x. Broadcasting CPM raises also helped. Mid-term plan: CaaS (Content-as-a-Service) strategy + global IP-media transformation. FY28 guidance: revenue ¥165 billion, OP ¥11.5 billion. PER 15.7x forecast, PBR 1.12x, yield 2.21%.",
    "minkabu 9413 + Nikkei 9413 + TV Tokyo IR mid-term plan"
)

# ───── SaaS / Defense / SI ─────

apply_update("9412",
    "**売上¥1,276億円(+3.1%)、営業¥353億円(+28.3%)、経常¥354億円(+29.8%)**で大幅増益。FY27予想経常¥390億円(+10.1%)で4期連続最高益更新見通し。**宇宙事業が業績ドライバー** — 通信事業から防衛銘柄への変貌、衛星画像が反撃能力の目に。過去12四半期の純利益率・営業利益率持続改善、自己資本比率上昇+有利子負債縮小で安定性強化、売上・EPS伸長。",
    "**Revenue ¥127.6 billion (+3.1%), OP ¥35.3 billion (+28.3%), ordinary ¥35.4 billion (+29.8%)** — sharp growth. FY27 ordinary profit guide ¥39 billion (+10.1%) — 4th consecutive year of record-high earnings expected. **Space business is the driver** — transformation from telecom into defense play; satellite imagery as 'eye for counter-attack capability.' 12 consecutive quarters of margin improvement, equity ratio rising + debt declining, revenue+EPS expanding.",
    "kabutan 9412 + kabuyoho 9412 + Nikkei 9412"
)

apply_update("4686",
    "**売上¥515.15億円(+15.6%)、営業¥224.92億円(+24.7%)、経常¥231.01億円(+27.2%)、純利益¥150.92億円(+22.4%)**。Q3累計: 売上¥385.21億円(+16.8%)、営業¥175.12億円(+24.0%)。**法人事業+37.7%が高成長エンジン**、サブスクリプション売上が全社の71.4%占有。継続課金売上は約74%。営業利益率43.7%(JustSystemsとしてはトップクラス)、キーエンスとの資本業務提携(筆頭株主)が経営改革を加速。**FY26配当¥27→FY27予定¥30**、4期連続増配方針。",
    "**Revenue ¥51.515 billion (+15.6%), OP ¥22.492 billion (+24.7%), ordinary ¥23.101 billion (+27.2%), NP ¥15.092 billion (+22.4%)**. Q3 YTD: revenue ¥38.521 billion (+16.8%), OP ¥17.512 billion (+24.0%). **Corporate business +37.7% is the high-growth engine**, subscription revenue 71.4% of total. ~74% recurring. OP margin 43.7% (top-tier). Keyence capital + business alliance (top equity holder) accelerated reform. **FY26 dividend ¥27 → FY27 plan ¥30**, 4 consecutive years of hikes.",
    "kabutan 4686 + jin-plus.com 4686 + sbbit 4686"
)

apply_update("4194",
    "**FY7/2026 H1: 売上¥466.1億円(+26.2%)、営業¥127.68億円(+24.9%)** — HR Tech好調。BizReachが牽引、HRMOS事業も成長加速。**ROA 18.58%、ROE 26.72%**で高収益体質、自己資本比率高水準。PER予25.6倍、PBR実5.65倍。人材需要の強さがさらなる成長期待を支える。過去12四半期の業績良好で純利益率・営業利益率安定、収益基盤堅め。",
    "**FY7/2026 H1: Revenue ¥46.61 billion (+26.2%), OP ¥12.77 billion (+24.9%)** — HR Tech strong. BizReach leading, HRMOS accelerating. **ROA 18.58%, ROE 26.72%** — high profitability; equity ratio high. PER 25.6x forecast, PBR 5.65x. Labor demand strength supports further growth expectations. 12 consecutive quarters of strong results, OP/net margins stable, profit base solid.",
    "kabuyoho 4194 + moneyworld 4194 + minkabu 4194"
)

apply_update("3626",
    "**売上¥5,964.79億円(+4.3%)、営業¥762.29億円(+10.4%)で過去最高**。営業利益率12.8%(+0.7pp)へ改善。但し純利益¥466.24億円は訴訟損失引当金+減損損失計上で減益。FY27予想: 売上¥6,200億円、営業¥810億円。**¥500億円の自社株買い実施+総還元性向目安45%→50%引上げ**、配当¥80(FY26)→¥90(FY27予定)。**AI中心開発推進**、生成AIをシステム開発全工程に組込む方針。中期計画(2024-2026)+グループビジョン2032で持続的成長を志向。AIによる産業構造変化を成長機会と位置付け。",
    "**Revenue ¥596.479 billion (+4.3%), OP ¥76.229 billion (+10.4%) — record**. OP margin 12.8% (+0.7 pp). NP ¥46.624 billion was down due to litigation loss provision + impairment. FY27 guide: revenue ¥620 billion, OP ¥81 billion. **¥50 billion buyback + total return ratio target 45% → 50%**, dividend ¥80 (FY26) → ¥90 (FY27 plan). **AI-centric development push** — generative AI to be embedded in entire system development process. Mid-term plan (2024-2026) + Group Vision 2032 for sustained growth. AI-driven industry transformation as growth opportunity.",
    "kabutan 3626 + TIS IR finance_meeting260508 + minkabu 3626"
)

# ───── SaaS / Mid-cap SI ─────

apply_update("4733",
    "**売上¥514億円(+9.4%)、営業¥235.8億円(+8.4%)**で増収増益。クラウドサービス収益増加+新規顧客獲得が牽引。**自己資本比率76.7%**の超優良財務基盤。中小企業向け業務パッケージ『奉行』シリーズで高シェア。過去12四半期の純利益率・営業利益率改善、ROEは8-10%を上回る水準。**PER 23.7倍、PBR 2.71倍** — 業績成長を反映した市場評価。",
    "**Revenue ¥51.4 billion (+9.4%), OP ¥23.58 billion (+8.4%)** — growth in both. Cloud-service revenue + new-customer wins drove growth. **Equity ratio 76.7%** — extraordinarily strong finances. SME business-package Bugyo series holds high share. 12 consecutive quarters of margin improvement; ROE above the 8-10% benchmark. **PER 23.7x, PBR 2.71x** — market valuation reflects growth.",
    "Yahoo Finance 4733 + minkabu 4733 + kabutan 4733"
)

apply_update("4812",
    "**FY12/2025: 経常利益¥236億円(+12.0%)、売上10期連続+営業利益・純利益8期連続最高益**。FY26予想: 経常¥261億円(+10.5%)で2期連続最高益。**Q1 FY26: 売上¥438.2億円(+8.9%)、営業¥65.88億円(+14.0%)**で増収増益。金融+ビジネス+コミュニケーションIT各セグメント好調、ビジネスソリューションが顕著。受託システム開発・ソフトウェア製品・アウトソーシング・情報機器が2桁成長。**時価総額¥5,267億円**、PER予32.5倍、ROE 17.36%、自己資本比率61.9%。**13期連続増配**(FY25 ¥116→¥120、FY26 ¥45+株式分割勘案で実質12.5%増配)、FY27に配当性向50%目標。AI駆動開発+新規事業領域開拓+2030年に向けた研究開発投資強化。",
    "**FY12/2025: Ordinary ¥23.6 billion (+12.0%), 10 consecutive years of revenue + 8 years of OP/NP record highs**. FY26 guide: ordinary ¥26.1 billion (+10.5%) — 2nd consecutive record year. **Q1 FY26: Revenue ¥43.82 billion (+8.9%), OP ¥6.588 billion (+14.0%)** — growth. Finance + Business + Comm-IT segments all strong; Business Solution standout. Contracted dev + software products + outsourcing + IT equipment double-digit growth. **Market cap ¥526.7 billion**, PER 32.5x forecast, ROE 17.36%, equity ratio 61.9%. **13 consecutive years of dividend hikes** (FY25 ¥116→¥120, FY26 ¥45 + share split = ~12.5% effective), FY27 50% payout target. AI-driven development + new business areas + R&D investment for 2030.",
    "logmi finance 4812 + SalesNow 4812 + Nikkei TDnet 4812 Q1 + Dentsu Soken IR"
)

apply_update("7595",
    "**売上¥695億円、営業¥102億円、営業利益率14.7%、純利益¥74.47億円(+14.2%)**(2025年3月期)。**FY3/2026予想: 純利益¥75.3億円(+1.1%)**。当期売上¥69,541百万円(+16.9%) — 自動車・半導体関連業界のIT投資意欲が牽引。営業¥10,199百万円(+11.2%)、稼働率改善+内製化のコスト管理が利益率改善に寄与。3社のM&Aでワンストップソリューション体制を強化、電磁界解析+デジタルツイン+VR/ゲーミングへ事業拡大。中期計画では設計DX+製造DX+AI活用+人的資本投資を志向。CASE対応・技術革新が継続的需要を生む構造。",
    "**Revenue ¥69.5 billion, OP ¥10.2 billion, OP margin 14.7%, NP ¥7.447 billion (+14.2%)** (FY3/2025). **FY3/2026 guide: NP ¥7.53 billion (+1.1%)**. Current revenue ¥69.541 billion (+16.9%) — auto / semiconductor industry IT investment driving. OP ¥10.199 billion (+11.2%); utilization improvement + in-housing helped margin. 3 M&As built one-stop solution capability — expansion into electromagnetic analysis + digital twin + VR/gaming. Mid-term plan: design DX + manufacturing DX + AI use + human capital investment. CASE adoption + tech innovation generate continued demand.",
    "Nikkei 7595 + ARGO IR + minkabu 7595"
)

apply_update("3923",
    "**FY3/2026: 経常¥174億円(+70.7%)、売上¥442.97億円(+24.6%)、営業¥125億円(+65.7%)**で大幅増収増益。FY3/2027予想は経常¥205億円(+17.5%)で4期連続最高益。**Q4経常¥49億円(+84.4%)、売上営業利益率19.8%→30.3%へ急上昇**。クラウド事業+IT人材事業両セグメント成長。楽楽精算は累計導入社数19,418社(シェア1位)。**クラウド事業売上の93.5%が月額料金(ストック型)、利益率19.6%**。広告宣伝費最適化で利益率大幅改善。JPX日経インデックス400採用銘柄でETF需要あり。無借金経営+豊富な営業CF。",
    "**FY3/2026: Ordinary ¥17.4 billion (+70.7%), revenue ¥44.297 billion (+24.6%), OP ¥12.5 billion (+65.7%)** — sharp growth. FY3/2027 ordinary guidance ¥20.5 billion (+17.5%) — 4th consecutive year of record-high earnings. **Q4 ordinary ¥4.9 billion (+84.4%), OP margin 19.8% → 30.3% surge**. Cloud + IT-talent segments both growing. Rakuraku Seisan: 19,418 cumulative adoptions (#1 share). **Cloud revenue 93.5% monthly (stock-type), OP margin 19.6%**. Ad-spending optimization sharply improved margins. JPX-Nikkei 400 constituent — ETF demand. Near-zero debt + abundant operating cash flow.",
    "kabutan 3923 + Rakus IR + bitget wiki 3923"
)

# ───── Fan economy / Adtech / SaaS / SI ─────

apply_update("3661",
    "**売上¥317.15億円(+23.0%)、営業¥50.03億円(+23.1%)**で増収増益。Q1: 売上¥74.13億円(+27.0%)、営業¥13.87億円(+59.3%)で大幅増益スタート。**直近2年平均増収率30.67%、増益率33.07%**で持続的高成長。有料会員数増加+電子チケット発券枚数増加+周辺サービス(オンラインくじ等)+公式二次流通(チケットトレード)+スポーツ向けデジタルカード(プロ野球/バスケ/バレー)など多角的成長エンジン。FY27は有料会員拡大+生成AI実装による開発効率化+オフショア体制活用で利益成長目指す。",
    "**Revenue ¥31.715 billion (+23.0%), OP ¥5.003 billion (+23.1%)** — growth in both. Q1: revenue ¥7.413 billion (+27.0%), OP ¥1.387 billion (+59.3%) — strong start. **2-year average revenue growth 30.67%, OP growth 33.07%** — sustained high growth. Paid-member growth + e-ticket volume + adjacent services (online lottery) + official secondary distribution (ticket trade) + sports digital cards (baseball/basketball/volleyball) — diversified growth engines. FY27: paid-member expansion + generative-AI dev efficiency + offshore utilization.",
    "diamond ZAi 3661 + kabutan 3661 + Buffett-Code 3661"
)

apply_update("3741",
    "**FY12/2025: 売上¥303.09億円(+7.2%)、営業¥42.39億円(+35.4%)**で大幅増益。FY26 Q1: 純利益¥26.5億円(+74.1%)で大幅増益継続。中間期: 売上¥152.07億円(+8.7%)、Non-GAAP営業¥20.65億円(+16.8%)。3セグメント(マーケティング・コミュニケーション+ダイレクトビジネス+データ・ソリューション)で企業DXを総合支援。**長期投資家の評価**: 独自成長できる会社、長期成長目線で努力継続、独自性が強い — 機関投資家から長期保有銘柄として評価。現在の証券コードは**4293**(東証スタンダード)。",
    "**FY12/2025: Revenue ¥30.309 billion (+7.2%), OP ¥4.239 billion (+35.4%)** — sharp profit growth. FY26 Q1: NP ¥2.65 billion (+74.1%) — continued strong growth. Interim: revenue ¥15.207 billion (+8.7%), Non-GAAP OP ¥2.065 billion (+16.8%). 3 segments (Marketing Comm + Direct Business + Data Solution) provide full-stack DX support. **Long-term investor view**: 'Independently growing company; sustained long-term growth focus; distinct competitive position' — recognized as long-hold name by institutions. Current ticker is **4293** (TSE Standard).",
    "kabutan 4293 + Septeni IR note + minkabu 4293"
)

apply_update("4431",
    "**FY4/2026 中間期: 売上¥62.64億円、営業¥13.21億円**で堅調、**ARR¥99.4億円達成**(中期計画前倒し)。FY4/2025 通期: 売上¥110.66億円、営業¥23.75億円、経常¥23.58億円。FY4/2026予想: 売上¥138.59億円(+25.2%)、営業¥28.04億円(+18.1%)。**+48.6% YoY成長率、ARR ¥81.9億円**。POSを核としたクロスセル+機器サブスクで通期予想上方修正。**チャーンレート0.5%、ARR売上比率約90%**で堅牢なビジネス基盤。**自己資本比率69.2%**、純資産¥89.14億円。バーティカルSaaS市場2025年¥1,335億ドル→2029年¥1,940億ドル成長見込み(国内小売・飲食特化型として恩恵)。PER予22.4倍。経済産業省がスマートレジ普及を支援(政策追い風)。",
    "**FY4/2026 H1: Revenue ¥6.264 billion, OP ¥1.321 billion** — solid, **ARR ¥9.94 billion achieved** (mid-term plan ahead of schedule). FY4/2025 full: revenue ¥11.066 billion, OP ¥2.375 billion, ordinary ¥2.358 billion. FY4/2026 guide: revenue ¥13.859 billion (+25.2%), OP ¥2.804 billion (+18.1%). **+48.6% YoY growth rate, ARR ¥8.19 billion**. POS-core cross-sell + equipment subscription drove upward revision. **Churn 0.5%, ARR share ~90% of revenue** — robust business base. **Equity ratio 69.2%**, net assets ¥8.914 billion. Vertical SaaS market: $135B in 2025 → $194B by 2029 (Japan retail/restaurant niche benefits). PER 22.4x forecast. METI promoting smart-register adoption — policy tailwind.",
    "Smaregi IR + minkabu 4431 + Nikkei 4431"
)

apply_update("4481",
    "**FY12/2025 Q3累計: 売上¥164.73億円(+11.8%)、営業¥44.16億円(+16.6%)**で増収増益。DX需要+SAP移行需要+人材育成・営業強化で利益率改善。日本+中国のSE融合+ERP(SAP)・ICTソリューション提供が事業特性。**ROA 22.73%、ROE 30.50%、自己資本比率74.6%**という高収益・優良財務。過去12四半期の業績改善傾向で純利益率・営業利益率上向き。",
    "**FY12/2025 Q3 YTD: Revenue ¥16.473 billion (+11.8%), OP ¥4.416 billion (+16.6%)** — growth. DX demand + SAP migration + talent training + sales strengthening improved margins. Business mix: Japan + China engineer fusion + ERP (SAP) / ICT solutions. **ROA 22.73%, ROE 30.50%, equity ratio 74.6%** — highly profitable + strong finances. 12 consecutive quarters of improving fundamentals; net/OP margins rising.",
    "kabutan 4481 + kabuyoho 4481 + minkabu 4481"
)

# ───── Think tank / Cosmetics / Speculative / Travel ─────

apply_update("3636",
    "**FY9/2026 中間: 売上¥725.71億円(+10.9%)、経常¥100.94億円(+32.1%)** — 大幅増収増益。通期予想上方修正後: 売上¥1,250億円(+2.9%)、経常¥95億円(-2.4%)で保守的。シンクタンク・コンサル事業好調。重点分野: 電力・エネルギー+医療・介護+ビジネスアナリティクス・AI、ITサービスは金融・決済+公共・電力+人材・文教。**中計2026**: 2030年売上¥2,000億円目標、ホップ/ステップ/ジャンプ3段階。DX事業成長+基幹事業質的改革+次世代事業育成で事業ポートフォリオ転換加速。新規顧客獲得(地銀・一般企業・ノンバンク)+収益性改善+M&A/提携でリカーリング拡大。注意点: ITサービスの不採算案件対応が課題。",
    "**FY9/2026 H1: Revenue ¥72.571 billion (+10.9%), ordinary ¥10.094 billion (+32.1%)** — sharp growth. Conservative full-year guidance: revenue ¥125 billion (+2.9%), ordinary ¥9.5 billion (-2.4%). Think-tank / consulting business strong. Focus areas: power/energy + medical/care + business analytics/AI; IT services in finance/payment + public/power + HR/education. **Mid-term plan 2026**: FY3/2030 revenue ¥200 billion target via 3-stage (Hop/Step/Jump). DX growth + core-business quality reform + next-gen business cultivation = portfolio transformation acceleration. New-customer expansion (regional banks, corporates, non-banks) + profitability improvement + M&A/alliances for recurring growth. Caveat: unprofitable IT-service projects need addressing.",
    "MRI IR + Astris MRI report + ir.mri.co.jp"
)

apply_update("3660",
    "**FY6/2026 中間: 売上¥400.89億円(+21.2%)、営業¥18.39億円(+23.0%)**。Q3: 売上¥596.94億円(+19.7%)、営業¥28.84億円(+23.0%)で大幅増収増益。EC成長顕著(プラットフォーム連携+販売イベント)。店舗新店効果+既存店成長+客数・リピート増。限界利益率の高い事業モデルで増収が採算に反映されやすい構造。過去12四半期の業績改善傾向、純利益率・営業利益率持ち直し、自己資本比率上昇、EPS底上げ。ROE・ROA目安超水準。注意: グローバル(香港旗艦店)は開店費用先行で損失拡大だが、店舗オープン後は短期で売上貢献中。",
    "**FY6/2026 H1: Revenue ¥40.089 billion (+21.2%), OP ¥1.839 billion (+23.0%)**. Q3: revenue ¥59.694 billion (+19.7%), OP ¥2.884 billion (+23.0%) — sharp growth. EC growth standout (platform partnerships + sales events). New stores + existing-store growth + traffic/repeat increases. High-marginal-revenue model means top-line growth flows to profitability. 12 consecutive quarters of improvement; net/OP margins recovering, equity ratio rising, EPS lifting. ROE/ROA above benchmarks. Note: Global (Hong Kong flagship) loss-widening on launch costs but post-opening already contributing.",
    "kabutan 3660 + minkabu 3660 + Yahoo Finance 3660"
)

apply_update("3803",
    "**FY3/2026: 売上¥7.31億円(+13.2%)、営業損失¥1.75億円、経常損失¥1.95億円、純損失¥2.59億円で損失拡大**。前提とは異なり業績は赤字状態 — 売上微増だが利益面は悪化。**株価上昇は業績連動ではなく材料(イベント)主導**: (1) サイブリッジ合同会社との資本業務提携によるM&A期待、(2) 増資で財務基盤強化、(3) 投資ファンドの大量保有報告などの個別イベントが株価を動かす構造。業績ベースでは割安と評価できない、典型的なイベントドリブン銘柄。",
    "**FY3/2026: Revenue ¥0.731 billion (+13.2%), operating loss ¥175 million, ordinary loss ¥195 million, net loss ¥259 million — losses widening**. Contrary to the premise, the business is in deficit — slight revenue growth but profitability worsening. **Stock rise is NOT earnings-linked but material (event)-driven**: (1) Cybridge LLC capital + business alliance M&A expectations, (2) capital injection strengthening balance sheet, (3) investment-fund large-shareholder reports. Cannot be called undervalued on fundamentals — a classic event-driven name.",
    "Yahoo Finance 3803 + minkabu 3803 + Image Information IR"
)

apply_update("9416",
    "**売上¥390.12億円(+9.8%)、営業¥64.65億円(+20.5%)で過去最高**。Q2累計経常¥29.1億円(+5.6%)。グローバルWiFi事業(訪日外国人向けNINJA WiFi、SIMカード自販機)が好調、無制限プラン需要で顧客単価高水準。**訪日外国人3,600万人超(過去最高)**が追い風。情報通信サービス事業(OA機器・移動体通信・エコソリューション)も好調。**売上総利益率48.4%→56.0%へ大幅改善、売上総利益+44.4%(¥178億円)**。PER予14.1倍、ROE実21.19%、ROA実14.48%、自己資本比率69.1%。海外向けWiFiレンタル分野で国内3社中売上シェア4割強の最大手。大阪万博会場2か所でサービスブース展開。",
    "**Revenue ¥39.012 billion (+9.8%), OP ¥6.465 billion (+20.5%) — record high**. H1 ordinary ¥2.91 billion (+5.6%). Global WiFi (NINJA WiFi for foreign visitors, SIM-card vending machines) strong; unlimited plan demand keeps ARPU high. **Foreign visitors over 36M (record)** is tailwind. ICT business (OA equipment, mobile, eco solutions) also strong. **Gross margin 48.4% → 56.0% — major improvement; gross profit +44.4% (¥17.8 billion)**. PER 14.1x forecast, ROE 21.19%, ROA 14.48%, equity ratio 69.1%. Overseas WiFi rental: top market share with over 40% among the 3 main domestic players. Two booths at Osaka Expo.",
    "minkabu 9416 + Vision IR + bridge-salon 9416 report"
)

# ───── SI majors ─────

apply_update("4722",
    "**FY12/2025: 売上¥759.93億円(+8.8%)、営業¥161.76億円(+10.3%)**で増収増益。FY26 Q1経常¥35億円(+7.9%)で増益継続。ITコンサルティング&サービス事業好調+リヴァンプとのシナジー効果、次世代バンキングシステム導入拡大で知財活用案件が業績牽引。**10年累積で売上2.2倍、純利益4.4倍**の長期成長実績。AI技術活用+グループシナジー強化で更なる成長戦略。Q3は市場予想上振れ。注意: 自己資本比率低下と負債増加が重し、利益率は若干弱含み。",
    "**FY12/2025: Revenue ¥75.993 billion (+8.8%), OP ¥16.176 billion (+10.3%)** — growth in both. FY26 Q1 ordinary ¥3.5 billion (+7.9%) — continued growth. IT Consulting & Services strong + Revamp synergy + next-gen banking system expansion + IP-utilization projects driving. **10-year track record: revenue 2.2x, NP 4.4x**. AI tech utilization + group synergy strengthening = further growth strategy. Q3 beat market expectations. Caveat: equity ratio declining + debt rising weighing; margin slightly softer.",
    "minkabu 4722 + Future Corp IR + kabuyoho 4722"
)

apply_update("4783",
    "**FY3/2025: 売上¥301.06億円(+18.1%)、営業¥28.09億円(+32.8%)、経常¥28.52億円(+33.3%)、純利益¥19.05億円(+37.3%)**で大幅増収増益。3セグメント全て成長: システム開発¥126.99億円(+21.9%、保険・ガス・製造業案件)、サポート&サービス¥94.09億円(+21.6%、AWS/Azureクラウド+IT資産管理)、パーキングシステム¥79.75億円(+9.3%、自治体駐輪場+大規模再開発)。**ストック売上比率8割超**、ジャパンコンピューターサービス子会社が連結貢献。**時価総額¥212億円、PER 11.93倍、PBR 2.43倍、ROE 20.39%、ROA 10.38%**。**配当上方修正¥66.00円(+¥16増配)、予想配当性向30.0%、配当方針30%→50%へ引上げ**。",
    "**FY3/2025: Revenue ¥30.106 billion (+18.1%), OP ¥2.809 billion (+32.8%), ordinary ¥2.852 billion (+33.3%), NP ¥1.905 billion (+37.3%)** — sharp growth. All 3 segments grew: System Development ¥12.699 billion (+21.9%, insurance/gas/manufacturing), Support & Service ¥9.409 billion (+21.6%, AWS/Azure cloud + IT-asset management), Parking System ¥7.975 billion (+9.3%, municipal bicycle parking + redevelopment). **Stock-revenue ratio over 80%**, Japan Computer Service subsidiary contributing to consolidation. **Market cap ¥21.2 billion, PER 11.93x, PBR 2.43x, ROE 20.39%, ROA 10.38%**. **Dividend upward-revised to ¥66.00 (+¥16), forecast payout 30.0%, policy raised from 30% to 50%**.",
    "kabutan 4783 + bridge-salon 4783 + NCD IR note"
)

apply_update("9682",
    "**FY3/2026 Q3累計: 売上¥983.35億円(+8.1%)、営業¥123.25億円(+19.2%)**で大幅増収増益。**プラットフォーム&サービスセグメント+19.2%が成長エンジン**。情報サービス業大手で金融・通信向け強み、IT+組込技術も展開。顧客と直取引7割+幅広い業種対応で成長持続。過去12四半期の業績改善傾向、純利益率・EPS・売上全て上向き、自己資本比率高水準で安定。**経常+2.5-3.5%増益、PBR 3.30倍、ROE 17.68%**。",
    "**FY3/2026 Q3 YTD: Revenue ¥98.335 billion (+8.1%), OP ¥12.325 billion (+19.2%)** — strong growth. **Platform & Services segment +19.2% is the growth engine**. Major info-services player with finance/telecom strengths; IT + embedded tech too. Direct customer transactions 70% + broad industry coverage sustain growth. 12 consecutive quarters of improvement; net margin/EPS/revenue all uptrending; equity ratio high and stable. **Ordinary profit guidance +2.5-3.5%, PBR 3.30x, ROE 17.68%**.",
    "kabutan 9682 + Yahoo Finance 9682 + DTS IR"
)

apply_update("9692",
    "**FY1/2026: 売上¥658.82億円(+17.2%)、営業¥73.38億円(+9.6%)**で増収増益。DX関連投資需要+セキュリティ対策需要が牽引、特にインテグレーションセグメント貢献。独立系SI、**トヨタグループ等優良顧客の情報活用ツール実績**+組み込みソフト開発強み。収益性は前年同期比持ち直し、売上拡大基調。ROE・ROA目安超水準で収益性安定。",
    "**FY1/2026: Revenue ¥65.882 billion (+17.2%), OP ¥7.338 billion (+9.6%)** — growth in both. DX investment demand + security demand driving; Integration segment especially. Independent SI with **strong track record in information utilization tools for prime customers like Toyota Group** + embedded software strength. Profitability recovering YoY; revenue uptrending. ROE/ROA above benchmark — stable profitability.",
    "minkabu 9692 + Yahoo Finance 9692 + CEC IR"
)

# ───── Accounting / Mobility / Integration / Speculative ─────

apply_update("9746",
    "**FY9/2026 H1累計: 純利益¥79億円(+26%)、売上¥468億円(+19%)、営業¥111億円(+28%)**で大幅増益。経常¥114億円(+29.0%)で通期計画¥171億円に対する進捗66.9%(5年平均59.3%を上回る)。**地方自治体ガバメントクラウド上の標準準拠システム移行特需が牽引**。地方公共団体事業の一時的特需により大幅増収増益、当期がピークで来期以降は減収予想。**TKCグループソリューションは全国税理士事務所の33%超が利用**、税理士・公認会計士連携で会計システム開発、金融機関・地方自治体・企業で利用。**注意**: 164団体全てで標準準拠システム移行完了したため、FY27予想は純利益¥121億円(+1%)、売上¥855億円(+2%)と成長率低下見込み。",
    "**FY9/2026 H1: NP ¥7.9 billion (+26%), revenue ¥46.8 billion (+19%), OP ¥11.1 billion (+28%)** — sharp profit growth. Ordinary ¥11.4 billion (+29.0%) vs full-year plan ¥17.1 billion = 66.9% progress (vs 5-year average 59.3%). **Local-government Government Cloud standards-compliant system migration special demand is the driver**. Local Government segment one-time special demand drove sharp growth; this year peaks, next year guides for revenue decline. **TKC Group solutions used by over 33% of tax-accountant offices nationwide**; tax accountant / CPA partnership develops accounting systems; used by financial institutions, local governments, corporates. **Caveat**: All 164 entities have completed standards-migration, so FY27 guidance is NP ¥12.1 billion (+1%), revenue ¥85.5 billion (+2%) — growth rate decline.",
    "kabutan 9746 + Nikkei 9746 + TKC IR"
)

apply_update("2317",
    "**売上¥944億円(+12.9%)、営業¥153.67億円(+27.3%)**で大幅増収増益。**次世代モビリティ事業+デジタルインテグレーション事業の成長+ビジネスソリューション事業特需**が貢献。DX投資+AI活用拡大が追い風。**『AIデータセンター推進室』新設**で市場調査+技術要件検証実施 — 事業化なら新領域選択肢。株価¥385.0円、PER予15.6倍、ROE実24.04%。過去12四半期業績改善、売上・利益率・自己資本比率・EPS全て上向き。",
    "**Revenue ¥94.4 billion (+12.9%), OP ¥15.367 billion (+27.3%)** — sharp growth. **Next-gen Mobility + Digital Integration growth + Business Solution special demand** contributed. DX investment + AI utilization expansion is tailwind. **'AI Datacenter Promotion Office' newly established** for market research + tech-requirements verification — if commercialized, becomes a new area. Stock ¥385.0, PER 15.6x forecast, ROE 24.04%. 12 consecutive quarters of improvement; revenue, margins, equity ratio, EPS all uptrending.",
    "minkabu 2317 + kabutan 2317 + Systena IR"
)

apply_update("3853",
    "**売上¥33.89億円(+6.9%)、営業¥10.25億円(+31.2%)、当期利益¥7億円(+35.7%)**。ストック売上比率77%、営業利益率30.2%、全製品AI対応『Asset-hook』戦略始動。ASTERIA Warpはクラウド移行・レガシー刷新需要で堅調、サブスク売上+サポートの継続収益比率上昇。**重要触媒**: **スペースXがIPO予定**(時価総額$2兆=¥270兆円規模) — Asteria Vision Fund I経由のスペースX出資が出資当時から数十倍〜100倍以上のマルチプル化、保有資産価値が数十億円〜100億円規模に膨張見込み。**3か月株価+83.1%(¥1,216→¥2,226)**、決算発表後急騰。**JPYC連携**: 日本円ステーブルコインJPYC(2025年10月発行)との連携で新規ステーブルコイン市場参入。ノーコードデータ連携シェア国内1位、累計1万社以上の導入実績。出来高+237%増で市場関心高い。",
    "**Revenue ¥3.389 billion (+6.9%), OP ¥1.025 billion (+31.2%), NP ¥0.7 billion (+35.7%)**. Stock-revenue ratio 77%, OP margin 30.2%, all-product AI 'Asset-hook' strategy launched. ASTERIA Warp solid on cloud migration / legacy modernization, subscription + support revenue share rising. **Key catalyst**: **SpaceX planning IPO** (valuation ~$2 trillion = ¥270 trillion) — Asteria's SpaceX investment via Asteria Vision Fund I would mark up valuation 10-100x+; holding could swell from billions to tens of billions of yen. **3-month stock +83.1% (¥1,216 → ¥2,226)**, post-earnings surge. **JPYC linkage**: integration with JPYC yen-stablecoin (Oct 2025 issue) entering new stablecoin market. #1 share in Japan no-code data integration, 10,000+ cumulative adoptions. Trading volume +237% — high market interest.",
    "note tekkan 3853 article + note Yanagi 3853 SpaceX analysis + kabushiki 3853 + Nikkei Asteria SpaceX article"
)

apply_update("3908",
    "**Q3累計: 売上¥12.95億円(-10.1%)、営業¥7,200万円(+44.9%)** — 売上は減少だが利益大幅増。現有サービスの減収を独自サービスの成長でカバー+コスト削減効果で増益。**AIコールセンターシステム『VLOOM』売上¥5,700万円(+148%)** — AI音声認識需要+在宅環境+海外拠点での利用拡大で受注拡大。コスト改善施策で営業¥7,000万円(前期赤字から黒字転換)。ホスティング等固定費削減+業務見直し+自動化推進。**株価¥384.0円(+8.17%)、PER予111.7倍**(成長期待で高水準)。ROA実8.26%、ROE実12.33%、自己資本比率72.7%。市場は『苦境からの脱却期→次のステージへの成長企業』として再評価中。",
    "**Q3 YTD: Revenue ¥1.295 billion (-10.1%), OP ¥72 million (+44.9%)** — revenue down but profit up sharply. Decline in legacy services offset by proprietary-service growth + cost cuts. **AI call-center system 'VLOOM' revenue ¥57 million (+148%)** — AI voice-recognition demand + remote-work + overseas-base usage expansion driving order growth. Cost-improvement measures drove OP ¥70 million (turnaround from prior loss). Hosting fixed-cost cuts + business-review + automation. **Stock ¥384.0 (+8.17%), PER 111.7x forecast** (high reflecting growth expectations). ROA 8.26%, ROE 12.33%, equity ratio 72.7%. Market is re-rating from 'struggling phase' to 'growing into next stage.'",
    "logmi 3908 + Yahoo Finance 3908 + Collabos IR"
)

# ───── Final ─────

apply_update("3989",
    "**FY9/2026 Q1: 売上¥22.76億円(+17.2%)、営業¥5.33億円(+9.5%)**で増収増益。H1累計純利益¥6.6億円(+13.0%)で継続成長。**自社施工事業の売上が大きく伸長**、加盟店約6,400社と提携してプラットフォーム+自社施工の両エンジン稼働。プラットフォーム事業の加盟店手数料が成長ドライバー。**時価総額¥278億円、PER 17.4倍、ROE 27.4%、自己資本比率69.3%**で高収益・成長企業。**アセット・バリュー・インベスターズ・リミテッドが大量保有報告**を提出 — 機関投資家の関心高まり。豊富なネットキャッシュ+業績成長期待が株価と連動。",
    "**FY9/2026 Q1: Revenue ¥2.276 billion (+17.2%), OP ¥0.533 billion (+9.5%)** — growth in both. H1 NP ¥0.66 billion (+13.0%) — continued growth. **In-house construction segment revenue grew significantly**, ~6,400 affiliated stores partnered, Platform + In-house both engines firing. Platform business affiliate fees are the growth driver. **Market cap ¥27.8 billion, PER 17.4x, ROE 27.4%, equity ratio 69.3%** — high profitability + growth profile. **Asset Value Investors Limited filed large-shareholder report** — institutional investor interest rising. Abundant net cash + sustained growth expectations tracking with stock.",
    "kabutan 3989 + kabuyoho 3989 + Sharing Technology IR"
)

apply_update("8056",
    "**売上¥4,336.86億円(+7.3%)、営業¥426.04億円(+9.1%)、純利益¥312.09億円(+15.7%)**で増収増益。FY27予想は純利益¥322億円(+3.2%)で**4期連続最高益**更新見通し。**カタリナマーケティングジャパン買収+継続的IT投資需要**が業績牽引。**AI・クラウド領域強化**: Data&AI Innovation Labで業界知見コンサル+業界別業務シナリオテンプレートでAI業務組込みを支援。**配当上方修正¥120→¥130、FY27予定¥140(+¥10)**で株主還元強化。過去12四半期業績改善、純利益率・営業利益率・売上・EPS伸長、自己資本比率水準維持。",
    "**Revenue ¥433.686 billion (+7.3%), OP ¥42.604 billion (+9.1%), NP ¥31.209 billion (+15.7%)** — growth in both. FY27 NP guide ¥32.2 billion (+3.2%) — **4 consecutive years of record-high earnings** expected. **Catalina Marketing Japan acquisition + sustained IT-investment demand** drove earnings. **AI / cloud area strengthening**: Data & AI Innovation Lab uses industry-knowledge consultants + industry-specific business-scenario templates to embed AI into operations. **Dividend upward-revised ¥120 → ¥130, FY27 plan ¥140 (+¥10)** — stronger shareholder returns. 12 consecutive quarters of improvement; net/OP margin, revenue, EPS all uptrending; equity ratio sustained.",
    "kabutan 8056 + Yahoo Finance 8056 + BIPROGY IR + Nikkei BIPROGY"
)

DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nOK — applied single-pass combined-prompt addenda; total entries: {len(data)}")
