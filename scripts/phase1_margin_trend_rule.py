"""Final Phase 1 candidate: declining op_margin as a veto.

Compute op_margin_trend_pp = current_pair.my.op_margin - prior_pair.my.op_margin
for each ticker. Test rule "trend < -2pp" on GL survivors of R5/R6/R7.
"""
from __future__ import annotations
import json
import sys
import io
import glob
import copy
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import _enrich_pairs_with_confidence

JGAAP_ORIG = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697"]
JGAAP_OOS = ["4063","4716","4751","6861"]
JGAAP_EXT = ["3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
             "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"]
ALL_JGAAP = set(JGAAP_ORIG + JGAAP_OOS + JGAAP_EXT)


def load_margin_trend():
    """{(ticker, pair_key): {op_margin, trend_pp, post_veto_judgment}}"""
    out = {}
    for tk in ALL_JGAAP:
        files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                     f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if not files: continue
        with open(files[-1], encoding="utf-8") as f:
            data = json.load(f)
        result = copy.deepcopy(data)
        for pair in result.get("pairs", []):
            for k in ("confidence_label", "confidence_factors",
                      "veto_triggered", "veto_rule", "veto_reason", "original_judgment"):
                pair.pop(k, None)
        _enrich_pairs_with_confidence(result)

        # Collect op_margin per pair, sorted by curr_fy
        pairs = []
        for pair in result.get("pairs", []):
            if pair.get("history_only"): continue
            curr_fy = pair.get("curr_fiscal_year")
            if curr_fy is None: continue
            pc = pair.get("peer_comparison") or {}
            my = pc.get("my") or {}
            op_m = my.get("op_margin_pct")
            pairs.append((curr_fy, op_m, pair))
        pairs.sort(key=lambda x: x[0])

        # Compute trend per pair
        prior_op_m = None
        for curr_fy, op_m, pair in pairs:
            trend = (op_m - prior_op_m) if (op_m is not None and prior_op_m is not None) else None
            key = (tk, f"FY{pair.get('prev_fiscal_year')}->FY{curr_fy}")
            out[key] = {
                "op_margin_pct": op_m,
                "op_margin_trend_pp": trend,
                "post_veto_judgment": pair.get("outlook_judgment"),
            }
            prior_op_m = op_m
    return out


def main():
    trend_map = load_margin_trend()

    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes = json.load(f)["rows"]

    rows = []
    for r in outcomes:
        key = (r["ticker"], r["prediction_pair"])
        t = trend_map.get(key)
        if not t: continue
        post = t["post_veto_judgment"]
        outcome = r["outcome_lenient"]
        if post == "uncertain":
            score = "abstain"
        elif post == "growth_likely" and outcome == "positive":
            score = "hit"
        elif post == "growth_unlikely" and outcome == "negative":
            score = "hit"
        else:
            score = "miss"
        rows.append({**r, **t, "post_veto_score": score})

    gl_survivors = [r for r in rows if r["post_veto_judgment"] == "growth_likely"]
    print(f"GL survivors after R5+R6+R7+GU2: {len(gl_survivors)}")

    # Sweep margin_trend thresholds
    print("\n" + "=" * 100)
    print("RULE 8 CANDIDATE: GL + op_margin_trend_pp < X")
    print("=" * 100)
    print(f"\n{'Threshold':<12}{'killed':<10}{'caught_miss':<14}{'killed_hit':<12}{'verdict'}")
    for thresh in [0, -0.5, -1.0, -2.0, -3.0]:
        killed = [r for r in gl_survivors
                  if r.get("op_margin_trend_pp") is not None and r["op_margin_trend_pp"] < thresh]
        h = sum(1 for r in killed if r["post_veto_score"] == "hit")
        m = sum(1 for r in killed if r["post_veto_score"] == "miss")
        verdict = "PERFECT" if h == 0 and m > 0 else "GOOD" if m > h else "wash" if m == h else "BAD" if h > 0 else "—"
        print(f"  trend < {thresh:<6} {len(killed):<10}{m:<14}{h:<12}{verdict}")

    # Show all survivors with their trend
    print(f"\n{'='*100}")
    print(f"GL survivor margin trend dump")
    print(f"{'='*100}")
    print(f"\n  {'Ticker':<7}{'Pair':<22}{'op_margin':<12}{'trend_pp':<12}{'score'}")
    for r in sorted(gl_survivors, key=lambda x: (x["op_margin_trend_pp"] if x["op_margin_trend_pp"] is not None else 0)):
        om = f"{r['op_margin_pct']:+.2f}" if r['op_margin_pct'] is not None else "n/a"
        t = f"{r['op_margin_trend_pp']:+.2f}" if r['op_margin_trend_pp'] is not None else "n/a"
        print(f"  {r['ticker']:<7}{r['prediction_pair']:<22}{om:<12}{t:<12}{r['post_veto_score']}")


if __name__ == "__main__":
    main()
