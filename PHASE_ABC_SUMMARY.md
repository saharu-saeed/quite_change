# Phases A / B / C — closeout summary (2026-05-01)

Three back-to-back phases shipped against the QUICK roadmap. Phase D (BS / CF /
pattern lenses) is parked pending real-usage signal.

## What shipped

### Phase A — Quiet Change explanation upgrade
Upgraded the agent's per-pair English/Japanese explanation to (a) open with a
revenue-composition sentence naming the top segments by share-of-total, (b)
attempt a hedged reconciliation when operating profit and the 5-day post-filing
stock direction disagree, and (c) drop foreign-company tangents that aren't
tied to a revenue/profit driver in the filing. Surface area: a new
`OPERATING_PROFIT_TAGS` extractor, a re-shaped prompt with a divergence flag
block, three new sentence-level coverage rules, and a stacked-bar composition
chart per pair in the UI. Verified on SoftBank Corp / Sony / Rakuten — all
three explanations stayed on Japanese segments with zero false-positive
foreign-tangent flags.

### Phase B — Multi-sector expansion
Replaced the hardcoded JPX 5250 (IT) filter with a `sector_code` parameter
threaded through `build_universe`, `run`, the `/similar-company` endpoint, and
a 13-option dropdown in the UI. Added three sector-seed ingest scripts
(`fetch_finance_peers.py`, `fetch_realestate_peers.py`,
`fetch_logistics_peers.py`) and ran them. Discovered mid-flight that banks /
transport / insurance use different XBRL revenue tags
(`OrdinaryIncomeSummaryOfBusinessResults`,
`OperatingRevenue1SummaryOfBusinessResults`) — added them to `REVENUE_TAGS`.
Final non-IT universe: Banking 5, Securities 2, Insurance 3, Real Estate 9,
Land Transport 5, Marine Transport 3, Air Transport 2, Warehousing 2. Verified
on MUFG / Mitsui Fudosan / JR East — top-3 peers and rationales were
domain-correct, including the "Yamato → JR East" relatedness drop to 28/100
(same JPX code, different business).

### Phase C — Phase-matching for young companies
For candidates with fewer than 4 fiscal years of revenue history (where
trajectory similarity is undefined), find older filers in the SAME sector
whose own early-history phase pattern-matches the young candidate's full
history, and surface what came next for them as a hedged prediction.
Three-dimensional fingerprint (growth rate / top segment share / segment
count), Euclidean distance on z-scored values, top-3 anchors per young
candidate, hard cap on confidence at 40/100 (intentional — phase-matching is
speculative), one bilingual LLM-narrative call per matched anchor, SVG
sparkline per match in the UI. Verified end-to-end on a LINEヤフー
2-year-truncation: confidence 14/40, 3 sensible matched anchors (NRI / U-NEXT
/ NTT), bilingual narratives generated cleanly. Confidence sanity check
confirmed: N=3 truncation raised confidence to 22/40 (caught and fixed a bug
in the confidence-input wiring during verification).

## Known v1 limitations (all three phases)

**Phase A**
- `_check_foreign_tangent` allows a sentence with a `%` or yen figure even if
  the foreign mention is decorative ("compared to the US, which grew 15%"
  passes). Tightening would require semantic parsing — not in v1.
- yfinance silently returns no data for delisted / halted tickers. The
  divergence flag won't fire in those cases, even if profit and stock truly
  diverged.

**Phase B**
- Sectors with fewer than 2 companies in the local data error out with a
  clear message but the UI doesn't disable empty options in the dropdown.
- JPX 33業種 classifications drift over time (Rakuten was reclassified into
  5250 IT in 2023). The override list in `app/tools/jpx_industries.py` needs
  manual maintenance whenever this happens.
- A handful of seed codes failed during ingest (9147 NIPPON EXPRESS — zero
  ZIPs returned; 8804 Tokyo Tatemono — FY2020/FY2021 outside scan window).
  Scripts are idempotent — re-running picks up nothing extra unless the EDINET
  scan windows widen.

**Phase C**
- Single-segment filers can't phase-match. `extract_segments` returns empty,
  so `top_segment_share` and `segment_count` are unobtainable, so the
  fingerprint can't be built and `match_young_candidate` returns None. Hit
  during verification on 出前館 (food delivery, single segment).
- Anchor segment data uses a snapshot from the latest ZIP and is reused
  across all sliding phases of that anchor. An anchor that diversified mid-
  history (e.g., a former single-segment company that's now a conglomerate)
  will appear single-segment in its earlier phases too — distorting matches.
- Era factor is a coarse 2010 / 2015 cutoff. A real macro adjustment would
  normalize for GDP / interest rates / market cycle.
- 40-cap on confidence is intentional. Even a perfect match can't exceed
  40/100. This is a feature, not a bug — flag if it confuses readers.

**Cross-cutting**
- `outputs/cache/similar_company_pairs_v5.json` and the feature cache grow
  unbounded. No eviction logic. Manually delete if disk fills.
- EDINET fiscal-year-end disagreement warnings flood the logs on every load
  (each ZIP is checked individually). Cosmetic only — the iXBRL value is
  trusted and the values are correct.

## Things to watch for in real usage (likely-to-surface bugs)

| Pattern | What might break | Where to look |
|---|---|---|
| User picks a sector with 0 ingested companies (e.g. JPX 3050 Foods, never seeded) | Endpoint returns clean error; UI shows error message but dropdown still offers the option | `similar_company.run` error branch; `app/api/ui.html` `renderSimilarResults` |
| Young candidate is a single-segment filer (most early-stage SaaS) | Phase-match panel renders nothing; no error to user | `app/subagents/phase_matching.py:_segments_snapshot` returns `{}` |
| Quiet Change run on a non-IT mega-cap (e.g., MUFG) | Foreign-tangent guardrail not yet validated outside IT — banks routinely mention overseas operations | `_check_foreign_tangent` may flag legitimate driver mentions or miss tangents |
| Anchor classification changed mid-window (Rakuten → 5250 in 2023) | Pre-2023 phases may still appear under the old sector for the JPX master, depending on cache state | `app/tools/jpx_industries.py` overrides + `_OVERRIDES` dict |
| Sector with 2 companies (Air Transport: JAL / ANA) | n_anchors=1 → 1 candidate. Works mathematically but ranking is degenerate | UI shows it, no error |
| Phase-match anchor diversified later | Latest-segment-snapshot reuse means early phases get current-day segment metrics. Distance calculations off-target | `phase_matching._build_anchor_phases` — segments fetched once per anchor |
| Foreign mention with numeric attribution but no real driver tie | Rule allows: e.g., "compared to the US which grew 15%" passes the `_NUMERIC_ATTRIBUTION_RE` check | `quiet_change.py:_check_foreign_tangent` |
| LLM cache hits stale data after prompt changes | Runs use old rationales until the cache version bumps | `similar_company.py:PAIR_CACHE` is `_v5`. Bump on prompt changes |
| Profit/stock divergence flag with magnitude under 0.5% | Flag suppressed by design; explanation skips reconciliation | `quiet_change.py:_divergence_flag` — `abs(...) < 0.5` guard |

## What's parked

- Phase D — BS / CF / pattern-matching lenses. Originally scoped as
  "exploration" with undecided spec. Revisit after 1-2 weeks of real usage to
  see what users (or QUICK) actually ask for; might not be BS/CF.

## Quick references

- Plan file: `C:\Users\Sahal Saeed\.claude\plans\here-we-have-to-recursive-crystal.md`
- Verification scripts: `verify_foreign_tangent.py`, `verify_phase_b.py`,
  `verify_cross_sector.py`, `verify_phase_c.py`
- Unit tests: `tests/test_phase_matching.py` (9 cases, all passing)
