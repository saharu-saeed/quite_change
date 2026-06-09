# -*- coding: utf-8 -*-
"""Apply IT batches 9-11 (IT09 telco + IT10 internet + IT11 media, 20 entries)."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
IT_PATH = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data\company_research_2025.json")
C = {}

# IT09 telco/broadcasters
C["9401"] = {"jp": """**会社概要** TBSホールディングスは地上波放送(TBSテレビ)を中核に、メディア・コンテンツ(配信、映画、音楽、アニメ)、ライフスタイル(物販)、不動産(赤坂エリアの大型ビル群)、生活情報サービスを持つ総合メディア企業。長年「日曜劇場」「半沢直樹」「VIVANT」など強いドラマ枠を持ち、近年は配信(TVer、TBS NEWS DIG)とコンテンツIPで再評価されている。

**業績の動き** 2026年3月期は売上高4,248.5億円(+4.5%)、営業利益247.5億円(+27.1%)、経常利益373.7億円(+18.3%)、当期純利益522.2億円(+18.9%)で過去最高益。配当は2026年3月期年84円(中間35円、期末49円)、2027年3月期は年100円(中間50円、期末50円)へ大幅増配予定、配当性向は約40%を目処に引き上げる方針。

**なぜ業績がこう動いたのか** ①TBSテレビのスポット広告が、ヒットドラマ枠の高視聴率を背景に単価を維持し増収。②TVerなど配信プラットフォームの配信広告収入が二桁成長し、地上波の構造減少を補った。③ライフスタイル事業のStylingLifeブランドや、教育事業のYARUKIスイッチグループなどグループ会社の利益貢献が積み上がり、メディア外収益が利益率改善に寄与した。

**なぜ株価がこう動いたのか** ①過去最高益達成と、2027年3月期年100円への増配・配当性向40%目処の明確なガイダンスがインカム志向の機関・個人投資家を引きつけた。②赤坂本社周辺の大規模不動産の含み益と、「赤坂エンタテインメント・シティ」再開発期待がSOTPでの割安感を意識させ、アクティビスト含む機関投資家の関心を集めた。③東証PBR1倍割れ是正要請を受け、自社株買い・政策保有株縮減・IR強化を進めたことで、「放送局」から「グロース志向メディア企業」への再評価が進行。""",
"en": """**Company overview** TBS Holdings is an integrated media group centered on TBS Television, with Media & Content, Lifestyle, Real Estate (Akasaka), and lifestyle-information services. Strong drama franchises (Sunday Theater, Hanzawa Naoki, VIVANT); being re-rated on streaming (TVer, TBS NEWS DIG) and content IP.

**Earnings movement** FY3/2026 revenue ¥424.85B (+4.5%), OP ¥24.75B (+27.1%), ordinary ¥37.37B (+18.3%), net ¥52.22B (+18.9%) — record high. Dividend ¥84 in FY3/2026, ¥100 planned for FY3/2027, with payout ratio targeted around 40%.

**Why earnings moved this way** 1) TBS TV spot ad revenue held unit prices firm on high-rated drama slots. 2) Streaming ad revenue on TVer grew double-digit. 3) Lifestyle (StylingLife) and education (YARUKI Switch) added non-media profit.

**Why the stock moved this way** 1) Record earnings + FY27 ¥100 / 40% payout ratio guidance pulled in income-oriented investors. 2) Akasaka HQ real-estate hidden gains + Akasaka Entertainment City redevelopment surfaced SOTP undervaluation thesis. 3) TSE PBR-improvement response — buybacks, cross-shareholding reductions, IR strengthening drove re-rating from broadcaster toward growth media company."""}

C["9404"] = {"jp": """**会社概要** 日本テレビホールディングス(日テレHD)は地上波放送(日本テレビ)を中核に、配信(Hulu Japan、TVer)、映画・アニメ製作、不動産(汐留タワー)、生命保険、スポーツ事業を持つ大手メディア企業。2023年9月にスタジオジブリを子会社化(株式42.3%取得)し、コンテンツカンパニーとしての性格を強めた。

**業績の動き** 2026年3月期は売上高4,844億円(+4.9%)、営業利益693億円(+26.2%)、純利益567億円(+23.4%)と過去最高水準。第1四半期は売上1,146.5億円(+8.1%)、営業利益174.8億円(+52.8%)で好スタート。配当は年45円(前期比+5円)。2027年3月期予想は売上5,350億円(+10.4%)、営業利益490億円(-29.3%)と先行投資で減益見通し。

**なぜ業績がこう動いたのか** ①スポット広告とデジタル広告の好調で広告収入が伸長。②コンテンツ制作・興行収入が拡大。舞台「となりのトトロ」「久石譲コンサート2025」「ジブリの立体造型物展」など、ジブリ関連イベントが好調で興行収入は前期比+23億円(+14.7%)。③Hulu日本版の収益拡大、ドラマ・映画の海外配信権販売、コンテンツライセンスの寄与も加わり、利益率が拡大した。

**なぜ株価がこう動いたのか** ①記録的な業績(過去最高益、Q1営業利益+52.8%)と「グローバルコンテンツ企業への変革」中期戦略が、放送株ではなくIPホルダーとしての評価軸に移行。②ジブリIPの長期キャッシュ価値が再評価され続け、ジブリ子会社化以降の構造的な株価押し上げ要因。③汐留タワー等の不動産含み益によるSOTPでの割安感が下支え。一方、2027年3月期の-29.3%減益ガイダンスは先行投資要因と市場が認識し、株価は底堅く推移。""",
"en": """**Company overview** Nippon Television Holdings (NTV HD) is a major media group centered on terrestrial broadcasting, with streaming (Hulu Japan, TVer), film/anime production, real estate (Shiodome Tower), life insurance, and sports. Acquired Studio Ghibli (42.3% stake) in September 2023.

**Earnings movement** FY3/2026: revenue ¥484.4B (+4.9%), OP ¥69.3B (+26.2%), net ¥56.7B (+23.4%) — record-high. Q1 revenue ¥114.65B (+8.1%), OP ¥17.48B (+52.8%). Dividend ¥45/share (+¥5 YoY). FY3/2027 guidance: revenue ¥535B (+10.4%), OP ¥49B (-29.3%) — profit decline from upfront investment.

**Why earnings moved this way** 1) Spot ads and digital ads both strong. 2) Content production and live-event revenue expanded — Ghibli-related events were hits, lifting event revenue by ¥2.3B (+14.7%). 3) Hulu Japan growth, overseas distribution, and content licensing widened margins.

**Why the stock moved this way** 1) Record earnings + 'transformation into a global content company' pushed the market to evaluate NTV as an IP-holder rather than broadcaster. 2) Long-term cash-flow value of Ghibli IP continued to be re-rated. 3) Hidden real-estate gains at Shiodome Tower support an SOTP undervaluation case."""}

C["9409"] = {"jp": """**会社概要** テレビ朝日ホールディングスは地上波放送(テレビ朝日)を中核に、インターネット(配信、TVer、TELASA)、不動産(六本木周辺)、ショッピング(ROBOT)、映画製作、音楽出版を持つ大手メディア企業。「相棒」「ドクターX」「ザ! 鉄腕! DASH!!」等の長寿ヒット番組を保有。

**業績の動き** 2026年3月期は売上高3,394.9億円(+4.8%)、営業利益261.8億円(+32.9%)で過去最高益。上期単独は売上2,543.9億円(+6.9%)、営業利益231.9億円(+76.8%)と上期で通期計画の大半を達成。配当は年100円(前期比+30円)、中間30円+期末40円(うち特別配当10円)。2027年3月期は「東京ドリームパーク」開業に伴う先行費用で減益予想。

**なぜ業績がこう動いたのか** ①スポット広告の単価維持+需要回復が中核ドライバー、上期スポット収入は+17.8%と非常に強い。②インターネット事業(配信)が高成長 — TELASAの「相棒」「ドクターX」など独自IPで差別化、TVer配信広告も拡大、上期ネット事業売上+18.7%。③番組制作費の効率化と固定費抑制が利益率を押し上げ、上期営業利益+76.8%という大幅増益につながった。

**なぜ株価がこう動いたのか** ①過去最高益達成と上期での通期計画大幅前倒し達成という「クリーンな良い決算」が、機関投資家のサプライズ買いを誘発した。②増配 — 年配当を70円→100円(+30円)へ大幅増額する明確なガイダンス。③テレビ朝日が出資参画する大型エンタテインメント施設「東京ドリームパーク」開業期待 — 放送業の構造減少を補う新規収益源として高く評価された。""",
"en": """**Company overview** TV Asahi Holdings is a major media group centered on TV Asahi, with Internet (streaming, TVer, TELASA), real estate (Roppongi), shopping (ROBOT), film production, and music publishing. Owns long-lived hit shows.

**Earnings movement** FY3/2026 revenue ¥339.49B (+4.8%), OP ¥26.18B (+32.9%) — record-high OP. H1 alone revenue ¥254.39B (+6.9%), OP ¥23.19B (+76.8%). Dividend ¥100/share (+¥30 YoY). FY3/2027 guided for profit decline due to upfront Tokyo Dream Park opening costs.

**Why earnings moved this way** 1) Spot ad unit prices firm + demand recovery; H1 spot revenue +17.8%. 2) Internet (streaming) grew sharply — TELASA differentiated with proprietary IP, H1 Internet business revenue +18.7%. 3) Production-cost efficiency lifted margins.

**Why the stock moved this way** 1) Record earnings + H1 print nearly fulfilling full-year plan triggered institutional buying. 2) Dividend hike from ¥70 to ¥100 gave income investors a clear yield-improvement catalyst. 3) Tokyo Dream Park (planned FY3/2027 opening) is highly valued as a new revenue stream."""}

C["9412"] = {"jp": """**会社概要** スカパーJSATホールディングスは「宇宙事業(衛星通信・放送、衛星画像、防衛向け宇宙インテリジェンス)」と「メディア事業(スカパー!有料多チャンネル放送、Wowowなど)」の二本柱を持つ、アジア最大規模の衛星オペレーター。

**業績の動き** 2026年3月期は営業収益1,275.8億円(+3.1%)、営業利益352.7億円(+28.3%)、当期純利益233.1億円(+22.0%)で過去最高益。配当は年27円→42円へ大幅増配、2027年3月期予想は48円。2027年3月期予想は売上1,350億円(+5.8%)、営業利益390億円(+10.6%)、純利益270億円(+15.8%)と4期連続最高益更新を見込む。

**なぜ業績がこう動いたのか** ①宇宙事業の伸長 — 売上698億円(+7.9%)、国内衛星通信需要に加え、防衛省の衛星コンステレーション事業の受注、スペースインテリジェンス(衛星画像解析)が貢献。②メディア事業のコスト削減効果 — 売上643億円(-1.9%)と微減ながら、放送オペレーション最適化と費用抑制でセグメント利益+74.3%と大幅改善。③スペースインテリジェンスなど新規領域の収益拡大が利益率改善を後押し。

**なぜ株価がこう動いたのか** ①防衛・安全保障テーマでの再評価 — 防衛省衛星コンステレーション受注という具体的な政府関連案件を持つ稀少な民間企業として、政府の防衛費GDP比2%引き上げ方針の追い風。②過去最高益・修正予想超過・連続増益という「クリーンな決算」が機関投資家の買いを誘発、岡三証券が目標株価を2,600円→4,200円に引き上げ。③大幅増配と3年間で計2,200億円の投資計画(低軌道衛星10機含む)による中長期成長期待。過去1年でスカパーJSAT株は+248.96%の上昇という極めて大きな再評価が進んだ。""",
"en": """**Company overview** SKY Perfect JSAT Holdings is Asia's largest satellite operator, with two pillars: Space (satellite comms/broadcasting, satellite imagery, defense-related space intelligence) and Media (SKY PerfecTV! pay-TV, Wowow).

**Earnings movement** FY3/2026: revenue ¥127.58B (+3.1%), OP ¥35.27B (+28.3%), net ¥23.31B (+22.0%) — record-high. Dividend lifted from ¥27 to ¥42, FY3/2027 guided ¥48. FY3/2027 guidance: revenue ¥135B (+5.8%), OP ¥39B (+10.6%), NP ¥27B (+15.8%) — 4th consecutive record-high.

**Why earnings moved this way** 1) Space business grew — revenue ¥69.8B (+7.9%) on Defense Ministry satellite-constellation contract and Space Intelligence growth. 2) Media business cost cuts drove segment profit +74.3%. 3) Space Intelligence new revenue widened margins.

**Why the stock moved this way** 1) Re-rating on defense/national-security themes. 2) Record-high earnings and consecutive growth — Okasan raised target from ¥2,600 to ¥4,200. 3) Large dividend hike + 3-year ¥220B investment plan. Stock has risen +248.96% over the past year — very large re-rating."""}

C["9413"] = {"jp": """**会社概要** テレビ東京ホールディングスは地上波放送(テレビ東京)を中核に、アニメ・配信事業(海外含む)、コンテンツ販売、BSテレ東(衛星放送)、出版、ライセンス事業を持つコンテンツ志向の強い大手メディア企業。「NARUTO」「BORUTO」「ポケットモンスター」「鬼滅の刃」「SPY×FAMILY」「孤独のグルメ」等のIPを保有。

**業績の動き** 2026年3月期は売上高1,649.15億円(+5.8%)、営業利益114.02億円(+46.4%)、純利益77億円(+27.61%)で過去最高益更新。期中に営業利益予想を90億円→110億円へ上方修正。配当は前期90円→100円(中間15円+期末85円)へ増配、配当性向34.6%見込み。自己資本比率68.9%と財務健全。

**なぜ業績がこう動いたのか** ①アニメ・配信事業の海外売上拡大 — 「NARUTO/BORUTO」海外スマホゲームのアプリライツ収入が好調でセグメント利益約1.5倍、「BLEACH」の中国・欧州ゲーム収入も伸長。②放送事業のスポットCM単価引き上げが奏功。③Crunchyroll、Netflix、Prime Video等のグローバルプラットフォーム向け配信権販売、コンテンツライセンスがストック型収益として積み上がり、利益率が大幅改善。

**なぜ株価がこう動いたのか** ①期中の上方修正(営業利益90億→110億)と過去最高益更新で、市場は「放送局」ではなく「コンテンツライツホルダー」としての評価軸に移行。②長寿アニメIPによる10年・20年単位のロイヤルティ収益はストック型キャッシュフローとして再評価され、海外配信プラットフォームの台頭で「売り手市場」のメリットを享受。③増配と東証PBR改善要請への対応で個人・機関の両方から買いが入った。他キー局比でコンテンツ・ライセンス収益比率が高く、広告市況に左右されにくい安定成長業態として、PBR1.12倍水準でも再評価が継続。""",
"en": """**Company overview** TV Tokyo Holdings is a content-oriented major media group centered on TV Tokyo, with anime/distribution, content sales, BS TV Tokyo, publishing, and licensing. Key IP includes Naruto, Boruto, Pokémon, Demon Slayer, Spy x Family, Solitary Gourmet.

**Earnings movement** FY3/2026: revenue ¥164.92B (+5.8%), OP ¥11.40B (+46.4%), net ¥7.7B (+27.61%) — record. Mid-year OP guidance raised from ¥9.0B to ¥11.0B. Dividend lifted from ¥90 to ¥100, payout ratio ~34.6%. Equity ratio 68.9%.

**Why earnings moved this way** 1) Overseas-revenue expansion in anime/streaming — NARUTO/BORUTO mobile-game rights drove segment profit ~1.5x. 2) Broadcasting spot-CPM raises helped. 3) Distribution-rights sales (Crunchyroll, Netflix, Prime Video) and licensing accumulated as stock-type revenue.

**Why the stock moved this way** 1) Mid-year upward revision + record-high earnings pushed re-rating as 'content-rights holder.' 2) Long-lived anime IP generate decade-plus royalty streams. 3) Dividend hike + TSE PBR-improvement response. Higher content/licensing revenue mix makes earnings less swingy with ad cycles."""}

C["9416"] = {"jp": """**会社概要** 株式会社ビジョン(VISION INC.)は東証プライム上場の情報通信企業。海外渡航向け「グローバルWiFi」(海外モバイルWiFiルーターレンタル)と訪日外国人向け「NINJA WiFi」を中核に、中小企業向け情報通信サービス事業、グランピング・ツーリズム事業の三本柱を持つ。海外向けWiFiレンタル分野で国内3社中売上シェア4割強の最大手。

**業績の動き** 2025年12月期は売上高390.12億円(+9.8%)、営業利益64.65億円(+20.5%)で過去最高益。全セグメントで増収増益、売上総利益率48.4%→56.0%へ大幅改善し売上総利益+44.4%。配当は前期27円→50円(+85.2%)へ大幅増配、配当性向55.5%見込み。ROE 21.19%、自己資本比率69.1%。2026年12月期も増収増益を見込む。

**なぜ業績がこう動いたのか** ①訪日外国人の急増 — 2025年は訪日客3,600万人超で過去最高、NINJA WiFiと空港・主要観光地のSIMカード自販機が好調、無制限プラン需要で顧客単価が高水準。②円安・インバウンド回復の二重の追い風で、グローバルWiFi両方向の需要拡大。③中小企業向け情報通信サービス事業が中小企業DX需要で安定成長、グランピング事業も増収。全セグメント増益で利益率が大幅改善。

**なぜ株価がこう動いたのか** ①大幅増配(27円→50円、+85%)と配当性向55.5%という明確な株主還元強化シグナルが、インカム志向の機関・個人投資家を強く引きつけた。②全セグメント増収増益という稀少な「クリーンな決算」と過去最高益で、機関投資家のクオリティスクリーニングに合致。③訪日外国人3,600万人超(過去最高)を起点とするインバウンド需要拡大の構造化期待、大阪万博会場でのサービスブース展開、海外向けWiFiレンタル国内最大手としてのシェア優位が中期成長の支えとなった。""",
"en": """**Company overview** Vision Inc. (TSE Prime, 9416) is an information & communication company built on three pillars: Global WiFi (overseas mobile WiFi router rental for Japanese outbound travelers) and NINJA WiFi (for inbound foreign visitors); SME ICT services; and a glamping/tourism business.

**Earnings movement** FY12/2025: revenue ¥39.01B (+9.8%), OP ¥6.47B (+20.5%) — record. All segments grew; gross margin improved sharply from 48.4% to 56.0%. Dividend lifted from ¥27 to ¥50 (+85.2%), payout ratio ~55.5%. ROE 21.19%, equity ratio 69.1%.

**Why earnings moved this way** 1) Surging foreign-visitor inflows — 2025 inbound exceeded 36 million (record). 2) Double tailwind of weak JPY + inbound recovery. 3) SME ICT services grew steadily on SME DX demand.

**Why the stock moved this way** 1) Major dividend hike (¥27 → ¥50, +85%) signaled clear shareholder-return commitment. 2) Rare 'clean earnings' with all segments growing. 3) Structural inbound demand thesis + Osaka Expo service booths + leading domestic share in overseas WiFi rental."""}

C["9432"] = {"jp": """**会社概要** NTT(日本電信電話)は日本の通信業界の超大手 — NTTドコモ(携帯)、NTT東日本/西日本(固定電話・光回線)、NTTデータ(法人IT)などを傘下に持ち、日本全土の通信インフラを支える企業グループ。政府が発行済株式の約32.25%を保有する特殊会社。

**業績の動き** 2026年3月期は営業収益14兆4,091億円(+5.1%、過去最高水準)、当期純利益1兆370億円(+3.7%)。配当は16期連続増配で年5.4円(前期+0.1円)。ただし2027年3月期予想は純利益9,800億円(-5.5%)と減益見通し。中期経営戦略は「2030 powered by AIOWN」へ修正し、EBITDA4兆円目標を2031年3月期へ3年後ろ倒し。

**なぜ業績がこう動いたのか** ①グローバル・ソリューション事業(海外データセンター需要等)の成長で全体は増収増益を達成。②主力の総合ICT事業は国内モバイル競争激化・料金値下げ圧力・5G投資の負担で減益。③FY27減益の要因は、(a)米欧の高金利継続で支払利息が前期比で大幅増、(b)NTTドコモによる住信SBIネット銀行買収などM&Aで負債増、(c)AI・データセンターへの巨額投資に伴う減価償却費増大、(d)NTTデータグループ事業統合関連の一時的費用。

**なぜ株価がこう動いたのか** ①FY27減益予想と中期目標3年後ろ倒しで、市場は「投資フェーズが想定以上に長い」と読み取り、株価は2026年5月時点で約149.8〜152.6円、PER12.4倍、配当利回り3.60%と割安水準。②政府保有株売却懸念 — 日本政府は約32.25%を保有、長期売却計画が常に「天井」として機能。③2023年7月の1対25株式分割で個人投資家層は拡大したが、政府保有株供給懸念が需給の重しとなり、KDDI・ソフトバンクとの相対比較でグロース性の評価が劣後。16期連続増配で「成長株」ではなく「安定インカム株」としての位置付けが定着。""",
"en": """**Company overview** NTT (Nippon Telegraph and Telephone) is Japan's largest telecom group — comprising NTT Docomo (mobile), NTT East/West (fixed-line and fiber), NTT Data (corporate IT). Government holds roughly 32.25% of issued shares.

**Earnings movement** FY3/2026: revenue ¥14.41T (+5.1%, record-level), net ¥1.037T (+3.7%). Dividend hiked for the 16th consecutive year to ¥5.4. However, FY3/2027 net profit guided -5.5% to ¥980B. Mid-term plan revised to '2030 powered by AIOWN', pushing the EBITDA ¥4T target back 3 years to FY3/2031.

**Why earnings moved this way** 1) Global Solutions drove consolidated growth. 2) Domestic ICT declined on competition, price-cut pressure, and 5G capex. 3) FY27 decline factors: high US/EU rates pushing interest expense, M&A debt, AI/data-center depreciation, NTT Data integration costs.

**Why the stock moved this way** 1) FY27 profit decline + 3-year deferral of mid-term targets — stock held in ¥149.8-¥152.6 range, PER 12.4x, yield 3.60%. 2) Government-share-sale overhang (~32.25%) acts as a ceiling. 3) July 2023 1-for-25 stock split widened retail base; now positioned as 'stable income' rather than 'growth.'"""}

# IT10 internet/services
C["9433"] = {"jp": """**会社概要** KDDI(au・UQモバイルのブランドで知られる)は、NTTドコモ・ソフトバンクと並ぶ日本3大携帯キャリアの一角。本業のモバイル・固定通信に加え、auフィナンシャル、auエネルギー、決済(au PAY)、DX/法人ソリューションを展開する複合インフラ企業。2026年にはローソンとの統合も控えており、「通信+金融+小売+エネルギー」のライフデザインプラットフォーム化を推進中。

**業績の動き** 2026年5月12日発表のFY2026実績は、売上収益6兆719億円(前期比+4.1%)、営業利益1兆991億円(+1.1%)、親会社所有者帰属当期利益7,071億円(+7.9%)と増収増益。FY2027会社予想は売上6兆4,100億円(+5.6%)、調整後営業利益1兆2,100億円(+5.0%)、調整後当期利益7,310億円(+2.7%)。配当はFY2026の80円から84円へ4円増配予想で、達成すれば25期連続増配・配当性向42.8%・利回り3.32%水準。

**なぜ業績がこう動いたのか** ①ビジネスセグメントが売上+8.7%(1兆5,279億円)・営業利益+12.2%(2,639億円)と全社の成長エンジン化。DX・法人クラウド・データセンター需要を取り込んだ。②auフィナンシャルなど非通信領域の利益貢献拡大が、税効果と相まって当期利益+7.9%を実現。③パーソナル(コンシューマ通信)は売上+2.2%だが営業利益は▲2.1%と、政府主導の料金値下げ圧力と販促コスト増の影響が残る。

**なぜ株価がこう動いたのか** ①25期連続増配予想の発表が、新NISA成長投資枠でディフェンス銘柄を探す個人層の追加買いを誘発。②中期計画「Power-to-Connect 2028」(営業利益CAGR5%、3年で1.2兆円のAI/低遅延網投資)が長期成長ストーリーとして再評価。③通信セクター全体の成熟視と料金圧力で短期上値は重く、株価は2,500〜2,780円のレンジ内で推移、全体としてはほぼ横ばい。""",
"en": """**Company Overview** KDDI runs the au and UQ mobile brands and is one of Japan's three major mobile carriers. Beyond mobile and fixed-line, it operates au Financial, au Energy, au PAY wallet, and enterprise DX/cloud solutions. With Lawson integration completing in 2026, KDDI is building a 'telecom + finance + retail + energy' life-design platform.

**Earnings Movement** FY3/2026 actuals (May 12, 2026): revenue 6.072 trillion yen (+4.1% YoY), OP 1.099 trillion yen (+1.1%), net 707.1 billion yen (+7.9%). FY3/2027 guidance: revenue 6.41 trillion yen (+5.6%), adjusted OP 1.21 trillion yen (+5.0%), adjusted NP 731 billion yen (+2.7%). Dividend guided 80 → 84 yen — if achieved, 25 consecutive years of dividend hikes, payout 42.8%, yield 3.32%.

**Why the earnings moved this way** 1) Business segment (DX, enterprise cloud, data centers) grew revenue +8.7% to 1.528 trillion yen and OP +12.2% to 263.9 billion yen. 2) Non-telecom contribution (au Financial) plus favorable tax mix lifted net profit +7.9%. 3) Personal (consumer) grew revenue only +2.2% with OP down -2.1%.

**Why the stock moved this way** 1) 25-consecutive-year dividend-hike guide attracted new-NISA growth-quota retail buying. 2) New mid-term plan 'Power-to-Connect 2028' re-evaluated as long-run growth story. 3) Sector-wide telecom maturity views and recurring price-pressure capped upside — stock in 2,500–2,780 yen range."""}

C["9434"] = {"jp": """**会社概要** ソフトバンク(株)は、ソフトバンク・Y!mobile・LINEMOブランドを運営する日本3大携帯キャリアの一角。親会社ソフトバンクグループ(9984)の中核連結子会社で、国内事業を担う。コンシューマ通信に加え、エンタープライズ、ディストリビューション、ファイナンス、LINEヤフー子会社化を通じたメディア・コマースまで領域拡大。

**業績の動き** FY2026実績は売上7兆387億円(前期比+7.6%)、営業利益1兆426億円(+5.4%)と初の1兆円超え、親会社株主帰属純利益5,508億円(+4.7%)で過去最高更新。FY2027会社予想は売上7兆5,000億円、営業利益1兆1,000億円、純利益5,600億円と通期で増収増益。配当はFY2026の年間8.6円据え置きからFY2027は8.8円へ増配予想。新中計「Activate AI for Society」では2031年3月期に営業利益1兆7,000億円・純利益7,000億円。

**なぜ業績がこう動いたのか** ①コンシューマ・エンタープライズ・ディストリビューション・ファイナンスの4事業が全て増益。特にディストリビューションとファイナンスが牽引。②PayPayの黒字化定着とLINEヤフー連結効果で金融・広告領域の収益貢献が拡大。③エンタープライズ事業がAI/クラウド/セキュリティ需要を取り込み、法人向けARPU相当が上昇。

**なぜ株価がこう動いたのか** ①NVIDIA・Foxconnと連携した国内AIデータセンター建設構想が「AIインフラ銘柄」としての再評価を促し、複数アナリストが目標株価を引き上げ(強気目標270円・米系中立目標243円)。②配当利回り約4%・連結配当性向約78%という高インカム性が新NISA口座での個人需要の下支え。③5年連続8.6円据置き後の小幅増配にとどまったため「増配ストーリー化」には弱く、また配当性向が高水準なことから上値はやや重い。直近株価は211〜217円レンジ。""",
"en": """**Company Overview** SoftBank Corp operates the SoftBank, Y!mobile and LINEMO mobile brands and is one of Japan's three major carriers. Core domestic operating subsidiary of SoftBank Group (9984). Beyond consumer telecom: Enterprise, Distribution, Finance, and (via LINE Yahoo subsidiary) media and commerce.

**Earnings Movement** FY3/2026 actuals: revenue 7.039 trillion yen (+7.6% YoY), OP 1.043 trillion yen (+5.4%) — first ever above 1 trillion — net 550.8 billion yen (+4.7%), record. FY3/2027 guidance: revenue 7.5 trillion yen, OP 1.1 trillion yen, NP 560 billion yen. Dividend 8.6 → 8.8 yen. New mid-term plan 'Activate AI for Society' targets FY3/2031 OP 1.7 trillion yen, NP 700 billion yen.

**Why the earnings moved this way** 1) All four segments — Consumer, Enterprise, Distribution, Finance — grew. 2) PayPay turning sustainably profitable plus LINE Yahoo consolidation lifted finance/advertising contribution. 3) Enterprise captured AI/cloud/security demand.

**Why the stock moved this way** 1) Plans with NVIDIA/Foxconn for domestic AI data centers reframed the name as 'AI infrastructure stock' — multiple brokers raised targets (bull 270 yen, US-broker neutral 243 yen). 2) Yield ~4%, consolidated payout ~78% supported new-NISA retail demand. 3) Small dividend hike after 5 flat years and high payout cap upside. Stock in 211–217 yen range."""}

C["9444"] = {"jp": """**会社概要** トーシンホールディングス(東証スタンダード)は1988年設立の持株会社。中部地方(愛知・岐阜・三重)を中心にau/ソフトバンク等の携帯ショップ運営を主力事業とし、不動産賃貸事業、ゴルフ場運営事業も傘下に持っていた。会社更生手続中の特殊状況銘柄。

**業績の動き** FY2026 Q3累計実績は、売上高130.4億円(前期比+2.2%)と微増ながら、経常利益0.75億円(▲43.6%)、親会社株主帰属四半期純利益4.26億円(▲35.6%)と大幅減益。FY2027通期会社予想はUNVERIFIED(会社更生手続中のため、通常の予想は出されていない可能性が高い)。配当もUNVERIFIED/実質的に無配状態と推定。負債総額は約162億円。

**なぜ業績がこう動いたのか** ①子会社で発覚した不適切会計(売上の過大計上・売掛金の架空計上)の調査と是正処理が利益を直撃。②携帯ショップ業界そのものが、キャリアからの代理店手数料引下げと顧客の店舗離れで構造的な収益悪化に直面。③不適切会計発覚で取引銀行との融資継続条件を満たせず、資金繰りが悪化。2025年11月22日に東証から「特別注意銘柄」指定、2026年5月8日に東京地裁へ会社更生手続開始申立て・同日に手続開始決定が出された。

**なぜ株価がこう動いたのか** ①2026年5月29日に株価が前日比+50円(+27.93%)の229円へ急騰したが、これは会社更生申立て後の投機的なストップ高であり、ファンダメンタルズ評価ではない。②特別注意銘柄指定と会社更生手続入りで機関投資家は完全撤退、流動性が個人短期売買に偏る構造に。③株価形成は今後の更生計画認可・100%減資の有無・株式希薄化リスクといった法的手続きの帰結に依存する局面に入っており、通常のバリュエーション軸から外れている。一般投資家には推奨しない特殊状況銘柄。""",
"en": """**Company Overview** Toshin Holdings (TSE Standard) is a 1988-founded holding company. Its core business was operating au and SoftBank mobile retail shops centered on the Chubu region. The company is currently in corporate-reorganization proceedings — a special-situation name.

**Earnings Movement** FY3/2026 Q3 cumulative: revenue 13.04 billion yen (+2.2% YoY), ordinary 75 million yen (-43.6%), Q3 net 426 million yen (-35.6%). FY3/2027 guidance UNVERIFIED. Dividend effectively suspended. Total liabilities approximately 162 billion yen.

**Why the earnings moved this way** 1) Improper-accounting issue uncovered at a subsidiary directly hit profits. 2) Mobile-retail industry itself in structural decline. 3) Accounting scandal broke covenants with lending banks. Nov 22, 2025 TSE designated 'Special Attention Issue'; May 8, 2026 filed for corporate reorganization at Tokyo District Court.

**Why the stock moved this way** 1) May 29, 2026 stock surged +50 yen (+27.93%) to 229 yen — speculative limit-up after the reorganization filing, NOT fundamentals. 2) Institutional investors fully withdrew. 3) Price formation now depends on legal outcomes — reorganization plan approval, 100% capital reduction, dilution risk. Not recommended for general investors."""}

C["9468"] = {"jp": """**会社概要** KADOKAWA(東証プライム、9468)は出版(ライトノベル・コミック・雑誌)、アニメ制作、ゲーム(フロム・ソフトウェアを中核とする)、教育・EdTech(N高等学校/S高等学校)、ライブイベントなどIPを軸に多角展開する総合エンタメ大手。海外IP展開とアニメ・ゲームのグローバル収益化が中期テーマ。

**業績の動き** FY2026実績は売上2,829.1億円(前期比+1.8%)、営業利益81.0億円(▲51.3%)、経常利益117.0億円(▲34.1%)、純利益12.8億円と大幅減益。期初予想は11月時点で営業利益167億円→103億円へ下方修正済みで、最終81億円とさらに下振れ着地。動画工房の連結子会社化に伴うのれん償却で27億円の特損も計上。FY2027会社予想は売上3,003億円(+6.1%)、営業利益101億円(+24.7%)、経常利益120億円(+2.6%)、純利益58億円(+353.7%)。

**なぜ業績がこう動いたのか** ①出版・IP創出事業の営業利益が▲51.6%。新人作品の刊行点数増で販促リソースが分散し、「なろう/異世界系」ジャンル飽和もあって既存タイトルのヒット規模が縮小。②アニメ・実写映像事業が営業赤字転落。初アニメ化作品比率が上昇し1作品あたり売上が低下、加えて自社制作スタジオの先行投資負担が重い。③ゲーム事業も前期の大型タイトル反動で減収減益。一方、教育・EdTech事業のみ売上+13.5%・営業利益+19.4%と独自の成長軌道を維持。

**なぜ株価がこう動いたのか** ①期中の度重なる業績下方修正で「ガイダンスの信頼性」が毀損、機関投資家のディスカウントが拡大。②配信プラットフォーム(Netflix等)の作品選別の厳格化で中ヒット以下のアニメは海外ライセンス収入が見込みにくくなり、業界のビジネスモデル転換リスクが意識された。③FY27予想営業利益+24.7%は回復シナリオだが、「鬼滅/SAO級の新規大型ヒット」または「具体的な海外IP成功」が見えるまでバリュエーション回復は限定的との見方が支配的。""",
"en": """**Company Overview** KADOKAWA (TSE Prime, 9468) is a major Japanese entertainment conglomerate operating across publishing, anime production, games (FromSoftware), education/EdTech (N High School / S High School), and live events — all built around IP. Overseas IP expansion and global monetization is the mid-term theme.

**Earnings Movement** FY3/2026 actuals: revenue 282.91 billion yen (+1.8% YoY), OP 8.10 billion yen (-51.3%), ordinary 11.70 billion yen (-34.1%), net 1.28 billion yen — sharp profit decline. Guidance cut from 16.7B to 10.3B in November, final 8.10B. A 2.7B yen extraordinary loss for goodwill amortization at Doga Kobo. FY3/2027 guidance: revenue 300.3B (+6.1%), OP 10.1B (+24.7%), NP 5.8B (+353.7%).

**Why the earnings moved this way** 1) Publishing & IP-Creation OP fell -51.6%. Raising the number of new-author titles fragmented marketing resources. 2) Anime & Live-Action segment swung to operating loss. 3) Games declined on absence of prior-year mega-titles. Only Education / EdTech grew (revenue +13.5%, OP +19.4%).

**Why the stock moved this way** 1) Repeated within-year downward revisions damaged 'guidance credibility.' 2) Streaming platforms (Netflix etc.) have become pickier — mid-tier anime can no longer count on overseas licensing. 3) FY27 OP +24.7% sketches a recovery, but until a new flagship hit or concrete overseas IP success appears, re-rating remains capped."""}

C["9602"] = {"jp": """**会社概要** 東宝(東証プライム、9602)は日本最大の映画制作・配給・興行会社。「ゴジラ」「君の名は。」「鬼滅の刃 劇場版」等を配給。事業は①映画(配給・興行・TOHOシネマズ運営)、②演劇(東宝ミュージカル)、③不動産(首都圏ビル賃貸)、④IP・アニメ(GKIDS、サイエンスSARU等を含む海外配給網)の4本柱。コンテンツ+安定収益(不動産)のディフェンシブ・グロース型ポートフォリオ。

**業績の動き** FY2026実績は営業収入3,606.6億円(前期比+15.2%)、営業利益678.9億円(+5.0%)、経常利益701.4億円(+8.8%)、純利益517.7億円(+19.4%)で過去最高更新。映画事業セグメントは営業収入1,826億円(+30.6%)、営業利益373億円(+30.3%)。配給収入1,399億円は歴代最高。配当は年間85円据置き予定(FY2025実績85円)。期初予想(営業収入3,450億円、営業利益620億円)を大幅に上回り、期中に上方修正。

**なぜ業績がこう動いたのか** ①「劇場版『鬼滅の刃』無限城編 第一章 猗窩座再来」が興行収入400億円超のメガヒット、「国宝」が200億円超と2大ヒットを同時に獲得。②「名探偵コナン」「チェンソーマン レゼ篇」「8番出口」など中堅ヒット作も併走し、映画館入場者数約4,900万人(+27.6%)と大幅増。③IP・アニメ事業も売上373億円規模に拡大、GKIDS・サイエンスSARUの貢献で海外IP収益が底上げされた。

**なぜ株価がこう動いたのか** ①過去最高益+配給収入歴代最高という極めて強い決算で、業績連動で株価が評価される教科書的展開。②ワーナー・ブラザース日本配給契約(2026年開始)と50億円規模のTOHO-ONE顧客データ基盤投資など中期成長施策が好感。アナリスト評価は強気買い4/買い1/中立4、平均目標株価約1,864円。③足元では2026年6月3日株価1,218円(前日比▲4.13%)と短期的に調整局面入り。FY2027は反動減のリスクも意識されている。""",
"en": """**Company Overview** Toho (TSE Prime, 9602) is Japan's largest film production, distribution and exhibition company. Distributes Godzilla, Your Name, Demon Slayer films. Four pillars: Film (distribution, exhibition, TOHO Cinemas), Theater, Real Estate (Tokyo metro buildings), IP & Anime (overseas distribution via GKIDS, Science SARU). Defensive-growth portfolio.

**Earnings Movement** FY2/2026 actuals: operating revenue 360.66B yen (+15.2% YoY), OP 67.89B (+5.0%), ordinary 70.14B (+8.8%), net 51.77B (+19.4%) — record. Film segment: revenue 182.6B (+30.6%), OP 37.3B (+30.3%). Distribution revenue 139.9B yen — all-time high. Dividend flat at 85 yen annually. Initial guidance (345B revenue, 62B OP) was raised mid-year and beaten.

**Why the earnings moved this way** 1) Two simultaneous megahits — Demon Slayer Infinity Castle Chapter 1 surpassed 40B yen, Kokuhō cleared 20B yen. 2) Mid-tier hits ran in parallel; cinema admissions ~49 million (+27.6%). 3) IP & Anime expanded to about 37.3B yen with overseas contribution from GKIDS, Science SARU.

**Why the stock moved this way** 1) Record-profit / record-distribution-revenue print produced textbook re-rating. 2) Warner Bros. Japan distribution deal (2026) and TOHO-ONE customer data platform investment well received. Analyst stance: 4 strong-buy, 1 buy, 4 neutral, average target ~1,864 yen. 3) Jun 3, 2026 stock closed at 1,218 yen (-4.13%) — correction as market begins to price in FY27 hit-cycle reversion risk."""}

C["9605"] = {"jp": """**会社概要** 東映(東証プライム、9605)は日本の老舗映画・アニメ・テレビ制作会社。最大の価値は連結子会社「東映アニメーション(4816)」で、「ONE PIECE」「ドラゴンボール」「プリキュア」「スラムダンク」など世界的メガIPを保有。本体は映画制作・配給、特撮テレビ番組(「仮面ライダー」「スーパー戦隊」シリーズ)、東映京都撮影所などの不動産・観光事業を展開する複合エンタメ・コンテンツ企業。

**業績の動き** FY2026実績は売上1,853.3億円(前期比+3.0%)、営業利益361.0億円(+2.7%)と増収増益。Q3累計では売上1,363.5億円(+4.6%)、営業利益277.8億円(+9.6%)と興行関連事業+33.0%が牽引。自己資本比率59.4%(+2.3pp)と財務基盤強固。配当は前期41円→44円へ増額。FY2027会社予想は売上1,774億円(▲1.4%)、営業利益312億円(▲11.3%)、経常利益364億円(▲9.0%)、当期純利益205億円(+30.4%)と、減収減益・純利益のみ伸長の見通し。中期計画「VISION2030」では2031年3月期売上2,000億円を目標。

**なぜ業績がこう動いたのか** ①興行関連事業+33.0%・催事関連事業+16.1%。コロナ後の娯楽需要回復に加え、ONE PIECE関連作品の海外興行が貢献。②東映アニメーション側で円安基調+海外版権ライセンス収入が拡大、上方修正・増配へつながった。③FY2027は劇場用映画の大型タイトル端境期で営業益▲11.3%予想だが、純利益は政策保有株売却益等の特別利益で+30.4%予想と分かれた。

**なぜ株価がこう動いたのか** ①野村証券が投資判断を「Buy」→「Neutral」に格下げし、「大型タイトルへの期待低下」を理由として明示。コンテンツ企業特有の「次ヒット期待」の弱含みが直接の株価重しに。②東映アニメーション(4816)の業績・IPバリュエーションが本体の株価形成を実質的に支配する構造で、本体単体決算より子会社のサイクルが効く。③長寿IP(ONE PIECE:1997〜、ドラゴンボール:1984〜)の参入障壁と仮面ライダー/戦隊シリーズの安定キャッシュフローが下値を支え、短期は調整も長期保有層の厚みは健在。""",
"en": """**Company Overview** Toei Company (TSE Prime, 9605) is a long-established Japanese film, anime and TV production company. Its biggest asset is consolidated subsidiary Toei Animation (4816), which owns globally famous mega-IPs (One Piece, Dragon Ball, Pretty Cure, Slam Dunk). The parent itself produces films, makes tokusatsu TV series (Kamen Rider, Super Sentai), and runs real-estate/tourism assets.

**Earnings Movement** FY3/2026 actuals: revenue 185.33B yen (+3.0%), OP 36.10B (+2.7%). Q3 cumulative: revenue 136.35B (+4.6%), OP 27.78B (+9.6%), led by Exhibition +33.0%. Equity ratio 59.4% (+2.3pp). Dividend raised from 41 to 44 yen. FY3/2027 guidance: revenue 177.4B (-1.4%), OP 31.2B (-11.3%), ordinary 36.4B (-9.0%), net 20.5B (+30.4%). VISION 2030 targets FY3/2031 revenue 200B yen.

**Why the earnings moved this way** 1) Exhibition grew +33.0% and Events +16.1%. Post-pandemic demand recovery plus overseas One Piece exhibition. 2) At Toei Animation, yen weakness + rising overseas-licensing income produced upward revision and dividend hike. 3) FY27 sits between major theatrical-release cycles.

**Why the stock moved this way** 1) Nomura downgraded from Buy to Neutral, citing 'reduced expectations for major-title contribution.' 2) Toei Animation (4816) earnings effectively drive parent-stock formation. 3) Long-life IP moat (One Piece since 1997, Dragon Ball since 1984) plus Kamen Rider / Super Sentai steady cash flow support the downside."""}

C["9682"] = {"jp": """**会社概要** DTS(東証プライム、9682)はNTT系の流れを汲む中堅システムインテグレーター。金融(銀行・保険)・通信・産業・公共向けのシステム開発・運用保守、ITプラットフォーム構築、IT+組込技術を展開。中期計画「VISION2030」のもと、人月型SIから自社サービス・運用受託など高収益領域「フォーカスビジネス」への構造転換を加速。

**業績の動き** FY2026実績は売上1,352.1億円(前期比+7.4%)、営業利益164.3億円(+13.4%)で過去最高。Q3累計では売上983.3億円(+8.1%)、営業利益123.3億円(+19.2%)と一段加速。中間期は売上669.2億円・営業利益80.8億円。FY2027会社予想は売上1,420.0億円、営業利益170.0億円、当期純利益117.0億円と引き続き増収増益見通し。中間配当50円・期末配当77円(17円上方修正)の年間127円予想。

**なぜ業績がこう動いたのか** ①Q1時点でフォーカスビジネス比率が60.7%、上期累計でも62.2%に到達し、FY3/2028目標57%を3年以上前倒し達成。高収益サービス比率上昇が直接的に営業利益率改善を牽引。②プラットフォーム&サービス・デジタル&DX・IT基盤の全セグメントが揃って成長、特に法人ビジネス&ソリューションは売上+11.8%・営業利益+13.6%。③金融機関の基幹システム更改/保険会社のシステム再構築という中長期需要が継続し、受注残積み上げが利益の予見性を高めた。

**なぜ株価がこう動いたのか** ①中期計画フォーカス比率目標を3年以上前倒し達成という実行力の高さで機関投資家のレーティング改善、2025年中に株価が約+40%上昇。②ROE 17.68%・PBR 3.30倍と資本効率指標が改善、東証PBR改善要請への対応も評価された。③FY27ガイダンス(営業利益170億円)が+3.5%水準にとどまり、QYTD+19.2%実績に対する「保守的に見えるガイダンス/反動懸念」も意識され、株価は短期的にレンジ相場入り。""",
"en": """**Company Overview** DTS (TSE Prime, 9682) is a mid-sized systems integrator with NTT-group lineage. It provides system development and operations for finance (banks, insurance), telecom, industry and public sectors. Under VISION 2030, it's shifting from person-month SI to higher-margin proprietary services and operations — the 'Focus Business.'

**Earnings Movement** FY3/2026 actuals: revenue 135.21B yen (+7.4% YoY), OP 16.43B (+13.4%) — record high. Q3 YTD: revenue 98.33B (+8.1%), OP 12.33B (+19.2%) — accelerating. FY3/2027 guidance: revenue 142.0B, OP 17.0B, NP 11.7B. Dividend: interim 50 yen, year-end 77 yen, annual 127 yen guide.

**Why the earnings moved this way** 1) Focus Business share hit 60.7% by Q1 and 62.2% YTD — beating the FY3/2028 target of 57% by more than 3 years. 2) All segments grew; enterprise Business & Solutions grew revenue +11.8% and OP +13.6%. 3) Mid-long-term demand from mega-bank core-system renewals and insurance system rebuilds continues.

**Why the stock moved this way** 1) Hitting the Focus Business target 3+ years ahead of schedule demonstrated strong execution — stock rose roughly +40% during 2025. 2) Capital-efficiency metrics improved (ROE 17.68%, PBR 3.30x). 3) FY27 guidance (OP 17.0B yen, ~+3.5%) looked conservative versus the +19.2% Q3-YTD run-rate."""}

# IT11 media
C["9684"] = {"jp": """【会社概要】スクウェア・エニックス・ホールディングス(9684)は、『ファイナルファンタジー(FF)』『ドラゴンクエスト(DQ)』など世界的に有名な大型IPを保有する日本の総合エンタメ企業。家庭用ゲーム、PC、モバイル、MMO(『FF14』)、アーケード、漫画・書籍出版、ライツ・プロパティ(IPライセンス、グッズ)、ライブイベントなどを多角展開している。

【業績の動き】2026年3月期(FY2026)実績は売上高2,976.61億円(前期比-8.3%)と減収だが、営業利益547.36億円(+34.9%)、経常利益644.69億円(+57.5%)、純利益296.16億円(+21.3%)と大幅増益で着地。2027年3月期(FY2027)会社予想は売上高2,980億円(+0.1%)、営業利益490億円(-10.5%)、経常利益490億円(-24.0%)、純利益310億円(+4.7%)と保守的な減益見通し。配当は年間43円(中間18円・期末25円)で、FY27も同水準を予定。配当性向30%を基本方針としている。

【なぜ業績がこう動いたのか】第一に、デジタルエンタテインメント事業(HDゲーム)の収益性改善。新作販売は減ったが、不採算タイトルの整理と開発コスト管理を進めた結果、減収でも利益率が向上した。第二に、ライツ・プロパティ事業の好調。IPライセンス、グッズ、漫画書籍(『推しの子』など)など高粗利の領域が伸びた。第三に、アミューズメント事業も貢献。プライズや店舗運営の改善で安定収益を確保している。

【なぜ株価がこう動いたのか】第一に、大幅増益決算が市場で好感され、5月14日の決算発表前後で株価は堅調に推移。「減収でも利益が伸びる体質改善」が評価された。第二に、ライツ事業のストック性とIPの世界的知名度が、ゲーム会社特有のヒット依存リスクを和らげるとの見方で機関投資家の保有が継続。第三に、ただしFY27ガイダンスは経常利益-24%の正常化見通しで、株価の更なる上値追いには新作の大型ヒットが必要との見方が定着しており、上昇は限定的。注意:当期は「利益ピーク」との指摘もある。""",
"en": """[Company overview] Square Enix Holdings (9684) is a Japanese entertainment conglomerate holding globally famous mega-IPs like Final Fantasy and Dragon Quest. It operates across console games, PC, mobile, MMOs (FF14), arcade, manga/book publishing, Rights & Properties (IP licensing and merchandise), and live events.

[Earnings movement] FY3/2026 actuals: revenue 297.66 billion yen (-8.3% YoY), but operating profit 54.74 billion yen (+34.9%), ordinary profit 64.47 billion yen (+57.5%), and net profit 29.62 billion yen (+21.3%) — a sharp profit jump on a revenue decline. FY3/2027 guidance: revenue 298.0 billion yen (+0.1%), OP 49.0 billion yen (-10.5%), ordinary profit 49.0 billion yen (-24.0%), net profit 31.0 billion yen (+4.7%). Dividend held flat at 43 yen annual.

[Why earnings moved this way] First, profitability improvement in Digital Entertainment (HD games). New-title revenue fell, but cleanup of unprofitable titles and tighter development-cost control lifted margins. Second, strong Rights & Properties results. Third, Amusement also helped — prize machines and venue ops improved.

[Why the stock moved this way] First, the big profit beat was welcomed by the market. The 'revenue down, profit way up' transformation narrative scored well. Second, the stock retains heavy institutional ownership because the recurring Rights business cushions hit-dependence risk. Third, however, FY27 guidance projects a normalization, capping further upside."""}

C["9692"] = {"jp": """【会社概要】シーイーシー(CEC、9692)は独立系の中堅システムインテグレーター。製造業(自動車・電機・機械)向けの設計・生産系システム(CAD/CAM/PLM、MES等)に強みを持ち、トヨタグループなど優良顧客の情報活用ツールに豊富な実績を持つ。組み込みソフト開発、金融・流通向けDX、サイバーセキュリティ、クラウド移行(AWS/Azure/GCP)にも事業領域を拡大している。

【業績の動き】2026年1月期(FY2026)実績は売上高658.82億円(前期比+17.2%)、営業利益73.38億円(+9.6%)、経常利益74.35億円(+9.2%)、純利益52.01億円(+28.8%)で5期連続増収増益。特にインテグレーションセグメントが売上429.53億円(+20.3%)、営業利益87.86億円(+15.7%)と全社を牽引。2027年1月期(FY2027)会社予想は経常利益78億円(+4.9%)で4期連続の過去最高益更新見込み。配当は年間70円(前期+15円)、FY27は中間35円+期末45円の年間80円(+10円)を予定。

【なぜ業績がこう動いたのか】第一に、DX関連投資の需要拡大。製造業のIoT化・スマートファクトリー対応、クラウド移行案件が継続的に積み上がり、+17.2%という高い売上成長率につながった。第二に、セキュリティ対策需要の構造的拡大。サイバー攻撃の高度化を背景に、企業のセキュリティ投資は中長期で増加トレンドにある。第三に、トヨタグループ等の主要顧客の脱炭素・EV対応・スマートファクトリー化に伴う大型IT投資の継続受託。

【なぜ株価がこう動いたのか】第一に、5期連続増収増益と4期連続最高益更新見通しという持続的成長記録が、機関投資家のクオリティ・グロース選好と合致した。第二に、配当を70円→80円へ継続増配し、配当性向を引き上げる株主還元強化が、東証PBR改善要請への対応として評価された。第三に、独立系SIならではの顧客分散とDX/セキュリティの構造的追い風が、SI業界平均(5〜8%)を大きく上回る成長期待をもたらしている。""",
"en": """[Company overview] CEC (Computer Engineering Consultants, 9692) is an independent mid-sized systems integrator. It is strong in design/production systems (CAD/CAM/PLM, MES) for manufacturing and has a deep track record with prime customers such as the Toyota Group. Also covers embedded software, cybersecurity, and cloud migration.

[Earnings movement] FY1/2026 actuals: revenue 65.88 billion yen (+17.2% YoY), OP 7.34 billion yen (+9.6%), ordinary 7.43 billion yen (+9.2%), net 5.20 billion yen (+28.8%) — five consecutive years of revenue and profit growth. Integration segment led with revenue 42.95B yen (+20.3%) and OP 8.79B yen (+15.7%). FY1/2027 guidance: ordinary 7.80B yen (+4.9%) — fourth consecutive record. Dividend 70 yen, FY27 planned 80 yen.

[Why earnings moved this way] First, expanding DX-investment demand — manufacturing IoT/smart-factory adoption and cloud migration deals piled up. Second, structural growth in cybersecurity demand. Third, continued large IT-investment commissions from key customers tied to decarbonization and EV transition.

[Why the stock moved this way] First, five consecutive years of growth fits the Quality-Growth screen. Second, the dividend hike and rising payout ratio seen as TSE PBR-improvement response. Third, structural DX/security tailwind plus broad customer diversification has investors pricing in growth above the SI industry average."""}

C["9697"] = {"jp": """【会社概要】カプコン(9697)は『モンスターハンター』『バイオハザード』『ストリートファイター』『デビルメイクライ』など世界的人気IPを多数保有する日本のゲーム会社。家庭用ゲーム、PC(Steam)、モバイル、アーケード、グッズ販売、eスポーツ、映像化と多角展開。海外売上比率約80%で、世界230以上の国・地域に販売している。

【業績の動き】2026年3月期(FY2026)実績は売上高1,953.65億円(前期比+15.2%)、営業利益752.95億円(+14.5%)、経常/純利益も過去最高を更新し、11期連続2桁の営業増益、9期連続の過去最高益、13期連続増収増益を達成。家庭用ゲームの累計販売は5,907万本で過去最高。2027年3月期(FY2027)会社予想は売上高2,100億円(+7.5%)、営業利益830億円(+10.2%)、経常利益830億円(+12.0%)、純利益580億円(+6.3%)と引き続き最高業績更新を見込む。配当はFY26が年間45円(+5円)、FY27予想46円(中間23円+期末23円)、配当性向約33.2%。

【なぜ業績がこう動いたのか】第一に、デジタル販売比率約83%という収益構造。リピートタイトル比率は2015年の50%から70%超まで上昇し、過去作が新作と連動して長期間売れ続けるカタログ・モデルが定着、営業利益率38〜39%という高収益体質を実現した。第二に、『モンスターハンターワイルズ』『バイオハザード リクイエム(700万本超でフランチャイズ最速ペース)』など主力新作の販売拡大が利益を押し上げた。第三に、海外売上比率約80%とプラットフォーム分散(Switch/PS5/Steam)で地域・端末別リスクが低い。

【なぜ株価がこう動いたのか】第一に、11期連続2桁営業増益という稀少な記録が、長期保有を志向する機関投資家から高く評価された。第二に、ただし『モンスターハンターワイルズ』の販売本数が事前期待を下回ったとの見方から、株価は約4,800円のATHから4,000円台へ調整する場面が続いた。第三に、FY27も最高業績更新を会社が示したことで下値は限定的で、ジェフリーズは買い継続。投資判断は『業績67%・テクニカル33%』と業績ドリブンの健全な構図。""",
"en": """[Company overview] Capcom (9697) is a Japanese game company holding many globally popular IPs: Monster Hunter, Resident Evil, Street Fighter, Devil May Cry. It spans console, PC (Steam), mobile, arcade, merchandise, esports, and media adaptations. Overseas sales account for roughly 80%, distributed across more than 230 countries/regions.

[Earnings movement] FY3/2026 actuals: revenue 195.37B yen (+15.2% YoY), OP 75.30B (+14.5%); ordinary and net profit also hit all-time highs. 11th straight year of double-digit OP growth, 9th straight record year, 13 consecutive years of growth. Consumer game cumulative units hit 59.07 million — a record. FY3/2027 guidance: revenue 210.0B (+7.5%), OP 83.0B (+10.2%), ordinary 83.0B (+12.0%), net 58.0B (+6.3%). Dividend: FY26 45 yen (+5), FY27 plan 46 yen.

[Why earnings moved this way] First, the revenue model: digital sales make up around 83%, and the repeat-title share rose from 50% (2015) to over 70%, with back-catalog titles continuing to sell for years. This drove a structural OP margin of 38-39%. Second, flagship new-title strength: Monster Hunter Wilds and Resident Evil Requiem (7M+ units — fastest-selling in the franchise). Third, ~80% overseas mix and platform diversification.

[Why the stock moved this way] First, the rare record of 11 consecutive years of double-digit OP growth is highly valued. Second, however, Monster Hunter Wilds sales came in below pre-release expectations, pulling shares from an ATH ~4,800 yen down into the 4,000 yen range. Third, the FY27 record-update guide and Jefferies' maintained Buy rating limit downside."""}

C["9746"] = {"jp": """【会社概要】TKC(9746)は『会計事務所事業』(税理士・公認会計士向けの会計・税務・経営分析システム)と『地方公共団体事業』(市区町村向けの自治体・税務・住民情報システム)の二本柱を持つ独立系ITサービス企業。全国の税理士・会計事務所約12,000名を組織化した『TKC全国会』を顧客基盤とし、全国税理士事務所の3割超が利用するTKCグループソリューションが護城河(MOAT)となっている。印刷事業も保有。

【業績の動き】2025年9月期(FY2025)実績は売上高834.8億円(+11.0%)、営業利益161.4億円(+4.1%)、経常利益165.9億円(+3.5%)、純利益120.9億円(+7.3%)で12期連続の過去最高益。地方公共団体事業275.65億円(+26.7%)が急成長。2026年9月期(FY2026)上期累計は売上468.25億円(+19.4%)、営業利益111億円(+28%)、経常利益114.37億円(+29.0%)、純利益79億円(+26%)と大幅増益。FY2027会社予想は売上855億円(+2%)、純利益121億円(+1%)と成長率は急減速見込み。配当は年間110円、次期も110円据え置き。

【なぜ業績がこう動いたのか】第一に、自治体ガバメントクラウド上の標準準拠システム移行特需。デジタル庁主導の自治体システム標準化(164団体で対応完了)に伴う大型システム更改需要が一気に顕在化した。第二に、会計事務所事業の安定したストック型収益。約12,000名の税理士ネットワークを通じた契約継続率の高さと新規開拓、単価上昇が続いている。第三に、FY26 1-3月期(2Q単独)は経常利益-38.9%、営業利益率21.9%→12.5%と大幅悪化。理由は標準化案件の検収集中の反動と新会計年度の費用先行で、上期通算では大幅増益の構図。

【なぜ株価がこう動いたのか】第一に、12期連続最高益というクオリティ・グロース銘柄の代表格として、長期保有する機関投資家のコア銘柄に組み入れられている。第二に、ただし164団体すべての標準化移行完了によりFY27は売上+2%・純利益+1%への急減速が会社自身から示され、ピークアウト懸念が株価上値を抑えている。第三に、配当110円据え置きと無借金経営に近い高自己資本比率で、金利上昇局面でのディフェンシブ性が評価されている。リスクは特需剥落、税理士業界の高齢化、NTTデータ・富士通等との自治体案件競争。""",
"en": """[Company overview] TKC (9746) is an independent IT-services company built on two pillars: Accounting Firms (systems for tax accountants and CPAs) and Local Government (systems for municipalities). Customer base is the 'TKC National Federation' — ~12,000 tax accountants. Over 30% of tax-accountant offices nationwide use TKC.

[Earnings movement] FY9/2025 actuals: revenue 83.48B yen (+11.0%), OP 16.14B (+4.1%), ordinary 16.59B (+3.5%), net 12.09B (+7.3%) — 12 consecutive years of record-high earnings. Local Government 27.57B (+26.7%). FY9/2026 H1: revenue 46.83B (+19.4%), OP 11.10B (+28%), ordinary 11.44B (+29%), net 7.9B (+26%). FY27 guidance: revenue 85.5B (+2%) and net 12.1B (+1%) — sharp deceleration. Dividend held at 110 yen.

[Why earnings moved this way] First, special demand from the Government-Cloud-based standards-compliant migration program — Digital Agency-led standardization (now complete across all 164 target entities) drove a one-off wave of large-scale system replacements. Second, stable stock-type revenue from the Accounting Firms business. Third, however, the standalone Jan-Mar quarter showed ordinary profit -38.9% and OP margin collapsing from 21.9% to 12.5%.

[Why the stock moved this way] First, 12 consecutive years of record earnings make TKC a Quality-Growth holding. Second, the FY27 guide for just +2% revenue / +1% net profit — after completion of all 164 migrations — has anchored peak-out concerns. Third, a flat 110-yen dividend and near-zero debt give it defensive appeal."""}

C["9759"] = {"jp": """【会社概要】NSD(9759)は日本の独立系IT企業で、企業向けにシステム開発・保守・運用サービスを提供。重点分野はDAS事業(Digital Architecture Solution=クラウド活用のDX関連システム開発)で、金融IT(銀行・保険の基幹系)、産業IT(製造業向け)、セキュリティ製品も展開。受託開発+準委任契約(エンジニア常駐)+保守運用が主体の労働集約型ビジネスモデル。

【業績の動き】2026年3月期(FY2026)実績は売上高1,178.13億円(+9.3%)、営業利益190.73億円(+13.2%)、経常利益193.3億円(+13.4%)と増収増益。重点のDAS事業が575.78億円(+15.8%)と高成長で全体を牽引。2027年3月期(FY2027)は経常利益197億円見込みで8期連続最高益更新の方針。配当はFY26実績96円、FY27予想97円、総還元性向70%以上・配当性向50%以上を株主還元の基本方針として掲げ、自社株買いも併用。期末配当は2025年10月に増配修正。

【なぜ業績がこう動いたのか】第一に、大企業のDXニーズ拡大で重点分野DAS事業が+15.8%と全体平均(+9.3%)を大きく上回り、収益構成のシフトが進んだ。第二に、金融IT(銀行勘定系刷新、保険のシステム更改)と産業IT(製造業のスマートファクトリー・脱炭素対応IT投資)が同時に伸び、需要分散が効いた。第三に、セキュリティ製品の好調も寄与。長期で純利益率・営業利益率が改善し、ROE/ROAも一般的な目安を上回る水準。

【なぜ株価がこう動いたのか】第一に、業績は連続最高益なのに株価は2026年5月14日に年初来安値2,509円(10年来高値は2025年9月の3,670円)まで調整、コンセンサス目標株価4,200円に対し2,625円と6割上昇余地を放置するアンダーパフォーム。第二に、市場の本音は『NSDはSaaSではなく、準委任・保守運用主体でAIによるコスト圧縮の影響を最も受けやすい』との指摘。NRI、TIS等が自社プロダクトSaaSとAIマネタイズで先行する中、相対比較で見劣り。第三に、配当97円・総還元性向70%という株主還元の手厚さが下値を支えているが、AI時代に向けた事業モデル転換のロードマップが見えるまでバリュエーション再評価は限定的との見方が定着。""",
"en": """[Company overview] NSD (9759) is a Japanese independent IT company providing system development, maintenance, and operations services. Priority area is DAS (Digital Architecture Solution) — cloud-based DX system development. Also covers financial IT, industrial IT, and security products. Labor-intensive model.

[Earnings movement] FY3/2026 actuals: revenue 117.81B yen (+9.3% YoY), OP 19.07B (+13.2%), ordinary 19.33B (+13.4%). DAS segment grew +15.8% to 57.58B. FY3/2027 ordinary profit guidance 19.7B — eighth consecutive record. Dividend: 96 yen for FY26, 97 yen planned for FY27. Total return ratio 70%+ and payout ratio 50%+, combined with buybacks.

[Why earnings moved this way] First, large-enterprise DX demand pushed DAS up +15.8%, well above the overall +9.3% — mix shift. Second, financial IT and industrial IT both grew simultaneously. Third, security products also contributed. Net/operating margins are trending up.

[Why the stock moved this way] First, despite consecutive record earnings, the stock fell to a YTD low of 2,509 yen on May 14, 2026 (10-year high was 3,670 yen in Sept 2025), leaving ~60% upside vs consensus target of 4,200 yen unrewarded. Second, the market view is that NSD is not a SaaS company — it's a staffing/maintenance shop most exposed to AI-driven cost compression, and peers like NRI and TIS are ahead in proprietary-SaaS and AI monetization. Third, the 97-yen dividend and 70%+ total-return policy support the floor."""}

C["9984"] = {"jp": """【会社概要】ソフトバンクグループ(9984)は孫正義氏が率いる日本最大の投資持株会社。半導体設計の英Arm Holdings(連結子会社)、米OpenAI(保有比率約11%、投資予約含む)、PayPay(連結子会社)、Vision Fund経由の世界中のテクノロジー企業、東南アジア・インドのスタートアップなどに大規模投資。事業領域はAI・半導体・通信・決済・ロボティクスへ拡大中。

【業績の動き】2026年3月期(FY2026)実績は売上高7兆7,987億円(+7.7%)、親会社所有者帰属純利益5兆23億円(前期比+333.7%=約4.3倍)と急増し、5期ぶりに過去最高益更新。金額ベースで国内企業歴代最高水準。投資損益は7兆2,865億円の利益で、うちOpenAI出資に係る投資利益が6兆7,304億円(4Q単独でも巨額の評価益)。NAV(時価純資産)は約40兆1,000億円。2027年3月期(FY2027)の連結業績予想は『未確定要素が多い』として非開示。配当は2025年12月31日割当の1→4株式分割を反映して年間11円(分割前換算44円)を予定、配当性向は1.3%水準。

【なぜ業績がこう動いたのか】第一に、最大要因はOpenAIへの大規模出資に係る評価益約6.7兆円の計上。OpenAIの企業価値急騰がそのまま帳簿利益となった(実現益ではなくIFRSの公正価値評価ベース)。第二に、Arm事業の好調。最新技術の採用拡大とAIデータセンター向け需要を背景に、ロイヤルティー収入が単価・出荷量の両面で増加。第三に、PayPayの上場(連結子会社として継続)と決済・金融残高拡大による手数料・金利収入の伸びも全社利益に貢献。

【なぜ株価がこう動いたのか】第一に、決算発表後はBloombergによれば一時2.8%安の5,841円となるなど、すでに織り込み済みとの反応。OpenAIへの依存度の高さが警戒された。第二に、それでも年初来では連日最高値を付ける場面があり、OpenAIのIPO観測(米報道で22日にも申請)報道で急反発する局面が続いた。第三に、AI関連銘柄として日本市場で最も明確な選択肢であり、半導体・ロボティクスへの『次の矢』戦略と日経平均寄与度の大きさが指数連動マネーを呼び込む構造。主リスクはOpenAI評価額の調整に伴う巨額の評価損リスクと、有利子負債増加。""",
"en": """[Company overview] SoftBank Group (9984), led by Masayoshi Son, is Japan's largest investment holding company. Makes large-scale investments in UK chip designer Arm Holdings, US-based OpenAI (about 11% stake), PayPay, Vision Fund portfolio companies, and Southeast-Asian/Indian startups. Business reach now spans AI, semiconductors, telecom, payments, and robotics.

[Earnings movement] FY3/2026 actuals: revenue 7.7987T yen (+7.7% YoY), net profit attributable to owners of the parent 5.0023T yen (+333.7%, ~4.3x YoY) — a 5-year-high record and one of the largest annual profits ever for a Japanese listed company. Investment gains totaled 7.2865T yen, of which OpenAI alone contributed 6.7304T. NAV expanded to ~40.1T yen. FY3/2027 guidance withheld due to 'too many uncertain factors.' Dividend 11 yen annual (post-1:4 split allotted Dec 31, 2025).

[Why earnings moved this way] First, the dominant driver was a ~6.7T yen mark-to-market valuation gain on the OpenAI investment — OpenAI's surging private valuation was booked as accounting profit under IFRS fair-value treatment. Second, Arm's royalty revenue grew on both higher unit pricing and shipping volume, propelled by AI data-center demand. Third, PayPay's listing plus expanding payment/financial balances lifted fee and interest income.

[Why the stock moved this way] First, on the earnings day Bloomberg reported shares briefly fell 2.8% to 5,841 yen — the strong print was largely priced in. Second, however, the stock hit record highs on consecutive days, surging on reports that OpenAI may file for an IPO as early as the 22nd. Third, SBG is Japan's clearest AI-exposure proxy, and the next-arrow strategy targeting semiconductors and robotics keeps drawing index-linked money flow."""}

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
