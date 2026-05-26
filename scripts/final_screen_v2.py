"""Final screening pipeline for Quiet Change Agent v2.

Architecture (per the iterative review with external Claude):
  1. UNIVERSE FILTER (Tempest cache):
        rev↑ YoY AND stock ↓ 3-month
        AND scale_category in {TOPIX Small 1/2, Mid400}   (mid-cap floor + ceiling)
        AND no possible stock-split artifact
  2. ATTENTION GATE (attention_score from anomaly + confirmation SerpAPI searches)
  3. SECTOR-RELATIVE DIVERGENCE GATE (peer-median within same sector_33_name)
  4. DUAL: quiet_change candidate requires BOTH (low attention) AND (idiosyncratic)

This script reads the existing calibration JSON (so no extra SerpAPI cost)
and applies gates 1-4 in order, producing the final candidate list +
PM report markdown.

Usage:
    python scripts/final_screen_v2.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change_peers import (  # noqa: E402
    ACCEPTABLE_SCALE_CATEGORIES,
    classify_sector_relative,
    compute_peer_baseline,
    detect_possible_split,
    load_sector_info,
    quiet_change_dual_gate,
)
from app.subagents.quality_screen import (  # noqa: E402
    compute_global_norms,
    compute_quality_metrics,
    compute_sector_norms,
    score_quality,
)

CAL_FILE = ROOT / "outputs" / "quiet_change_v2" / "calibration" / "_calibration_2026-05-22.json"
OUT_DIR = ROOT / "outputs" / "quiet_change_v2" / "final"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    data = json.load(open(CAL_FILE, encoding="utf-8"))
    rows = [r for r in data["rows"] if "error" not in r]

    # Step 1: enrich with sector + scale_category from company.json
    for r in rows:
        info = load_sector_info(r["ticker"])
        r.update(info)

    # Step 2: split-artifact filter
    split_excluded: list[dict] = []
    survivors_after_split: list[dict] = []
    for r in rows:
        split = detect_possible_split(r["ticker"])
        r["split_check"] = split
        if split["possible_split"]:
            split_excluded.append(r)
        else:
            survivors_after_split.append(r)

    # Step 3: scale_category filter (mid-cap band)
    band_excluded: list[dict] = []
    survivors_after_band: list[dict] = []
    for r in survivors_after_split:
        if r.get("scale_category") in ACCEPTABLE_SCALE_CATEGORIES:
            survivors_after_band.append(r)
        else:
            band_excluded.append(r)

    # Step 4: compute peer baseline within the SURVIVING universe (still conditioned
    # on rev↑+stock↓, but at least it's the right scale band — and we flag this
    # in every row's classify_sector_relative output).
    peer_baseline = compute_peer_baseline(survivors_after_band)

    # Step 5: apply sector-relative gate to each survivor
    for r in survivors_after_band:
        r["sector_rel"] = classify_sector_relative(
            r["stock_move_pct"], r.get("sector_33_name"), peer_baseline
        )

    # Step 6: dual gate (attention + divergence)
    for r in survivors_after_band:
        r["dual_gate"] = quiet_change_dual_gate(r["attention_score"], r["sector_rel"])

    # Step 7: quality annotation (scored, not gated — informs desk review)
    # Computed AFTER the universe survives — peer norms here are within the
    # rev↑+stock↓+mid-cap pool, same conditioning caveat as the divergence gate.
    quality_metrics_by_ticker: dict[str, dict] = {}
    for r in survivors_after_band:
        qm = compute_quality_metrics(r["ticker"])
        qm["sector_33_name"] = r.get("sector_33_name")
        qm["scale_category"] = r.get("scale_category")
        quality_metrics_by_ticker[r["ticker"]] = qm

    quality_valid = [qm for qm in quality_metrics_by_ticker.values() if qm.get("data_ok")]
    quality_sector_norms = compute_sector_norms(quality_valid)
    quality_global_norms = compute_global_norms(quality_valid)

    for r in survivors_after_band:
        qm = quality_metrics_by_ticker[r["ticker"]]
        if qm.get("data_ok"):
            qm["quality_score"] = score_quality(qm, quality_sector_norms, quality_global_norms)
        r["quality"] = qm

    # ===== REPORT =====
    print("=" * 80)
    print("QUIET CHANGE AGENT — FINAL SCREENING (v2)")
    print("=" * 80)
    print(f"Universe source: Tempest local cache")
    print(f"Total raw candidates (rev↑+stock↓):    {len(rows)}")
    print(f"After split-artifact exclusion:        {len(survivors_after_split)} "
          f"({len(split_excluded)} excluded)")
    print(f"After scale_category band filter:      {len(survivors_after_band)} "
          f"({len(band_excluded)} excluded)")

    print("\nSplit-flagged tickers (excluded):")
    for r in split_excluded:
        evts = r["split_check"]["events"]
        if evts:
            ex = evts[0]
            print(f"  {r['ticker']:<6} {ex['date']}  {ex['prev_close']:.0f} → {ex['today_close']:.0f}  "
                  f"({ex['delta_pct']:+.1f}%)")
        else:
            print(f"  {r['ticker']}  no events recorded")

    print("\nPeer baselines (CONDITIONED on rev↑+stock↓ — see caveat below):")
    for sector, base in sorted(peer_baseline.items(), key=lambda kv: -kv[1]["n"]):
        flag = "  ⚠ low-confidence" if base["low_confidence"] else ""
        print(f"  {(sector or '?'):<14} n={base['n']:>2}  median_3mo: {base['median_move']:+.2f}%{flag}")

    # Ranking: by dual_gate first, then by sector_relative_pp ascending
    print("\nFinal ranking — all survivors with sector divergence + attention + quality:")
    print(f"{'Ticker':<7} {'Sector':<14} {'Scale':<16} {'Stock3m':<8} {'PeerMed':<8} {'Diverge':<8} {'Attn':<6} {'Qual':<6} {'QuietChange?':<12}")
    print("-" * 120)
    survivors_after_band.sort(key=lambda r: (
        not r["dual_gate"]["quiet_change_candidate"],
        r["sector_rel"].get("sector_relative_pp") or 999,
    ))
    for r in survivors_after_band:
        sec = (r.get("sector_33_name") or "?")[:13]
        sc = (r.get("scale_category") or "?")[:15]
        sr = r["sector_rel"]
        rel = sr.get("sector_relative_pp")
        rel_str = f"{rel:+.2f}" if rel is not None else "n/a"
        med = sr.get("peer_median")
        med_str = f"{med:+.2f}" if med is not None else "n/a"
        q = r.get("quality", {})
        q_score = q.get("quality_score", {}).get("composite_score") if q.get("data_ok") else None
        q_str = f"{q_score:5.1f}" if q_score is not None else "  -  "
        verdict = "YES" if r["dual_gate"]["quiet_change_candidate"] else "no"
        print(
            f"{r['ticker']:<7} {sec:<14} {sc:<16} "
            f"{r['stock_move_pct']:+6.1f}  {med_str:>7}  {rel_str:>7}  "
            f"{r['attention_score']:+5.1f}  {q_str:<6} {verdict:<12}"
        )

    # Quiet-change winners
    winners = [r for r in survivors_after_band if r["dual_gate"]["quiet_change_candidate"]]
    print("\n" + "=" * 80)
    print(f"QUIET-CHANGE CANDIDATES SURVIVING BOTH GATES: {len(winners)}")
    print("=" * 80)
    for r in winners:
        print(f"\n  {r['ticker']}  ({r.get('sector_33_name')}, {r.get('scale_category')})")
        print(f"    Stock 3mo:        {r['stock_move_pct']:+.1f}%")
        print(f"    Sector peer med:  {r['sector_rel']['peer_median']:+.1f}%  (n={r['sector_rel']['peer_n']})")
        print(f"    Divergence:       {r['sector_rel']['sector_relative_pp']:+.1f}pp idiosyncratic")
        print(f"    Attention score:  {r['attention_score']:+.1f}  (ed={r['editorial']} br={r['brokerage']})")
        print(f"    Revenue YoY:      {r['revenue_yoy_pct']:+.1f}%")
        q = r.get("quality") or {}
        if q.get("data_ok"):
            qs = q["quality_score"]
            print(
                f"    Quality score:    {qs['composite_score']:.1f}/100   "
                f"(CAGR3y={q['revenue_cagr_3y']:+.1f}%, OPmar={q['op_margin_latest']:+.1f}%, "
                f"OPtrnd={q['op_margin_trend_pp']:+.1f}pp, ROE={q['roe_latest']:+.1f}%, "
                f"EqRat={q['equity_ratio_latest']:+.1f}%)"
            )

    # Save JSON output
    out = {
        "universe_source": "tempest_local_cache",
        "screened_at": today,
        "stats": {
            "raw_candidates": len(rows),
            "after_split_filter": len(survivors_after_split),
            "after_scale_band": len(survivors_after_band),
            "quiet_change_candidates": len(winners),
        },
        "peer_baseline": peer_baseline,
        "split_excluded": [{"ticker": r["ticker"], "split_check": r["split_check"]} for r in split_excluded],
        "winners": winners,
        "all_band_survivors": survivors_after_band,
        "caveats": [
            "Peer median is CONDITIONED on the rev↑+stock↓ pre-filter — every peer "
            "is already down by construction. The true (unconditioned) sector "
            "baseline is less negative, so divergence values UNDERSTATE real idiosyncrasy.",
            "Stock-split detection uses a 30%-single-day heuristic (no corp-action "
            "field in Tempest's prices.json). Misses 2:3 splits and may false-positive "
            "real crashes.",
            "Tempest cache is heavily IT-biased (~86% 情報・通信業) which limits cross-"
            "sector inference. Broader-sector cache needed for production screening.",
            "Quality score percentiles are computed WITHIN the band survivors (~30) "
            "so 'top-quartile' here means top of the rev↑+stock↓ mid-cap pool, "
            "not top of the broader Japanese market. Re-rank on broad-universe data.",
        ],
    }
    out_path = OUT_DIR / f"_final_screen_{today}.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull output saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
