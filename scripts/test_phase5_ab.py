"""Phase 5 A/B test — qualitative disclosure signals, 12 tickers, Bedrock Sonnet 4.6.

Dual baseline:
  - V1 (from backtest_20_it_5250.json):  cumulative effect of Phase 1+2+5
  - Phase 2 (from agent_cache/*_v3_2026-05-15_peers.json): incremental Phase 5 effect

Same 12 tickers as the Phase 2 A/B for direct comparability. 11 will get
both peer block (Phase 2) and the qualitative-signals block (Phase 5); 9719
SCSK skips the peer block (sector unmapped) but still gets the qualitative
block.

Budget: ~$1.50 (12 fresh runs, cache version bumped to v4 — all 12 are
orphaned vs Phase 5 keys, so all run fresh under the new prompt).
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
    """Phase 2 baseline = cache files from the v3 (peers) version."""
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


def main() -> int:
    print("Phase 5 A/B test — 12 tickers, Bedrock Sonnet 4.6", flush=True)
    print(f"BEDROCK_MODEL_ID: {os.environ.get('BEDROCK_MODEL_ID')}", flush=True)
    print(f"Tickers ({len(TICKERS)}): {TICKERS}\n", flush=True)

    print("[step 1] Loading baselines…", flush=True)
    v1_map = _load_v1_baselines()
    p2_map: dict[str, dict] = {}
    for code in TICKERS:
        p2 = _load_phase2_baseline(code)
        if p2 is None:
            print(f"  {code}: Phase2 baseline MISSING — skipping incremental compare",
                  flush=True)
        else:
            p2_map[code] = p2
        v1 = v1_map.get(code)
        print(f"  {code}: V1={'ok' if v1 else 'MISSING'}  Phase2={'ok' if code in p2_map else 'MISSING'}",
              flush=True)

    print("\n[step 2] Running Phase-5 agent fresh via Bedrock…", flush=True)
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
    print("\n" + "=" * 110, flush=True)
    print("COMPARISON — Phase 5 (new) vs V1 (cumulative) and vs Phase 2 (incremental)",
          flush=True)
    print("=" * 110, flush=True)
    print(
        f"\n  {'ticker':>6s}  {'pair':>16s}  {'V1':>14s}  {'Phase2':>14s}  "
        f"{'Phase5':>14s}  {'v1':>3s}  {'p2':>3s}  cites: risk audit peer cf traj",
        flush=True,
    )

    RISK_TOKENS = (
        "risk factor", "risk-factor", "newly disclosed risk", "new risk",
        "事業等のリスク", "リスクが追加", "risk language", "added a risk",
        "intensified", "added risk", "risk disclosure",
    )
    AUDIT_TOKENS = (
        "auditor", "audit", "key audit matter", "KAM", "監査", "監査法人",
        "重要な監査上", "going concern", "audit opinion",
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
    matches_p2 = 0
    gli_v1 = 0
    gli_p2 = 0
    incremental_flips = []
    cites_risk = 0
    cites_audit = 0
    cites_peer = 0
    cites_cf = 0
    cites_traj = 0
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
            l = expl.lower()
            cr = any(t.lower() in l for t in RISK_TOKENS)
            ca = any(t.lower() in l for t in AUDIT_TOKENS)
            cp = any(t.lower() in l for t in PEER_TOKENS)
            cc = any(t.lower() in l for t in CF_TOKENS)
            ct = any(t.lower() in l for t in TRAJ_TOKENS)
            if cr: cites_risk += 1
            if ca: cites_audit += 1
            if cp: cites_peer += 1
            if cc: cites_cf += 1
            if ct: cites_traj += 1

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

            print(
                f"  {code:>6s}  {pair_label:>16s}  {v1j:>14s}  {p2j:>14s}  "
                f"{nj:>14s}  {'YES' if ok_v1 else 'NO':>3s}  {'YES' if ok_p2 else 'NO':>3s}  "
                f"   {'Y' if cr else '.'}    {'Y' if ca else '.'}     "
                f"{'Y' if cp else '.'}    {'Y' if cc else '.'}   {'Y' if ct else '.'}",
                flush=True,
            )

            qs = np_.get("qualitative_signals") or {}
            full_pairs.append({
                "ticker": code, "pair": pair_label,
                "v1_judgment": v1j, "p2_judgment": p2j, "new_judgment": nj,
                "match_v1": ok_v1, "match_p2": ok_p2,
                "new": {
                    "outlook_reason_en": _truncate(np_.get("outlook_reason_en")),
                    "outlook_reason_ja": _truncate(np_.get("outlook_reason_ja")),
                    "explanation_en":    _truncate(np_.get("explanation_advanced_en")),
                    "explanation_ja":    _truncate(np_.get("explanation_advanced_ja")),
                    "narrative_coverage_warnings":
                        [w.get("rule") for w in np_.get("narrative_coverage_warnings", [])],
                    "cites_risk_factor":   cr,
                    "cites_audit":         ca,
                    "cites_peer":          cp,
                    "cites_cashflow":      cc,
                    "cites_trajectory":    ct,
                    "qualitative_signals_summary": {
                        "prev_has_risk":       qs.get("prev_has_risk"),
                        "curr_has_risk":       qs.get("curr_has_risk"),
                        "prev_has_governance": qs.get("prev_has_governance"),
                        "curr_has_governance": qs.get("curr_has_governance"),
                    },
                },
            })

    pct_v1 = matches_v1 / total * 100 if total else 0
    pct_p2 = matches_p2 / total * 100 if total else 0
    print(f"\n  Match vs V1 (cumulative): {matches_v1}/{total} ({pct_v1:.1f}%)", flush=True)
    print(f"  Match vs Phase 2 (incr.): {matches_p2}/{total} ({pct_p2:.1f}%)", flush=True)
    print(f"  growth_likely → uncertain vs V1:      {gli_v1}/{total} ({gli_v1/total*100:.0f}%)", flush=True)
    print(f"  growth_likely → uncertain vs Phase 2: {gli_p2}/{total} ({gli_p2/total*100:.0f}%)", flush=True)
    print(f"\n  Citation rates (out of {total}):", flush=True)
    print(f"    risk factor:    {cites_risk:>3d}  ({cites_risk/total*100:.0f}%)", flush=True)
    print(f"    audit / KAM:    {cites_audit:>3d}  ({cites_audit/total*100:.0f}%)", flush=True)
    print(f"    peer comp:      {cites_peer:>3d}  ({cites_peer/total*100:.0f}%)", flush=True)
    print(f"    cash flow:      {cites_cf:>3d}  ({cites_cf/total*100:.0f}%)", flush=True)
    print(f"    trajectory:     {cites_traj:>3d}  ({cites_traj/total*100:.0f}%)", flush=True)

    if incremental_flips:
        print(f"\n  Phase 5 incremental flips (vs Phase 2):", flush=True)
        for c, p, a, b in incremental_flips:
            print(f"    {c} {p}: Phase2={a} → Phase5={b}", flush=True)
    else:
        print(f"\n  Phase 5 introduced no new flips vs Phase 2.", flush=True)

    new_signals_cited = cites_risk + cites_audit
    if pct_p2 >= 85 and gli_p2 <= total * 0.15 and new_signals_cited >= total * 0.5:
        verdict = "PICTURE A — Phase 5 ships. Qualitative signals are being used."
    elif pct_p2 >= 90 and new_signals_cited < total * 0.2:
        verdict = "PICTURE B — Phase 5 stable but qualitative data ignored. Strengthen framing rules."
    elif pct_p2 < 80 or gli_p2 > total * 0.25:
        verdict = "PICTURE C — Phase 5 caused regressions. Investigate before shipping."
    else:
        verdict = "MIXED — partial win, inspect mismatches manually."
    print(f"\n  Verdict: {verdict}", flush=True)

    out_path = ROOT / "outputs" / "phase5_ab_test.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "decision_cutoff_fy": DECISION_CUTOFF_FY,
        "total_pairs": total,
        "matches_v1": matches_v1, "match_pct_v1": pct_v1,
        "matches_p2": matches_p2, "match_pct_p2": pct_p2,
        "growth_likely_to_uncertain_vs_v1": gli_v1,
        "growth_likely_to_uncertain_vs_p2": gli_p2,
        "cites_risk_factor_count": cites_risk,
        "cites_audit_count":       cites_audit,
        "cites_peer_count":        cites_peer,
        "cites_cashflow_count":    cites_cf,
        "cites_trajectory_count":  cites_traj,
        "incremental_flips_vs_p2": [{"code": c, "pair": p, "p2": a, "p5": b}
                                    for c, p, a, b in incremental_flips],
        "verdict": verdict,
        "pairs_full": full_pairs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
