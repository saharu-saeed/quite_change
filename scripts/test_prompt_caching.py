"""A/B test: V1 prompt vs V2 (prompt-caching) prompt.

Validates that the V2 split (static system + dynamic user, with "above"→"in
the data section" rewrites) produces the same outlook_judgment as V1 on a
small sample. If the judgments match, V2 is safe to adopt and we get
~30% input cost reduction for free.

Reads existing V1 cached results from outputs/agent_cache/ and runs V2
fresh (no cache) on the same tickers, then diffs the outlook_judgment
fields per pair.

Budget: ~$0.40-$0.50 for 5 tickers × 2 decision pairs = 10 LLM calls at
prompt-caching prices.
"""
from __future__ import annotations
import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import (  # noqa: E402
    analyze_company_multi_year, _AGENT_CACHE_DIR, _agent_cache_key,
)

TICKERS = ["4307", "9432", "9433", "9434", "9697"]  # spread of outcomes
DECISION_CUTOFF_FY = 2023


def _load_v1_from_cache(ticker: str) -> dict | None:
    """Read the V1 cached result (skip_simplify=True, cutoff=2023)."""
    key = _agent_cache_key(ticker, 2020, True, DECISION_CUTOFF_FY,
                           use_prompt_caching=False)
    p = _AGENT_CACHE_DIR / f"{key}.json"
    if not p.exists():
        # Try without decision cutoff (older runs)
        key2 = _agent_cache_key(ticker, 2020, True, None,
                                use_prompt_caching=False)
        p = _AGENT_CACHE_DIR / f"{key2}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _judgments_by_pair(result: dict) -> dict[str, str]:
    """Extract {pair_label: outlook_judgment} for decision pairs only."""
    if not result or "pairs" not in result:
        return {}
    out = {}
    for p in result["pairs"]:
        if p.get("history_only"):
            continue
        curr_fy = p.get("curr_fiscal_year", 0)
        if curr_fy > DECISION_CUTOFF_FY:
            continue
        prev_fy = p.get("prev_fiscal_year", "?")
        label = f"FY{prev_fy}->FY{curr_fy}"
        out[label] = p.get("outlook_judgment", "uncertain")
    return out


def main() -> int:
    print(f"A/B testing V1 vs V2 (prompt caching) on {len(TICKERS)} tickers", flush=True)
    print(f"Tickers: {TICKERS}", flush=True)
    print(f"Decision cutoff: FY{DECISION_CUTOFF_FY}\n", flush=True)

    # Step 1: load V1 cached results (or run fresh if missing)
    print("[step 1] Loading V1 results from cache (no LLM calls if cached)...",
          flush=True)
    v1_results: dict[str, dict] = {}
    for code in TICKERS:
        v1 = _load_v1_from_cache(code)
        if v1 is None:
            print(f"  {code}: V1 NOT CACHED — running fresh now (no cache write)",
                  flush=True)
            v1 = analyze_company_multi_year(
                code, min_year=2020, run_tests=False,
                skip_simplify=True,
                decision_cutoff_fy=DECISION_CUTOFF_FY,
                use_cache=True,            # save for future re-use
                use_prompt_caching=False,  # V1 path
            )
        else:
            print(f"  {code}: V1 from cache", flush=True)
        v1_results[code] = v1

    # Step 2: run V2 fresh (forced no-cache so we actually exercise the prompt)
    print("\n[step 2] Running V2 fresh (forced no-cache, LLM calls hit Bedrock)...",
          flush=True)
    v2_results: dict[str, dict] = {}
    for i, code in enumerate(TICKERS, 1):
        print(f"  [{i}/{len(TICKERS)}] {code}: V2 running...", end="", flush=True)
        try:
            v2 = analyze_company_multi_year(
                code, min_year=2020, run_tests=False,
                skip_simplify=True,
                decision_cutoff_fy=DECISION_CUTOFF_FY,
                use_cache=False,           # force fresh LLM
                use_prompt_caching=True,   # V2 path
            )
            n_pairs = len([p for p in v2.get("pairs", []) if not p.get("history_only")])
            print(f" ok ({n_pairs} pairs)", flush=True)
        except Exception as e:
            print(f" CRASHED: {e}", flush=True)
            v2 = {"error": str(e)}
        v2_results[code] = v2

    # Step 3: diff outlook_judgments per decision pair
    print("\n" + "=" * 80, flush=True)
    print("COMPARISON — V1 vs V2 outlook_judgment per decision pair", flush=True)
    print("=" * 80, flush=True)
    print(f"\n  {'ticker':>6s}  {'pair':>15s}  {'V1':>16s}  {'V2':>16s}  {'match':>5s}", flush=True)
    print(f"  {'-'*6}  {'-'*15}  {'-'*16}  {'-'*16}  {'-'*5}", flush=True)
    total_pairs = 0
    matches = 0
    mismatches_detail = []
    for code in TICKERS:
        v1_j = _judgments_by_pair(v1_results.get(code, {}))
        v2_j = _judgments_by_pair(v2_results.get(code, {}))
        pairs = sorted(set(v1_j.keys()) | set(v2_j.keys()))
        for pair in pairs:
            j1 = v1_j.get(pair, "<missing>")
            j2 = v2_j.get(pair, "<missing>")
            match = "YES" if j1 == j2 else "NO"
            print(f"  {code:>6s}  {pair:>15s}  {j1:>16s}  {j2:>16s}  {match:>5s}", flush=True)
            total_pairs += 1
            if j1 == j2:
                matches += 1
            else:
                mismatches_detail.append((code, pair, j1, j2))

    print(f"\n  Result: {matches}/{total_pairs} pairs match ({matches/total_pairs*100:.1f}%)", flush=True)
    if mismatches_detail:
        print(f"\n  MISMATCHES:", flush=True)
        for code, pair, j1, j2 in mismatches_detail:
            print(f"    {code} {pair}: V1={j1} → V2={j2}", flush=True)
        print(f"\n  → V2 changes the agent's judgment on {len(mismatches_detail)} pair(s).", flush=True)
        print(f"    Investigate before adopting V2.", flush=True)
    else:
        print(f"\n  → V2 is SAFE TO ADOPT. Same judgments, 30% cheaper input cost.", flush=True)

    # Save full diff for later inspection
    out_path = ROOT / "outputs" / "prompt_caching_ab_test.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "decision_cutoff_fy": DECISION_CUTOFF_FY,
        "matches": matches,
        "total_pairs": total_pairs,
        "mismatches": [{"code": c, "pair": p, "v1": j1, "v2": j2}
                       for c, p, j1, j2 in mismatches_detail],
        "v1_results": {c: _judgments_by_pair(v1_results.get(c, {})) for c in TICKERS},
        "v2_results": {c: _judgments_by_pair(v2_results.get(c, {})) for c in TICKERS},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
