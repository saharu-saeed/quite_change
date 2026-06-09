# -*- coding: utf-8 -*-
"""Apply IT batch 7 (IT07, 8 entries)."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
IT_PATH = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data\company_research_2025.json")
C = {}

C["4733"] = {"jp": """【会社概要】オービックビジネスコンサルタント(OBC)は中堅・中小企業向けの基幹業務ソフト「奉行シリーズ」(会計・人事給与・販売・税務など)を作る会社。親会社のオービック(4684、大企業向け)とは別法人で、両社とも東証プライム上場。近年は「奉行クラウド」というクラウド版へ顧客を移行中で、月額課金型のストック収益が売上の8割超を占める。

【業績の動き】2026年3月期は売上¥514億円(+9.4%)、営業利益¥235.8億円(+8.4%)、経常¥252.2億円(+9.4%)、純利益¥181.3億円(+12.0%)と全項目増益。営業利益率45.9%という驚異的な水準。2027年3月期予想は売上¥575億円(+11.9%)、営業¥265億円(+12.4%)、純¥193.5億円(+6.7%)とさらに伸びる見通し。年間配当は前期100円→今期111円(+11円)へ増配、来期は130円(+19円)を予定。

【なぜ業績がこう動いたのか】第一に「奉行クラウド」の利用社数拡大が継続。ARR(年間継続収益)は¥442億円で前年比+13.5%伸び、特にクラウドARRは¥322億円と単四半期で¥19億円増加。第二に高単価製品(奉行クラウドプレミアム等)へのアップセルでARPUが上昇。単なる契約社数増ではなく1社あたり単価まで上がる構造。第三に改正電帳法・インボイス制度・働き方改革対応で中小企業の業務ソフト需要がイベント駆動的に増加。

【なぜ株価がこう動いたのか】第一に営業利益率45.9%という極めて高い収益性が米国SaaS企業並みと再評価。第二に増配の継続(11円増配)と来期さらに19円増配予定でインカム志向の機関投資家が買い継続。第三に自己資本比率76.7%の超優良財務でディフェンシブ性が高く、金利上昇局面でも財務リスクが極小。PER予23.8倍、PBR2.71倍、ROE11.04%。アナリスト目標株価は¥8,867で現値¥6,127から+44.7%の上昇余地評価。""",
"en": """[Company Overview] OBIC Business Consultants (OBC) makes core business software (the 「Bugyo」 series — accounting, HR/payroll, sales, tax) for mid-sized and SME customers. Separate listed company from parent OBIC (4684). OBC is migrating customers to 「Bugyo Cloud」, and stock-type recurring revenue exceeds 80% of total sales.

[Earnings Movement] FY3/2026 revenue ¥51.4 billion (+9.4%), operating profit ¥23.58 billion (+8.4%), ordinary ¥25.22 billion (+9.4%), net profit ¥18.13 billion (+12.0%). Operating margin: 45.9%. FY3/2027 guidance: revenue ¥57.5 billion (+11.9%), OP ¥26.5 billion (+12.4%), net ¥19.35 billion (+6.7%). Annual dividend raised from ¥100 to ¥111 this year, with ¥130 (+¥19) guided for next year.

[Why Earnings Moved] First, sustained user growth in 「Bugyo Cloud」 — ARR reached ¥44.2 billion (+13.5% YoY), with cloud ARR alone at ¥32.2 billion. Second, upselling to high-priced products lifted ARPU. Third, event-driven SME demand from the revised e-storage law, invoice system, and work-style reforms.

[Why the Stock Moved] First, the 45.9% operating margin earned a re-rating as 'mature high-margin SaaS-like cash machine' on par with top US SaaS. Second, the sustained dividend-hike trajectory is attracting income-oriented institutional capital. Third, equity ratio of 76.7% means defensive characteristics. Forecast PER 23.8x, PBR 2.71x, ROE 11.04%. Analyst target ¥8,867 vs current ¥6,127 implies ~44.7% upside."""}

C["4751"] = {"jp": """【会社概要】サイバーエージェントは日本のインターネット総合企業。3つの事業の柱を持つ — (1)インターネット広告(国内最大級のネット広告代理店)、(2)メディア&IP(動画配信「ABEMA」など)、(3)ゲーム(「ウマ娘 プリティーダービー」など)。ABEMAは2016年開局以来、長年赤字事業だったが、2026年9月期にようやく黒字転換を達成した点が大きな転機。

【業績の動き】2026年9月期第2四半期(中間)累計は売上¥4,785.8億円(+13.3%、四半期で過去最高)、営業利益¥524.6億円(+79.8%)、経常¥539億円(+84.8%)で大幅増収増益。セグメント別: ゲーム売上¥1,322億円(+47.4%)、営業¥386億円(+106.3%)で2倍増益。メディア&IP売上¥626億円(+12.5%)、営業¥49億円(+3.5倍)。広告売上¥1,277億円(+8.6%)、営業¥68億円(+13.9%)。通期予想は売上¥8,800億円、営業¥500-600億円のレンジで据え置き。配当は前期¥17→今期¥19予定。

【なぜ業績がこう動いたのか】第一にゲーム事業の構造的成長 — 「ウマ娘」海外展開とアニバーサリーイベントが大幅増益を牽引、複数の既存タイトルが安定収益化。第二にABEMAの黒字転換 — 2025年Q1にABEMA単体が初の四半期黒字¥5億円を達成、メディア事業全体も黒字定着。長年の投資フェーズが「投資回収フェーズ」へ転換。第三に広告事業の生成AI活用 — 動画広告と生成AIによる広告制作効率化で利益率改善。

【なぜ株価がこう動いたのか】第一に第1四半期発表で営業利益+2.8倍と決算サプライズで反発上昇。第二にABEMA黒字化という「投資家が長年待っていた構造転換」の実現で再評価。第三に通期予想据え置きで「下期もさらなる上振れ余地」期待が広がり、業績ドリブンの正統派上昇銘柄として機関投資家に評価。加えて日経225採用銘柄でETFパッシブフローの影響も大。""",
"en": """[Company Overview] CyberAgent is a Japanese internet conglomerate with three pillars: (1) Internet Ads, (2) Media & IP (video service 「ABEMA」), (3) Games (「Uma Musume Pretty Derby」). ABEMA had been loss-making since launch in 2016 — its turn to profitability in FY9/2026 is a major inflection point.

[Earnings Movement] FY9/2026 H1 cumulative: revenue ¥478.6 billion (+13.3%, record quarterly), OP ¥52.5 billion (+79.8%), ordinary ¥53.9 billion (+84.8%). Game: revenue ¥132.2 billion (+47.4%), OP ¥38.6 billion (+106.3%). Media & IP: revenue ¥62.6 billion (+12.5%), OP ¥4.9 billion (3.5x). Ads: revenue ¥127.7 billion (+8.6%), OP ¥6.8 billion (+13.9%). Full-year guidance held at revenue ¥880 billion, OP ¥50-60 billion. Dividend: ¥17 → ¥19.

[Why Earnings Moved] First, structural growth in Games — 「Uma Musume」 overseas expansion plus anniversary events drove the doubling of profit. Second, ABEMA's turn to profitability — Q1 marked ABEMA's first standalone quarterly profit (¥0.5 billion). Third, generative-AI applied to ad production lifted ad-business margins.

[Why the Stock Moved] First, Q1's 2.8x OP growth was an earnings surprise. Second, ABEMA's profitability drove a re-rating. Third, by holding full-year guidance after a strong H1, management left room for further upside. As a Nikkei 225 constituent, ETF passive flows also amplify the move."""}

C["4776"] = {"jp": """【会社概要】サイボウズはビジネス向けコラボツール・クラウドサービスの会社。主力は「kintone」というノーコード(プログラミング無し)で業務アプリを作れるクラウドプラットフォーム。ほかに「サイボウズOffice」「Garoon」などの中小・中堅・大企業向けグループウェアも提供。クラウド契約は約7万社、ユーザーライセンス360万を突破している。

【業績の動き】2025年12月期は売上¥374.3億円(+26.1%)、営業利益¥101.1億円(+106.4%、倍以上)、経常¥103.3億円(+93.5%)、純利益¥70.8億円(+99.2%)と全項目大幅増益。kintone単体売上¥216.9億円(+33.9%)。クラウド関連売上¥344.85億円(+28.7%)。2026年12月期予想は売上¥421.7億円(+12.7%)、営業¥105.1億円(+4.1%)。第1四半期は売上¥102.5億円(+17.0%)、営業¥30.1億円(+15.3%)で順調なスタート。増配と自己株式取得も決定。

【なぜ業績がこう動いたのか】第一にkintoneの契約社数拡大が継続(国内39,000社へ)。第二に価格改定とアップセル — kintoneのARPA(1社あたり売上)はQ2で前年+27%伸び、約2割が価格改定、残り8割が全社展開アップセル効果。第三に大規模顧客への浸透 — 1社全社導入の事例が増え、ライセンス数が大幅に拡大。

【なぜ株価がこう動いたのか】時価総額¥1,159億円、予想PER16.2倍、PBR6.25倍。第一に2024年2月以降の「IR姿勢転換」が継続評価 — ARR等SaaS指標の開示開始で機関投資家の分析可能性が向上。第二に自社株買い発表で株価が大幅反発した局面あり、株主還元強化が支持材料。第三に2026年6月のkintone AI ローンチへの先行投資コスト懸念で、来期営業+4.1%にとどまる利益鈍化が一部嫌気され、kintone事業の急成長にしては評価が伸びにくい構造。""",
"en": """[Company Overview] Cybozu makes business collaboration tools and cloud services. The flagship is 「kintone」, a no-code cloud platform for building business apps. Other products include 「Cybozu Office」 and 「Garoon」 groupware. Cloud contracts total about 70,000 companies with 3.6 million user licenses.

[Earnings Movement] FY12/2025: revenue ¥37.43 billion (+26.1%), OP ¥10.11 billion (+106.4%, more than doubled), ordinary ¥10.33 billion (+93.5%), net ¥7.08 billion (+99.2%). kintone alone: ¥21.69 billion (+33.9%). Cloud-related revenue ¥34.485 billion (+28.7%). FY12/2026 guide: revenue ¥42.17 billion (+12.7%), OP ¥10.51 billion (+4.1%). Q1: revenue ¥10.25 billion (+17.0%), OP ¥3.01 billion (+15.3%). Dividend hike + share buyback also decided.

[Why Earnings Moved] First, kintone customer-count growth continues (39,000 domestic companies). Second, pricing + upsell — kintone ARPA rose +27% YoY in Q2. Third, deeper penetration in large-enterprise accounts.

[Why the Stock Moved] Market cap ¥115.9 billion, forecast PER 16.2x, PBR 6.25x. First, the IR pivot since Feb 2024 continues to improve institutional analyzability. Second, the share-buyback announcement drove a sharp rebound. Third, FY26 OP growth of just +4.1% — held down by upfront costs for the June 2026 kintone AI launch — disappointed some investors."""}

C["4783"] = {"jp": """【会社概要】NCD(2024年1月に旧社名「日本コンピュータ・ダイナミクス」から商号変更)は中堅システムインテグレーター。3つの事業セグメント — (1)システム開発(保険・ガス・製造業向け)、(2)サポート&サービス(AWS/Azureクラウド+IT資産管理)、(3)パーキングシステム「Park ICT」(自治体駐輪場+大規模再開発向け)。ストック型売上比率8割超。東証スタンダード上場。

【業績の動き】2026年3月期は売上¥308.67億円(+2.5%)と微増だが、営業利益¥26.38億円(-6.1%)、経常¥26.72億円(-6.3%)と減益。大型公共案件終了の反動減と新規投資費用増加が主因。2027年3月期予想は売上¥320億円、営業¥27.5億円、経常¥27.8億円、純¥18.3億円で回復見通し。配当は前期年70円→今期120円(+71%、中間60円+期末60円)へ大幅増配。連結配当性向50%以上を目標化。

【なぜ業績がこう動いたのか】第一に前期に貢献した大型公共案件の終了による反動減。第二に将来成長のためのIT人材採用拡大による人件費先行投資。第三に新規事業(駐車場ICT領域での新サービス、AI活用ソリューション等)の立ち上げ費用先行計上。ただしストック型売上比率8割超で基盤は堅調、Vision2029に向けた戦略投資フェーズ。

【なぜ株価がこう動いたのか】第一に大幅増配 — 年¥70→¥120(+71%)、配当性向30%→50%へ引き上げ。予想配当利回りは4.98%と高水準。第二に東証PBR改善要請への積極対応 — 減益局面でも還元強化に踏み込む経営姿勢を機関投資家が評価。第三に駐車場ICTのニッチ独自ポジション+ジャパンコンピューターサービス子会社連結効果でストック収益基盤が安定。PBR2.25倍、ROE20.39%、ROA10.38%、自己資本比率50.1%と財務基盤は強固。""",
"en": """[Company Overview] NCD (renamed from 「Nippon Computer Dynamics」 in January 2024) is a mid-sized systems integrator. Three segments: (1) System Development, (2) Support & Service, (3) Parking System 「Park ICT」. Stock-type revenue exceeds 80% of total. TSE Standard listed.

[Earnings Movement] FY3/2026 revenue ¥30.867 billion (+2.5%), OP ¥2.638 billion (-6.1%), ordinary ¥2.672 billion (-6.3%) — profit declined. FY3/2027 guidance: revenue ¥32 billion, OP ¥2.75 billion, ordinary ¥2.78 billion, net ¥1.83 billion — recovery. Annual dividend lifted from ¥70 to ¥120 (+71%). Target consolidated payout ratio raised to 50%+.

[Why Earnings Moved] First, reaction-decline from end of a prior-year large public-sector project. Second, upfront personnel costs from accelerated IT-talent hiring. Third, launch costs for new businesses booked upfront.

[Why the Stock Moved] First, major dividend hike — ¥70 → ¥120 (+71%). Forecast dividend yield: 4.98%. Second, active response to TSE PBR-improvement request. Third, unique niche in parking ICT + consolidation effect from subsidiary Japan Computer Service stabilizes the stock-revenue base. PBR 2.25x, ROE 20.39%, equity ratio 50.1%."""}

C["4812"] = {"jp": """【会社概要】電通総研は2024年1月1日に「電通国際情報サービス(ISID)」から商号変更した大手システム・コンサル企業。親会社の電通グループが主要株主。同時にコンサル子会社2社を統合し、電通グループから「シンクタンク機能」を移管 — 「システム開発(SI)×コンサル×シンクタンク」の3機能型プロフェッショナルファームに進化。金融・製造・公共向けが主要顧客。

【業績の動き】2025年12月期は経常利益¥236億円(+12.0%)で過去最高、売上10期連続+営業利益・純利益8期連続最高益を達成。営業利益率13.8%。ROE17.4%。2026年12月期予想は経常¥261億円(+10.5%)で2期連続最高益。Q1は売上¥438.2億円(+8.9%)、営業¥65.88億円(+14.0%)で増収増益。配当は前期¥116→¥120(+¥4)、2026年1月1日に1:3株式分割実施、今期¥45 — 実質+12.5%増配。13期連続増配、2027年に配当性向50%目標。

【なぜ業績がこう動いたのか】第一に金融・製造・公共向けDXコンサル需要の継続 — 各セグメントが好調、ビジネスソリューション部門が特に顕著。第二に商号変更後のシナジー — 統合コンサルとシンクタンクの加わりで高単価サービスの比率が上昇し、構造的に利益率が改善。第三に親会社電通グループの顧客資産(国内全業種の広告主企業)へのDX・データコンサル提供が案件パイプラインを太くした。

【なぜ株価がこう動いたのか】第一にROE17.4%という高い資本効率が日本企業平均(8-9%)を大きく上回り、海外ファンドのスクリーニングで選好されやすい。第二に13期連続増配+株式分割1:3で個人投資家層が拡大、流動性向上。第三に過去最高益の連続更新+「Vision2030(2030年売上¥3,000億円)」という長期成長ストーリーがPER再評価につながった。時価総額約¥5,267億円、PER予32.5倍、PBR4.16倍、自己資本比率61.9%。""",
"en": """[Company Overview] Dentsu Soken changed its name from 「Information Services International-Dentsu (ISID)」 on January 1, 2024. Parent Dentsu Group is the major shareholder. Concurrently it integrated two consulting subsidiaries and transferred the think-tank function — evolving into a three-function professional firm.

[Earnings Movement] FY12/2025 ordinary profit ¥23.6 billion (+12.0%, record-high), 10 consecutive years of revenue + 8 years of OP/NP record highs. Operating margin 13.8%. ROE 17.4%. FY12/2026 guidance: ordinary ¥26.1 billion (+10.5%). Q1 revenue ¥43.82 billion (+8.9%), OP ¥6.588 billion (+14.0%). Dividend: ¥116 → ¥120 (+¥4); 1:3 stock split executed Jan 1, 2026; current term ¥45. 13 consecutive years of dividend hikes.

[Why Earnings Moved] First, sustained DX-consulting demand from finance/manufacturing/public sectors. Second, synergies post-rename — integrated consulting plus the think-tank lifted high-ARPU services share. Third, access to Dentsu Group's client base deepened the pipeline.

[Why the Stock Moved] First, ROE 17.4% — far above Japan corporate average (8-9%) — screens well with overseas funds. Second, 13 consecutive years of dividend hikes + the 1:3 stock split broadened retail ownership. Third, the streak of record earnings + Vision2030 long-term growth narrative supports PER re-rating. Market cap ~¥526.7 billion, forecast PER 32.5x, PBR 4.16x, equity ratio 61.9%."""}

C["5032"] = {"jp": """【会社概要】ANYCOLOR(エニーカラー)は日本最大級のVTuber(バーチャルYouTuber)事務所「にじさんじ」を運営する会社。VTuberとは2D/3Dアニメキャラクターの姿で動画配信を行うエンターテイナーで、所属VTuberは2026年Q3時点で172人。収益源はYouTube/Twitchでの配信(スーパーチャット投げ銭)、グッズ販売、ライブイベント、ライセンス事業。アジア中心に海外展開も進める。

【業績の動き】2026年4月期第3四半期累計(9ヶ月)は売上¥420.2億円(+45.4%)、営業利益¥169.09億円(+54.2%)、経常¥169.25億円(+54.9%)、純利益¥117.93億円(+55.5%)で大幅増収増益。ANYCOLOR ID(ファン会員)は194.4万(前年+25.5%)。2026年3月通期業績予想を修正 — 売上は¥547.3-556.3億円へ上方修正、しかし営業利益は¥198.2-203.6億円へ下方修正された「ねじれ」決算。配当は¥70→¥75増配予定。

【なぜ業績がこう動いたのか】第一にコマース事業(グッズ・ライブ)の大幅成長 — 年間グッズ施策190件超で売上を牽引、海外展開も進展。第二にVTuber業界の構造的拡大とにじさんじの認知向上(女性ファン71%が中核)。第三に利益面の下方修正は「過年度開催イベントの陳腐化在庫」の評価損が原因 — Q3で¥9.7億円、Q4でさらに約¥15億円の棚卸資産評価損を計上見込み + 期末賞与約¥6.5億円。

【なぜ株価がこう動いたのか】2025年11月に高値¥6,790を付けたが、12月のQ2発表と2026年3月の通期業績「ねじれ修正」(売上上方修正・利益下方修正)が株価急落のトリガー。第一に在庫管理体制への投資家の不信感が表面化。第二に営業利益率38%維持できるかへの懸念。第三にFY27中計目標(売上¥600億円・営業¥240億円)への進捗が在庫減損で揺らぐ懸念。国内大手証券目標¥6,100→¥6,600、米系証券「買い」継続もある。ROE55.23%、ROA42.46%、自己資本比率75.4%と財務は依然超優良。""",
"en": """[Company Overview] ANYCOLOR operates 「Nijisanji」, one of Japan's largest VTuber agencies. The roster reached 172 at Q3 FY26. Revenue sources: YouTube/Twitch streaming (Super Chat tipping), merchandise, live events, licensing.

[Earnings Movement] FY4/2026 Q3 YTD (9 months): revenue ¥42.02 billion (+45.4%), OP ¥16.909 billion (+54.2%), ordinary ¥16.925 billion (+54.9%), net ¥11.793 billion (+55.5%). ANYCOLOR ID 1.944 million (+25.5% YoY). Full-year guidance revised — revenue upward to ¥54.73-55.63 billion, but OP downward to ¥19.82-20.36 billion: a 「twisted」 revision. Dividend planned to rise from ¥70 to ¥75.

[Why Earnings Moved] First, sharp growth in Commerce — over 190 merchandise campaigns drove revenue. Second, structural VTuber-industry growth and Nijisanji's awareness lift. Third, the profit downward-revision was caused by obsolete inventory from past events — ¥0.97 billion write-down in Q3 with ~¥1.5 billion more expected in Q4.

[Why the Stock Moved] After hitting a high of ¥6,790 in Nov 2025, the Dec Q2 announcement and the March 2026 twisted revision triggered a sharp decline. First, investor distrust of inventory-management practices surfaced. Second, concerns over whether the 38% OP margin can be sustained. Third, doubts about FY27 mid-term targets. ROE 55.23%, ROA 42.46%, equity ratio 75.4% — finances remain ultra-strong."""}

C["5244"] = {"jp": """【会社概要】jig.jpの主力事業はライブ配信アプリ「ふわっち(FUWATCH)」 — 配信者(主にアマチュアライバー)が動画やライブ配信を視聴者に向けて発信し、視聴者がアイテム(ギフト)を購入すると配信者にお金が入るC2Cライブストリーミング・プラットフォーム。東証グロース上場の小型株。ほかにIoT・ふるさと納税関連の新規事業も展開。

【業績の動き】2026年3月期は売上¥146.31億円(+6.1%)と微増、営業利益¥19.76億円(-1.8%)と微減。ふわっち堅調も人件費・広告費増で利益圧迫。第3四半期は売上¥112.01億円(+9.3%)、営業¥16.04億円(+4.3%)と増収増益も、Q4で減速。2027年3月期予想は売上¥165億円、営業¥19.8億円(+0.2%、ほぼ横ばい)、経常¥18.3億円、純¥11.6億円 — 人件費・広告費・新規事業投資が利益を抑える見通し。自己資本比率66.94%と財務は強固。

【なぜ業績がこう動いたのか】第一に主力「ふわっち」が堅調に推移しユーザーエンゲージメント施策が機能。第二に同時に3つのコスト要因が利益を圧迫 — (a)人件費の増加、(b)新規ユーザー獲得のための広告宣伝費とイベント費用の拡大、(c)新規事業への投資。第三に来期も同様の投資フェーズが続く見通しで、構造的に利益伸長が抑えられている。

【なぜ株価がこう動いたのか】2025年通期で-34% YoYと大きく下落。第一にライブ配信市場の競争激化 — 大手新規参入で配信者(ライバー)獲得コスト(CAC)上昇懸念、マージン圧縮への市場の嫌気。第二に来期営業利益予想が+0.2%とほぼ横ばいで「成長ストーリーの終わり」と読まれた。第三に東証グロースの小型株という構造的弱点 — 機関投資家カバレッジ不足+個人投資家センチメント悪化。株価¥278前後で停滞、再評価には新規事業ヒットか海外展開が必要。""",
"en": """[Company Overview] jig.jp's main business is the live-streaming app 「FUWATCH」 — a C2C live-streaming platform where streamers broadcast to viewers, and viewers buy items (gifts). A TSE Growth small-cap. Also operates IoT and hometown-tax-payment-related new businesses.

[Earnings Movement] FY3/2026 revenue ¥14.631 billion (+6.1%, slight up), OP ¥1.976 billion (-1.8%, slight down). FUWATCH performed well, but personnel and ad costs pressured profit. Q3: revenue ¥11.201 billion (+9.3%), OP ¥1.604 billion (+4.3%). FY3/2027 guidance: revenue ¥16.5 billion, OP ¥1.98 billion (+0.2%, essentially flat). Equity ratio 66.94%.

[Why Earnings Moved] First, the core 「FUWATCH」 held up steadily. Second, three cost pressures simultaneously squeezed profit. Third, the same investment phase continues next fiscal year.

[Why the Stock Moved] Down -34% YoY for full-year 2025. First, live-streaming market competition intensifying — well-capitalized new entrants drive up CAC. Second, FY27 OP guidance of just +0.2% read as 「end of the growth narrative」. Third, TSE Growth small-cap structural weakness. Stock stalled around ¥278."""}

C["6055"] = {"jp": """【会社概要】ジャパンマテリアルは半導体工場向けインフラサービス会社。半導体製造の現場で必要な「高純度ガス」(製造工程で使う特殊ガス)の供給、薬品管理、装置の保守メンテナンスを提供する。半導体メーカーが工場(ファブ)を建てるたびにジャパンマテリアルの仕事が増える「ピックス・アンド・ショベル」モデル。ほか3D映像処理ツール、太陽光発電も。

【業績の動き】2026年3月期は売上¥579.76億円(+10.1%)、営業利益¥146.4億円(+30.9%)で大幅増収増益。第3四半期累計は売上¥417.32億円(+18.0%)、営業¥100.03億円(+46.1%)。2027年3月期予想は売上¥610億円(+5.2%)、営業¥155億円(+5.9%)で増収増益継続。配当は前期¥24→今期¥27(+¥3)、予想配当性向約30.8%。過去12四半期にわたって純利益率・営業利益率が継続的に改善。

【なぜ業績がこう動いたのか】第一に主力エレクトロニクス事業が半導体関連設備投資の拡大と高水準の生産活動の恩恵を享受。第二に生成AI普及・データセンター需要拡大による先端半導体(2nm/3nmなど)向け需要増 — TSMC熊本やRapidus北海道などの新規ファブ立ち上げが追い風。第三に「イニシャル部門(設備投資対応)+オペレーション部門(生産同伴)」の二本立て体制で顧客の投資・稼働両局面で稼ぐ構造。

【なぜ株価がこう動いたのか】過去1年で株価+38.94%と中長期で好調。第一に2026年5月29日に日系中堅証券が強気評価継続+目標株価¥2,400へ引き上げ。第二に半導体テーマの中で「地味だが堅実な勝ち組」評価が定着しつつある。ただし上昇には構造的制約 — (a)小型株のため年金・パッシブファンド等の巨大資金が入りにくい、(b)特定大口顧客への依存度が高く投資計画変動の影響大、(c)エンジニア確保が成長スピードの制約となる、(d)機関投資家カバレッジが薄い。本格再評価にはTSMC/Rapidus等新規ファブの本格稼働が必要。""",
"en": """[Company Overview] Japan Material is an infrastructure-services company for semiconductor factories. It supplies high-purity gas, chemical management, and equipment maintenance at semi fabs. A classic 「picks-and-shovels」 model. Also handles 3D imaging tools and solar power.

[Earnings Movement] FY3/2026 revenue ¥57.976 billion (+10.1%), OP ¥14.64 billion (+30.9%). Q3 YTD revenue ¥41.732 billion (+18.0%), OP ¥10.003 billion (+46.1%). FY3/2027 guidance: revenue ¥61 billion (+5.2%), OP ¥15.5 billion (+5.9%). Dividend: ¥24 → ¥27 (+¥3), forecast payout ratio ~30.8%.

[Why Earnings Moved] First, the core Electronics segment benefits from expanding semi capex. Second, generative-AI proliferation and data-center demand drive leading-edge semi capex — TSMC Kumamoto, Rapidus Hokkaido are tailwinds. Third, the two-pillar structure captures profit in both customer capex and operating phases.

[Why the Stock Moved] Past 12 months up +38.94%. First, on May 29, 2026 a mid-tier domestic broker reiterated 「Bullish」 and raised the target to ¥2,400. Second, within the semi theme, an understated but solid winner reputation is settling in. Structural constraints: small-cap, limited institutional coverage, heavy concentration on a few large customers."""}

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
