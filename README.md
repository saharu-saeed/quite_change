# Quiet-Change Agent (静かな変化エージェント)

LLM-driven filter signal for Japanese listed equities. Reads each
company's annual securities report (有価証券報告書) and emits one of three
verdicts: `growth_likely` / `growth_unlikely` / `uncertain`. Intended as
a *first-pass triage* on a large universe — flag the companies that need
human attention.

**Status: shipped, not deployed.** Code is functional and validated;
not currently running on a schedule or behind an API.

---

## TL;DR — what this does

1. Loads pre-cached Tempest Finance API data for a Japanese ticker (TOPIX 100
   universe; ~44 tickers in the local cache).
2. For each YoY pair of annual reports, assembles a structured prompt with
   **four evidence categories**:
   - Multi-year revenue/margin trajectory (Phase 1)
   - Cash-flow quality (CFO, FCF, CFO/NI ratio + multi-year quality flag)
   - Sector peer comparison (JPX 33業種 medians)
   - Balance-sheet quality & concentration (Herfindahl, goodwill ratio)
3. Calls Claude Sonnet 4.6 (Bedrock) → produces a 7-field structured JSON
   judgment + bilingual explanation.
4. Runs 17 coverage-rule post-checks against the explanation.
5. Caches the full per-ticker result so re-runs are instant.

**Performance (rolling-window backtest, 20 tickers, 28 confident calls):**
- `growth_unlikely` precision: **85.7%** — reliable warning signal
- `growth_likely` precision: 52.4% — unreliable as all-clear
- Hit rate (overall): 60.7% on confident calls (excludes ~49% `uncertain`)

The agent is a **negative filter** (catch the bad ones for human review),
not a positive selector. Don't trust `growth_likely` calls as "this is fine."

---

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure credentials in .env
#    - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (for Bedrock — required)
#    - BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6
#    - ANTHROPIC_API_KEY (optional — if set, routes to Anthropic Direct instead of Bedrock)
#    - EDINET_API_KEY (optional — not used by the production agent; needed only for one-off EDINET investigations)
cp .env.example .env

# 3. Run on a single ticker (Python REPL or script)
python -c "
from app.subagents.quiet_change import analyze_company_multi_year
r = analyze_company_multi_year('9432', min_year=2020,
                               decision_cutoff_fy=2023, skip_simplify=True)
print(r['pairs'][-1]['outlook_judgment'])
"

# 4. Run a full backtest
python scripts/backtest_rolling_window.py        # rolling-window (correct method)
python scripts/backtest_quiet_change.py --tickers "9432,9697,4307"  # bundled (legacy)
```

**Cost guidance:**
- Single company fresh run: ~$0.08 (2 LLM calls × ~$0.04)
- TOPIX 100 full fresh run: ~$8
- Cached re-runs: free (instant)

---

## What's in the cache, what's not

Data lives in `data/tempest/<ticker>/`:

| File | Contents |
|------|----------|
| `financials.json` | Annual summary financials |
| `financials_line_items.json` | All XBRL line items (BS, PL, CF, GOV) per FY |
| `financials_quarterly.json` | Quarterly + semi-annual summaries |
| `segments.json` | Per-segment revenue per FY |
| `prices.json` | Daily close prices |
| `asr_texts/<doc_id>.json` | Parsed text sections from each annual report |
| `disclosures.json` | All filing metadata |

Cache is read-only at runtime; the agent never fetches from Tempest API live.
Refreshing requires running Tempest's data ingestion separately (not in this repo).

---

## Architecture

```
app/
├── subagents/
│   ├── quiet_change.py          # Main agent (analyze_company_multi_year)
│   └── quiet_change_prompt.py   # Prompt templates + per-block builders
├── ingest/
│   ├── tempest_loader.py        # All data extractors (BS, PL, CF, segments, ASR text)
│   └── prices.py                # Stock price helpers
├── tools/
│   ├── bedrock.py               # LLM transport (Bedrock + Anthropic Direct routing)
│   └── jpx_industries.py        # JPX 33業種 sector lookup
└── api/
    ├── server.py                # FastAPI endpoint
    └── ui.html                  # Web UI (note: not updated for Phase 6 outputs yet)

scripts/
├── backtest_rolling_window.py   # Rolling-window backtest (industry-standard methodology)
├── backtest_quiet_change.py     # Bundled backtest (legacy)
├── test_phase{1,2,5,6}_ab.py    # Phase-specific A/B test harnesses
└── _smoke_phase{1,5,6}_blocks.py# Smoke tests (no LLM)

outputs/
├── agent_cache/                 # Per-ticker run cache (keyed by version + prompt hash)
├── CLIENT_DEMO.md               # Client-facing summary
├── AGENT_REPORT.md              # Full technical reference (read this for details)
└── *_ab_test.json               # A/B comparison results
```

---

## Key entry points

| Function | Purpose |
|----------|---------|
| `analyze_company_multi_year(code)` | Production entry — annual analysis with all 4 evidence categories |
| `analyze_company_quarterly(code)` | Quarterly variant — uses legacy V1 prompt only (no Phase 1+2+6 evidence) |
| `analyze_company(code)` | Single-pair convenience wrapper |
| `backtest_ticker(code)` | Backtest one company (called by backtest scripts) |

---

## Cache invalidation

Cache key includes:
- ticker, min_year, skip_simplify, decision_cutoff_fy, use_prompt_caching
- SHA256 hash of `ADVANCED_PROMPT` template (auto-invalidates on prompt edits)
- `_AGENT_CACHE_VERSION` constant (manually bumped when agent behavior changes)

**Current cache version: `v5_2026-05-16_bs_quality`** (in `quiet_change.py`)

**If you change agent behavior (new evidence category, voting rule, etc.):**
1. Bump `_AGENT_CACHE_VERSION` in `app/subagents/quiet_change.py`
2. Use a descriptive suffix like `v6_<date>_<feature>`
3. Old cache files become orphaned but stay on disk (cleanup is manual)

---

## Methodology — bundled vs rolling-window

Two backtest scripts exist for historical reasons:

- **`scripts/backtest_quiet_change.py`** — original "bundled" methodology.
  Combines per-pair LLM judgments via a voting rule (default: `trend_aware`)
  into ONE verdict per company. Scores against an aggregate of multiple
  future-year outcomes. **The voting rule manufactures confidence from
  uncertain inputs, which inflates hit rate.** Retired but still works.

- **`scripts/backtest_rolling_window.py`** — corrected methodology.
  Industry-standard walk-forward validation: each annual report drives
  ONE prediction for the next year, scored independently. No voting. More
  predictions per ticker, methodologically defensible. **Use this for
  any accuracy claim.**

Headline numbers in `outputs/CLIENT_DEMO.md` and `outputs/AGENT_REPORT.md`
are from the rolling-window methodology.

---

## What the agent CANNOT do

- **Predict stock returns.** It's a 3-class qualitative filter, not a return-forecasting model.
- **Reason over thin quarterly data.** Quarterly XBRL lacks segments, goodwill, narrative.
  The quarterly path uses only the legacy V1 prompt (not Phase 1/2/6 evidence).
- **Use management forecasts (業績予想).** Not in Tempest cache; would need TDnet integration.
- **Reason over risk-factor text.** Phase 5 tried this (text injection) and was rolled back —
  the LLM ignored ~96% of the text. The structured-diff retry path is documented in
  `outputs/AGENT_REPORT.md` Section 17 but not built.
- **Work on companies outside TOPIX 100.** Tempest API limit.

---

## For full detail

| Document | Purpose |
|----------|---------|
| `outputs/AGENT_REPORT.md` | Comprehensive technical report — every detail of evidence categories, methodology, known issues, code structure, future paths. **Start here for any deep question.** |
| `outputs/CLIENT_DEMO.md` | Client-facing summary — positioning, demo cases, honest framing of metrics. |

---

## Honest limitations (short version)

- **In-sample only.** Same 20 tickers for development AND measurement.
  Out-of-sample test (50-100 tickers, ~$5-8) not yet done.
- **Asymmetric reliability.** Agent is reliable on `growth_unlikely`
  (~86% precision) but unreliable on `growth_likely` (~52%). Deploy
  accordingly.
- **Abstains ~49% of cases.** Honest behavior, but means the agent only
  commits on half of pairs.
- **Phase 6 doesn't render for telcos** (NTT, KDDI) — thin segment data.
- **DSO and inventory_days signals are dead code** — Tempest BS extractor
  doesn't expose `trade_receivables` / `inventory` for our tickers.
- **No human expert validation** of the agent's reasoning yet. Highest-
  leverage missing de-risking step.

Full audit and prioritized next-step list: `outputs/AGENT_REPORT.md` Sections 15-17.

---

## Project history (one-line per phase)

| Phase | Result |
|-------|--------|
| Phase 1 | ✅ Trajectory + cash-flow quality (shipped) |
| Phase 2 | ✅ Sector peer comparison (shipped) |
| Phase 3 | ⏭️ Reasoning prompt restructure (skipped — V2 caching precedent showed it can flip 40% of judgments) |
| Phase 4 | ⏭️ Quarterly cadence (skipped — Japan abolished quarterly reports for FY2024+) |
| Phase 5 | ❌ Risk-factor text injection (rolled back — LLM ignored 96% of text) |
| Phase 6 | ✅ BS quality + concentration (shipped) |
| Methodology audit | ✅ Corrected from bundled (70.6% inflated) to rolling-window (60.7% honest) |

Total LLM testing investment across all phases: ~$10.
