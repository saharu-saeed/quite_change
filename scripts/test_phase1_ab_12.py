"""Phase 1 A/B test — wider validation (12 tickers) via Bedrock Sonnet 4.6.

Expands the 5-ticker A/B test to 12 with deliberate sector + scale + volatility
diversity. Reuses `outputs/backtest_20_it_5250.json` as the V1-equivalent
baseline source — its per_pair_judgments match the v1_2026-05-14 cache
exactly for the 5 already validated, so trustworthy for the 7 new picks.

Existing 5 (from previous A/B):
  9432 NTT, 9433 KDDI, 9434 SoftBank Corp, 4307 Nomura Research, 9697 Capcom

New 7:
  9984 SoftBank Group  — investment conglomerate, different volatility
  9684 Square Enix     — gaming peer to Capcom
  4684 Obic            — IT services peer to 4307
  4385 Mercari         — growth tech / marketplace
  3659 NEXON           — mobile gaming, lumpy
  9719 SCSK            — mid-cap IT services
  4475 HENNGE          — small-cap SaaS

Budget: ~$0.96 (12 × ~2 pairs × ~$0.04). Bedrock Sonnet 4.6.
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

from app.subagents.quiet_change import analyze_company_multi_year  # noqa: E402

TICKERS = [
    "9432", "9433", "9434", "4307", "9697",         # existing 5
    "9984", "9684", "4684", "4385", "3659",         # new 5
    "9719", "4475",                                  # new 2 — round out to 12
]
DECISION_CUTOFF_FY = 2023
BASELINE_FILE = ROOT / "outputs" / "backtest_20_it_5250.json"


def _load_all_v1_baselines() -> dict[str, dict[str, str]]:
    """Map ticker → {pair_label → outlook_judgment} from backtest_20_it_5250."""
    if not BASELINE_FILE.exists():
        raise FileNotFoundError(f"missing baseline source: {BASELINE_FILE}")
    bt = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for r in bt.get("rows", []):
        code = r.get("code")
        if not code:
            continue
        pair_map = {j["pair"]: j["judgment"] for j in r.get("per_pair_judgments", [])}
        if pair_map:
            out[code] = pair_map
    return out


def _decision_pairs(result: dict | None) -> list[dict]:
    if not result or "pairs" not in result:
        return []
    return [p for p in result["pairs"]
            if not p.get("history_only")
            and p.get("curr_fiscal_year", 0) is not None
            and p.get("curr_fiscal_year", 0) <= DECISION_CUTOFF_FY]


def _truncate(s: str | None, n: int = 1200) -> str:
    if not s:
        return ""
    s = str(s)
    return s if len(s) <= n else (s[: n - 30] + " …[truncated]")


def main() -> int:
    print(f"Phase 1 A/B test — WIDER (12 tickers, Bedrock Sonnet 4.6)", flush=True)
    print(f"Tickers ({len(TICKERS)}): {TICKERS}", flush=True)
    print(f"Decision cutoff: FY{DECISION_CUTOFF_FY}", flush=True)
    print(f"BEDROCK_MODEL_ID: {os.environ.get('BEDROCK_MODEL_ID')}\n", flush=True)

    print("[step 1] Loading V1 baselines from backtest_20_it_5250.json …", flush=True)
    v1_map = _load_all_v1_baselines()
    missing = [t for t in TICKERS if t not in v1_map]
    if missing:
        print(f"  MISSING baselines for: {missing}", flush=True)
        return 1
    for code in TICKERS:
        print(f"  {code}: {len(v1_map[code])} decision pair baselines", flush=True)

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

    # --- step 3: compare ---
    print("\n" + "=" * 88, flush=True)
    print("COMPARISON — Phase 1 (new) vs V1 (backtest_20 baselines) on decision pairs",
          flush=True)
    print("=" * 88, flush=True)
    print(
        f"\n  {'ticker':>6s}  {'pair':>16s}  {'V1':>16s}  {'NEW':>16s}  "
        f"{'match':>5s}  cites_traj  cites_cf  cfo_flag",
        flush=True,
    )
    print(
        f"  {'-'*6}  {'-'*16}  {'-'*16}  {'-'*16}  {'-'*5}  {'-'*10}  {'-'*8}  {'-'*8}",
        flush=True,
    )

    TRAJ_TOKENS = (
        "trajectory", "multi-year", "multiple years", "prior years", "expansion",
        "compression", "sustained", "bouncy", "3-year", "5-year",
        "year-over-year trend", "trend has",
    )
    CF_TOKENS = (
        "cash flow", "cash-flow", "operating cash", "free cash", "FCF",
        "CFO", "CFO/NI", "earnings quality", "earnings-quality",
        "capex", "capital expenditure",
    )

    total = 0
    matches = 0
    growth_likely_to_uncertain = 0
    growth_likely_to_unlikely = 0
    other_flips = 0
    mismatches = []
    cites_traj_count = 0
    cites_cf_count = 0
    cfo_flag_count = 0
    full_pairs: list[dict] = []

    for code in TICKERS:
        v1_pairs_map = v1_map.get(code, {})
        new_pairs = _decision_pairs(new.get(code, {}))
        new_pairs_map = {
            f"FY{p['prev_fiscal_year']}->FY{p['curr_fiscal_year']}": p
            for p in new_pairs
        }
        for pair_label in sorted(set(v1_pairs_map) | set(new_pairs_map)):
            v1j = v1_pairs_map.get(pair_label, "<missing>")
            np_ = new_pairs_map.get(pair_label, {})
            nj = np_.get("outlook_judgment", "<missing>")
            ok = v1j == nj

            expl_new = (np_.get("explanation_advanced_en") or "") + " " + \
                       (np_.get("outlook_reason_en") or "")
            l = expl_new.lower()
            cites_traj = any(t.lower() in l for t in TRAJ_TOKENS)
            cites_cf = any(t.lower() in l for t in CF_TOKENS)
            cfo_flag = bool((np_.get("cfo_quality_flag") or {}).get("flagged"))
            if cites_traj: cites_traj_count += 1
            if cites_cf: cites_cf_count += 1
            if cfo_flag: cfo_flag_count += 1

            print(
                f"  {code:>6s}  {pair_label:>16s}  {v1j:>16s}  {nj:>16s}  "
                f"{'YES' if ok else 'NO ':>5s}  {'YES' if cites_traj else '.  ':>10s}  "
                f"{'YES' if cites_cf else '.  ':>8s}  {'YES' if cfo_flag else '.  ':>8s}",
                flush=True,
            )
            total += 1
            if ok:
                matches += 1
            else:
                mismatches.append((code, pair_label, v1j, nj))
                if v1j == "growth_likely" and nj == "uncertain":
                    growth_likely_to_uncertain += 1
                elif v1j == "growth_likely" and nj == "growth_unlikely":
                    growth_likely_to_unlikely += 1
                else:
                    other_flips += 1

            full_pairs.append({
                "ticker": code, "pair": pair_label, "match": ok,
                "v1_judgment": v1j,
                "new": {
                    "outlook_judgment":  nj,
                    "outlook_reason_en": _truncate(np_.get("outlook_reason_en")),
                    "outlook_reason_ja": _truncate(np_.get("outlook_reason_ja")),
                    "explanation_en":    _truncate(np_.get("explanation_advanced_en")),
                    "explanation_ja":    _truncate(np_.get("explanation_advanced_ja")),
                    "narrative_coverage_warnings":
                        [w.get("rule") for w in np_.get("narrative_coverage_warnings", [])],
                    "cites_trajectory":  cites_traj,
                    "cites_cashflow":    cites_cf,
                    "cfo_quality_flag":  np_.get("cfo_quality_flag"),
                },
            })

    pct = matches / total * 100 if total else 0
    print(f"\n  Result: {matches}/{total} pairs match ({pct:.1f}%)", flush=True)
    if mismatches:
        print(f"\n  MISMATCHES:", flush=True)
        for code, pair, v1j, nj in mismatches:
            print(f"    {code} {pair}: V1={v1j} → NEW={nj}", flush=True)
    print(
        f"\n  growth_likely → uncertain flips:        {growth_likely_to_uncertain}/{total} "
        f"({growth_likely_to_uncertain/total*100:.0f}%)",
        flush=True,
    )
    print(f"  growth_likely → growth_unlikely flips:  {growth_likely_to_unlikely}", flush=True)
    print(f"  Other flips:                            {other_flips}", flush=True)
    print(f"  Explanations citing trajectory: {cites_traj_count}/{total}", flush=True)
    print(f"  Explanations citing cash flow:  {cites_cf_count}/{total}", flush=True)
    print(f"  CFO/NI low-quality flag fires:  {cfo_flag_count}/{total}", flush=True)

    gli_pct = growth_likely_to_uncertain / total * 100 if total else 0
    if pct >= 85 and gli_pct <= 15 and cites_cf_count + cites_traj_count >= total * 0.5:
        verdict = "PICTURE A — clean win. Ship Phase 1, proceed to Phase 2."
    elif pct >= 85 and (cites_cf_count + cites_traj_count) < total * 0.2:
        verdict = "PICTURE B — match rate fine but data ignored. Strengthen block usage guidance."
    elif pct < 80 or gli_pct >= 25:
        verdict = "PICTURE C — unexpected flips. Investigate before shipping."
    else:
        verdict = "MIXED — partial win, inspect mismatches manually before next step."
    print(f"\n  Verdict: {verdict}", flush=True)

    out_path = ROOT / "outputs" / "phase1_ab_test_12.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "decision_cutoff_fy": DECISION_CUTOFF_FY,
        "matches": matches, "total_pairs": total, "match_pct": pct,
        "growth_likely_to_uncertain": growth_likely_to_uncertain,
        "growth_likely_to_unlikely":  growth_likely_to_unlikely,
        "other_flips":                other_flips,
        "cites_trajectory_count":     cites_traj_count,
        "cites_cashflow_count":       cites_cf_count,
        "cfo_flag_count":             cfo_flag_count,
        "verdict": verdict,
        "mismatches": [{"code": c, "pair": p, "v1": v, "new": n}
                       for c, p, v, n in mismatches],
        "pairs_full": full_pairs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
