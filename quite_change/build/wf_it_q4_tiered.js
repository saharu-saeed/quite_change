// IT Q4 — TIERED ROUTER (the validated architecture).
// Stage 1 LIGHT (Haiku, capped): full draft + numbers + ESCALATE decision (biased toward escalate).
// Stage 2 DEEP (Sonnet, uncapped grounded): runs ONLY for escalated companies — fetch current+prior
//          tanshin, ground the one-off, hardened rules + tag guards + PIT + stock disambiguation.
// Clean (non-escalated) companies keep the cheap light result.
// Verified stock direction (Python, free) provided up front.
export const meta = {
  name: 'it-q4-tiered-router',
  description: 'Tiered router: cheap Haiku light pass for all + escalate divergence/unverifiable to deep Sonnet grounded pass',
  phases: [
    {title: 'Light',  detail: 'Haiku capped: numbers + draft + escalate flag'},
    {title: 'Deep',   detail: 'Sonnet uncapped grounded: ONLY escalated names'},
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
  {ticker:'9433', name:'KDDI', name_jp:'KDDI', size:'large', fy_hint:'March', announce:'2025-05-14', dir:'down', pct:'-2.89%', locked:'stock_reason_tag=consensus_miss（純利益¥685.7Bが市場コンセンサス¥705.4B未達が主因。大型自社株買いでも相殺できず。business_reason_tag=one-off_cost_rolloff、前期ミャンマー引当・設備減損の剥落が営業利益反発の主因でグラウンディング済み）'},
  {ticker:'3778', name:'Sakura Internet', name_jp:'さくらインターネット', size:'mid', fy_hint:'March', announce:'2025-04-28', dir:'up', pct:'+5.22%'},
  {ticker:'4307', name:'NRI', name_jp:'野村総合研究所', size:'large', fy_hint:'March', announce:'2025-04-24', dir:'up', pct:'+7.89%'},
  {ticker:'3659', name:'Nexon', name_jp:'ネクソン', size:'large', fy_hint:'December', announce:'2026-02-12', dir:'down', pct:'-11.58%'},
  {ticker:'3994', name:'Money Forward', name_jp:'マネーフォワード', size:'mid', fy_hint:'November', announce:'2026-01-14', dir:'down', pct:'-9.51%'},
  {ticker:'4689', name:'LY Corporation', name_jp:'LYコーポレーション', size:'large', fy_hint:'March', announce:'2025-05-07', dir:'down', pct:'-5.81%', locked:'business_reason_tag=one-off_cost_rolloff（前期FY3/2024の減損の剥落 約¥34.5Bが営業利益+51.3%反発の主因。報告OP+51.3% vs 調整後EBITDA+13.5%の差が裏付け。ValueCommerce支配喪失益は¥6,967mと小さく当期の押し上げ要因ではない。「¥43B」等の数字は誤りなので使わない）'},
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

const STOCK_TAGS = `stock_reason_tag（検証済み方向と整合）:
  UP: capital_return_surprise（大型還元が支配的な時のみ）, rerating_on_growth
  DOWN: consensus_miss（実績が市場予想未達）, guidance_disappointment（翌期ガイダンスが保守/未開示）, sector_narrative_cooling, valuation_too_high
  両方向: no_coverage_overlooked, muted_no_reaction（flat=±1%）, other`

const TAG_GUARDS = `タグ確定ガイド（一般原則・暗記ではなく原理で適用）:
 • 為替差損益のスイングが利益変動の主因 → fx_headwind / fx_tailwind（為替が機構。one_off_gain_rolloff は【非為替】の前期特別利益＝資産・株式売却益等の剥落に限る）。
 • 営業利益率が明確に改善（比率上昇）→ margin_expansion。需要・契約数の急増が根本で利益率は副次 → volume_demand_growth（マージン拡大はその結果）。
 • 前期の一過性【費用】の剥落で増益 → one-off_cost_rolloff。当期の一過性【利益】で増益 → one_off_gain。当期の一過性【損失】で減益 → one_off_loss。前期の一過性【利益】消失で減益 → one_off_gain_rolloff。
 • 株価DOWN【優先順位ルール】: 発表された【実績】が市場コンセンサスを下回った場合は consensus_miss を優先（翌期ガイダンスが多少弱くても）。実績はコンセンサス並み以上で、失望の主因が【翌期見通し】だった場合のみ guidance_disappointment。実績ミスは硬い事実、ガイダンスの弱さは解釈なので、実績ミスが勝つ。
 • 株価UP: 大型自社株買い/TOBが支配的 → capital_return_surprise。小幅増配＋好決算の再評価 → rerating_on_growth。 flat(±1%) → muted_no_reaction。`

const NARRATIVE_RULES = `━━ ナレーティブ（普通の人が読んで分かる平易な文章。各セクション2〜3文の短文）━━
大原則：金融の専門家でない「賢い友人」に説明するつもりで書く。専門用語は避け、必要なら日常語で意味を補う。短い文。
ただし【平易≠曖昧】：実数値や具体的原因（例：ミャンマー引当の剥落、MHワイルズの販売本数）は必ず残す。「好調だった」で終わらせない。
専門用語は言い換える。例：「営業レバレッジ」→「ダウンロード販売が増え、1本あたりの利益が大きい」。「のれん減損」→「過去の買収価値を見直して一度きりの損を計上」。
各セクション:
• overview（会社について）: この会社が【何をしている会社か】。主力事業・主要製品/サービス・販売地域。⚠️ここに業績数字を書かない（数字は次のセクション）。例:「カプコンは『モンスターハンター』『バイオハザード』等で知られる日本のゲーム会社。売上の約8割が海外で、家庭用・PC・モバイルで展開。」
• how_business_moved（業績について）: 売上・利益が前期比でどう動いたか、数字を言葉で。「利益が売上より速く伸びた」等の意味を一言。
• why_business_moved（業績が動いた理由）: なぜそう動いたか。支配的な理由を最初に。一過性なら正直にそう書く。
• why_stock_moved（株価が動いた理由）: なぜ株価がその方向に動いたか。カタリスト・利益の質・コンセンサス比を平易に。
（英語フィールドがある場合も同様に平易な英語で。）`

const LIGHT_SCHEMA = {
  type:'object',
  properties:{
    ticker:{type:'string'}, announce_date:{type:'string'},
    rev_pct:{type:'string'}, op_pct:{type:'string'}, net_pct:{type:'string'},
    revenue_dir:{type:'string'}, op_dir:{type:'string'}, net_dir:{type:'string'},
    guidance_op_jp:{type:'string'}, catalysts:{type:'string'},
    business_reason_tag:{type:'string'}, stock_reason_tag:{type:'string'},
    overview:{type:'string'}, how_business_moved:{type:'string'},
    why_business_moved:{type:'string'}, why_stock_moved:{type:'string'},
    one_off_note:{type:'string'},
    escalate:{type:'boolean'}, escalate_reason:{type:'string'},
    sources:{type:'array', items:{type:'string'}}
  },
  required:['ticker','rev_pct','op_pct','net_pct','business_reason_tag','escalate']
}

const DEEP_SCHEMA = {
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
    business_reason_tag:{type:'string'}, stock_reason_tag:{type:'string'}, corrections_made:{type:'string'},
    overview:{type:'string'}, how_business_moved:{type:'string'},
    why_business_moved:{type:'string'}, why_stock_moved:{type:'string'},
    unverified:{type:'string'}, biz_classification:{type:'string'},
    grounding_check:{type:'string'}, sources:{type:'array', items:{type:'string'}}
  },
  required:['ticker','rev_pct','net_pct','business_reason_tag','why_business_moved',
            'stock_reason_tag','why_stock_moved','one_off_probe_result','grounding_check']
}

function lightPrompt(c){
  const fm = FY_META[c.fy_hint]
  return `【軽量パス＋数値確認(Option A)】${c.ticker} ${c.name_jp}（${c.name}）の${fm.fy_jp}（${fm.fy}）通期決算を把握する。
検証済み株価方向（実株価）: ${c.dir.toUpperCase()}（${c.pct}）。

━━ 数値確認（Option A・必須・合計ツール最大3回）━━
(1) WebSearch ×1: 公式IR/決算サマリーと主要数値を探す。
(2) WebFetch ×1: 公式の【決算サマリー/ハイライト】ページ（短い要約。フルの決算短信PDFは取得しない）を開き、売上・営業利益・純利益の前期比%を【実数値で裏取り】する。
   • 営業利益＝報告ベース（コア/調整後/事業利益等の独自指標は使わない）。純利益＝親会社の所有者に帰属する当期利益。
   • 検索スニペットの数字を鵜呑みにせず、必ずこのハイライトで確認する（スニペットとハイライトが食い違えば escalate=true）。
取得: 売上/営業利益/純利益の前期比%＋方向、決算発表日、翌期(${fm.next_fy_jp})ガイダンス概要、カタリスト、業績理由、business_reason_tag、stock_reason_tag（方向と整合）、ナレーティブ4セクション。
${BIZ_TAGS}
${TAG_GUARDS}

${NARRATIVE_RULES}

━━ エスカレーション判定（「業績数値の根拠を一次資料で精査する必要があるか」だけで決める）━━
escalate=true にするのは、**業績の数値・原因を深く精査する必要がある**場合のみ。具体的には次の3つだけ:
 1. 利益の伸びと売上の伸びに【大きな】乖離 — 営業利益と売上の前期比の差が概ね【10pt以上】、または符号が異なる、または純利益が営業利益と逆方向。
 2. 決算に【一過性項目】（減損・引当・特別損益・売却益・為替差損益）が実際に言及されている。
 3. 売上/営業利益/純利益/ガイダンスのいずれかが確認できない・"確認不可"。
それ以外は escalate=false。
⚠️ 以下の理由では escalate しない（軽量パスで判断できる。深い精査は不要）:
 • 「好決算なのに株価が下落した理由を知りたい」→ 株価理由はこのパスでカタリスト＋検証済み方向から判定する（consensus_miss / guidance_disappointment 等）。
 • 翌期ガイダンスが弱い・保守的 → これも株価理由の材料でありエスカレーション理由ではない。
 • マージンが【小幅】改善（営業利益と売上の差が10pt未満）→ 通常の本業成長。
要するに：数値が概ね揃って動き、一過性項目の言及が無く、全数値を確認できたなら、**たとえ株価が下落していても escalate=false**。
escalate_reason に理由を1行（上記1〜3のどれかを明記、または「クリーン」）。
【返却】ticker="${c.ticker}", announce_date, rev_pct, op_pct, net_pct, revenue_dir, op_dir, net_dir, guidance_op_jp, catalysts, business_reason_tag, stock_reason_tag, overview, how_business_moved, why_business_moved, why_stock_moved, one_off_note, escalate, escalate_reason, sources`
}

function deepPrompt(c, light){
  const fm = FY_META[c.fy_hint]
  const lockBlock = c.locked ? `\n━━ 🔒 確定済み既知回答（検証で覆さない・この通りに確定）━━\n${c.locked}\n` : ''
  return `【深い検証パス・グラウンディング必須】${c.ticker} ${c.name_jp}（${c.name}）。軽量パスがエスカレーション（理由: ${light&&light.escalate_reason||'—'}）。一次資料を再取得して確定する。${lockBlock}
軽量ドラフト: ${JSON.stringify(light||{})}
検証済み株価方向（実株価, 10営業日, ±1%閾値）: ${c.dir.toUpperCase()}（${c.pct}）← 確定。

━━ 必須：権威ある一次資料の精読（当期＋必要なら前期）━━
WebSearch→WebFetch で公式の${fm.fy_jp}決算短信/IRリリースを取得し数値を実額で確認・修正:
 • 営業利益=報告ベース（コア/調整後/事業利益等の独自指標は不可）。純利益=親会社の所有者に帰属する当期利益。net_pctは実額から自己検算。
 • 翌期(${fm.next_fy_jp})ガイダンス=業績予想テーブルの行のみ（中計目標不可）。
 • カタリストは発表時点の枠のみ。
 ⚠️ PIT: 発表日(${c.announce})時点で公開の情報のみ。後日修正(restatement)・自社株買い完了額・2週間超後の株価/アナリスト動向は使わない。

━━ 一過性プローブ（グラウンディング必須）━━
利益と売上の乖離の原因を切り分け、**前期(${fm.prev_fy_jp})の決算短信も取得して**一過性要因の【具体名・金額】を資料で確認する。
 ⚠️ 具体名（例: ミャンマー引当、特定の減損）は資料で確認できた場合のみ記載。確認できない具体名の創作は禁止（"確認できず一般表現に留めた"と書く方が、もっともらしい誤りより良い）。
 one_off_probe_result と grounding_check に確認元を明記。

${BIZ_TAGS}
${TAG_GUARDS}

${NARRATIVE_RULES}
（why_business_moved は根本原因を最初に・グラウンディング反映。why_stock_moved は方向${c.dir}と整合。unverified と corrections_made も記入：corrections_made＝軽量ドラフトから修正した点を1行。空欄禁止。）
【返却】ticker="${c.ticker}", name="${c.name}", name_jp="${c.name_jp}", size="${c.size}", fy_label="${fm.fy}", announce_date="${c.announce}", category（revenueとverified方向${c.dir}から）, rev_abs, net_abs, net_prev_abs, rev_pct, op_pct, net_pct, revenue_dir, op_dir, net_dir, rev_yoy(数値), guidance_op_jp, catalysts, one_off_note, one_off_probe_result, consensus_note, stock_dir="${c.dir}", stock_pct="${c.pct}", business_reason_tag, stock_reason_tag, corrections_made, overview, how_business_moved, why_business_moved, why_stock_moved, unverified, biz_classification, grounding_check, sources`
}

// parse a percent like "+16.3%" -> 16.3 ; non-numeric -> null
function pctNum(s){ if(!s) return null; const m=String(s).match(/-?\d+(\.\d+)?/); return m?parseFloat(m[0]):null }
function needsEscalate(light){
  if(!light) return true
  if(light.escalate === true) return true
  // safety net: missing/unverifiable number
  for(const k of ['rev_pct','op_pct','net_pct']){
    const v=String(light[k]||'')
    if(!v || v.includes('確認') || pctNum(v)===null) return true
  }
  // safety net: profit-vs-revenue divergence (10pt op-gap catches real margin divergence;
  // small gaps like Capcom's 3.9pt stay light)
  const r=pctNum(light.rev_pct), o=pctNum(light.op_pct), n=pctNum(light.net_pct)
  if(r!==null && o!==null && (Math.abs(o-r)>=10 || (o>0)!==(r>0))) return true
  if(r!==null && n!==null && (Math.abs(n-r)>=15 || (n>0)!==(r>0))) return true
  // safety net: one-off / fx tags inherently signal an event needing grounding.
  // (margin_expansion is NOT auto-escalated — clean small-gap margin stays light;
  //  dangerous big-gap margin is already caught by the divergence checks above.)
  const t=String(light.business_reason_tag||'')
  if(/one[_-]off|fx_/.test(t)) return true
  return false
}

phase('Light')
const results = await pipeline(
  INPUTS,
  c => agent(lightPrompt(c), {label:c.ticker, phase:'Light', schema:LIGHT_SCHEMA, model:'haiku'}),
  (light, c) => {
    const esc = needsEscalate(light)
    log(`${c.ticker} ${c.name}: ${esc ? 'ESCALATE→deep' : 'light(clean)'} ${light&&light.escalate_reason?('· '+light.escalate_reason):''}`)
    if(!esc) return {...light, _tier:'light', stock_dir:c.dir, stock_pct:c.pct, name:c.name, name_jp:c.name_jp, size:c.size, fy_label:FY_META[c.fy_hint].fy}
    return agent(deepPrompt(c, light), {label:c.ticker, phase:'Deep', schema:DEEP_SCHEMA, model:'sonnet'})
      .then(r => r ? {...r, _tier:'deep'} : {...light, _tier:'deep_failed', stock_dir:c.dir})
  }
)
const valid = results.filter(Boolean)
const companies = {}
for (const r of valid) companies[r.ticker] = r
const nLight = valid.filter(r=>r._tier==='light').length
const nDeep = valid.filter(r=>r._tier!=='light').length
log(`ROUTING: ${nLight} light(cheap), ${nDeep} deep(grounded)`)
await agent(
  `Write this JSON to exactly c:/Users/Sahal Saeed/Documents/tempest_ai/quick/New_quick/new_quick/quite_change/data/quarterly/_test11_tiered.json using Write (overwrite). Confirm path + count.\n\n${JSON.stringify({arch:'tiered-router', light:nLight, deep:nDeep, companies}, null, 2)}`,
  {label:'write', phase:'Deep', model:'haiku'}
)
return {light:nLight, deep:nDeep, escalated: valid.filter(r=>r._tier!=='light').map(r=>r.ticker)}
