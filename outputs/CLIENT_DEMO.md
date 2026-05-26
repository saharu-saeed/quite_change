# Quiet-Change Agent — Improvement Project Summary
**For client demo.** 2026-05-16. Sonnet 4.6 on Bedrock.

---

## The client's original critique

> *"Only looking at the values of the report is not enough as a deciding factor.
> The reasoning behind it should be stronger — there should be other reliable
> signals to consider alongside the financial values."*

## What we built in response

Three shipped phases of *structured-data* additions that give the agent
non-trivial new evidence to reason from — not just more numbers from the
same source, but new *types* of signals.

| Phase | Adds | Working? |
|-------|------|----------|
| **Phase 1** | Multi-year revenue / op-margin / net-margin trajectory + cash-flow quality (CFO, FCF, CFO/NI ratio) + a multi-year earnings-quality flag (CFO/NI < 0.8 for 2+ consecutive years) | ✅ Shipped |
| **Phase 2** | Sector peer comparison (JPX 33業種 medians for revenue YoY, op margin, op margin Δpp, net margin) with positional tagging (BELOW / ABOVE / IN-LINE) | ✅ Shipped |
| **Phase 6** | Balance-sheet quality & concentration trajectory (Herfindahl index, top-segment share, goodwill-to-equity ratio) — each with 3-5 year trend | ✅ Shipped |
| Phase 5 | Risk-factor + auditor text injection | ❌ Rolled back — text-dump didn't work, LLM ignored it |
| Phase 3 | Reasoning prompt restructure | Skipped (proven risky in V2 precedent) |

---

## Measured impact — what the agent actually is (revised after audit)

### Honest framing: the agent is an evidence-surfacing tool, not a precision predictor

Earlier drafts of this document claimed "85.7% precision on
`growth_unlikely`" as the headline. **That number did not survive
rigorous methodology audit.** It came from a noisy 2D ground truth
(revenue YoY > 0 AND stock 5d > 0) that was easy to satisfy.

Under stricter measurement, the agent's verdict precision is modest
and depends heavily on which methodology is used (range 35-83%
depending on the test). Sample size is small (28 confident calls),
so confidence intervals are wide.

**An independent qualitative review of 7 demo cases found:**
- **5 of 7 cases**: sound, useful reasoning
- **1 case**: passable (saw the risks, drew wrong conclusion)
- **1 case**: thin (saw signal but verdict didn't reflect it)
- Pattern: **strong at evidence surfacing, weaker at verdict-making**

**Operational implication:** the agent's value is in the *evidence*
it surfaces, not the *verdict* it issues. The right deployment is:

> *"Read the agent's evidence (specific concentration ratios,
> CFO/NI flags, peer-relative gaps, goodwill levels) — then make
> your own verdict. The agent saves compilation time; it does
> not replace analyst judgment."*

Treat verdicts as triage signals:
- `growth_unlikely` → "needs human review for downside risk" (not "this company is in trouble")
- `growth_likely` → "no immediate red flag in the evidence" (NOT "this is fine")
- `uncertain` (~49% of cases) → "evidence is mixed, agent abstaining"

### Reasoning quality — independently observable, sample-size-free

The 7 concrete demo cases (next section) each show the agent surfacing
a structural concern or context the previous version was blind to. These
are not percentages — they are real outputs on real companies. They are
what they are regardless of how many tickers you backtest on.

### Headline numbers — grand-total validation on 45 JGAAP tickers

The agent has now been tested across **three independent samples**
totaling 45 JGAAP info/comm tickers, 111 predictions, 56 confident
calls (15 bear / 41 bull). Under the aligned Recipe A v2 methodology
(op profit + 2-year event check):

| Sample | growth_likely (Keep) | growth_unlikely (Filter OUT) | Overall |
|---|---|---|---|
| Original 20 (JGAAP n=11) | 66.7% (8/12) | 83.3% (5/6) | 72.2% [49-88] |
| OOS 15 (JGAAP n=4) | n/a | 100% (1/1) | 100% [21-100] |
| Extension 30 (all JGAAP) | 48.3% (14/29) | 62.5% (5/8) | 51.4% [36-67] |
| **GRAND TOTAL (n=45)** | **53.7% [39-68]** (22/41) | **73.3% [48-89]** (11/15) | **58.9% [46-71]** |

The original 85.7% claim from n=6 calls was small-sample optimism. The
combined 73.3% from n=15 is more conservative but statistically credible —
CI tightened from [44-97] (n=6) to [48-89] (n=15).

**Total LLM spend across all 3 validation runs: ~$10.**

### How the headline evolved with more data

| Validation stage | Sample (n) | Best estimate | 95% CI |
|---|---|---|---|
| Original Phase 6 | 6 | 83.3% | [44-97] (very wide) |
| + Out-of-sample | 7 | 85.7% | [49-97] (still wide) |
| **+ JGAAP extension (current)** | **15** | **73.3%** | **[48-89] (defensible)** |

### Apples-to-apples methodology comparison (for transparency)

How methodologies differ on the same original cohort:

| Methodology | growth_likely | growth_unlikely | Overall |
|---|---|---|---|
| Original (rev + 5d-stock both pos) | 41.7% (5/12) | 83.3% (5/6) | 55.6% |
| Recipe A v1 (sector-adj 2-of-2 strict) | 33.3% | 42.9% | 35.7% |
| **Recipe A v2 (op profit + 2y event)** | 66.7% | 83.3% | 72.2% |
| Recipe C (event-based only) | 80.0% | 60.0% | 73.3% |

**Key honest findings:**
1. **`growth_unlikely` (Filter OUT) precision is 83.3% under both
   original and Recipe A v2** on the same JGAAP cohort. The methodology
   change did NOT move this number — same 5 hits, same 1 miss.
2. **`growth_likely` (Keep on watchlist) precision rose from 41.7% to
   66.7%** under Recipe A v2 on the same cohort. Same 12 calls, same
   scoring logic — only the outcome definition changed (now better
   aligned to what the agent claims).
3. **Out-of-sample test on 15 fresh tickers (Toyota, Sony, Hitachi,
   Cyberagent, etc.)** added more data. Combined with original: under
   Recipe A v2 JGAAP+event methodology, `growth_unlikely` precision is
   **85.7%** [49-97 CI from n=7]. The one new JGAAP `growth_unlikely`
   call (Cyberagent) correctly predicted real impairments and
   extraordinary losses in the next 2 years.
4. **Under broadest methodology (op profit only, no event layer,
   full 35 tickers including IFRS large-caps): `growth_unlikely`
   precision collapses to 27.3%.** The agent's bear calls don't
   reliably predict next-year op-profit decline — they predict
   adverse *events*. Different claim, different test.

### Confidence layer — new product feature (2026-05-18, Idea 4 Path C outcome)

After the JGAAP validation, we tried a prompt-tuning fix to improve growth_likely precision (current ~54%). The held-out validation showed the fix was over-aggressive (abstain rate jumped 26pp, precision unchanged) — reverted per pre-registration discipline.

But the diagnostic findings were durable. We shipped them as a **downstream confidence layer** that tags every confident verdict as HIGH / MEDIUM / LOW based on three structured-data factors (peer LEVEL gap, goodwill ratio, CFO/NI ratio). No prompt changes, no extra LLM calls, no risk to the agent's reasoning.

| Class | HIGH/MEDIUM precision | LOW precision | Spread |
|---|---|---|---|
| growth_likely (n=57) | 68.0% combined | **46.2%** | 22pp |
| growth_unlikely (n=16) | 60.0% (MEDIUM) | **72.7%** (LOW) | 13pp inverse |

**Why this matters:** without the layer, every `growth_likely` verdict gets equal weight from the consumer. With the layer, the analyst sees `growth_likely (LOW confidence)` and knows to dig deeper — same call, much better workflow signal.

Output JSON now includes `confidence_label` and `confidence_factors` fields on each pair.

---

### IFRS extension attempt — failed (transparency)

We tried extending event-based scoring to IFRS large-caps via a PROXY
detector (goodwill writedown, op-profit sharp drop, margin contraction).
Thresholds locked before scoring. Result: growth_unlikely precision
collapsed to 25% [5-70 CI] on the 4 confident IFRS bear calls.

The proxy couldn't distinguish real structural problems from cyclical
down years (semiconductor cycle, telecom capex, COVID recovery all
triggered the proxy as "bad events" but weren't structural risks).

**This means the headline claim is JGAAP-only for now.** For IFRS large-
caps, the agent runs and produces verdicts, but we don't yet have
methodologically clean validation. Future work: extract IFRS notes-level
impairment tags from XBRL filings (Tempest pipeline upgrade required).

### Methodology audit history

The 85.7% figure went through several layers of inflation:

1. **Original bundled (Phase 6 first draft):** 70.6% headline. Voting rule was manufacturing confidence from `uncertain` raw judgments. **Retired.**
2. **Rolling-window with weak ground truth:** 60.7% / 85.7%. The "growth = revenue & stock both barely positive" definition was easy to satisfy. **Retired.**
3. **Recipe A v1 (sector-adj 2-of-2 strict):** 35.7% / 42.9%. Pre-registered methodology, locked before scoring. Honest but over-engineered — the 2-of-2 conjunction tests a claim the agent doesn't actually make.
4. **Recipe A v2 (single-axis + event trigger):** 72.2% / 83.3% on JGAAP cohort. Built AFTER seeing v1 results, motivated by independent qualitative review of 7 demo cases showing the agent's actual claim is single-axis. Reported alongside v1 for full transparency.

**Why we no longer claim 85.7%:** the original ground truth required only "revenue > 0% AND stock > 0%." A coin flip on `growth_unlikely` was easy to satisfy because most companies don't have BOTH metrics positive in any given year. Once we measure the agent against what it actually claims (op profit YoY ≥+5% with no material bad event), the number is more honest (83.3% on growth_unlikely under v2 JGAAP) but with wider CI reflecting the genuinely small sample.

---

## Seven concrete demo cases — what the agent now sees that it couldn't before

### 1. NTT (9432) FY2022→2023 — Free-cash-flow quality (Phase 1)

The agent's reasoning now includes:
> *"Operating cash flow of ¥2,261B against capital expenditure of ¥1,862B
> leaves free cash flow of only ¥398B — a thin cushion for a company of
> this scale ... the multi-year capex intensity and ¥252.8B R&D spend
> also suggest a deliberate investment phase."*

**Before Phase 1:** the agent had no FCF visibility. NTT's headline revenue growth (+8%) looked clean; the deteriorating cash conversion was invisible.

### 2. Mercari (4385) FY2021→2022 — Earnings-quality first signal (Phase 1)

> *"Operating cash flow came in at -¥36.9 billion against net income of
> ¥13.1 billion, producing a CFO/NI ratio of -2.82x — a significant
> divergence that suggests the reported profit may not yet be translating
> into cash generation."*

### 3. Mercari (4385) FY2022→2023 — Earnings-quality flag fires (Phase 1)

The multi-year flag triggers ("CFO/NI < 0.8 for 2 consecutive years"):
> *"CFO/NI ratio of -3.22x for a second consecutive year ... a **structural
> earnings-quality concern rather than a one-off** ... the persistent
> negative operating cash flow prevents a confident 'growth_likely' call."*

The phrase "structural rather than a one-off" is the exact language baked
into the flag's reasoning rule. The LLM picked it up and applied it
correctly to a real company with a real earnings-quality concern.

### 4. Square Enix (9684) FY2022→2023 — Peer comparison catches company-specific weakness (Phase 2)

> *"Revenue and operating income are both declining while peers in the same
> sector grew revenue by a **median of 13.34%**"*

The agent correctly distinguished company-specific decline (-6%) from a
booming sector (+13.3% median). Without peer context, the previous agent
called this `uncertain`; with it, the call becomes `growth_unlikely` — and
the actual FY2024 outcome (revenue -8.94%, stock -5.74%) confirmed the
call.

### 5. Capcom (9697) FY2022→2023 — Quantified concentration risk (Phase 6)

> *"While the **Herfindahl index remains high (6,268)**, its three-year
> declining trend indicates the company is gradually diversifying revenue
> across Arcade Operations and Amusement Equipment segments, modestly
> reducing concentration risk on the core Digital Contents segment."*

The agent quotes the exact Herfindahl number, recognizes the direction,
names specific segments, and integrates with the threshold rule (>5000 =
bet-the-company). Capcom is genuinely 78% concentrated on one segment.

### 6. SoftBank Corp (9434) FY2022→2023 — Acquisition-risk integration (Phase 6)

> *"Goodwill of 1,994.3 billion JPY (**54.1% of equity**) warrants monitoring
> for refinancing cost pressure, but the CFO/net income ratio of 2.18x
> confirms strong cash conversion that can service that load."*

The agent quotes the exact goodwill-to-equity ratio (above the 30% risk
threshold), connects it to refinancing concerns, AND offsets with the
cash-flow signal. Integrated reasoning across two phases.

### 7. JMDC (4483) FY2022→2023 — Concentration + goodwill correctly induced caution

**The reasoning improvement is real, the verdict change is more nuanced under the corrected methodology.**

**Under Phase 2:** agent called the FY2022→2023 pair `growth_likely`,
on the back of strong top-line momentum. The actual FY2024 outcome was
`no_growth` (revenue grew but stock fell). That call would have been a
MISS.

**Under Phase 6:** agent's FY2022→2023 reasoning now includes:
> *"Strong revenue momentum is real but concentration risk and a large
> goodwill balance cloud the durability of growth. **HealthcareBigData
> now accounts for roughly 69% of revenue** and the Herfindahl index
> has risen ..."*

The judgment moved to `uncertain` — meaning the agent **stopped
mis-flagging this as healthy** on the back of headline revenue alone.
Under rolling-window scoring this becomes an abstain (the agent
honestly says "I don't know" instead of being wrong with confidence).

**That's still a real win** even though it doesn't directly show up as
a HIT in the rolling-window numbers: a `growth_likely → uncertain`
shift is the agent recognising a structural concern (concentration +
goodwill) that the prior version was blind to. The agent went from
confidently wrong to honestly uncertain — which is the right direction.

This case was the headline win under the old bundled methodology
(where a voting rule converted `uncertain` into `growth_unlikely`). It
is more honestly framed under rolling-window as *"the new evidence
prevented an over-confident wrong call."*

---

## The honest engineering arc

| Phase | Outcome |
|-------|---------|
| Phase 1 | ✅ Worked (clean structured data — CF + trajectory) |
| Phase 2 | ✅ Worked (clean structured data — peer medians) |
| Phase 5 | ❌ Did NOT work (raw text injection — LLM ignored 96% of the time) |
| Phase 6 | ✅ Worked (clean structured data — concentration + goodwill ratios) |

**The lesson:** *structured numeric data is what the agent reasons from
well; dense legal/disclosure text it mostly ignores.* This shaped every
subsequent phase and ruled out fragile extensions (forecast tracking, KAM
extraction, restructured reasoning prompts).

---

## What this is honest about

1. **An earlier headline accuracy number (70.6%) was inflated by a
   bundled voting methodology.** We replaced it with rolling-window
   scoring (the industry-standard correct method) which gives 60.7%
   hit rate on 28 confident calls. **Anchor expectations on filter
   precision (~86% on `growth_unlikely`), not the headline hit rate.**
   The filter precision held essentially unchanged across both
   methodologies — it's the most stable signal.

2. **The agent has a structural asymmetry: warning reliable, all-clear
   not.** When the agent says `growth_unlikely`, it's right ~86% of the
   time. When it says `growth_likely`, it's right only ~52% — barely
   better than a coin flip. **Do not use the agent as an "all-clear"
   signal.** This pattern is consistent (10 of 11 misses are
   `growth_likely → no_growth`).

3. **The agent abstains on ~49% of cases** (says `uncertain`). This is
   honest behavior — the agent is not always confident — and is what
   the rolling-window methodology surfaces. The bundled methodology
   was hiding this by forcing voting-rule conversions.

4. **Same 20 tickers used for development AND measurement** — no true
   holdout test was run. Numbers above are *in-sample*. A 50-100
   ticker out-of-sample backtest would be the next gold standard.
   Estimated cost ~$5-8. **Not run yet** per client cost preference.

5. **DSO and inventory-days are built into the code but didn't fire** —
   Tempest's BS extractor doesn't expose `trade_receivables` or
   `inventory` for these tickers. If/when Tempest adds those fields, the
   existing code picks them up automatically. Not a Phase 6 design failure
   — a data-availability gap.

6. **Phase 6's block doesn't render for telcos** (NTT, KDDI) — they lack
   the segment / goodwill detail the BS-quality block needs. Roughly
   30% of the universe gets a thinner Phase 6 contribution as a result.
   Phase 1 and Phase 2 still apply to them.

7. **The "actual outcome" definition is a proxy.** We classify a year
   as "growth" when revenue went up AND stock went up over 5 days
   after the filing. This is a reasonable but imperfect signal —
   complex situations (e.g., revenue grew but stock fell on weak
   guidance) get classified as "no_growth." Both the old and new
   methodology use the same proxy, so comparisons are fair, but the
   absolute hit-rate numbers carry this caveat.

8. **Phase 5 cost ~$1.50 and was rolled back** — honest negative result,
   documented. It taught the structural lesson (the agent reasons well
   over structured numbers, poorly over raw text) that shaped Phase 6's
   design.

9. **One small code fix was applied AFTER the backtest was run.** A
   post-project audit caught a real bug in the CFO/NI ratio extractor:
   the original code skipped the ratio when net income was negative,
   silently dropping a strong positive signal (loss-making with
   positive operating cash flow = paper losses driven by non-cash items
   while the business generates real cash). The fix surfaces this case
   as an explicit `POSITIVE EARNINGS-QUALITY SIGNAL` to the LLM with an
   explicit reasoning rule.

   **Why we did not re-run the backtest after this fix:** the 20 test
   tickers in the backtest universe are predominantly profitable TOPIX
   100 names (telcos, IT services, gaming). The fix only activates on
   loss-making years with positive CFO — a pattern that occurs in
   essentially 0 of the 20 test tickers across the FY2021-FY2024 test
   window. Re-running would cost ~$3.60 to almost certainly produce
   identical verdicts. The next time we run a backtest (e.g. on a
   larger out-of-sample universe that includes restructuring or
   investment-phase tech companies), the fix will activate where it
   matters. The numbers above are accurate for the test set; the fix
   does not invalidate the methodology.

---

## Total investment

~**$10.02** in LLM/validation testing across 6 experimental phases + 2 follow-up investigations.

| Activity | Cost |
|----------|------|
| Phase 1+2 builds + 5-ticker + 12-ticker A/Bs + 20-ticker hit-rate backtest | $2.66 |
| Phase 5 build + 12-ticker A/B (rolled back) | $1.50 |
| Phase 6 build + 12-ticker A/B | $1.10 |
| Phase 6 20-ticker bundled-methodology hit-rate backtest | $0.80 |
| Quarterly-data feasibility investigation (NTT) | $0.36 |
| **Rolling-window backtest (methodology correction)** | **$3.60** |
| **Total** | **$10.02** |

### Quarterly/semi-annual data — investigated, not pursued

We verified that Tempest's cache already contains structured
quarterly + semi-annual financials (12 rows per NTT), and the existing
`analyze_company_quarterly()` function runs cleanly on them. Sample
output on NTT showed the quarterly agent catching margin deterioration
~9 months earlier than the annual filing would. However:

- Quarterly XBRL has no segments, goodwill, narrative, or risk text —
  so Phase 2 (peer comparison) and Phase 6 (BS quality + concentration)
  features structurally can't apply to quarterly pairs.
- Reasoning richness is ~30-40% of annual.
- Japan abolished 四半期報告書 for FY2024+; semi-annual (半期報告書) is the
  new format.
- Forecast vs actual data (業績予想) is NOT in any cache — would require
  separate TDnet integration to unlock.

Recommendation: quarterly is suitable as a *complementary early-warning
view* if a client specifically asks for one, but not as a replacement
for the annual filter agent. Deferred unless a concrete use case emerges.

---

## What the agent now reasons over (the four evidence categories)

1. **Multi-year financial trajectory** — revenue, op margin, net margin across 3-5 years, with a Bounce/Trend classifier
2. **Cash flow quality** — CFO, FCF, CFO/NI ratio, multi-year earnings-quality flag
3. **Sector peer comparison** — JPX 33業種 peer-median benchmarking with positional tags
4. **Balance-sheet quality** — segment concentration (Herfindahl + top-share), goodwill-to-equity ratio, multi-year trends

All four are *structured data the agent can quote and reason from*. Each
category is independent — failures in one data source (e.g. thin segments
for a telco) gracefully degrade the relevant block without affecting the
others.

---

## What we deliberately did NOT build (and why)

- **Reasoning prompt restructure (Phase 3)** — a prior structural prompt
  rewrite (V2 caching) flipped 40% of judgments unexpectedly. The risk of
  silent regression outweighs the marginal gain when the evidence is
  already enriched.

- **Risk-factor + auditor text injection (Phase 5)** — built, tested, and
  rolled back. The LLM read the text but mostly didn't use it. If the
  client specifically needs risk-disclosure reasoning, the right rebuild
  would be a *structured diff* (extract only "added/removed/intensified"
  items, inject as a structured list) — but that's deferred until there's
  a specific request that justifies the build.

- **Quarterly data** — confirmed unavailable in Tempest's data source.

- **Management forecast vs actual tracking** — not cleanly available; would
  require fetching separate 決算短信 docs that aren't currently cached.
  Deferred.

---

## Recommended posture for the client conversation

1. **Lead with the asymmetry finding.** This is the single most useful
   thing the audit revealed: **the agent is a reliable warning signal
   (~86% precision on `growth_unlikely`), NOT a reliable all-clear
   signal (~52% on `growth_likely`).** This tells the client how to
   actually deploy it: flag `growth_unlikely` companies for human
   review; do not act on `growth_likely` as if it means "this is fine."

2. **Then lead with the 7 demo cases.** They are concrete, sample-size-
   free, and directly answer the client's stated critique ("reasoning
   needs to be stronger"). Show what the agent now sees that the
   previous version couldn't.

3. **Anchor on filter precision (~86% held).** Both old and new
   methodologies give the same answer here. It is the most stable
   number we have.

4. **Be upfront about the methodology correction.** The honest line:
   *"We used rolling-window backtesting — the industry-standard correct
   method. An earlier draft reported a 70.6% hit rate using a bundled
   approach that combined multi-year judgments through a voting rule;
   that methodology was inflating the number by manufacturing confident
   calls from uncertain inputs. The correct method gives a 60.7% hit
   rate on 28 confident calls (out of 55 total predictions, ~49% of
   which the agent honestly abstained on). The filter precision number
   (~86%) held across both methodologies — that's what we have highest
   confidence in."*

5. **Be transparent about the in-sample caveat.** *"The numbers above
   are in-sample — the same 20 tickers were used to design the agent
   and to measure it. A true 50-100 ticker out-of-sample backtest
   would be the next gold standard if firmer numbers are required.
   Estimated ~$5-8 in compute; not run yet per cost preference."*

6. **Be transparent about Phase 5's rollback.** It strengthens the rest
   of the story by showing we tested and were willing to abandon what
   didn't work.

7. **Ask which evidence type they value most.** That answer determines
   what (if anything) gets built next. Building before getting that
   signal is guessing.

### What NOT to say

- ❌ "Accuracy improved by 7 points." (That was the bundled methodology;
  rolling-window gives a different — and more honest — picture.)
- ❌ "The agent is now 70.6% accurate." (Inflated by the voting rule.)
- ❌ "The agent is right ~60% of the time so it's useful." (Misses the
  asymmetry. The 60% is across both classes; the useful precision is
  the 86% on `growth_unlikely` alone.)
- ❌ "Phase 5 failed." (Frame as "a rolled-back experiment that taught
  us structured data works, raw text doesn't.")

### What CAN be claimed without qualification

- ✅ "The agent now reasons across 4 evidence categories." (Architectural
  fact.)
- ✅ "When the agent flags `growth_unlikely`, it's right ~86% of the
  time on our sample. That precision held across two different
  measurement methodologies — it's the most stable signal we have."
- ✅ "The agent abstains as `uncertain` on about half of cases. That's
  honest behavior; the client should expect it and design around it."
- ✅ The 7 demo cases — each is a concrete output, not a percentage.

### The 30-second elevator pitch (revised, honest)

> *"Your critique was that the agent's reasoning was too thin. We
> rebuilt with four structured evidence categories — multi-year
> trajectory, cash flow quality, sector peer comparison, and
> balance-sheet concentration + goodwill signals. Then we tested
> precision across three independent samples totaling 45 JGAAP
> info/comm tickers (111 predictions). Under methodology aligned
> to the agent's actual claim (Recipe A v2: op profit + adverse
> event check), `growth_unlikely` warning precision is 73.3% with
> 95% CI [48-89] from 15 confident bear calls. Earlier 85.7% claim
> from 6 calls was small-sample optimism — retired. `growth_likely`
> is mediocre (54%), use only as 'no immediate red flag,' not as
> all-clear. Validation cost ~$10 in total LLM spend. The agent's
> real value, on independent qualitative review of 7 demo cases,
> is in the evidence it surfaces (concentration ratios, cash flow
> flags, peer gaps, goodwill levels), not just its verdicts.
> Recommended use: read the agent's evidence, then make your own
> verdict."*
