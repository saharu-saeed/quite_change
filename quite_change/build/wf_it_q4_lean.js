// IT Q4 — SINGLE-AGENT pipeline (cost test).
// One agent per company: fetch authoritative doc -> numbers/guidance/catalyst/business-reason,
// two-way probe ONLY on divergence, then stock-reason using the VERIFIED direction (provided).
// No Phase-2 reload. Verified price computed up front (Python, free) and passed in-prompt.
// MODEL switch at top: 'sonnet' first (isolate structural saving), then 'haiku'.
export const meta = {
  name: 'it-q4-lean-costtest',
  description: 'LEAN single-agent (HARD tool-call cap) — efficiency test on 11 known-answer companies',
  phases: [{title: 'Research', detail: 'one agent/company, max ~3 tool calls: 1 search + 1 fetch-extract-all + probe-if-divergence'}]
}

const MODEL = 'sonnet'   // <-- change to 'haiku' for the second run

const FY_META = {
  'March':    {fy:'FY3/2025',  fy_jp:'2025年3月期',  prev_fy_jp:'2024年3月期',  next_fy_jp:'2026年3月期'},
  'December': {fy:'FY12/2025', fy_jp:'2025年12月期', prev_fy_jp:'2024年12月期', next_fy_jp:'2026年12月期'},
  'November': {fy:'FY11/2025', fy_jp:'2025年11月期', prev_fy_jp:'2024年11月期', next_fy_jp:'2026年11月期'},
  'February': {fy:'FY2/2025',  fy_jp:'2025年2月期',  prev_fy_jp:'2024年2月期',  next_fy_jp:'2026年2月期'},
  'June':     {fy:'FY6/2025',  fy_jp:'2025年6月期',  prev_fy_jp:'2024年6月期',  next_fy_jp:'2026年6月期'},
}

// 11 known-answer companies. dir/pct = Python-verified (free), provided up front.
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

const BIZ_TAGS = `business_reason_tag（業績が動いた本当の理由。1つだけ。合わなければ "other"）:
  one-off_cost_rolloff   — 前期の一過性費用（減損・引当・特損）が剥落し利益が反発
  one_off_gain           — 当期の一過性利益（売却益・特別利益等）が利益を押し上げ
  one_off_loss           — 当期の一過性損失（減損・特損・不祥事/訴訟費用等）で利益が押し下げ
  one_off_gain_rolloff   — 前期の一過性利益が当期は無くなり、その反動で利益が減少（高基準の反動）
  margin_expansion       — 一過性要因が無いと確認の上、構成比・単価・コスト効率でマージン拡大
  margin_compression     — コスト増・価格競争・先行投資でマージン悪化
  volume_demand_growth   — 数量・需要・契約数の伸びで増収増益
  price_arpu_growth      — 単価・ARPU・値上げで増益
  m&a_consolidation      — M&A・新規連結で規模拡大
  fx_tailwind            — 円安等の為替の追い風 ／ fx_headwind — 為替差損・円高で利益減
  cyclical_recovery      — 市況・サイクルの回復
  other                  — 上記に当てはまらない`

const STOCK_TAGS = `stock_reason_tag（検証済み方向と整合する1つ。合わなければ "other"）:
  UP系:   capital_return_surprise（【大型】自社株買い/TOB/特別還元が支配的な場合のみ）, rerating_on_growth（好決算・コンセンサス超過・利益率改善への再評価）
  DOWN系: guidance_disappointment（翌期保守/未開示）, consensus_miss（実績が市場予想未達）, sector_narrative_cooling, valuation_too_high
  両方向: no_coverage_overlooked, muted_no_reaction（flat=±1%以内）, other`

const SCHEMA = {
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
    overview:{type:'string'}, how_business_moved:{type:'string'},
    why_business_moved:{type:'string'}, why_stock_moved:{type:'string'},
    unverified:{type:'string'}, biz_classification:{type:'string'},
    grounding_check:{type:'string'}, sources:{type:'array', items:{type:'string'}}
  },
  required:['ticker','rev_pct','net_pct','revenue_dir','business_reason_tag','why_business_moved',
            'stock_reason_tag','why_stock_moved','one_off_probe_result','grounding_check']
}

function makePrompt(c){
  const fm = FY_META[c.fy_hint]
  return `あなたは日本株アナリストです。${c.ticker} ${c.name_jp}（${c.name}, ${c.size}）の${fm.fy_jp}（${fm.fy}, 発表${c.announce}）通期決算を、ポイント・イン・タイムで調査し、業績と株価の両方の理由を1回でまとめます。

【検証済みの株価反応（Python実株価, 10営業日, ±1%閾値）】方向: ${c.dir.toUpperCase()}（${c.pct}）← 確定事実。覆さない。

━━ ⚠️ツール呼び出しは最大3回・厳守（コスト効率の要）━━
 (1) WebSearch ×1: 公式の決算短信/IRリリースのURLを特定（数値概要も拾う）
 (2) WebFetch ×1: そのURLを取得し、必要な情報を【この1つの資料から全て】抽出（数値・ガイダンス・カタリスト・業績理由）
 (3) WebSearch ×1（OPと売上が大きく乖離する時のみ＝プローブ）: 前期/当期の一過性要因を確認
 これ以上は検索・フェッチしない。1つの資料を使い回すこと。冗長な再検索は禁止。

━━ データ収集（権威ある一次資料を1回フェッチ）━━
SEARCH→FETCH: 公式の決算短信/IRリリースを特定し取得。**同じ資料から**:
 • 売上高・営業利益・純利益：当期【実額】と【前期実額】。営業利益は【報告ベース】（コア/調整後/事業利益等の独自指標は不可）。純利益は【親会社の所有者に帰属する当期利益】（非支配持分込み総額ではない）。発表時点の原開示値（後日修正は使わない）。
 • 翌期(${fm.next_fy_jp})ガイダンス：【業績予想テーブルの行のみ】（中計目標は不可）。確認不可なら "確認不可"。
 • 同時発表カタリスト：自己株買い/TOB/増配/M&A 等を【具体数値】で（発表時点の枠のみ。完了額・平均単価等の後日情報は書かない）。
 • net_pct は当期/前期の実額から自己検算（検索要約の%を転記しない）。

━━ 一過性プローブ（双方向・乖離時のみ追加1検索）━━
売上成長率と利益成長率が大きく乖離（差≧2倍／符号反転／純利益が営業利益と逆）、または報告OPの伸びが「調整後/コア」の伸びを大きく上回る場合のみ、追加で1回検索し切り分け:
 (a)前期一過性費用の剥落→one-off_cost_rolloff (b)当期一過性利益→one_off_gain (c)当期一過性損失→one_off_loss(為替差損ならfx_headwind) (d)前期一過性利益の剥落で減益→one_off_gain_rolloff (e)一過性なし本業マージン→margin_expansion/compression
 乖離が無ければプローブ不要（one_off_probe_result に「乖離なし・本業要因」と記載）。

━━ グラウンディング規則 ━━
原因の具体名は資料で確認できた場合のみ記載。未確認の具体名の創作は禁止（曖昧でも正しい＞具体的でも誤り）。grounding_check に各具体原因の確認元を1行で。

${BIZ_TAGS}

${STOCK_TAGS}
 ⚠️ 根本原因でタグ付け（結果ではなく）: 例 需要急増→稼働率上昇→営業レバレッジで増益 は volume_demand_growth（根本原因）であって margin_expansion（結果）ではない。
 ⚠️ DOWN判別: 実績（売上/利益）が市場コンセンサス未達が主因＝consensus_miss。翌期ガイダンスの弱さが主因＝guidance_disappointment。両にらみは「決算当日に何が嫌気されたか」で決める（例: KDDIは純利益コンセンサス未達が主因→consensus_miss）。
 ⚠️ NRI型: 小幅増配だけで株価が大きく上昇＝capital_return_surpriseではなくrerating_on_growth。capital_return_surpriseは【大型】還元が支配的な場合のみ。

━━ ナレーティブ（平易・各2〜3行・空欄禁止）━━
overview / how_business_moved / why_business_moved（支配的理由を最初に・プローブ結論反映） / why_stock_moved（検証済み方向${c.dir}と整合・カタリストや利益の質を反映）/ unverified。

【返却】ticker="${c.ticker}", name="${c.name}", name_jp="${c.name_jp}", size="${c.size}", fy_label="${fm.fy}",
announce_date="${c.announce}", category（例 "R+xS-"：revenueとverified方向${c.dir}から）,
rev_abs, net_abs, net_prev_abs, rev_pct, op_pct, net_pct, revenue_dir, op_dir, net_dir, rev_yoy(数値),
guidance_op_jp, catalysts, one_off_note, one_off_probe_result, consensus_note,
stock_dir="${c.dir}", stock_pct="${c.pct}", business_reason_tag, stock_reason_tag,
overview, how_business_moved, why_business_moved, why_stock_moved, unverified, biz_classification, grounding_check, sources`
}

phase('Research')
log(`LEAN cost test (hard tool cap) — MODEL=${MODEL} — ${INPUTS.length} companies`)
const results = await pipeline(
  INPUTS,
  c => agent(makePrompt(c), {label: c.ticker, phase: 'Research', schema: SCHEMA, model: MODEL})
)
const valid = results.filter(Boolean)
const companies = {}
for (const r of valid) companies[r.ticker] = r
await agent(
  `Write this JSON to exactly c:/Users/Sahal Saeed/Documents/tempest_ai/quick/New_quick/new_quick/quite_change/data/quarterly/_test11_lean_${MODEL}.json using Write (overwrite). Confirm path + count.\n\n${JSON.stringify({model:MODEL, companies}, null, 2)}`,
  {label:'write', phase:'Research', model:'haiku'}
)
return {model: MODEL, count: valid.length, tickers: valid.map(r=>r.ticker)}
