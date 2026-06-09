# -*- coding: utf-8 -*-
"""Apply IT corrections batch 1 (IT01-IT04, 32 entries)."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

IT_PATH = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data\company_research_2025.json")
C = {}

# IT01 SaaS A
C["3653"] = {"jp": """【会社概要】モルフォは画像処理AIのソフトウェア技術を開発・ライセンス提供する独立系企業 — スマートフォンのカメラ補正アルゴリズム、自動車向けのAD/ADAS(先進運転支援システム)・DMS(ドライバーモニタリング)・テレマティクス、産業用機器向けの画像認識など、見えないところで多くのデバイスに組み込まれる技術を作っている。東証グロース上場。

【業績の動き】2026年10月期 第1四半期は厳しい結果 — 売上は前年同期比-32.2%減の4.74億円、営業損失は3.91億円(前期は赤字幅拡大)。営業利益率は-19.7%から-82.5%へ大幅悪化。それでも会社の通期予想は据え置きで、売上35億円(+4.1%)、営業利益1億円(+118.1%)、純利益7,000万円 — 下半期での急回復に賭けた強気予想。配当は無配を継続(2026年10月期予想0円)。

【なぜ業績がこう動いたのか】第一に主力のスマートデバイス領域での苦戦が直接の原因 — 中国スマホメーカー向けの新規開拓を継続しているものの、Q1時点では数字に表れていない。第二にスマートフォン市場の成熟化(全体の出荷台数が頭打ち)で、画像処理エンジンの売上ベースが構造的に縮小している。第三に自動車向けの『Morpho Automotive Suite』(2025年提供開始)など新規領域への先行投資は継続しているが、収益貢献は将来時点で、足元の費用が先行する構造。

【なぜ株価がこう動いたのか】第一に2026年3月30日に10年来安値609円を記録するなど、株価は弱含み — 市場は通期『増収増益見通し』を信じておらず、Q1の-32%減収を下半期で取り戻すシナリオに現実味がないと判断。第二に5月28日終値681円まで反発したものの、600~700円台でのレンジ推移にとどまり、出来高は薄い『様子見モード』。第三に無配・赤字継続・グロース市場小型株という3点セットで機関投資家のスクリーニングから外れやすく、買い手不在の状態。

【UNVERIFIED】2027年10月期ガイダンス、直近の中期経営計画の数値目標、自動車向け案件の具体的な大口受注金額は公開情報からは確認できなかった。""",
"en": """[Company Overview] Morpho is an independent developer and licensor of image-processing AI software — its technology is embedded in smartphone camera correction algorithms, automotive AD/ADAS (advanced driver assistance), DMS (driver monitoring), telematics, and industrial machine-vision products, often invisibly inside customer devices. Listed on the TSE Growth market.

[How did business move] FY10/2026 Q1 was rough: revenue fell -32.2% YoY to ¥474 million, with an operating loss of ¥391 million (widening loss). Operating margin deteriorated sharply from -19.7% to -82.5%. Despite this, full-year guidance was left unchanged: revenue ¥3.5 billion (+4.1%), operating profit ¥100 million (+118.1%), net income ¥70 million — an aggressive bet on H2 recovery. Dividend remains at zero.

[Why did business move this way] First, weakness in the core Smart Device segment is the direct cause — Morpho continues to develop new Chinese smartphone-maker customers but the wins are not yet showing in Q1 numbers. Second, smartphone-market maturation (flat global shipments) is structurally shrinking the image-processing-engine revenue base. Third, upfront investment in new areas like the automotive 「Morpho Automotive Suite」 (launched 2025) continues, but revenue contribution lies in the future while costs hit today.

[Why did the stock move this way] First, the stock has been weak — it hit a 10-year low of ¥609 on March 30, 2026 as the market refused to believe full-year guidance, judging that recovering a -32% Q1 decline in H2 is unrealistic. Second, while it rebounded to a ¥681 close on May 28, it remains stuck in a ¥600-700 range on thin volume — a wait-and-see mode. Third, the combination of no dividend, ongoing losses, and being a small-cap Growth-market name pushes Morpho off institutional screens, so buyers are simply absent.

[UNVERIFIED] FY10/2027 guidance, specific mid-term plan targets, and concrete large-order amounts for automotive deals could not be verified from public sources."""}

C["3660"] = {"jp": """【会社概要】アイスタイルは化粧品クチコミサイト『@cosme(アットコスメ)』を中核に、@cosme STORE(全国の実店舗)、@cosme TOKYO(原宿旗艦店)、@cosme SHOPPING(EC)、化粧品ブランド向けのマーケティング支援(広告・サンプリング・データ提供)、@cosme HONG KONGなどのアジア展開を行うコスメ・プラットフォーマー。東証プライム上場。

【業績の動き】2026年6月期第3四半期累計は、売上高596.94億円(+19.7%)、営業利益28.84億円(+23.0%)で大幅増収増益。第1四半期は売上400.89億円(+21.2%)、営業利益18.39億円(+23.0%)。通期予想は売上830億円(+20.7%)、営業利益38億円(+20.1%)、経常利益38億円(+14.8%)、純利益26.5億円(+13.9%)を据え置き。配当は予想1株1円(配当性向約3.5%) — 再投資優先の姿勢。

【なぜ業績がこう動いたのか】第一にリテール事業の好調 — 店舗売上が前年比+26.5%伸長し、店舗リニューアルや訪日インバウンド消費の取り込みが寄与。第二にマーケティング支援事業の継続成長 — @cosme上の口コミ・閲覧データを活用したブランド向け広告・サンプリング・データ販売は粗利率が高い構造で、売上以上に利益が伸びるレバレッジが効いた。第三にECの新規顧客獲得とプラットフォーム連携・販売イベント成功でEC成長が顕著。一方グローバル(@cosme HONG KONG)は開店費用先行で短期赤字。

【なぜ株価がこう動いたのか】第一にインバウンド消費回復の代表銘柄として再評価 — 韓国・中国・東南アジアからの訪日客による日本コスメ需要が構造的な追い風と認識された。第二に2026年6月期の中間・3Q累計でいずれも+20%超の増益が続き、機関投資家のクオリティ・グロース戦略に合致。第三にマーケティング支援事業の高粗利と@cosmeの『化粧品ブランドが無視できないインフラ』というプラットフォーム性が長期評価ポイントとして定着。

【UNVERIFIED】2026年6月期通期確定値、2027年6月期ガイダンス、年間配当の確定値は決算発表前のため未確認。""",
"en": """[Company Overview] istyle is a cosmetics platform built around 「@cosme」, Japan's largest cosmetics review site. Around the @cosme core it operates @cosme STORE (physical stores nationwide), @cosme TOKYO (Harajuku flagship), @cosme SHOPPING (e-commerce), brand-side marketing support (advertising, sampling, data sales), and Asia expansion including @cosme HONG KONG. Listed on TSE Prime.

[How did business move] FY6/2026 9-month cumulative: revenue ¥59.694 billion (+19.7% YoY), OP ¥2.884 billion (+23.0%). Q1: revenue ¥40.089 billion (+21.2%), OP ¥1.839 billion (+23.0%). Full-year guide left unchanged: revenue ¥83.0 billion (+20.7%), OP ¥3.8 billion (+20.1%), ordinary profit ¥3.8 billion (+14.8%), net income ¥2.65 billion (+13.9%). Dividend forecast at just ¥1 per share (payout ratio ~3.5%) — heavily reinvesting.

[Why did business move this way] First, Retail business strength — store sales rose +26.5% YoY thanks to renovations and inbound-tourist capture. Second, sustained Marketing Support growth — brand-side advertising, sampling, and data sales using @cosme review and browsing data carry high gross margins, producing operating-leverage where profit grows faster than revenue. Third, EC growth was standout via platform partnerships and successful sales events. Global (@cosme HONG KONG) is loss-making short-term due to launch costs.

[Why did the stock move this way] First, re-rated as a flagship inbound-recovery name — Korean, Chinese, and Southeast Asian tourist demand for Japanese cosmetics is recognized as a structural tailwind. Second, +20%-plus OP growth in both H1 and 9M consistently meets institutional Quality Growth criteria. Third, the high-margin Marketing Support business plus @cosme's platform power are entrenched long-term valuation drivers.

[UNVERIFIED] FY6/2026 final results, FY6/2027 guidance, and finalized annual dividend were not yet announced at search time."""}

C["3661"] = {"jp": """【会社概要】エムアップホールディングスは、子会社のFanplus(ファンクラブ・ファンサイト運営、EC事業)、Dear U plus(ファン向けコンテンツ事業)、The Star Japanなどを通じて、アーティスト・タレント・スポーツチーム向けの公式ファンクラブの構築・運営、電子チケット販売・トレード、グッズEC、オンラインくじ、スポーツ向けデジタルカード(プロ野球・バスケ・バレー)などを展開するエンタメ・コンテンツ持株会社。東証プライム上場。

【業績の動き】2026年3月期(本決算)は売上高317.15億円(+23.0%)、営業利益50.03億円(+23.1%)、経常利益54.3億円(+32.1%) — 7期連続の最高益、8期連続の増収増益を達成。Q1単独でも売上+27.0%、営業利益+59.3%と急成長スタート。配当は12.5円→20円→24円(2027年3月期予想)へ継続増配。配当性向目標を従来の30%から『40~50%』へ引き上げ、累進配当方針を導入。2026年5月15日に決算発表。

【なぜ業績がこう動いたのか】第一にコンテンツ事業(ファンクラブ)の有料会員数増加 — ライブエンタメ市場の本格回復に加え、オンラインライブ配信や限定動画など、ファンクラブのデジタル化投資がARPUを押し上げた。第二に電子チケット事業の好調 — コロナ後の対面イベント完全復活で発券枚数が増加、公式二次流通も成長。第三に周辺サービス(オンラインくじ、スポーツ向けデジタルカード等)の多角化で売上構成が拡大。FY27は生成AI実装による開発効率化+オフショア活用で利益成長を狙う。

【なぜ株価がこう動いたのか】第一に8期連続増収増益という極めて稀な持続成長記録 — 機関投資家のクオリティ・グロース戦略のスクリーニングに合致する分かりやすいストーリー。第二に配当性向引き上げと累進配当方針の導入 — インカム志向の機関投資家を引き付けた。第三に旧ジャニーズ事務所(現STARTO ENTERTAINMENT)など大型芸能IPの再編後の新体制下でファンクラブ・チケット案件への深い関与期待が長期成長期待を支えている。

【UNVERIFIED】2027年3月期の売上高・営業利益のガイダンス具体数値、FY2026の純利益確定値の出所URLは未確認。""",
"en": """[Company Overview] m-up holdings is an entertainment / content holding company that runs official fan clubs, fan sites and e-commerce for artists, talent and sports teams through subsidiaries such as Fanplus, Dear U plus, and The Star Japan — businesses include fan-club operations, e-ticket sales and trade, merchandise EC, online lottery, and sports digital cards. Listed on TSE Prime.

[How did business move] FY3/2026 full-year: revenue ¥31.715 billion (+23.0%), OP ¥5.003 billion (+23.1%), ordinary profit ¥5.43 billion (+32.1%) — 7th consecutive year of record profit and 8th consecutive year of revenue + profit growth. Q1 alone: revenue +27.0%, OP +59.3%. Dividend stepped up ¥12.5 → ¥20 → ¥24 (FY3/2027 plan). Payout-ratio target raised from 30% to 「40-50%」, with a progressive-dividend policy. Results announced May 15, 2026.

[Why did business move this way] First, paid-member growth in the Content (fan club) business — beyond live-entertainment recovery, investment in fan-club digitalization lifted ARPU. Second, strong e-ticket business — full return of in-person events boosted ticket volumes, and official secondary distribution is growing. Third, adjacent services (online lottery, sports digital cards) diversified the revenue mix. For FY27, the company targets profit growth via generative-AI dev efficiency and offshore utilization.

[Why did the stock move this way] First, an exceptionally rare 8-year sustained revenue + profit growth streak. Second, the payout-ratio raise and progressive-dividend policy attracted income-oriented institutional investors. Third, expectations of deep involvement in fan-club / ticket businesses after the major Johnny's reorganization (now STARTO ENTERTAINMENT) support long-term growth views.

[UNVERIFIED] Specific FY3/2027 revenue / OP guidance figures and the source URL for confirmed FY2026 net income could not be fully verified."""}

C["3668"] = {"jp": """【会社概要】コロプラはスマートフォン向けゲームの開発・運営会社 — 代表作は『白猫プロジェクト』『魔法使いと黒猫のウィズ』『ドラゴンクエストウォーク』。位置情報サービスや、起業家・XR(VR/AR)スタートアップへの『投資育成事業』も併営する。東証プライム上場。

【業績の動き】2026年9月期第2四半期(中間期)は厳しい — 売上高100.88億円(-28.2%)、営業利益5.33億円(-62.3%)、経常利益14.35億円(-29.2%)、親会社株主に帰属する四半期純利益は8.25億円(+364%、特別要因)。エンターテインメント事業は既存タイトル売上逓減をコスト削減でカバーし営業益を確保。投資育成事業は前期の大型案件の反動減で営業損失。中間配当は0円で、期末配当予想は未定。前期(2024年9月期)は上場以来初の通期赤字を計上していた経緯がある。

【なぜ業績がこう動いたのか】第一に主力『白猫プロジェクト』など長期運営タイトルの売上逓減 — サービス10年を超え、コラボイベントでランキング上昇しても恒常的な売上減を補えない。第二にApp Store/Google Playの30%プラットフォーム手数料とユーザー獲得広告費は規模に関係なく一律で発生し、中小パブリッシャーには構造的な不利。第三に投資育成事業の前期大型案件(IPO/Exitなどの特別収益)の反動で当期は損失計上、業績ボラティリティ要因に。

【なぜ株価がこう動いたのか】第一に2026年5月7日の中間決算翌日(5月8日)に株価-7.64%(-32円)と即時下落、5月11日時点では376円。第二にモバイルゲーム業界全体のセクター・デレーティング — 日本のスマホゲーム市場は横ばいで、『原神』『アズールレーン』など中国製ゲームの侵食で日本パブリッシャーの取り分が縮小している。第三にPBRが1倍前後と純資産割れ水準、無配・アナリストカバレッジ乏しい東証プライム小型ゲーム株として機関投資家の買い手が不在。

【UNVERIFIED】2026年9月期通期ガイダンス、期末配当予想、新作タイトルの具体的なリリース計画は未確認。""",
"en": """[Company Overview] COLOPL is a Japanese smartphone game developer and operator — best known for hits like 「Shironeko Project」, 「Quiz RPG: Wizard and Black Cat Wiz」, and 「Dragon Quest Walk」. It also operates location-based services and an 「investment-incubation business」 investing in entrepreneurs and XR (VR/AR) startups. Listed on TSE Prime.

[How did business move] FY9/2026 H1 (interim) was rough — revenue ¥10.088 billion (-28.2%), OP ¥533 million (-62.3%), ordinary profit ¥1.435 billion (-29.2%), net income ¥825 million (+364% on special factors). The Entertainment segment offset declining legacy-title revenue with cost cuts; the Investment-Incubation segment swung to an operating loss. Interim dividend ¥0; year-end dividend forecast undecided. FY9/2024 had been the first full-year loss since listing.

[Why did business move this way] First, gradual revenue decline of flagship long-running titles like Shironeko Project — past their 10-year mark, even collaboration events lifting rankings cannot offset structural attrition. Second, App Store / Google Play 30% platform fees and user-acquisition ad costs are flat regardless of company size, structurally disadvantaging mid-sized publishers. Third, the Investment-Incubation segment's prior-year special gains did not repeat, swinging to a loss and adding volatility.

[Why did the stock move this way] First, the day after the May 7, 2026 interim release (May 8), the stock fell -7.64% (-¥32) and was at ¥376 by May 11. Second, sector-wide derating of mobile-game stocks — Japan's smartphone-game market is flat, and Chinese titles are eroding Japanese publishers' share. Third, with PBR near 1x, no dividend, and limited analyst coverage as a small Prime-market game stock, there are essentially no institutional buyers.

[UNVERIFIED] FY9/2026 full-year guidance, year-end dividend forecast, and specific new-title release plans could not be verified."""}

C["3697"] = {"jp": """【会社概要】SHIFTはソフトウェアの品質保証(QA)を専門とする独立系IT企業 — 他社が開発したソフトを発売前にテストしてバグを見つける『第三者検証』が本業。近年はソフトウェア開発支援、AI活用の自動テストサービス『DQS』(DX Quality Service)、コンサルティングも拡大している。東証プライム上場。

【業績の動き】2026年8月期 中間期(2025年9月~2026年2月)は、売上高720.35億円(+16.8%)、経常利益66.09億円(-16.0%)、営業利益率は前年同期14.4%→直近3ヶ月で11.0%へ低下。会社の通期予想は売上1,500億円(+15.5%)、調整後営業利益200億円(+13.4%)、調整後経常利益200億円(+16.3%)、純利益135億円(+24.3%)。前期(2025年8月期)は売上+17%増の1,298億円、営業利益+48%増で粗利率34.7%と過去最高だった。配当はゼロ継続。

【なぜ業績がこう動いたのか】第一にAI活用QAサービス『DQS』への先行投資 — エンジニアの大量採用と販売・マーケティング強化で費用が先に出る構造。前期に抑制していた採用が今期から正常化し人件費が急増。第二に短期借入金増加で支払利息が上昇、経常利益を圧迫。第三にAI関連の新規売上は将来時点での貢献を見込むため、現在の利益が将来投資のために犠牲になる『spend first, earn later』の谷間に位置している。

【なぜ株価がこう動いたのか】第一に2026年6月2日に大和証券がレーティングを最上位『1』→『3』へ2段階格下げ、目標株価を1,700円→780円へ半減以下に切り下げ、AI投資の利益転換タイミングへの信頼が崩れたシグナルに。第二に6月3日に株価が-12.21%急落し694.7円まで下落、2月24日には年初来安値590円を記録済み。第三にPER約41倍という高バリュエーション銘柄では利益鈍化が激しく売られる構造、加えて無配で長期保有インセンティブが乏しく、過去M&Aののれん償却負担も残る。

【UNVERIFIED】2027年8月期ガイダンス、DQSの具体的な売上規模、目標株価引き下げを実施した正確な証券会社名(大和証券で確認)以外のアナリスト動向は未確認。""",
"en": """[Company Overview] SHIFT is an independent Japanese IT company specializing in software quality assurance (QA) — its core business is 「third-party verification」, testing other companies' software before launch to find bugs. It has expanded into software-development support, an AI-powered automated test service 「DQS」 (DX Quality Service), and consulting. Listed on TSE Prime.

[How did business move] FY8/2026 H1 (Sep 2025 - Feb 2026): revenue ¥72.035 billion (+16.8%), ordinary profit ¥6.609 billion (-16.0%); operating margin fell from 14.4% YoY to 11.0% in the latest 3-month quarter. Full-year guidance: revenue ¥150.0 billion (+15.5%), adjusted OP ¥20.0 billion (+13.4%), adjusted ordinary profit ¥20.0 billion (+16.3%), net income ¥13.5 billion (+24.3%). FY8/2025 was a record year: revenue +17% to ¥129.8 billion, OP +48%, gross margin a record 34.7%. Dividend remains zero.

[Why did business move this way] First, heavy upfront investment in AI-QA service 「DQS」 — mass hiring of engineers and aggressive sales-and-marketing push spending out the door. Hiring restrained in the prior year normalized this year, so personnel costs jumped. Second, short-term borrowing for working capital rose, lifting interest expense and pressuring ordinary profit. Third, AI-related revenue is expected to contribute only in future periods, putting SHIFT in a 「spend first, earn later」 valley.

[Why did the stock move this way] First, on June 2, 2026 Daiwa Securities downgraded SHIFT two notches from top rating 「1」 to 「3」 AND slashed the target price from ¥1,700 to ¥780 — a signal that trust in the AI-investment payback timing collapsed. Second, on June 3 the stock crashed -12.21% to ¥694.7, after already hitting a year-low of ¥590 on February 24. Third, at PER ~41x SHIFT is a high-valuation name where slowing profit growth is punished hard; with no dividend and lingering goodwill amortization from past M&A, long-term holders have no income reason to stay.

[UNVERIFIED] FY8/2027 guidance, specific DQS revenue scale, and broader analyst-action details beyond the confirmed Daiwa downgrade could not be verified."""}

C["3741"] = {"jp": """【会社概要】セックは1970年設立の独立系ソフトウェア企業で、『リアルタイム技術』を中核に4つの事業領域を展開 — (1)ロボット・モビリティ事業(自動運転車両、産業用/サービスロボット、宇宙探査ロボットの制御ソフト)、(2)宇宙・天文・科学事業(科学衛星搭載ソフト、はやぶさ系列の地上管制システム、ISS実験モジュール向けソフト)、(3)社会基盤システム事業(官公庁・防衛・医療・エネルギー)、(4)モバイルネットワーク・インターネット事業(通信キャリア基地局ソフト、組込みソフト、IoT/クラウド)。主要取引先にJAXAなど。東証プライム上場。

【業績の動き】2026年3月期 通期(本決算)は売上高112.2億円(+9.0%)、営業利益18.79億円(+4.8%)で増収増益。2027年3月期会社予想は売上107億円(+3.9%、※減収予想)、営業利益18.4億円(+2.6%)、経常利益20.1億円(+6.1%)、当期純利益13.95億円(+3.8%)。2025年10月1日付で1株→2株の株式分割を実施。配当は分割考慮後で2026年3月期56円(分割前換算112円)を予定し、前期110円から増配。

【なぜ業績がこう動いたのか】第一にロボット・モビリティ事業の好調 — 自動運転・先進運転支援システム(AD/ADAS)実用化と、自律搬送ロボット向けの制御ソフト需要拡大が寄与。第二に宇宙・天文・科学事業の継続案件 — JAXA向けはやぶさ系列の地上管制システムや科学衛星向けソフトなど、長期の安定収益。第三に社会基盤システム(防衛・防災)分野の需要拡大 — 国内安全保障・サイバー防衛投資の増加で官公庁案件が伸長。

【なぜ株価がこう動いたのか】第一に2026年6月4日時点の株価は3,750円(-4.21%)と決算後に弱含み — 翌期(2027年3月期)が会社予想で減収転換となることが嫌気された。第二に株価分割実施で個人投資家層を取り込みやすくなった一方、分割直後特有の需給調整が継続。第三に宇宙・ロボット・自動運転・防衛など『フィジカルAI関連株』として中長期テーマ性は強いが、グロース株からバリュー寄りの再評価で機関投資家のリバランスが入りやすい局面。

【UNVERIFIED】2027年3月期の配当予想、最新の中期経営計画数値目標、目標株価コンセンサスの具体水準は未確認。""",
"en": """[Company Overview] SEC Co. (3741) is an independent Japanese software firm founded in 1970, built on 「real-time technology」 across four business fields: (1) Robot / Mobility, (2) Space / Astronomy / Science, (3) Social Infrastructure, (4) Mobile Network / Internet. Major customers include JAXA. Listed on TSE Prime.

[How did business move] FY3/2026 full-year: revenue ¥11.22 billion (+9.0%), OP ¥1.879 billion (+4.8%). Company guidance for FY3/2027: revenue ¥10.7 billion (+3.9%), OP ¥1.84 billion (+2.6%), ordinary profit ¥2.01 billion (+6.1%), net income ¥1.395 billion (+3.8%). A 1-for-2 stock split was executed on October 1, 2025. Post-split FY3/2026 dividend planned at ¥56 per share (¥112 pre-split equivalent) vs ¥110 the prior year — a hike.

[Why did business move this way] First, strong Robot / Mobility segment — AD/ADAS commercialization and demand for autonomous-transport-robot control software contributed. Second, sustained projects in the Space / Astronomy / Science segment — Hayabusa-series ground-control systems and science-satellite software provide long-term stable revenue. Third, Social Infrastructure (defense / disaster prevention) demand expansion — rising domestic-security and cyber-defense investment drove government-segment growth.

[Why did the stock move this way] First, the stock was at ¥3,750 (-4.21% on the day) on June 4, 2026 — weak post-earnings, as next-year (FY3/2027) guidance suggesting a possible top-line cooling spooked investors. Second, the stock split likely broadened retail-investor participation but introduced short-term supply-demand adjustment typical of post-split periods. Third, while SEC enjoys strong mid-long-term theme appeal as a 「Physical AI」 stock, the market's rotation from growth toward more value-tilted positioning invites institutional rebalancing.

[UNVERIFIED] FY3/2027 dividend forecast, latest mid-term-plan numerical targets, and concrete analyst target-price consensus could not be verified."""}

C["3760"] = {"jp": """【会社概要】ケイブはシューティングゲームを中心に開発するゲーム会社で、アーケード時代の名作IP(『怒首領蜂』『虫姫さま』『デススマイルズ』『東方幻想エクリプス』等)のスマートフォン展開を主力とする。子会社の『でらゲー』を通じてスマホゲーム開発・運営も実施。並行して動画配信関連事業(VTuber・ライブ配信プラットフォーム関連)も保有。東証スタンダード上場。

【業績の動き】2026年5月期 第1四半期は売上高26.27億円(-11.6%)、営業損失5.65億円と減収減益。ゲーム事業セグメントが-10.6%減収。第3四半期累計の経常損益は-8.52億円、通期予想(2025年4月13日発表)は経常損益-6.40億円の赤字転落予想、増収率-14.8%予想。前期(2024年5月期)は『東方幻想エクリプス』ヒットで売上122.7億円(+76.3%)、営業利益18.7億円(+667.4%)と急成長していた反動。ROE-62.3%と自己資本毀損が大きい。

【なぜ業績がこう動いたのか】第一に前期『東方幻想エクリプス』(2023年11月リリース、登録20万人超)の特需の反動 — 単一ヒットへの依存度が高く、翌期は新作不在で売上の谷を迎えた。第二に動画配信関連事業のセグメント損失 — ライブ配信プラットフォームの多様化とクリエイター急増による競争激化で-32%減収・赤字。第三にシューティングゲームというニッチジャンル特性 — 大ヒットが出にくく、IPの寿命に依存する構造的な業績ボラティリティ。

【なぜ株価がこう動いたのか】第一に通期赤字転落見通しと-14.8%減収予想で長期低迷 — 過去1年トータルリターンは-29%超。第二に東証スタンダード小型株でアナリスト・カバレッジが限定的、機関投資家の買い手不在で売り圧力に弱い。第三にPBRは1倍台に低下しすでに業績悪化を織り込む水準 — 期待値は底値圏だが、新作ヒット・IPライセンス契約など明確な再評価トリガーが見えるまでは出来高薄い様子見モードが継続。

【UNVERIFIED】2026年5月期通期確定値、2027年5月期ガイダンス、新作タイトルの具体パイプラインは未確認。""",
"en": """[Company Overview] CAVE Interactive develops games, specializing in shoot-em-ups, and is primarily known for arcade-era classic IPs such as 「Dodonpachi」, 「Mushihimesama」, 「Deathsmiles」, and 「Touhou Gensou Eclipse」, mostly on mobile. Through subsidiary 「DeLaGame」 it also develops and operates other smartphone games. In parallel it runs a video-distribution-related business. Listed on TSE Standard.

[How did business move] FY5/2026 Q1: revenue ¥2.627 billion (-11.6%), operating loss ¥565 million. Game segment -10.6%. 9-month cumulative ordinary loss ¥852 million. Full-year guide: ordinary loss ¥640 million, revenue -14.8%. The prior year FY5/2024 had been a hit-year — 「Touhou Gensou Eclipse」 (released Nov 2023, 200,000+ pre-registrations) drove revenue ¥12.27 billion (+76.3%) and OP ¥1.87 billion (+667.4%); this year is the payback. ROE -62.3% reflects meaningful equity erosion.

[Why did business move this way] First, the 「Touhou Gensou Eclipse」 hit-driven boom is not repeating — heavy dependence on a single hit means the year after sees a revenue valley with no follow-up release. Second, video-distribution-related business posted a segment loss — fragmentation of live-streaming platforms and a surge of creators intensified competition (-32% revenue, loss). Third, the shoot-em-up niche makes 「hit-or-miss」 new-title risk especially acute.

[Why did the stock move this way] First, the full-year loss-reversion guide and -14.8% revenue forecast kept the stock in a downtrend — 1-year total return below -29%. Second, as a TSE Standard small-cap with limited analyst coverage, there are essentially no institutional buyers to absorb sell pressure. Third, PBR has come down to the low single digits, already pricing in the deterioration — expectations are bombed-out, but until a clear re-rating trigger appears, low-volume wait-and-see drift continues.

[UNVERIFIED] FY5/2026 final results, FY5/2027 guidance, and concrete new-title pipeline details could not be verified."""}

C["3762"] = {"jp": """【会社概要】テクマトリックスは法人向けITインフラを提供する独立系IT企業 — 主に2本柱で運営している。(1)『情報基盤事業』はサイバーセキュリティ製品(Cortex XSIAM等の代理販売、SOCサービス)やネットワーク機器の販売・保守、(2)『アプリケーション・サービス事業(CRM等)』はコンタクトセンター向け『FastHelp』など顧客対応ソリューションを提供。医療画像クラウド『NOBORI』も保有。東証プライム上場。

【業績の動き】2026年3月期 通期は会社予想で売上収益730億円(+12.5%)、営業利益76億円(+14.0%)、親会社所有者帰属当期利益48.8億円(+20.2%) — 11期連続で過去最高益更新見通し。前期(2025年3月期)は売上648.82億円(+21.7%)、営業利益66.68億円(+14.0%)、純利益40.6億円(+14.7%)。配当は2025年3月期年間34円から2026年3月期は中間13円+期末23円=年間36円へ増配予定。

【なぜ業績がこう動いたのか】第一に情報基盤事業のクラウド型セキュリティ製品が好調 — Cortex XSIAMをはじめとするXDR/SOC領域の新規顧客獲得と既存契約の更新が順調に取れている。第二にCRM事業の『FastHelp』など主力ソリューションがコンタクトセンターのDX需要を取り込み安定成長。第三に情報セキュリティ規制強化(個人情報保護、サイバー防衛)に伴う企業のセキュリティ投資が国内全体で構造的に増加 — テクマトリックスの主戦場で追い風が継続。

【なぜ株価がこう動いたのか】第一に11期連続最高益更新という素晴らしい実績にもかかわらず、ITサービス業界では『派手な物語のないコンパウンダー』はAI・データセンター関連のような目立つテーマ性に欠け、グロース投資家の注目を集めにくい。第二にPBRが相対的に高水準で『市場が高い期待を織り込んでいる』状態、わずかな業績未達でも調整が入りやすい。第三にグローバル展開は限定的で海外マネー流入による再評価触媒に乏しく、日本市場内での『地味な良企業』評価に留まりがち。

【UNVERIFIED】2026年3月期の通期確定値(検索時点では予想値ベース)、2027年3月期ガイダンス、医療画像クラウドNOBORIの売上規模は未確認。""",
"en": """[Company Overview] TechMatrix is an independent Japanese IT company providing corporate IT infrastructure across two main pillars: (1) 「Information Infrastructure」 — reselling and maintaining cybersecurity products (Cortex XSIAM etc., SOC services) and networking gear; (2) 「Application Services (CRM etc.)」 — customer-service solutions like 「FastHelp」 for contact centers. It also operates a medical-image cloud service 「NOBORI」. Listed on TSE Prime.

[How did business move] FY3/2026 full-year company guidance: revenue ¥73.0 billion (+12.5%), OP ¥7.6 billion (+14.0%), net income attributable to parent owners ¥4.88 billion (+20.2%) — projected 11th consecutive year of record-high profit. FY3/2025 actuals were revenue ¥64.882 billion (+21.7%), OP ¥6.668 billion (+14.0%), net income ¥4.06 billion (+14.7%). Dividend rising from FY3/2025 annual ¥34 to FY3/2026 ¥36.

[Why did business move this way] First, Information Infrastructure cloud-security products are strong — XDR/SOC offerings like Cortex XSIAM are winning new customers and renewing existing contracts. Second, CRM offerings like 「FastHelp」 are capturing contact-center DX demand for stable growth. Third, tightening information-security regulations are structurally raising corporate security spend across Japan.

[Why did the stock move this way] First, despite 11 consecutive years of record profits, in IT services 「compounders without a dramatic narrative」 lack the eye-catching themes that attract growth investors. Second, the relatively elevated PBR reflects 「the market already pricing in high expectations」, so even minor misses trigger corrections. Third, very limited overseas business means no global-rerating catalyst.

[UNVERIFIED] FY3/2026 full-year actuals, FY3/2027 guidance, and the NOBORI medical-image-cloud revenue scale could not be verified."""}

# Apply
data = json.loads(IT_PATH.read_text(encoding='utf-8'))
applied, missing = [], []
for ticker, content in C.items():
    if ticker not in data:
        missing.append(ticker); continue
    data[ticker]['jp_summary'] = content['jp']
    data[ticker]['en_summary'] = content['en']
    applied.append(ticker)
IT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
json.loads(IT_PATH.read_text(encoding='utf-8'))
print(f"Applied {len(applied)}: {applied}")
if missing: print(f"MISSING: {missing}")
