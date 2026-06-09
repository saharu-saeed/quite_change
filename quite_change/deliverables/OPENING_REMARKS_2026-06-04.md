# 5-line opener — Sahal to read aloud at the start of the Nakamachi-san meeting (2026-06-04)

---

**1. What this is:** The 2025 single-year output of the first-stage Classification agent — companies sorted into **R+×S-** (revenue up, stock down — *the 本命*, default tab) and **R+×S+** (revenue up, stock up — secondary tab). R- (revenue down) companies are filtered out of the view per the brief.

**2. Coverage:** 98 of the 122-name IT census have 2025 data classified — 82 of those are R+ (41 in R+×S-, 41 in R+×S+). 14 are R- and excluded. The view is a partial census, not all 4000 listed companies — but the methodology is the deliverable, the names are illustrative.

**3. How the view works:** Two tabs at top — **R+×S- is default-selected and the focus** (green underline + "本命" chip). Inside each tab, **reason buckets are click-to-expand toggles** (▸ closed; ▾ open). Each company card now has **three layers**: (i) the **Genuine research** green block (primary content — source-verified per-company JP web-search summary), (ii) a small collapsed **Pattern** line (bucket-templated label), and (iii) the **Source prose** toggle that expands to show the older fixture rawExplanation.

**4. On the reasoning — UPGRADED with Round 2 verification (now BOTH tabs):** All **82 R+ companies (41 R+×S- + 41 R+×S+)** have now been verified through TWO rounds of JP web searches per company: Round 1 used Sahal's original prompt to gather earnings + stock-impact facts; **Round 2 used a combined prompt that ADDED a structural question** — for R+×S-: *「業績が良いのに株価が長期で評価されない場合の構造的な理由（競合状況、セクターのデレーティング、機関投資家のカバレッジなど）も教えて」*; for R+×S+ the variant is *「株価が業績と共に上昇している場合の構造的な理由(成長ドライバー、市場評価、機関投資家の動向など)も教えて」* (asks WHY the stock is rising along with earnings, not why it's lagging). The summaries you see in both tabs now integrate sourced broker actions, valuation metrics (PER, PBR, PSR, ROE), explicit competitor names, sector themes, dividend-hike commitments, and message-board/analyst views captured in the searches. Where I had earlier added inference layers from general market knowledge, those have now been replaced with sourced content. Full R+×S- audit trail is in [verification_findings_round2.md](verification_findings_round2.md).

**5. Language toggle:** Top-right corner has EN / 日本語 buttons. Switches the page UI, bucket titles, per-card Pattern text, and the Genuine-research body to Japanese — both EN and JP summaries were generated per company. The Source prose stays in its original language (mostly English with embedded JP).

---

## Most impactful verified facts you should be ready to cite

Several high-impact items came out of Round 2 verification that weren't in my earlier inference layer:

- **PLAID's actual competitors are Repro and b→dash** (Japan CX-platform peers), plus Salesforce, Adobe, Braze (foreign). PLAID is **#2 in Japan CX-platform market after Salesforce**. (I had earlier inferred the HR-SaaS competitor list — wrong.)
- **Money Forward**: Tokai Tokyo Intelligence Lab downgraded "Outperform → Neutral", **target price ¥6,900 → ¥4,200** — a significant institutional derating event. PER 137x.
- **TerraSky** recent +24% surge driven by **quantum-computing JV with Nissan + Mitsui Kinzoku** — a fresh catalyst, not just the Salesforce thesis.
- **VisasQ structural overhang is the 2021 Coleman Research Group acquisition disaster**: ¥14.4bn impairment + ¥14.5bn special loss damaged equity nearly to insolvency. (Bigger story than the AI-disruption thesis I had earlier.)
- **Cybozu** — the "why no re-rating" story is uniquely about corporate philosophy: **CEO Aono is openly market-averse, quoted as calling profit "絞りカス" (squeezed dregs)**, IR is intentionally limited (no quarterly materials, no 1-on-1 institutional meetings, no SaaS KPI disclosure). PSR consistently below MoneyForward/freee/SaaS average — institutions face "unable to value" rather than "choosing not to value."
- **SHIFT**: PER 41.36x vs historical 1.97-15.4x — that **extreme overvaluation** is the structural derating driver, not just the AI investment.
- **NSD**: NOT a SaaS company — investor view explicitly: *"NSDはSaas企業でない。準委任/派遣の保守運用事業でAIでのコスト圧縮されやすく戻り弱い"* — AI is a THREAT, not a tailwind. Investors compare unfavorably to NRI and TIS (peers leading AI monetization).
- **HENNGE**: 5-year IDaaS market-share #1, 3M+ users, ~20% of TSE-listed companies use HENNGE One. PER 43x and analyst-coverage-none is what caps the multiple.
- **NTT**: 25:1 stock split widened retail but government-holding sale-pressure remains the ceiling. Interest expense rose ¥149bn → ¥226.6bn on US/EU rates.
- **Toshin Holdings (9444)**: NOT a "business recovering" pattern — it has **going-concern doubts from accounting irregularities** + TSE Special Attention Issue designation + corporate-reorganization filing. Special case in the deck.
- **jig.jp (5244)**: main business is FUWATCH live-streaming app — not a regional small-cap as I'd earlier framed. Live-streaming sector competition intensifying with deep-pocket competitors.
- **70.5% of Japanese listed companies have NO analyst coverage** (industry stat) — confirmed as the dominant structural reason for the small/mid cap orphan pattern across many names here.

## Quick navigation talking points

- **Tab 1 (default):** R+×S- — *Revenue up, stock down* — green-themed, 本命 / Focus.
- **Tab 2:** R+×S+ — secondary, gray-themed.
- **Inside each tab:** reason bucket headers are collapsed by default. Click ▸ to expand.
- **Inside each company card:** the green "Genuine research" block is now Round 2 verified — concrete numbers, sourced broker actions, named competitors, explicit message-board/analyst views. The small gray "Pattern" toggle below it shows the bucket-templated framing for context. The "Source prose" toggle shows the older fixture-time rawExplanation.
- **Language toggle:** EN / 日本語 in the top-right.

## On R+×S- buckets (4 reason groups, 41 companies, ALL now Round 2 verified)

1. **Durably overlooked — multi-year mismatches** (3 names: SHIFT, Plus Alpha Consulting, PLAID). The strongest signal — 3+ consecutive Q2 years. Round 2 verified the key structural drivers per name.
2. **All financials up, stock still fell — clean mismatch or profit-taking sell-off** (2 names: jig.jp, SAKURA internet — placed last with the AI-bubble framing).
3. **Revenue up, profit compressed** (17 names). The margin-compression cohort Nakamachi explicitly said to keep. Each card now has source-verified sub-stories — Money Forward's Tokai Tokyo target cut, SHIFT's broker downgrade, COLOPL's structural mobile-game challenges, etc.
4. **Other under-recognized** (19 names). Each has its own specific verified story now — VisasQ's Coleman disaster, freee's "SaaSの死" theme, Cybozu's CEO philosophy, HENNGE's IDaaS dominance under coverage gap, Trend Micro's modest react despite beat.

## On the R+ definition (default is revenue-up only)

Includes both 業績◎ (all-three-up) AND 業績=mixed (rev up + profit down — margin compression). To confirm with Nakamachi later whether to gate on revenue-only or rev+OP+NP.

## Honest meta-note for Sahal

If Nakamachi-san presses on "how was this reasoning generated":
> "For ALL 82 R+ companies (both tabs), we did TWO rounds of per-company JP web searches. Round 1 used your earnings-and-stock-impact prompt. Round 2 used a structural prompt tuned to each tab: for R+×S- it asked WHY the stock is NOT re-rating despite good earnings (competitive position, sector de-rating, analyst-coverage gaps); for R+×S+ it asked WHY the stock IS rising along with earnings (growth drivers, market evaluation, institutional flow). The combined results gave us sourced broker actions, valuation metrics, named competitors, dividend-hike commitments, sector themes, and explicit message-board / analyst views. Every concrete fact in the green block is traceable to a source named in the source_hint field per card."

If he asks "what's the AUDIT TRAIL":
> "Two audit-trail files exist. For R+×S-: [verification_findings_round2.md](verification_findings_round2.md). For R+×S+: [verification_findings_round2_RplusSplus.md](verification_findings_round2_RplusSplus.md). Both list every company with: ✅ what the Round 2 search confirmed, ➕ NEW facts discovered, ⚠️ where my earlier inferences were wrong or unsupported. R+×S- key corrections: PLAID's actual competitors (Repro/b→dash); Money Forward's broker downgrade; TerraSky's quantum-computing catalyst; VisasQ's Coleman disaster as primary overhang; Cybozu's CEO market-aversion; NSD's AI-as-threat framing. R+×S+ key corrections were applied as addenda to 13 specific entries — the highest-impact ones being: SoftBank Corp dividend is FLAT not growing (¥8.60 × 5 years); ARGO Graphics net profit was actually +157.7% via extraordinary gain; Asteria's true catalyst was the JPYC stablecoin connection (18-year #1 share, 56.9%); Fuji Media's named activist is Dalton Investments (7.51%); Square Enix has 3D Investment Partners at 18.53%; TBS's hidden assets are ¥7,500 hundred million; Base (4481)'s dividend is actually ¥186 with 6.30% yield; Image Information's September limit-up was driven by the Miyama 5.1% large-shareholder report; SKY Perfect JSAT signed SpaceX launch contracts doubling satellite capacity; NRI booked goodwill impairment in Australia/NA; Collabos is in TSE listing-maintenance improvement period; CEC has a VISION 2030 plan targeting ROE 14% → 20%; BIPROGY is a DNP affiliate with an AI-productivity-doubling plan by 2030."

## R+×S+ key verified facts worth citing

Several high-impact items from R+×S+ verification:

- **SoftBank Group**: stock +91.6% — pure OpenAI-proxy story; PSG investment value re-rating drives the move, not standalone earnings.
- **Studio Ghibli effect on NTV**: the September 2023 acquisition (42.3%) was the trigger for NTV's re-rating from broadcaster to content company.
- **TV Tokyo (9413)**: anime IP (Naruto, Pokémon, Demon Slayer co-pro, Spy×Family) drives high overseas distribution-fee growth from Crunchyroll / Netflix / Prime Video — TV Tokyo is in a sellers' market.
- **SKY Perfect JSAT (9412)**: stock +119.4% — Defense Ministry satellite-constellation contract drives the re-rating, NOT pay-TV.
- **Fuji Media (4676)**: stock +113.3% — pure activist-investor pressure on hidden real estate value (Odaiba HQ + Sankei + Granvista), not earnings (which collapsed to operating loss).
- **TBS (9401)**: stock +42.7% — Akasaka Entertainment City redevelopment + payout-ratio target of 40% are bigger drivers than the +27% OP growth.
- **JUSTSYSTEMS (4686)**: operating margin **43.7%** — among the highest of any Japanese listed software company, rivaling top US SaaS — Smile Zemi auto-renewal is the engine.
- **OBIC Business (4733)**: operating margin **45.9%** — even higher; equity ratio 76.7%, ARR +13.5%, cloud-shift accelerating.
- **Visional (4194)**: BizReach OP margin **42.7%** + HRMOS ARR **+181%** with quarterly break-even — the rarest combination of profitable SaaS × hyper-growth.
- **m-up (3661)**: **8 consecutive years of revenue+profit growth, 7 consecutive years of record earnings** — extremely rare quality streak, fan-club platform with Johnny's-successor (STARTO) involvement.
- **Vision Inc (9416)**: dividend +85% (¥27 → ¥50) — most aggressive dividend hike in the cohort; payout ratio 55.5%.
- **TKC (9746)**: **12 consecutive years of record-high earnings** — also extremely rare; municipal-system standardization (Digital Agency mandate) is the tailwind.
- **Asteria (3853)**: operating margin **30.2%** under IFRS — Warp cloud-migration + generative-AI data-integration demand drove +31.2% OP growth and stock +80%+.
- **BIPROGY (8056)**: 4 years record-streak, next-year guide projects 5th — dividend ¥110 → ¥130 → ¥140 path. Renamed from Nihon Unisys in April 2022.
- **DTS (9682)**: Focus Business mix hit 60.7% at Q1 — beating the FY3/2028 target (57%) **by 3+ years**. Structural-transformation early achievement.
- **Image Information Inc (3803)**: a CAUTION case — revenue +13.2% but **operating loss expanded**. Stock +50%+ driven by **Cybridge LLC capital alliance + M&A speculation**, not fundamentals. Treat as event-driven.
- **Collabos (3908)**: another CAUTION — absolute profit at ¥17-40 million scale (tiny); stock surge is AI-call-center theme + small-cap liquidity, not earnings substance.

This is the honest framing.
