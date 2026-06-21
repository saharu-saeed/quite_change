// IT Q4 FY-ending-2025 — Phase 2 (final assembled)
// Runs AFTER Phase-1 JSON is written and patch_stock_prices.py has filled verified stock_dir.
// Writes why_stock_moved + stock_reason_tag from the VERIFIED direction.
// NRI-type guard baked in: capital_return_surprise only when a LARGE buyback/TOB/special
// return is the dominant catalyst; a modest dividend + big up-move on a clean beat = rerating_on_growth.
// Subset: args.tickers ; input file: args.suffix ('' full, '_subset' for the subset JSON)
export const meta = {
  name: 'it-q4-phase2-final',
  description: 'IT Q4 Phase-2: stock reason + bucket tag from verified direction',
  phases: [{title: 'StockReason', detail: 'one search each, plain why + direction-consistent bucket'}]
}

const ROOT = 'c:/Users/Sahal Saeed/Documents/tempest_ai/quick/New_quick/new_quick/quite_change'

const STOCK_TAGS = `stock_reason_tag（verified方向と整合する1つ。合わなければ "other"）:
  ── UP (S+) 系 ──
  capital_return_surprise — 【大型】自社株買い・TOB・特別還元が支配的カタリストで好感（※小幅増配のみでは選ばない）
  rerating_on_growth      — 好決算（コンセンサス超過・利益率改善・構造成長）への再評価で買われた
  ── DOWN (S-) 系 ──
  guidance_disappointment — 翌期ガイダンスが保守的/未開示/減益で失望売り
  consensus_miss          — 実績が市場コンセンサスを下回り売られた
  sector_narrative_cooling— セクターテーマの一服・過熱感後退で売られた
  valuation_too_high      — 好材料でも株価が先行・割高で出尽くし売り
  ── 双方向 ──
  no_coverage_overlooked  — カバレッジ薄で材料が株価に反映されにくい
  muted_no_reaction       — ほぼ無反応（±1%以内のflat）
  other                   — 上記に当てはまらない`

const SCHEMA = {
  type:'object',
  properties:{
    ticker:{type:'string'}, why_stock_moved:{type:'string'}, stock_reason_tag:{type:'string'},
    stock_reason_note:{type:'string'}, sources:{type:'array',items:{type:'string'}}
  },
  required:['ticker','why_stock_moved','stock_reason_tag']
}

function makePrompt(c){
  const pct = (c.stock_pct_change!=null) ? `${c.stock_pct_change}%` : c.stock_2w_estimate
  return `あなたは日本株アナリストです。${c.ticker} ${c.name_jp}（${c.name}）の${c.fy_label}決算（発表${c.announce_date}）について、**決算後の株価の実際の方向はPython/実株価で検証済み**です。その方向を前提に「株価が動いた理由」を説明し、バケットタグを選んでください。

【検証済みの株価反応（10営業日, ±1%閾値）】
  方向: ${String(c.stock_dir).toUpperCase()}（${pct}）← 確定事実。覆さないこと。

【Phase-1で判明した事実】
  カタリスト: ${c.catalysts || 'なし'}
  コンセンサス/利益の質: ${c.consensus_note || '不明'}
  翌期ガイダンス: ${c.guidance_op_jp || '確認不可'}
  業績の理由(business_reason_tag): ${c.business_reason_tag}

【タスク】
1. WebSearchを**1回だけ**実施し、「なぜ株価がその方向（${c.stock_dir}）に動いたか」の市場の受け止めを確認。
   クエリ例: "${c.ticker} ${c.name_jp} 決算 株価 ${c.stock_dir==='up'?'上昇 買われた':(c.stock_dir==='down'?'下落 売られた':'反応')} ${String(c.announce_date).slice(0,7)}"
2. why_stock_moved（平易な日本語・一般読者向け・2〜3行）。検証済み方向（${c.stock_dir}）と必ず整合。支配的要因を最初に。カタリスト/利益の質/コンセンサス比を正直に反映。
   ⚠️ KDDI型注意：大型還元があっても株価が下げたなら、還元より「コンセンサス未達」等が勝ったと素直に書く。
3. stock_reason_tag を1つ選ぶ（方向と整合必須）。
   ⚠️ NRI型注意：小幅増配だけで株価が大きく上昇した場合は capital_return_surprise ではなく rerating_on_growth（好決算への再評価）を選ぶ。capital_return_surprise は【大型】自社株買い・TOB・特別還元が支配的な場合のみ。

${STOCK_TAGS}

【返却】ticker="${c.ticker}", why_stock_moved, stock_reason_tag, stock_reason_note（タグ選択根拠1行）, sources`
}

// ── load Phase-1 + priced JSON ──────────────────────────────────────────────
const suffix = (args && args.suffix) ? args.suffix : ''
const inPath = `${ROOT}/data/quarterly/it_q4_2025${suffix}.json`
const raw = await agent(
  `Read the JSON file at ${inPath} and return its raw contents verbatim (just the file text, no commentary).`,
  {label: 'read-json', phase: 'StockReason'}
)
const data = JSON.parse(raw.slice(raw.indexOf('{'), raw.lastIndexOf('}') + 1))
let list = Object.values(data.companies)
if (args && Array.isArray(args.tickers)) list = list.filter(c => args.tickers.includes(c.ticker))
log(`Phase-2 on ${list.length} companies (suffix='${suffix}')`)

phase('StockReason')
const results = (await pipeline(
  list,
  c => agent(makePrompt(c), {label: c.ticker, phase: 'StockReason', schema: SCHEMA})
)).filter(Boolean)

// merge back + write
for (const r of results) {
  if (data.companies[r.ticker]) {
    data.companies[r.ticker].why_stock_moved = r.why_stock_moved
    data.companies[r.ticker].stock_reason_tag = r.stock_reason_tag
    data.companies[r.ticker].stock_reason_note = r.stock_reason_note || ''
  }
}
await agent(
  `Write this exact JSON to ${inPath} using the Write tool (overwrite). Confirm path + count.\n\n${JSON.stringify(data, null, 2)}`,
  {label: 'write-json', phase: 'StockReason'}
)
return results.map(r => ({ticker: r.ticker, tag: r.stock_reason_tag}))
