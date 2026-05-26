"""Phase 1 A/B test — Bedrock Sonnet 4.6.

Compares the Phase-1-enhanced agent (multi-year trajectory + cash-flow
block + CFO/NI < 0.8 flag) against the V1 cached baseline on a deliberate
5-ticker mix:
  - 9432 NTT             stable telco (sanity)
  - 9433 KDDI            telco peer (cross-check)
  - 9434 SoftBank Corp   known V2-prompt regression case
  - 4307 Nomura Research IT-services control
  - 9697 Capcom          lumpy entertainment

V1 baselines are read from `outputs/agent_cache/*_v1_2026-05-14.json`
(orphaned by the cache-version bump but still on disk). New runs hit
Bedrock fresh under the new prompt + new cache key.

Saves a full side-by-side per pair so we can read actual text diffs,
not just metrics.

Budget: ~$0.50 (10 LLM calls × ~$0.05).
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

# Sanity: ANTHROPIC_API_KEY must stay unset (user's pause is in effect).
assert not os.environ.get("ANTHROPIC_API_KEY"), \
    "ANTHROPIC_API_KEY must remain unset — user paused it. Aborting."

from app.subagents.quiet_change import (  # noqa: E402
    analyze_company_multi_year, _AGENT_CACHE_DIR,
)

TICKERS = ["9432", "9433", "9434", "4307", "9697"]
DECISION_CUTOFF_FY = 2023


def _load_v1_baseline(ticker: str) -> dict | None:
    """Find the V1 cache file (orphaned by the version bump but still on disk)."""
    matches = sorted(_AGENT_CACHE_DIR.glob(
        f"{ticker}_min2020_simp1_cutoff2023_v1_*_v1_2026-05-14.json"
    ))
    if not matches:
        return None
    try:
        return json.loads(matches[0].read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [warn] could not read {matches[0].name}: {e}", flush=True)
        return None


def _decision_pairs(result: dict | None) -> list[dict]:
    """Pairs we care about for comparison: curr_fy <= cutoff AND not history-only."""
    if not result or "pairs" not in result:
        return []
    out = []
    for p in result["pairs"]:
        if p.get("history_only"):
            continue
        curr_fy = p.get("curr_fiscal_year", 0)
        if curr_fy is None or curr_fy > DECISION_CUTOFF_FY:
            continue
        out.append(p)
    return out


def _pair_key(p: dict) -> tuple[int, int]:
    return (p.get("prev_fiscal_year", 0), p.get("curr_fiscal_year", 0))


# --- new-run lever: tone down per-pair sleep so the run finishes faster ---
def _truncate(s: str | None, n: int = 1200) -> str:
    if not s:
        return ""
    s = str(s)
    return s if len(s) <= n else (s[: n - 30] + " …[truncated]")


def main() -> int:
    print(f"Phase 1 A/B test — Bedrock Sonnet 4.6", flush=True)
    print(f"Tickers: {TICKERS}", flush=True)
    print(f"Decision cutoff: FY{DECISION_CUTOFF_FY}", flush=True)
    print(f"BEDROCK_MODEL_ID: {os.environ.get('BEDROCK_MODEL_ID')}\n", flush=True)

    # ---- Step 1: load V1 baselines ----
    print("[step 1] Loading V1 baselines from disk cache…", flush=True)
    v1: dict[str, dict] = {}
    missing = []
    for code in TICKERS:
        b = _load_v1_baseline(code)
        if b is None:
            missing.append(code)
        else:
            v1[code] = b
            pairs = _decision_pairs(b)
            print(f"  {code}: V1 cached ({len(pairs)} decision pair(s))", flush=True)
    if missing:
        print(f"  MISSING V1 baselines: {missing}", flush=True)
        return 1

    # ---- Step 2: run Phase-1 agent fresh on each ticker ----
    print("\n[step 2] Running Phase-1 agent fresh via Bedrock…", flush=True)
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
                use_cache=True,           # cache the new-version output for re-use
                use_prompt_caching=False,
            )
            elapsed = time.time() - ts
            n = len(_decision_pairs(r))
            print(f" ok ({n} pair(s), {elapsed:.1f}s)", flush=True)
        except Exception as e:
            print(f" CRASHED: {e}", flush=True)
            r = {"error": str(e)}
        new[code] = r
    total_elapsed = time.time() - t0
    print(f"\n  total wall time: {total_elapsed:.1f}s", flush=True)

    # ---- Step 3: side-by-side comparison ----
    print("\n" + "=" * 80, flush=True)
    print("COMPARISON — Phase 1 (new) vs V1 (cached) on decision pairs", flush=True)
    print("=" * 80, flush=True)
    print(f"\n  {'ticker':>6s}  {'pair':>16s}  {'V1':>16s}  {'NEW':>16s}  {'match':>5s}  cites_traj  cites_cf",
          flush=True)
    print(f"  {'-'*6}  {'-'*16}  {'-'*16}  {'-'*16}  {'-'*5}  {'-'*10}  {'-'*8}", flush=True)

    total = 0
    matches = 0
    growth_likely_to_uncertain = 0
    mismatches = []
    cites_traj_count = 0
    cites_cf_count = 0
    full_pairs: list[dict] = []

    # Tokens we count as "the explanation cited the new context"
    TRAJ_TOKENS = (
        "trajectory", "multi-year", "multiple years", "prior years", "expansion",
        "compression", "sustained", "bouncy", "3-year", "5-year", "year-over-year trend",
        "trend has",
    )
    CF_TOKENS = (
        "cash flow", "cash-flow", "operating cash", "free cash", "FCF",
        "CFO", "CFO/NI", "earnings quality", "earnings-quality",
        "capex", "capital expenditure",
    )

    for code in TICKERS:
        v1_pairs = {_pair_key(p): p for p in _decision_pairs(v1.get(code, {}))}
        new_pairs = {_pair_key(p): p for p in _decision_pairs(new.get(code, {}))}
        for key in sorted(set(v1_pairs) | set(new_pairs)):
            v1p = v1_pairs.get(key, {})
            np_ = new_pairs.get(key, {})
            v1j = v1p.get("outlook_judgment", "<missing>")
            nj = np_.get("outlook_judgment", "<missing>")
            ok = v1j == nj
            pair_label = f"FY{key[0]}->FY{key[1]}"

            expl_new = (np_.get("explanation_advanced_en") or "") + " " + \
                       (np_.get("outlook_reason_en") or "")
            expl_new_l = expl_new.lower()
            cites_traj = any(t.lower() in expl_new_l for t in TRAJ_TOKENS)
            cites_cf = any(t.lower() in expl_new_l for t in CF_TOKENS)
            if cites_traj:
                cites_traj_count += 1
            if cites_cf:
                cites_cf_count += 1

            print(
                f"  {code:>6s}  {pair_label:>16s}  {v1j:>16s}  {nj:>16s}  "
                f"{'YES' if ok else 'NO ':>5s}  {'YES' if cites_traj else '.  ':>10s}  "
                f"{'YES' if cites_cf else '.  ':>8s}",
                flush=True,
            )
            total += 1
            if ok:
                matches += 1
            else:
                mismatches.append((code, pair_label, v1j, nj))
                if v1j == "growth_likely" and nj == "uncertain":
                    growth_likely_to_uncertain += 1

            full_pairs.append({
                "ticker": code,
                "pair": pair_label,
                "match": ok,
                "v1": {
                    "outlook_judgment":     v1j,
                    "outlook_reason_en":    _truncate(v1p.get("outlook_reason_en")),
                    "outlook_reason_ja":    _truncate(v1p.get("outlook_reason_ja")),
                    "explanation_en":       _truncate(v1p.get("explanation_advanced_en")),
                    "explanation_ja":       _truncate(v1p.get("explanation_advanced_ja")),
                    "narrative_coverage_warnings": [w.get("rule") for w in v1p.get("narrative_coverage_warnings", [])],
                },
                "new": {
                    "outlook_judgment":     nj,
                    "outlook_reason_en":    _truncate(np_.get("outlook_reason_en")),
                    "outlook_reason_ja":    _truncate(np_.get("outlook_reason_ja")),
                    "explanation_en":       _truncate(np_.get("explanation_advanced_en")),
                    "explanation_ja":       _truncate(np_.get("explanation_advanced_ja")),
                    "narrative_coverage_warnings": [w.get("rule") for w in np_.get("narrative_coverage_warnings", [])],
                    "cites_trajectory":     cites_traj,
                    "cites_cashflow":       cites_cf,
                    "cfo_quality_flag":     np_.get("cfo_quality_flag"),
                },
            })

    pct = matches / total * 100 if total else 0
    print(f"\n  Result: {matches}/{total} pairs match ({pct:.1f}%)", flush=True)
    if mismatches:
        print(f"\n  MISMATCHES:", flush=True)
        for code, pair, v1j, nj in mismatches:
            print(f"    {code} {pair}: V1={v1j} → NEW={nj}", flush=True)
    print(f"\n  growth_likely → uncertain flips: {growth_likely_to_uncertain}", flush=True)
    print(f"  Explanations citing trajectory: {cites_traj_count}/{total}", flush=True)
    print(f"  Explanations citing cash flow: {cites_cf_count}/{total}", flush=True)

    if pct >= 85 and growth_likely_to_uncertain <= 1 and cites_cf_count >= total * 0.3:
        verdict = "PICTURE A — clean win. Ship Phase 1, proceed to Phase 2."
    elif pct >= 85 and cites_cf_count + cites_traj_count < total * 0.2:
        verdict = "PICTURE B — match rate fine but data ignored. Strengthen block usage guidance."
    elif pct < 80 or growth_likely_to_uncertain >= 3:
        verdict = "PICTURE C — unexpected flips. Investigate before shipping."
    else:
        verdict = "MIXED — partial win, inspect mismatches manually before next step."
    print(f"\n  Verdict: {verdict}", flush=True)

    # ---- Step 4: save full side-by-side ----
    out_path = ROOT / "outputs" / "phase1_ab_test.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "decision_cutoff_fy": DECISION_CUTOFF_FY,
        "matches": matches,
        "total_pairs": total,
        "match_pct": pct,
        "growth_likely_to_uncertain": growth_likely_to_uncertain,
        "cites_trajectory_count": cites_traj_count,
        "cites_cashflow_count": cites_cf_count,
        "verdict": verdict,
        "mismatches": [{"code": c, "pair": p, "v1": v, "new": n}
                       for c, p, v, n in mismatches],
        "pairs_full": full_pairs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
