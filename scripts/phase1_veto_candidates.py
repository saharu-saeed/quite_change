"""Phase 1: Test multiple candidate veto rules side-by-side.

Tests rules 2-5 (rule 1 already shown to fail — base rate too high).

For each candidate, computes:
  - misses CAUGHT (good — wrong calls correctly downgraded)
  - hits KILLED (bad — correct calls wrongly downgraded)
  - net precision change on remaining confident GL calls
  - volume kept

Goal: identify which (if any) veto rule has a positive sacrifice ratio
(catches more misses than hits sacrificed). If none, Phase 1 fails and
we move to Phase 2.

Pure post-processing on cached predictions — no LLM calls.
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
from pathlib import Path

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


def extract_pair_features(pair: dict) -> dict:
    """Pull all the indicator features we need for veto rules."""
    pc = pair.get("peer_comparison") or {}
    pc_my = pc.get("my") or {}
    pc_med = pc.get("sector_median") or {}
    my_op = pc_my.get("op_margin_pct")
    med_op = pc_med.get("op_margin_pct")
    peer_gap = (my_op - med_op) if (my_op is not None and med_op is not None) else None

    bs_hist = pair.get("bs_quality_history") or []
    gw = bs_hist[-1].get("goodwill_to_equity_pct") if bs_hist else None

    cf_ratios = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
    cfo_ni = cf_ratios.get("curr")

    return {
        "peer_gap_pp": peer_gap,
        "op_margin_pct": my_op,
        "goodwill_to_equity_pct": gw,
        "cfo_to_ni_curr": cfo_ni,
        "stock_anomaly": pair.get("stock_response_anomaly"),
        "stock_class": pair.get("stock_response_class"),
        "stock_5d_pct": pair.get("stock_5d_return_pct"),
        "op_profit_delta_pct": pair.get("op_profit_delta_pct"),
        "revenue_delta_pct": pair.get("revenue_delta_pct"),
    }


def load_features():
    """{(ticker, pred_pair): feature_dict}"""
    out = {}
    for tk in ALL_JGAAP:
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
            out[key] = extract_pair_features(pair)
    return out


# ---------- Veto rule definitions ----------
def rule2_below_peer(f):
    """GL + peer_gap <= 0 -> veto."""
    g = f.get("peer_gap_pp")
    return g is not None and g <= 0.0

def rule3_divergence_only(f):
    """GL + stock_class == 'divergence' -> veto."""
    return f.get("stock_class") == "divergence"

def rule4_low_cash_quality(f):
    """GL + cfo_ni < 0.5 -> veto."""
    c = f.get("cfo_to_ni_curr")
    return c is not None and c < 0.5

def rule5_below_peer_or_low_cash(f):
    """GL + (peer_gap <= 0 OR cfo_ni < 0.5) -> veto."""
    return rule2_below_peer(f) or rule4_low_cash_quality(f)

def rule6_below_peer_and_low_cash(f):
    """GL + (peer_gap <= 0 AND cfo_ni < 0.5) -> veto (very conservative)."""
    return rule2_below_peer(f) and rule4_low_cash_quality(f)

def rule7_divergence_and_below_peer(f):
    """GL + (stock_class == divergence AND peer_gap <= 0) -> veto."""
    return rule3_divergence_only(f) and rule2_below_peer(f)

def rule8_divergence_or_low_cash(f):
    """GL + (divergence OR low cfo_ni) -> veto."""
    return rule3_divergence_only(f) or rule4_low_cash_quality(f)


CANDIDATES = [
    ("Rule 2", "peer_gap <= 0",                       rule2_below_peer),
    ("Rule 3", "stock_class == divergence",           rule3_divergence_only),
    ("Rule 4", "cfo_ni < 0.5",                        rule4_low_cash_quality),
    ("Rule 5", "peer_gap<=0 OR cfo_ni<0.5",           rule5_below_peer_or_low_cash),
    ("Rule 6", "peer_gap<=0 AND cfo_ni<0.5",          rule6_below_peer_and_low_cash),
    ("Rule 7", "divergence AND peer_gap<=0",          rule7_divergence_and_below_peer),
    ("Rule 8", "divergence OR cfo_ni<0.5",            rule8_divergence_or_low_cash),
]


def main():
    # Load outcomes + features
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes = json.load(f)["rows"]
    features = load_features()

    rows = []
    for r in outcomes:
        key = (r["ticker"], r["prediction_pair"])
        f_ = features.get(key)
        if not f_:
            continue
        rows.append({**r, **f_})

    print(f"n joined rows: {len(rows)}\n")

    # ========================================================================
    # 1. Headline comparison table — FULL cohort, GL calls only
    # ========================================================================
    gl = [r for r in rows if r["llm_verdict"] == "growth_likely"]
    base_h = sum(1 for r in gl if r["llm_lenient_score"] == "hit")
    base_m = sum(1 for r in gl if r["llm_lenient_score"] == "miss")
    base_c = base_h + base_m
    base_p = base_h/base_c*100 if base_c else None
    print("=" * 110)
    print(f"BASELINE (no veto): {base_h}/{base_c} hits = {base_p:.1f}% precision on growth_likely  (n_GL = {len(gl)})")
    print("=" * 110)

    print(f"\n{'Rule':<8}{'Definition':<35}{'killed':<10}{'hits_lost':<12}{'miss_caught':<14}"
          f"{'ratio':<10}{'survivor_prec':<22}{'volume_kept'}")
    print("-" * 110)

    for rule_name, defn, fn in CANDIDATES:
        killed = [r for r in gl if fn(r)]
        survivors = [r for r in gl if not fn(r)]
        killed_hits = sum(1 for r in killed if r["llm_lenient_score"] == "hit")
        killed_misses = sum(1 for r in killed if r["llm_lenient_score"] == "miss")
        surv_h = sum(1 for r in survivors if r["llm_lenient_score"] == "hit")
        surv_m = sum(1 for r in survivors if r["llm_lenient_score"] == "miss")
        surv_c = surv_h + surv_m
        surv_p = surv_h/surv_c*100 if surv_c else None
        surv_ci = _wilson(surv_h, surv_c)
        ratio_str = f"{killed_misses}:{killed_hits}"
        if killed_hits == 0:
            verdict = "PERFECT" if killed_misses > 0 else "—"
        elif killed_misses > killed_hits:
            verdict = "GOOD"
        elif killed_misses == killed_hits:
            verdict = "wash"
        else:
            verdict = "BAD"
        surv_str = f"{surv_p:.1f}% CI[{surv_ci[0]:.0f}-{surv_ci[1]:.0f}]" if surv_p is not None else "n/a"
        vol = f"{surv_c}/{base_c} = {surv_c/base_c*100:.0f}%"
        print(f"{rule_name:<8}{defn:<35}{len(killed):<10}{killed_hits:<12}{killed_misses:<14}"
              f"{ratio_str:<6}{verdict:<6}{surv_str:<22}{vol}")

    # ========================================================================
    # 2. Same on TRAIN and TEST cohorts (to check generalization)
    # ========================================================================
    for cohort_name, cohort_set in [("TRAIN", TRAIN_TICKERS), ("TEST", TEST_TICKERS)]:
        print("\n" + "=" * 110)
        print(f"  {cohort_name} cohort (growth_likely calls only)")
        print("=" * 110)
        gl_c = [r for r in rows if r["ticker"] in cohort_set and r["llm_verdict"] == "growth_likely"]
        bh = sum(1 for r in gl_c if r["llm_lenient_score"] == "hit")
        bm = sum(1 for r in gl_c if r["llm_lenient_score"] == "miss")
        bc = bh + bm
        bp = bh/bc*100 if bc else None
        print(f"\n  Baseline: {bh}/{bc} = {bp:.1f}% (n_GL = {len(gl_c)})")
        print(f"\n  {'Rule':<8}{'killed':<10}{'hits_lost':<12}{'miss_caught':<14}"
              f"{'ratio':<10}{'survivor_prec'}")
        for rule_name, defn, fn in CANDIDATES:
            killed = [r for r in gl_c if fn(r)]
            survivors = [r for r in gl_c if not fn(r)]
            killed_hits = sum(1 for r in killed if r["llm_lenient_score"] == "hit")
            killed_misses = sum(1 for r in killed if r["llm_lenient_score"] == "miss")
            surv_h = sum(1 for r in survivors if r["llm_lenient_score"] == "hit")
            surv_m = sum(1 for r in survivors if r["llm_lenient_score"] == "miss")
            surv_c = surv_h + surv_m
            surv_p = f"{surv_h/surv_c*100:.1f}% ({surv_h}/{surv_c})" if surv_c else "n/a"
            print(f"  {rule_name:<8}{len(killed):<10}{killed_hits:<12}{killed_misses:<14}"
                  f"{killed_misses}:{killed_hits:<6}{surv_p}")

    # ========================================================================
    # 3. Best-rule detail: list which cases it catches and kills
    # ========================================================================
    print("\n" + "=" * 110)
    print("DETAIL — which calls each rule affects (FULL cohort)")
    print("=" * 110)
    for rule_name, defn, fn in CANDIDATES:
        killed = [r for r in gl if fn(r)]
        if not killed:
            continue
        killed_hits = [r for r in killed if r["llm_lenient_score"] == "hit"]
        killed_misses = [r for r in killed if r["llm_lenient_score"] == "miss"]
        if len(killed_misses) <= len(killed_hits):
            continue  # only show rules that look promising
        print(f"\n  >>> {rule_name}: {defn}")
        print(f"      Caught {len(killed_misses)} MISSES (good):")
        for r in killed_misses:
            print(f"        {r['ticker']} {r['prediction_pair']:<22} "
                  f"peer_gap={_fmt(r['peer_gap_pp'])}  cfo_ni={_fmt(r['cfo_to_ni_curr'])}  "
                  f"stock_class={r.get('stock_class', '?'):<14}")
        print(f"      Sacrificed {len(killed_hits)} HITS (bad):")
        for r in killed_hits:
            print(f"        {r['ticker']} {r['prediction_pair']:<22} "
                  f"peer_gap={_fmt(r['peer_gap_pp'])}  cfo_ni={_fmt(r['cfo_to_ni_curr'])}  "
                  f"stock_class={r.get('stock_class', '?'):<14}")

    out = ROOT / "outputs" / "phase1_veto_candidates.json"
    out.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


def _fmt(v):
    return f"{v:+.2f}" if isinstance(v, (int, float)) else "n/a"


if __name__ == "__main__":
    main()
