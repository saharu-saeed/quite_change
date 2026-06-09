# -*- coding: utf-8 -*-
"""Merge the extracted percentage fields from the 5 Sonnet agents back into the
sector JSON files. Each block below is what the agent returned for that sector."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data")

EXTRACTS = {
    "company_research_air_transport_sector.json": {
        "9201": {"rev_dir":"up","rev_pct":"+9.1%","op_dir":"up","op_pct":"+26.4%","net_dir":"up","net_pct":"+28.6%","stock_yoy_estimate":"-20% from 52-wk high (¥3,272→¥2,671)","biz_classification":"フルサービス大手 / Full-service major (international + cargo)"},
        "9202": {"rev_dir":"up","rev_pct":"+12.3%","op_dir":"up","op_pct":"+10.6%","net_dir":"up","net_pct":"+10.5%","stock_yoy_estimate":"-17% from 52-wk high (¥3,350→¥2,717)","biz_classification":"フルサービス大手 / Full-service major (international + cargo + LCC)"},
        "9204": {"rev_dir":"up","rev_pct":"+1.4%","op_dir":"down","op_pct":"-1.4%","net_dir":"down","net_pct":"-24%","stock_yoy_estimate":"-23% from 52-wk high (¥530→¥406)","biz_classification":"中堅国内航空 / Mid-tier domestic carrier"},
        "9206": {"rev_dir":"up","rev_pct":"+4.4%","op_dir":"up","op_pct":"+12.9%","net_dir":"down","net_pct":"-77.4%","stock_yoy_estimate":"-23% from 52-wk high (¥2,481→¥1,903)","biz_classification":"プレミアム・リージョナル / Premium regional"},
    },
    "company_research_mining_sector.json": {
        "1514": {"rev_dir":"down","rev_pct":"-5.5%","op_dir":"down","op_pct":"","net_dir":"down","net_pct":"-61.9%","stock_yoy_estimate":"-48% in ~3 months (Mar→Jun 2026)","biz_classification":"石炭輸入・資源投資 / Coal import & resource investment"},
        "1515": {"rev_dir":"down","rev_pct":"-2.3% (H1)","op_dir":"up","op_pct":"+60.9% (H1)","net_dir":"up","net_pct":"+15.6% (H1)","stock_yoy_estimate":"上昇トレンド / uptrend (no specific % stated)","biz_classification":"石灰石鉱業・金属資源投資 / Limestone mining & metal resource investment"},
        "1518": {"rev_dir":"up","rev_pct":"+8.1%","op_dir":"up","op_pct":"+25.7%","net_dir":"down","net_pct":"-22.3%","stock_yoy_estimate":"上昇トレンド / uptrend (no specific % stated)","biz_classification":"産業用製品・金融・生活消費財 / Industrial products, financial services & consumer goods (former coal)"},
        "1663": {"rev_dir":"down","rev_pct":"-1.2%","op_dir":"up","op_pct":"+20.1%","net_dir":"up","net_pct":"+35.9%","stock_yoy_estimate":"上昇トレンド・過去最高益 / uptrend on record earnings (no specific % stated)","biz_classification":"天然ガス採掘・ヨウ素事業 / Natural gas extraction & iodine"},
    },
    "company_research_petroleum_sector.json": {
        "5009": {"rev_dir":"up","rev_pct":"+4.9% (Q1)","op_dir":"up","op_pct":"+21.5% (Q1)","net_dir":"up","net_pct":"","stock_yoy_estimate":"est. up (no % stated; rated undervalued with ¥1,413 target)","biz_classification":"石油多角化 / Diversified energy (petroleum + recycling + environmental)"},
        "5019": {"rev_dir":"up","rev_pct":"","op_dir":"up","op_pct":"+30.84%","net_dir":"up","net_pct":"","stock_yoy_estimate":"est. down (no % stated; -70.2% OP in Q3-cum FY3/2026 weighs)","biz_classification":"石油精製・販売 / Oil refiner & distributor (+ high-functional materials)"},
        "5020": {"rev_dir":"up","rev_pct":"","op_dir":"up","op_pct":"","net_dir":"up","net_pct":"+14.4%","stock_yoy_estimate":"est. up (no % stated; 91% guidance beat + ¥50B buyback)","biz_classification":"石油精製・販売 / Oil refiner & distributor (largest in Japan)"},
        "5021": {"rev_dir":"down","rev_pct":"-4.4%","op_dir":"up","op_pct":"+12.9%","net_dir":"up","net_pct":"+28.4%","stock_yoy_estimate":"est. flat to up (no % stated; analyst avg target ¥4,845-4,983, Buy)","biz_classification":"石油精製・販売・再エネ / Oil refiner & distributor + wind power"},
        "5011": {"rev_dir":"up","rev_pct":"","op_dir":"down","op_pct":"","net_dir":"down","net_pct":"-13.8% (recurring profit)","stock_yoy_estimate":"est. flat (no % stated; dividend raised ¥75→¥80 despite profit decline)","biz_classification":"アスファルト・道路舗装 / Asphalt products & road paving"},
        "5015": {"rev_dir":"up","rev_pct":"","op_dir":"up","op_pct":"+20.9%","net_dir":"up","net_pct":"","stock_yoy_estimate":"est. flat to up (no % stated; ~5% dividend yield, stable growth)","biz_classification":"潤滑油 / Lubricants (BP Castrol Japan)"},
        "5018": {"rev_dir":"up","rev_pct":"+6.2%","op_dir":"up","op_pct":"+25.8%","net_dir":"up","net_pct":"+28.3%","stock_yoy_estimate":"est. up (no % stated; stock being re-rated, analyst buy signal)","biz_classification":"特殊潤滑油・合成油 / Specialty lubricants & synthetic oils (HDD, EV, battery)"},
    },
    "company_research_marine_sector.json": {
        "9104": {"rev_dir":"up","rev_pct":"+2.8%","op_dir":"down","op_pct":"-58.1%","net_dir":"down","net_pct":"-58%","stock_yoy_estimate":"flat / range-bound","biz_classification":"総合海運大手 / Major diversified shipping"},
        "9130": {"rev_dir":"up","rev_pct":"","op_dir":"down","op_pct":"","net_dir":"down","net_pct":"","stock_yoy_estimate":"","biz_classification":"タンカー専業 / Specialty tanker (VLCC/VLGC)"},
        "9171": {"rev_dir":"up","rev_pct":"+1%","op_dir":"down","op_pct":"-7%","net_dir":"up","net_pct":"+88%","stock_yoy_estimate":"+26% (limit-up on revision day 2025-09-22; full YoY not stated)","biz_classification":"内航RoRo海運 / Coastal RoRo shipping"},
    },
    "company_research_land_transport_sector.json": {
        "9020": {"rev_dir":"up","rev_pct":"+6.8%","op_dir":"up","op_pct":"+9.9%","net_dir":"up","net_pct":"","stock_yoy_estimate":"down ~-23% from Jan peak (¥4,211→¥3,243)","biz_classification":"鉄道大手 / Major JR railway (East Japan)"},
        "9021": {"rev_dir":"up","rev_pct":"+8.1%","op_dir":"up","op_pct":"+9.9%","net_dir":"up","net_pct":"","stock_yoy_estimate":"down ~-5% post-results (¥2,995→¥2,857)","biz_classification":"鉄道大手 / Major JR railway (West Japan)"},
        "9022": {"rev_dir":"up","rev_pct":"+9.5%","op_dir":"up","op_pct":"+18.1%","net_dir":"up","net_pct":"+20.6%","stock_yoy_estimate":"down ~-24% from 2026 high (¥4,329→~¥3,300)","biz_classification":"鉄道大手 / Major JR railway (Central Japan)"},
        "9001": {"rev_dir":"up","rev_pct":"+3.8%","op_dir":"down","op_pct":"-6.2%","net_dir":"up","net_pct":"+8.4%","stock_yoy_estimate":"up (clear uptrend, % unverified)","biz_classification":"関東大手私鉄 / Major Kanto private railway (Tobu)"},
        "9003": {"rev_dir":"up","rev_pct":"+5.3%","op_dir":"up","op_pct":"+2.7%","net_dir":"up","net_pct":"+10.9%","stock_yoy_estimate":"-23% from Apr peak (¥3,167→¥2,430)","biz_classification":"関東私鉄 / Kanto private railway (Sotetsu)"},
        "9007": {"rev_dir":"down","rev_pct":"-0.94%","op_dir":"up","op_pct":"","net_dir":"down","net_pct":"-28.08%","stock_yoy_estimate":"down ~-6% from Apr high (¥1,758→¥1,650)","biz_classification":"関東大手私鉄 / Major Kanto private railway (Odakyu)"},
        "9031": {"rev_dir":"up","rev_pct":"","op_dir":"up","op_pct":"","net_dir":"up","net_pct":"+20%","stock_yoy_estimate":"+42% YoY (¥1,926 Apr-2025 low → ¥2,741 May-2026)","biz_classification":"九州私鉄・物流 / Kyushu private railway & logistics (Nishitetsu)"},
        "9041": {"rev_dir":"up","rev_pct":"+0.5%","op_dir":"up","op_pct":"+6.0%","net_dir":"up","net_pct":"+15.1%","stock_yoy_estimate":"flat to slightly up (¥3,052–¥3,628 range, % unverified)","biz_classification":"関西大手私鉄 / Major Kansai private railway (Kintetsu)"},
        "9042": {"rev_dir":"up","rev_pct":"+9.6% (H1)","op_dir":"up","op_pct":"+20.1% (H1)","net_dir":"up","net_pct":"","stock_yoy_estimate":"up sharply (clear uptrend, % unverified)","biz_classification":"関西大手私鉄 / Major Kansai private railway (Hankyu Hanshin)"},
        "9044": {"rev_dir":"up","rev_pct":"+4.4% (H1)","op_dir":"up","op_pct":"+17.0% (H1)","net_dir":"up","net_pct":"+10.1% (H1)","stock_yoy_estimate":"-17% from Apr peak (¥3,318→~¥2,584)","biz_classification":"関西私鉄 / Kansai private railway (Nankai)"},
        "9045": {"rev_dir":"up","rev_pct":"+6.0%","op_dir":"up","op_pct":"+16.8%","net_dir":"up","net_pct":"","stock_yoy_estimate":"up sharply (clear uptrend, major dividend hike, % unverified)","biz_classification":"関西私鉄 / Kansai private railway (Keihan)"},
        "9052": {"rev_dir":"up","rev_pct":"","op_dir":"up","op_pct":"","net_dir":"up","net_pct":"+42.0% (H1, incl. one-off)","stock_yoy_estimate":"stable ~¥2,048 (range-bound, % unverified)","biz_classification":"関西中堅私鉄 / Mid-tier Kansai private railway (Sanyo)"},
        "9069": {"rev_dir":"up","rev_pct":"+5.3%","op_dir":"up","op_pct":"+5.9%","net_dir":"up","net_pct":"","stock_yoy_estimate":"-6% YoY (~¥1,992→¥1,876)","biz_classification":"総合物流大手 / Major comprehensive logistics (SENKO)"},
        "9072": {"rev_dir":"up","rev_pct":"+8.9%","op_dir":"up","op_pct":"+2.9%","net_dir":"up","net_pct":"+10.2%","stock_yoy_estimate":"up substantially over 1-2 years (% unverified)","biz_classification":"自動車物流 / Auto-logistics specialist (NIKKON)"},
        "9066": {"rev_dir":"up","rev_pct":"+13.5% (H1, pre-delisting)","op_dir":"up","op_pct":"+10.1% (H1, pre-delisting)","net_dir":"up","net_pct":"","stock_yoy_estimate":"converged to TOB price ¥8,100; delisted Oct 2025","biz_classification":"総合物流(上場廃止) / Comprehensive logistics (delisted Oct 2025)"},
        "9090": {"rev_dir":"up","rev_pct":"+10.6%","op_dir":"up","op_pct":"+8.3%","net_dir":"up","net_pct":"","stock_yoy_estimate":"-26% YoY (¥1,023 Jan-2026 high → ¥762 low, downtrend)","biz_classification":"EC・小売3PL / EC & retail 3PL logistics (AZ-COM Maruwa)"},
        "9147": {"rev_dir":"up","rev_pct":"+1.1% (Q1 FY12/2026)","op_dir":"up","op_pct":"+32.3% (Q1 FY12/2026)","net_dir":"up","net_pct":"","stock_yoy_estimate":"up strongly on 1-year view (~¥5,259, % unverified)","biz_classification":"総合物流大手 / Major comprehensive logistics (NX / Nippon Express)"},
        "9005": {"rev_dir":"up","rev_pct":"+3.0%","op_dir":"flat","op_pct":"-0.3%","net_dir":"up","net_pct":"+9.3%","stock_yoy_estimate":"-21% from Mar peak (¥2,011→¥1,580)","biz_classification":"関東大手私鉄 / Major Kanto private railway (Tokyu)"},
        "9008": {"rev_dir":"up","rev_pct":"","op_dir":"down","op_pct":"-2.9% (Q3 YTD)","net_dir":"up","net_pct":"","stock_yoy_estimate":"up sharply (stock split + buyback + dividend hike, % unverified)","biz_classification":"関東大手私鉄 / Major Kanto private railway (Keio)"},
        "9009": {"rev_dir":"up","rev_pct":"+4.1%","op_dir":"down","op_pct":"-5.6%","net_dir":"down","net_pct":"-31.4%","stock_yoy_estimate":"down softly (target cut ¥1,470→¥1,310, % unverified)","biz_classification":"関東私鉄(成田アクセス) / Kanto private railway, Narita airport access (Keisei)"},
        "9024": {"rev_dir":"down","rev_pct":"-43.0%","op_dir":"down","op_pct":"-84.4%","net_dir":"down","net_pct":"","stock_yoy_estimate":"down (RE sale reaction-decline suppresses valuation, % unverified)","biz_classification":"関東私鉄・ホテル / Kanto private railway & hotel (Seibu Holdings)"},
        "9006": {"rev_dir":"up","rev_pct":"+3.5%","op_dir":"down","op_pct":"-5.9%","net_dir":"up","net_pct":"+13.1%","stock_yoy_estimate":"up (major dividend hike ¥26→¥46, uptrend, % unverified)","biz_classification":"関東大手私鉄(羽田アクセス) / Major Kanto railway, Haneda access (Keikyu)"},
        "9048": {"rev_dir":"flat","rev_pct":"","op_dir":"down","op_pct":"-14.0%","net_dir":"down","net_pct":"-39.2%","stock_yoy_estimate":"down softly (redevelopment shelved, % unverified)","biz_classification":"中部大手私鉄 / Major Chubu private railway (Meitetsu)"},
        "9064": {"rev_dir":"up","rev_pct":"+5.8%","op_dir":"up","op_pct":"+99.2%","net_dir":"down","net_pct":"-64.0%","stock_yoy_estimate":"down ~-22% (¥1,800 range, mid-term plan cut, % unverified)","biz_classification":"宅配大手 / Major parcel delivery (Yamato / Kuroneko)"},
        "9065": {"rev_dir":"up","rev_pct":"","op_dir":"down","op_pct":"","net_dir":"down","net_pct":"-2.4%","stock_yoy_estimate":"firm / range-bound (% unverified)","biz_classification":"重工業向け物流 / Heavy-industry logistics & engineering (Sankyu)"},
        "9039": {"rev_dir":"up","rev_pct":"+3.1%","op_dir":"down","op_pct":"-2.7%","net_dir":"up","net_pct":"+1.7%","stock_yoy_estimate":"up (major dividend hike ¥98→¥117, uptrend, % unverified)","biz_classification":"引越大手 / Major moving company (Sakai)"},
        "2384": {"rev_dir":"up","rev_pct":"+10.3% (9M)","op_dir":"up","op_pct":"+31.1% (9M)","net_dir":"up","net_pct":"+27.4% (9M)","stock_yoy_estimate":"firm ~¥3,460 (Oct 2025 reference, % unverified)","biz_classification":"3PL・物流不動産 / 3PL & logistics real estate (SBS Holdings)"},
        "9010": {"rev_dir":"up","rev_pct":"+2.5%","op_dir":"up","op_pct":"+5.4%","net_dir":"up","net_pct":"+13.5%","stock_yoy_estimate":"up gently (inbound theme, % unverified)","biz_classification":"観光鉄道・レジャー / Tourism railway & leisure (Fuji Kyuko)"},
        "9012": {"rev_dir":"up","rev_pct":"+6.8%","op_dir":"up","op_pct":"+76.9%","net_dir":"up","net_pct":"+231.6%","stock_yoy_estimate":"up sharply (record NP, uptrend, % unverified)","biz_classification":"地方観光鉄道 / Regional tourism railway (Chichibu Railway)"},
        "9017": {"rev_dir":"up","rev_pct":"+1.7%","op_dir":"up","op_pct":"+11.0%","net_dir":"up","net_pct":"","stock_yoy_estimate":"up gently (% unverified)","biz_classification":"地方バス・多角化 / Regional bus & diversified (Niigata Kotsu)"},
        "9023": {"rev_dir":"up","rev_pct":"+3.6%","op_dir":"up","op_pct":"+3.0%","net_dir":"up","net_pct":"+9.8%","stock_yoy_estimate":"up from ¥1,200 IPO price (stable, % unverified)","biz_classification":"都市地下鉄 / Urban subway (Tokyo Metro)"},
        "9025": {"rev_dir":"up","rev_pct":"+3.1%","op_dir":"up","op_pct":"+6.5%","net_dir":"up","net_pct":"","stock_yoy_estimate":"up gently (~¥2,751 May 2026, % unverified)","biz_classification":"重工業・空港物流 / Heavy-industry & airport ground handling (Konoike)"},
        "9027": {"rev_dir":"up","rev_pct":"+1.0%","op_dir":"up","op_pct":"+1.2%","net_dir":"up","net_pct":"+22%","stock_yoy_estimate":"up gently (~¥3,220, % unverified)","biz_classification":"北海道・海上3PL / Hokkaido marine & 3PL logistics (Loginet Japan)"},
        "9028": {"rev_dir":"up","rev_pct":"+5.0%","op_dir":"up","op_pct":"+64.4%","net_dir":"up","net_pct":"+73.0%","stock_yoy_estimate":"+77.5% YoY (Bloomberg, as of May 2025)","biz_classification":"完成車輸送 / Finished-vehicle logistics specialist (Zero)"},
        "9029": {"rev_dir":"up","rev_pct":"+20.5%","op_dir":"up","op_pct":"","net_dir":"up","net_pct":"+41.4% (recurring)","stock_yoy_estimate":"up (¥1,972 Jun from lower base, % unverified)","biz_classification":"EC・総務物流3PL / EC & general-affairs 3PL (Higashi Holdings)"},
        "9033": {"rev_dir":"up","rev_pct":"+11.2%","op_dir":"up","op_pct":"","net_dir":"down","net_pct":"-16.0%","stock_yoy_estimate":"range-bound ~¥619-625 (direction unverified)","biz_classification":"路面電車・バス / Tram & bus operator (Hiroshima Electric Railway)"},
        "9034": {"rev_dir":"up","rev_pct":"+2.44%","op_dir":"flat","op_pct":"","net_dir":"down","net_pct":"-1.31%","stock_yoy_estimate":"range-bound ~¥1,200 (% unverified)","biz_classification":"地方中堅物流 / Regional mid-tier logistics (Nansou Tsuun)"},
        "9035": {"rev_dir":"up","rev_pct":"+13.1%","op_dir":"up","op_pct":"+17.6%","net_dir":"up","net_pct":"","stock_yoy_estimate":"up (clear uptrend, % unverified)","biz_classification":"タクシー大手・不動産 / Major taxi operator & real estate (Daiichi Kotsu)"},
        "9036": {"rev_dir":"down","rev_pct":"-2.8%","op_dir":"up","op_pct":"+44.8%","net_dir":"up","net_pct":"+184.4%","stock_yoy_estimate":"direction unverified","biz_classification":"化学品・産業ガス輸送 / Chemical & industrial-gas trucking (Tobu Network)"},
        "9037": {"rev_dir":"up","rev_pct":"+6.0%","op_dir":"up","op_pct":"+11.7%","net_dir":"up","net_pct":"","stock_yoy_estimate":"up gently (% unverified)","biz_classification":"3PL専業中堅 / 3PL pure-play mid-tier (Hamakyorex)"},
        "9040": {"rev_dir":"up","rev_pct":"+4.2%","op_dir":"up","op_pct":"+31.0%","net_dir":"down","net_pct":"-33.1%","stock_yoy_estimate":"stable ~¥4,190 (% unverified)","biz_classification":"地方中堅トラック / Regional mid-tier trucker (Taiho Transportation)"},
        "9046": {"rev_dir":"up","rev_pct":"+5.5%","op_dir":"up","op_pct":"+20.7%","net_dir":"up","net_pct":"","stock_yoy_estimate":"near 52-week low ~¥2,322-2,378 (down from highs, % unverified)","biz_classification":"関西中堅私鉄 / Mid-tier Kansai private railway (Kobe Electric)"},
        "9049": {"rev_dir":"up","rev_pct":"+2.9%","op_dir":"up","op_pct":"+5.1%","net_dir":"up","net_pct":"+5.6%","stock_yoy_estimate":"-13.5% from Mar high (¥8,300→¥7,180)","biz_classification":"京都観光路面電車 / Kyoto tourism tram (Keifuku / Randen)"},
        "9051": {"rev_dir":"up","rev_pct":"+5.7% (9M)","op_dir":"down","op_pct":"-19.9% (9M)","net_dir":"down","net_pct":"","stock_yoy_estimate":"+42% from low (¥891 Jan → ¥1,739 Aug high, then ~¥1,260)","biz_classification":"東北3PL物流 / Tohoku 3PL logistics (Senkon)"},
        "9057": {"rev_dir":"up","rev_pct":"+7.3%","op_dir":"up","op_pct":"+4.9%","net_dir":"up","net_pct":"","stock_yoy_estimate":"modest / range-bound (% unverified)","biz_classification":"静岡3PL物流 / Shizuoka 3PL logistics (Enshu Truck)"},
        "9059": {"rev_dir":"flat","rev_pct":"+0.2% (Q3 YTD)","op_dir":"up","op_pct":"+9.4% (Q3 YTD)","net_dir":"up","net_pct":"+10.4% (Q3 YTD)","stock_yoy_estimate":"stable ~¥846 (% unverified)","biz_classification":"関東中堅総合物流 / Kanto mid-tier comprehensive logistics (Kanda Holdings)"},
        "9060": {"rev_dir":"up","rev_pct":"+8.1%","op_dir":"up","op_pct":"+16.9%","net_dir":"up","net_pct":"","stock_yoy_estimate":"up gently (% unverified)","biz_classification":"3PL・倉庫不動産 / 3PL & owned-warehouse logistics (Nippon Logitem)"},
        "9063": {"rev_dir":"up","rev_pct":"+0.9% (Q3 YTD)","op_dir":"up","op_pct":"+17.7% (Q3 YTD)","net_dir":"up","net_pct":"+177.4% (Q3 YTD, incl. RE gain)","stock_yoy_estimate":"up gently (% unverified)","biz_classification":"中四国地方トラック / Chu-Shikoku regional trucker (Okayama Freight)"},
        "9068": {"rev_dir":"up","rev_pct":"+2.8%","op_dir":"up","op_pct":"+5.6%","net_dir":"up","net_pct":"","stock_yoy_estimate":"up gently (¥40 dividend hike, % unverified)","biz_classification":"京浜総合物流 / Keihin comprehensive logistics (Marzen Showa)"},
        "9073": {"rev_dir":"up","rev_pct":"+3.3%","op_dir":"up","op_pct":"+867.8%","net_dir":"up","net_pct":"","stock_yoy_estimate":"volatile, Jul-2025 spike (% unverified)","biz_classification":"化学品・ドラム缶輸送 / Chemical transport & drum-can recycling (Kyogoku)"},
        "9074": {"rev_dir":"up","rev_pct":"+3.9%","op_dir":"up","op_pct":"+20.2%","net_dir":"up","net_pct":"+19.4%","stock_yoy_estimate":"direction unverified (~¥4,635 Dec 2025)","biz_classification":"危険物・石油輸送 / Hazmat & petroleum transport (Japan Oil Transportation)"},
        "9075": {"rev_dir":"up","rev_pct":"+5.3%","op_dir":"up","op_pct":"+26.9%","net_dir":"up","net_pct":"+56.6%","stock_yoy_estimate":"up (uptrend, % unverified)","biz_classification":"特積み大手 / Major LTL freight (Fukuyama Transport)"},
        "9076": {"rev_dir":"up","rev_pct":"+10.4%","op_dir":"up","op_pct":"+25.8%","net_dir":"up","net_pct":"+14.3%","stock_yoy_estimate":"up (uptrend, % unverified)","biz_classification":"特積み大手 / Major LTL freight (Seino Holdings)"},
        "9081": {"rev_dir":"up","rev_pct":"+7.3%","op_dir":"down","op_pct":"-8.3%","net_dir":"down","net_pct":"-28.8%","stock_yoy_estimate":"range-bound ¥3,215-¥3,880 (direction unverified)","biz_classification":"大手バス・自動車販売 / Major bus operator & auto dealer (Kanachu)"},
        "9082": {"rev_dir":"up","rev_pct":"+5.6%","op_dir":"up","op_pct":"","net_dir":"down","net_pct":"-62.1%","stock_yoy_estimate":"up (clear uptrend, % unverified)","biz_classification":"東京大手タクシー / Major Tokyo taxi operator (Daiwa Auto)"},
        "9083": {"rev_dir":"up","rev_pct":"+5.0%","op_dir":"up","op_pct":"+20.9%","net_dir":"up","net_pct":"","stock_yoy_estimate":"up (clear uptrend, % unverified)","biz_classification":"兵庫大手バス / Major Hyogo bus operator (Shinki Bus)"},
        "9085": {"rev_dir":"up","rev_pct":"+6.7%","op_dir":"up","op_pct":"+17.1%","net_dir":"up","net_pct":"+22.9%","stock_yoy_estimate":"up (uptrend, % unverified)","biz_classification":"北海道大手バス / Major Hokkaido bus operator (Hokkaido Chuo Bus)"},
        "9087": {"rev_dir":"up","rev_pct":"+2.0% (Q3 YTD)","op_dir":"up","op_pct":"+120.3% (Q3 YTD)","net_dir":"up","net_pct":"","stock_yoy_estimate":"up gently (% unverified)","biz_classification":"国際・国内ハイブリッド物流 / International & domestic hybrid logistics (Takase)"},
        "9142": {"rev_dir":"up","rev_pct":"+10.1%","op_dir":"up","op_pct":"+25.5%","net_dir":"up","net_pct":"","stock_yoy_estimate":"-18% from Feb peak (¥4,154→~¥3,390)","biz_classification":"鉄道大手 / Major JR railway (Kyushu)"},
        "9143": {"rev_dir":"up","rev_pct":"+11.2%","op_dir":"up","op_pct":"+2.7%","net_dir":"up","net_pct":"+1.6%","stock_yoy_estimate":"down softly (~¥1,437, % unverified)","biz_classification":"宅配大手 / Major parcel delivery (SG Holdings / Sagawa)"},
        "9145": {"rev_dir":"up","rev_pct":"+14.6%","op_dir":"up","op_pct":"+24.8%","net_dir":"up","net_pct":"+5%","stock_yoy_estimate":"direction unverified","biz_classification":"自動車・総合物流 / Auto & comprehensive logistics (Being Holdings)"},
    },
}

total_updated = 0
for fname, ticker_data in EXTRACTS.items():
    path = BASE / fname
    data = json.loads(path.read_text(encoding='utf-8'))
    updated = 0
    for ticker, fields in ticker_data.items():
        if ticker in data:
            for k, v in fields.items():
                data[ticker][k] = v
            updated += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    json.loads(path.read_text(encoding='utf-8'))  # validate
    print(f"{fname[:50]:50s}: updated {updated} entries")
    total_updated += updated

print(f"\nTotal entries with pct/biz fields injected: {total_updated}")
