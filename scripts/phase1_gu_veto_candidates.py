"""Phase 1b: Test candidate veto rules for growth_unlikely calls.

GU misses are FALSE NEGATIVES — LLM said "won't grow" but company did grow.
Mirror of the GL veto logic, in the opposite direction:
  - High peer dominance → unlikely to be a decliner → downgrade GU to uncertain
  - Strong cash quality → unlikely to be a decliner → downgrade
  - Very high op margin level → resilient business → downgrade

For each rule:
  - misses CAUGHT (good — wrong bearish calls correctly downgraded)
  - hits KILLED (bad — correct bearish calls wrongly downgraded)

Note: GU n is small (~15 calls). CIs will be wide. Direction-of-effect
across TRAIN/TEST matters more than absolute precision.
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
    }


def load_features():
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


# ---------- GU Veto rule candidates ----------
# Logic: GU = "won't grow". A veto fires when something says "actually might grow"
# → downgrade the bearish call to uncertain.

def gu_rule1_strong_peer(f):
    """GU + peer_gap > +10pp -> veto (still beating peers strongly)."""
    g = f.get("peer_gap_pp")
    return g is not None and g > 10.0

def gu_rule2_strong_peer_5(f):
    """GU + peer_gap > +5pp -> veto (more lenient peer threshold)."""
    g = f.get("peer_gap_pp")
    return g is not None and g > 5.0

def gu_rule3_high_margin(f):
    """GU + op_margin > 25% -> veto (very high margin business, resilient)."""
    m = f.get("op_margin_pct")
    return m is not None and m > 25.0

def gu_rule4_high_margin_15(f):
    """GU + op_margin > 15% -> veto."""
    m = f.get("op_margin_pct")
    return m is not None and m > 15.0

def gu_rule5_strong_cash(f):
    """GU + cfo_ni > 1.0 -> veto (strong cash conversion)."""
    c = f.get("cfo_to_ni_curr")
    return c is not None and c > 1.0

def gu_rule6_strong_peer_and_high_margin(f):
    """GU + peer_gap > 5 AND op_margin > 15 -> veto (combined)."""
    return gu_rule2_strong_peer_5(f) and gu_rule4_high_margin_15(f)

def gu_rule7_any_strength(f):
    """GU + (peer_gap>5 OR op_margin>20 OR cfo_ni>1.0) -> veto (broad OR)."""
    g = f.get("peer_gap_pp")
    m = f.get("op_margin_pct")
    c = f.get("cfo_to_ni_curr")
    return ((g is not None and g > 5.0) or
            (m is not None and m > 20.0) or
            (c is not None and c > 1.0))


GU_CANDIDATES = [
    ("GU-1", "peer_gap > +10pp",                gu_rule1_strong_peer),
    ("GU-2", "peer_gap > +5pp",                 gu_rule2_strong_peer_5),
    ("GU-3", "op_margin > 25%",                 gu_rule3_high_margin),
    ("GU-4", "op_margin > 15%",                 gu_rule4_high_margin_15),
    ("GU-5", "cfo_ni > 1.0",                    gu_rule5_strong_cash),
    ("GU-6", "peer_gap>5 AND op_margin>15",     gu_rule6_strong_peer_and_high_margin),
    ("GU-7", "peer_gap>5 OR margin>20 OR cfo>1",gu_rule7_any_strength),
]


def main():
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

    gu = [r for r in rows if r["llm_verdict"] == "growth_unlikely"]
    print(f"n joined rows: {len(rows)}   n_GU: {len(gu)}\n")

    base_h = sum(1 for r in gu if r["llm_lenient_score"] == "hit")
    base_m = sum(1 for r in gu if r["llm_lenient_score"] == "miss")
    base_c = base_h + base_m
    base_p = base_h/base_c*100 if base_c else None
    print("=" * 110)
    print(f"BASELINE GU (no veto): {base_h}/{base_c} hits = {base_p:.1f}% precision  (n_GU = {len(gu)})")
    print("=" * 110)

    print(f"\n{'Rule':<8}{'Definition':<40}{'killed':<10}{'hits_lost':<12}{'miss_caught':<14}"
          f"{'ratio':<10}{'survivor_prec':<22}{'volume_kept'}")
    print("-" * 110)

    for rule_name, defn, fn in GU_CANDIDATES:
        killed = [r for r in gu if fn(r)]
        survivors = [r for r in gu if not fn(r)]
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
        print(f"{rule_name:<8}{defn:<40}{len(killed):<10}{killed_hits:<12}{killed_misses:<14}"
              f"{ratio_str:<6}{verdict:<6}{surv_str:<22}{vol}")

    # ========================================================================
    # Train / Test breakdown
    # ========================================================================
    for cohort_name, cohort_set in [("TRAIN", TRAIN_TICKERS), ("TEST", TEST_TICKERS)]:
        print("\n" + "=" * 110)
        print(f"  {cohort_name} cohort (growth_unlikely calls only)")
        print("=" * 110)
        gu_c = [r for r in rows if r["ticker"] in cohort_set and r["llm_verdict"] == "growth_unlikely"]
        bh = sum(1 for r in gu_c if r["llm_lenient_score"] == "hit")
        bm = sum(1 for r in gu_c if r["llm_lenient_score"] == "miss")
        bc = bh + bm
        bp = bh/bc*100 if bc else None
        bp_str = f"{bp:.1f}%" if bp is not None else "n/a"
        print(f"\n  Baseline: {bh}/{bc} = {bp_str} (n_GU = {len(gu_c)})")
        print(f"\n  {'Rule':<8}{'killed':<10}{'hits_lost':<12}{'miss_caught':<14}"
              f"{'ratio':<10}{'survivor_prec'}")
        for rule_name, defn, fn in GU_CANDIDATES:
            killed = [r for r in gu_c if fn(r)]
            survivors = [r for r in gu_c if not fn(r)]
            killed_hits = sum(1 for r in killed if r["llm_lenient_score"] == "hit")
            killed_misses = sum(1 for r in killed if r["llm_lenient_score"] == "miss")
            surv_h = sum(1 for r in survivors if r["llm_lenient_score"] == "hit")
            surv_m = sum(1 for r in survivors if r["llm_lenient_score"] == "miss")
            surv_c = surv_h + surv_m
            surv_p = f"{surv_h/surv_c*100:.1f}% ({surv_h}/{surv_c})" if surv_c else "n/a"
            print(f"  {rule_name:<8}{len(killed):<10}{killed_hits:<12}{killed_misses:<14}"
                  f"{killed_misses}:{killed_hits:<6}{surv_p}")

    # ========================================================================
    # Detail for promising rules
    # ========================================================================
    print("\n" + "=" * 110)
    print("DETAIL — which GU calls each promising rule affects (FULL cohort)")
    print("=" * 110)
    for rule_name, defn, fn in GU_CANDIDATES:
        killed = [r for r in gu if fn(r)]
        if not killed:
            continue
        killed_hits = [r for r in killed if r["llm_lenient_score"] == "hit"]
        killed_misses = [r for r in killed if r["llm_lenient_score"] == "miss"]
        if len(killed_misses) <= len(killed_hits) and len(killed_misses) == 0:
            continue
        print(f"\n  >>> {rule_name}: {defn}")
        print(f"      Caught {len(killed_misses)} MISSES (good):")
        for r in killed_misses:
            print(f"        {r['ticker']} {r['prediction_pair']:<22} "
                  f"peer_gap={_fmt(r['peer_gap_pp'])}  op_margin={_fmt(r['op_margin_pct'])}  "
                  f"cfo_ni={_fmt(r['cfo_to_ni_curr'])}")
        print(f"      Sacrificed {len(killed_hits)} HITS (bad):")
        for r in killed_hits:
            print(f"        {r['ticker']} {r['prediction_pair']:<22} "
                  f"peer_gap={_fmt(r['peer_gap_pp'])}  op_margin={_fmt(r['op_margin_pct'])}  "
                  f"cfo_ni={_fmt(r['cfo_to_ni_curr'])}")

    # ========================================================================
    # All GU calls — show raw data so we can see distributions
    # ========================================================================
    print("\n" + "=" * 110)
    print("ALL GU calls — raw indicator dump (sorted by hit/miss)")
    print("=" * 110)
    print(f"\n  {'Ticker':<8}{'Pair':<22}{'Split':<8}{'Score':<8}{'peer_gap':<12}"
          f"{'op_margin':<12}{'cfo_ni':<10}{'outcome'}")
    for r in sorted(gu, key=lambda x: (x["llm_lenient_score"], x["ticker"])):
        split = "train" if r["ticker"] in TRAIN_TICKERS else "test"
        print(f"  {r['ticker']:<8}{r['prediction_pair']:<22}{split:<8}{r['llm_lenient_score']:<8}"
              f"{_fmt(r['peer_gap_pp']):<12}{_fmt(r['op_margin_pct']):<12}"
              f"{_fmt(r['cfo_to_ni_curr']):<10}{r['outcome_lenient']}")

    out = ROOT / "outputs" / "phase1_gu_veto_candidates.json"
    out.write_text(json.dumps({"rows": gu}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


def _fmt(v):
    return f"{v:+.2f}" if isinstance(v, (int, float)) else "n/a"


if __name__ == "__main__":
    main()
