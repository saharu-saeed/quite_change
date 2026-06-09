# -*- coding: utf-8 -*-
"""Apply IT batch 6 (IT06, 8 entries)."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
IT_PATH = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data\company_research_2025.json")
C = {}

C["4483"] = {"jp": """【会社概要】JMDCは日本最大級の医療ビッグデータ会社。健康保険組合などから匿名化された医療レセプトや健診データを集め、製薬会社のマーケティング、保険会社の引受、医療研究機関などに販売している。さらに遠隔医療プラットフォームも運営。親会社はオムロン(持株比率約50%超、2023年のTOBで連結子会社化)。

【業績の動き】2026年3月期の実績は、Q3累計で売上収益364.88億円(+23.2%)、営業利益77.67億円(+37.1%)と大幅な増収増益。通期会社計画は営業利益115億円(+31.9%)。Q3累計の経常利益は前年比+32%で2期ぶり過去最高更新ペース。2027年3月期の具体的な数値見通しは未確認(UNVERIFIED)。配当利回りは約0.6%と低水準で、成長投資優先の方針。

【なぜ業績がこう動いたのか】第一に、主力のヘルスビッグデータセグメントが+26.4%と高成長したこと。製薬・保険業界からのデータ需要が構造的に拡大しており、契約件数とARPUの両方が伸びている。第二に、データ販売ビジネス特有の高い限界利益率。一度収集したデータをもう1社に売っても追加コストはほぼゼロのため、売上増がそのまま利益増に直結する構造。第三に、遠隔医療事業の収益化進展。オンライン診療の利用拡大で、第二の柱が育ちつつある。

【なぜ株価がこう動いたのか】第一に、期待値ギャップ。Q3進捗率65.0%は5年平均67.1%を下回り、通期見通しもアナリストコンセンサスを若干下回ったため「良い決算だが期待ほどではない」と受け止められた。第二に、オムロンが過半数保有する親子上場構造による流動性・需給の制約。少数株主の自由度が限られ、機関投資家の積極買いが入りにくい。第三に、医療データという特殊ニッチ・セクターのため機関投資家のカバレッジが薄く、長期的にデレーティングが継続している。""",
"en": """[Company Overview] JMDC is one of Japan's largest medical big-data companies. It collects anonymized medical claims and health-checkup data, then sells it to pharma marketing teams, insurance underwriters, and medical research institutions. It also runs a telemedicine platform. Parent company is Omron (over ~50% stake after the 2023 TOB).

[Earnings Movement] FY3/2026 Q3 cumulative: revenue 36.488 billion yen (+23.2%), operating profit 7.767 billion yen (+37.1%). Full-year company guidance is OP 11.5 billion yen (+31.9%). Q3 cumulative ordinary profit is on pace for a record high. Specific FY3/2027 guidance is UNVERIFIED. Dividend yield is only ~0.6%.

[Why earnings moved] First, the flagship Health-Big-Data segment grew +26.4%, driven by structural pharma and insurance demand for data. Second, data-sales has a very high marginal margin: once data is collected, selling it to one more customer costs almost nothing. Third, monetization of the telemedicine business is progressing.

[Why the stock moved] First, the expectation gap. Q3 progress ratio of 65.0% is below the 5-year average of 67.1%, and full-year guidance slightly trailed analyst consensus. Second, the parent-subsidiary listing structure with Omron owning the majority limits free float. Third, medical-data is a specialized niche sector with thin analyst coverage."""}

C["4488"] = {"jp": """【会社概要】AI insideは「DX Suite」というAI-OCR(光学文字認識)クラウドサービスを提供する東証グロース上場企業。紙の書類(請求書、申込書、注文書など)をスキャンすると、AIが文字や数字を読み取り自動で電子データに変換する。日本企業の紙ベース業務をデジタル化するDXニーズに応えるサービス。

【業績の動き】2026年3月期実績は、売上47.47億円(+7.9%)、当期純利益3.51億円で黒字転換を達成(前期は赤字)。DX Suite契約数は約3,105件、ユーザー数約66,812と拡大し、チャーンレート(解約率)は0.59%と極めて低水準。自己資本比率は72.6%に上昇し財務基盤も強化。2027年3月期会社予想は更なる増収増益見込みだが、具体的な数値はUNVERIFIED。配当は無配(成長投資優先)。

【なぜ業績がこう動いたのか】第一に、DX Suiteのライセンス数とユーザー数が継続的に増加。日本企業のペーパーレス・DX需要が構造的に拡大しており、新規顧客獲得が堅調。第二に、チャーンレート0.59%という極めて低い解約率。一度導入すれば既存業務に深く組み込まれるため、解約されにくいSaaS理想形のリテンションを実現。第三に、コスト構造の改善とAI処理エンジンの自社開発による粗利率向上。クラウド配信のため売上が伸びると追加コストが少なく、黒字化の閾値を超えた。

【なぜ株価がこう動いたのか】第一に、黒字転換による再評価期待。ただしFY26は黒字化「初年度」のため、市場が「持続性」を本格的に信じるにはまだ数四半期の継続実績が必要で、本格的な再評価は来ていない。第二に、東証グロース小型株のため機関投資家のカバレッジが薄く、買い手の参入が限定的。第三に、AI-OCR市場でGoogle・Microsoft等のグローバル大手が既存製品に同種機能を組み込み始めており、競合激化への警戒感が株価の上値を抑えている。""",
"en": """[Company Overview] AI inside provides DX Suite, a cloud-based AI-OCR service, listed on the TSE Growth market. Users scan paper documents and the AI automatically reads and converts text/numbers into digital data. The service targets Japan's heavy reliance on paper-based workflows.

[Earnings Movement] FY3/2026 actuals: revenue 4.747 billion yen (+7.9%), net profit 351 million yen — a turn-to-profit (prior year was a loss). DX Suite contracts grew to ~3,105 and users to ~66,812, with churn at an extremely low 0.59%. Equity ratio rose to 72.6%. FY3/2027 guidance projects further growth, specific figures UNVERIFIED. No dividend.

[Why earnings moved] First, DX Suite license count and user count keep rising as Japanese corporate paperless / DX demand expands structurally. Second, churn at 0.59% is exceptionally low — textbook SaaS retention. Third, cost structure improved and the in-house AI processing engine lifted gross margin.

[Why the stock moved] First, re-rating hopes from the turn-to-profit. But FY26 is the 'first year' of profitability. Second, as a TSE Growth small-cap, analyst coverage is thin. Third, in the AI-OCR market, global giants Google and Microsoft are embedding similar OCR features, and the competitive threat caps the upside."""}

C["4490"] = {"jp": """【会社概要】※入力ファイルでは「Visional」とされていたが、証券コード4490の実際の発行企業はビザスク(VisasQ)であることを確認した(Visionalの正式コードは4194)。ビザスクはスポットコンサル(単発の専門家相談)マッチングのプラットフォーム企業。企業が特定分野の知見を持つエキスパートに1時間単位でアドバイスを求められるサービスを国内No.1で運営し、2021年に米国Coleman Research Groupを買収し海外展開している。

【業績の動き】2026年2月期Q3累計で営業利益は前年比+12.1%、進捗率87.1%と通期計画達成軌道。経常利益は9.01億円。一方Q2単独は営業収益47.74億円(-3.3%)、営業利益4.99億円(-14.2%)と苦戦。通期会社計画は営業利益10.3億円(-16.1%)で「増収減益」を見込む。2026年4月にはコールマンに関連したソフトウェア開発コストの減損損失(特別損失)を追加計上。配当は無配。

【なぜ業績がこう動いたのか】第一に、国内スポットコンサル事業は底堅いものの、米国Coleman事業の業績低迷が継続。買収以降、米M&A市場の冷却で需要が減少し、繰り返し減損損失を計上。第二に、Q3の利益改善は短期的なコスト管理(販管費抑制)の効果が主因で、トップライン成長による構造的改善ではない。第三に、成長投資(プロダクト開発・営業強化)を継続しているため、減収局面でも利益が圧迫されやすい体質。

【なぜ株価がこう動いたのか】第一に、Coleman買収(約100億円)後の累計144億円規模の減損損失と特別損失の歴史。自己資本が大きく毀損し、投資家の信頼回復に時間がかかっている。第二に、2026年4月の追加減損損失計上で「のれんリスクが終わっていない」ことが再確認され、上値が重い。第三に、スポットコンサルというビジネスモデル自体が労働集約的(人を人にマッチングする)ため、純粋SaaSのような高利益率に到達できず、グロース株としての評価倍率が伸びにくい構造的問題が続く。""",
"en": """[Company Overview] Note: the input file labels 4490 as 'Visional,' but the actual issuer of ticker 4490 is VisasQ — Visional's correct ticker is 4194. VisasQ runs Japan's leading spot-consulting marketplace, matching companies with subject-matter experts for hourly advisory calls. In 2021 it acquired US-based Coleman Research Group as the foundation for overseas expansion.

[Earnings Movement] FY2/2026 Q3 cumulative: operating profit +12.1% YoY, with progress vs. full-year plan at 87.1% — on track. Ordinary profit was 901 million yen. But Q2 standalone was weak: revenue 4.774 billion yen (-3.3%), OP 499 million yen (-14.2%). Full-year company guidance projects OP of 1.03 billion yen (-16.1%) — 'revenue up, profit down.' In April 2026, an additional impairment loss on Coleman-related software-development costs was booked as a special loss. No dividend.

[Why earnings moved] First, domestic spot-consulting is steady, but US Coleman continues to drag. Second, the Q3 profit improvement came mainly from short-term cost control. Third, continued growth investment makes profits easy to compress.

[Why the stock moved] First, the legacy of the ~10 billion yen Coleman acquisition and the subsequent cumulative ~14.4 billion yen impairment loss / special loss. Second, the April 2026 additional impairment confirmed that 'goodwill risk isn't over.' Third, the spot-consulting business model is inherently labor-intensive, so it can't reach pure-SaaS-like margins."""}

C["4676"] = {"jp": """【会社概要】フジ・メディア・ホールディングスはフジテレビを中核とする大手メディア・コングロマリット。テレビ放送(フジテレビ系列)、配信(FOD)、新聞(産経新聞)、出版、不動産(都市開発・台場本社ビル等)、観光(グランビスタホテル&リゾート、神戸須磨シーワールド等)を傘下に持つ。

【業績の動き】2026年3月期実績は、売上5,518.65億円(+0.2%)と微増ながら、営業損失87.66億円・経常損失28.07億円と上場来初の営業赤字に転落。一方、当期純利益は資産売却益等の特別利益で64.99億円。FY27会社予想は売上6,257億円(+13.4%)、営業利益401億円、経常利益383億円、純利益261億円と大幅V字回復見通し。FY26配当は125円、FY27予想配当は200円(配当性向50%目途)と大幅増配。約2,350億円規模の自己株取得も実施。

【なぜ業績がこう動いたのか】第一に、2025年初頭から続いた中居正広氏とフジテレビをめぐる事案の影響で、Q4にスポンサーの広告出稿停止が拡大しメディア・コンテンツ事業の広告収入が急減。第二に、グランビスタが神戸須磨シーワールド開業効果と過去最高のインバウンド需要で都市開発・観光事業の利益を押し上げ、放送赤字の一部を吸収。第三に、不動産・有価証券売却益等の特別利益計上により、本業赤字でも最終利益は黒字を確保した。

【なぜ株価がこう動いたのか】第一に、アクティビスト圧力。ダルトン・インベストメンツ(保有率7.51%)やSBIホールディングス(4月20日に6.20%→7.10%に増加)等が経営改革・株主還元拡大を要求し、コーポレートアクション期待が株価を押し上げた。第二に、保有不動産(台場本社ビル等)のSOTP(部分価値合計)評価で含み益が大きく、企業価値再評価が見込まれる。第三に、2,350億円の自社株買いと配当200円方針による株主還元拡大が需給を改善。ただしダルトン側はこの自社株買いを「愚策」と批判するなど、ガバナンス論争は続いている。""",
"en": """[Company Overview] Fuji Media Holdings is a major Japanese media conglomerate centered on Fuji TV. Under its umbrella: TV broadcasting, streaming (FOD), newspapers (Sankei Shimbun), publishing, real estate (Odaiba HQ building), and tourism (Granvista Hotels, Kobe Suma Sea World).

[Earnings Movement] FY3/2026 actuals: revenue 551.865 billion yen (+0.2%), operating LOSS 8.766 billion yen, ordinary LOSS 2.807 billion yen — the first operating loss in company history. But net profit was 6.499 billion yen on extraordinary gains. FY27 guidance: revenue 625.7 billion (+13.4%), OP 40.1 billion, ordinary 38.3 billion, net 26.1 billion — a major V-shape recovery. FY26 dividend 125 yen; FY27 planned dividend 200 yen — large hike. Also a roughly 235 billion yen share buyback was executed.

[Why earnings moved] First, fallout from the early-2025 Masahiro Nakai / Fuji TV scandal escalated in Q4 as sponsors paused ad spending. Second, Granvista beat targets thanks to Kobe Suma Sea World launch and record-high inbound demand. Third, extraordinary gains from real-estate and securities sales kept net profit positive.

[Why the stock moved] First, activist pressure: Dalton Investments (7.51%) and SBI Holdings (raised stake to 7.10% on April 20) demand governance reform. Second, hidden asset value: SOTP for owned real estate implies significant upside. Third, the 235 billion yen buyback plus 200 yen dividend plan improved supply-demand. But Dalton called the buyback 'foolish' — governance battles continue."""}

C["4686"] = {"jp": """【会社概要】ジャストシステムは「一太郎」「ATOK」で知られる京都本拠の老舗ソフトウェア企業。現在の利益の主力は個人向けタブレット通信教育サービス「スマイルゼミ」(小中高生向け月額課金)と、法人向けクラウドサービス「JUST.SCHOOL」「JUST.DBクラウド」等のサブスクリプション事業。キーエンスが筆頭株主で資本業務提携を結ぶ。

【業績の動き】2026年3月期実績は、売上515.15億円(+15.6%)、営業利益224.92億円(+24.7%)、経常利益231.01億円(+27.2%、3期ぶり過去最高)、純利益150.92億円(+22.4%)。営業利益率43.7%と業界トップ水準。法人事業は+37.7%と高成長。サブスクリプション売上は全社の71.4%、継続課金売上は約74%を占める。配当はFY26 27円(+5円増配)、FY27予想30円(+3円増配)と4期連続増配方針。FY27の具体的な売上・利益予想は会社が非開示。

【なぜ業績がこう動いたのか】第一に、スマイルゼミの会員数とARPUが継続拡大。文部科学省のGIGAスクール構想と教育デジタル化トレンドが追い風。第二に、法人事業(自治体・教育委員会向けクラウド)の+37.7%という高成長。教育機関のクラウド移行ニーズが顕在化。第三に、プラットフォーム型ビジネス特有の高い限界利益率。一度開発したコンテンツ・学習エンジンの追加顧客への提供コストが極めて低く、売上増がそのまま利益増に直結。

【なぜ株価がこう動いたのか】第一に、営業利益率43.7%という業界トップ水準が機関投資家に「クオリティ・グロース」銘柄として再評価された。米SaaS優良企業に匹敵する利益率を構造的に維持できる点が評価される。第二に、4期連続増配方針による株主還元強化がインカム志向の機関投資家を呼び込んだ。第三に、FY27ガイダンス非開示が「保守的にしか言えないだけで弱気ではない」と解釈され、安心感を生んだ。キーエンスとの資本業務提携も経営改革加速期待材料。""",
"en": """[Company Overview] JustSystems is a Kyoto-based veteran software company known for 'Ichitaro' word processor and 'ATOK.' The current profit driver is Smile Zemi — a subscription tablet-based distance-learning service for elementary-through-high-school students — plus corporate cloud subscriptions. Keyence is the top shareholder via a capital and business alliance.

[Earnings Movement] FY3/2026 actuals: revenue 51.515 billion yen (+15.6%), OP 22.492 billion (+24.7%), ordinary 23.101 billion (+27.2% — first record in 3 years), net 15.092 billion (+22.4%). Operating margin 43.7% is top-tier. Corporate business +37.7%. Subscription revenue is 71.4% of total. Dividend FY26 27 yen (+5 yen); FY27 plan 30 yen (+3 yen) — 4 consecutive years of hikes. FY27 specific guidance is not disclosed.

[Why earnings moved] First, Smile Zemi keeps growing subscribers and ARPU, aided by MEXT GIGA-School program. Second, the Corporate business grew +37.7% as cloud-migration demand from educational institutions accelerated. Third, the high marginal margin of a platform business.

[Why the stock moved] First, the 43.7% operating margin earned re-rating as a 'quality growth' name. Second, 4 consecutive years of dividend hikes attract income-oriented institutional buyers. Third, the non-disclosure of FY27 guidance is read as 'just conservative — not bearish.'"""}

C["4689"] = {"jp": """【会社概要】LINEヤフー(LY Corporation)は2021年にヤフージャパンとLINEが経営統合して誕生した日本最大級のインターネット企業。検索エンジン「Yahoo! JAPAN」、メッセージアプリ「LINE」、eコマース(「Yahoo!ショッピング」「ZOZOTOWN」)、決済(「PayPay」)、ニュース、エンタメ等、日本のインターネット生活の中核サービスを多数運営。ソフトバンクGとNAVER(韓国)が共同支配株主。

【業績の動き】2026年3月期実績は、売上収益2兆363億円(+6.2%)、調整後EBITDA 4,966億円(+5.5%)と過去最高更新。連結最終利益は前年比+26.2%の1,936億円で、3期ぶり過去最高益。戦略事業(PayPay連結+LINE Bank Taiwan等)が+30.6%、調整後EBITDA+85.0%と大幅成長。FY27会社予想は売上2兆2,400億円(+10.0%)、調整後EBITDA 5,850億円(+17.8%)、調整後EPS 30円(+4.4%)。

【なぜ業績がこう動いたのか】第一に、PayPayの連結化と決済・金融サービスの収益化進展。決済GMV拡大とLINEヤフー経済圏(IDの相互連携)のシナジーが収益に転換し始めた。第二に、コマース事業のテイクレート改善と広告事業の単価上昇。Yahoo!ショッピングとZOZOTOWNの統合運用が効率を高めた。第三に、LINE Bank Taiwan等のアジア金融子会社の連結化と成長。一方、メディア事業の検索広告は、AI検索台頭の影響で売上が一部減少した。

【なぜ株価がこう動いたのか】第一に、過去最高益でも市場期待には届かず、税引前利益はIFISコンセンサスを-10.4%下回ったため失望売り。第二に、2021年LINE統合時の大量新株発行(約28億株、60%希薄化)の影響が継続し、EPSが伸びにくい構造。ROEは依然5%台と低水準。第三に、AI検索(ChatGPT・Perplexity等)の台頭による検索広告ビジネスへの構造的脅威。Yahoo! 検索のシェア低下懸念とAIシフトに伴う広告枠減少が長期成長期待を抑えている。情報漏洩問題の信頼失墜も尾を引く。""",
"en": """[Company Overview] LY Corporation (LINE Yahoo) is one of Japan's largest internet companies, formed in 2021 by merging Yahoo Japan and LINE. It runs many core internet services: Yahoo! JAPAN search, the LINE messaging app, e-commerce (Yahoo! Shopping, ZOZOTOWN), payments (PayPay), news, and entertainment. SoftBank Group and Korea's NAVER are co-controlling shareholders.

[Earnings Movement] FY3/2026 actuals: revenue 2,036.3 billion yen (+6.2%), adjusted EBITDA 496.6 billion yen (+5.5%) — both record highs. Consolidated net profit 193.6 billion yen (+26.2%) — first record high in 3 years. Strategic Business grew +30.6% revenue and +85.0% adjusted EBITDA. FY27 guidance: revenue 2,240 billion yen (+10.0%), adjusted EBITDA 585 billion yen (+17.8%), adjusted EPS 30 yen (+4.4%).

[Why earnings moved] First, PayPay consolidation and monetization of payment / financial services progressed. Second, the Commerce business improved take rates and the Ads business raised unit prices. Third, the Asian financial subsidiaries consolidation and growth helped. On the negative side, Media-segment search ads partly declined as AI search rose.

[Why the stock moved] First, despite record-high profit, results disappointed: pretax profit missed IFIS consensus by -10.4%. Second, the 2021 LINE merger issued ~2.8 billion new shares (~60% dilution), and ROE remains in the 5% range. Third, AI search is a structural threat to the search-ad business."""}

C["4704"] = {"jp": """【会社概要】トレンドマイクロは日本発のグローバル・サイバーセキュリティ大手。個人向け・法人向けにウイルス対策、エンドポイント(PC・スマホ)セキュリティ、クラウドセキュリティ、AI活用次世代SOC(Security Operations Center)等の製品を世界中で販売。売上の約7割が海外という日本企業として珍しい高グローバル展開度を持つ。

【業績の動き】2025年12月期実績は、売上2,759億円(+1.2%)、営業利益577億円(+20.1%)、純利益345億円(+0.5%)。AI活用次世代SOC関連が成長を牽引し、費用抑制で営業利益は大幅増。自己資本比率も改善。2026年12月期予想は、売上3,015億円(+9.2%)、営業利益564億円(-2.4%)、経常利益551億円(+2.1%)、純利益366億円(+6.0%)。増収だが費用増で営業利益は微減見通し。

【なぜ業績がこう動いたのか】第一に、AI活用次世代SOC関連製品(AI-SOC、XDR等)の高成長。生成AIを使ったフィッシング・ディープフェイク詐欺等の新型脅威増加で、企業のセキュリティ支出が拡大している。第二に、徹底した費用抑制が営業利益+20.1%を実現。グローバル組織の最適化と販管費の選別投資が効いた。第三に、FY26は次世代製品開発・AI投資の拡大局面に入るため、コスト先行で営業利益は一時的に減益見通し。

【なぜ株価がこう動いたのか】第一に、2026年6月5日にAIミュトス活用開始の発表をきっかけに半年ぶり高値(6,900円・+10.84%)を更新。生成AIによる脅威分析強化が好感された。第二に、米国競合(CrowdStrike、SentinelOne、Palo Alto Networks等)に対するAI統合差別化への期待。日本発のグローバル企業として再評価されつつある。第三に、サイバー攻撃の頻発と為替動向(円安局面で海外売上が円換算で押し上げられる)に株価が連動する構造。FY26の営業減益見通しが上値を一定程度抑えている。""",
"en": """[Company Overview] Trend Micro is a Japan-headquartered global cybersecurity major selling antivirus, endpoint security, cloud security, and AI-powered next-gen SOC products worldwide. About 70% of revenue is overseas — an unusually international profile for a Japanese company.

[Earnings Movement] FY12/2025 actuals: revenue 275.9 billion yen (+1.2%), OP 57.7 billion yen (+20.1%), net profit 34.5 billion yen (+0.5%). AI-powered next-gen SOC products drove growth, and cost discipline lifted OP sharply. FY12/2026 guidance: revenue 301.5 billion (+9.2%), OP 56.4 billion (-2.4%), ordinary 55.1 billion (+2.1%), net 36.6 billion (+6.0%).

[Why earnings moved] First, high growth in AI-powered next-gen SOC products — new generative-AI-era threats are pushing enterprise security spending higher. Second, disciplined cost control delivered the +20.1% OP jump. Third, FY26 enters a phase of expanded next-gen product development and AI investment.

[Why the stock moved] First, on June 5, 2026, an announcement on AI Mythos utilization triggered a half-year-high close (6,900 yen, +10.84%). Second, expectations of AI-integration differentiation versus US peers (CrowdStrike, SentinelOne, Palo Alto Networks). Third, the stock follows two macro factors: cyberattack news frequency and FX (a weaker yen boosts yen-translated overseas revenue)."""}

C["4722"] = {"jp": """【会社概要】フューチャー(旧フューチャーアーキテクト)は「IT × 経営コンサルティング」を融合させた独立系IT戦略コンサル企業。大手金融機関の次世代バンキングシステム、流通・小売の基幹システム再構築、製造業のサプライチェーンDX等、大型・上流案件を得意とする。子会社のリヴァンプとのシナジーで経営改革支援領域も強化。「Future AI」「Future IoT」等のAI・IoT活用コンサルも提供。

【業績の動き】2025年12月期実績は、売上759.93億円(+8.8%)、営業利益161.76億円(+10.3%)、純利益117億円(+13.5%)。6期連続増収、3期連続増益を達成し営業利益率は21.3%と業界トップ水準。FY26予想は売上806億円(+6.1%)、営業利益175億円(+8.2%)、純利益118億円(+0.7%)と引き続き増収増益見通し。配当はFY25実績46円→FY26予想48円(連結配当性向36.1%目途)と継続増配。

【なぜ業績がこう動いたのか】第一に、ITコンサル&サービス事業の好調。次世代バンキングシステム等の大型・上流案件が積み上がり、自社知財(フレームワーク・リファレンスアーキテクチャ等)を活用した高単価案件の比率が上昇。第二に、子会社リヴァンプとのクロスセル(経営コンサル × DXの組み合わせ提案)が機能し、顧客内シェア拡大。第三に、生成AI活用による生産性向上と新サービス(Future AI)展開で、限られたITエンジニアリソースから高い付加価値を生み出せた。

【なぜ株価がこう動いたのか】第一に、営業利益率21.3%という業界トップ水準(SI業界平均7-9%を大きく上回る)が「単なるSIではなく上流コンサルで稼ぐ」差別化ビジネスモデルとして機関投資家に再評価された。第二に、6期連続増収・3期連続増益の質の高い成長実績がクオリティ・グロース銘柄として認識され、長期投資家の買いを集めた。第三に、生成AI戦略の明確化でAIテーマ銘柄の一角としても評価された。継続増配方針も需給を改善。""",
"en": """[Company Overview] Future Corp (formerly Future Architect) is an independent IT-strategy consulting firm fusing 'IT × management consulting.' It specializes in large upstream projects: next-generation banking systems, retail core-system rebuilds, supply-chain DX. Subsidiary Revamp Inc. strengthens management-reform consulting through synergies.

[Earnings Movement] FY12/2025 actuals: revenue 75.993 billion yen (+8.8%), OP 16.176 billion (+10.3%), net 11.7 billion (+13.5%). 6 consecutive years of revenue growth, 3 consecutive years of profit growth, OP margin 21.3% — top-tier. FY26 guidance: revenue 80.6 billion (+6.1%), OP 17.5 billion (+8.2%), net 11.8 billion (+0.7%). Dividend FY25 actual 46 yen → FY26 plan 48 yen.

[Why earnings moved] First, strong IT Consulting & Services — large upstream projects accumulated, and the share of high-day-rate engagements leveraging proprietary IP rose. Second, cross-sell with subsidiary Revamp worked. Third, generative-AI-driven internal productivity gains and the new Future AI service line extracted higher value-add.

[Why the stock moved] First, the 21.3% operating margin — well above the SI-industry average of 7-9% — was repriced. Second, the 6-year revenue / 3-year profit growth streak earned recognition as a 'quality growth' name. Third, the generative-AI strategy placed it within the AI-theme stock universe."""}

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
