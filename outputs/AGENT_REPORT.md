# Quiet-Change Agent — Detailed Technical Report

**Model:** Anthropic Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`) via AWS Bedrock

**Document version:** Updated 2026-05-18 after a comprehensive methodology
audit triggered by client critique of the original ground-truth metric.

**Important — methodology audit + expansion summary (read first):** The
original "85.7% growth_unlikely precision" headline did NOT survive
rigorous re-measurement and sample expansion. It came from a noisy 2D
ground truth on a small sample (n=6 bear calls) that was somewhat lucky.

After three independent validation samples (original 20 + OOS 15 +
JGAAP extension 30 = 45 JGAAP info/comm tickers total) under the
aligned Recipe A v2 methodology (op profit + adverse event check):

- `growth_unlikely` precision: **73.3% [48-89 95% CI]** from n=15
  confident bear calls
- `growth_likely` precision: 53.7% [39-68 95% CI] from n=41 confident
  bull calls
- Abstain rate: ~50% (honest)

**The narrower CI [48-89] on n=15 is much more credible than the
flashier [44-97] on n=6.** Total validation spend across all 3 runs:
~$10 in Bedrock LLM calls.

**Recommended framing after audit:** the agent's value is in the
**evidence it surfaces**, not in its verdicts as decision-makers.
Independent qualitative review of 7 demo cases found 5 of 7 with
sound, useful reasoning. Treat verdicts as triage signals; treat
the underlying numbers (concentration ratios, CFO/NI flags, peer
gaps, goodwill levels) as the actually valuable output.

---

## 1. Executive summary

The Quiet-Change Agent is a **filter signal generator for Japanese listed
equities**. For each company, it reads the latest annual securities report
(有価証券報告書, ASR) and produces one of three verdicts:
`growth_likely` / `growth_unlikely` / `uncertain`.

Its purpose is to triage a large universe into a smaller "needs human
attention" set — not to predict stock returns or recommend trades.

After ~3 weeks of engineering across 6 experimental phases (4 shipped,
1 rolled back, 1 skipped) and 3 independent validation samples (65
tickers total, 45 in JGAAP cohort), the agent's precision under aligned
Recipe A v2 methodology:

| Cohort / sample | growth_likely | growth_unlikely | Overall |
|---|---|---|---|
| Original 20 (JGAAP n=11) | 66.7% (8/12) | 83.3% (5/6) | 72.2% [49-88] |
| Out-of-sample 15 (JGAAP n=4) | n/a | 100% (1/1) | 100% [21-100] |
| JGAAP extension 30 | 48.3% (14/29) | 62.5% (5/8) | 51.4% [36-67] |
| **GRAND TOTAL (JGAAP n=45)** | **53.7% [39-68]** (22/41) | **73.3% [48-89]** (11/15) | **58.9% [46-71]** |

`uncertain` abstain rate: ~50% of all predictions (consistent across
all 3 samples — honest behavior).

**The headline `growth_unlikely` precision (73.3% with CI [48-89])
is the most credible number we have:** based on the largest sample
(n=15 bear calls vs n=6 originally), narrowest CI we've achieved.



---

## 2. The problem the agent is trying to solve

A human equity analyst cannot read every Japanese annual report (~3,700
listed companies, each 100-200 pages). They need a **first-pass filter**:

> *"Out of these 100 companies, which 20 should I actually spend time on?"*

The agent reads each company's report and answers that question by
flagging companies likely to disappoint vs companies that look stable
enough to keep on the candidate list. It is a **negative filter** in
the workflow sense: the operator uses it to *drop* the obviously-
concerning names from a candidate universe so analysts can spend their
limited time on what's left. It is NOT a stock picker, NOT a return
forecaster, and NOT a confirmation that the "kept" companies are
healthy — the kept watchlist still needs human review (the
`growth_likely` precision is only ~52%, see Section 11).

### Verdict → workflow action mapping (revised after audit)

| Verdict | Operational action | Reliability |
|---------|---------------------|-------------|
| `growth_unlikely` | **Triage flag — needs human review for downside risk** | 43-83% precision depending on methodology (Recipe A v1 ↔ v2); use as triage signal, not determination |
| `growth_likely` | **Triage flag — no immediate red flag in agent's evidence** | 33-83% precision depending on methodology; do NOT treat as "this company is fine" |
| `uncertain` | **Hold** (evidence is genuinely mixed) | ~49% of cases; abstain is honest behavior |

**Important:** treat ALL verdicts as triage signals, not as decisions.
The agent's actual value, per independent qualitative review, is in
the structured evidence it surfaces (concentration ratios, CFO/NI
flags, peer gaps, goodwill levels), not in its verdict-making.

### The 4-quadrant framework

The intuition the agent operationalises: revenue and stock reaction
form a 2x2 matrix:

|                | Stock ↑ | Stock ↓ |
|----------------|---------|---------|
| **Revenue ↑** | Aligned positive — usually growth_likely | **DIVERGENCE** — investigate (the "quiet change" case) |
| **Revenue ↓** | DIVERGENCE — investigate | Aligned negative — usually growth_unlikely |

The interesting cells are the **divergences**: when revenue and stock
disagree, something nuanced is happening that needs analysis. The agent
also explicitly handles **weak-response** cases (profit moved ≥5% but
stock barely moved) as a separate anomaly.

---

## 3. End-to-end pipeline (what happens when you run the agent on one company)

`analyze_company_multi_year(code, min_year=2020, decision_cutoff_fy=2023)` in
[app/subagents/quiet_change.py](../app/subagents/quiet_change.py):

```
1. Load ASR series from Tempest cache (typically 4-5 annual reports per ticker)
2. Extract restated revenue history from the latest ASR's 5-year-summary table
3. Per-year preprocessing (no LLM):
   - For each year, extract P/L items + derive margins (op margin, net margin)
   - For each year, extract cash flow items (CFO, CFI, CFF, capex) and derive
     FCF + CFO/NI ratio
   - For each year, extract BS items (goodwill, equity, inventory, receivables)
     + segment shares
4. Build per-ticker context (used by every pair):
   - margin_trajectory: list of {fiscal_year, revenue, op_margin_pct, net_margin_pct}
   - cashflow_history: list of {fiscal_year, cfo_to_ni_ratio}
   - bs_quality_history: list of {fiscal_year, top_seg_share, herfindahl, goodwill/eq, dso, inv_days}
   - industry_context: JPX 33業種 sector code → cyclicality hint (mostly disabled)
5. Per-pair loop (curr = each consecutive pair of ASRs):
   a. Compute segment YoY (delta per segment, sorted by |delta|)
   b. Compute BS YoY (item-by-item, with mover flags)
   c. Compute P/L YoY (item-by-item + margin pp deltas, with mover flags)
   d. Compute cash flow YoY (CFO/capex/FCF/CFO-NI prev→curr)
   e. Detect CFO/NI < 0.8 for 2+ consecutive years quality flag
   f. Compute peer comparison vs JPX 33業種 sector medians (≥5 peers required)
   g. Trim trajectory + history to years ≤ curr_fy (no future leakage)
   h. Get 5-day post-filing stock reaction (close-to-close return)
   i. Decide stock_response_class: divergence / weak_response / aligned / n/a
   j. If decision_cutoff_fy is set AND curr_fy > cutoff → skip LLM (outcome pair)
      Otherwise: build prompt → call LLM → parse JSON output
   k. Run coverage-rule post-checks against the explanation
6. Synthesize "history-only" pairs for years where 5y-summary has revenue but
   no full ASR is cached (e.g. FY2019 → FY2020 if only FY2020+ ZIPs exist)
7. Optionally write all-tests sanity-check log (default off)
8. Cache the full result to outputs/agent_cache/<key>.json
9. Return structured dict: {code, name, years, pairs[...], history_only_years}
```

**Per-pair LLM call** is the expensive step (~$0.04-0.05, ~60 sec wall time
with the per-pair 1-sec sleep). Everything else is cache reads.

---

## 4. The four evidence categories the agent reasons over

This is the core of "what is the agent looking at."

### 4.1 Multi-year trajectory (Phase 1)

**What it shows the LLM:** A 5-year table of revenue + operating margin %
+ net margin %, with a "Bounce vs Trend" classification appended.

```
Multi-year trajectory (revenue YoY, operating margin, net margin — 5-year context):
  FY      Revenue (bn)      YoY  Op margin  Net margin
  FY2020      10,200.0        —     12.50%       8.10%
  FY2021      10,500.0    +2.9%     13.20%       8.40%
  FY2022      11,200.0    +6.7%     13.80%       9.10%
  FY2023      11,900.0    +6.3%     14.10%       9.40%
  FY2024      12,100.0    +1.7%     12.90%       8.20% ← curr

Trajectory classification: BOUNCY trajectory — margin has oscillated...
```

**Why this matters:** A single year's margin compression could be cyclical
noise or the start of structural decline. Without history, the agent
can't distinguish them. The classifier (`SUSTAINED EXPANSION`, `SUSTAINED
DECLINE`, `BOUNCE in DOWN-trend`, `DIP in UP-trend`, `NEW HIGH after BOUNCY`,
`BOUNCY trajectory`, `FLAT trajectory`) gives the LLM an explicit anchor.

**Source code:** [`_build_margin_trajectory_block`](../app/subagents/quiet_change_prompt.py)

**Data source:** Tempest `financials_line_items.json`, extracted per
fiscal year via `extract_pl_from_zip_path`.

---

### 4.2 Cash-flow quality (Phase 1)

**What it shows the LLM:** Operating cash flow (CFO), capex, free cash flow (FCF),
and the CFO / Net Income ratio for both prev and curr year, plus a flag.

```
Cash-flow movements (prev → curr; * = CFO/NI < 0.8 = earnings-quality concern):
  Operating cash flow       :    2,261.0bn →    2,374.2bn  (+5.0%)
  Capital expenditure       :    1,862.4bn →    2,063.1bn  (+10.8%)
  Free cash flow            :      398.6bn →      311.0bn  (-22.0%)
  CFO / Net income ratio    :    1.86x →    1.86x

  EARNINGS-QUALITY FLAG: CFO/NI has been below 0.8 for 2 consecutive year(s)...
```

**The CFO/NI < 0.8 flag** is computed across the full multi-year history.
Threshold = 0.8; required streak = 2 consecutive years. When triggered,
the prompt explicitly tells the LLM: *"Treat this as a STRUCTURAL
earnings-quality concern, not a one-off."*

**Why this matters:** Reported profit can be inflated by accounting
non-cash items (writedowns reversed, deferred revenue tricks). Real
operating cash flow doesn't lie. A persistent gap between accounting
profit and cash generation is one of the strongest forward-warning
signals in fundamental analysis.

**Threshold rationale:** 0.8 is a standard threshold in academic earnings-
quality literature. Single year below = noise; 2+ consecutive years = signal.

**Source code:** [`_build_cashflow_block`](../app/subagents/quiet_change_prompt.py),
[`_detect_cfo_ni_low_quality`](../app/subagents/quiet_change.py)

**Data source:** Tempest `financials_line_items.json` with `statement_type='CF'`,
extracted via `extract_cashflow_from_zip_path`. FCF formula: `cfo - capex`
(Tempest reports both as positive magnitudes).

**Fixed 2026-05-16 (post-project audit):** The extractor originally skipped
the ratio entirely when net income was negative. That silently dropped a
real signal — a company reporting paper losses while generating positive
operating cash flow is a *positive* earnings-quality indicator (the loss
is likely non-cash: writedowns, impairments, fair-value markdowns). The
fix surfaces this case as a structured `cfo_positive_despite_loss` boolean
flag, which the prompt block renders to the LLM as an explicit
`POSITIVE EARNINGS-QUALITY SIGNAL` with a reasoning rule:
*"Do NOT use a reported net loss as standalone evidence for `growth_unlikely`
when CFO is positive — investigate the narrative for the non-cash cause."*
The fix is non-breaking (the existing `<0.8 for 2 years` detector still
operates on positive-NI ratios only). Backtest was NOT re-run after the fix
because the 20 test tickers are predominantly profitable; effect on those
specific results is essentially zero.

---

### 4.3 Sector peer comparison (Phase 2)

**What it shows the LLM:** This company's revenue YoY %, operating margin %,
op margin Δpp YoY, and net margin % — compared against the **median** of
all other companies in the same JPX 33業種 (33-sector industry classification)
that have data for the same fiscal year.

```
Sector peer comparison (FY2023, JPX 33業種 5250 情報・通信業, N=18 peers — *= material gap vs median):
  metric                        this     median  position
  Revenue YoY %                8.10%     13.34%  BELOW peers by 5.24pp *
  Operating margin %          13.92%     14.10%  IN-LINE (-0.18pp vs median)  
  Op margin Δpp YoY          -0.63pp    +0.99pp  BELOW peers by 1.62pp *
  Net margin %                 9.23%     10.29%  BELOW peers by 1.06pp  

  PEER-READING RULES: Below-median revenue YoY or a more-negative op-margin
  Δpp than the sector is a COMPANY-SPECIFIC concern (not cyclicality)...
```

**Key design decisions:**

- **Sector taxonomy:** JPX 33業種 (Japan's standard 33-industry classification).
  Each ticker is looked up via `app.tools.jpx_industries.lookup()`.
- **Minimum peer count:** ≥5 peers (excluding self) required to render the
  block. Below that, the block is skipped entirely — a 2-name median is
  noise, not signal. Better to give the agent nothing than garbage.
- **Self-exclusion:** The target ticker is excluded from the median
  computation so it's not compared to itself.
- **Positional tags** with thresholds (the "IN-LINE band"):
  - Margin metrics: ±0.5pp band → IN-LINE; outside → ABOVE / BELOW
  - Revenue YoY: ±1.0pp band → IN-LINE; outside → ABOVE / BELOW
  - "Material gap" asterisk if |diff| ≥ 2 × band
- **Reading rules** embedded in the block tell the LLM how to use the data:
  - BELOW peers = company-specific concern, NOT cyclical
  - ABOVE peers = structural moat candidate
  - IN-LINE = sector-driven, do NOT cite

**Why this matters:** A -2pp margin drop sounds bad — unless every peer
also dropped 2pp (cycle, not company-specific). Peer context distinguishes.

**Coverage gaps:**
- Sector code unmapped: 2 of 44 Tempest tickers (1306, 9719) — block skips
- Sector with <5 peers: 14 of 44 tickers in 9 small sectors — block skips
- Telcos (NTT, KDDI) DO get the block — they're in sector 5250 with 18 peers

**Source code:** [`_compute_sector_peer_medians`](../app/subagents/quiet_change.py),
[`_build_peer_block`](../app/subagents/quiet_change_prompt.py)

**Known issue:** The IN-LINE band thresholds (0.5pp, 1.0pp) were guessed,
not calibrated from actual cross-sector standard deviations.

---

### 4.4 Balance-sheet quality + concentration (Phase 6)

**What it shows the LLM:** A 3-5 year trajectory of four structured signals
+ embedded reading rules with explicit thresholds.

```
Balance-sheet quality & concentration trajectory (3-5y, structured):
  FY       top seg     Herf.     goodwill/eq      DSO  inv days
  FY2021     79.0%      6405             —        —         —  
  FY2022     79.5%      6481             —        —         —  
  FY2023     77.9%      6268             —        —         —   ← curr

  Multi-year trends worth citing in outlook_reason:
    Top segment share: -1.1 over 3 years  (rising = increasing concentration)
    Herfindahl: -137.0 over 3 years  (rising = increasing concentration)

  READING RULES:
    - Herfindahl > 5000 OR top segment > 70% → bet-the-company concentration
    - Rising Herfindahl/top-share over 3+ years → structural concentration risk
    - Goodwill/equity > 30% AND rising → acquisition-heavy growth model, impairment risk
    - DSO rising 20%+ over 3 years → receivables-quality concern
    - Inventory days rising 20%+ over 3 years on flat/declining revenue → demand softening
    - At sector-normal / flat → treat as neutral, do NOT cite
```

**The four metrics:**

| Metric | Formula | What it signals |
|--------|---------|----------------|
| **Top segment share %** | max(segment_share) × 100 | "Bet-the-company" risk if >70% |
| **Herfindahl index** | Σ(segment_share²) × 10000 | Concentration on 1-10000 scale; >5000 = highly concentrated |
| **Goodwill / Equity %** | (goodwill / equity) × 100 | Acquisition risk; >30% = impairment-prone |
| **DSO (days)** | (trade_receivables / revenue) × 365 | Collection quality / aggressive revenue recognition |
| **Inventory days** | (inventory / revenue) × 365 | Demand softening / overstocking |

**Min-data requirement:** ≥3 years with at least one populated metric.
Below that, block is skipped (3-5 year trend can't be established).

**Why this matters:** A company that's 80% dependent on one segment is
fragile. A company with goodwill = 50% of equity has a writedown risk
hidden in its balance sheet. Neither shows up in revenue or margin numbers.

**Known issues:**
1. **DSO and inventory days are dead code today.** Tempest's BS extractor
   doesn't expose `trade_receivables` or `inventory` for our test universe.
   The code is correct; the data just isn't there yet.
2. **Phase 6 block doesn't render for telcos** — NTT and KDDI lack the
   segment / goodwill detail. ~30% of the test universe affected.
3. **Trend label direction is confusing for declining values** — "Top
   segment share: -1.1 over 3 years (rising = increasing concentration)"
   forces the reader to mentally invert when the value is falling.

**Source code:** [`_compute_bs_quality_history`](../app/subagents/quiet_change.py),
[`_build_bs_quality_block`](../app/subagents/quiet_change_prompt.py)

---

## 5. Other context the agent receives (in addition to the four categories above)

| Block | What it contains | Source |
|-------|------------------|--------|
| `divergence_block` | "DIVERGENCE: profit and stock disagree" or "WEAK-RESPONSE: stock under-reacted" | computed from op_delta_pct + stock_5d |
| `bs_change_block` | All 11 BS items prev→curr with mover flags (≥15% YoY or >2% of assets + ≥10% YoY) | `_bs_yoy` → `extract_balance_sheet_from_zip_path` |
| `pl_change_block` | All P/L items + margin pp deltas with mover flags (≥25% YoY or ≥1.5pp margin) | `_pl_yoy` → `extract_pl_from_zip_path` |
| `segment_table` | Per-segment prev→curr revenue + YoY % + share % | `extract_segments` |
| `narrative` | 3,000-char excerpt from MD&A section | Tempest `asr_texts/<doc_id>.json` → `md_and_a` field |
| `key_clauses_block` | Extracted "offset/despite/acquisition/divestiture/volume_decline" clauses from full narrative | regex-based, lives in `quiet_change_prompt.py` |
| `scope_note_block` | Revenue-scope ambiguity warning (if the same filing exposes multiple plausible revenue numbers) | `_build_revenue_scope_note` |
| `op_profit_block` | Operating profit prev→curr with YoY % | `_op_profit_yoy` |
| `macro_context_block` | Generic "apply your knowledge of FY{year} macro environment" — does NOT inject specific facts (to avoid stale data) | `_build_macro_context_block` |
| `stock_reaction` | 5-day close-to-close return after filing date | `_stock_5d_move` → Tempest `prices.json` |

The prompt assembles these in a fixed order. Total assembled length:
~25,000-28,000 characters (~6,500-7,000 tokens).

---

## 6. The LLM call

### Model and parameters

| Setting | Value |
|---------|-------|
| Provider | AWS Bedrock |
| Model | Claude Sonnet 4.6 |
| Inference profile | `us.anthropic.claude-sonnet-4-6` |
| Temperature | 0 (deterministic) |
| Max output tokens | 4,500 (advanced) / 1,500 (simplify, optional, skipped by default in backtests) |
| Routing fallback | Anthropic Direct if `ANTHROPIC_API_KEY` set, else Bedrock |

**Currently:** runs through Bedrock with old AWS creds. Anthropic Direct key
paused per user instruction.

### Two LLM calls per pair (or one, with `skip_simplify=True`)

1. **Advanced call** (always runs): produces the structured JSON with 7 fields
   - `outlook_judgment` (enum: growth_likely/growth_unlikely/uncertain)
   - `outlook_reason_en`, `outlook_reason_ja`
   - `explanation_advanced_en`, `explanation_advanced_ja`
   - `stock_reaction_en`, `stock_reaction_ja`

2. **Simplify call** (skipped by default in backtests via `skip_simplify=True`):
   produces a layman-friendly version of the advanced explanation.

### Cost per call (Sonnet 4.6 pricing, $3/M input + $15/M output)

| Block | Avg input tokens | Avg output tokens | Avg cost |
|-------|------------------|-------------------|----------|
| Advanced call | ~6,500 | ~1,200 | ~$0.038 |
| Simplify call (when included) | ~2,500 | ~700 | ~$0.018 |
| **Per pair (advanced only)** | | | **~$0.04** |

### Per-company cost

- Typical company: 4-5 ASRs → 3-4 YoY pairs → 3-4 advanced LLM calls
- Default backtest mode skips outcome pairs (curr_fy > 2023) → 2 calls
- Per company per fresh run: **~$0.08 (2 decision pairs) to ~$0.16 (4 pairs)**

### Prompt structure (V1)

`ADVANCED_PROMPT` in [quiet_change_prompt.py](../app/subagents/quiet_change_prompt.py):

```
Header: "You are evaluating Japanese company {ticker} based on its ASR..."
[Unit convention rules]
[STRICT RULES — segment direction discipline, no external expectations,
                 BS discipline, P/L discipline, etc.]
[Per-pair data]:
  - Headline numbers (revenue + op profit + stock reaction)
  - Segment table + composition table
  - {divergence_block}
  - {bs_change_block}
  - {pl_change_block}
  - {cashflow_block}              ← Phase 1
  - {margin_trajectory_block}     ← Phase 1
  - {peer_block}                  ← Phase 2
  - {bs_quality_block}            ← Phase 6
  - {macro_context_block}
  - Narrative excerpt (3000 chars)
  - {key_clauses_block}
[PRE-FLIGHT CHECKLIST — silent reasoning rules]
[DIVERGENCE-REASONING RULE]
[BS DISCIPLINE — only cite mover items]
[TEMPORARY-CAUSE softening rule — for outlook judgment]
[Output schema — strict JSON]
```

### V2 (prompt-caching variant) — disabled in production

A version splits the static rules (system prompt, ~24k chars) from the
dynamic per-pair data (user prompt, ~3k chars) so the system half can be
prompt-cached on the Anthropic API. A 5-ticker A/B test showed it flipped
4 of 10 judgments from `growth_likely` to `uncertain` — rolled back. The
code exists but is gated behind `use_prompt_caching=True` (default False).

---

## 7. Voting / aggregation strategies

The per-pair LLM call produces one judgment per pair. To roll multiple
pairs into a single per-company verdict, the agent has two strategies
(in [scripts/backtest_quiet_change.py](../scripts/backtest_quiet_change.py)):

### `vote_trend_aware` (production default)

Rules (latest pair drives, prior pairs modify):

- latest = `growth_likely` → return `growth_likely`
- latest = `growth_unlikely` → return `growth_unlikely`
- latest = `uncertain`:
  - any prior was `growth_likely` → return `growth_unlikely` (deteriorating)
  - any prior was `growth_unlikely` (none was likely) → return `growth_unlikely`
  - all priors were `uncertain` → return `uncertain`

This rule **forces a confident call from an uncertain latest judgment**
when the trajectory is deteriorating. The audit found that this is the
mechanism by which the bundled backtest inflated hit rate — the rule
manufactures confidence from raw uncertainty.

### `vote_recency_weighted`

Latest pair = 2x weight, others = 1x. Tally weighted votes for
growth_likely vs growth_unlikely; uncertain contributes 0. Higher tally
wins; ties → uncertain.

### Why these matter

The voting strategy ONLY applies in the **bundled backtest methodology**.
Under the corrected **rolling-window methodology** (see Section 10), each
per-pair judgment stands alone and is scored independently — no voting.

In production deployment, if you score per pair (which is more honest),
the voting rules are not needed. They were a development artifact for
producing a single "verdict per company" for an earlier framing.

---

## 8. Outcome scoring (the "actual" side of the backtest)

For backtesting, each year's actual outcome is classified as:

```
"growth" if (revenue_delta_pct > 0 AND stock_5d_return_pct > 0)
"no_growth" otherwise
"n/a" if either is missing
```

This is a **strict conjunction**: BOTH revenue up AND stock up to count
as growth. Either weak → no_growth.

### Per-prediction scoring

```
HIT: prediction is growth_likely AND actual is growth
HIT: prediction is growth_unlikely AND actual is no_growth
MISS: prediction is directionally wrong
ABSTAIN: prediction is uncertain (excluded from hit rate)
N/A: outcome data is missing
```

Hit rate = HIT / (HIT + MISS), excluding ABSTAIN and N/A.

### Known issue with the outcome rule

Strict `> 0` thresholds make the classifier fragile near zero. A company
with +0.01% revenue and +0.01% stock = growth; flipping either sign by a
sliver inverts the classification. A more robust definition might require
magnitude (e.g. `> 1%`) or use a band where edge cases are excluded.

Inherited from the earlier baseline code, not introduced by phase work.

---

## 9. Coverage rules (post-LLM output checks)

After the LLM produces its explanation, 17 rules are run to detect
omissions or unsupported claims. They produce warnings (the agent's
output still ships), not blockers.

In [`_COVERAGE_RULES`](../app/subagents/quiet_change.py):

### Regex rules (narrative trigger must produce output mention)

| Rule | Fires when |
|------|-----------|
| `explicit_offset` | Narrative says "相殺/部分相殺/partially offset" but explanation doesn't |
| `mixed_drivers_despite` | Narrative says "ものの/にもかかわらず/despite" not preserved in output |
| `acquisition_driver` | Narrative names "買収/取得/acquisition" but explanation doesn't surface M&A |
| `divestiture_driver` | Narrative names business disposal but explanation doesn't surface |
| `volume_decline` | Narrative says "販売台数減少/unit sales declined" but output doesn't mention "unit/volume/台数" |
| `streaming_music_driver` | Narrative mentions music + streaming but explanation cites only FX/acquisitions |
| `named_acquisition_omission` | Narrative names specific M&A targets (Crunchyroll, AWAL, etc.) not all surfaced |
| `no_expectations_invented` | Output mentions beat/miss/consensus but narrative doesn't contain such data (hallucination check) |

### Structured rules (richer than regex)

| Rule | Fires when |
|------|-----------|
| `composition_opener` | DEPRECATED (soft fallback) |
| `divergence_addressed` | Anomaly stock_response_class but no hedged tokens in explanation |
| `bs_citation_missing` | Divergence + BS movers exist but explanation cites no mover |
| `financial_attribution_mismatch` | Explanation attributes Financial-segment decline to consolidation but narrative cites separate-account losses (apples-to-oranges) |
| `unit_discipline_trillion` | Comma-formatted number paired with "trillion/兆" — almost certainly billion mislabeled |
| `outlook_reason_missing` | outlook_judgment set but outlook_reason_en/ja empty |
| `outlook_no_accounting_item` | outlook_reason doesn't cite ≥1 accounting item (営業利益率, のれん, etc.) |
| `stock_reaction_present` | Stock data given but explanation doesn't mention stock |
| `foreign_tangent_check` | Explanation cites foreign country/company not in segment table or narrative + no driver context |

### Production usage

Warnings appear in the response payload as
`narrative_coverage_warnings: [{"rule": ..., "message": ...}]`. The web
UI renders them as yellow badges. They are NOT acted on by the agent
itself — they are diagnostic for human review.

**Known issue:** Some rules fire noisily (`bs_citation_missing` triggers
on ~half of pairs). Either the rules are overzealous or the BS data is
genuinely sparse for many divergence cases. Worth investigating.

---

## 10. Backtesting methodology

### 10.1 Bundled methodology (original, now retired)

Used during Phase 1-2-6 development:

```
1. Decision pairs: pairs where curr_fiscal_year <= decision_cutoff_fy (=2023)
2. For each decision pair, agent produces a judgment
3. Aggregate per-pair judgments via voting (default: trend_aware)
   → ONE verdict per company
4. Outcome pairs: pairs where curr_fiscal_year > 2023
5. For each outcome pair, classify as growth / no_growth
6. Aggregate outcome via majority vote across outcome pairs
   → ONE actual outcome per company
7. Score: ONE verdict vs ONE outcome per company
```

**Problem:** The voting rule in step 3 manufactures confidence — it converts
`uncertain` judgments into `growth_unlikely` when the trajectory is
deteriorating. The bundled hit rate (70.6% on 20 tickers) was partly an
artifact of this manufactured confidence.

### 10.2 Rolling-window methodology (corrected, used for final numbers)

Industry-standard "walk-forward validation":

```
1. For each company, run LLM on ALL pairs (no decision_cutoff_fy)
   This gives one judgment per (prev_year, curr_year) pair
2. For each pair P[i], the "prediction" is its judgment
3. The "outcome" for P[i] is the NEXT pair P[i+1]'s revenue + stock signal
4. Score each pair INDEPENDENTLY (no voting)
```

This matches real-world use: when a new annual report drops, the agent
re-reads with the latest data and makes a fresh prediction for the next
year. Each prediction is tested against ONE specific subsequent year.

**Properties:**
- More predictions (55 instead of 17 on 20 tickers)
- No voting-rule confidence manufacturing
- Each prediction is short-horizon (1 year out, not 2)
- Closer to how the agent would be used in production

This is the methodology the final reported numbers (60.7% hit rate,
85.7% filter precision) are computed from.

---

## 11. Performance metrics (the honest numbers)

### Sample

- **20 tickers** from `outputs/backtest_20_it_5250.json` (a prior universe selection)
- **55 individual predictions** (rolling-window methodology)
- **28 confident calls** (predictions that weren't `uncertain`)
- Tickers: 4307, 4689, 9432, 9433, 9434, 9984, 9684, 9697, 4385, 3659, 9719, 4684, 4768, 3923, 3656, 4477, 4480, 4475, 3760, 4483

### Headline — apples-to-apples methodology comparison

**Scoring logic invariant across all methodologies:** `growth_likely`
HITs when company grew; `growth_unlikely` HITs when company didn't
grow. The workflow mapping (`growth_unlikely` → Filter OUT,
`growth_likely` → Keep on watchlist) is documentation, separate from
the HIT/MISS attribution math. Numbers below differ only because of
methodology (outcome definition) and sample (which tickers included),
NOT because of any scoring-logic flip.

#### Same JGAAP cohort (n=11 tickers, 18 confident calls)

Holding sample constant to isolate methodology effects:

| Methodology | growth_likely (Keep) | growth_unlikely (Filter OUT) | Overall |
|---|---|---|---|
| Original (rev + 5d-stock both pos) | 41.7% (5/12) | **83.3%** (5/6) | 55.6% |
| Recipe A v1 (sector-adj 2-of-2 strict ±5%) | 33.3% [17-55] | 42.9% [16-75] | 35.7% [21-54] |
| **Recipe A v2 (op profit + 2y event)** | **66.7%** (8/12) | **83.3%** (5/6) | **72.2% [49-88]** |
| Recipe C (event-based only) | 80.0% (8/10) | 60.0% (3/5) | 73.3% [48-89] |

**Observations on same-cohort comparison:**
- `growth_unlikely` precision is **identical (83.3%) under original
  and Recipe A v2** on this cohort — methodology change did NOT move
  it. Same 5 hits, same 1 miss.
- `growth_likely` rose 41.7% → 66.7% under Recipe A v2. Same calls,
  same scoring logic — change reflects better outcome alignment.
- Recipe A v1 (pre-registered 2-of-2 strict) was over-engineered.
  Kept here for transparency.

#### Out-of-sample addition (15 fresh tickers, +14 confident calls)

Recipe A v2 tested on 15 tickers not in original test set (Toyota,
Sony, Hitachi, Cyberagent, etc.). Combined sample numbers (original
JGAAP + new JGAAP, n=7 confident `growth_unlikely`):
- `growth_unlikely` (Filter OUT) precision: **85.7%** [49-97 CI from 6/7]
- One new JGAAP `growth_unlikely` call (Cyberagent FY21→22) correctly
  predicted 2 impairments + 2 extraordinary losses in FY2023-2024.

#### Confidence layer — Path C product feature (added 2026-05-18)

After Recipe A v2 validation, we explored whether the agent's growth_likely
precision (53.7% on n=41) could be improved. The structured-data diagnostic
(Idea 4 Phase 1) on 56 historical calls identified three factors with
large effect sizes for HIT-vs-MISS:

- Peer LEVEL gap (operating margin vs sector median): Δ +8.97pp
- Operating margin LEVEL (current FY): Δ +8.85pp
- Goodwill / equity ratio: Δ -5.43pp (inverse)

A prompt-tuning fix encoding these factors as hard gates was attempted
and held-out tested. **It failed** (abstain rate +25.7pp, precision
unchanged) — reverted per pre-registration discipline.

The failure taught us: hard prompt gates from small-sample averages
over-block, because individual cases have overlapping distributions even
when population means differ.

**Path C — confidence layer as downstream enrichment** was implemented
instead. Each confident verdict now carries a HIGH/MEDIUM/LOW confidence
label based on three binary factor checks (peer LEVEL gap > +10pp,
goodwill/equity < 30%, CFO/NI > 0.8). No prompt changes, no LLM calls,
applied as post-processing in [app/subagents/quiet_change.py](../app/subagents/quiet_change.py)
via `_compute_confidence_for_pair()` and `_enrich_pairs_with_confidence()`.

**Cross-tab on 73 confident JGAAP calls (full validation universe):**

| Class | HIGH | MEDIUM | LOW |
|---|---|---|---|
| growth_likely (n=57) | 66.7% (n=6) | 68.0% (n=25) | **46.2% (n=26)** |
| growth_unlikely (n=16) | n/a (n=0) | 60.0% (n=5) | **72.7% (n=11)** |

**Interpretation:**
- `growth_likely` with HIGH/MEDIUM confidence is significantly more reliable than LOW (68% vs 46%, ~22pp spread)
- `growth_unlikely` with LOW confidence (i.e., factors don't support a bull case) is MORE reliable as a bear call (72.7%) — symmetric and intuitive

**Output JSON enrichment:**
Each pair now contains:
- `confidence_label`: `"HIGH"` / `"MEDIUM"` / `"LOW"` / `null` (for uncertain verdicts)
- `confidence_factors`: dict with the 3 factor values + binary pass flags

Existing cached pair JSON files automatically get the label on next load
(idempotent enrichment). No cache version bump needed.

**Failed attempt artifacts** (kept for transparency):
- `outputs/idea4_factor_preregistration.md` — locked factor list
- `outputs/idea4_diagnostic_results.json` — effect sizes per factor
- `outputs/idea4_phase2_findings.md` — synthesis with qualitative review cross-check
- `outputs/idea4_phase4_holdout_selection.md` — held-out 15-ticker selection
- `outputs/idea4_phase4_ab_comparison.json` — paired A/B test result (failed)
- `outputs/idea4_phase5_outcome_report.md` — full outcome report with revert documentation

#### IFRS extension attempt — failed (full transparency)

We attempted to extend the event-based methodology to IFRS filers via
a PROXY event detector. Methodology pre-registered at
[outputs/ifrs_event_proxy_methodology.md](ifrs_event_proxy_methodology.md)
before scoring.

Proxy triggers (locked):
- Goodwill balance YoY decline ≥10% of prior balance OR ≥1% of prior equity
- Operating profit YoY drop ≥15%
- Operating margin contraction ≥3 percentage points YoY

Result on IFRS cohort (n=20 tickers):

| Class | Precision | Sample |
|---|---|---|
| Overall | 35.3% [17-59] | 6/17 |
| growth_likely | 38.5% [18-65] | 5/13 |
| growth_unlikely | 25.0% [5-70] | 1/4 |

**Why it failed:** the proxy cannot distinguish a real structural problem
(impairment, goodwill writedown) from a cyclical down year. Many IFRS
proxy events triggered on macro/sector cyclicality: KDDI normal telecom
capex cycle, Advantest semiconductor cycle, Recruit COVID effect.
Combining JGAAP direct + IFRS proxy gives a misleadingly diluted headline
(growth_unlikely drops from 85.7% to 63.6%).

**Conclusion: headline precision claim stays JGAAP-only.** IFRS large-cap
coverage is documented as future work requiring IFRS notes-level XBRL
tag extraction (Tempest pipeline upgrade, ~1-2 days of engineering work).

#### Broadest methodology (op profit only, full 35 tickers)

Op-profit YoY direction only, no event layer (works for both JGAAP
and IFRS filers):

| Sample | growth_likely | growth_unlikely | Overall |
|---|---|---|---|
| Original 20 | 61.9% [41-79] | 42.9% [16-75] | 57.1% [39-74] |
| OOS 15 | 50.0% [15-85] | 0.0% [0-49] (0/4) | 25.0% [7-59] |
| **Combined 35** | 60.0% [41-77] | **27.3% [10-57]** | **50.0% [35-66]** |

**Critical honest finding:** under op-profit-direction methodology on
combined sample, `growth_unlikely` collapses to 27%. The agent's bear
calls do NOT reliably predict next-year op-profit decline — they
predict adverse *events* (impairment, extraordinary loss). These are
different claims and require different tests.

### Methodology audit (chronological)

1. **Bundled Phase 6 (initial):** 70.6% hit rate. Voting rule was manufacturing confidence from `uncertain` raw judgments. Retired.
2. **Rolling-window with original ground truth:** 60.7% / 85.7%. Improved methodology but the ground truth ("growth = revenue AND stock both barely positive") was too easy to satisfy. Retired.
3. **Recipe A v1 (pre-registered):** Locked thresholds and 2-of-2 strict ±5% conjunction rule BEFORE scoring. Number collapsed to 35.7%. This was over-engineered — the agent's actual claim is single-axis fundamentals, not 2-axis conjunction.
4. **Qualitative review of 7 demo cases:** Independent reviewer scored agent's reasoning soundness. Result: 5 of 7 cases had useful reasoning, 1 passable, 1 thin. Pattern: agent is strong at evidence-surfacing, weaker at verdict-making with mild over-bullish tilt.
5. **Recipe A v2 (post-v1, justified by qualitative review):** Single-axis (op profit YoY) + event-based negative trigger. On JGAAP cohort with 2-year event window: 72.2% overall, 83.3% growth_unlikely.
6. **Recipe C (event-based only):** Separate axis — did a real impairment or extraordinary loss materialize? 73.3% / 80.0% / 60.0% on JGAAP cohort 2y window.

### The agent's actual value (after audit)

The agent's verdicts are modestly accurate with wide CIs. The
**agent's real value is in the evidence it surfaces**, not in its
verdicts as decision-makers. Independent qualitative review found
the reasoning consistently identifies real quantitative concerns
even when the final verdict is wrong.

Operational implication:

- **Read the agent's evidence (concentration ratios, CFO/NI flags, peer gaps, goodwill levels) and make your own verdict.** That's the legitimate use.
- **Treat verdicts as triage signals**, not determinations. Both `growth_likely` and `growth_unlikely` deserve human review; precision on either is too modest at this sample size to be acted on alone.
- **The agent saves compilation time** for analysts (the structured evidence would otherwise be manual work) but does NOT replace analyst judgment.

In one line: *the agent is a structured-evidence aggregator with
inspectable reasoning, not a precision predictor.*

### What we did NOT measure

- **Out-of-sample test** — same 20 tickers used for development AND
  measurement. Numbers are in-sample. True out-of-sample test on a
  separate 50-100 ticker universe was deliberately not run per cost
  decision.
- **Holdout time period** — we tested on FY2024+ outcomes which were
  available throughout development. A true forward test on FY2026+ data
  would take a year to accumulate.

### Confidence interval honesty

n=28 confident calls is small. Each ticker change ≈ 3.5pp shift. The
60.7% headline could plausibly be 55-65% on a different 20-ticker sample.
The 86% filter precision is more stable because it's based on focused
calls (only `growth_unlikely`) but n=7 is small.

---

## 12. Caching

### Cache directory

`outputs/agent_cache/`

### Cache key format

```
{ticker}_min{min_year}_simp{skip_simplify_0_or_1}_cutoff{cutoff_or_'none'}_{v1_or_v2cache}_{prompt_hash[:12]}_{_AGENT_CACHE_VERSION}.json
```

Example:
```
9432_min2020_simp1_cutoff2023_v1_38dd1625a574_v5_2026-05-16_bs_quality.json
```

### Components

| Component | Why |
|-----------|-----|
| ticker | Different companies = different cache entries |
| min_year | Different time windows = different entries |
| skip_simplify (0/1) | With/without simplify call = different output shape |
| cutoff | Different cutoffs = different LLM call counts |
| v1 vs v2cache | Different prompt-caching mode = different prompts |
| prompt_hash[:12] | SHA256 of the ADVANCED_PROMPT template — auto-invalidates on prompt edits |
| _AGENT_CACHE_VERSION | Bumped manually when agent behavior changes |

### Current version: `v5_2026-05-16_bs_quality`

Bump history:
- `v1_2026-05-14` — original Phase 1+2 cache
- `v2_2026-05-15_cashflow` — added cash-flow block
- `v3_2026-05-15_peers` — added peer comparison
- `v4_2026-05-15_qualitative` — Phase 5 text injection (rolled back)
- `v5_2026-05-16_bs_quality` — current, Phase 6 BS quality + concentration

**Known issue:** Old cache versions are not deleted. Disk grows unbounded
across bumps. Cleanup is manual.

---

## 13. Data sources and coverage

### Provider: Tempest Finance API

Per-ticker cache directory `data/tempest/<ticker>/` contains:

| File | Contents |
|------|----------|
| `company.json` | Basic identifiers (ticker, EDINET code, JPX code, name) |
| `disclosures.json` | All filing metadata (doc_type, doc_id, period_end, etc.) |
| `financials.json` | Annual top-level financial summary per FY |
| `financials_line_items.json` | All XBRL line items (BS, PL, CF, GOV) per FY with structured keys |
| `financials_quarterly.json` | Quarterly + semi-annual financial summaries |
| `indicators.json` | Per-FY ratios/derived metrics |
| `indicators_quarterly.json` | Quarterly indicators |
| `segments.json` | Per-segment revenue/profit per FY |
| `prices.json` | Daily close prices (for stock_5d_return) |
| `snapshot.json` | Latest-state convenience dump |
| `asr_texts/<doc_id>.json` | Parsed text sections from each ASR (only for `doc_type=120`, annual reports) |

### ASR text sections cached per annual report

| Section key | Japanese label | Typical length |
|-------------|---------------|----------------|
| `business_overview` | 事業の内容 | 1,500-2,500 chars |
| `business_risks` | 事業等のリスク | 5,000-30,000 chars |
| `md_and_a` | 経営者による経営成績等の検討及び分析 | 1,000-2,500 chars |
| `management_policy` | 経営方針、経営環境及び対処すべき課題等 | 1,500-3,000 chars |
| `research_development` | 研究開発活動 | 1,500-3,000 chars |
| `corporate_governance` | コーポレート・ガバナンスの状況 | 4,000-20,000 chars |
| `shareholder_distribution` | 株式の所有者別状況 | 500-1,000 chars |
| `major_shareholders` | 大株主の状況 | 500-2,000 chars |

### Universe coverage

- **Cached locally:** 44 tickers (subset of TOPIX 100 + some growth tech)
- **Tempest API limit:** TOPIX 100 only at the provider level
- **JPX 33業種 mapping:** 42 of 44 tickers mapped (95.5%); 2 unmapped (1306 ETF, 9719 SCSK — sector definition gap)
- **Peer-viable (sector has ≥5 peers):** 28 of 42 mapped tickers (67%)
- **Phase 6 active (≥3 years of BS quality data):** ~70% of tickers; telcos skip due to thin segment/goodwill data

### What's NOT in the cache (and would need separate integration)

- **決算短信 (earnings flash, Q1/Q3 reports):** In TDnet, not in Tempest cache
- **Forecast (業績予想) data:** Not exposed as structured fields in `financials.json`. Companies' next-year guidance numbers would need text extraction or separate fetching
- **Insider transactions:** Not in cache
- **Analyst consensus estimates:** Not in cache (and the agent is explicitly forbidden from inventing them)

---

## 14. Engineering arc (which phases worked, which didn't)

| Phase | Theme | Result |
|-------|-------|--------|
| **Phase 1** | Multi-year trajectory + cash-flow quality  | ✅ Shipped. LLM uses the data substantively (e.g. Mercari CFO/NI flag). |
| **Phase 2** | Sector peer comparison with min-peer rule  | ✅ Shipped. 88% citation rate when block active. |
| Phase 3 | Restructured "5-step reasoning" prompt  | ⏭️ Skipped. V2 caching precedent showed structural prompt changes can flip 40% of judgments. Risk > expected reward. |
| Phase 4 | Quarterly cadence  | ⏭️ Skipped. Japan abolished quarterly reports for FY2024+. Historical data exists in Tempest cache but quarterly XBRL is structurally thin (no segments, no goodwill, no narrative). Quarterly agent would be ~30-40% as rich as annual. |
| **Phase 5** | Risk-factor + auditor text injection  | ❌ Rolled back. 4% citation rate. LLMs don't reliably diff dense legal text. The structural lesson ("structured > raw text") shaped Phase 6. |
| **Phase 6** | Balance-sheet quality + concentration  | ✅ Shipped. 64% citation rate when block active. Caught JMDC's concentration risk (1 ticker correctly flipped). |
| Phase 7+ | Quarterly investigation | ⏭️ Investigated, deferred. Tempest already caches structured quarterly + semi-annual. Existing `analyze_company_quarterly()` works but uses only the legacy V1 prompt fields. Could be wired through later if needed. |
| Methodology audit | Rolling-window backtest  | ✅ Corrected the headline number. Replaced inflated 70.6% with honest 60.7%. |



---

## 15. Known limitations (the full audit)

### Statistical / measurement

1. **In-sample only.** Same 20 tickers for design + measurement. No
   out-of-sample test. Cited numbers carry this caveat.
2. **Small n.** 28 confident calls is small for an accuracy claim. ~3.5pp
   per ticker variance.
3. **Outcome proxy is rough.** rev↑ AND stock↑ over 5 days is a reasonable
   but imperfect signal. Complex cases (revenue grew, stock fell on weak
   guidance) get binned with truly bad outcomes.
4. **The 7 demo cases are hand-picked.** Selection bias — they're the
   best 7 cases out of ~55 predictions. Worth disclosing.

### Code-level

5. ~~**CFO/NI ratio skips negative-NI cases**~~ **✅ FIXED 2026-05-16.**
   The extractor now emits a `cfo_positive_despite_loss` flag when
   NI < 0 AND CFO > 0; the prompt block renders it as an explicit
   `POSITIVE EARNINGS-QUALITY SIGNAL` for the LLM.
6. ~~**Phase 5 dead code still runs per pair.**~~ **✅ FIXED 2026-05-16.**
   The per-pair `_qualitative_signals_yoy()` call, the kwarg threading
   through both build paths, and the response-payload entry have all
   been removed. The helper functions remain *defined* for a future
   structured-diff retry but are no longer called in the production
   pipeline.
7. **`_segment_yoy(zp, zp)` hack** in Phase 6 trajectory loop — works,
   but extracts segments twice per year.
8. **Quarterly path uses none of Phase 1/2/6 evidence.** Anyone running
   `analyze_company_quarterly()` gets the original V1 agent, not the
   improved one.
9. **Trend label directions confusing for declining values** in Phase 6
   block.
10. **Cache files grow unbounded** across version bumps.
11. **IN-LINE band thresholds (0.5pp, 1.0pp) are arbitrary**, not
    calibrated from sector standard deviations.

### Data-availability

12. **DSO and inventory_days never fire** — Tempest BS extractor doesn't
    expose `trade_receivables` or `inventory` for these tickers.
13. **Phase 6 doesn't render for telcos** (NTT, KDDI) — thin segment data.
14. **Forecast / management guidance not in cache** — biggest realistic
    accuracy unlock blocked behind TDnet integration.
15. **Universe limited to TOPIX 100** (Tempest API limit).

### Process

16. **No human expert validation** of the agent's reasoning. "Looks
    sensible" was checked by an LLM, not a Japanese equity analyst.
17. **No production deployment.** Code is committed but not running on a
    schedule, no API endpoint, no monitoring.
18. **Web UI not updated** for Phase 6 outputs (`app/api/ui.html` last
    touched for Phase 2).
19. ~~**No README**~~ **✅ FIXED 2026-05-16.** [README.md](../README.md)
    rewritten to reflect current state — TL;DR, quickstart, cache
    invalidation rules, methodology section, what the agent cannot do,
    pointers to AGENT_REPORT.md (this doc) and CLIENT_DEMO.md.
20. **No schema validation** on Tempest reads — if their API shape
    changes, agent silently breaks.

---

## 16. Code architecture

### Top-level files

```
app/
  subagents/
    quiet_change.py             # Main agent orchestration (2700+ lines)
    quiet_change_prompt.py      # Prompt templates + per-block builders
  ingest/
    tempest_loader.py           # All data extractors (BS, PL, CF, segments, ASR text)
    prices.py                   # Stock price helpers
  tools/
    bedrock.py                  # LLM transport (Bedrock + Anthropic Direct routing)
    jpx_industries.py           # JPX 33業種 sector lookup
  api/
    ui.html                     # Web UI (not updated for Phase 6)
    server.py                   # FastAPI endpoint
scripts/
  backtest_quiet_change.py      # Bundled-methodology backtest
  backtest_rolling_window.py    # Rolling-window backtest (corrected method)
  test_phase{1,2,5,6}_ab.py     # Per-phase A/B test harnesses
  _smoke_phase{1,5,6}_blocks.py # Per-phase smoke tests (no LLM)
outputs/
  agent_cache/                  # Per-ticker run cache, keyed by version + prompt hash
  backtest_*.json               # Backtest results
  phase{1,2,5,6}_ab_test.json   # A/B comparisons
  CLIENT_DEMO.md                # Client-facing summary
  AGENT_REPORT.md               # This document
data/
  tempest/<ticker>/             # Per-ticker Tempest API cache
```

### Key functions

| Function | File | Purpose |
|----------|------|---------|
| `analyze_company_multi_year` | quiet_change.py | Main entry — annual analysis |
| `analyze_company_quarterly` | quiet_change.py | Quarterly variant (legacy prompt only) |
| `analyze_company` | quiet_change.py | Single-pair convenience wrapper |
| `_segment_yoy` | quiet_change.py | Segment YoY computation |
| `_bs_yoy` | quiet_change.py | Balance-sheet YoY |
| `_pl_yoy` | quiet_change.py | P/L YoY + margin pp deltas |
| `_cashflow_yoy` | quiet_change.py | CF YoY |
| `_detect_cfo_ni_low_quality` | quiet_change.py | Earnings-quality flag |
| `_compute_sector_peer_medians` | quiet_change.py | Peer median computation |
| `_compute_bs_quality_history` | quiet_change.py | BS quality + concentration trend |
| `_check_narrative_coverage` | quiet_change.py | Run 17 post-LLM coverage rules |
| `build_advanced_prompt` | quiet_change_prompt.py | Assemble main LLM prompt |
| `build_advanced_v2` | quiet_change_prompt.py | V2 cacheable variant (gated off) |
| `_build_*_block` | quiet_change_prompt.py | Per-block renderers |
| `extract_*_from_zip_path` | tempest_loader.py | All data extractors |
| `invoke_text` | bedrock.py | LLM transport |
| `_explain_bilingual` | quiet_change.py | Two-call advanced+simplify orchestration |

---

## 17. Future approaches (prioritized, for the meeting)

### Tier 1 — Engineering hygiene

| Action | Status |
|--------|--------|
| Fix CFO/NI negative-NI bug | ✅ DONE 2026-05-16 (Section 4.2) |
| Remove dead Phase 5 code | ✅ DONE 2026-05-16 (Section 15 item #6) |
| Write README | ✅ DONE 2026-05-16 ([README.md](../README.md)) |
| Update web UI for Phase 6 | ⏳ PENDING — `app/api/ui.html` still renders only through Phase 2 fields. Realistic effort 4-6 hrs (initial estimate was optimistic). Conditional on whether the UI is part of the client demo. |

### Tier 2 — Should de-risk before any production use

| Action | Effort | Cost | Value |
|--------|--------|------|-------|
| Get Japanese equity analyst to review 5 demo cases | 1 day external | small | **Catches subtle hallucinations neither code nor LLM would see.** Highest leverage non-engineering step. |
| 50-100 ticker out-of-sample backtest | 1 day | ~$5-8 | Validates the +5.9pp Phase 6 gain isn't noise. Replaces the in-sample caveat. |
| Calibrate IN-LINE band thresholds from sector stddev | half day | $0 | Empirically grounded thresholds |
| Schema validation on Tempest reads | 1 day | $0 | Protects against silent breakage |

### Tier 3 — Depends on client feedback

| Option | Effort | Cost | When to do |
|--------|--------|------|------------|
| Wire Phase 1 features into quarterly path | 2 hrs | $0 | If client values early-warning use case |
| TDnet integration for forecast tracking | 1-2 weeks | high | If client specifically wants management-credibility signals |
| Structured-diff Phase 5 retry (parse risk text into added/removed/intensified items) | 3-5 days | ~$2 | If client values risk-disclosure changes specifically |
| Expand beyond TOPIX 100 | varies | data-provider cost | If client needs broader coverage |

### Tier 4 — Long-term

| Option | Notes |
|--------|-------|
| Phase 3 (reasoning prompt restructure) | High risk per V2 precedent; only worth it if Tier 2/3 don't unlock more |
| Production deployment + scheduling + monitoring | Requires a real deployment plan first |
| Alternative data integration | Out of scope of current data sources |
| Multi-model ensembling (Sonnet + Haiku) | Earlier A/B showed Haiku 4.5 was too different; not promising |

### My honest recommendation for the meeting

The single highest-leverage next step is **Tier 2 item #1: external
human expert validation of 5 demo cases**. Half a day external, cheap,
and it surfaces issues neither code review nor LLM self-evaluation can
catch. If the expert says "the reasoning is sound on these 5," the
agent's credibility for the client conversation goes up substantially.

The second highest is the **50-100 ticker out-of-sample backtest** —
~$5-8 of compute is trivial compared to the engineering already spent,
and it removes the in-sample caveat from every accuracy claim.

Everything else is conditional on what the client actually says they need.

---

## 18. Glossary

| Term | Meaning |
|------|---------|
| ASR | 有価証券報告書 — annual securities report filed with Japan's FSA |
| EDINET | Japan's official electronic disclosure system |
| TDnet | Tokyo Stock Exchange's timely disclosure system (separate from EDINET, hosts 決算短信) |
| 業績予想 | Management's published earnings forecast for the next period |
| 決算短信 | Quarterly earnings flash report (Q1/Q3) |
| 四半期報告書 | Quarterly report (abolished for FY2024+) |
| 半期報告書 | Semi-annual report (new format from FY2024) |
| JPX 33業種 | Japan Exchange's 33-sector industry classification |
| YoY | Year-over-year |
| pp | Percentage points |
| CFO | Cash from Operations |
| FCF | Free Cash Flow (CFO − capex) |
| CFO/NI ratio | Operating cash flow divided by net income — earnings quality signal |
| Herfindahl index | Sum of squared market shares × 10000; concentration measure |
| DSO | Days Sales Outstanding (trade_receivables / revenue × 365) |
| ABSTAIN | Agent's `uncertain` verdict — excluded from hit-rate scoring |
| Rolling-window backtest | Each prediction tested against next single year (industry standard) |
| Bundled backtest | Multiple judgments combined via voting rule vs aggregate outcome (retired methodology) |
| Filter precision | When the agent flags `growth_unlikely`, how often it's right |

---

## 19. Key numbers at a glance (for the meeting)

| Question | Answer |
|----------|--------|
| What is the agent? | A 3-class filter for Japanese listed equities |
| What 3 classes? | `growth_likely` / `growth_unlikely` / `uncertain` |
| How many evidence categories? | 4 (trajectory, cash flow, peers, BS quality) |
| LLM used? | Claude Sonnet 4.6 on Bedrock |
| Cost per company per fresh run? | ~$0.08 (2 LLM calls × $0.04) |
| Cost for TOPIX 100 fresh run? | ~$8 |
| Hit rate (original rolling-window, retired)? | 60.7% (weak ground truth, not anchored on) |
| Hit rate (Recipe A v2 grand-total JGAAP n=45, current best)? | **58.9%** [46-71 CI] |
| `growth_unlikely` precision (Recipe A v2 JGAAP, 2y)? | **73.3%** [48-89 CI, n=15] — earlier 85.7% from n=6 retired (small-sample optimism) |
| `growth_likely` precision (Recipe A v2 JGAAP, 2y)? | 53.7% [39-68 CI, n=41] — basically a coin flip, do not anchor on |
| Abstain rate? | ~49% |
| Total engineering investment? | ~$10.02 in LLM testing across 6 phases (no further LLM calls expected) |
| Number of demo cases ready? | 7 |
| Universe? | 44 tickers cached, TOPIX 100 subset, JPX 33業種 mapped |
| Production deployment? | Not yet — code committed, not running |
| Out-of-sample test? | Not done — deferred per cost decision |
| Human expert validation? | Not done — recommended as highest-leverage next step |
| Audit fixes applied? | ✅ 3 of 4 Tier 1 items done 2026-05-16 (CFO/NI fix, dead-code removal, README). UI update pending. |
| Backtest re-run after audit fixes? | No — fixes affect 0 of the 20 test tickers (all profitable); pattern only fires on loss-making companies with positive CFO. Disclosed in CLIENT_DEMO.md item #9. |
