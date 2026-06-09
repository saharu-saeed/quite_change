"""Build the Land Transportation sector JSON data file.

26 listed companies in TOPIX-33 sector 5200 (陸運業 / Land Transportation).
All entries based on FY3/2026 reports + combined-prompt JP web searches per company.

Filter: 売上○ default (revenue-driven sector — fares, parcel volume, e-commerce volume
are real business-quality signals, NOT distorted by commodity prices).
"""
import json
from pathlib import Path

OUT = Path(__file__).parent.parent / 'data' / 'company_research_land_transport_sector.json'

# All 26 companies — each entry has the standard schema
data = {
    "_meta": {
        "sector": "LandTransport",
        "sector_code_topix33": "5200 (陸運業 / Land Transportation)",
        "fiscal_year_target": "FY3/2026",
        "data_vintage": "2026-06 (latest available reports)",
        "filter_default": "売上○",
        "description": "Per-company JP+EN narratives + classification tags for the Land Transportation sector. Revenue-driven sector — default filter is 売上○ (same as IT). FY3/2026 was a strong year: 大阪・関西万博 effect + inbound recovery + post-COVID normalization drove most majors to record results. JR Big 3 + major private railways are mostly R+×S+; some R+×S- on profit-mixed or stock overhang (Tokyu's Shibuya delay, Keisei's special-loss, etc.).",
    },
}

# ──────────────────────────────────────────────────────────────────────────
# R+ × S+ companies (revenue up + stock up)
# ──────────────────────────────────────────────────────────────────────────

data["9020"] = {
    "name": "East Japan Railway (JR East)",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (record results — 6-year revenue / 4-year profit growth streak)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+15-25% (US broker target ¥4,500; dividend ¥74 → ¥84)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** JR東日本(東日本旅客鉄道)は日本最大の鉄道会社で、東北・関東圏の旅客輸送+流通サービス(エキナカ)+不動産+ホテル事業を展開する総合インフラ企業。 **2026年3月期: 売上¥3兆846億円(+6.8%)、営業利益¥4,142億円(+9.9%)、経常¥3,516億円(+9.4%)で6期連続増収・4期連続増益、過去最高水準を更新**。 鉄道運輸収入+4%、駅ナカ店舗売上増、不動産販売も拡大。 Q4単独経常利益は前年比3.9倍の¥496億円、売上営業利益率は3.2%→7.7%へ急改善。 配当は¥70→¥74→¥84(FY27予定)へ大幅増配。\n\n**構造的成長ドライバー:** (1)非鉄道事業(駅ナカ・不動産・ホテル)の中長期成長期待、(2)運賃値上げによる収益改善、(3)伊藤忠都市開発の吸収合併で不動産事業強化、(4)時価総額¥4.2兆円、PER予16.4倍、配当利回り予2.27%。 米系大手証券は強気継続も目標¥4,500円へ若干引下げ。 来期は増収増益だが利益伸び率鈍化見通し。 リスク:鉄道は資本集約的でROEは構造的に低位。",
    "en_summary": "**What happened:** JR East (East Japan Railway) is Japan's largest railway company — passenger transport in Tohoku/Kanto + retail (station shops) + real estate + hotels. **FY3/2026: revenue ¥3.0846 trillion (+6.8%), operating profit ¥414.2 billion (+9.9%), ordinary profit ¥351.6 billion (+9.4%) — 6 consecutive years of revenue growth, 4 consecutive years of profit growth, record-high levels**. Railway transport revenue +4%, station retail growth, real estate sales expansion. Q4 alone ordinary profit +3.9x to ¥49.6 billion, OP margin 3.2% → 7.7% sharp improvement. Dividend ¥70 → ¥74 → ¥84 (FY27 plan).\n\n**Structural drivers:** (1) mid-long-term non-railway growth (station retail / real estate / hotels), (2) fare hike impact, (3) Itochu Urban Development merger strengthens RE, (4) market cap ¥4.2 trillion, PER 16.4x, yield 2.27%. US broker maintains Buy with target ¥4,500. Next year guides for growth but slower profit pace. Risk: railway is capital-intensive — ROE structurally low.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9020 + Nikkei 9020 + minkabu 9020"
}

data["9021"] = {
    "name": "West Japan Railway (JR West)",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (万博 + inbound boost)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+15-30% (3,278 +6.2% on print; dividend ¥84.5 → ¥90.5)",
    "tab": "R+xS+",
    "bucket": "acceleration_rerating",
    "jp_summary": "**何が起きたか:** JR西日本(西日本旅客鉄道)は近畿・中国地方の旅客鉄道+流通+不動産事業を展開。 **2026年3月期: 売上¥1兆8,458億円(+8.1%)、営業利益¥1,980億円(+9.9%)で増収増益**。 H1経常利益+16.8%(¥1,151億円)、Q2単独 経常+27.9%、売上営業利益率11.4%→13.4%へ改善。 **大阪・関西万博効果は運輸収入で約¥70億円、通期で¥200億円(うちインバウンド¥20億円)、営業利益¥150億円押し上げ**。 Q1インバウンド収入¥220億円で過去最高、通期インバウンド運輸¥450億円(+10%)。\n\n**株価への影響:** 増益+増配発表で株価¥3,278(+6.2%)へ急騰。 配当は¥84.5→¥90.5(従来予想¥86から増額)、5円増配。 米国機関投資家は安定キャッシュフロー+広大な不動産資産を高評価。\n\n**構造的成長ドライバー:** (1)円安+ビザ緩和でインバウンド長期成長、(2)複数セグメント(運輸・流通・不動産)の好調、(3)株主還元強化、(4)『観光立国』政策の追い風。",
    "en_summary": "**What happened:** JR West covers Kinki and Chugoku passenger rail + retail + real estate. **FY3/2026: Revenue ¥1.8458 trillion (+8.1%), OP ¥198 billion (+9.9%) — growth in both**. H1 ordinary +16.8% to ¥115.1 billion, Q2 ordinary +27.9%, OP margin 11.4% → 13.4%. **Osaka Expo effect: ~¥7 billion to railway revenue, ¥20 billion full-year (¥2 billion inbound), ¥15 billion OP boost**. Q1 inbound revenue ¥22 billion (record); full-year inbound transport ¥45 billion (+10%).\n\n**Stock impact:** Stock surged to ¥3,278 (+6.2%) on the print + dividend hike. Dividend ¥84.5 → ¥90.5 (raised from prior ¥86). US institutional investors value stable cash flow + extensive real estate.\n\n**Structural drivers:** (1) yen weakness + visa relaxation → long-term inbound growth, (2) multiple segments (transport/retail/RE) all strong, (3) stronger shareholder returns, (4) 'tourism nation' policy tailwind.",
    "source_hint": "Combined-prompt JP web search 2026-06 + Nikkei JR West Expo article + kabutan 9021 + honichi.com 9021"
}

data["9022"] = {
    "name": "Central Japan Railway (JR Central)",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (highest-margin JR, Tokaido Shinkansen)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+15-25% (Tokaido Shinkansen recovery, but Linear delays a structural overhang)",
    "tab": "R+xS+",
    "bucket": "acceleration_rerating",
    "jp_summary": "**何が起きたか:** JR東海(東海旅客鉄道)は東海道新幹線を中核とする日本の鉄道業界で最も収益性の高い企業 — 単独営業利益¥5,663億円、従業員の91.6%が運輸業従事という鉄道集中型ビジネスモデル。 **2026年3月期Q3累計: 売上¥1兆5,141億円(+10.7%)、経常¥6,568億円(+21.4%)、通期経常+20.3%で¥7,809億円**。\n\n**業績ドライバー:** (1)**万博効果で東海道新幹線運輸収入+¥400億円**、(2)Q2インバウンド収入推計¥320億円(前年比+130%)、(3)LINE上予約決済+『推し旅』キャンペーン+貸切車両等の営業施策強化、(4)輸送実績の本格回復。\n\n**構造的優位:** 『稼ぐ力』『儲ける力』で業界最強 — JR東日本より本体利益が大きい。 鉄道事業集中の高収益体質。\n\n**長期リスク:** リニア中央新幹線(品川-名古屋)の工事遅延が大きな投資リスク。 長期投資では慎重判断が必要との指摘。",
    "en_summary": "**What happened:** JR Central is the most profitable railway in Japan — single-entity OP ¥566.3 billion, 91.6% of employees in transport — a rail-centric business model. **Q3 YTD FY3/2026: Revenue ¥1.5141 trillion (+10.7%), ordinary ¥656.8 billion (+21.4%); full-year ordinary +20.3% to ¥780.9 billion**.\n\n**Drivers:** (1) **Expo effect contributed ~¥40 billion to Tokaido Shinkansen revenue**, (2) Q2 inbound revenue ~¥32 billion (+130% YoY), (3) LINE booking + 'Oshi-tabi' campaigns + chartered cars, (4) full-fledged volume recovery.\n\n**Structural edge:** Industry's strongest profit-generating capability — exceeds JR East at single-entity level. High-margin rail-focused model.\n\n**Long-term risk:** Linear Chuo Shinkansen (Tokyo-Nagoya) construction delays are a major investment risk. Long-term thesis requires caution.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9022 + sbbit 9022 + Nikkei 9022"
}

data["9001"] = {
    "name": "Tobu Railway",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (3-year record NP)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+10-15% (steady; FY27 increase + dividend hike planned)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** 東武鉄道は埼玉・栃木・群馬中心の私鉄+レジャー事業(東武動物公園・SLなど)+不動産+流通。 **2026年3月期: 営業収益¥6,554.35億円(+3.8%)、純利益¥556.2億円(+8.4%)で3期連続最高益更新**。 レジャー事業好調、運輸事業は減益。 業績予想・配当予想を上方修正、FY27も増収増益+増配計画。 過去12四半期で純利益率小幅改善、安定した堅実成長。 株主資本政策強化が株価評価を支える。",
    "en_summary": "**What happened:** Tobu Railway operates the Saitama-Tochigi-Gunma private rail + leisure (Tobu Zoo, SL trains) + real estate + retail. **FY3/2026: Revenue ¥655.435 billion (+3.8%), net profit ¥55.62 billion (+8.4%) — 3 consecutive years of record-high NP**. Leisure strong, transport segment down. Upward revisions to guidance and dividend, FY27 plans further growth and dividend hike. 12-quarter net margin slight improvement — steady reliable growth. Strengthened shareholder capital policy supports stock evaluation.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9001 + Nikkei 9001"
}

data["9003"] = {
    "name": "Sotetsu Holdings",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (RE + hotels driving)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+10-15% (steady)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** 相鉄ホールディングス(旧相模鉄道)は神奈川県横浜・湘南エリアの私鉄+不動産+ホテル+流通。 **2026年3月期: 営業収益¥3,075.72億円(+5.3%)、営業利益¥388.33億円(+2.7%)で増収増益**。 不動産分譲業・ホテル業の好調が主要因。 自己資本比率25.0%へ改善。 配当¥65→¥70(+¥5増配)、FY27も¥70維持。\n\n**FY27見通し:** 営業収益¥3,213億円(+4.5%)だが、相鉄新横浜線関連費用増加で営業利益は¥370億円(-4.7%)を見込む — 投資先行による減益局面。",
    "en_summary": "**What happened:** Sotetsu Holdings (formerly Sagami Railway) covers Kanagawa Yokohama-Shonan private rail + real estate + hotels + retail. **FY3/2026: Revenue ¥307.572 billion (+5.3%), OP ¥38.833 billion (+2.7%) — growth in both**. RE subdivision and hotels driving. Equity ratio improved to 25.0%. Dividend ¥65 → ¥70 (+¥5), FY27 maintained at ¥70.\n\n**FY27 outlook:** Revenue ¥321.3 billion (+4.5%), but Sotetsu-Shin-Yokohama line costs drive OP down to ¥37.0 billion (-4.7%) — investment-driven temporary decline.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9003 + Sotetsu IR"
}

data["9007"] = {
    "name": "Odakyu Electric Railway",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (transport recovery)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+5-15% (Nikkei 225 component; analyst target ¥1,792, rating 2.50/5)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** 小田急電鉄は東京-神奈川県中央部の私鉄+不動産+流通+ホテル。 **2026年3月期: 経常利益¥540億円(+7.0%)、交通業の好調で増益**。 総資産¥1兆3,935億円、自己資本比率36.4%。 FY27は不動産業の伸長で増収増益見込み+株主還元強化。 営業利益は2期連続増益。\n\n**構造的課題:** 過去12四半期で純利益率・ROEが低下傾向 — 資本効率の悪化が課題。 成長ドライバーは不動産業の今後の動向に依存。 日経平均構成銘柄でETFフローの影響あり。",
    "en_summary": "**What happened:** Odakyu Electric Railway runs central Tokyo-Kanagawa private rail + RE + retail + hotels. **FY3/2026: Ordinary profit ¥54 billion (+7.0%) — gains from strong transport business**. Total assets ¥1.3935 trillion, equity ratio 36.4%. FY27 guides growth with real estate momentum + stronger shareholder returns. OP up 2 consecutive years.\n\n**Structural concern:** 12-quarter declining net margin / ROE — capital efficiency deteriorating. Growth depends on real estate trajectory. Nikkei 225 constituent — ETF flow impact.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9007 + minkabu 9007"
}

data["9031"] = {
    "name": "Nishi-Nippon Railroad (Nishitetsu)",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (M&A + logistics boost — record streak)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+15-25% (2-year record profit, dividend ¥40 → ¥50)",
    "tab": "R+xS+",
    "bucket": "acceleration_rerating",
    "jp_summary": "**何が起きたか:** 西日本鉄道(西鉄)は福岡・九州地盤の私鉄+物流+不動産+ホテル+ヒノマルグループ(農業資材)を含む多角化企業。 **2026年3月期: 経常利益を従来¥276億円→¥343億円へ24.3%上方修正、+19.4%増益で2期連続最高益**。 純利益¥250億円(+20%、過去最高、従来予想を¥38億円上回る)。 営業収益+7%の¥4,765億円(従来予想¥65億円上回る)。\n\n**業績ドライバー:** (1)**物流業: 売上¥1,104億円(+5.1%)、営業¥39.79億円(+61.0%)** — 国際物流(航空+海運)堅調、(2)**不動産・ホテル**: マンション販売+ホテル単価¥12,853(稼働率77.2%、コロナ前を上回る)、(3)**M&Aヒノマルホールディングス子会社化**(10月)、(4)路線バス減便で人件費削減+投資有価証券売却益。\n\n**福岡・九州地域の構造的成長:** 福岡空港滑走路増設+『ワン・フクオカ・ビルディング』開業 — 半導体関連産業集積で成長著しい福岡経済の追い風。 配当¥40→¥50円(+¥10増配)。 過去12四半期業績改善トレンド、ROE 8-10%超、ROA持続上昇。",
    "en_summary": "**What happened:** Nishi-Nippon Railroad (Nishitetsu) is a Fukuoka/Kyushu-based private rail + logistics + RE + hotels + Hinomaru Group (agricultural materials) diversified company. **FY3/2026: Ordinary profit upward-revised from ¥27.6B to ¥34.3B (+24.3%), +19.4% growth — 2nd consecutive record year**. Net profit ¥25 billion (+20%, record, ¥3.8B above prior guidance). Revenue +7% to ¥476.5 billion (¥6.5B above prior guidance).\n\n**Drivers:** (1) **Logistics: revenue ¥110.4B (+5.1%), OP ¥3.979B (+61.0%)** — international logistics (air+sea) strong, (2) **RE/hotels**: condo sales + hotel ARPU ¥12,853 (occupancy 77.2%, above pre-COVID), (3) **Hinomaru Holdings acquisition** (October), (4) bus route reductions cut labor costs + investment securities gains.\n\n**Structural Fukuoka/Kyushu growth:** Fukuoka Airport runway expansion + 'One Fukuoka Building' opening — tailwind from semiconductor industry clustering. Dividend ¥40 → ¥50 (+¥10). 12-quarter improvement trend, ROE above 8-10%, ROA rising.",
    "source_hint": "Combined-prompt JP web search 2026-06 + Nikkei 9031 + lnews 9031 + logmi 9031"
}

data["9041"] = {
    "name": "Kintetsu Group Holdings",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (万博 + inbound)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+10-15% (under-performing peers; WACC concerns)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** 近鉄グループHDは関西・名古屋圏の私鉄+不動産+ホテル+流通+国際物流の総合企業。 **2026年3月期: 営業収益¥1兆7,503億円(+0.5%)、営業利益¥894億円(+6.0%)、純利益¥537億円(+15.1%)**。 配当¥50→¥60(+¥10増配)。 万博効果+特急『ひのとり』増発で観光・インバウンド堅調、不動産はマンション分譲+中古住宅買取再販、流通は万博オフィシャルストア+あべのハルカス近鉄本店リモデル、国際物流は半導体関連シンガポール新倉庫着工。\n\n**FY27懸念:** 万博反動減見込み — 不動産・国際物流・ホテルレジャー上積みで吸収する想定。 中長期は大阪IR(2030年秋)を起点に奈良・伊勢志摩への送客モデル。 **株価アンダーパフォーム要因:** 金利上昇によるWACC上昇とROIC-WACCスプレッド縮小。 野村絢氏が保有2.7%報告(5/21)で株価反発。",
    "en_summary": "**What happened:** Kintetsu Group HD covers Kansai/Nagoya private rail + RE + hotels + retail + international logistics. **FY3/2026: Revenue ¥1.7503 trillion (+0.5%), OP ¥89.4 billion (+6.0%), NP ¥53.7 billion (+15.1%)**. Dividend ¥50 → ¥60 (+¥10). Expo effect + Hinotori limited express expansion drove tourism/inbound; RE benefited from condo sales + used-house repurchase resale; retail from Expo Official Store + Abeno Harukas Kintetsu Main Store remodel; international logistics started Singapore warehouse for semiconductors.\n\n**FY27 concern:** Expo reaction-decline expected — to be offset by RE/international logistics/hotels growth. Long-term plan ties Osaka IR (Autumn 2030) to Nara/Ise-Shima tourism flow. **Stock underperforming peers** on rising WACC concerns + ROIC-WACC spread contraction. Aya Nomura disclosed 2.7% stake (May 21), triggering rebound.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9041 + Nikkei 9041 + Kintetsu IR"
}

data["9042"] = {
    "name": "Hankyu Hanshin Holdings",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (record results — Q3 OP +20.1%)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+15-25% (Q3 record + Umeda redevelopment momentum)",
    "tab": "R+xS+",
    "bucket": "acceleration_rerating",
    "jp_summary": "**何が起きたか:** 阪急阪神ホールディングスは関西の阪急・阪神両私鉄を中核に不動産+ホテル+娯楽(プロ野球阪神タイガース)+情報通信を展開する関西最大の私鉄持株会社。 **2026年3月期Q3累計: 営業収益¥8,815.04億円(+9.6%)、営業利益¥1,112.43億円(+20.1%)で大幅増収増益、全セグメント増収**。\n\n**業績ドライバー:** (1)不動産好調、(2)旅行セグメント拡大、(3)梅田エリア再開発の継続、(4)阪神タイガース日本一による娯楽収益増。\n\n**FY27懸念:** 万博・プロ野球関連特需の剝落+中東情勢の影響で営業・経常利益は減益見込み — 反動減リスク。 ただし不動産多角化(梅田大阪駅周辺再開発含む)が長期的な成長基盤。",
    "en_summary": "**What happened:** Hankyu Hanshin Holdings is Kansai's largest private rail holdco, centered on Hankyu and Hanshin railways, with RE + hotels + entertainment (pro baseball Hanshin Tigers) + information services. **FY3/2026 Q3 YTD: Revenue ¥881.504 billion (+9.6%), OP ¥111.243 billion (+20.1%) — sharp growth, all segments up**.\n\n**Drivers:** (1) RE strength, (2) travel segment expansion, (3) ongoing Umeda redevelopment, (4) entertainment revenue from Hanshin Tigers championship.\n\n**FY27 concern:** Expo + pro baseball special demand falling away + Middle East impact will drive OP/ordinary decline — reaction-decline risk. But RE diversification (including Umeda Osaka Station redevelopment) is long-term growth base.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9042 + minkabu 9042"
}

data["9044"] = {
    "name": "Nankai Electric Railway",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (record OP — analyst target ¥3,100 Buy)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+25-35% (record Q3, hidden RE value re-rating)",
    "tab": "R+xS+",
    "bucket": "acceleration_rerating",
    "jp_summary": "**何が起きたか:** 南海電気鉄道は大阪・関西国際空港-なんば-和歌山を結ぶ私鉄+不動産+流通+ホテル+M&A(通天閣)。 **2026年3月期Q3累計: 営業収益¥1,953.92億円(+4.4%)、営業利益¥341.71億円(+17.0%)、経常+8.3%、純利益+10.1%で営業収益・各段階利益が過去最高更新**。\n\n**業績ドライバー:** (1)**空港線旅客収入が中韓+東南アジア訪日客で+10.3%増** — 高単価で鉄道収入の約20%、(2)**不動産業: 営業¥353.62億円(+15.4%)、営業利益¥101.22億円(+4.6%)** — ホテル+マンション+セブン-イレブン駅ナカ、(3)**通天閣運営会社子会社化のM&A効果**。\n\n**含み資産の再評価:** **関西国際空港-なんば直結の唯一無二路線網**+創業以来保有のなんば周辺膨大な不動産含み益 — 円安インバウンド+インフレ実物資産見直しというマクロ環境変化で『強烈な輝き』。 南海難波駅は高島屋・なんばCITY・なんばパークス等を直結 — 実質『南海の街』を形成。\n\n**戦略:** なにわ筋線開業に向けた戦略投資+M&Aで大家業→総合不動産事業へ脱却。 配当年¥40→¥50(+25%増)。 **アナリスト評価:** 強気買い、平均目標¥3,100(+21.9%上値余地)。",
    "en_summary": "**What happened:** Nankai Electric Railway connects Osaka–Kansai Airport–Namba–Wakayama private rail + RE + retail + hotels + M&A (Tsutenkaku). **FY3/2026 Q3 YTD: Revenue ¥195.392 billion (+4.4%), OP ¥34.171 billion (+17.0%), ordinary +8.3%, NP +10.1% — revenue and all profit levels at record highs**.\n\n**Drivers:** (1) **Airport line passenger revenue +10.3%** from China/Korea/SE-Asia inbound — high ARPU, ~20% of rail revenue, (2) **RE: revenue ¥35.362 billion (+15.4%), OP ¥10.122 billion (+4.6%)** — hotels + condos + 7-Eleven station-shops, (3) **Tsutenkaku operator acquisition**.\n\n**Hidden asset re-rating:** **Unique route directly linking Kansai International Airport to Namba** + massive unrealized RE gains around Namba — under yen weakness + inflation, 'shining brightly.' Nankai-Namba Station connects directly to Takashimaya, Namba CITY, Namba Parks — essentially 'Nankai's city.'\n\n**Strategy:** Naniwasuji Line strategic investment + M&A to shift from landlord to comprehensive RE business. Dividend ¥40 → ¥50 (+25%). **Analyst rating:** Strong Buy, target ¥3,100 (+21.9% upside).",
    "source_hint": "Combined-prompt JP web search 2026-06 + Nikkei 9044 + diamond 9044 + note 9044 article"
}

data["9045"] = {
    "name": "Keihan Holdings",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (5-year record streak, dividend +¥49)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+15-25% (5 consecutive record years, major dividend hike)",
    "tab": "R+xS+",
    "bucket": "acceleration_rerating",
    "jp_summary": "**何が起きたか:** 京阪ホールディングスは京都-大阪を結ぶ私鉄+流通+不動産+ホテル。 **2026年3月期: 全セグメント増収増益、営業収益¥3,324.71億円(+6.0%)、営業利益¥491.52億円(+16.8%)で過去最高更新、5期連続増収・増益**。\n\n**業績ドライバー:** (1)不動産開発+ホテル事業好調、(2)インバウンド需要回復、(3)自己資本比率37.5%へ改善。\n\n**配当大幅増額:** **年間配当¥40→¥89(+¥49、+122.5%増配)** — 5期連続増収増益を背景に株主還元を大幅強化。 ROE 8-10%付近、過去12四半期は業績改善トレンド、収益性安定。 多角的収益源+安定配当政策が機関投資家評価を押し上げ。",
    "en_summary": "**What happened:** Keihan Holdings runs the Kyoto-Osaka private rail + retail + RE + hotels. **FY3/2026: All segments grew, revenue ¥332.471 billion (+6.0%), OP ¥49.152 billion (+16.8%) — record-high, 5 consecutive years of revenue + profit growth**.\n\n**Drivers:** (1) RE development + hotels strong, (2) inbound recovery, (3) equity ratio improved to 37.5%.\n\n**Major dividend hike:** **Annual dividend ¥40 → ¥89 (+¥49, +122.5%)** — 5-year record streak underpins major shareholder return strengthening. ROE around 8-10%, 12-quarter improvement trend, profitability stable. Diversified revenue + stable dividend policy lifting institutional ratings.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9045 + Keihan IR"
}

data["9052"] = {
    "name": "Sanyo Electric Railway",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (Q3 NP +42%)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+15-25% (record-high QoQ improvement)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** 山陽電気鉄道は神戸-姫路間の私鉄+不動産+流通。 阪神電鉄(阪急阪神HD)と相互乗り入れし、関西経済圏の鉄道網の一部を担う。 **2026年3月期Q3決算: 増収増益、純利益+42.0%の¥35.42億円(退職給付制度改定による特別利益寄与)**。 通期業績予想を上方修正、運輸業の増収が中核。\n\n**構造的成長基盤:** (1)阪神電鉄相互乗り入れによる神戸都心-姫路の直通アクセス、(2)沿線開発の継続、(3)自己資本比率上昇+増配で財務健全性強化。 過去12四半期で純利益率上昇傾向、営業利益率も持ち直し。",
    "en_summary": "**What happened:** Sanyo Electric Railway runs the Kobe-Himeji private rail + RE + retail. Reciprocal through-service with Hanshin Electric Railway (Hankyu-Hanshin HD) connects to Kansai economic zone rail network. **FY3/2026 Q3: Revenue + profit growth; NP +42.0% to ¥3.542 billion (boosted by retirement benefit accounting change)**. Full-year guidance upward-revised; railway revenue growth is core.\n\n**Structural growth base:** (1) Direct Kobe-Himeji access via Hanshin through-service, (2) ongoing line-side development, (3) equity ratio rising + dividend hike strengthening finances. 12-quarter net margin uptrend, OP margin recovering.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9052 + minkabu 9052"
}

data["9069"] = {
    "name": "SENKO Group Holdings",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (M&A-driven 1兆円 plan)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+10-15% (steady; on track to ¥1T revenue)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** センコーグループHDは総合物流大手 — 既存事業深掘り+新規事業推進の『両利き経営』+積極的M&A戦略が特徴。 **2026年3月期: 営業収益¥8,996.2億円(+5.3%)、営業利益¥369.96億円(+5.9%)、経常+4.4%で増収増益**。\n\n**FY27予想: 営業収益¥1.02兆円(+13.4%)、営業利益¥430億円(+16.2%)で『1兆円企業』到達見込み**。\n\n**M&A実績(2025-2026):** (1)PDS International(インド・4月、通関・国内輸送)、(2)Total Fresh Connection(シンガポール・11月)、(3)丸運(2026年3月、貨物輸送)。 5カ年中期計画で物流M&A¥250億円・非物流M&A¥232億円投資済み。 売上¥1兆円・営業利益¥450億円・利益率4.5%が目標。",
    "en_summary": "**What happened:** SENKO Group Holdings is a major comprehensive logistics player — 'ambidextrous management' (deepening existing + new business) + aggressive M&A. **FY3/2026: Revenue ¥899.62 billion (+5.3%), OP ¥36.996 billion (+5.9%), ordinary +4.4% — growth in both**.\n\n**FY27 guide: Revenue ¥1.02 trillion (+13.4%), OP ¥43 billion (+16.2%) — hitting the '¥1 trillion company' milestone**.\n\n**M&A track record (2025-2026):** (1) PDS International (India, April — customs/domestic transport), (2) Total Fresh Connection (Singapore, November), (3) Maru Un (March 2026, cargo transport). 5-year mid-term plan invested ¥25 billion in logistics M&A + ¥23.2 billion in non-logistics. Targets: ¥1 trillion revenue, ¥45 billion OP, 4.5% margin.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9069 + maonline 9069 + daily-cargo 9069"
}

data["9072"] = {
    "name": "NIKKON Holdings",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (Honda anchor + warehouse expansion)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+74.6% YoY, +223.5% 2-year — dramatic re-rating",
    "tab": "R+xS+",
    "bucket": "acceleration_rerating",
    "jp_summary": "**何が起きたか:** ニッコンホールディングス(日本梱包運輸倉庫)は自動車輸送+梱包+倉庫の総合物流企業。 **本田技研工業向け主力**で梱包事業で高収益。 **2026年3月期: 売上¥2,698.62億円(+8.9%)、営業利益¥238.18億円(+2.9%)で全セグメント増収**。 経常利益¥248.53億円(+3.7%)でアナリスト予想¥245.33億円を上回る着地。\n\n**業績ドライバー:** (1)倉庫の新増設で保管貨物量増加、(2)運送事業好調、(3)料金改定+業務量増加。\n\n**驚異的な株価上昇:** **株価は1年前比+74.59%、2年前比+223.49%** — 物流セクター内でも稀有な再評価。 第13次中期経営計画で『既存事業効率化』+『成長ドライバー確立』を掲げる。 配当増額予定。 課題: 営業利益率の低下傾向 — コスト管理が次の焦点。",
    "en_summary": "**What happened:** NIKKON Holdings (Nihon Konpou Unyu Soko) is an integrated logistics company combining auto transport + packaging + warehousing. **Honda Motor is the anchor customer**; packaging business is high-margin. **FY3/2026: Revenue ¥269.862 billion (+8.9%), OP ¥23.818 billion (+2.9%) — all segments grew**. Ordinary profit ¥24.853 billion (+3.7%) beat analyst consensus of ¥24.533 billion.\n\n**Drivers:** (1) Warehouse new construction expanded storage volumes, (2) transport business strong, (3) rate revisions + volume growth.\n\n**Dramatic stock re-rating:** **Stock +74.59% YoY, +223.49% over 2 years** — exceptional within the logistics sector. 13th mid-term plan emphasizes 'existing business efficiency' + 'establishing growth drivers.' Dividend hike planned. Concern: OP margin trending down — cost management is the next focus.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9072 + Nikkon IR + finance.logmi 9072"
}

data["9066"] = {
    "name": "Nissin Corporation",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (international logistics + EC + semiconductor warehouses)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+10-20% (PER 10.92x, PBR 1.37x — fair-value re-rating)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** 日新は国際物流(航空+海運)+倉庫+陸上輸送を手がける総合物流企業。 **2025年3月期H1: 売上¥934.52億円(+13.5%)、営業利益¥45.43億円(+10.1%)で増収増益**。 物流事業売上¥883.55億円(+12.9%)、セグメント利益¥35.78億円(+3.2%)。\n\n**業績ドライバー:** (1)自動車関連貨物+食品+化学品取扱が堅調、(2)海上貨物の輸出入順調、(3)航空輸出食品+輸入医薬品堅調、(4)**倉庫業務でEC関連貨物の新規取扱開始**、(5)**熊本県での新倉庫建設による半導体関連貨物対応** — TSMC熊本工場関連の物流ハブ。\n\n**市場評価:** 時価総額¥1,250億円、PER 10.92倍、PBR 1.37倍 — 適度な評価水準。",
    "en_summary": "**What happened:** Nissin is an integrated logistics company in international (air + sea) + warehousing + land transport. **FY3/2025 H1: Revenue ¥93.452 billion (+13.5%), OP ¥4.543 billion (+10.1%) — growth in both**. Logistics revenue ¥88.355 billion (+12.9%), segment profit ¥3.578 billion (+3.2%).\n\n**Drivers:** (1) Auto-related + food + chemical cargo strong, (2) ocean export-import smooth, (3) air-export foods + import pharmaceuticals strong, (4) **new EC cargo handling started in warehousing**, (5) **new Kumamoto warehouse for semiconductor cargo** — logistics hub tied to TSMC Kumamoto plant.\n\n**Market eval:** Market cap ¥125 billion, PER 10.92x, PBR 1.37x — reasonable valuation.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9066 + Nissin IR"
}

data["9090"] = {
    "name": "AZ-COM Maruwa Holdings",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (3PL + cold-chain + last-mile)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+10-20% (steady growth, FY27 increase guided)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** AZ-COM丸和ホールディングス(旧丸和運輸機関)は小売業向け3PL+低温食品物流に強みを持つ物流企業。 **個人事業主を束ねた『桃太郎便』宅配でラストワンマイル事業展開**。 **2026年3月期: 売上¥2,305.31億円(+10.6%)、営業利益¥118.64億円(+8.3%)で増収増益**。\n\n**業績ドライバー:** (1)新規物流センター開設、(2)取引先増加による取扱物量増加、(3)桃太郎便の新規配送エリア獲得+稼働台数増。\n\n**FY27見通し:** 外部環境変化を踏まえた構造改革加速+IT/DX投資+法改正・リスク対応投資の前倒し実行で増収増益見込み — 投資先行型の成長フェーズ。",
    "en_summary": "**What happened:** AZ-COM Maruwa Holdings (formerly Maruwa Unyu Kikan) specializes in retail-focused 3PL + cold-chain food logistics. **The 'Momotaro Bin' last-mile parcel service uses an individual-contractor model**. **FY3/2026: Revenue ¥230.531 billion (+10.6%), OP ¥11.864 billion (+8.3%) — growth in both**.\n\n**Drivers:** (1) New logistics center openings, (2) expanded client base lifting volumes, (3) Momotaro Bin's new delivery area expansion + active vehicle growth.\n\n**FY27 outlook:** Structural reform acceleration responding to environmental changes + IT/DX investment + early implementation of regulation-response investment supports growth guidance — front-loaded investment growth phase.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9090 + AZ-COM Maruwa IR"
}

data["9147"] = {
    "name": "NIPPON EXPRESS Holdings (NX HD)",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "all-three-up (international logistics + rate hikes)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+5-15% (analyst target ¥3,620 +11.8% upside; ¥1T海外plan)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** NIPPON EXPRESSホールディングス(日本通運/NX)は日本最大級の総合物流企業 — 国内陸海空物流+グローバル物流ネットワーク。 **2026年12月期Q1: 売上¥6,523億円(+1.1%)、営業利益¥149億円(+32.3%)、純利益¥45億円(+287.3%大幅増益)**。 FY12/2026通期予想: **売上¥2.7兆円(+4.9%)、営業利益¥1,000億円(+94.2%大幅増益)、純利益¥600億円**。\n\n**業績ドライバー:** (1)航空・海運貨物の堅調回復+料金改定、(2)**海外売上拡大戦略** — 2024年海外売上¥9,864億円(2021年比+40%)、(3)グローバル物流M&A推進。\n\n**長期戦略:** **海外売上¥5,855億円→5年で¥1.2兆円へ倍増目標**、M&A寄与を¥3,700億円に設定。 グループ全体売上¥3兆円へ。\n\n**市場評価:** PBR 1.37倍、ROE/ROIC が資本コストをわずか上回る水準 — 『事業はグローバル、利益はまだ国内』の成長過渡期バリュー銘柄。 アナリスト判断:強気買い3、買い1、中立5、平均目標¥3,620(+11.76%上値余地)。 日本マスタートラスト信託銀行が筆頭株主14.57%保有。 注意: 米関税影響でFY25見通し下方修正済み。",
    "en_summary": "**What happened:** NIPPON EXPRESS Holdings (Nittsu/NX) is one of Japan's largest comprehensive logistics companies — domestic land/sea/air logistics + global network. **FY12/2026 Q1: Revenue ¥652.3 billion (+1.1%), OP ¥14.9 billion (+32.3%), NP ¥4.5 billion (+287.3%, dramatic growth)**. Full-year FY12/2026 guide: **revenue ¥2.7 trillion (+4.9%), OP ¥100 billion (+94.2% dramatic growth), NP ¥60 billion**.\n\n**Drivers:** (1) Air/sea cargo recovery + rate revisions, (2) **overseas revenue expansion strategy** — 2024 overseas revenue ¥986.4 billion (+40% vs 2021), (3) global logistics M&A.\n\n**Long-term plan:** **Overseas revenue ¥585.5 billion → ¥1.2 trillion in 5 years (double)**, with M&A contribution set at ¥370 billion. Group-wide revenue target ¥3 trillion.\n\n**Market eval:** PBR 1.37x, ROE/ROIC slightly above capital cost — 'business is global, profit still domestic' value-name in growth transition. Analyst rating: 3 strong-buy + 1 buy + 5 neutral, target ¥3,620 (+11.76% upside). Master Trust Bank of Japan top equity holder at 14.57%. Note: US tariffs caused FY25 downward revision.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9147 + Nikkei 9147 + NX IR + cargo-news 9147"
}

# ──────────────────────────────────────────────────────────────────────────
# R+ × S- companies (revenue up but profit-mixed or stock-down)
# ──────────────────────────────────────────────────────────────────────────

data["9005"] = {
    "name": "Tokyu Corporation",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "down", "net_dir": "up", "stock_dir": "down",
    "biz_classification": "mixed (rev up, OP slightly down, NP up; stock down on Shibuya delay)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "**-19.2% past 3 months (¥1,998 Feb → ¥1,614 May 2026)**",
    "tab": "R+xS-",
    "bucket": "profit_compressed",
    "jp_summary": "**何が起きたか:** 東急は私鉄最大の乗客数+渋谷・沿線の都市再開発が成長エンジン。 **2026年3月期: 営業収益¥1兆861.79億円(+3.0%)、営業利益¥1,031.93億円(-0.3%)、純利益¥870.71億円(+9.3%)** — 売上は微増、営業利益はほぼ横ばい、純利益のみ増益。 交通+ホテル・リゾート好調、不動産は前期大型物件販売の反動減。\n\n**株価は急落:** **2026年2/27 ¥1,998 → 5/27 ¥1,614 へ -19.2%下落**。 業績改善とは逆方向 — **R+×S-の典型的なパターン**。\n\n**なぜ株価は下落したのか — 構造的要因:** (1)**渋谷再開発の完成予定が2027年→2034年へ7年延期** — 最大の成長ストーリーが大きく揺らぐ、(2)**通勤定期収入の構造的減少**(リモートワーク定着) — 安定収入源が長期的に減少、(3)将来成長への期待値が大きく引き下げられた。 **米系大手証券は強気維持・目標¥2,510**だが、決算発表時点での評価で、市場の懸念を完全には反映していない可能性。\n\n**長期的には**: 交通利用者増+不動産・ホテルレジャー継続成長で来期増収増益見込み。 渋谷再開発が完成すれば長期的な評価是正の可能性。",
    "en_summary": "**What happened:** Tokyu Corporation has the largest passenger count among private railways + Shibuya line-side urban redevelopment as its growth engine. **FY3/2026: Revenue ¥1.08617 trillion (+3.0%), OP ¥103.193 billion (-0.3%), NP ¥87.071 billion (+9.3%)** — revenue slightly up, OP roughly flat, NP up. Transport + hotels/resorts strong; RE reaction-decline from prior-year large transactions.\n\n**Stock plunged:** **Down -19.2% past 3 months (¥1,998 Feb 27 → ¥1,614 May 27, 2026)**. Opposite direction to fundamental improvement — **classic R+×S- pattern**.\n\n**Why did the stock fall — structural reasons:** (1) **Shibuya redevelopment completion pushed back from 2027 to 2034 — 7-year delay** of the biggest growth narrative, (2) **structural decline in commuter pass revenue** (remote work entrenched) — stable income source declining long-term, (3) forward growth expectations significantly cut. **US broker maintains Buy with ¥2,510 target** — though that's earnings-time evaluation, may not fully reflect subsequent concerns.\n\n**Long-term:** Transport ridership growth + RE / hotels-leisure ongoing growth points to next-year revenue + profit growth guidance. If Shibuya redevelopment completes, long-term re-rating possible.",
    "source_hint": "Combined-prompt JP web search 2026-06 + Tokyu FY3/2026 IR doc + note denchan article + LIMO 9005 + minkabu 9005"
}

data["9008"] = {
    "name": "Keio Corporation",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "down", "net_dir": "down", "stock_dir": "up",
    "biz_classification": "mixed (rev up, profit slightly down — but capital-return reaction strong)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+10-20% (5-for-1 split + buyback + dividend ¥100 → ¥110)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** 京王電鉄は新宿-八王子-多摩エリアの私鉄+不動産+ホテル+流通(京王百貨店)。 **2026年3月期Q3: 営業収益¥3,601.63億円(+7.6%)で増収だが、営業利益¥481.18億円(-2.9%)で減益**。 通期予想は売上¥5,020億円(+10.8%)、営業¥510億円(-5.8%)、純利益¥420億円(-2.0%)。\n\n**業績ドライバー:** 不動産販売業+ホテル業が業績牽引、事業別ROA管理導入。\n\n**強力な株主還元策で株価は上昇:** **配当¥100→¥110(+¥10増配)+自社株買い+1株を5株への株式分割発表** — 株式分割により個人投資家の参入容易化+流動性向上。 PBR 1倍前後で東証PBR改善要請への対応。 **新宿駅西南口地区再開発**プロジェクトで100年先を見据えた成長戦略。 国内大手証券は目標株価引き上げ。\n\n**バリュー投資の代表格:** PER割安+PBR改善期待+株主還元強化で割安株(バリュー)選好の投資家ポートフォリオに組み入れ。",
    "en_summary": "**What happened:** Keio Corporation runs the Shinjuku-Hachioji-Tama private rail + RE + hotels + retail (Keio Department Store). **FY3/2026 Q3: Revenue ¥360.163 billion (+7.6%) — up, but OP ¥48.118 billion (-2.9%) — down**. Full-year guide: revenue ¥502 billion (+10.8%), OP ¥51 billion (-5.8%), NP ¥42 billion (-2.0%).\n\n**Drivers:** RE sales + hotels led; segment ROA management introduced.\n\n**Stock UP on strong capital returns:** **Dividend ¥100 → ¥110 (+¥10) + buyback + 1-to-5 stock split announced** — split makes shares accessible to retail + boosts liquidity. PBR ~1.0 — TSE PBR-improvement request response. **Shinjuku Station Southwest Exit district redevelopment** — '100-year forward' growth strategy. Domestic broker raised target.\n\n**Value-stock favorite:** PER discount + PBR improvement potential + strengthened shareholder returns make this a portfolio addition for value-oriented investors.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9008 + Nikkei 9008 + diamond ZAi 9008"
}

data["9009"] = {
    "name": "Keisei Electric Railway",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "down", "net_dir": "down", "stock_dir": "down",
    "biz_classification": "mixed (rev up, OP/NP down — Oriental Land equity overhang)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "Range-bound to down (NP -31.4% is severe)",
    "tab": "R+xS-",
    "bucket": "profit_compressed",
    "jp_summary": "**何が起きたか:** 京成電鉄は東京-成田空港-千葉エリアの私鉄+不動産+流通+運輸(成田空港アクセス)。 オリエンタルランド(東京ディズニーリゾート)株式の大株主としても知られる。 **2026年3月期: 営業収益¥3,324億円(+4.1%)で増収、営業利益¥339億円(-5.6%)で減益、純利益¥480億円(-31.4%で大幅減益)**。\n\nQ3決算は増収減益、特別損失等の影響で純利益が大きく下振れ。\n\n**構造的課題:** (1)運輸業の増収にもかかわらず減益、(2)次期も減益予想、(3)過去12四半期はやや弱含み — 純利益率・ROE・ROAが前年同期比低下、(4)売上拡大が収益に十分つながっていない。\n\n**市場評価:** PER予14.6倍、PBR実1.16倍、配当利回り予1.40% — 比較的低調。 配当は増配予定で株主還元には注力。 オリエンタルランド株式売却益等の特殊要因が業績変動の主因となる構造で、本業の収益性向上が市場の課題認識。",
    "en_summary": "**What happened:** Keisei Electric Railway runs the Tokyo-Narita Airport-Chiba private rail + RE + retail + transport (Narita Airport access). Also known as a major shareholder of Oriental Land (Tokyo Disney Resort). **FY3/2026: Revenue ¥332.4 billion (+4.1%) up, OP ¥33.9 billion (-5.6%) down, NP ¥48.0 billion (-31.4% sharp decline)**.\n\nQ3 was revenue up, profit down — extraordinary losses dragged NP sharply lower.\n\n**Structural concerns:** (1) Transport segment grew revenue but operations still declined, (2) next-year also guided down, (3) 12 quarters of soft trend — net margin/ROE/ROA all declining YoY, (4) revenue expansion not flowing to profit adequately.\n\n**Market eval:** PER 14.6x, PBR 1.16x, yield 1.40% — relatively muted. Dividend hike planned to strengthen shareholder returns. Oriental Land equity sales gains and other extraordinary factors are major earnings drivers — core profitability improvement is the market's concern.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9009 + minkabu 9009"
}

data["9024"] = {
    "name": "Seibu Holdings",
    "sector_code": "LandTransport",
    "rev_dir": "down", "op_dir": "down", "net_dir": "down", "stock_dir": "down",
    "biz_classification": "all-three-down (large RE liquidation reaction-decline)",
    "filter_qualifies": [],
    "stock_yoy_estimate": "Range-bound to down (reaction-decline year)",
    "tab": "R+xS-",
    "bucket": "profit_compressed",
    "jp_summary": "**何が起きたか:** 西武ホールディングスは埼玉・東京西部の私鉄(西武鉄道)+不動産(西武不動産)+ホテル・レジャー(プリンスホテル等)+スポーツ事業(西武ライオンズ)。 **2026年3月期: 前期の大型不動産流動化の反動で大幅減収減益**。 H1経常利益-2.2%の¥295億円。\n\n**減益の中の明るい点:** ホテル・レジャー事業+都市交通・沿線事業は堅調推移、自己資本比率改善。\n\n**注: 実質的にはR-(売上減)でR+の定義からは外れるが、本書では『前期大型不動産流動化の反動』という特殊要因を理解しやすくするため掲載**。 過去12四半期で純利益率・営業利益率・ROE・ROAが大幅低下 — 反動減局面の弱さが顕著。\n\n**FY27見通し:** 各事業での施策により増収増益見込み + 安定した株主還元継続方針 — 反動減後の正常化を期待。",
    "en_summary": "**What happened:** Seibu Holdings runs the Saitama/west Tokyo private rail (Seibu Railway) + RE (Seibu Real Estate) + hotels/leisure (Prince Hotels etc.) + sports (Seibu Lions). **FY3/2026: Sharp revenue + profit decline due to reaction-decline from prior-year large real estate liquidations**. H1 ordinary -2.2% to ¥29.5 billion.\n\n**Bright spots within the decline:** Hotels/leisure + urban transport / line-side businesses steady, equity ratio improving.\n\n**Note: Technically R- (revenue down) — outside the strict R+ definition. Included here to make the 'reaction-decline from prior-year large RE liquidation' special-factor visible**. 12-quarter sharp decline in net margin/OP margin/ROE/ROA — reaction-decline phase weakness is evident.\n\n**FY27 outlook:** Initiatives across each business expected to drive revenue + profit growth, sustained shareholder returns — normalization expected post-reaction.",
    "source_hint": "Combined-prompt JP web search 2026-06 + Seibu IR + kabutan 9024 + minkabu 9024"
}

data["9006"] = {
    "name": "Keikyu Corporation",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "down", "net_dir": "up", "stock_dir": "up",
    "biz_classification": "mixed (rev up, OP down, NP up on extraordinary items)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "+5-15% (steady; FY27 guides increase)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** 京浜急行電鉄(京急)は東京-横浜-羽田空港-三浦半島の私鉄+不動産+流通+ホテル+バス。 羽田空港アクセスを担う重要路線。 **2026年3月期: 営業収益¥3,041.92億円(+3.5%)で増収だが、営業利益¥335.53億円(-5.9%)で減益。 ただし特別利益計上で純利益¥274.92億円(+13.1%)で増益達成**。\n\n**FY27は増収増益見込み:** 不動産事業での不動産流動化による売却益+分譲マンション販売の増加が成長ドライバー。\n\n**構造的成長余地:** 京急は沿線の再開発余地が大きい — 不動産事業による将来的な利益拡大の可能性が投資家の期待を支える。 羽田空港利用増+インバウンドが長期的追い風。",
    "en_summary": "**What happened:** Keikyu Corporation runs the Tokyo-Yokohama-Haneda Airport-Miura Peninsula private rail + RE + retail + hotels + buses. Important Haneda Airport access line. **FY3/2026: Revenue ¥304.192 billion (+3.5%) up, but OP ¥33.553 billion (-5.9%) down. However, extraordinary gains brought NP to ¥27.492 billion (+13.1%) — net profit growth**.\n\n**FY27 guides growth:** RE liquidation gains + condo sales growth as drivers.\n\n**Structural growth runway:** Keikyu has significant line-side redevelopment headroom — RE-driven future profit expansion supports investor expectations. Haneda traffic growth + inbound a long-term tailwind.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9006 + minkabu 9006"
}

data["9048"] = {
    "name": "Meitetsu (Nagoya Railroad)",
    "sector_code": "LandTransport",
    "rev_dir": "flat", "op_dir": "down", "net_dir": "down", "stock_dir": "down",
    "biz_classification": "mixed (rev marginal, OP -14%, NP -39% — adjustment phase)",
    "filter_qualifies": [],
    "stock_yoy_estimate": "Range-bound (Nagoya redevelopment delayed)",
    "tab": "R+xS-",
    "bucket": "profit_compressed",
    "jp_summary": "**何が起きたか:** 名古屋鉄道は名古屋・東海地方の私鉄+不動産+レジャー+ホテル。 **2026年3月期: 営業収益¥6,915.83億円で微増、営業利益¥361.85億円(-14.0%)で減益、純利益¥229.54億円(-39.2%大幅減益)** — 人件費+減価償却費の増加、持分法投資利益の減少などが影響。\n\n**FY27予想は大幅な回復見込み:** 営業収益¥7,340億円(+6.1%)、営業利益¥450億円(+24.4%)、純利益¥390億円(+69.9%) — 運送事業収支改善+特別損益改善。\n\n**配当:** FY27予想¥60円(増配)、連結配当性向30%以上+年間¥60下限配当の新方針。\n\n**構造的懸念:** (1)成長の柱と位置付けた**名古屋駅地区再開発計画が人手不足・資材高騰でスケジュール未定** — 中計開始早々から大きな見直し、(2)過去12四半期はやや弱含み横ばい — 営業利益率・純利益率低下、(3)ROE・ROAが目安未達。 『成長基盤構築・収益力強化期』 — 構造改革+運送事業改善が焦点。",
    "en_summary": "**What happened:** Meitetsu (Nagoya Railroad) runs Nagoya/Tokai-area private rail + RE + leisure + hotels. **FY3/2026: Revenue ¥691.583 billion marginal, OP ¥36.185 billion (-14.0%) down, NP ¥22.954 billion (-39.2% sharp decline)** — labor costs + depreciation up, equity-method investment income down.\n\n**FY27 guide significant recovery:** Revenue ¥734 billion (+6.1%), OP ¥45 billion (+24.4%), NP ¥39 billion (+69.9%) — transport business improvement + extraordinary items recovery.\n\n**Dividend:** FY27 ¥60 (increase), with 30%+ payout ratio + ¥60 minimum-floor new policy.\n\n**Structural concerns:** (1) **Nagoya Station district redevelopment plan suspended due to labor shortage / material cost inflation** — major revision early in mid-term plan, (2) 12-quarter soft trend — OP/net margin declining, (3) ROE/ROA below benchmark. 'Growth-base building / profit-strength enhancement period' — structural reform + transport improvement is the focus.",
    "source_hint": "Combined-prompt JP web search 2026-06 + Meitetsu IR + kabutan 9048 + minkabu 9048"
}

data["9064"] = {
    "name": "Yamato Holdings",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "up", "net_dir": "down", "stock_dir": "down",
    "biz_classification": "mixed (revenue up + OP +99%, but NP -64% + downward revision later)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "Range-bound to down (FY25 downward revision NP -60%)",
    "tab": "R+xS-",
    "bucket": "profit_compressed",
    "jp_summary": "**何が起きたか:** ヤマトホールディングスは『クロネコヤマト』ブランドで知られる宅急便の最大手。 **2026年3月期: 売上¥1兆8,656.75億円(+5.8%)、営業利益¥283.04億円(+99.2%大幅増)、経常¥262.58億円(+34.1%)、純利益¥136.62億円(-64.0%大幅減)** — 売上+営業利益は急回復だが、純利益は大幅減少という複雑な構造。\n\n**増益の理由:** 小口法人・個人顧客の宅急便取扱数量拡大+大口法人プライシング適正化+法人向けビジネス拡大。 **プライシング適正化で営業利益+¥297億円の効果**。\n\n**注意 - 業績見通しの下方修正:** 2026年3月期Q3決算で通期経常利益を従来¥400億円→¥270億円に**32.5%下方修正** — 取扱数量減少が影響。 中計目標も大幅下方修正。 株価はこれを織り込み軟調推移。\n\n**長期戦略:** 収益構成変革+付加価値プライシング+法人ビジネス強化+拠点戦略+輸送効率化+変動費管理で利益成長へ。 **R+×S-に分類:** 売上は伸びているが、利益面の不安定さ+下方修正による株価下落というパターン。",
    "en_summary": "**What happened:** Yamato Holdings, known for the 'Kuroneko Yamato' brand, is Japan's largest parcel delivery company. **FY3/2026: Revenue ¥1.865675 trillion (+5.8%), OP ¥28.304 billion (+99.2% sharp gain), ordinary ¥26.258 billion (+34.1%), NP ¥13.662 billion (-64.0% sharp decline)** — revenue + OP recovered sharply but NP fell dramatically — a complex picture.\n\n**Why profit grew:** Small business + retail customer parcel volume expansion + large-account pricing rationalization + B2B business expansion. **Pricing rationalization created +¥29.7 billion OP effect**.\n\n**Note — guidance downgrade:** Q3 result revised full-year ordinary profit from ¥40 billion to ¥27 billion (**-32.5% revision**) — volume decline. Mid-term plan also revised down sharply. Stock has been pricing this in (range-bound to down).\n\n**Long-term strategy:** Revenue mix transformation + premium pricing + B2B strengthening + facility strategy + transport efficiency + variable-cost management. **R+×S- classification:** Revenue grew but profit volatility + guidance cut drove stock down.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9064 + Nikkei 9064 + Yamato IR + lnews 9064 + diamond 9064"
}

data["9065"] = {
    "name": "Sankyu Inc.",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "down", "net_dir": "up", "stock_dir": "flat-to-up",
    "biz_classification": "mixed (rev up, OP/经常 down, NP up — logistics + heavy industry mix)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "Steady (PER 13.4x, dividend ¥232 → ¥236)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** 山九は重工業向け物流(製鉄所・化学プラント関連)+機工事業(工場建設・メンテナンス)+海外物流を展開する物流・エンジニアリング企業。 **2026年3月期: 売上¥6,315.73億円(+4.1%)、営業利益¥432.40億円(-1.6%)、経常¥433.85億円(-2.9%)、純利益+5.9%(Q3時点)**。\n\nQ3売上¥4,723.76億円(+3.7%)、純利益¥235.99億円(+5.9%)で増収・最終利益増。\n\n**セグメント別:** **物流事業利益+7.4%**、機工事業-5.9%。\n\n**機工事業の今後:** メンテナンスでは春・秋のSDM(定期修理)工事量が想定上回り、設備工事では大型工場構内工事+環境関連工事獲得が見込まれる。\n\n**配当・市場評価:** 配当¥232→¥236(+¥4増配)、配当性向約40%。 時価総額¥4,436億円、PER予13.42倍、PBR 1.39倍。 過去2年平均増収率5.86%。",
    "en_summary": "**What happened:** Sankyu provides heavy-industry logistics (steel mill, chemical plant) + engineering (factory construction & maintenance) + international logistics — logistics & engineering company. **FY3/2026: Revenue ¥631.573 billion (+4.1%), OP ¥43.24 billion (-1.6%), ordinary ¥43.385 billion (-2.9%), NP +5.9% (Q3 basis)**.\n\nQ3 revenue ¥472.376 billion (+3.7%), NP ¥23.599 billion (+5.9%) — revenue + bottom-line growth.\n\n**By segment:** **Logistics profit +7.4%**, engineering -5.9%.\n\n**Engineering outlook:** Maintenance saw spring/autumn SDM (scheduled maintenance) work above forecast; facility work expects large-factory + environmental project wins.\n\n**Dividend / market:** Dividend ¥232 → ¥236 (+¥4), ~40% payout ratio. Market cap ¥443.6 billion, PER 13.42x, PBR 1.39x. 2-year average revenue growth 5.86%.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9065 + Sankyu IR + buffett-code 9065"
}

data["9039"] = {
    "name": "Sakai Moving Service",
    "sector_code": "LandTransport",
    "rev_dir": "up", "op_dir": "down", "net_dir": "down", "stock_dir": "up",
    "biz_classification": "mixed (rev up +3.1%, OP -2.7%, NP -1% — but M&A driving forward)",
    "filter_qualifies": ["売上○"],
    "stock_yoy_estimate": "Steady (dividend ¥98 → ¥117 +19%, 8 consecutive years revenue #1)",
    "tab": "R+xS+",
    "bucket": "clean_grower",
    "jp_summary": "**何が起きたか:** サカイ引越センターは日本最大の引越事業者(8年連続売上高No.1)+電気工事+クリーンサービス+物販。 **2026年3月期: 売上¥1,247.41億円(+3.1%)、営業利益¥125.72億円(-2.7%)、純利益¥86億円(-1%)** — 売上は微増、利益は微減。 引越件数825,134件(+1.7%)、引越単価+1.1% — 引越事業は堅調だが、外注委託費+株主優待コメ調達コスト増が利益圧迫。\n\n**M&A加速で成長路線回帰:** (1)2024年12月**九州地盤のスタイル買収**(創業以来初の同業M&A)、(2)**2026年4月ファミリー引越センター買収**(関東地盤)。 FY27グループ売上目標¥1,400億円、将来的に経常利益率12%維持。\n\n**業界寡占化:** 2025年3月期の同社シェア20.6%、大手5社合計シェア60.8%(10年前から自社+7.0pt、5社合計+10.6pt) — 寡占化進行による競争優位性強化。\n\n**配当大幅増:** **¥98→¥117(+¥19、+19.4%増配)** — 配当利回り予3.47%、株主還元を強化。 PER 12.85倍。",
    "en_summary": "**What happened:** Sakai Moving Service is Japan's largest moving company (8 consecutive years #1 by revenue) + electrical work + cleaning services + merchandise. **FY3/2026: Revenue ¥124.741 billion (+3.1%), OP ¥12.572 billion (-2.7%), NP ¥8.6 billion (-1%)** — revenue marginally up, profit slightly down. Moving job count 825,134 (+1.7%), unit price +1.1% — moving business steady, but outsourcing fees + shareholder-perk rice costs squeezed profit.\n\n**M&A acceleration — return to growth path:** (1) December 2024 **acquired Style** (Kyushu-based, first-ever same-industry M&A), (2) **April 2026 acquired Family Mover** (Kanto-based). FY27 group revenue target ¥140 billion; long-term ordinary margin target 12%.\n\n**Industry oligopoly:** FY3/2025 Sakai share 20.6%, top-5 combined 60.8% (vs 10 years prior: +7.0 pts for Sakai, +10.6 pts for top-5) — oligopoly progression strengthens competitive position.\n\n**Major dividend hike:** **¥98 → ¥117 (+¥19, +19.4%)** — yield 3.47%, strengthened shareholder returns. PER 12.85x.",
    "source_hint": "Combined-prompt JP web search 2026-06 + kabutan 9039 + Sakai IR + Nikkei 9039 + maonline 9039"
}

# ──────────────────────────────────────────────────────────────────────────
# Write file
# ──────────────────────────────────────────────────────────────────────────

OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
total = len([k for k in data if k != '_meta'])
print(f"Wrote {OUT.name} with {total} companies")
print(f"  R+×S+: {sum(1 for k,v in data.items() if k!='_meta' and v.get('tab')=='R+xS+')}")
print(f"  R+×S-: {sum(1 for k,v in data.items() if k!='_meta' and v.get('tab')=='R+xS-')}")
