"""Validation runner for the quality screen.

Scores tickers from:
  - the rev↑+stock↓ universe (42 candidates from the local Tempest cache)
  - the labelled eval set used earlier in v2 development
  - today's two PM-report candidates (4686 Justsystems, 9682 DTS)

What we're validating (per the user's brief):
  - Justsystems should rank in the top quartile — it has ~26% OP margin,
    multi-year revenue growth, and a net-cash balance sheet. If it doesn't
    rank high, the scoring weights or sector-norm logic is broken.
  - DTS should pass the hard floor and rank somewhere reasonable.
  - Names with one-off litigation provisions or declining revenue should
    rank lower without being hard-killed by a single bad year.

Usage:
    python scripts/run_quality_screen.py
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

from app.subagents.quality_screen import quality_screen, QUALITY_METRICS  # noqa: E402
from scripts.universe_screen import screen_universe  # noqa: E402

OUT_DIR = ROOT / "outputs" / "quiet_change_v2" / "quality_screen"

# Labelled eval set from earlier v2 development. Spread across known
# quality levels (the meeting set + Claude's research additions).
EVAL_TICKERS = [
    "7974",  # Nintendo (mega cap; should pass quality easily)
    "7011",  # Mitsubishi Heavy
    "4751",  # CyberAgent (guided-down — recent profitability stress)
    "4661",  # Oriental Land
    "4544",  # H.U. Group (theme-ending — likely fails floor or scores low)
    "4324",  # Dentsu (had a litigation provision — checks one-down-year tolerance)
    "7203",  # Toyota
    "7270",  # Subaru
    "7267",  # Honda
    "2221",  # Iwatsuka Confectionery (small consumer)
    "8253",  # Credit Saison
    "8035",  # Tokyo Electron (semicap)
    "6857",  # Advantest
    "4686",  # Justsystems (today's lead)
    "9682",  # DTS (today's watch)
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    # Universe from cache pre-filter (rev↑+stock↓ survivors)
    uni = screen_universe()
    uni_tickers = [c["ticker"] for c in uni]

    # All tickers to score (universe + eval set, deduped)
    all_tickers = sorted(set(uni_tickers + EVAL_TICKERS))
    universe_set = set(uni_tickers)

    print(f"Quality-screening {len(all_tickers)} tickers:")
    print(f"  Universe (rev↑+stock↓ from cache): {len(uni_tickers)}")
    print(f"  Eval-set additions (not in universe): {len(set(EVAL_TICKERS) - universe_set)}")
    print()

    ranked = quality_screen(all_tickers)

    valid = [r for r in ranked if r.get("data_ok")]
    excluded = [r for r in ranked if not r.get("data_ok")]

    # Distribution of composite scores
    scores = sorted(r["quality_score"]["composite_score"] for r in valid)
    print("=" * 110)
    print(f"COMPOSITE SCORE DISTRIBUTION  (n={len(valid)} valid, {len(excluded)} excluded)")
    print("=" * 110)
    if scores:
        for label, idx in [
            ("min", 0),
            ("p10", int(len(scores) * 0.10)),
            ("p25", int(len(scores) * 0.25)),
            ("median", len(scores) // 2),
            ("p75", int(len(scores) * 0.75)),
            ("p90", int(len(scores) * 0.90)),
            ("max", len(scores) - 1),
        ]:
            print(f"  {label:>8}: {scores[min(idx, len(scores)-1)]:5.1f}")
    print()

    # Ranking table
    print("=" * 130)
    print("QUALITY RANKING (sector-aware percentile composite)")
    print("=" * 130)
    print(
        f"{'Rank':<5} {'Ticker':<7} {'Sector':<14} {'Scale':<14} "
        f"{'CAGR3y%':<8} {'OPmar%':<8} {'OPtrnd':<7} {'EqRat%':<7} {'ROE%':<7} "
        f"{'Score':<6} {'Univ':<5}"
    )
    print("-" * 130)
    for i, r in enumerate(valid, 1):
        sec = (r.get("sector_33_name") or "?")[:13]
        sc = (r.get("scale_category") or "?")[:13]
        in_uni = "yes" if r["ticker"] in universe_set else ""
        eqr = r.get("equity_ratio_latest")
        roe = r.get("roe_latest")
        print(
            f"{i:<5} "
            f"{r['ticker']:<7} "
            f"{sec:<14} "
            f"{sc:<14} "
            f"{r['revenue_cagr_3y']:+6.2f}  "
            f"{r['op_margin_latest']:+6.2f}  "
            f"{r['op_margin_trend_pp']:+6.2f} "
            f"{(eqr if eqr is not None else 0):+5.1f}  "
            f"{(roe if roe is not None else 0):+5.1f}  "
            f"{r['quality_score']['composite_score']:5.1f}  "
            f"{in_uni:<5}"
        )

    if excluded:
        print(f"\nHard-floor excluded ({len(excluded)}):")
        for r in excluded:
            in_eval = " [eval]" if r["ticker"] in EVAL_TICKERS else ""
            in_uni = " [universe]" if r["ticker"] in universe_set else ""
            print(f"  {r['ticker']:<7} {r.get('reason', '?')}{in_eval}{in_uni}")

    # Validation checks
    print("\n" + "=" * 80)
    print("VALIDATION CHECKS")
    print("=" * 80)
    by_ticker = {r["ticker"]: (i + 1, r) for i, r in enumerate(valid)}
    excluded_set = {r["ticker"] for r in excluded}

    expectations = [
        ("4686", "TOP QUARTILE", "Justsystems — ~26% OP margin, net cash, multi-year growth"),
        ("9682", "ANY VALID",    "DTS — steady SIer; should pass floor"),
        ("4544", "LOW or EXCLUDED", "H.U. Group — theme-ending (COVID demand collapsed)"),
        ("4751", "ANY VALID",    "CyberAgent — recent stress but historically profitable"),
        ("4324", "ANY VALID",    "Dentsu — litigation provision; one-down-year tolerance"),
        ("4661", "ANY VALID",    "Oriental Land — forward-outlook concern but historically strong"),
        ("7974", "TOP HALF",     "Nintendo — even in a tough year, business is high-quality"),
    ]
    p75_cutoff = scores[int(len(scores) * 0.75)] if scores else 75.0
    p25_cutoff = scores[int(len(scores) * 0.25)] if scores else 25.0
    median_cutoff = scores[len(scores) // 2] if scores else 50.0
    print(f"  (p25={p25_cutoff:.1f}, median={median_cutoff:.1f}, p75={p75_cutoff:.1f})\n")

    for t, expected, note in expectations:
        if t in excluded_set:
            verdict = "EXCLUDED" if "EXCLUDED" in expected else "UNEXPECTED EXCLUSION"
            reason = next((r["reason"] for r in excluded if r["ticker"] == t), "?")
            print(f"  {t}  {verdict:<22} ({reason})  — {note}")
            continue
        if t not in by_ticker:
            print(f"  {t}  NOT IN CACHE                  — {note}")
            continue
        rank, r = by_ticker[t]
        s = r["quality_score"]["composite_score"]
        if s >= p75_cutoff:
            zone = "top-quartile"
        elif s >= median_cutoff:
            zone = "top-half"
        elif s >= p25_cutoff:
            zone = "bottom-half"
        else:
            zone = "bottom-quartile"
        print(f"  {t}  rank {rank:>2}/{len(valid)}  score={s:5.1f}  ({zone:<16})  — {note}")

    # Save full output
    out_path = OUT_DIR / f"_quality_ranking_{today}.json"
    out_path.write_text(
        json.dumps({"ranked": ranked, "score_distribution": scores}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nFull ranking saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
