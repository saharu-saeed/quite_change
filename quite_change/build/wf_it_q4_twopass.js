// IT Q4 — TWO-PASS pipeline (cost/quality test).
// Pass 1 = light cheap DRAFT on HAIKU (WebSearch only, no PDF fetch).
// Pass 2 = grounded VERIFY+FINALIZE on SONNET (re-reads the primary source, corrects numbers,
//          applies PIT + probe, locks tags). Verified stock direction (Python, free) -> Pass 2.
// Tag-finalization rules live in Pass 2 (consensus_miss vs guidance_disappointment; root cause not consequence).
export const meta = {
  name: 'it-q4-twopass-costtest',
  description: 'Two-pass (Haiku draft -> Sonnet grounded verify) cost/quality test on 11 known-answer companies',
  phases: [
    {title: 'Draft',  detail: 'Haiku: light WebSearch draft of numbers + reason + tag'},
    {title: 'Verify', detail: 'Sonnet: re-read source, correct numbers, PIT, probe, lock tags + stock reason'},
  ]
}

const FY_META = {
  'March':    {fy:'FY3/2025',  fy_jp:'2025年3月期',  prev_fy_jp:'2024年3月期',  next_fy_jp:'2026年3月期'},
  'December': {fy:'FY12/2025', fy_jp:'2025年12月期', prev_fy_jp:'2024年12月期', next_fy_jp:'2026年12月期'},
  'November': {fy:'FY11/2025', fy_jp:'2025年11月期', prev_fy_jp:'2024年11月期', next_fy_jp:'2026年11月期'},
  'February': {fy:'FY2/2025',  fy_jp:'2025年2月期',  prev_fy_jp:'2024年2月期',  next_fy_jp:'2026年2月期'},
  'June':     {fy:'FY6/2025',  fy_jp:'2025年6月期',  prev_fy_jp:'2024年6月期',  next_fy_jp:'2026年6月期'},
}

const INPUTS = [
  {ticker:'9433', name:'KDDI', name_jp:'KDDI', size:'large', fy_hint:'March', announce:'2025-05-14', dir:'down', pct:'-2.89%'},
  {ticker:'3778', name:'Sakura Internet', name_jp:'さくらインターネット', size:'mid', fy_hint:'March', announce:'2025-04-28', dir:'up', pct:'+5.22%'},
  {ticker:'4307', name:'NRI', name_jp:'野村総合研究所', size:'large', fy_hint:'March', announce:'2025-04-24', dir:'up', pct:'+7.89%'},
  {ticker:'3659', name:'Nexon', name_jp:'ネクソン', size:'large', fy_hint:'December', announce:'2026-02-12', dir:'down', pct:'-11.58%'},
  {ticker:'3994', name:'Money Forward', name_jp:'マネーフォワード', size:'mid', fy_hint:'November', announce:'2026-01-14', dir:'down', pct:'-9.51%'},
  {ticker:'4689', name:'LY Corporation', name_jp:'LYコーポレーション', size:'large', fy_hint:'March', announce:'2025-05-07', dir:'down', pct:'-5.81%'},
  {ticker:'9602', name:'Toho', name_jp:'東宝', size:'large', fy_hint:'February', announce:'2025-04-14', dir:'flat', pct:'-0.94%'},
  {ticker:'4676', name:'Fuji Media Holdings', name_jp:'フジ・メディアHD', size:'large', fy_hint:'March', announce:'2025-05-16', dir:'down', pct:'-2.63%'},
  {ticker:'9468', name:'Kadokawa', name_jp:'KADOKAWA', size:'large', fy_hint:'March', announce:'2025-05-08', dir:'up', pct:'+3.80%'},
  {ticker:'4385', name:'Mercari', name_jp:'メルカリ', size:'large', fy_hint:'June', announce:'2025-08-05', dir:'down', pct:'-3.80%'},
  {ticker:'9984', name:'SoftBank Group', name_jp:'ソフトバンクグループ', size:'large', fy_hint:'March', announce:'2025-05-13', dir:'up', pct:'+2.64%'},
]

const BIZ_TAGS = `business_reason_tag（1つ。合わなければ "other"）:
  one-off_cost_rolloff / one_off_gain / one_off_loss / one_off_gain_rolloff /
  margin_expansion / margin_compression / volume_demand_growth / price_arpu_growth /
  m&a_consolidation / fx_tailwind / fx_headwind / cyclical_recovery / other`

const STOCK_TAGS = `stock_reason_tag（検証済み方向と整合する1つ）:
  UP: capital_return_surprise（大型還元が支配的な時のみ）, rerating_on_growth（好決算/予想超過/利益率改善への再評価）
  DOWN: consensus_miss（実績が市場予想未達）, guidance_disappointment（翌期ガイダンスが保守/未開示）, sector_narrative_cooling, valuation_too_high
  両方向: no_coverage_overlooked, muted_no_reaction（flat=±1%以内）, other`

const P1_SCHEMA = {
  type:'object',
  properties:{
    ticker:{type:'string'}, announce_date:{type:'string'},
    rev_pct:{type:'string'}, op_pct:{type:'string'}, net_pct:{type:'string'},
    revenue_dir:{type:'string'}, op_dir:{type:'string'}, net_dir:{type:'string'},
    guidance_draft:{type:'string'}, catalysts_draft:{type:'string'},
    company_stated_reason:{type:'string'}, business_reason_tag_draft:{type:'string'},
    overview:{type:'string'}, how_business_moved:{type:'string'}, why_business_moved_draft:{type:'string'},
    sources:{type:'array', items:{type:'string'}}
  },
  required:['ticker','rev_pct','net_pct','business_reason_tag_draft','overview']
}

const P2_SCHEMA = {
  type:'object',
  properties:{
    ticker:{type:'string'}, name:{type:'string'}, name_jp:{type:'string'}, size:{type:'string'},
    fy_label:{type:'string'}, announce_date:{type:'string'}, category:{type:'string'},
    rev_abs:{type:'string'}, net_abs:{type:'string'}, net_prev_abs:{type:'string'},
    rev_pct:{type:'string'}, op_pct:{type:'string'}, net_pct:{type:'string'},
    revenue_dir:{type:'string'}, op_dir:{type:'string'}, net_dir:{type:'string'}, rev_yoy:{type:'number'},
    guidance_op_jp:{type:'string'}, catalysts:{type:'string'},
    one_off_note:{type:'string'}, one_off_probe_result:{type:'string'}, consensus_note:{type:'string'},
    stock_dir:{type:'string'}, stock_pct:{type:'string'},
    business_reason_tag:{type:'string'}, stock_reason_tag:{type:'string'},
    corrections_made:{type:'string'},
    overview:{type:'string'}, how_business_moved:{type:'string'},
    why_business_moved:{type:'string'}, why_stock_moved:{type:'string'},
    unverified:{type:'string'}, biz_classification:{type:'string'},
    grounding_check:{type:'string'}, sources:{type:'array', items:{type:'string'}}
  },
  required:['ticker','rev_pct','net_pct','revenue_dir','business_reason_tag','why_business_moved',
            'stock_reason_tag','why_stock_moved','one_off_probe_result','grounding_check','corrections_made']
}

function pass1Prompt(c){
  const fm = FY_META[c.fy_hint]
  return `【速報ドラフト】${c.ticker} ${c.name_jp}（${c.name}）の${fm.fy_jp}（${fm.fy}）通期決算をWebSearchで素早く下書きする。PDFのフェッチは不要（次の検証パスが一次資料で精査するため）。
WebSearch（1〜2回）で取得:
 • 売上高・営業利益・純利益の前期比%（概算で可）と決算発表日
 • 翌期(${fm.next_fy_jp})ガイダンスの概要（あれば）
 • 同時発表カタリスト（自社株買い・増配・TOB等、あれば）
 • 会社が述べる業績変動の理由（company_stated_reason）
 • business_reason_tag_draft を下記から仮選択
 • overview / how_business_moved / why_business_moved_draft（各1〜2行・平易）
${BIZ_TAGS}
これは「下書き」。数値やタグは次パスで検証・修正される。確信が持てない箇所はそのまま記載し次パスに委ねてよい。
返却: ticker="${c.ticker}", announce_date, rev_pct, op_pct, net_pct, revenue_dir, op_dir, net_dir, guidance_draft, catalysts_draft, company_stated_reason, business_reason_tag_draft, overview, how_business_moved, why_business_moved_draft, sources`
}

function pass2Prompt(c, draft){
  const fm = FY_META[c.fy_hint]
  return `【検証＋確定パス】あなたは日本株アナリスト。下記は速報ドラフト（誤りを含む可能性あり）。**一次資料を再取得して検証・修正し、最終確定する。**

ドラフト: ${JSON.stringify(draft)}

検証済み株価反応（Python実株価, 10営業日, ±1%閾値）: 方向=${c.dir.toUpperCase()}（${c.pct}）← 確定事実。

━━ 必須：一次資料の再読（テキストレビューだけで承認しない）━━
WebSearch→WebFetch で公式の決算短信/IRリリースを取得し、ドラフトの数値を**実額で確認・修正**:
 • 営業利益=【報告ベース】（コア/調整後/事業利益等の独自指標は不可）。純利益=【親会社の所有者に帰属する当期利益】。
 • net_pct は当期/前期実額から自己検算（ドラフトの%を鵜呑みにしない）。
 • 翌期(${fm.next_fy_jp})ガイダンス=【業績予想テーブルの行のみ】（中計目標は不可）。
 • カタリストは発表時点の枠のみ。
 ⚠️ ポイント・イン・タイム: 発表日(${c.announce})時点で公開の情報のみ。**後日の修正(restatement)・自社株買い完了額・2週間超後の株価/アナリスト動向は使わない。**

━━ 一過性プローブ（双方向・乖離時のみ追加1検索）━━
OPと売上の伸びが大きく乖離／純利益が営業利益と逆／報告OPが調整後を大きく上回る場合のみ切り分け:
 (a)前期費用剥落→one-off_cost_rolloff (b)当期一過性利益→one_off_gain (c)当期一過性損失→one_off_loss(為替差損→fx_headwind) (d)前期利益剥落で減益→one_off_gain_rolloff (e)本業マージン→margin_expansion/compression
 grounding_check に具体原因の確認元を記載（未確認の具体名は創作しない）。

${BIZ_TAGS}

━━ タグ確定ルール（このパスで必ず適用）━━
1. 【根本原因でタグ付け／結果ではなく】例: 需要急増→稼働率上昇→営業レバレッジで増益 は「volume_demand_growth」（根本原因）であって「margin_expansion」（結果）ではない。
2. ${STOCK_TAGS}
3. 【株価DOWNの判別】実績（売上/利益）が市場コンセンサスを下回ったことが主因＝consensus_miss。翌期ガイダンスの弱さが主因＝guidance_disappointment。両にらみの時は「決算当日に何が嫌気されたか」で決める。例: KDDIは純利益がコンセンサス未達が主因なら consensus_miss。
4. 【株価UPの判別】大型自社株買い/TOBが支配的＝capital_return_surprise。小幅増配＋好決算の再評価＝rerating_on_growth。
5. flat（±1%以内）＝muted_no_reaction。

━━ ナレーティブ（平易・各2〜3行・空欄禁止）━━
overview / how_business_moved / why_business_moved（根本原因を最初に）/ why_stock_moved（検証済み方向${c.dir}と整合）/ unverified。
corrections_made: ドラフトから修正した点を1行で（修正なしなら「修正なし」）。

【返却（最終確定）】ticker="${c.ticker}", name="${c.name}", name_jp="${c.name_jp}", size="${c.size}", fy_label="${fm.fy}",
announce_date="${c.announce}", category（revenueとverified方向${c.dir}から 例"R+xS-"）,
rev_abs, net_abs, net_prev_abs, rev_pct, op_pct, net_pct, revenue_dir, op_dir, net_dir, rev_yoy(数値),
guidance_op_jp, catalysts, one_off_note, one_off_probe_result, consensus_note,
stock_dir="${c.dir}", stock_pct="${c.pct}", business_reason_tag, stock_reason_tag, corrections_made,
overview, how_business_moved, why_business_moved, why_stock_moved, unverified, biz_classification, grounding_check, sources`
}

const results = await pipeline(
  INPUTS,
  c => agent(pass1Prompt(c), {label:c.ticker, phase:'Draft', schema:P1_SCHEMA, model:'haiku'}),
  (draft, c) => agent(pass2Prompt(c, draft || {}), {label:c.ticker, phase:'Verify', schema:P2_SCHEMA, model:'sonnet'})
)
const valid = results.filter(Boolean)
const companies = {}
for (const r of valid) companies[r.ticker] = r
await agent(
  `Write this JSON to exactly c:/Users/Sahal Saeed/Documents/tempest_ai/quick/New_quick/new_quick/quite_change/data/quarterly/_test11_twopass.json using Write (overwrite). Confirm path + count.\n\n${JSON.stringify({arch:'haiku-draft+sonnet-verify', companies}, null, 2)}`,
  {label:'write', phase:'Verify', model:'haiku'}
)
return {count: valid.length, tickers: valid.map(r=>r.ticker)}
