"""Phase 6 A/B test — BS-quality + concentration bundle, 12 tickers, Bedrock Sonnet 4.6.

Dual baseline:
  - V1 (from backtest_20_it_5250.json):  cumulative Phase 1+2+6 effect
  - Phase 2 (agent_cache/*_v3_2026-05-15_peers.json): incremental Phase 6 effect
    (Phase 5 is rolled back — its v4 cache files are orphaned and ignored.)

Tracks the four new signals SEPARATELY so we can tell which add value and
which are dead weight if we ever want to prune.

Budget: ~$1.10 (12 fresh runs under v5 cache; Phase 6 block is ~10x smaller
than Phase 5's was, so prompts are actually slightly cheaper than Phase 5).
"""
from __future__ import annotations
import json
import os
import sys
import io
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

assert not os.environ.get("ANTHROPIC_API_KEY"), \
    "ANTHROPIC_API_KEY must remain unset — user paused it. Aborting."

from app.subagents.quiet_change import (  # noqa: E402
    analyze_company_multi_year, _AGENT_CACHE_DIR,
)

TICKERS = [
    "9432", "9433", "9434", "4307", "9697",
    "9984", "9684", "4684", "4385", "3659",
    "9719", "4475",
]
DECISION_CUTOFF_FY = 2023
V1_BASELINE_FILE = ROOT / "outputs" / "backtest_20_it_5250.json"


def _load_v1_baselines() -> dict[str, dict[str, str]]:
    bt = json.loads(V1_BASELINE_FILE.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for r in bt.get("rows", []):
        code = r.get("code")
        if not code:
            continue
        out[code] = {j["pair"]: j["judgment"] for j in r.get("per_pair_judgments", [])}
    return out


def _load_phase2_baseline(ticker: str) -> dict | None:
    matches = sorted(_AGENT_CACHE_DIR.glob(
        f"{ticker}_min2020_simp1_cutoff2023_v1_*_v3_2026-05-15_peers.json"
    ))
    if not matches:
        return None
    try:
        return json.loads(matches[0].read_text(encoding="utf-8"))
    except Exception:
        return None


def _decision_pairs(result: dict | None) -> list[dict]:
    if not result or "pairs" not in result:
        return []
    return [p for p in result["pairs"]
            if not p.get("history_only")
            and p.get("curr_fiscal_year", 0) is not None
            and p.get("curr_fiscal_year", 0) <= DECISION_CUTOFF_FY]


def _truncate(s: str | None, n: int = 1500) -> str:
    if not s:
        return ""
    s = str(s)
    return s if len(s) <= n else (s[: n - 30] + " …[truncated]")


def _pair_label(p: dict) -> str:
    return f"FY{p['prev_fiscal_year']}->FY{p['curr_fiscal_year']}"


# Four NEW Phase 6 signal categories tracked individually per other-Claude's
# instruction. Tokens chosen narrowly: a hit means the explanation
# substantively referenced THAT category, not just any vaguely-related word.
NEW_SIGNAL_TOKENS = {
    "concentration": (
        "concentration", "concentrated", "herfindahl", "top segment",
        "top-segment", "single segment", "diversification",
        "bet-the-company", "revenue concentration",
    ),
    "goodwill_ratio": (
        "goodwill/equity", "goodwill to equity", "goodwill-to-equity",
        "goodwill ratio", "acquisition risk", "goodwill build",
        "impairment risk", "acquisition-heavy", "acquisition heavy",
    ),
    "dso": (
        "dso", "days sales outstanding", "days-sales-outstanding",
        "receivables collection", "collection cycle",
        "receivables quality",
    ),
    "inventory_days": (
        "inventory days", "inventory-days", "days of inventory",
        "inventory build", "inventory turnover", "inventory accumulation",
    ),
}

# Existing Phase 1+2 signals kept for continuity (so we see if older
# features still get cited at the same rate as before).
PRIOR_SIGNAL_TOKENS = {
    "peer":      (
        "sector", "peer", "median", "below peers", "above peers",
        "below-median", "above-median",
    ),
    "cashflow":  (
        "cash flow", "cash-flow", "operating cash", "free cash", "FCF",
        "CFO", "CFO/NI", "earnings quality", "earnings-quality",
        "capex", "capital expenditure",
    ),
    "trajectory": (
        "trajectory", "multi-year", "multiple years", "prior years",
        "expansion", "compression", "sustained", "3-year", "5-year",
    ),
}


def _hits(text: str, tokens: tuple) -> bool:
    l = text.lower()
    return any(t.lower() in l for t in tokens)


def main() -> int:
    print("Phase 6 A/B test — 12 tickers, Bedrock Sonnet 4.6", flush=True)
    print(f"BEDROCK_MODEL_ID: {os.environ.get('BEDROCK_MODEL_ID')}", flush=True)
    print(f"Tickers ({len(TICKERS)}): {TICKERS}\n", flush=True)

    print("[step 1] Loading baselines…", flush=True)
    v1_map = _load_v1_baselines()
    p2_map: dict[str, dict] = {}
    for code in TICKERS:
        p2 = _load_phase2_baseline(code)
        if p2 is None:
            print(f"  {code}: Phase2 baseline MISSING", flush=True)
        else:
            p2_map[code] = p2
        v1 = v1_map.get(code)
        print(f"  {code}: V1={'ok' if v1 else 'MISSING'}  Phase2={'ok' if code in p2_map else 'MISSING'}",
              flush=True)

    print("\n[step 2] Running Phase-6 agent fresh via Bedrock…", flush=True)
    new: dict[str, dict] = {}
    t0 = time.time()
    for i, code in enumerate(TICKERS, 1):
        print(f"  [{i}/{len(TICKERS)}] {code}: running…", end="", flush=True)
        ts = time.time()
        try:
            r = analyze_company_multi_year(
                code, min_year=2020, run_tests=False,
                skip_simplify=True,
                decision_cutoff_fy=DECISION_CUTOFF_FY,
                use_cache=True,
                use_prompt_caching=False,
            )
            elapsed = time.time() - ts
            n = len(_decision_pairs(r))
            print(f" ok ({n} pair(s), {elapsed:.1f}s)", flush=True)
        except Exception as e:
            print(f" CRASHED: {e}", flush=True)
            r = {"error": str(e)}
        new[code] = r
    print(f"\n  total wall time: {time.time()-t0:.1f}s", flush=True)

    # --- comparison + per-signal citation tracking ---
    print("\n" + "=" * 100, flush=True)
    print("COMPARISON — Phase 6 (new) vs V1 (cumulative) vs Phase 2 (incremental)",
          flush=True)
    print("=" * 100, flush=True)
    print(
        f"\n  {'ticker':>6}  {'pair':>16}  {'V1':>14}  {'Phase2':>14}  "
        f"{'Phase6':>14}  {'v1':>3}  {'p2':>3}  "
        f"NEW: conc gwl dso inv  PRIOR: peer cf traj  bs6_active",
        flush=True,
    )

    total = 0
    matches_v1 = 0
    matches_p2 = 0
    gli_v1 = 0
    gli_p2 = 0
    incremental_flips = []
    cite_counts_new = {k: 0 for k in NEW_SIGNAL_TOKENS}
    cite_counts_prior = {k: 0 for k in PRIOR_SIGNAL_TOKENS}
    block_active_count = 0
    full_pairs: list[dict] = []

    for code in TICKERS:
        v1_pairs_map = v1_map.get(code, {})
        p2_pairs_map = {_pair_label(p): p for p in _decision_pairs(p2_map.get(code, {}))}
        new_pairs_map = {_pair_label(p): p for p in _decision_pairs(new.get(code, {}))}
        for pair_label in sorted(set(v1_pairs_map) | set(p2_pairs_map) | set(new_pairs_map)):
            v1j = v1_pairs_map.get(pair_label, "<missing>")
            p2j = (p2_pairs_map.get(pair_label) or {}).get("outlook_judgment", "<missing>")
            np_ = new_pairs_map.get(pair_label, {})
            nj = np_.get("outlook_judgment", "<missing>")

            expl = (np_.get("explanation_advanced_en") or "") + " " + \
                   (np_.get("outlook_reason_en") or "")

            cites_new = {k: _hits(expl, toks) for k, toks in NEW_SIGNAL_TOKENS.items()}
            cites_prior = {k: _hits(expl, toks) for k, toks in PRIOR_SIGNAL_TOKENS.items()}
            for k, h in cites_new.items():
                if h: cite_counts_new[k] += 1
            for k, h in cites_prior.items():
                if h: cite_counts_prior[k] += 1

            bs_hist = np_.get("bs_quality_history") or []
            bs_active = bool([r for r in bs_hist
                              if any(r.get(k) is not None for k in
                                     ("top_segment_share_pct", "herfindahl_index",
                                      "goodwill_to_equity_pct", "dso_days",
                                      "inventory_days"))]) and len(bs_hist) >= 3
            if bs_active:
                block_active_count += 1

            ok_v1 = (v1j == nj)
            ok_p2 = (p2j == nj)
            if ok_v1: matches_v1 += 1
            if ok_p2: matches_p2 += 1
            if not ok_v1 and v1j == "growth_likely" and nj == "uncertain":
                gli_v1 += 1
            if not ok_p2 and p2j == "growth_likely" and nj == "uncertain":
                gli_p2 += 1
            if not ok_p2:
                incremental_flips.append((code, pair_label, p2j, nj))
            total += 1

            def _y(b): return 'Y' if b else '.'
            print(
                f"  {code:>6}  {pair_label:>16}  {v1j:>14}  {p2j:>14}  {nj:>14}  "
                f"{'YES' if ok_v1 else 'NO':>3}  {'YES' if ok_p2 else 'NO':>3}  "
                f"     {_y(cites_new['concentration'])}   {_y(cites_new['goodwill_ratio'])}   "
                f"{_y(cites_new['dso'])}   {_y(cites_new['inventory_days'])}        "
                f"{_y(cites_prior['peer'])}    {_y(cites_prior['cashflow'])}   "
                f"{_y(cites_prior['trajectory'])}    {'ACT' if bs_active else 'skip'}",
                flush=True,
            )

            full_pairs.append({
                "ticker": code, "pair": pair_label,
                "v1_judgment": v1j, "p2_judgment": p2j, "new_judgment": nj,
                "match_v1": ok_v1, "match_p2": ok_p2,
                "bs6_block_active": bs_active,
                "new": {
                    "outlook_reason_en": _truncate(np_.get("outlook_reason_en")),
                    "outlook_reason_ja": _truncate(np_.get("outlook_reason_ja")),
                    "explanation_en":    _truncate(np_.get("explanation_advanced_en")),
                    "explanation_ja":    _truncate(np_.get("explanation_advanced_ja")),
                    "narrative_coverage_warnings":
                        [w.get("rule") for w in np_.get("narrative_coverage_warnings", [])],
                    "cites": {**cites_new, **cites_prior},
                    "bs_quality_history": bs_hist,
                },
            })

    pct_v1 = matches_v1 / total * 100 if total else 0
    pct_p2 = matches_p2 / total * 100 if total else 0
    print(f"\n  Match vs V1 (cumulative): {matches_v1}/{total} ({pct_v1:.1f}%)", flush=True)
    print(f"  Match vs Phase 2 (incr.): {matches_p2}/{total} ({pct_p2:.1f}%)", flush=True)
    print(f"  growth_likely → uncertain vs V1:      {gli_v1}/{total} ({gli_v1/total*100:.0f}%)",
          flush=True)
    print(f"  growth_likely → uncertain vs Phase 2: {gli_p2}/{total} ({gli_p2/total*100:.0f}%)",
          flush=True)
    print(f"\n  bs_quality block active: {block_active_count}/{total} pairs", flush=True)

    print(f"\n  NEW signal citation rates (each tracked separately):", flush=True)
    for k in NEW_SIGNAL_TOKENS:
        n = cite_counts_new[k]
        denom = block_active_count if block_active_count else 1
        print(f"    {k:<20}: {n}/{total} overall ({n/total*100:.0f}%)  |  "
              f"{n}/{block_active_count} of active-block pairs ({n/denom*100:.0f}%)",
              flush=True)

    print(f"\n  PRIOR signal citation rates (Phase 1+2 features still working?):", flush=True)
    for k in PRIOR_SIGNAL_TOKENS:
        n = cite_counts_prior[k]
        print(f"    {k:<20}: {n}/{total} ({n/total*100:.0f}%)", flush=True)

    if incremental_flips:
        print(f"\n  Phase 6 incremental flips (vs Phase 2):", flush=True)
        for c, p, a, b in incremental_flips:
            print(f"    {c} {p}: Phase2={a} → Phase6={b}", flush=True)
    else:
        print(f"\n  Phase 6 introduced no new flips vs Phase 2.", flush=True)

    # Verdict
    new_signal_active_uses = sum(cite_counts_new.values())
    needed = max(1, block_active_count) * 0.4
    if pct_p2 >= 85 and gli_p2 <= total * 0.15 and new_signal_active_uses >= needed:
        verdict = "PICTURE A — Phase 6 ships. New signals being used by the LLM."
    elif pct_p2 >= 90 and new_signal_active_uses < block_active_count * 0.2:
        verdict = ("PICTURE B — Phase 6 stable but new signals ignored "
                   "(same failure mode as Phase 5). Consider rollback.")
    elif pct_p2 < 80 or gli_p2 > total * 0.25:
        verdict = "PICTURE C — Phase 6 caused regressions. Investigate before shipping."
    else:
        verdict = "MIXED — inspect manually."
    print(f"\n  Verdict: {verdict}", flush=True)

    out_path = ROOT / "outputs" / "phase6_ab_test.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "decision_cutoff_fy": DECISION_CUTOFF_FY,
        "total_pairs": total,
        "matches_v1": matches_v1, "match_pct_v1": pct_v1,
        "matches_p2": matches_p2, "match_pct_p2": pct_p2,
        "growth_likely_to_uncertain_vs_v1": gli_v1,
        "growth_likely_to_uncertain_vs_p2": gli_p2,
        "bs6_block_active_count": block_active_count,
        "new_signal_citation_counts":  cite_counts_new,
        "prior_signal_citation_counts": cite_counts_prior,
        "incremental_flips_vs_p2": [{"code": c, "pair": p, "p2": a, "p6": b}
                                    for c, p, a, b in incremental_flips],
        "verdict": verdict,
        "pairs_full": full_pairs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
