"""Apply the H1 (semi-annual) overlay to an existing backtest run and
report the comparison.

Reads outputs/backtest_quiet_change_annual.json (produced by
backtest_quiet_change.py --mode annual), pulls each ticker's trend_aware
prediction, applies the bidirectional H1 overlay (Option B per user
2026-05-11), and re-scores against the same actual outcomes already in
the JSON. No new LLM calls — pure post-hoc arithmetic on cached data.

Usage:
    python scripts/score_h1_overlay.py
    python scripts/score_h1_overlay.py --in outputs/backtest_quiet_change_annual.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import apply_h1_overlay   # noqa: E402


def _score(prediction: str, actual: str) -> str:
    if actual == "n/a":
        return "n/a"
    if prediction == "uncertain":
        return "abstain"
    if prediction == "growth_likely" and actual == "growth":
        return "hit"
    if prediction == "growth_unlikely" and actual == "no_growth":
        return "hit"
    return "miss"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="input_path",
                    default="outputs/backtest_quiet_change_annual.json",
                    help="Backtest JSON produced by backtest_quiet_change.py")
    ap.add_argument("--decision-cutoff-fy", type=int, default=2023,
                    help="Same value passed to the original backtest run. "
                         "H1 lookup is capped to FY = cutoff + 1 to avoid "
                         "look-ahead bias.")
    args = ap.parse_args()

    in_path = ROOT / args.input_path
    if not in_path.exists():
        print(f"ERROR: input not found: {in_path}")
        print("Run scripts/backtest_quiet_change.py --mode annual first.")
        return 1
    data = json.loads(in_path.read_text(encoding="utf-8"))
    rows = data.get("rows", [])

    print(f"H1 overlay scoring against {in_path.name}")
    print(f"Decision cutoff FY{args.decision_cutoff_fy} → "
          f"H1 lookup capped at FY{args.decision_cutoff_fy + 1}")
    print()

    # Per-ticker comparison
    headers = ["#", "ticker", "actual", "annual", "→ overlay", "ann_v", "ovl_v", "arm", "rev_h1%", "op_h1%"]
    fmt = "{:>2} {:<7} {:<9} {:<14} {:<14} {:<5} {:<5} {:<13} {:<7} {:<7}"
    print(fmt.format(*headers))
    print("-" * 100)

    overlay_overall = {"hit": 0, "miss": 0, "abstain": 0, "n/a": 0, "errors": 0}
    annual_overall = {"hit": 0, "miss": 0, "abstain": 0, "n/a": 0, "errors": 0}
    overrides = {"turnaround": 0, "deterioration": 0, "none": 0}
    flips = {"hit→miss": 0, "miss→hit": 0, "abstain→hit": 0, "abstain→miss": 0,
             "hit→hit": 0, "miss→miss": 0, "no_change": 0}

    for i, r in enumerate(rows, 1):
        if "error" in r:
            overlay_overall["errors"] += 1
            annual_overall["errors"] += 1
            print(fmt.format(i, r["code"], "ERR", "-", "-", "-", "-", r["error"][:13], "-", "-"))
            continue
        actual = r.get("actual_outcome", "n/a")
        ann = r["by_strategy"]["trend_aware"]["prediction"]
        ann_v = _score(ann, actual)
        annual_overall[ann_v] += 1

        ov = apply_h1_overlay(r["code"], ann,
                              max_h1_fy=args.decision_cutoff_fy + 1)
        final = ov["final_judgment"]
        ov_v = _score(final, actual)
        overlay_overall[ov_v] += 1
        overrides[ov.get("override_arm") or "none"] += 1

        # Flip tracking
        if ann == final:
            if ann_v == ov_v:
                flips["no_change"] += 1
            else:
                flips["no_change"] += 1
        else:
            key = f"{ann_v}→{ov_v}".replace("hit", "hit").replace("miss", "miss").replace("abstain", "abstain")
            flips[key] = flips.get(key, 0) + 1

        ev = ov.get("h1_evidence") or {}
        rev_s = "n/a" if ev.get("revenue_yoy_pct") is None else f"{ev['revenue_yoy_pct']:+.1f}%"
        op_s = "n/a" if ev.get("op_profit_yoy_pct") is None else f"{ev['op_profit_yoy_pct']:+.1f}%"
        arm = ov.get("override_arm") or "—"
        flip_marker = "" if ann == final else f" → {final[:8]}"
        print(fmt.format(
            i, r["code"], actual, ann[:14], (final + flip_marker)[:14] if ann != final else "(no change)",
            ann_v[:5].upper(), ov_v[:5].upper(), arm[:13], rev_s, op_s,
        ))

    print()
    print("=" * 60)
    print("AGGREGATE — TREND_AWARE vs TREND_AWARE + H1 OVERLAY")
    print("=" * 60)

    def _rate(b):
        d = b["hit"] + b["miss"]
        return None if d == 0 else b["hit"] / d

    for label, agg in [("annual only          ", annual_overall),
                       ("annual + H1 overlay  ", overlay_overall)]:
        rate = _rate(agg)
        rate_s = "n/a" if rate is None else f"{rate*100:.1f}%"
        print(f"  {label}: {agg['hit']:>2} hit / {agg['miss']:>2} miss / "
              f"{agg['abstain']:>2} abstain  → hit rate {rate_s}")

    print()
    print("OVERRIDES APPLIED:")
    print(f"  turnaround    (un-filter): {overrides['turnaround']}")
    print(f"  deterioration (re-filter): {overrides['deterioration']}")
    print(f"  no override                : {overrides['none']}")

    print()
    print("FLIP IMPACT (where overlay changed the verdict):")
    for k in ("miss→hit", "abstain→hit", "hit→miss", "abstain→miss"):
        if flips.get(k, 0) > 0:
            print(f"  {k:<14}: {flips[k]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
