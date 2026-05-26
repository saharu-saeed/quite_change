"""Phase 1: Stock-disagreement veto analysis.

Hypothesis: when LLM says growth_likely but `stock_response_anomaly=true`
(market disagreed with bullish reading via weak_response or divergence),
the call is much more likely to be wrong.

Approach: cross-reference agent_cache stock_response_anomaly with the
hit/miss labels in lenient_outcome_results.json. Measure the veto's effect:
  - How many MISSES does it catch? (saved)
  - How many HITS does it kill? (collateral)
  - Net precision and volume change.

Pure post-processing on cached predictions — no LLM calls.
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent

JGAAP_ORIG = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697"]
JGAAP_OOS = ["4063","4716","4751","6861"]
JGAAP_EXT = ["3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
             "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"]
TRAIN_TICKERS = set(JGAAP_ORIG + JGAAP_OOS)
TEST_TICKERS = set(JGAAP_EXT)
ALL_JGAAP = TRAIN_TICKERS | TEST_TICKERS


def _wilson(hits, n, z=1.96):
    if n == 0: return (None, None)
    p = hits/n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    r = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den
    return (max(0.0,(c-r)*100), min(100.0,(c+r)*100))


def load_stock_anomaly_map():
    """Returns: {(ticker, prediction_pair): {'anomaly': bool, 'class': str}}"""
    out = {}
    for tk in ALL_JGAAP:
        # Use the latest cache file (v5 is most recent schema)
        files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                     f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if not files:
            continue
        with open(files[-1], encoding="utf-8") as f:
            data = json.load(f)
        for pair in data.get("pairs", []):
            if pair.get("history_only"):
                continue
            prev_fy = pair.get("prev_fiscal_year")
            curr_fy = pair.get("curr_fiscal_year")
            if prev_fy is None or curr_fy is None:
                continue
            key = (tk, f"FY{prev_fy}->FY{curr_fy}")
            out[key] = {
                "anomaly": pair.get("stock_response_anomaly"),
                "class": pair.get("stock_response_class"),
                "stock_5d": pair.get("stock_5d_return_pct"),
            }
    return out


def main():
    # Load outcome scoring (has hit/miss labels)
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes = json.load(f)["rows"]

    # Load stock anomaly per prediction
    anomaly_map = load_stock_anomaly_map()

    # Join
    rows = []
    missing_anomaly = 0
    for r in outcomes:
        key = (r["ticker"], r["prediction_pair"])
        a = anomaly_map.get(key)
        if a is None:
            missing_anomaly += 1
            continue
        rows.append({
            **r,
            "stock_anomaly": a["anomaly"],
            "stock_class": a["class"],
        })

    print(f"Total outcomes: {len(outcomes)}  joined with anomaly: {len(rows)}  missing: {missing_anomaly}\n")

    # ========================================================================
    # 1. Confusion matrix: anomaly × hit/miss, by verdict class
    # ========================================================================
    print("=" * 90)
    print("CONFUSION: anomaly × hit/miss/abstain, by LLM verdict")
    print("=" * 90)

    for verdict in ("growth_likely", "growth_unlikely"):
        sub = [r for r in rows if r["llm_verdict"] == verdict]
        print(f"\n  LLM = {verdict}  (n={len(sub)})")
        print(f"  {'anomaly':<12}{'HIT':<8}{'MISS':<8}{'abstain':<10}{'total':<8}{'hit-rate':<10}")
        for ano in (True, False, None):
            subsub = [r for r in sub if r["stock_anomaly"] == ano]
            h = sum(1 for r in subsub if r["llm_lenient_score"] == "hit")
            m = sum(1 for r in subsub if r["llm_lenient_score"] == "miss")
            a = sum(1 for r in subsub if r["llm_lenient_score"] == "abstain")
            c = h + m
            rate = f"{h/c*100:.1f}%" if c else "n/a"
            label = "True" if ano is True else ("False" if ano is False else "None")
            print(f"  {label:<12}{h:<8}{m:<8}{a:<10}{len(subsub):<8}{rate}")

    # ========================================================================
    # 2. Veto rule effect: for growth_likely calls
    # ========================================================================
    print("\n" + "=" * 90)
    print("VETO RULE 1 EFFECT: 'GL + stock_anomaly=True → uncertain'")
    print("=" * 90)

    for cohort_name, cohort_set in [
        ("FULL (45 tickers)", ALL_JGAAP),
        ("TRAIN (15 tickers)", TRAIN_TICKERS),
        ("TEST (30 tickers)", TEST_TICKERS),
    ]:
        sub = [r for r in rows if r["ticker"] in cohort_set and r["llm_verdict"] == "growth_likely"]
        n = len(sub)
        # Baseline: all GL calls
        h0 = sum(1 for r in sub if r["llm_lenient_score"] == "hit")
        m0 = sum(1 for r in sub if r["llm_lenient_score"] == "miss")
        c0 = h0 + m0
        p0 = h0/c0*100 if c0 else None
        ci0 = _wilson(h0, c0)
        # After veto: only GL calls without anomaly survive
        survivors = [r for r in sub if r["stock_anomaly"] is False]
        h1 = sum(1 for r in survivors if r["llm_lenient_score"] == "hit")
        m1 = sum(1 for r in survivors if r["llm_lenient_score"] == "miss")
        c1 = h1 + m1
        p1 = h1/c1*100 if c1 else None
        ci1 = _wilson(h1, c1)
        # Killed by veto
        killed = [r for r in sub if r["stock_anomaly"] is True]
        killed_hits = sum(1 for r in killed if r["llm_lenient_score"] == "hit")
        killed_misses = sum(1 for r in killed if r["llm_lenient_score"] == "miss")

        def fmt_ci(ci):
            if ci[0] is None: return ""
            return f" CI[{ci[0]:.1f}-{ci[1]:.1f}]"

        print(f"\n  {cohort_name}  n_GL={n}")
        print(f"    BEFORE veto: {h0:>2}/{c0:<2} hits → {p0:5.1f}%{fmt_ci(ci0) if p0 is not None else ''}")
        print(f"    AFTER  veto: {h1:>2}/{c1:<2} hits → {p1 if p1 is None else f'{p1:5.1f}%'}"
              f"{fmt_ci(ci1) if p1 is not None else ''}   (volume kept: {c1}/{c0} = {c1/c0*100:.0f}%)")
        print(f"    Killed by veto: {len(killed)} calls  ({killed_hits} hits SACRIFICED, {killed_misses} misses CAUGHT)")
        ratio = killed_misses / killed_hits if killed_hits else float('inf')
        print(f"    Sacrifice ratio: {killed_misses}:{killed_hits} (catch:sacrifice) — "
              f"{'GOOD' if killed_misses > killed_hits else 'BAD' if killed_misses < killed_hits else 'WASH'}")

    # ========================================================================
    # 3. List the saved misses and sacrificed hits (FULL cohort)
    # ========================================================================
    print("\n" + "=" * 90)
    print("CASE-LEVEL DETAIL (FULL cohort, GL calls)")
    print("=" * 90)

    sub = [r for r in rows if r["llm_verdict"] == "growth_likely"]
    killed = [r for r in sub if r["stock_anomaly"] is True]

    print(f"\n  Misses CAUGHT by veto (good — these were wrong calls):")
    for r in [x for x in killed if x["llm_lenient_score"] == "miss"]:
        print(f"    {r['ticker']:<6} {r['prediction_pair']:<22} stock_class={r['stock_class']:<14}"
              f"  outcome={r['outcome_lenient']}")

    print(f"\n  Hits KILLED by veto (collateral — these were correct calls we'd block):")
    for r in [x for x in killed if x["llm_lenient_score"] == "hit"]:
        print(f"    {r['ticker']:<6} {r['prediction_pair']:<22} stock_class={r['stock_class']:<14}"
              f"  outcome={r['outcome_lenient']}")

    # ========================================================================
    # 4. Save full rows for further analysis
    # ========================================================================
    out = ROOT / "outputs" / "phase1_stock_anomaly_veto.json"
    out.write_text(json.dumps({
        "rule": "GL + stock_anomaly=True -> uncertain",
        "n_total": len(rows),
        "rows": rows,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()
