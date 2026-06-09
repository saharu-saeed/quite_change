# -*- coding: utf-8 -*-
"""Apply IT corrections batch 2 (IT02, 8 entries)."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
IT_PATH = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data\company_research_2025.json")
C = {}

C["3776"] = {"jp": """【会社概要】ブロードバンドタワー(BBT)は東京・大手町を拠点とする都市型データセンター運営会社。企業のサーバーを預かるデータセンター事業(コンピュータプラットフォーム事業)と、地方自治体や事業者向けのケーブルテレビ向けプラットフォーム・情報サービスを行うメディアソリューション事業の2本柱。最近は5G対応設備を新設し、AI・IoT分野への展開も進めている。

【業績の動き】2026年12月期第1四半期は売上31.93億円(+2.9%)、営業利益2.24億円(+41.0%)と好調なスタート。一方で2026年12月期通期予想は売上134億円(-12.4%)、営業利益5億円(-38.4%)、経常利益4.9億円(-46.1%)、純利益1億円(-66.7%)と大幅減益見通し。年間配当は前期比1円増の3円(中間1円・期末2円)を予定し、業績悪化下でも増配を維持。

【なぜ業績がこう動いたのか】第一に、第1四半期のメディアソリューション事業が自治体向け需要を取り込んで好調に推移し、ケーブルテレビ向けプラットフォームと情報サービスが牽引した。第二に、通期予想ではコンピュータプラットフォーム事業(データセンター・データソリューション)の減収を見込んでおり、これが通期で-12.4%減収・-38.4%減益の主因。第三に、企業ITのクラウド移行が継続しており、自社データセンターの稼働率に構造的逆風が想定されている。

【なぜ株価がこう動いたのか】第一に、第1四半期の増収増益という好材料が出たものの、通期予想が経常利益-46.1%減と大幅減益のため、市場は「Q1の好調は一時的」と判断し方向感に欠ける動きが続いている。第二に、AIブームの恩恵を受けるはずのデータセンター銘柄でありながら、自社データセンターのGPU化・AI用途への明確な転換策が打ち出されておらず、テーマ性での評価が乏しい。第三に、時価総額が小さくPER水準が極端に高いため、機関投資家のカバレッジが薄く、流動性面からも積極的な買いが入りにくい構造。""",
"en": """[Company Overview] BroadBand Tower (BBT) operates urban-type data centers based in Otemachi, Tokyo. The business has two main pillars: a Computer Platform segment and a Media Solutions segment (cable TV platform and information services for local governments). Recently the company added 5G-ready facilities and is pushing into AI / IoT areas.

[Business Movement] FY12/2026 Q1: revenue 3.19 billion yen (+2.9%) and operating profit 224 million yen (+41.0%). However, full-year FY12/2026 guidance is for sharp decline: revenue 13.4 billion yen (-12.4%), operating profit 0.5 billion yen (-38.4%), ordinary profit 0.49 billion yen (-46.1%), and net profit 0.1 billion yen (-66.7%). Annual dividend is set at 3 yen (interim 1 yen, year-end 2 yen), up 1 yen YoY.

[Why business moved this way] First, Q1 Media Solutions did well by capturing local-government demand. Second, full-year guidance assumes a decline in the Computer Platform segment. Third, corporate IT continues to migrate to hyperscalers (AWS, Azure, Google Cloud), creating a structural headwind to in-house data center utilization.

[Why the stock moved this way] First, even though Q1 showed solid growth, the harsh full-year ordinary-profit guidance of -46.1% left the stock directionless. Second, although BBT should be a data-center play that benefits from the AI boom, the company has not announced clear pivots toward GPU clusters or AI workloads. Third, the small market cap and extreme historical PER range leave institutional coverage thin."""}

C["3778"] = {"jp": """【会社概要】さくらインターネットは石狩データセンターを中核とする日本のクラウド・データセンター事業者。レンタルサーバーから始まり、現在は法人向けクラウド、生成AI向けGPUインフラストラクチャーサービス、ガバメントクラウドに正式採択された国産クラウドを展開する。

【業績の動き】2026年3月期は売上353.01億円(+12.4%)と過去最高を更新したが、営業損益は前期+41.4億円の黒字から-4.0億円の赤字へ転落(従来予想は-5億円の赤字、上振れ着地)。純利益も大幅減益。1-3月期単独でも営業利益7.1億円(-54.2%)と急減。2027年3月期予想は売上450億円(+27.5%)、営業利益15億円への黒字転換を見込み、年間配当は0.5円増配を計画。エヌビディアB200を国内最大規模の約1,100基設置済。

【なぜ業績がこう動いたのか】第一に、生成AI向けGPUインフラ事業(+20.3%)とクラウドサービス(+9.4%)が成長を牽引し売上は過去最高となった一方、機材投資(B200大量導入)と人材獲得の戦略投資コストが先行し営業赤字に転落。第二に、データセンター拡張に伴う減価償却費とリース費用が急増し、利益を圧迫した。第三に、2026年3月にガバメントクラウドサービス提供事業者として正式採択され、国産クラウド需要を開拓する販売チャネルが整備された。

【なぜ株価がこう動いたのか】第一に、4月27日の決算発表で前日比-9.60%の3,295円まで急落、出来高は+415%増となった。市場は「クラウド事業の不透明感」と「投資先行による営業赤字」を嫌気し、増収・27年3月期黒字転換見通しという好材料を上回るマイナス反応となった。第二に、2023-2024年の「日本のAIクラウド代表格」というプレミアム評価が剥落しつつあり、株価は5月下旬から6月にかけて3,100円→2,939円と続落した。第三に、AWS・Azure・Google Cloudというハイパースケーラーとの規模格差、AI投資資金がエヌビディア等大手AI半導体銘柄に集中する構造があり、さくらのような中型銘柄への物色は限定的。""",
"en": """[Company Overview] SAKURA internet is a Japanese cloud and data center operator centered on its Ishikari Data Center. The company offers corporate cloud services, GPU infrastructure for generative AI, and a domestic cloud officially adopted for the Japanese Government Cloud program.

[Business Movement] FY3/2026 revenue reached a record 35.30 billion yen (+12.4%), but operating profit swung from +4.14 billion yen the prior year to a 0.40 billion yen loss. Net profit also fell sharply. January-March operating profit was just 0.71 billion yen (-54.2%). FY3/2027 guidance projects revenue of 45.0 billion yen (+27.5%) and operating profit of 1.5 billion yen, returning to the black. ~1,100 NVIDIA B200 GPUs installed (largest in Japan).

[Why business moved this way] First, generative-AI GPU infrastructure (+20.3%) and cloud services (+9.4%) drove record revenue, but heavy upfront investment in equipment and hiring tipped operating profit into the red. Second, surging depreciation and lease costs from data center expansion compressed margins. Third, official adoption as a Government Cloud provider in March 2026 opened a new sales channel.

[Why the stock moved this way] First, the stock crashed 9.60% to 3,295 yen on April 27 with volume up 415% after earnings; the market punished cloud-business uncertainty and the investment-driven operating loss. Second, the premium narrative as a top Japanese AI-cloud play (2023-2024) is fading. Third, structural scale gaps versus hyperscalers and concentration of AI-investment money into chipmakers leave only limited buying for mid-cap names."""}

C["3803"] = {"jp": """【会社概要】イメージ情報開発は東証グロース市場上場の小型ITサービス企業。画像処理・データ分析関連のソフトウェア開発、システム構築受託、技術者派遣等を行う。2026年1月に投資・経営コンサルティング会社のサイブリッジ合同会社が筆頭株主となり、M&Aを軸とする事業構造改革フェーズに突入している。

【業績の動き】2026年3月期決算は売上7.31億円(+13.2%)と増収だが、営業損失1.75億円、経常損失1.95億円、純損失2.59億円と損失拡大。FY2027業績予想は非開示。サイブリッジへの第三者割当増資で1,301,500株を1株461円で発行し、約5.94億円を調達。サイブリッジの保有比率は39.23%となり筆頭株主に。

【なぜ業績がこう動いたのか】第一に、画像処理・データ分析関連の受託案件増加で売上は2桁成長を実現。第二に、人材確保のための先行人件費投資と新規事業立ち上げ費用が利益を圧迫し損失が拡大した。第三に、サイブリッジから優れた顧客ネットワークが共有され、オフショア開発ノウハウやBPO・Webプロダクト開発分野の協業が始まったが、これらは未だ収益化前のフェーズ。

【なぜ株価がこう動いたのか】第一に、2025年9月にサイブリッジとの資本業務提携が発表され、株価は1,123円から9月10日の1,646円まで最大46.57%上昇しストップ高カイ気配となった。第二に、2026年1月29日にサイブリッジが筆頭株主となる第三者割当増資の発表で再びカイ気配を切り上げた。第三に、東証グロース小型株のため少額資金流入で株価が大きく動く構造、かつFY2027業績予想非開示が「大型M&Aが控えている」というメッセージと解釈され、投機的な買いが集中している。""",
"en": """[Company Overview] Image Information Development is a small-cap IT services company listed on the TSE Growth market, doing image-processing and data-analysis software development, contracted systems work, and engineer dispatch. In January 2026, Cybridge LLC became the largest shareholder.

[Business Movement] FY3/2026 revenue was 0.731 billion yen (+13.2%) but the company posted an operating loss of 175 million yen, ordinary loss of 195 million yen, and net loss of 259 million yen. FY3/2027 guidance is withheld. A third-party share allocation issued 1,301,500 new shares at 461 yen each, raising about 0.594 billion yen, with Cybridge at 39.23%.

[Why business moved this way] First, revenue grew double-digits on increased contract work. Second, upfront hiring costs and new-business launch expenses widened losses. Third, the alliance with Cybridge brought customer-network sharing and BPO collaboration, but none have yet been monetized.

[Why the stock moved this way] First, when the Cybridge capital alliance was announced in September 2025, the stock surged +46.57% to 1,646 yen. Second, on January 29, 2026, when the third-party share allotment naming Cybridge as the largest shareholder was announced, the stock again jumped higher. Third, as a TSE Growth small-cap with withheld FY27 guidance, the market read this as 'a major M&A deal is coming' — concentrating speculative buying."""}

C["3825"] = {"jp": """【会社概要】リミックスポイントは事業ポートフォリオが特殊な会社。電力小売事業(エナジー事業)、蓄電ソリューション・省エネ事業に加え、2024年から本格化したデジタルアセットマネジメント事業(暗号資産、特にビットコインのトレジャリー保有・運用)の3本柱で運営している。2025年以降は「ビットコイン保有量で日本最大規模を目指す」戦略を明確化。

【業績の動き】2026年3月期第1四半期は売上64.94億円(+50.8%)、営業利益17.41億円(+3,137.4%、約31倍)、経常利益17.6億円(+4,168.3%、約43倍)、純利益22.83億円(+11,863.5%、約119倍)と劇的な急回復。ビットコイン・トレジャリー事業での暗号資産評価益19.7億円計上が主因。自己資本比率は87.2%→91.9%へ向上。2026年3月期通期予想は非開示。

【なぜ業績がこう動いたのか】第一に、ビットコイン・トレジャリー事業で保有暗号資産の含み益19.7億円を計上したことが利益急増の決定的要因。本業のオペレーション改善ではなく、ビットコイン価格上昇による「紙の利益」が大半を占める。第二に、315億円の大型資金調達(新株予約権+社債)でビットコインの追加取得を進める方針を明示し、暗号資産依存度をさらに引き上げる。第三に、本業の電力小売事業は市場が小さく低マージンの構造的弱さを抱えており、収益の柱を暗号資産にシフトしている。

【なぜ株価がこう動いたのか】第一に、第1四半期決算の劇的増益はサプライズだが、業績予想非開示・暗号資産価格依存・本業の構造的弱さで機関投資家のカバレッジが薄く、株価は2026年5月25日時点で208円(前日比-5.88%)と低迷。第二に、市場はリミックスポイントを「ビットコインのレバレッジ・プレイ(代理銘柄)」として扱っており、ビットコイン価格の上下が株価変動を支配している。第三に、暗号資産を外部カストディアンに預けているため不正アクセス・規制強化リスクがあり、新株予約権発行による希薄化懸念も加わって、決算サプライズが長期的な再評価につながらない構造。""",
"en": """[Company Overview] Remixpoint has an unusual business mix. Beyond an electricity retail business (Energy segment) and energy-storage solutions, it added a Digital Asset Management segment in earnest from 2024, focused on holding and operating cryptoassets (mainly Bitcoin treasury).

[Business Movement] FY3/2026 Q1 saw a dramatic surge: revenue 6.49 billion yen (+50.8%), operating profit 1.74 billion yen (+3,137.4% YoY), ordinary profit 1.76 billion yen (+4,168.3%), and net profit 2.28 billion yen (+11,863.5%). The main driver was 1.97 billion yen in unrealized cryptoasset valuation gains. Equity ratio rose from 87.2% to 91.9%. Full-year FY3/2026 guidance is undisclosed.

[Why business moved this way] First, the decisive driver of the profit surge was a 1.97 billion yen unrealized valuation gain on Bitcoin holdings — paper gains from a higher Bitcoin price. Second, the planned 31.5 billion yen capital raise is earmarked for buying more Bitcoin. Third, the legacy electricity retail business has structural weakness.

[Why the stock moved this way] First, Q1 was a positive surprise, but with no full-year guidance and heavy dependence on crypto prices, institutional coverage is thin, and the stock was just 208 yen on May 25, 2026 (-5.88%). Second, the market treats Remixpoint as a leveraged Bitcoin proxy. Third, cryptoassets are held with external custodians, exposing risk from cyber incidents and tighter regulation, and the planned warrant issuance adds dilution concerns."""}

C["3844"] = {"jp": """【会社概要】コムチュアは日本の独立系SIer(システムインテグレーター)。大手・中堅企業向けに、クラウド基盤構築、データ活用、生成AI関連のソリューション開発・運用保守を提供する。SAP、Microsoft、AWS、Google Cloud、Salesforceなどとパートナーシップを持ち、ストック型の運用保守サービスも展開している。

【業績の動き】2026年3月期は連結経常利益が約50億円(+7.3%)となり、14期連続で過去最高益を更新する見通し。Q3累計では売上280.41億円(+4.4%)、営業利益はほぼ横ばい+0.7%。2027年3月期予想は売上420億円(+10.2%)、営業利益47億円(+0.8%)、純利益32.3億円(-1.7%)。年間配当は2026年3月期に前期比2円増の50円(配当性向48.42%)、四半期配当(各回12.5円)に移行。

【なぜ業績がこう動いたのか】第一に、クラウド基盤構築・データ活用・生成AI関連の案件が好調で売上は安定成長を継続。第二に、人材獲得競争激化のなかで昇給・社員数増加・新卒研修費用が増加し、営業利益の伸び率を抑制。第三に、グループ事業連携強化のためのオフィス集約、社員エンゲージメント向上のための全社イベント、新基幹システム導入など、長期競争力強化のための「再投資」コストが先行している。

【なぜ株価がこう動いたのか】第一に、14期連続最高益更新という驚異的な記録にもかかわらず、2026年5月18日の年初来安値1,268円~1月23日の年初来高値1,749円のレンジで推移し、株価は冴えない。投資家コメントでは「自社サービスがない独立系」「将来性に乏しい」との評価が見られ、構造的な低評価要因。第二に、AI・データセンター・量子コンピュータといった派手な成長テーマから外れ、メディア・機関投資家の注目を集めにくい。第三に、配当性向48.42%・累進的増配を続けるインカム特性はあるが、人件費上昇という構造的マージン圧迫リスクが意識されており、グロース投資家もインカム投資家も決定的な買い手とならない状態。""",
"en": """[Company Overview] COMTURE is an independent Japanese SIer, providing cloud-platform construction, data-utilization, and generative-AI solution development plus operational maintenance for large and mid-sized clients. It has partnerships with SAP, Microsoft, AWS, Google Cloud, and Salesforce.

[Business Movement] FY3/2026 consolidated ordinary profit is on track for about 5.0 billion yen (+7.3%), the 14th consecutive year of record profit. Q3 YTD revenue was 28.04 billion yen (+4.4%) with operating profit nearly flat at +0.7%. FY3/2027 guidance: revenue 42.0 billion yen (+10.2%), operating profit 4.7 billion yen (+0.8%), net profit 3.23 billion yen (-1.7%). Annual dividend rises to 50 yen.

[Why business moved this way] First, cloud-platform construction, data-utilization, and generative-AI engagements remained strong. Second, in a tightening talent market, wage hikes, headcount growth, and new-graduate training costs compressed operating-profit growth. Third, reinvestment costs ran ahead of revenue — office consolidation, engagement events, and new core-system rollout.

[Why the stock moved this way] First, despite the remarkable 14-year record-profit streak, the stock stayed range-bound (1,268 yen low on May 18 to 1,749 yen high on Jan 23) with no breakout. Investor commentary often cites lack of in-house products. Second, COMTURE sits outside flashy themes like AI, data centers, quantum computing. Third, while the 48.42% payout ratio creates income appeal, structural wage-inflation margin pressure prevents both growth and income investors from becoming decisive buyers."""}

C["3853"] = {"jp": """【会社概要】アステリアは独立系ソフトウェア企業。主力製品は「ASTERIA Warp」(企業内の異なるシステム間のデータをノーコード/ローコードで連携するEAIミドルウェア、国内シェア19年連続No.1)と「Platio」(現場業務向けノーコードアプリ作成プラットフォーム)。米国子会社アステリア・ビジョン・ファンドI経由でスペースX等のシリコンバレー系スタートアップへの投資事業も行う。

【業績の動き】2026年3月期(IFRS基準)は売上収益33.89億円(+6.9%)、営業利益10.25億円(+31.2%)、当期利益7億円(+35.7%)と大幅増益。営業利益率は30.2%と高水準。ストック型売上比率77%。年間配当は1株当たり9円(前期比+1円)。2027年3月期予想は売上37億円(+9.2%)、営業利益11億円(+7.3%)で、累進配当方針に基づき期末配当を10円(初の2桁)と予想開示。

【なぜ業績がこう動いたのか】第一に、ASTERIA Warpがオンプレミスからクラウドへの移行需要を取り込み、サブスクリプション売上+サポートの継続収益比率が上昇した。第二に、生成AI活用の前提となる「企業内データの統合・連携・整備」需要が急増し、Warpがこの需要を直接取り込んでいる。全製品AI対応の「Asset-hook」戦略も始動。第三に、米国投資事業でスペースX等の評価益が業績に寄与。Asteria Vision Fund I経由のスペースX出資は出資時(2022年1月)の評価額7兆円から、2026年3月にはIPO観測で1兆7,500億ドル(約262兆円)まで37倍以上に拡大。

【なぜ株価がこう動いたのか】第一に、2026年3月25日に米メディア「ジ・インフォメーション」がスペースXのSEC機密申請計画を報じると、アステリア株は単日+22.60%急騰し終値1,519円となった。スペースXのIPO観測がアステリア出資分の評価益期待を引き起こした決定的触媒。第二に、決算発表翌日(5月21日)に2,144円(+19.58%)と大幅高、年初来高値2,753円を5月26日に更新し、3か月で+83.1%(1,216円→2,226円)の急騰。営業利益率30.2%という日本SaaS最上位クラスの収益性が再評価された。第三に、日本円ステーブルコイン「JPYC」(2025年10月発行)との連携でステーブルコイン市場への参入を打ち出し、テーマ性をさらに獲得した。""",
"en": """[Company Overview] Asteria is an independent software company. Its flagship is ASTERIA Warp, no-code / low-code EAI middleware (top market share in Japan for 19 consecutive years), alongside Platio. Via its US subsidiary Asteria Vision Fund I, the company also invests in Silicon Valley startups including SpaceX.

[Business Movement] FY3/2026 (IFRS): revenue 3.389 billion yen (+6.9%), operating profit 1.025 billion yen (+31.2%), net profit 0.7 billion yen (+35.7%). Operating margin: 30.2%. Stock-type revenue share: 77%. Annual dividend: 9 yen (+1 yen YoY). FY3/2027 guidance projects revenue +9.2%, OP +7.3%, with a 10 yen year-end dividend (first double-digit).

[Why business moved this way] First, ASTERIA Warp captured demand for the on-premises-to-cloud transition. Second, demand for the data integration that generative-AI deployment requires surged; the all-product AI Asset-hook strategy also launched. Third, the US investment business contributed valuation gains — the SpaceX stake from January 2022 ballooned to a ~$1.75 trillion valuation on IPO speculation in March 2026, a more-than-37x markup.

[Why the stock moved this way] First, on March 25, 2026, US outlet The Information reported SpaceX's plan to file a confidential SEC submission, and Asteria stock surged +22.60% in a single day to close at 1,519 yen. Second, the day after earnings (May 21), the stock jumped +19.58% to 2,144 yen and hit a YTD high of 2,753 yen on May 26 — a +83.1% three-month surge. Third, integration with the JPYC yen stablecoin (issued October 2025) gave the stock additional thematic exposure."""}

C["3858"] = {"jp": """【会社概要】ユビキタスAI(旧「ユビキタス」)は組み込みソフトウェアのミドルウェア開発企業。IoT機器、自動車、家電などのデバイスに組み込まれる接続性ソフトウェア(TCP/IP、Bluetooth、Wi-Fi等)、セキュリティ製品、組み込みデバイス向けのソフトウェア部品を提供する。社名を「ユビキタスAI」に変更し、エッジAI(端末側で動くAI)事業への戦略的ピボットを進めている。

【業績の動き】2026年3月期は売上39.24億円(-5.2%)、営業損失2.01億円、過去のM&Aで計上した「のれん」の減損損失と構造改革推進により純損失5.18億円。次期も損失計上を見込む。配当は予想0円(無配)、配当利回り0.00%。過去12四半期は業績悪化トレンドが継続。株価は355円(前日比-2.74%)、年初来高値615円(2025年1月8日)、年初来安値277円(2025年4月7日)。

【なぜ業績がこう動いたのか】第一に、過去の企業買収で計上した「のれん」が、買収先業績の悪化により回収不能と判定され、減損損失として一括計上された。第二に、不採算事業の整理と人員見直しという構造改革を進行中で、短期的にはリストラ関連費用が先行している。第三に、組み込みミドルウェア事業の本業自体が-5.2%減収となっており、社名変更で打ち出したエッジAI事業はまだ収益化フェーズに至っていない。

【なぜ株価がこう動いたのか】第一に、過去1ヶ月+1.76%、過去1年でも+3.87%と意外な安定感を示している。これは小型株かつ流動性が薄いため、損失計上にもかかわらず売り手が少なく株価が大きく下げにくい「薄商い」効果。第二に、2025年12月末時点で日本の上場企業の70.5%(2,870社)にアナリストの目標株価予想がない構造があり、ユビキタスAIのような小型株はカバレッジから外れる傾向。第三に、社名変更とAI戦略の明示は短期テーマ性として注目されたが(1月に高値615円)、その後はエッジAI事業の具体的な大型契約や黒字化の兆しが見えず、277円~400円台の薄商いレンジに沈静化している。""",
"en": """[Company Overview] Ubiquitous AI (formerly Ubiquitous) develops embedded-software middleware: connectivity software (TCP/IP, Bluetooth, Wi-Fi) and security products. The company renamed itself Ubiquitous AI to signal a strategic pivot to Edge AI.

[Business Movement] FY3/2026: revenue 3.924 billion yen (-5.2%), operating loss 0.201 billion yen, net loss 0.518 billion yen due to goodwill impairment from past M&A and restructuring costs. Dividend: 0 yen. Stock: 355 yen (-2.74%), YTD high 615 yen, YTD low 277 yen.

[Why business moved this way] First, goodwill from past acquisitions was deemed unrecoverable and a lump-sum impairment was booked. Second, the company is restructuring — cleaning up unprofitable businesses and adjusting headcount. Third, the embedded-middleware core itself shrank 5.2%, and the Edge AI business has not yet reached monetization.

[Why the stock moved this way] First, despite the losses, the stock is oddly stable — the thin float means sellers are also scarce. Second, as of December 2024, 70.5% of all listed Japanese companies (2,870 names) had no analyst price targets, and small-caps like Ubiquitous AI are easily dropped. Third, the name change and AI-strategy signaling drew brief thematic attention (the 615 yen January high), but with no concrete Edge-AI contract wins, the stock settled back into a thin-trading range."""}

C["3908"] = {"jp": """【会社概要】コラボスはコールセンター向けクラウドシステムを主力とする小型SaaS企業(東証グロース上場)。自社開発のクラウド型コールセンターシステム「@nyplace」「COLLABOS PHONE」、AI音声認識を活用した「VLOOM」、マーケティング支援系の「UZ」「GROWCE」「GOLDEN LIST」などを展開。コールセンター業界のDX需要を取り込む位置付け。

【業績の動き】2026年3月期Q3累計は売上12.95億円(-10.1%)、営業利益7,200万円(+44.9%)と「減収増益」の構造。Q2上期は売上8.85億円(前年同期比-9,800万円減)、営業利益5,800万円(+2,100万円増)。Q1で営業利益2,000万円・経常利益2,000万円の黒字転換を達成。25年3月期は経常利益1.02億円の黒字。26年3月期通期予想は経常利益1,700万円(前期比-83.3%、特殊要因剥落後の通常水準への戻り)。前期末配当は見送り、今期配当は未定。株価は344円。

【なぜ業績がこう動いたのか】第一に、AIコールセンターシステム「VLOOM」が売上高+148%の急成長を達成。AI音声認識ニーズの高まりに加え、協業企業や既存顧客からの紹介で新規案件獲得が拡大した。第二に、独自サービス(VLOOM・UZ・GROWCE・GOLDEN LIST)全体で約1.4億円の売上増を見込み、全体売上構成比率は約20%まで上昇する見通し。「@nyplace」の減収を独自サービスで補う構図。第三に、ホスティング等の固定費削減、業務見直し、自動化推進というコスト改善施策で営業利益が黒字転換した。

【なぜ株価がこう動いたのか】第一に、生成AIブームを背景とした「AIコールセンター」テーマの中心銘柄として注目され、2025年に+50%以上の急騰を経験した。VLOOMの+148%急成長というファクトが市場の期待に火を付けた。第二に、東証グロース小型株のため少額の資金流入でも株価が大きく動く構造で、テーマ性を伴う買いが集中しやすい。第三に、Q1黒字転換のサプライズと、上期予想経常利益を800万円から4,000万円へ上方修正したモメンタム転換が市場に印象付けられた。一方で通期経常利益予想1,700万円の絶対水準の低さ、PER111.7倍という高水準、無配方針が継続的な株価上昇の重しとなっている。""",
"en": """[Company Overview] Collabos is a small SaaS company (TSE Growth listed) focused on cloud systems for call centers. Products include @nyplace, COLLABOS PHONE, the AI-voice-recognition-powered VLOOM, and marketing-support products UZ, GROWCE, and GOLDEN LIST.

[Business Movement] FY3/2026 Q3 YTD revenue was 1.295 billion yen (-10.1%) with operating profit 72 million yen (+44.9%) — 'lower revenue, higher profit' pattern. Q1 achieved a return to profit. FY3/2026 full-year ordinary-profit guidance is 17 million yen (-83.3% YoY). Stock was 344 yen.

[Why business moved this way] First, the VLOOM AI call-center system achieved a +148% revenue surge. Second, proprietary services are expected to add about 140 million yen in revenue, lifting their share to roughly 20% and offsetting @nyplace decline. Third, cost-improvement actions pushed operating profit back into the black.

[Why the stock moved this way] First, Collabos became a focal AI-call-center theme play during the generative-AI boom, surging more than +50% in 2025. Second, as a TSE Growth small-cap, small inflows move the stock heavily. Third, the Q1 return-to-profit and the H1 guidance upward revision impressed the market. Offsetting these, the low absolute level of full-year guidance, the high 111.7x forward PER, and no-dividend stance weigh on sustained upside."""}

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
