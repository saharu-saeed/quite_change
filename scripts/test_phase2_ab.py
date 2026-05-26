"""Phase 2 A/B test — peer comparison + min-peer rule, 12 tickers, Bedrock Sonnet 4.6.

Dual baseline:
  - V1 (from backtest_20_it_5250.json): cumulative effect Phase 1 + Phase 2 vs original
  - Phase 1 (from agent_cache/*_v2_2026-05-15_cashflow.json): incremental Phase 2 effect

Same 12 tickers as the Phase 1 wider test. 11 will get the peer block;
9719 SCSK is unmapped, so its block will SKIP — both paths are exercised.

Budget: ~$0.65 (all 12 need fresh runs; cache version bumped to v3).
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


def _load_phase1_baseline(ticker: str) -> dict | None:
    matches = sorted(_AGENT_CACHE_DIR.glob(
        f"{ticker}_min2020_simp1_cutoff2023_v1_*_v2_2026-05-15_cashflow.json"
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


def _truncate(s: str | None, n: int = 1200) -> str:
    if not s:
        return ""
    s = str(s)
    return s if len(s) <= n else (s[: n - 30] + " …[truncated]")


def _pair_label(p: dict) -> str:
    return f"FY{p['prev_fiscal_year']}->FY{p['curr_fiscal_year']}"


def main() -> int:
    print("Phase 2 A/B test — 12 tickers, Bedrock Sonnet 4.6", flush=True)
    print(f"BEDROCK_MODEL_ID: {os.environ.get('BEDROCK_MODEL_ID')}", flush=True)
    print(f"Tickers ({len(TICKERS)}): {TICKERS}\n", flush=True)

    print("[step 1] Loading baselines…", flush=True)
    v1_map = _load_v1_baselines()
    p1_map: dict[str, dict] = {}
    for code in TICKERS:
        p1 = _load_phase1_baseline(code)
        if p1 is None:
            print(f"  {code}: Phase1 baseline MISSING — skipping incremental compare", flush=True)
        else:
            p1_map[code] = p1
        v1 = v1_map.get(code)
        print(f"  {code}: V1={'ok' if v1 else 'MISSING'}  Phase1={'ok' if code in p1_map else 'MISSING'}", flush=True)

    print("\n[step 2] Running Phase-2 agent fresh via Bedrock…", flush=True)
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

    # --- step 3: dual side-by-side ---
    print("\n" + "=" * 100, flush=True)
    print("COMPARISON — Phase 2 (new) vs V1 (cumulative) and vs Phase 1 (incremental)",
          flush=True)
    print("=" * 100, flush=True)
    print(
        f"\n  {'ticker':>6s}  {'pair':>16s}  {'V1':>14s}  {'Phase1':>14s}  {'Phase2':>14s}  "
        f"{'v1=?':>4s}  {'p1=?':>4s}  cites: peer cf traj  peer_block",
        flush=True,
    )

    PEER_TOKENS = (
        "sector", "peer", "median", "below peers", "above peers",
        "below-median", "above-median", "in line with sector",
        "company-specific", "structural moat",
    )
    CF_TOKENS = (
        "cash flow", "cash-flow", "operating cash", "free cash", "FCF",
        "CFO", "CFO/NI", "earnings quality", "earnings-quality",
        "capex", "capital expenditure",
    )
    TRAJ_TOKENS = (
        "trajectory", "multi-year", "multiple years", "prior years",
        "expansion", "compression", "sustained", "3-year", "5-year",
        "trend has",
    )

    total = 0
    matches_v1 = 0
    matches_p1 = 0
    gli_v1 = 0
    gli_p1 = 0
    p2_only_flips = []
    cites_peer = 0
    cites_cf = 0
    cites_traj = 0
    peer_block_active = 0
    full_pairs: list[dict] = []

    for code in TICKERS:
        v1_pairs_map = v1_map.get(code, {})
        p1_pairs_map = {_pair_label(p): p for p in _decision_pairs(p1_map.get(code, {}))}
        new_pairs_map = {_pair_label(p): p for p in _decision_pairs(new.get(code, {}))}
        for pair_label in sorted(set(v1_pairs_map) | set(p1_pairs_map) | set(new_pairs_map)):
            v1j = v1_pairs_map.get(pair_label, "<missing>")
            p1j = (p1_pairs_map.get(pair_label) or {}).get("outlook_judgment", "<missing>")
            np_ = new_pairs_map.get(pair_label, {})
            nj = np_.get("outlook_judgment", "<missing>")

            expl = (np_.get("explanation_advanced_en") or "") + " " + \
                   (np_.get("outlook_reason_en") or "")
            l = expl.lower()
            cp = any(t.lower() in l for t in PEER_TOKENS)
            cc = any(t.lower() in l for t in CF_TOKENS)
            ct = any(t.lower() in l for t in TRAJ_TOKENS)
            pc = np_.get("peer_comparison")
            has_peer_block = bool(pc and pc.get("peer_count_excl_self", 0) >= 5)
            if cp: cites_peer += 1
            if cc: cites_cf += 1
            if ct: cites_traj += 1
            if has_peer_block: peer_block_active += 1

            ok_v1 = (v1j == nj)
            ok_p1 = (p1j == nj)
            if ok_v1: matches_v1 += 1
            if ok_p1: matches_p1 += 1
            if not ok_v1 and v1j == "growth_likely" and nj == "uncertain":
                gli_v1 += 1
            if not ok_p1 and p1j == "growth_likely" and nj == "uncertain":
                gli_p1 += 1
            # P2 changed something P1 hadn't: track for inspection
            if not ok_p1:
                p2_only_flips.append((code, pair_label, p1j, nj))
            total += 1

            print(
                f"  {code:>6s}  {pair_label:>16s}  {v1j:>14s}  {p1j:>14s}  {nj:>14s}  "
                f"{'YES' if ok_v1 else 'NO':>4s}  {'YES' if ok_p1 else 'NO':>4s}  "
                f"  {'Y' if cp else '.'}    {'Y' if cc else '.'}   {'Y' if ct else '.'}    "
                f"{'ACTIVE' if has_peer_block else 'skip'}",
                flush=True,
            )

            full_pairs.append({
                "ticker": code, "pair": pair_label,
                "v1_judgment": v1j, "p1_judgment": p1j, "new_judgment": nj,
                "match_v1": ok_v1, "match_p1": ok_p1,
                "new": {
                    "outlook_reason_en": _truncate(np_.get("outlook_reason_en")),
                    "outlook_reason_ja": _truncate(np_.get("outlook_reason_ja")),
                    "explanation_en":    _truncate(np_.get("explanation_advanced_en")),
                    "explanation_ja":    _truncate(np_.get("explanation_advanced_ja")),
                    "narrative_coverage_warnings":
                        [w.get("rule") for w in np_.get("narrative_coverage_warnings", [])],
                    "cites_peer":        cp,
                    "cites_cashflow":    cc,
                    "cites_trajectory":  ct,
                    "peer_block_active": has_peer_block,
                    "peer_comparison":   pc,
                    "cfo_quality_flag":  np_.get("cfo_quality_flag"),
                },
            })

    pct_v1 = matches_v1 / total * 100 if total else 0
    pct_p1 = matches_p1 / total * 100 if total else 0
    print(f"\n  Match vs V1 (cumulative):  {matches_v1}/{total} ({pct_v1:.1f}%)", flush=True)
    print(f"  Match vs Phase 1 (incr.):  {matches_p1}/{total} ({pct_p1:.1f}%)", flush=True)
    print(f"  growth_likely → uncertain vs V1:      {gli_v1}/{total} ({gli_v1/total*100:.0f}%)", flush=True)
    print(f"  growth_likely → uncertain vs Phase 1: {gli_p1}/{total} ({gli_p1/total*100:.0f}%)", flush=True)
    print(f"\n  Peer block active: {peer_block_active}/{total}", flush=True)
    print(f"  Explanations citing peer/median: {cites_peer}/{total}", flush=True)
    print(f"  Explanations citing cash flow:   {cites_cf}/{total}", flush=True)
    print(f"  Explanations citing trajectory:  {cites_traj}/{total}", flush=True)

    if p2_only_flips:
        print(f"\n  Phase 2 incremental flips (vs Phase 1):", flush=True)
        for c, p, a, b in p2_only_flips:
            print(f"    {c} {p}: Phase1={a} → Phase2={b}", flush=True)
    else:
        print(f"\n  Phase 2 introduced no new flips vs Phase 1.", flush=True)

    # Verdict
    if pct_p1 >= 85 and gli_p1 <= total * 0.15 and cites_peer >= peer_block_active * 0.5:
        verdict = "PICTURE A — Phase 2 ships cleanly. LLM is using peer context."
    elif pct_p1 >= 85 and cites_peer < peer_block_active * 0.2:
        verdict = "PICTURE B — Phase 2 stable but peer data ignored. Strengthen block guidance."
    elif pct_p1 < 80 or gli_p1 > total * 0.25:
        verdict = "PICTURE C — Phase 2 caused regressions. Investigate before shipping."
    else:
        verdict = "MIXED — inspect manually."
    print(f"\n  Verdict: {verdict}", flush=True)

    out_path = ROOT / "outputs" / "phase2_ab_test.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "decision_cutoff_fy": DECISION_CUTOFF_FY,
        "total_pairs": total,
        "matches_v1": matches_v1, "match_pct_v1": pct_v1,
        "matches_p1": matches_p1, "match_pct_p1": pct_p1,
        "growth_likely_to_uncertain_vs_v1": gli_v1,
        "growth_likely_to_uncertain_vs_p1": gli_p1,
        "peer_block_active": peer_block_active,
        "cites_peer_count": cites_peer,
        "cites_cashflow_count": cites_cf,
        "cites_trajectory_count": cites_traj,
        "p2_incremental_flips": [{"code": c, "pair": p, "phase1": a, "phase2": b}
                                 for c, p, a, b in p2_only_flips],
        "verdict": verdict,
        "pairs_full": full_pairs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
