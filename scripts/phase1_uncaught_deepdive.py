"""Phase 1 deep-dive: find structured signals that differentiate the
UNCAUGHT GL misses (those that survive Rule 5) from the UNCAUGHT GL hits.

If we can find one or two indicators that systematically differ between
miss and hit in the survivor pool, that's our candidate Rule 6.

Loads the full agent_cache, applies Rule 5 in-process, then for surviving
GL calls dumps every reasonable indicator + outcome.
"""
from __future__ import annotations
import json
import sys
import io
import glob
import copy
from pathlib import Path
from statistics import median, mean

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change import _enrich_pairs_with_confidence

JGAAP_ORIG = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697"]
JGAAP_OOS = ["4063","4716","4751","6861"]
JGAAP_EXT = ["3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
             "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"]
TRAIN_TICKERS = set(JGAAP_ORIG + JGAAP_OOS)
TEST_TICKERS = set(JGAAP_EXT)
ALL_JGAAP = TRAIN_TICKERS | TEST_TICKERS


def extract_full_features(pair: dict) -> dict:
    pc = pair.get("peer_comparison") or {}
    pc_my = pc.get("my") or {}
    pc_med = pc.get("sector_median") or {}
    my_op = pc_my.get("op_margin_pct")
    med_op = pc_med.get("op_margin_pct")
    peer_gap = (my_op - med_op) if (my_op is not None and med_op is not None) else None
    my_net = pc_my.get("net_margin_pct")
    med_net = pc_med.get("net_margin_pct")
    net_gap = (my_net - med_net) if (my_net is not None and med_net is not None) else None

    bs_hist = pair.get("bs_quality_history") or []
    latest_bs = bs_hist[-1] if bs_hist else {}
    gw_eq = latest_bs.get("goodwill_to_equity_pct")
    debt_eq = latest_bs.get("debt_to_equity_pct")

    cf_ratios = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
    cfo_ni_curr = cf_ratios.get("curr")
    cfo_ni_prev = cf_ratios.get("prev")

    # Margin trajectory — get latest delta vs sector
    mt = pair.get("margin_trajectory") or []
    op_margin_trend_pp = None
    if len(mt) >= 2:
        latest = mt[-1].get("op_margin_pct")
        prev = mt[-2].get("op_margin_pct")
        if latest is not None and prev is not None:
            op_margin_trend_pp = latest - prev

    # Segment concentration
    segments = pair.get("segments") or []
    top_seg_share = None
    if segments:
        total = sum((s.get("curr") or 0) for s in segments)
        if total > 0:
            top_seg_share = max((s.get("curr") or 0) for s in segments) / total * 100

    return {
        "peer_gap_pp": peer_gap,
        "net_gap_pp": net_gap,
        "op_margin_pct": my_op,
        "op_margin_trend_pp": op_margin_trend_pp,
        "goodwill_to_equity_pct": gw_eq,
        "debt_to_equity_pct": debt_eq,
        "cfo_to_ni_curr": cfo_ni_curr,
        "cfo_to_ni_prev": cfo_ni_prev,
        "top_segment_share": top_seg_share,
        "op_profit_delta_pct": pair.get("op_profit_delta_pct"),
        "revenue_delta_pct": pair.get("revenue_delta_pct"),
        "stock_class": pair.get("stock_response_class"),
    }


def load_all():
    out = {}
    for tk in ALL_JGAAP:
        files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                     f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if not files:
            continue
        with open(files[-1], encoding="utf-8") as f:
            data = json.load(f)
        result = copy.deepcopy(data)
        for pair in result.get("pairs", []):
            for k in ("confidence_label", "confidence_factors",
                      "veto_triggered", "veto_rule", "veto_reason", "original_judgment"):
                pair.pop(k, None)
        _enrich_pairs_with_confidence(result)
        for pair in result.get("pairs", []):
            if pair.get("history_only"):
                continue
            prev_fy = pair.get("prev_fiscal_year")
            curr_fy = pair.get("curr_fiscal_year")
            if prev_fy is None or curr_fy is None:
                continue
            key = (tk, f"FY{prev_fy}->FY{curr_fy}")
            features = extract_full_features(pair)
            features["veto_triggered"] = pair.get("veto_triggered")
            features["pre_veto_judgment"] = pair.get("original_judgment")
            features["post_veto_judgment"] = pair.get("outlook_judgment")
            out[key] = features
    return out


def main():
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        outcomes = json.load(f)["rows"]
    feats = load_all()

    rows = []
    for r in outcomes:
        key = (r["ticker"], r["prediction_pair"])
        f_ = feats.get(key)
        if not f_:
            continue
        rows.append({**r, **f_})

    # Focus: GL calls that SURVIVED the veto (post == growth_likely)
    survivors = [r for r in rows if r["post_veto_judgment"] == "growth_likely"]
    print(f"GL survivors after Rule 5: {len(survivors)}")
    hits = [r for r in survivors if r["llm_lenient_score"] == "hit"]
    misses = [r for r in survivors if r["llm_lenient_score"] == "miss"]
    print(f"  Hits: {len(hits)}   Misses: {len(misses)}\n")

    # ============================================================
    # Side-by-side dump
    # ============================================================
    print("=" * 130)
    print("UNCAUGHT GL MISSES (survived Rule 5 but the company didn't grow)")
    print("=" * 130)
    print(f"  {'Ticker':<7}{'Pair':<20}{'peer_gap':<10}{'op_marg':<9}{'op_trend':<10}{'gw_eq':<9}"
          f"{'cfo_ni':<9}{'top_seg':<9}{'op_yoy':<10}{'rev_yoy':<9}{'split'}")
    for r in sorted(misses, key=lambda x: x["ticker"]):
        split = "train" if r["ticker"] in TRAIN_TICKERS else "test"
        print(f"  {r['ticker']:<7}{r['prediction_pair']:<20}{_fmt(r['peer_gap_pp']):<10}"
              f"{_fmt(r['op_margin_pct']):<9}{_fmt(r['op_margin_trend_pp']):<10}"
              f"{_fmt(r['goodwill_to_equity_pct']):<9}{_fmt(r['cfo_to_ni_curr']):<9}"
              f"{_fmt(r['top_segment_share']):<9}{_fmt(r['op_profit_delta_pct']):<10}"
              f"{_fmt(r['revenue_delta_pct']):<9}{split}")

    print(f"\n  {'Ticker':<7}{'Pair':<20}{'peer_gap':<10}{'op_marg':<9}{'op_trend':<10}{'gw_eq':<9}"
          f"{'cfo_ni':<9}{'top_seg':<9}{'op_yoy':<10}{'rev_yoy':<9}{'split'}")
    print("\n" + "=" * 130)
    print("UNCAUGHT GL HITS (survived Rule 5 AND the company actually grew)")
    print("=" * 130)
    print(f"  {'Ticker':<7}{'Pair':<20}{'peer_gap':<10}{'op_marg':<9}{'op_trend':<10}{'gw_eq':<9}"
          f"{'cfo_ni':<9}{'top_seg':<9}{'op_yoy':<10}{'rev_yoy':<9}{'split'}")
    for r in sorted(hits, key=lambda x: x["ticker"]):
        split = "train" if r["ticker"] in TRAIN_TICKERS else "test"
        print(f"  {r['ticker']:<7}{r['prediction_pair']:<20}{_fmt(r['peer_gap_pp']):<10}"
              f"{_fmt(r['op_margin_pct']):<9}{_fmt(r['op_margin_trend_pp']):<10}"
              f"{_fmt(r['goodwill_to_equity_pct']):<9}{_fmt(r['cfo_to_ni_curr']):<9}"
              f"{_fmt(r['top_segment_share']):<9}{_fmt(r['op_profit_delta_pct']):<10}"
              f"{_fmt(r['revenue_delta_pct']):<9}{split}")

    # ============================================================
    # Compare medians: hits vs misses on each indicator
    # ============================================================
    print("\n" + "=" * 130)
    print("INDICATOR DISTRIBUTIONS — hits vs misses (survivors only)")
    print("=" * 130)
    keys = ["peer_gap_pp", "op_margin_pct", "op_margin_trend_pp", "goodwill_to_equity_pct",
            "cfo_to_ni_curr", "top_segment_share", "op_profit_delta_pct", "revenue_delta_pct"]
    print(f"\n  {'Indicator':<24}{'Hit median':<14}{'Miss median':<14}{'Hit mean':<14}{'Miss mean':<14}{'Hit n':<8}{'Miss n':<8}")
    for k in keys:
        h_vals = [r[k] for r in hits if r[k] is not None]
        m_vals = [r[k] for r in misses if r[k] is not None]
        h_med = f"{median(h_vals):+.2f}" if h_vals else "n/a"
        m_med = f"{median(m_vals):+.2f}" if m_vals else "n/a"
        h_mean = f"{mean(h_vals):+.2f}" if h_vals else "n/a"
        m_mean = f"{mean(m_vals):+.2f}" if m_vals else "n/a"
        print(f"  {k:<24}{h_med:<14}{m_med:<14}{h_mean:<14}{m_mean:<14}{len(h_vals):<8}{len(m_vals):<8}")

    out = ROOT / "outputs" / "phase1_uncaught_deepdive.json"
    out.write_text(json.dumps({
        "uncaught_misses": misses,
        "uncaught_hits": hits,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}")


def _fmt(v):
    return f"{v:+.2f}" if isinstance(v, (int, float)) else "n/a"


if __name__ == "__main__":
    main()
