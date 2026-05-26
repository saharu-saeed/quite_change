"""A/B test: Sonnet 4.6 vs Haiku 4.5 on the Quiet-Change agent.

Runs the SAME prompt (V1) on the SAME 5 tickers with both models, then
compares outlook_judgment per decision pair. If judgments match, Haiku
is acceptable as a ~4x cheaper drop-in replacement.

Cost estimate: ~$0.15 (10 Haiku LLM calls). The Sonnet side reads from
the existing V1 disk cache (free).
"""
from __future__ import annotations
import json
import os
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# CRITICAL: load .env BEFORE the bedrock module first reads BEDROCK_MODEL_ID,
# then override to Haiku for the test runs.
from dotenv import load_dotenv  # noqa: E402
load_dotenv(override=True)

from app.subagents.quiet_change import (  # noqa: E402
    analyze_company_multi_year, _AGENT_CACHE_DIR, _agent_cache_key,
)

TICKERS = ["4307", "9432", "9433", "9434", "9697"]
DECISION_CUTOFF_FY = 2023
HAIKU_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def _load_sonnet_from_cache(ticker: str) -> dict | None:
    """Load V1 (Sonnet) result from the existing disk cache."""
    key = _agent_cache_key(ticker, 2020, True, DECISION_CUTOFF_FY,
                           use_prompt_caching=False)
    p = _AGENT_CACHE_DIR / f"{key}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _judgments_by_pair(result: dict) -> dict[str, str]:
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
        out[f"FY{prev_fy}->FY{curr_fy}"] = p.get("outlook_judgment", "uncertain")
    return out


def main() -> int:
    print(f"A/B test: Sonnet 4.6 (cached) vs Haiku 4.5 (fresh)", flush=True)
    print(f"Tickers: {TICKERS}", flush=True)
    print(f"Decision cutoff: FY{DECISION_CUTOFF_FY}\n", flush=True)

    # Step 1: load Sonnet results from cache
    print("[step 1] Loading Sonnet 4.6 results from disk cache...", flush=True)
    sonnet_results: dict[str, dict] = {}
    missing = []
    for code in TICKERS:
        s = _load_sonnet_from_cache(code)
        if s is None:
            missing.append(code)
        else:
            sonnet_results[code] = s
            print(f"  {code}: Sonnet from cache ({len(s.get('pairs', []))} pairs)", flush=True)
    if missing:
        print(f"  MISSING from Sonnet cache: {missing}", flush=True)
        print(f"  Run scripts/test_prompt_caching.py first to populate.", flush=True)
        return 1

    # Step 2: switch to Haiku and run fresh
    print(f"\n[step 2] Switching BEDROCK_MODEL_ID to {HAIKU_MODEL_ID}", flush=True)
    os.environ["BEDROCK_MODEL_ID"] = HAIKU_MODEL_ID

    print(f"\n[step 3] Running Haiku 4.5 fresh (forced no-cache)...", flush=True)
    haiku_results: dict[str, dict] = {}
    for i, code in enumerate(TICKERS, 1):
        print(f"  [{i}/{len(TICKERS)}] {code}: Haiku running...", end="", flush=True)
        try:
            h = analyze_company_multi_year(
                code, min_year=2020, run_tests=False,
                skip_simplify=True,
                decision_cutoff_fy=DECISION_CUTOFF_FY,
                use_cache=False,           # force fresh LLM
                use_prompt_caching=False,  # use V1 prompt (production)
            )
            n_pairs = len([p for p in h.get("pairs", []) if not p.get("history_only")])
            print(f" ok ({n_pairs} pairs)", flush=True)
        except Exception as e:
            print(f" CRASHED: {e}", flush=True)
            h = {"error": str(e)}
        haiku_results[code] = h

    # Step 4: compare
    print("\n" + "=" * 80, flush=True)
    print("COMPARISON — Sonnet 4.6 vs Haiku 4.5 outlook_judgment per decision pair", flush=True)
    print("=" * 80, flush=True)
    print(f"\n  {'ticker':>6s}  {'pair':>15s}  {'Sonnet 4.6':>16s}  {'Haiku 4.5':>16s}  {'match':>5s}", flush=True)
    print(f"  {'-'*6}  {'-'*15}  {'-'*16}  {'-'*16}  {'-'*5}", flush=True)
    total = 0
    matches = 0
    mismatches = []
    for code in TICKERS:
        sj = _judgments_by_pair(sonnet_results.get(code, {}))
        hj = _judgments_by_pair(haiku_results.get(code, {}))
        for pair in sorted(set(sj.keys()) | set(hj.keys())):
            s = sj.get(pair, "<missing>")
            h = hj.get(pair, "<missing>")
            ok = "YES" if s == h else "NO"
            print(f"  {code:>6s}  {pair:>15s}  {s:>16s}  {h:>16s}  {ok:>5s}", flush=True)
            total += 1
            if s == h:
                matches += 1
            else:
                mismatches.append((code, pair, s, h))

    pct = matches / total * 100 if total else 0
    print(f"\n  Result: {matches}/{total} pairs match ({pct:.1f}%)", flush=True)
    if mismatches:
        print(f"\n  MISMATCHES:", flush=True)
        for code, pair, s, h in mismatches:
            print(f"    {code} {pair}: Sonnet={s} → Haiku={h}", flush=True)

    print(f"\n  COST COMPARISON (per company, 2 decision pairs):", flush=True)
    print(f"    Sonnet 4.6: ~$0.08", flush=True)
    print(f"    Haiku 4.5:  ~$0.025  ({100-25*100/8:.0f}% cheaper)", flush=True)

    if pct >= 90:
        print(f"\n  ✓ Haiku 4.5 looks ACCEPTABLE — judgments mostly match Sonnet.", flush=True)
        print(f"    Recommend: validate on a larger 20-ticker sample before adopting.", flush=True)
    elif pct >= 70:
        print(f"\n  ~ Haiku 4.5 is BORDERLINE — some judgments differ from Sonnet.", flush=True)
        print(f"    Risk depends on which way the mismatches go.", flush=True)
    else:
        print(f"\n  ✗ Haiku 4.5 is NOT acceptable — too many judgment differences.", flush=True)

    out_path = ROOT / "outputs" / "haiku_vs_sonnet_ab_test.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "decision_cutoff_fy": DECISION_CUTOFF_FY,
        "haiku_model": HAIKU_MODEL_ID,
        "matches": matches,
        "total_pairs": total,
        "match_pct": pct,
        "mismatches": [{"code": c, "pair": p, "sonnet": s, "haiku": h}
                       for c, p, s, h in mismatches],
        "sonnet_judgments": {c: _judgments_by_pair(sonnet_results.get(c, {})) for c in TICKERS},
        "haiku_judgments": {c: _judgments_by_pair(haiku_results.get(c, {})) for c in TICKERS},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
