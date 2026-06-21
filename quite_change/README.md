# quite_change — Quarterly flash-report classification (Japanese IT / 情報・通信業)

Classifies Japanese IT-sector companies, per fiscal year, into a **R± × S× quadrant**
(Revenue up/down × Stock up/down/flat over the 2-week post-earnings window), attaches a
**grounded Japanese "why"** read from each company's own 決算短信 (flash report) MD&A, groups
them into **reason buckets**, and renders a per-year **HTML view**.

The quadrant is always computed from the **data feed** (numbers + prices), never from the LLM.
The LLM only writes the narrative and picks a reason tag from a fixed vocabulary.

> There is an older, separate deliverable in this folder — the **R+ web-research view**
> (`build/build_view.py` → `deliverables/R_PLUS_2025_view.html`). It is *not* part of this
> pipeline; see the bottom of this file.

---

## 1. The model in one picture

```
         Stock ↑ (S+)      Stock ↓ (S−)      Stock ≈flat (S0, ±1%)
Rev ↑    R+S+              R+S−  ← "overlooked" focus
Rev ↓    R−S+              R−S−                  (5 tabs total)
```
- **Quadrant** = `category_of(rev%, net%, stock_dir)` — from the feed. Never the LLM.
- **stock_dir** = up / down / flat, from P0 (announce-day close) → P1 (10 trading days ≈ 2 weeks),
  with a ±1% "flat" noise band.
- **Reason buckets** = a fixed, shared vocabulary (e.g. `guidance_disappointment`,
  `margin_compression`, `saas_arr_expansion`). The **same reason → same bucket key + title in
  every year**, so buckets are comparable across years. New reasons go to `other`; if one recurs
  ≥3× and is grounded, it's *proposed* as a new bucket (human approves) — see `deliverables/quarterly/BUCKET_PROPOSAL.md`.

---

## 2. The pipeline is the SAME for every year

The year is just a parameter. The flow is identical:

```
select universe → retrieve reports → build packets → classify (LLM) → detect buckets → render HTML
```

**The only place it differs is WHERE the report comes from:**

| report age | source | file |
|---|---|---|
| **fresh** (≤ ~30 days) — latest/upcoming | live **TDnet** (release.tdnet.info) | `build/collect_tdnet.py` |
| **past years** (2022–2025 …) | **irbank / jiji / f.irbank** mirrors | `build/build_flash_db.py` + `build/backfill_irbank.py` |

Everything after retrieval (packets → classify → buckets → render) is year-agnostic.

---

## 3. Core files (the load-bearing ~14)

| stage | file(s) |
|---|---|
| **Universe** (any year) | `build/select_year.py` |
| **Retrieve — past** | `build/build_flash_db.py`, `build/backfill_irbank.py`, `build/recover_all.py` |
| **Retrieve — fresh** | `build/collect_tdnet.py` |
| **Packets** (numbers + prices + MD&A text) | `research/tempest_fetch.py`, `build/build_mdna_main.py`, `build/build_cohort_packets.py` |
| **Classify** (LLM) | `build/run_cohort_bedrock.py` (Bedrock sync), `build/run_it_batch.py` + `build/run_it_noweb.py` (prompt + schema + tag vocab), `app/tools/bedrock.py` (LLM wrapper) |
| **Buckets** | `build/phase1_detect_buckets.py`, `build/promote_buckets.py` |
| **Render** | `build/build_specific_view.py` (specific buckets), `build/build_reason_buckets.py` (generic buckets) |

> The other ~50 scripts in `build/` are one-off / experimental (`*_test50`, `select_2023`,
> `recover_9`, `build_oil_view`, `_make_*`, etc.) — **not** core to a fresh year run.

---

## 4. How to run a year

From `quite_change/` (env vars in `../.env`, see §6):

```bash
# 1) Universe for the year (JPX 情報・通信業 × Tempest financials for that period)
python build/select_year.py 2023            # → data/quarterly/_all_it_targets_2023.json

# 2) Retrieve the flash reports (past years; uses irbank/jiji/f.irbank mirrors)
JIJI_ONLY= python build/build_flash_db.py all-it data/quarterly/_all_it_targets_2023.json
#    (for the latest/fresh reports instead: python build/collect_tdnet.py)

# 3) Build packets (numbers/prices from Tempest + MD&A text from the fetched reports)
python build/build_cohort_packets.py 2023   # cohort back-year builder
#    (or build/build_mdna_main.py for the MD&A-prose upgrade on an existing packet dir)

# 4) Classify on Bedrock (sync; tracks cost, hard-stops at BUDGET_USD)
PKTDIR_NAME=_pkts_2023_mdna OUT_FILE=it_q4_2023.json BUDGET_USD=13 \
  python build/run_cohort_bedrock.py 2023   # → data/quarterly/it_q4_2023.json

# 5) Render
python build/build_reason_buckets.py 2023   # → deliverables/quarterly/VIEW_IT_2023Q4.html
```

---

## 5. What's implemented vs not (be honest with the orchestrator)

**Implemented & working:** retrieval (past + fresh), packet building, classification (on Bedrock),
bucket detection, rendering — all year-parameterized.

**Not yet / pending:**
- **No single one-command orchestrator** — it's the script *sequence* above. (A thin `run_year.py`
  wrapper is the natural next step.)
- **AWS batch (50% cheaper) is blocked** — the current IAM user has no S3 access, and Bedrock batch
  needs S3 + a service role. Classification runs on Bedrock **sync** until that's granted.
- **Anthropic API key is out of credits** — all LLM calls go through **AWS Bedrock** (same model,
  `claude-sonnet-4-6`, identical quality). `run_it_noweb.py` still references the old Anthropic batch
  API; `run_cohort_bedrock.py` is the Bedrock path.
- **Deterministic beat/raise/miss-vs-own-plan check** and the **analyst/news enrichment layer** are
  designed but not built (see `deliverables/quarterly/SENIOR_SUMMARY.md`).
- **Specific-bucket (Phase 2) classification** is staged/provisional, awaiting bucket-list sign-off.

---

## 6. Configuration (`.env`)

Secrets live in `../.env` (the repo root, one level above this folder) and are **never committed**.
Copy `.env.example` and fill in:

| var | purpose |
|---|---|
| `TEMPEST_API_URL`, `TEMPEST_API_KEY` | numbers + prices + 有報 MD&A (EDINET-XBRL feed) |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Bedrock LLM (billed to AWS) |
| `BEDROCK_MODEL_ID` | e.g. `us.anthropic.claude-sonnet-4-6` |
| `USE_BEDROCK` | `true` (Anthropic key is out of credits) |

Free mirrors (irbank / jiji / f.irbank) need no key — be a good citizen (gentle pacing).

---

## 7. Data policy — what's committed vs regenerated

**Committed** (small, valuable): code, `data/quarterly/it_q4_*.json` (outputs),
`*.staged.json`, `_all_it_targets_*.json` (universe), `_pkts_*_mdna/` (MD&A packet inputs),
`data/company_research_*.json`, `data/sector_config.json`, `deliverables/` HTML + reports.

**Ignored** (~1.7 GB, regenerable — see `.gitignore`): `data/flash_reports/` (決算短信 PDFs + text +
SQLite index), `_batch_results.jsonl`, cached PDFs (`_mdna_pdfs/`, `_test50_pdfs/`), `_tdnet_db/`,
backups. Re-fetch with the pipeline; you do **not** need them to read the results.

---

## Appendix — the older R+ web-research view (separate deliverable)

`build/build_view.py` builds `deliverables/R_PLUS_2025_view.html` from
`data/company_research_2025.json` + `data/parser_outputs/*.json` (web-research narratives, 82 R+
companies, FY2025). It is **standalone** and unrelated to the quarterly flash-report pipeline above —
kept for reference. `python build/build_view.py` regenerates it.
