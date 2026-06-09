# -*- coding: utf-8 -*-
"""Apply IT corrections batch 3 (IT03, 8 entries)."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
IT_PATH = Path(r"c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change\data\company_research_2025.json")
C = {}

C["3914"] = {"jp": """**会社概要:** JIG-SAW(東証グロース)はクラウドインフラの24時間365日監視・運用代行を行うITサービス会社。企業がAWSやAzureなどのクラウドを利用する際に、システムの稼働状況を常時監視し、トラブル発生時の対応や復旧を裏側で代行する『システムマネジメント事業』が主力。加えてIoT関連サービスも展開している。

**業績の動き:** 2025年12月期通期は売上+4.39%の36.25億円、純利益-12.64%の4.18億円と先行投資による減益で着地。2026年12月期Q1は売上+17.4%の10.39億円で四半期初の10億円超え、営業利益+64.2%の2.4億円、経常利益+60.8%の2.42億円と急回復。通期予想はグローバルな不確定要素と投資負担の影響で非開示を継続。配当は2015年以降連続無配。

**なぜ業績がこう動いたのか:** 第一に主力のシステムマネジメント事業の堅調 — 監視・運用代行の安定的なストック収益が積み上がる構造。第二にIoT分野の新サービス展開で売上の上乗せが進んだこと。第三に前期(2025年12月期)に実施した先行投資が収益化フェーズに入り、利益率が一気に改善したこと。前期Q3累計時点で営業利益-4.6%だった反動も寄与した。

**なぜ株価がこう動いたのか:** Q1の好決算にもかかわらず、株価は過去1年で大幅下落の長期下降トレンド継続。第一に通期予想を非開示にしているため、投資家にとって『見えない未来』が不安要素として残ること。第二に東証グロース小型銘柄で大手機関投資家のカバレッジが限定的で、好決算でも買い手が薄いこと。第三に連続無配方針のため配当インカム狙いの長期投資家層が入りづらい構造。Q1の急回復は短期的な反発要因にはなったが、長期下降トレンドを反転させるには複数四半期の連続ビートが必要。""",
"en": """**Company overview:** JIG-SAW (TSE Growth) is an IT services company that provides 24/7 monitoring and operations for cloud infrastructure. When companies use cloud services like AWS or Azure, JIG-SAW continuously monitors uptime and handles troubleshooting and recovery — that is the flagship System Management business. They also offer IoT services.

**How did business move:** FY12/2025 full-year: revenue +4.39% to ¥3.625 billion, net profit -12.64% to ¥418 million — a profit decline driven by upfront investment. FY12/2026 Q1 rebounded sharply: revenue +17.4% to ¥1.039 billion (first quarter ever above ¥1 billion), operating profit +64.2%, ordinary profit +60.8%. Full-year guidance is not disclosed. Dividend remains zero.

**Why did business move this way:** First, the flagship System Management business is solid — stock-type recurring revenue is compounding. Second, IoT segment new-service rollouts added incremental revenue. Third, the upfront investment from FY12/2025 entered a monetization phase from Q1, so margins jumped.

**Why did the stock move this way:** Despite the strong Q1, the stock continues its multi-year downtrend. First, full-year guidance is not disclosed — investors find the 「invisible future」 a structural worry. Second, JIG-SAW is a small-cap on TSE Growth with limited major-broker analyst coverage. Third, the zero-dividend policy excludes income-oriented long-term investors. Q1 prompted a short-term bounce but a multi-quarter beat streak is needed to reverse the long downtrend."""}

C["3915"] = {"jp": """**会社概要:** テラスカイ(東証プライム)は、Salesforce(顧客管理SaaSの世界最大手)を企業に導入・カスタマイズ・運用代行する『日本のSalesforce関連リーディング企業』。加えて自社製品事業と、グループ会社『Quemix』が量子コンピュータ関連の研究開発を担う。

**業績の動き:** 2026年2月期通期は売上+13.5%の280.56億円、営業利益+7.4%の15.6億円、経常利益+7.7%の17.27億円で着地。経常利益は従来予想14.8億円を大きく上回り、減益予想から一転して増益で着地。2027年2月期予想は売上+22.4%の343.49億円、営業利益+62.9%の25.41億円、経常利益+52.2%の26.28億円と3期連続最高益見通し。期末配当は16円、来期予想17円と1円増配。

**なぜ業績がこう動いたのか:** 第一に日本企業のSalesforce採用拡大という長期的な追い風が継続し、本業の導入・運用代行売上が二桁成長を維持。第二に自社製品事業への先行投資はあるものの、決算では予想を上方着地させる執行力を示したこと。第三に2026年2月期は当初の減益予想に対し、Salesforce関連の高粗利案件が想定を上回った結果、経常利益で増益着地となった。

**なぜ株価がこう動いたのか:** 過去1年は-11%程度のマイナス推移だったが、直近で急騰。第一カタリストは2026年6月1日のグループ会社Quemixが発表した量子コンピュータ関連の複数共同研究 — デンソー、三井金属、日産・トヨタ・東大、6月3日にホンダ系が追加。これを受け株価はストップ高、6月1日比+500円で2,563円まで上昇。第二に2027年2月期+52.2%経常増益ガイダンスへの期待。第三に『Salesforce持続成長+量子コンピュータ』という二層の成長ストーリーが投資家を惹き付けた。""",
"en": """**Company overview:** TerraSky (TSE Prime) is Japan's leading Salesforce partner — implementing, customizing, and operating Salesforce for Japanese enterprises. Additionally it has an in-house product business and, via its group company Quemix, quantum-computing R&D.

**How did business move:** FY2/2026 full-year: revenue +13.5% to ¥28.056 billion, operating profit +7.4%, ordinary profit +7.7% to ¥1.727 billion — beat prior guide of ¥1.48 billion. FY2/2027 guidance: revenue +22.4%, OP +62.9%, ordinary profit +52.2% — third consecutive year of record profit. Year-end dividend ¥16, next FY ¥17.

**Why did business move this way:** First, continued tailwind from Japanese-corporate Salesforce adoption. Second, despite ongoing in-house product investment, execution beat the guide. Third, high-margin Salesforce work exceeded plan.

**Why did the stock move this way:** Down ~-11% over 12 months but recently surged. First catalyst — June 1 2026, Quemix disclosed multiple quantum-computing JVs (Denso, Mitsui Kinzoku, Nissan/Toyota/Univ of Tokyo, then Honda R&D on June 3). Stock hit limit-up, +¥500 to ¥2,563. Second, expectations for the +52.2% FY2/2027 ordinary-profit guidance. Third, the dual 「Salesforce + quantum computing」 story drew investors."""}

C["3923"] = {"jp": """**会社概要:** ラクス(東証プライム)は中小企業向けクラウドSaaSの大手で、看板商品は経費精算SaaS『楽楽精算』(累計導入19,418社で国内シェアNo.1)と請求書発行・受領SaaS『楽楽明細』。加えて『楽楽販売』『MailDealer』『楽楽勤怠』等を展開。中小企業のバックオフィス業務をクラウド化し月額課金型のストック収益を積み上げる。

**業績の動き:** 2026年3月期通期実績は売上+24.6%の442.97億円、営業利益+65.7%の125億円、経常利益+70.7%の174億円、純利益+51.2%の121億円で着地。2026年4月27日に経常利益を従来予想160億円から174億円へ9%上方修正、期末一括配当も従来3.4円から7円へ大幅増額。2027年3月期予想はIT人材事業の譲渡を反映し売上597億円(-1.0%)、営業利益205億円(+18.2%)、経常利益205億円(+17.5%)、純利益252億円(+89.6%)。

**なぜ業績がこう動いたのか:** 第一に楽楽精算がインボイス制度本格運用と改正電子帳簿保存法対応で会員数とARPUが同時に拡大、ストック収益が継続的に積み上がったこと。クラウド事業売上の93.5%が月額料金。第二に過去数年の大規模TV広告投資による顧客獲得期から利益刈り取りフェーズへ移行し、売上営業利益率が前年Q4の19.8%から30.3%へ急上昇したこと。第三にIT人材事業の譲渡決定でクラウド事業に集中するビジネスポートフォリオの明確化が利益質を引き上げた。

**なぜ株価がこう動いたのか:** 2025年に+50%以上上昇し、上方修正発表で続伸。第一に経常+70.7%という同業比で突出した増益率がSaaS銘柄全般の低迷局面に資金を集中させたこと。第二に2026年4月の上方修正+増配同時発表が『成熟キャッシュ生成SaaS』への投資家認識の転換を促したこと。第三にJPX日経インデックス400採用銘柄でETF需要があり、無借金経営+豊富な営業CFという財務基盤の強さも下支え。""",
"en": """**Company overview:** Rakus (TSE Prime) is a major SME-focused cloud SaaS company. Flagship products are Rakuraku Seisan (expense-reimbursement SaaS, 19,418 cumulative installs, #1 in Japan) and Rakuraku Meisai. Other products include Rakuraku Hanbai, MailDealer, and Rakuraku Kintai.

**How did business move:** FY3/2026 actual: revenue +24.6% to ¥44.297 billion, OP +65.7% to ¥12.5 billion, ordinary +70.7% to ¥17.4 billion, net +51.2% to ¥12.1 billion. On April 27, 2026, ordinary-profit guidance revised UP 9% from ¥16.0B to ¥17.4B; year-end dividend raised from ¥3.4 to ¥7. FY3/2027 guidance reflects IT-talent divestiture: revenue ¥59.7B (-1.0%), OP ¥20.5B (+18.2%), net ¥25.2B (+89.6%).

**Why did business move this way:** First, Rakuraku Seisan saw simultaneous subscriber growth and ARPU expansion from the 2024 invoice-system rollout — cloud-segment revenue is 93.5% monthly recurring. Second, the company shifted from aggressive-TV-ad customer-acquisition to harvest phase, with OP margin in Q4 surging from 19.8% to 30.3% YoY. Third, the IT-talent divestiture clarified the cloud focus.

**Why did the stock move this way:** Up over +50% in 2025, continuing to rise. First, +70.7% ordinary growth was a standout in a struggling SaaS sector. Second, the April 27 upward-revision + dividend-hike shifted investor perception toward 「mature cash-generating SaaS」. Third, JPX-Nikkei 400 inclusion brings ETF demand, and near-zero debt provides a strong floor."""}

C["3983"] = {"jp": """**会社概要:** オロ(東証プライム)は2事業を運営するIT企業。クラウドソリューション事業ではプロジェクト型ビジネス(IT・コンサルタント・広告会社等)向け基幹システム『ZAC』シリーズを提供。マーケティングソリューション事業では企業向けにデジタルマーケティング支援サービスを行う。

**業績の動き:** 2026年12月期Q1は売上+18.7%の23.5億円、営業利益+22.3%の8.12億円と二桁の増収増益で着地。通期予想は売上収益95.72億円(+15.2%)、営業利益29.3億円(+10.6%)、親会社所有者帰属当期利益21.47億円(+13.2%)。ZACは新規契約社数104社(前期比+22社)、ARPA59.99万円(同+4.6万円)を想定。配当予想は年間50円(中間25円、期末25円)で2026年12月期から中間配当を開始。

**なぜ業績がこう動いたのか:** 第一にZACシリーズが大型の新規契約獲得で売上の主要ドライバーに — IT・コンサル・広告のプロジェクト型業務管理ニーズが堅調。第二にマーケティングソリューション事業の利益が大幅伸長し、利益面でも牽引役となった。第三にZACのARPA上昇(顧客単価アップ)で売上の質も改善。ただし純利益率は前年同期比で低下しており、人件費等の固定費負担で収益性の勢いはやや鈍化している点に注意。

**なぜ株価がこう動いたのか:** 業績は良好にもかかわらず株価は過去1年で-29%、5月15日時点1,962円と中期下落基調が継続。第一にみんかぶで『アナリスト対象外』と明示され機関投資家のカバレッジがゼロで、株予報Proのシグナルも『売り継続』表示。第二に予想PERが約15倍と相対的に低くSaaS銘柄のプレミアム評価が付かない構造。第三にクラウドとマーケティングの2事業ポートフォリオが『純粋なSaaS銘柄でも純粋なマーケ銘柄でもない』中途半端さで評価が分散。""",
"en": """**Company overview:** oRo (TSE Prime) runs two businesses. Cloud Solutions provides the ZAC series for project-based businesses (IT, consultancies, ad agencies). Marketing Solutions provides digital-marketing support services.

**How did business move:** FY12/2026 Q1: revenue +18.7% to ¥2.35 billion, OP +22.3% to ¥812 million. Full-year guidance: revenue ¥9.572 billion (+15.2%), OP ¥2.93 billion (+10.6%), net profit ¥2.147 billion (+13.2%). ZAC assumes 104 new contracts (+22 YoY) and ARPA ¥599,900 (+¥46,000). Dividend ¥50/year (¥25 interim + ¥25 year-end).

**Why did business move this way:** First, ZAC won large new contracts and became the main revenue driver. Second, Marketing Solutions profit grew sharply. Third, ZAC ARPA expansion improved revenue quality. Caveat: net margin compressed YoY due to fixed-cost loads.

**Why did the stock move this way:** Despite solid results the stock is -29% over 12 months, closing around ¥1,962 on May 15. First, minkabu flags 「Analyst coverage: none」 — zero institutional coverage. Second, forward PER of ~15x denies oRo a SaaS-growth premium. Third, the dual portfolio dilutes valuation."""}

C["3989"] = {"jp": """**会社概要:** シェアリングテクノロジー(東証グロース)は『暮らしのお困りごと』(水回りトラブル、鍵紛失、害虫駆除、不用品回収、エアコンクリーニング、葬儀、墓じまい等)を解決する事業者と消費者をマッチングするプラットフォーム企業。自社サイト『生活110番』等を通じて全国の中小事業者をネットワーク化。加えて自社施工事業も拡大中。

**業績の動き:** 2025年9月期通期(IFRS)は売上収益+14.4%の85.8億円、営業利益+15.9%の20.7億円、純利益14.1億円で5期連続増収を達成。2026年9月期予想は売上収益98億円(+14.2%)、営業利益23.5億円(+13.3%)、当期利益16億円(+13.2%)と2期連続最高益見通し。配当は年40円→55円(中間27.5円、期末27.5円、+15円、+37.5%)で3期連続増配、2年間で配当額は3.6倍に急増、配当利回り約5.9%。

**なぜ業績がこう動いたのか:** 第一に過去数年の事業整理で本業の『暮らしのお困りごと』マッチング事業に経営資源を集中させ、月間問合せ数の継続増加と事業者ネットワーク約6,400社への拡大が同時進行。第二に自社施工事業の売上が大きく伸長し、プラットフォーム+自社施工の両エンジンが稼働。第三にAIによる最適マッチング精度向上で顧客単価が上昇し、ユニットエコノミクスが改善。

**なぜ株価がこう動いたのか:** 株価は2025年に+30%以上上昇し、最近も底堅い推移(足元1,198円付近)。第一に2026年9月期の年55円大幅増配が高配当株として個人投資家の物色を集めたこと。第二にアセット・バリュー・インベスターズ・リミテッドが大量保有報告を提出し、機関投資家の関心が顕在化したこと。第三に5期連続増収というクオリティ・グロース実績、ROE 27.4%、自己資本比率69.3%、PER 17.4倍の妥当評価という財務基盤の堅さが下支え。""",
"en": """**Company overview:** Sharing Technology (TSE Growth) operates a matching platform for 「life's troubles」 (plumbing, lost keys, pest control, junk removal, AC cleaning, funerals, etc.). It networks small/medium service providers nationwide and matches them to consumers. An in-house construction business is expanding.

**How did business move:** FY9/2025 full-year (IFRS): revenue +14.4% to ¥8.58 billion, OP +15.9% to ¥2.07 billion, net profit ¥1.41 billion — 5 consecutive years of revenue growth. FY9/2026 guidance: revenue ¥9.8 billion (+14.2%), OP ¥2.35 billion (+13.3%), net profit ¥1.6 billion (+13.2%). Dividend ¥40 → ¥55 (+37.5%), 3 consecutive hikes, yield ~5.9%.

**Why did business move this way:** First, the years-back peripheral-business divestiture and focus on the core matching business produced simultaneous growth in monthly inquiries and expansion of the provider network to about 6,400 affiliates. Second, the in-house construction segment grew sharply. Third, AI-driven matching-precision improvements raised ARPU.

**Why did the stock move this way:** Stock up over +30% in 2025 and trading firmly around ¥1,198. First, the large FY9/2026 dividend hike to ¥55 attracted retail income-seekers. Second, Asset Value Investors Limited filed a large-shareholder report. Third, the 5-year compounding revenue track record plus ROE 27.4%, equity ratio 69.3%, and a reasonable PER of 17.4x provide a financial floor."""}

C["3994"] = {"jp": """**会社概要:** マネーフォワード(東証プライム)は中小企業・個人事業主向けのクラウド会計・人事労務・経費精算SaaSを開発・運営する大手フィンテック企業。バックオフィス業務をクラウド化する『マネーフォワード クラウド』が主力で、加えて家計簿アプリ『マネーフォワード ME』や中小企業向け金融サービスも展開。

**業績の動き:** 2026年11月期Q1(2025年12月-2026年2月)は売上+25.3%の146.7億円、SaaS ARR+34.2%の443.03億円と大幅成長。営業利益は1.68億円の黒字転換(前年同期-5.80億円)、純利益18.28億円(前年-11.2億円)、調整後EBITDA28.1億円(前年比2.4倍)と過去最高額の四半期営業利益を達成。Businessセグメント ARR+36.8%、Fintech関連ARR+90%と特に高成長。通期予想は売上534-575.5億円、調整後EBITDA80-100億円。配当は無配継続だが2026年5月末を初回基準日に株主優待制度を新設。

**なぜ業績がこう動いたのか:** 第一にアナリスト・コンセンサスが営業赤字を予想していた中での黒字転換 — 長年の先行投資がついにオペレーティング・レバレッジに転換し『稼げる会社』への構造転換点が到来。第二にBusinessセグメントの法人顧客向けSaaS ARRが分母拡大下でも+36.8%加速、Fintechは+90%と二つの高成長エンジンが同時稼働。第三に2026年7月始動予定の『AI Cowork』など、AI連携の新サービス投入で価格改定とARPU上昇に追い風。

**なぜ株価がこう動いたのか:** 第一に決算翌日(2026年4月15日)の株価は前日比+700円(+18.05%)の4,577円まで急騰 — 『-56億円超の赤字』予想に対する『massive beat』が再評価のきっかけ。第二に2026年5月1日にGitHubへの不正アクセス事案が発覚、銀行口座連携機能を一時停止する事態となりPTS株価は一時2%弱下落。第三に株主優待制度新設が個人投資家の長期保有インセンティブを高めた。バリュエーション面ではPER 137倍と高水準のため、四半期黒字の継続証明とARPU上昇加速が次の上値追いの条件。""",
"en": """**Company overview:** Money Forward (TSE Prime) is a major fintech that develops and operates cloud accounting, HR/labor, and expense-management SaaS for SMEs and sole proprietors. The flagship 「Money Forward Cloud」 puts back-office work in the cloud. Also runs 「Money Forward ME」 personal-finance app and Fintech services.

**How did business move:** FY11/2026 Q1: revenue +25.3% to ¥14.67 billion, SaaS ARR +34.2% to ¥44.303 billion. Operating profit flipped POSITIVE at ¥168 million (vs prior -¥580 million), net profit ¥1.828 billion (vs prior -¥1.12 billion), adjusted EBITDA ¥2.81 billion (2.4x YoY) — a record-high quarterly OP. Business-segment ARR +36.8%; Fintech ARR +90%. Full-year guidance: revenue ¥53.4-57.55 billion, adjusted EBITDA ¥8-10 billion. New shareholder-incentive program launches.

**Why did business move this way:** First, the operating-profit flip against analyst consensus expecting an OP loss — years of upfront investment finally clicked into operating leverage. Second, Business-segment SaaS ARR accelerated +36.8% despite a larger base, while Fintech grew +90%. Third, the planned July-2026 launch of 「AI Cowork」 supports price hikes and ARPU expansion.

**Why did the stock move this way:** First, the day after results (April 15, 2026) the stock surged +¥700 (+18.05%) to ¥4,577 — a massive beat triggered re-rating. Second, on May 1, 2026 a GitHub unauthorized-access incident emerged, temporarily suspending bank-account integration; PTS shares briefly fell ~2%. Third, the new shareholder-incentive program raised long-hold incentive. With PER around 137x, continued quarterly profitability is needed for the next leg."""}

C["4053"] = {"jp": """**会社概要:** Sun Asterisk(東証プライム、略称Sun*)は『デジタルプロダクトの共創』を行うIT企業。顧客企業の新規事業立ち上げ・DX推進を伴走する『クリエイティブ&エンジニアリング事業』が主力で、ベトナムを中心とする海外拠点に多数のエンジニアを抱え、オフショア開発を活用する事業モデル。加えて教育事業も展開。

**業績の動き:** 2025年12月期通期は売上+9.3%の148.35億円、営業利益-27.1%の10.52億円、経常利益-31.4%の9.9億円と減益で着地。直近Q4は経常利益-99.1%の200万円、売上営業利益率9.4%→3.4%と急悪化。2026年12月期予想は売上182.01億円、営業利益17.14億円、経常利益+90.4%の19億円と急回復見通しで、7期連続増収を見込む。配当は2020年から無配継続。なお2026年12月期からIFRS適用に移行するため前期比較は限定的。

**なぜ業績がこう動いたのか:** 第一に元々の投資テーゼ『キャパシティ主導の成長+オペレーティング・レバレッジ』が崩れた — 顧客数の伸びが想定より鈍化し、特定プロジェクトでの外部パートナー利用拡大で利益率を引きずった。第二に2026年12月期予想の急回復は前期の急落からの反発局面という側面が強い。第三にIFRS移行とポートフォリオ調整(教育事業の構造改革)で会計面の不連続性も発生。

**なぜ株価がこう動いたのか:** 業績が改善基調にもかかわらず株価評価は定着せず、足元396円近辺と低迷。第一にみんかぶで『アナリスト対象外』と明示され、機関投資家のカバレッジがゼロで研究レポートや目標株価予想がない構造的問題。第二に2025年8月の業績下方修正のインパクトで投資家の信頼が一度毀損し、回復に時間を要している。第三に時価総額が中堅規模で大型機関投資家の最低投資基準に届かず、配当も無配のため長期保有インセンティブが優待のみ。マージン再拡大が見えるまで上値は重い。""",
"en": """**Company overview:** Sun Asterisk (TSE Prime, often Sun*) is an IT company that does 「digital product co-creation」. The flagship Creative & Engineering business uses substantial offshore development (large engineering bases in Vietnam). Also runs an education business.

**How did business move:** FY12/2025: revenue +9.3% to ¥14.835 billion, OP -27.1% to ¥1.052 billion, ordinary -31.4% to ¥990 million. Q4 alone was extreme: ordinary profit -99.1% to ¥2 million. FY12/2026 guidance: revenue ¥18.201 billion, OP ¥1.714 billion, ordinary ¥1.9 billion (+90.4%) — sharp rebound expected, marking 7 consecutive years of revenue growth. Dividend remains zero since 2020.

**Why did business move this way:** First, the original investment thesis broke — customer growth slowed below plan, and increased use of external partners dragged margins. Second, the FY12/2026 rebound is heavily a bounce off the depressed prior-year base. Third, the IFRS transition and education-business restructuring add accounting-level discontinuity.

**Why did the stock move this way:** Despite the recovery profile the stock remains depressed, trading near ¥396. First, minkabu flags 「Analyst coverage: none」 — zero institutional research. Second, the shock of the August-2025 downward revision broke investor trust. Third, mid-cap value falls short of many large-institution minimum-size thresholds. Until margins re-expand, upside stays heavy."""}

C["4071"] = {"jp": """**会社概要:** プラスアルファ・コンサルティング(東証プライム)は『見える化プラットフォーム企業』を掲げ、ビッグデータ活用による業務効率化・意思決定支援のSaaSを開発・運営する企業。主力はHRソリューション事業のタレントマネジメントSaaS『タレントパレット』。加えてマーケティングソリューション事業も展開。

**業績の動き:** 2025年9月期通期は売上+14.2%の93.41億円、営業利益+32.2%の36.92億円と大幅増収増益、自己資本比率は81.1%と非常に強固。2026年9月期予想は売上195億円(+14.1%)、営業利益75億円(+17.6%)、経常利益75億円(+18.7%)、純利益52億円(+59.6%)。配当は前期29円→今期38円(+9円増配)、配当性向約31%。2026年9月期Q1は売上+14.0%の44.39億円、営業利益+49.5%の16.76億円と大幅増収増益で滑り出し好調。

**なぜ業績がこう動いたのか:** 第一にタレントパレットがエンタープライズ顧客への新規導入で高成長を継続 — ノジマ等の大型導入事例も追加され、エンタープライズ比率とARPUが同時に上昇。第二にマーケティング費用の効率化で営業利益率が大幅改善。第三に2026年5月12日発表のタレントパレットへのAIエージェント機能搭載で『AI時代の戦略人事プラットフォーム』へ進化、価格改定とARPU上昇の余地を確保。

**なぜ株価がこう動いたのか:** 好決算にもかかわらず株価は2,335円(2026年5月11日時点)でほぼ動かず — これがこの銘柄の核心的な謎。第一に2021年上場のグロース株として上場直後の高バリュエーションから数年かけて正常化中で、好決算でも再評価のきっかけになりにくい。第二に時価総額が中型のため大手機関投資家の最低投資基準に届きにくく、大手証券会社のリサーチ・カバレッジも限定的で好決算が市場に増幅されない。第三に救いは現在のPER 19.6倍と過去レンジの最下限 — 大型顧客獲得発表、大手証券カバレッジ開始、または数四半期の連続ビート証明のいずれかが再評価トリガーとなり得る。""",
"en": """**Company overview:** Plus Alpha Consulting (TSE Prime) describes itself as a 「visualization-platform company」 that builds SaaS for big-data-driven business-efficiency and decision-support. The flagship is HR Solutions' talent-management SaaS 「Talent Palette」. Marketing Solutions is the second pillar.

**How did business move:** FY9/2025 full-year: revenue +14.2% to ¥9.341 billion, OP +32.2% to ¥3.692 billion — sharp growth, with an 81.1% equity ratio. FY9/2026 guidance: revenue ¥19.5 billion (+14.1%), OP ¥7.5 billion (+17.6%), ordinary ¥7.5 billion (+18.7%), net profit ¥5.2 billion (+59.6%). Dividend ¥29 → ¥38 (+¥9 hike). FY9/2026 Q1: revenue +14.0%, OP +49.5%.

**Why did business move this way:** First, Talent Palette continues high growth driven by enterprise-customer wins — large new logos like Nojima boosted both enterprise share and ARPU. Second, marketing-spend rationalization sharply lifted OP margin. Third, on May 12, 2026 Talent Palette added AI-agent capabilities — evolving to an 「AI-era strategic HR platform」.

**Why did the stock move this way:** Despite strong results the stock was at ¥2,335 on May 11 — barely moving. That is the central puzzle. First, as a 2021-IPO growth name it has been normalizing down from the listing-era premium for years. Second, mid-cap value sits below many big-institution minimum sizes. Third, the silver lining is the current PER of 19.6x — the bottom of its historical 20-100x range."""}

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
