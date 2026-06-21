// IT Q4 FY-ending-2025 — Phase 1 (final assembled)
// Fixes baked in: find-then-fetch · net% self-compute · TWO-WAY one-off probe ·
// grounding rule · expanded business vocab · stock left pending.
// Run subset:  Workflow({scriptPath, args:{tickers:['9433','3659','3994']}})
// Run all 100: Workflow({scriptPath})   (no args)
export const meta = {
  name: 'it-q4-phase1-final',
  description: 'IT Q4 Phase-1: numbers + grounded business reason + tag, stock pending (Python fills later)',
  phases: [
    {title: 'Research', detail: 'agents: find+fetch tanshin, net% self-check, two-way one-off probe'},
    {title: 'Build',    detail: 'assemble + write data/quarterly/it_q4_2025.json'},
  ]
}

const ROOT = 'c:/Users/Sahal Saeed/Documents/tempest_ai/quick/New_quick/new_quick/quite_change'

const FY_META = {
  'March':    {fy:'FY3/2025',  fy_jp:'2025年3月期',  prev_fy_jp:'2024年3月期',  announce:'2025年5月',  next_fy_jp:'2026年3月期'},
  'December': {fy:'FY12/2025', fy_jp:'2025年12月期', prev_fy_jp:'2024年12月期', announce:'2026年2月',  next_fy_jp:'2026年12月期'},
  'June':     {fy:'FY6/2025',  fy_jp:'2025年6月期',  prev_fy_jp:'2024年6月期',  announce:'2025年8月',  next_fy_jp:'2026年6月期'},
  'September':{fy:'FY9/2025',  fy_jp:'2025年9月期',  prev_fy_jp:'2024年9月期',  announce:'2025年11月', next_fy_jp:'2026年9月期'},
  'October':  {fy:'FY10/2025', fy_jp:'2025年10月期', prev_fy_jp:'2024年10月期', announce:'2025年12月', next_fy_jp:'2026年10月期'},
  'November': {fy:'FY11/2025', fy_jp:'2025年11月期', prev_fy_jp:'2024年11月期', announce:'2026年1月',  next_fy_jp:'2026年11月期'},
  'May':      {fy:'FY5/2025',  fy_jp:'2025年5月期',  prev_fy_jp:'2024年5月期',  announce:'2025年7月',  next_fy_jp:'2026年5月期'},
  'July':     {fy:'FY7/2025',  fy_jp:'2025年7月期',  prev_fy_jp:'2024年7月期',  announce:'2025年9月',  next_fy_jp:'2026年7月期'},
  'August':   {fy:'FY8/2025',  fy_jp:'2025年8月期',  prev_fy_jp:'2024年8月期',  announce:'2025年10月', next_fy_jp:'2026年8月期'},
  'February': {fy:'FY2/2025',  fy_jp:'2025年2月期',  prev_fy_jp:'2024年2月期',  announce:'2025年4月',  next_fy_jp:'2026年2月期'},
  'April':    {fy:'FY4/2025',  fy_jp:'2025年4月期',  prev_fy_jp:'2024年4月期',  announce:'2025年6月',  next_fy_jp:'2026年4月期'},
}

const COMPANIES = [
  {ticker:'9984', name:'SoftBank Group', name_jp:'ソフトバンクグループ', size:'large', fy_hint:'March'},
  {ticker:'9432', name:'NTT', name_jp:'日本電信電話', size:'large', fy_hint:'March'},
  {ticker:'9433', name:'KDDI', name_jp:'KDDI', size:'large', fy_hint:'March'},
  {ticker:'9434', name:'SoftBank Corp', name_jp:'ソフトバンク', size:'large', fy_hint:'March'},
  {ticker:'4689', name:'LY Corporation', name_jp:'LYコーポレーション', size:'large', fy_hint:'March'},
  {ticker:'9766', name:'Konami Group', name_jp:'コナミグループ', size:'large', fy_hint:'March'},
  {ticker:'4307', name:'NRI', name_jp:'野村総合研究所', size:'large', fy_hint:'March'},
  {ticker:'4684', name:'OBIC', name_jp:'オービック', size:'large', fy_hint:'June'},
  {ticker:'3659', name:'Nexon', name_jp:'ネクソン', size:'large', fy_hint:'December'},
  {ticker:'9435', name:'Hikari Tsushin', name_jp:'光通信', size:'large', fy_hint:'August'},
  {ticker:'9697', name:'Capcom', name_jp:'カプコン', size:'large', fy_hint:'March'},
  {ticker:'4716', name:'Oracle Japan', name_jp:'日本オラクル', size:'large', fy_hint:'May'},
  {ticker:'9602', name:'Toho', name_jp:'東宝', size:'large', fy_hint:'February'},
  {ticker:'4768', name:'Otsuka Corp', name_jp:'大塚商会', size:'large', fy_hint:'December'},
  {ticker:'9412', name:'SKY Perfect JSAT', name_jp:'スカパーJSAT', size:'large', fy_hint:'March'},
  {ticker:'9401', name:'TBS Holdings', name_jp:'TBSホールディングス', size:'large', fy_hint:'March'},
  {ticker:'4676', name:'Fuji Media Holdings', name_jp:'フジ・メディアHD', size:'large', fy_hint:'March'},
  {ticker:'9684', name:'Square Enix Holdings', name_jp:'スクウェア・エニックスHD', size:'large', fy_hint:'March'},
  {ticker:'4704', name:'Trend Micro', name_jp:'トレンドマイクロ', size:'large', fy_hint:'December'},
  {ticker:'3626', name:'TIS', name_jp:'TIS', size:'large', fy_hint:'March'},
  {ticker:'9404', name:'NTV Holdings', name_jp:'日本テレビHD', size:'large', fy_hint:'March'},
  {ticker:'9413', name:'TV Tokyo Holdings', name_jp:'テレビ東京HD', size:'large', fy_hint:'March'},
  {ticker:'3769', name:'GMO Payment Gateway', name_jp:'GMOペイメントゲートウェイ', size:'large', fy_hint:'September'},
  {ticker:'4385', name:'Mercari', name_jp:'メルカリ', size:'large', fy_hint:'June'},
  {ticker:'2327', name:'NS Solutions', name_jp:'NS Solutions', size:'large', fy_hint:'March'},
  {ticker:'3774', name:'Internet Initiative Japan', name_jp:'インターネットイニシアティブ', size:'large', fy_hint:'March'},
  {ticker:'4816', name:'Toei Animation', name_jp:'東映アニメーション', size:'large', fy_hint:'March'},
  {ticker:'9468', name:'Kadokawa', name_jp:'KADOKAWA', size:'large', fy_hint:'March'},
  {ticker:'3635', name:'Koei Tecmo Holdings', name_jp:'コーエーテクモHD', size:'large', fy_hint:'March'},
  {ticker:'9613', name:'NTT Data Group', name_jp:'NTTデータグループ', size:'large', fy_hint:'March'},
  {ticker:'8056', name:'Biprogy', name_jp:'ビプロジー', size:'mid', fy_hint:'March'},
  {ticker:'4733', name:'OBIC Business Consultants', name_jp:'オービックビジネスコンサルタント', size:'mid', fy_hint:'March'},
  {ticker:'9605', name:'Toei', name_jp:'東映', size:'mid', fy_hint:'March'},
  {ticker:'4812', name:'Dentsu Soken', name_jp:'電通総研', size:'mid', fy_hint:'December'},
  {ticker:'9409', name:'TV Asahi Holdings', name_jp:'テレビ朝日HD', size:'mid', fy_hint:'March'},
  {ticker:'9436', name:'Okinawa Cellular', name_jp:'沖縄セルラー電話', size:'mid', fy_hint:'March'},
  {ticker:'9449', name:'GMO Internet Group', name_jp:'GMOインターネットグループ', size:'mid', fy_hint:'December'},
  {ticker:'3923', name:'Rakus', name_jp:'ラクス', size:'mid', fy_hint:'March'},
  {ticker:'4194', name:'Visional', name_jp:'ビジョナル', size:'mid', fy_hint:'July'},
  {ticker:'9418', name:'U-NEXT Holdings', name_jp:'Uーネクスト', size:'mid', fy_hint:'August'},
  {ticker:'4686', name:'JustSystems', name_jp:'ジャストシステム', size:'mid', fy_hint:'March'},
  {ticker:'4373', name:'Simplex Holdings', name_jp:'シンプレクスHD', size:'mid', fy_hint:'March'},
  {ticker:'3994', name:'Money Forward', name_jp:'マネーフォワード', size:'mid', fy_hint:'November'},
  {ticker:'9759', name:'NSD', name_jp:'NSD', size:'mid', fy_hint:'March'},
  {ticker:'4443', name:'Sansan', name_jp:'Sansan', size:'mid', fy_hint:'May'},
  {ticker:'9746', name:'TKC', name_jp:'TKC', size:'mid', fy_hint:'March'},
  {ticker:'2317', name:'Systena', name_jp:'システナ', size:'mid', fy_hint:'March'},
  {ticker:'4483', name:'JMDC', name_jp:'JMDC', size:'mid', fy_hint:'March'},
  {ticker:'9682', name:'DTS', name_jp:'DTS', size:'mid', fy_hint:'March'},
  {ticker:'4751', name:'CyberAgent', name_jp:'サイバーエージェント', size:'mid', fy_hint:'September'},
  {ticker:'5032', name:'Anycolor', name_jp:'エニーカラー', size:'mid', fy_hint:'April'},
  {ticker:'4776', name:'Cybozu', name_jp:'サイボウズ', size:'mid', fy_hint:'December'},
  {ticker:'4478', name:'freee', name_jp:'フリー', size:'mid', fy_hint:'June'},
  {ticker:'4180', name:'Appier Group', name_jp:'アピエグループ', size:'mid', fy_hint:'December'},
  {ticker:'3778', name:'Sakura Internet', name_jp:'さくらインターネット', size:'mid', fy_hint:'March'},
  {ticker:'4475', name:'HENNGE', name_jp:'ヘンジ', size:'mid', fy_hint:'September'},
  {ticker:'4431', name:'Smaregi', name_jp:'スマレジ', size:'mid', fy_hint:'October'},
  {ticker:'9692', name:'CEC', name_jp:'CEC', size:'mid', fy_hint:'March'},
  {ticker:'9715', name:'Comture', name_jp:'コムチュア', size:'mid', fy_hint:'March'},
  {ticker:'2121', name:'Mixi', name_jp:'ミクシィ', size:'mid', fy_hint:'March'},
  {ticker:'3765', name:'GungHo Online', name_jp:'ガンホー', size:'small', fy_hint:'December'},
  {ticker:'4490', name:'VisasQ', name_jp:'ビザスク', size:'small', fy_hint:'February'},
  {ticker:'4176', name:'Coconala', name_jp:'ココナラ', size:'small', fy_hint:'August'},
  {ticker:'4165', name:'Plaid', name_jp:'プレイド', size:'small', fy_hint:'March'},
  {ticker:'3914', name:'JIG-SAW', name_jp:'ジグソー', size:'small', fy_hint:'December'},
  {ticker:'3853', name:'Asteria', name_jp:'アステリア', size:'small', fy_hint:'March'},
  {ticker:'3915', name:'TerraSky', name_jp:'テラスカイ', size:'small', fy_hint:'February'},
  {ticker:'4169', name:'EneChange', name_jp:'エネチェンジ', size:'small', fy_hint:'September'},
  {ticker:'4264', name:'Secure', name_jp:'セキュア', size:'small', fy_hint:'September'},
  {ticker:'4427', name:'EduLab', name_jp:'エデュラボ', size:'small', fy_hint:'March'},
  {ticker:'4783', name:'NCD', name_jp:'NCD', size:'small', fy_hint:'March'},
  {ticker:'3744', name:'SIOS Technology', name_jp:'サイオス', size:'small', fy_hint:'December'},
  {ticker:'3681', name:'V-cube', name_jp:'ブイキューブ', size:'small', fy_hint:'December'},
  {ticker:'4344', name:'Source Next', name_jp:'ソースネクスト', size:'small', fy_hint:'March'},
  {ticker:'3911', name:'Aiming', name_jp:'エイミング', size:'small', fy_hint:'December'},
  {ticker:'3760', name:'Cave', name_jp:'ケイブ', size:'small', fy_hint:'February'},
  {ticker:'3668', name:'Colopl', name_jp:'コロプラ', size:'small', fy_hint:'September'},
  {ticker:'3656', name:'KLab', name_jp:'KLab', size:'small', fy_hint:'December'},
  {ticker:'3928', name:'Mynet', name_jp:'マイネット', size:'small', fy_hint:'December'},
  {ticker:'3653', name:'Morpho', name_jp:'モルフォAI', size:'small', fy_hint:'October'},
  {ticker:'4488', name:'AI inside', name_jp:'AIinside', size:'small', fy_hint:'June'},
  {ticker:'4477', name:'BASE', name_jp:'BASE', size:'small', fy_hint:'December'},
  {ticker:'6618', name:'HeroZ', name_jp:'ヒーローズ', size:'small', fy_hint:'September'},
  {ticker:'3858', name:'Ubiquitous AI', name_jp:'ユビキタスAI', size:'small', fy_hint:'September'},
  {ticker:'2326', name:'Digital Arts', name_jp:'デジタルアーツ', size:'small', fy_hint:'March'},
  {ticker:'3825', name:'Remixpoint', name_jp:'リミックスポイント', size:'small', fy_hint:'March'},
  {ticker:'7374', name:'Sharing Innovations', name_jp:'シェアリングイノベーション', size:'small', fy_hint:'September'},
  {ticker:'4071', name:'Plus Alpha Consulting', name_jp:'プラスアルファ・コンサルティング', size:'small', fy_hint:'August'},
  {ticker:'3909', name:'Showcase', name_jp:'ショーケース', size:'small', fy_hint:'December'},
  {ticker:'3983', name:'ORO', name_jp:'オロ', size:'small', fy_hint:'December'},
  {ticker:'4442', name:'Kubell', name_jp:'クベル', size:'small', fy_hint:'December'},
  {ticker:'9416', name:'Vision', name_jp:'ビジョン', size:'small', fy_hint:'December'},
  {ticker:'4293', name:'Septeni Holdings', name_jp:'セプテーニHD', size:'small', fy_hint:'September'},
  {ticker:'9889', name:'JBCC Holdings', name_jp:'JBCCホールディングス', size:'small', fy_hint:'March'},
  {ticker:'4005', name:'Collabos', name_jp:'コラボス', size:'small', fy_hint:'March'},
  {ticker:'4480', name:'Medley', name_jp:'メドレー', size:'small', fy_hint:'December'},
  {ticker:'4722', name:'Future', name_jp:'フューチャー', size:'small', fy_hint:'December'},
  {ticker:'2371', name:'Kakaku.com', name_jp:'カカクコム', size:'small', fy_hint:'March'},
  {ticker:'4755', name:'Rakuten Group', name_jp:'楽天グループ', size:'small', fy_hint:'December'},
  {ticker:'3776', name:'Broadmedia', name_jp:'ブロードメディア', size:'small', fy_hint:'March'},
]

const BIZ_TAGS = `business_reason_tag（業績が動いた本当の理由。1つだけ。合わなければ "other"）:
  one-off_cost_rolloff   — 前期の一過性費用（減損・引当・特別損失）が剥落し利益が反発
  one_off_gain           — 当期の一過性利益（資産・子会社株式売却益・特別利益等）が利益を押し上げ（本業改善ではない）
  one_off_loss           — 当期の一過性損失（減損・特別損失・訴訟/不祥事関連費用・撤退損等）で利益が押し下げ（本業悪化ではない）
  one_off_gain_rolloff   — 前期の一過性利益（株式・資産売却益・特別利益等）が当期は無くなり、その反動で利益が減少（本業悪化ではない＝高基準の反動）
  margin_expansion       — 一過性要因が無いことを確認した上で、高採算事業の構成比上昇・単価改善・コスト効率化でマージン拡大
  margin_compression     — コスト増・価格競争・先行投資でマージン悪化
  volume_demand_growth   — 数量・需要・契約数の伸びで増収増益
  price_arpu_growth      — 単価・ARPU・値上げで増益
  m&a_consolidation      — M&A・新規連結・子会社化で規模拡大
  fx_tailwind            — 円安など為替の追い風が主因
  fx_headwind            — 為替差損・円高など為替の逆風で利益が減少
  cyclical_recovery      — 市況・業界サイクルの回復が主因
  other                  — 上記に当てはまらない（無理に当てはめない）`

const SCHEMA = {
  type: 'object',
  properties: {
    ticker:{type:'string'}, name:{type:'string'}, name_jp:{type:'string'}, size:{type:'string'},
    fy_label:{type:'string'}, announce_date:{type:'string'}, category_provisional:{type:'string'},
    rev_abs:{type:'string'}, rev_prev_abs:{type:'string'},
    net_abs:{type:'string'}, net_prev_abs:{type:'string'},
    rev_pct:{type:'string'}, op_pct:{type:'string'}, net_pct:{type:'string'},
    revenue_dir:{type:'string'}, op_dir:{type:'string'}, net_dir:{type:'string'}, rev_yoy:{type:'number'},
    guidance_op_jp:{type:'string'}, guidance_source:{type:'string'},
    catalysts:{type:'string'}, one_off_note:{type:'string'}, one_off_probe_result:{type:'string'},
    consensus_note:{type:'string'},
    stock_dir:{type:'string'}, business_reason_tag:{type:'string'}, stock_reason_tag:{type:'string'},
    overview:{type:'string'}, how_business_moved:{type:'string'}, why_business_moved:{type:'string'},
    why_stock_moved:{type:'string'}, unverified:{type:'string'}, biz_classification:{type:'string'},
    grounding_check:{type:'string'}, sources:{type:'array', items:{type:'string'}}
  },
  required: ['ticker','name','fy_label','announce_date','rev_pct','net_pct','revenue_dir',
             'business_reason_tag','why_business_moved','overview','stock_dir',
             'one_off_probe_result','grounding_check']
}

function makePrompt(c) {
  const fm = FY_META[c.fy_hint]
  return `あなたは日本株アナリストです。${c.ticker} ${c.name_jp}（${c.name}, ${c.size}）の${fm.fy_jp}（${fm.fy}, 発表${fm.announce}頃）通期決算を、ポイント・イン・タイム（発表日時点で公開の情報のみ）で調査します。

【データ収集 ── 権威ある一次資料を1回フェッチして使い回す】
SEARCH（WebSearch）: 公式の決算短信/IRリリースのURLを特定。
  クエリ例: "${c.ticker} ${c.name_jp} ${fm.fy_jp} 決算短信 業績予想 IR ${fm.announce}"
FETCH（WebFetch）: 最も権威ある一次資料（公式IRリリース／決算短信）を取得し、**同じ資料から**抽出:
  • 売上高・営業利益・純利益：当期実績の【実額】と【前期実額】を取得。営業利益は必ず【報告ベース（IFRS/J-GAAP）の営業利益】を使うこと。非GAAP・「コア営業利益」・「調整後EBITDA」・「事業利益」等の独自指標を報告営業利益として転記しない（社内指標は別物。両方ある場合は報告値を採用し、独自指標は consensus_note 等に補足）。
  • 純利益は必ず【親会社の所有者に帰属する当期利益】を使う（非支配持分を含む当期利益総額ではない）。また後日修正(restatement)ではなく【発表時点(announce_date)の原開示値】を使う（ポイント・イン・タイム）。
  • 翌期(${fm.next_fy_jp})ガイダンス：**業績予想テーブルの行のみ**（「〜と見込む/予想」）。中計目標（「〜を目指す」）は不可。両方あれば業績予想。確認できなければ "確認不可"。
  • 同時発表カタリスト：自己株買い（総額・上限株数・発行済比率・期間）・TOB・増配・M&A・格上げ等を【具体的数値】で。
  • 会社が述べる業績変動の理由（概況/MD&A）。

【⚠️ 前期比%の自己検算（必須）】
rev_pct / op_pct / net_pct は、取得した【当期実額】と【前期実額】から自分で計算し直すこと（(当期-前期)/前期×100）。
検索要約の「+X%」をそのまま転記しない。実額(rev_abs, rev_prev_abs, net_abs, net_prev_abs)も併記し、%と整合させること。

【⚠️ 一過性プローブ（必須・双方向）】
売上成長率と利益成長率に大きな乖離がある場合（差が概ね2倍以上／符号が異なる／純利益が営業利益と大きく異なる動き）、**または報告営業利益の伸びが会社開示の「調整後/コア/事業利益」等の伸びを大きく上回る場合**（例：報告OP+51% vs 調整後EBITDA+13% ＝ 一過性が隠れている兆候）、その乖離の原因を必ず切り分けること。**追加で1回 WebSearch**を実施し、以下を判定：
  (a) 前期に一過性費用（減損・引当・特損）があり当期剥落して利益反発 → one-off_cost_rolloff
  (b) 当期に一過性利益（資産・子会社株式の売却益・特別利益）で利益が押し上げ → one_off_gain
  (c) 当期に一過性損失（減損・特別損失・訴訟/不祥事関連・撤退損）で利益が押し下げ → one_off_loss（為替差損が主因なら fx_headwind）
  (d) 前期に一過性利益（売却益・特別利益）があり当期その剥落で利益が減少（高基準の反動）→ one_off_gain_rolloff
  (e) 一過性要因が無く本業のマージン構造変化が主因 → margin_expansion / margin_compression
  ※ 方向の区別を厳守：当期に利益を【押し上げた】one-off → one_off_gain／前期の利益が【無くなり当期減益】→ one_off_gain_rolloff（混同しない）。
  ⚠️ net_dir が op_dir と逆（営業増益なのに純利益が減る等）の場合は、営業外・特別損益・税の一過性を必ず確認し、business_reason_tag を「利益が動いた支配的要因」に合わせること（営業が横ばいでも純益急減なら fx_headwind や one_off_loss を優先）。
  クエリ例："${c.ticker} ${c.name_jp} ${fm.prev_fy_jp} OR ${fm.fy_jp} 減損 OR 引当 OR 特別損益 OR 売却益 OR 為替差損 一過性"
  one_off_probe_result に、確認できた一過性要因（種類・名称・金額・年度）を1行で記載。確認できなければ「一過性要因は確認されず（本業要因）」と明記。

【⚠️ グラウンディング規則】
原因の「具体的な名称・内訳」は、資料で確認できた場合のみ記載。確認できない具体名の推測・創作は禁止（もっともらしいが未確認の原因名を書かない）。原則「曖昧でも正しい＞具体的でも誤り」。
grounding_check に、why_business_moved の各具体原因がどの資料で確認できたか（または「具体名未確認のため一般表現に留めた」）を1行で記載。

【ポイント・イン・タイム厳守】カタリストは発表時点の枠のみ（完了額・平均単価・早期完了日は書かない）。同年数値の後日修正・2週間超後の株価/アナリスト動向も不使用。

【⛔ 株価方向は推定しない】
stock_dir="pending" 固定（Pythonが実株価で確定）。why_stock_moved=""（Phase 2で記入）。stock_reason_tag="pending"。category_provisional は revenue 側のみ（例 "R+xS?"）。

${BIZ_TAGS}

【ナレーティブ（平易な日本語・一般読者向け・各2〜3行）】
• overview：1行。会社が何をしているか。
• how_business_moved：1〜2行。主要数字を言葉で。
• why_business_moved：2〜3行。専門用語を避け平易に。支配的な理由を最初に（一過性プローブの結論を反映）。一過性なら正直にそう書く。【空欄禁止】投資持株会社（例：投資損益が主因）でも、利益変動の支配的要因を必ず平易に記述すること。
• unverified：1行。確認できなかった点。

【返却（StructuredOutput）】
ticker="${c.ticker}", name="${c.name}", name_jp="${c.name_jp}", size="${c.size}", fy_label="${fm.fy}",
announce_date, category_provisional, rev_abs, rev_prev_abs, net_abs, net_prev_abs,
rev_pct, op_pct, net_pct, revenue_dir, op_dir, net_dir, rev_yoy(数値),
guidance_op_jp, guidance_source, catalysts, one_off_note, one_off_probe_result, consensus_note,
stock_dir="pending", business_reason_tag, stock_reason_tag="pending",
overview, how_business_moved, why_business_moved, why_stock_moved="", unverified, biz_classification, grounding_check, sources`
}

// ── subset control (RELIABLE: hardcoded, not args) ──────────────────────────
// ⚠️ To run a SUBSET, list tickers here. To run ALL 100, set SUBSET = [].
const SUBSET = ['4689','9984']
const RUN = SUBSET.length ? COMPANIES.filter(c => SUBSET.includes(c.ticker)) : COMPANIES
log(`Phase-1 MODE: ${SUBSET.length ? 'SUBSET' : 'FULL'} — ${RUN.length} companies: ${RUN.map(c=>c.ticker).join(',')}`)
if (SUBSET.length && RUN.length !== SUBSET.length) {
  log(`WARNING: SUBSET had ${SUBSET.length} tickers but only ${RUN.length} matched COMPANIES`)
}

phase('Research')
const results = await pipeline(
  RUN,
  c => agent(makePrompt(c), {label: c.ticker, phase: 'Research', schema: SCHEMA})
)
const valid = results.filter(Boolean)
log(`Phase-1 complete: ${valid.length}/${RUN.length}`)

// ── assemble + write JSON ───────────────────────────────────────────────────
phase('Build')
const companies = {}
for (const r of valid) companies[r.ticker] = {...r, sector: 'IT', en_summary: ''}

const outputJson = {
  _meta: {
    quarter: 'Q4', year: 2025, sector: 'IT', universe_size: valid.length,
    generated_by: 'it-q4-phase1-final (grounded, two-way probe, net self-check)',
    note: 'stock_dir=pending until patch_stock_prices.py runs; stock reason added in Phase-2',
  },
  companies,
}
const suffix = SUBSET.length ? '_refetch' : ''
const dataPath = `${ROOT}/data/quarterly/it_q4_2025${suffix}.json`
await agent(
  `Write this exact JSON to ${dataPath} using the Write tool (overwrite if exists). After writing, confirm path + company count.\n\n${JSON.stringify(outputJson, null, 2)}`,
  {label: 'write-json', phase: 'Build'}
)
return {written: dataPath, count: valid.length, tickers: valid.map(r => r.ticker)}
