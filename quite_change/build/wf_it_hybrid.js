// ════════════════════════════════════════════════════════════════════════════
// IT QUARTERLY — CANONICAL HYBRID PIPELINE (validated, ready to scale)
// ────────────────────────────────────────────────────────────────────────────
// Architecture (locked):
//   • PRICES   : Tempest (J-Quants daily, no lag)            — research/price_feed.py
//   • NUMBERS  : Tempest original 有報 for the exact period   — research/tempest_fetch.py
//                → period-aware fallback to tanshin if restated/missing/stale
//   • THE "WHY": PIT-strict tanshin reader (this script)      — Sonnet
//                fetch the ANNOUNCE-DATE 決算短信; catalysts ONLY from that doc
//   • OUTPUT   : four-part plain-language explanation + business/stock reason tags
//
// Inputs: per-company Tempest packets in data/quarterly/_pkts/{ticker}.json
//         (built free by: python -m research.tempest_fetch ...)
// Companies list via args.companies = [{ticker,name,announce,fy,prevfy,tier,dir,pct}, ...]
// ════════════════════════════════════════════════════════════════════════════
export const meta = {
  name: 'it-hybrid',
  description: 'Canonical hybrid: Tempest numbers/prices + PIT-strict tanshin why reader, with locked tag guards',
  phases: [{title: 'Why', detail: 'per company: Tempest numbers + announce-date 決算短信 → 4-part plain why + tags'}]
}
const PKTDIR='c:/Users/Sahal Saeed/Documents/tempest_ai/quick/New_quick/new_quick/quite_change/data/quarterly/_pkts'

const SCHEMA={ type:'object', properties:{
  ticker:{type:'string'}, tier:{type:'string'},
  business_reason_tag:{type:'string'}, stock_reason_tag:{type:'string'},
  cited_catalyst:{type:'string'}, catalyst_source_date:{type:'string'},
  overview:{type:'string'}, about_business:{type:'string'},
  why_business_moved:{type:'string'}, why_stock_moved:{type:'string'},
  sources:{type:'array',items:{type:'string'}}
}, required:['ticker','business_reason_tag','stock_reason_tag','overview','about_business','why_business_moved','why_stock_moved'] }

// ── LOCKED TAG GUARDS (settled rulings — keep buckets consistent across runs) ──
const TAG_GUARDS = `business_reason_tag:
  one-off_cost_rolloff（前期の一過性費用の剥落で利益増）/ one_off_gain（当期の一過性利益で利益増）/
  one_off_loss（当期の一過性損失で利益減）/ one_off_gain_rolloff（前期の一過性利益消失で利益減）/
  margin_expansion / margin_compression / volume_demand_growth / price_arpu_growth /
  m&a_consolidation / fx_tailwind / fx_headwind / cyclical_recovery / other

⚠️ ガード①【売上サージ要件】volume_demand_growth は【売上が実際に大きく伸びた】時のみ（目安：売上二桁%増）。
   売上の伸びが緩やか（例 +3.8%）でも利益率上昇で増益なら → margin_expansion。
   例：NRIは売上+3.8%・営業利益率16.4%→17.6% → 必ず margin_expansion（volume_demand_growthではない）。
⚠️ ガード②【具体性優先】ある原因が【具体タグ】と【一般タグ】の両方に当てはまる場合、具体タグを使う。
   例：純利益変動の主因が為替差損益のスイング → fx_headwind / fx_tailwind（一般の one_off_gain_rolloff ではない）。
   例：Nexonは為替差損が純利益減の主因 → 必ず fx_headwind。
⚠️ 方向自己チェック：選んだタグの利益方向（gain系=増、loss/gain_rolloff=減）が実際の利益方向と一致するか確認。

stock_reason_tag:
  UP:   capital_return_surprise（【大型】還元が支配的な時のみ）/ rerating_on_growth
  DOWN: consensus_miss / guidance_disappointment / sector_narrative_cooling / valuation_too_high
  flat: muted_no_reaction ／ both: other
⚠️ ガード③【DOWN優先＝実績ミス優先】発表された【実績】が市場コンセンサス未達なら consensus_miss を優先
   （翌期ガイダンスが多少弱くても）。why_stock_moved の文章も【実績のコンセンサス未達】を最初に書き、
   ガイダンスは二次的に。実績は妥当でガイダンスが主因の時のみ guidance_disappointment。
   例：KDDIは純利益¥685.7Bがコンセンサス¥705.4B未達を最初に書き、tag=consensus_miss。
⚠️ ガード④【小幅増配は還元サプライズではない】小幅増配だけで株価上昇＝rerating_on_growth。
   capital_return_surprise は大型自社株買い/TOBが支配的な時のみ。`

function prompt(c){
  const {ticker,name,announce,fy,prevfy,dir,pct,tier} = c
  return `あなたは日本株アナリスト。${ticker} ${name} の${fy}決算を分析し、普通の人が読んで分かる4部構成の説明を書く。

【数値はTempestから取得済み】Read ツールで ${PKTDIR}/${ticker}.json を開き numbers を使う（_pit_overrideがあればそれ／nullなら決算短信本文から補う）。stock_dir=${dir.toUpperCase()}（${pct}）は実株価検証済み・覆さない。

【「理由」は発表日の決算短信を読んで書く（最重要・PIT厳守）】
WebSearch で ${name} の${fy}【決算短信】（${announce}発表）の公式IRページ/PDFを特定し、WebFetch で本文を読む。
 ⚠️ ルース検索のスニペット・後日の資料は使わない。${announce}発表の決算短信そのものに基づく。
 ⚠️【資本還元イベントの年度厳守】自社株買い・増配は、この${fy}決算短信に記載されたもののみ引用可。
    前年/翌年の自社株買い・配当を混同しない。catalyst_source_date に「${announce}発表の決算短信」と明記。
    確認できなければ cited_catalyst="この決算で新規の資本還元発表なし"。
${tier==='hard'
  ? `【一過性プローブ（hard）】利益と売上の乖離があれば原因（減損・引当・売却益・為替差損等）を本文で確認。前期費用の剥落（${prevfy}）か当期の損益かを区別。前期との比較が必要なら ${prevfy} の数値も確認。`
  : `【軽量（easy/clean）】一過性プローブは不要。ただし業績の【具体的ドライバー】（製品・事業の実名）と【この決算のカタリスト】は決算短信本文から必ず拾う（「セグメントが伸びた」で終わらせない）。`}

${TAG_GUARDS}

【4部構成・各3〜4文・物語的で詳しく・平易（専門用語は日常語に）・具体的（実際のドライバーを書く。「セグメントが伸びた」は不可）】
 overview（会社について）: 何をする会社か、主力事業と戦略を物語的に。業績数字は書かない。
 about_business（業績について）: 今期の売上・営業利益・純利益がどう動いたかを数字（%）を言葉で。
  ⚠️【利益ラインの整合】営業利益と純利益の伸びが乖離する場合、後段の「理由」で説明する利益ライン
   （一過性が直撃するのは多くは営業利益）を必ず示す。例：KDDIは営業利益+16.3%（純利益+7.5%より大きい）を示す。
  ⚠️【表面原因を断定しない】後段の「理由」と矛盾する表面原因（「コスト削減」「効率化」等）を断定しない。
   むしろ「効率化のように見えるが実際の理由は別」と次の説明への伏線を張る。
 why_business_moved（業績が動いた理由）: 決算短信に基づく具体的な理由を物語的に（ガード①②適用）。
  一過性項目は可能なら金額も添える（例：約◯◯億円の減損/費用）。
 why_stock_moved（株価が動いた理由）: ${dir}の理由を物語的に（ガード③④適用、カタリストはこの決算のもの）。
  「市場は『成長』ではなく『予想超え』を評価する」など、普通の人に株価ロジックが分かるように。

返却: ticker="${ticker}", tier="${tier}", business_reason_tag, stock_reason_tag, cited_catalyst, catalyst_source_date, overview, about_business, why_business_moved, why_stock_moved, sources`
}

// Company list — hardcoded (args-via-scriptPath isn't reliable). Edit this list to change the batch.
const COMPANIES = [
 {ticker:'9433',name:'KDDI',announce:'2025-05-14',fy:'2025年3月期',prevfy:'2024年3月期',dir:'down',pct:'-2.89%',tier:'hard'},
 {ticker:'3778',name:'さくらインターネット',announce:'2025-04-28',fy:'2025年3月期',prevfy:'2024年3月期',dir:'up',pct:'+5.22%',tier:'hard'},
 {ticker:'4307',name:'野村総合研究所',announce:'2025-04-24',fy:'2025年3月期',prevfy:'2024年3月期',dir:'up',pct:'+7.89%',tier:'easy'},
 {ticker:'3659',name:'ネクソン',announce:'2026-02-12',fy:'2025年12月期',prevfy:'2024年12月期',dir:'down',pct:'-11.58%',tier:'hard'},
 {ticker:'3994',name:'マネーフォワード',announce:'2026-01-14',fy:'2025年11月期',prevfy:'2024年11月期',dir:'down',pct:'-9.51%',tier:'hard'},
 {ticker:'4689',name:'LYコーポレーション',announce:'2025-05-07',fy:'2025年3月期',prevfy:'2024年3月期',dir:'down',pct:'-5.81%',tier:'hard'},
 {ticker:'9602',name:'東宝',announce:'2025-04-14',fy:'2025年2月期',prevfy:'2024年2月期',dir:'flat',pct:'-0.94%',tier:'hard'},
 {ticker:'4676',name:'フジ・メディアHD',announce:'2025-05-16',fy:'2025年3月期',prevfy:'2024年3月期',dir:'down',pct:'-2.63%',tier:'hard'},
 {ticker:'9468',name:'KADOKAWA',announce:'2025-05-08',fy:'2025年3月期',prevfy:'2024年3月期',dir:'up',pct:'+3.80%',tier:'hard'},
 {ticker:'4385',name:'メルカリ',announce:'2025-08-05',fy:'2025年6月期',prevfy:'2024年6月期',dir:'down',pct:'-3.80%',tier:'hard'},
 {ticker:'9984',name:'ソフトバンクグループ',announce:'2025-05-13',fy:'2025年3月期',prevfy:'2024年3月期',dir:'up',pct:'+2.64%',tier:'hard'},
]
const suffix2 = '_guardcheck'
log(`Hybrid pipeline: ${COMPANIES.length} companies`)

phase('Why')
const out = await pipeline(COMPANIES, c => agent(prompt(c), {label:c.ticker, phase:'Why', schema:SCHEMA, model:'sonnet'}))
const valid = out.filter(Boolean)
const companies = {}; for (const r of valid) companies[r.ticker] = r
await agent(
  `Write this JSON to exactly c:/Users/Sahal Saeed/Documents/tempest_ai/quick/New_quick/new_quick/quite_change/data/quarterly/it_hybrid${suffix2}.json using Write (overwrite). Confirm path + count.\n\n${JSON.stringify({companies}, null, 2)}`,
  {label:'write', phase:'Why', model:'haiku'})
return {count: valid.length, tickers: valid.map(r=>r.ticker)}
