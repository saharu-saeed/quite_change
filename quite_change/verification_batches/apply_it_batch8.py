# -*- coding: utf-8 -*-
"""Apply IT batch 8 (IT08, 7 entries)."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
IT_PATH = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data\company_research_2025.json")
C = {}

C["2121"] = {"jp": """【会社概要】MIXI(ミクシィ)はスマホゲーム『モンスターストライク(モンスト)』で大ヒットした会社で、現在は「デジタルエンターテインメント(モンスト中心のゲーム)」「スポーツ(競輪オンラインベッティングのTIPSTAR、Bリーグの千葉ジェッツ、2025年9月に連結した豪州・カナダのスポーツベッティング会社PointsBet)」「ライフスタイル(家族向けSNSみてね等)」の3本柱体制。

【業績の動き】FY26(2026年3月期)実績は売上1,713.69億円(前年比+10.7%)、営業利益222.56億円(同-16.3%)で増収減益。FY27会社予想は売上1,850億円(+8.0%)、営業利益195億円(-12.4%)、純利益135億円(-21.8%)とさらに減益見通し。配当はFY26実績120円、FY27予想125円(株主資本配当率DOE5%目安)で増配方針。

【なぜ業績がこう動いたのか】第一にスポーツ事業の急成長 — セグメント売上は前年比+63.8%の658億円、PointsBet連結が大きく寄与し、TIPSTARや千葉ジェッツも好調。第二に主力モンストのMAU(月間利用者数)減少 — デジタルエンターテインメント売上は-10.8%の838億円と落ち込んだ。第三にPointsBet買収に伴うのれん償却や地上波アニメ広告費等の費用増 — 増収でも利益が減った主因はこの一時費用負担。

【なぜ株価がこう動いたのか】第一に「売上7割をモンストが占める」構造リスク — 10年超運営でユーザー入替が進まず、FY27もモンスト減収見通しが嫌気された。第二にスポーツ事業の評価軸 — PointsBet連結で売上は伸びたが、賭博関連事業として保守的機関投資家は敬遠しがち。第三に増配方針と還元強化 — DOE5%目安の継続増配・自社株買いがディフェンス材料となり、過去1年では概ね横ばい〜緩やかな上昇トレンドを維持。""",
"en": """[Company Overview] MIXI runs three pillars: Digital Entertainment (Monst-centered games), Sports (TIPSTAR online keirin betting, the Chiba Jets B-League team, and PointsBet — consolidated in Sept 2025), and Lifestyle (the family-photo-sharing app Mitene, etc.).

[Earnings Movement] FY26 actuals: revenue 171.37 bn yen (+10.7% YoY), OP 22.26 bn yen (-16.3%). FY27 guidance: revenue 185 bn yen (+8.0%), OP 19.5 bn yen (-12.4%), net 13.5 bn yen (-21.8%). Dividend FY26 actual 120 yen, FY27 guide 125 yen (DOE 5% target).

[Why earnings moved] First, Sports segment surged — segment sales +63.8% YoY to 65.8 bn yen, with PointsBet consolidation the main driver. Second, the core Monst saw MAU decline — Digital Entertainment sales -10.8% to 83.8 bn yen. Third, goodwill amortization tied to PointsBet plus one-time TV-anime ad spend lifted costs.

[Why the stock moved] First, the structural risk of '~70% of sales depending on Monst.' Second, mixed view on the Sports business — gambling exposure makes institutions cautious. Third, dividend-hike commitment acts as defensive support."""}

C["2317"] = {"jp": """【会社概要】システナはソフトウェア品質保証(テスト)を出自とする独立系ITサービス会社で、現在は「デジタルインテグレーション(企業のDX案件、システム開発、QA)」「ビジネスソリューション(自社プロダクト・ERP)」「次世代モビリティ(自動車向け組み込み開発、自動運転、コネクテッドカー)」の3セグメントを展開。自動車・通信・金融・流通など顧客基盤が広い。

【業績の動き】FY26実績は売上944億円(前年比+12.9%)、営業利益153.67億円(+27.3%)、経常利益161.5億円(+36.2%)、純利益113.12億円(+33.4%)と全項目で大幅増益。EPSは31.65円(前期23.17円)。FY27会社予想は売上980億円(+3.8%)、営業利益159.6億円(+3.9%)、純利益106.3億円(-6.0%)と利益はやや調整見込み。配当は前期14円→当期18円へ増配。

【なぜ業績がこう動いたのか】第一に次世代モビリティ事業の成長 — 自動車のソフトウェア定義車両(SDV)化、自動運転、コネクテッドカー開発需要が継続的に拡大した。第二にデジタルインテグレーション事業の堅調 — 企業のDX投資・AI関連投資が追い風で、システム開発・QA案件が積み上がった。第三にビジネスソリューション事業の特需 — 一時的な大型案件が当期利益を押し上げた(この特需剥落がFY27純利益-6.0%予想の主因)。

【なぜ株価がこう動いたのか】第一に営業利益+27.3%・経常+36.2%・純利益+33.4%という圧倒的な利益成長率 — SI業界平均を大きく上回り、機関投資家のクオリティ・グロース戦略に合致した。第二にSDVテーマへの長期評価 — トヨタ・ホンダ系列に組み込まれた長期成長ストーリーが買われた。第三に継続増配・東証PBR改善要請への対応 — 配当性向引き上げと政策保有株売却が評価された。リスクはFY27の特需剥落と人件費インフレ。""",
"en": """[Company Overview] Systena is an independent IT-services firm with roots in software quality assurance. Today it runs three segments: Digital Integration (enterprise DX, system development, QA), Business Solution (proprietary products and ERP), and Next-generation Mobility (automotive embedded development, autonomous driving, connected cars).

[Earnings Movement] FY26 actuals: revenue 94.4 bn yen (+12.9% YoY), OP 15.367 bn yen (+27.3%), ordinary 16.15 bn yen (+36.2%), net 11.312 bn yen (+33.4%). EPS rose to 31.65 yen (from 23.17 yen). FY27 guidance: revenue 98 bn yen (+3.8%), OP 15.96 bn yen (+3.9%), net 10.63 bn yen (-6.0%). Dividend hiked from 14 yen to 18 yen.

[Why earnings moved] First, Next-gen Mobility business grew — sustained expansion in SDV adoption, autonomous driving. Second, Digital Integration stayed strong — corporate DX and AI investment provided tailwinds. Third, Business Solution special demand — a one-time large project lifted current-year profit.

[Why the stock moved] First, exceptionally strong profit-growth rates (OP +27.3%, ordinary +36.2%, net +33.4%) — far above SI-industry averages. Second, long-term re-rating of the SDV theme. Third, sustained dividend hikes."""}

C["2371"] = {"jp": """【会社概要】カカクコムは日本最大級の比較・レビューサイト群を運営する会社で、「価格.com」「食べログ」「求人ボックス」「インキュベーション」の4セグメント体制。

【業績の動き】FY26実績は売上収益941.27億円(前年比+20.0%)と大幅増収だが、営業利益272.43億円(-7.0%)で減益。配当は1株50円(前期比-30円減 ※前期に特別配当があったため減少)。FY27会社予想は売上1,145億円(+21.6%)、営業利益308億円(+13.1%)、親会社利益207億円(+10.1%)と大幅成長見通し。FY27配当予想54円(+4円、配当性向51.6%)、新指標「調整後EBITDA」360億円見通し。

【なぜ業績がこう動いたのか】第一に食べログ事業の好調 — 売上402億円(+20.2%)。インバウンド観光客のオンライン予約増加が貢献し、多言語アプリの累計DLは約200万件。第二に求人ボックスの戦略的赤字 — 約14億円のセグメント損失。ブランド投資とAI関連投資を優先する先行投資フェーズ。第三に成長投資の前倒し — 売上は伸びたが利益は意図的に圧迫した、いわゆる「投資先行」型の決算。

【なぜ株価がこう動いたのか】第一に2026年5月、欧州系PEファンドEQTがTOB価格3,000円・総額5,900億円で買収・非公開化を発表 — 株価は急伸し、5/13に3,340円(年初来高値)、その後ストップ高3,425円まで上昇。第二にLINEヤフー連合が3,232円で対抗提案 — 買収合戦に発展し、株価がTOB価格を上回って推移。第三に食べログのインバウンド需要が成長期待を支えた一方、求人ボックスの先行投資による減益、AI(ChatGPT等のレコメンド型サービス)による食べログ脅威といった懸念もあり、投資家の見方は分かれていた — TOB発表が一気に評価を引き上げた。""",
"en": """[Company Overview] Kakaku.com runs Japan's largest portfolio of price-comparison and review sites: Kakaku.com, Tabelog, Job Box, and Incubation — four segments.

[Earnings Movement] FY26 actuals: revenue 94.127 bn yen (+20.0% YoY) — sharp top-line growth, but OP 27.243 bn yen (-7.0%) — profit decline. Dividend 50 yen/share (-30 yen YoY). FY27 guidance: revenue 114.5 bn yen (+21.6%), OP 30.8 bn yen (+13.1%), parent profit 20.7 bn yen (+10.1%).

[Why earnings moved] First, Tabelog grew strongly — sales 40.2 bn yen (+20.2%) on rising inbound-tourist online reservations. Second, Job Box's deliberate loss — segment loss of about 1.4 bn yen. Third, accelerated growth investment squeezed profit.

[Why the stock moved] First, in May 2026 European PE fund EQT announced a TOB at 3,000 yen/share (about 590 bn yen total) — the stock surged. Second, a LINE Yahoo consortium counter-bid at 3,232 yen — competitive bidding. Third, Tabelog's inbound demand supports growth expectations but concerns over Job Box's investment-related loss and AI threats had split investor views — the TOB announcement abruptly lifted valuation."""}

C["3626"] = {"jp": """【会社概要】TISは大手システムインテグレーター(SI、企業の基幹システム構築・運用受託)。金融(クレジットカード決済、銀行、保険)、産業(製造・サービス)、公共(自治体)を主要顧客とする独立系で、もとは三井グループのIT会社を統合して発足。生成AIをシステム開発全工程に組込む方針で、中期計画(2024-2026)とグループビジョン2032で長期成長を志向。

【業績の動き】FY26実績は売上5,964.79億円(前年比+4.3%)、営業利益762.29億円(+10.4%)で過去最高益を更新。営業利益率は12.8%(+0.7pp)へ改善。ただし純利益は訴訟損失引当金・減損損失計上で減益。FY27会社予想は売上6,200億円、営業利益810億円(+6.3%)とさらなる成長見通し。配当はFY26年間80円(中間38円+期末42円)→FY27予想90円で14期連続増配、500億円の自社株買い(FY26中139億円取得済み、残額361億円をFY27取得予定)も実施。

【なぜ業績がこう動いたのか】第一にDX(デジタルトランスフォーメーション)需要の継続 — 金融・産業・公共セグメント全方位で堅調。第二に金融セグメントの安定収益 — クレジットカード決済処理、銀行勘定系などミッションクリティカル領域が長期収益基盤。第三に原価管理・人材ミックス最適化・サービス化(ストック収益)シフトで営業利益率が12.8%まで改善 — SI業界平均7-9%を大幅に上回る水準を実現した。

【なぜ株価がこう動いたのか】第一に500億円の大型自社株買い発表 — 東証PBR改善要請への明確な回答となった。第二に14期連続増配と総還元性向引き上げ(目安45%→50%) — 配当+自社株買いの合計還元強化がROE改善ストーリーを補強。第三に過去最高益という質の高い成長 — SI業界の中で安定成長銘柄として機関投資家のクオリティ・グロース選好に合致した。""",
"en": """[Company Overview] TIS is a major systems integrator primarily serving Finance (credit-card payments, banking, insurance), Industrial (manufacturing/services), and Public (local government) clients. An independent firm formed by integrating Mitsui-group IT entities.

[Earnings Movement] FY26 actuals: revenue 596.479 bn yen (+4.3% YoY), OP 76.229 bn yen (+10.4%) — record-high OP. OP margin improved to 12.8% (+0.7pp). Net profit declined however due to litigation provision and impairment losses. FY27 guidance: revenue 620 bn yen, OP 81 bn yen (+6.3%). Dividend FY26 80 yen/year → FY27 guide 90 yen, marking 14 consecutive years of dividend hikes. A 50 bn yen share buyback is being implemented.

[Why earnings moved] First, sustained DX demand. Second, Finance segment delivered stable revenue. Third, cost management and talent-mix optimization pushed the OP margin to 12.8%.

[Why the stock moved] First, announcement of a 50 bn yen large-scale share buyback. Second, 14 consecutive years of dividend hikes and a raised total-return-ratio target. Third, record-high profit demonstrates high-quality growth."""}

C["3636"] = {"jp": """【会社概要】三菱総合研究所(MRI)は日本最大級のシンクタンク・コンサルティング企業。三菱グループを主要株主とし、政策提言・経済予測・産業調査・経営/ITコンサル・官公庁向け調査研究・DXコンサル・SIまで幅広く提供。中期計画2026では2030年売上2,000億円目標。注:本ティッカーはMKI(三井情報、コード2665)ではなくMRI(三菱総研、コード3636)。

【業績の動き】会計期は9月締め。FY9/2026中間期(2025年10月-2026年3月)実績は売上725.71億円(前年比+10.9%)、営業利益92.93億円(+36.3%)、経常利益100.94億円(+32.1%)、中間純利益84.7億円(+73.5%)と大幅増収増益。通期会社予想は上方修正後で売上1,250億円(+2.9%)、営業利益84億円(+4.9%)、経常95億円(-2.4%)、純利益66億円(+3.3%)と保守的水準。

【なぜ業績がこう動いたのか】第一にシンクタンク・コンサルティング事業の好調 — 中間期セグメント売上335.62億円(+16.1%)、経常84.31億円(+49.3%)と大幅伸長。政府のDX政策、デジタル庁関連、防衛・経済安全保障、エネルギー政策などテーマで政策コンサル需要が継続。第二に三菱グループ案件と民間DX/AI戦略・ESG/中長期戦略策定支援需要。第三にITサービス事業の不採算案件影響 — 中間セグメント売上390.09億円(+6.8%)も経常16.65億円(-16.7%)と利益面で課題。

【なぜ株価がこう動いたのか】第一に中間期で通期計画を大幅前倒し達成 — 経常+32.1%(中間)対通期-2.4%予想とのギャップで上方修正期待が高まった。第二にシンクタンク業態の希少性 — 上場シンクタンクは野村総研(4307)、MRI、大和総研、日本総研など少数で、政策・経済予測の質で評価が高い。第三に政府政策案件の安定需要・ROE改善・三菱グループの後ろ盾 — 機関投資家の資本効率重視スクリーニングに合致した。""",
"en": """[Company Overview] Mitsubishi Research Institute (MRI) is one of Japan's largest think tanks and consultancies. Major shareholders are Mitsubishi Group companies. Mid-term Plan 2026 targets revenue of 200 bn yen by FY3/2030. Note: This ticker is MRI (Mitsubishi Research Institute, code 3636), not MKI (Mitsui Knowledge Industry, code 2665).

[Earnings Movement] Fiscal year ends in September. FY9/2026 H1: revenue 72.571 bn yen (+10.9% YoY), OP 9.293 bn yen (+36.3%), ordinary 10.094 bn yen (+32.1%), interim net 8.47 bn yen (+73.5%). Upward-revised full-year guidance: revenue 125 bn yen (+2.9%), OP 8.4 bn yen (+4.9%), ordinary 9.5 bn yen (-2.4%), net 6.6 bn yen (+3.3%).

[Why earnings moved] First, the Think-Tank/Consulting segment was strong — H1 segment sales 33.562 bn yen (+16.1%), ordinary 8.431 bn yen (+49.3%). Government DX policy, Digital Agency, defense/economic-security, and energy policy themes drove sustained demand. Second, Mitsubishi-group work plus private-sector DX/AI-strategy advisory. Third, IT-services segment hit by unprofitable projects.

[Why the stock moved] First, H1 already far ahead of the full-year plan pace. Second, scarcity of listed think tanks. Third, stable government-policy work, rising ROE, and Mitsubishi-group backing."""}

C["7595"] = {"jp": """【会社概要】アルゴグラフィックスは「CAD/CAM/PLM(製品ライフサイクル管理)システム」の販売・カスタマイズ・運用支援に特化した中堅IT企業。主要顧客は自動車・電機・電子部品メーカー — DassaultのCATIA、PTCのCreo、Siemens NXなど海外CADの日本市場での代理販売・SIを行う。近年は3社のM&Aでワンストップ体制を強化し、電磁界解析・デジタルツイン・VR/ゲーミングへ事業領域を拡大。

【業績の動き】FY26会社予想は売上737億円(+6.0%)、営業利益107.5億円(+5.4%)、経常利益113.3億円(+3.8%)、純利益75.3億円(+1.1%)を見込む。第3四半期累計(2025年4月-12月)経常利益73.8億円(前年同期比-7.3%)で通期進捗率65.2%と進捗はやや遅れ気味。配当はFY26年間80円(中間60円+期末20円、特別配当含む)で前期比+52.5円の大幅増配を実施 — 配当利回りは約5.5%水準に上昇。

【なぜ業績がこう動いたのか】第一に自動車・電機業界の中長期EV・自動運転投資テーマ — トヨタ・ホンダ系列のEVプラットフォーム再設計、SDV対応で大型案件が継続。第二にPLM需要の継続 — 設計データを社内外で共有して開発期間を短縮する仕組みへの需要は構造的に拡大、ストック型保守収益も増加。第三に半導体・電子部品業界の在庫調整長期化 — 顧客側の設備投資が一部後ろ倒しとなり、Q3進捗を鈍化させた。

【なぜ株価がこう動いたのか】第一に大幅増配(年間80円・利回り約5.5%)発表 — 東証PBR改善要請への対応として高配当銘柄評価が強まった。第二にニッチ市場での独占的ポジション — 日本の製造業向けCAD/PLM代理販売市場で上位シェア、競合参入障壁が高い。第三に進捗鈍化への警戒 — 2025年中は+30%超の上昇局面があったが、Q3進捗65.2%への鈍化と半導体在庫調整懸念で2026年5-6月は一服感(2026/6/4株価1,254円水準)。""",
"en": """[Company Overview] ARGO GRAPHICS is a mid-sized IT firm specializing in selling, customizing, and supporting CAD/CAM/PLM systems. Main customers are automotive, electrical, and electronic-component makers — it distributes overseas CAD platforms (Dassault CATIA, PTC Creo, Siemens NX).

[Earnings Movement] FY26 guidance: revenue 73.7 bn yen (+6.0%), OP 10.75 bn yen (+5.4%), ordinary 11.33 bn yen (+3.8%), net 7.53 bn yen (+1.1%). Q3 YTD ordinary profit 7.38 bn yen (-7.3% YoY), reaching only 65.2% of the full-year plan. Dividend hiked sharply to 80 yen/year (60 interim + 20 year-end, including special), +52.5 yen YoY — dividend yield jumped to about 5.5%.

[Why earnings moved] First, the auto/electrical industries' EV and autonomous-driving theme. Second, sustained PLM demand. Third, prolonged semiconductor / electronic-component inventory adjustment — some customer capex got pushed out.

[Why the stock moved] First, the sharp dividend hike. Second, dominant niche position. Third, wariness about the slowing progress."""}

C["8056"] = {"jp": """【会社概要】BIPROGY(ビプロジー)は2022年4月に旧「日本ユニシス株式会社」から商号変更した大手システムインテグレーター。金融(三井住友銀行、地方銀行)、流通、製造、公共向けにシステム開発・運用受託、ITソリューション、クラウド基盤等を提供。Data&AI Innovation Labで業界別業務シナリオテンプレートを使ったAI業務組込み支援を強化中。

【業績の動き】FY26実績は売上収益4,336.86億円(前年比+7.3%)、営業利益426.04億円(+9.1%)、純利益312.09億円(+15.7%)で4期連続の過去最高益を達成。FY27会社予想は売上4,700億円(+8.4%)、営業利益484億円(+13.6%)、純利益322億円(+3.2%)で5期連続最高益見通し。配当はFY26年間130円(中間60円+期末70円、前期比+20円増配)、FY27予想140円(さらに+10円増配)。配当性向40%以上+自社株買いで還元拡充。

【なぜ業績がこう動いたのか】第一に金融機関のDX需要継続 — メガバンク(主要顧客の三井住友銀行)・地方銀行の基幹システム更改案件が継続的に積み上がった。第二に流通・小売・製造業のシステム再構築需要 — DX案件獲得が拡大、加えてカタリナマーケティングジャパン買収もリテール領域を補強。第三に自社のクラウド/データセンター基盤を活用したサービスがストック型収益として伸び、利益率改善に寄与。

【なぜ株価がこう動いたのか】第一に4期連続(FY27予想で5期連続)の過去最高益 — SI業界の中でも質の高い成長として機関投資家のクオリティ・グロース戦略に合致。アナリスト平均目標株価5,470円、現株価4,686円(2026/5/21)、買いレーティング。第二に大幅増配の継続 — 110円→130円→140円(FY27)と毎期増配し、インカム志向の機関投資家・個人を引きつけた。第三に旧日本ユニシスからのブランドリフレッシュ・米Unisysからの独立性確立 — 独立企業としての評価が高まり、AI/クラウドへの再投資ストーリーが補強された。""",
"en": """[Company Overview] BIPROGY was renamed from 'Nihon Unisys Ltd.' in April 2022 — a major systems integrator providing system development/operations, IT solutions, and cloud infrastructure for finance (SMBC, regional banks), distribution/retail, manufacturing, and public sectors.

[Earnings Movement] FY26 actuals: revenue 433.686 bn yen (+7.3% YoY), OP 42.604 bn yen (+9.1%), net 31.209 bn yen (+15.7%) — fourth consecutive year of record-high earnings. FY27 guidance: revenue 470 bn yen (+8.4%), OP 48.4 bn yen (+13.6%), net 32.2 bn yen (+3.2%). Dividend FY26 130 yen/year, FY27 guide 140 yen.

[Why earnings moved] First, sustained DX demand from financial institutions. Second, retail/distribution/manufacturing system-rebuild demand. Third, services leveraging proprietary cloud/data-center base grew as stock-type revenue.

[Why the stock moved] First, four consecutive years (five with FY27 guide) of record-high earnings — fits institutional quality-growth screens. Analyst average target 5,470 yen, current price 4,686 yen, Buy rating. Second, sustained large dividend hikes. Third, brand refresh from the Nihon Unisys rename and clarified independence from US Unisys."""}

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
