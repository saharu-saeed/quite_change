"""Robustness test — Phase A (minimal placeholder).

Pure-fundamental ground-truth metric, contrasted with the current lenient
3-signal blend. Implements the spec's minimal version:
  - Sign-transition on ordinary_income (経常利益) over T -> T+2
  - operating_income divergence cap (cap to NEUTRAL if ordinary up but op down)
  - operating_income fallback for ordinary_income nulls
  - Lenient scoring only (MIXED excluded from precision)
  - NO cash screen, NO sector adjustment, NO adverse event override yet
    (those come in Phase B)

ZERO LLM cost — purely re-scores existing 146 predictions against new metric.

Notation:
  T   = curr_fiscal_year of the prediction_pair (the year the LLM 'saw')
  T+2 = T + 2 (two-year forward window per spec)

If T+2 data is missing in our local cache, case is dropped (per spec).
"""
from __future__ import annotations
import json
import sys
import io
import math
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# Constants from spec
# ============================================================
POS_THRESHOLD = +0.05    # +5% CAGR
NEG_THRESHOLD = -0.05    # -5% CAGR
ABS_FLOOR_JPY = 50_000_000   # ¥50M — near-zero floor
REV_FRACTION_FLOOR = 0.005    # OR 0.5% of net_sales[T]


def _wilson(hits, n, z=1.96):
    if n == 0: return (None, None)
    p = hits/n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    r = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den
    return (max(0.0,(c-r)*100), min(100.0,(c+r)*100))


def _f(v):
    if v is None: return None
    try: return float(v)
    except: return None


def annual_val(items, key, fy):
    """Pull a single annual JGAAP value for a given fiscal year."""
    matches = [i for i in items if i.get("line_item_key") == key
               and i.get("fiscal_year") == fy
               and i.get("fiscal_quarter") is None
               and i.get("accounting_standard") == "Japan GAAP"]
    if not matches: return None
    return _f(matches[0].get("value"))


def load_line_items(ticker: str):
    p = ROOT / "data" / "tempest" / ticker / "financials_line_items.json"
    if not p.exists(): return None
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("data", [])


# ============================================================
# Spec §2 — sign-transition table for one line item
# ============================================================
def sign_transition(base, end, floor) -> tuple[str, dict]:
    """Returns (signal, flags). signal in {POSITIVE, NEGATIVE, NEUTRAL}."""
    flags = {"turnaround": False, "deterioration": False, "both_periods_loss": False,
             "unstable_base": False, "low_confidence": False}
    if base is None or end is None:
        return ("UNKNOWN", flags)

    if base > floor and end > floor:
        cagr = (end / base) ** (1/2) - 1
        if cagr >= POS_THRESHOLD: return ("POSITIVE", flags)
        if cagr <= NEG_THRESHOLD: return ("NEGATIVE", flags)
        return ("NEUTRAL", flags)
    if base <= floor and end > floor:
        flags["turnaround"] = True
        return ("POSITIVE", flags)
    if base > floor and end <= floor:
        flags["deterioration"] = True
        return ("NEGATIVE", flags)
    if base <= 0 and end <= 0:
        flags["both_periods_loss"] = True
        if abs(end) <= 0.70 * abs(base):
            flags["low_confidence"] = True
            return ("POSITIVE", flags)
        if abs(end) >= 1.30 * abs(base):
            return ("NEGATIVE", flags)
        return ("NEUTRAL", flags)
    flags["unstable_base"] = True
    return ("NEUTRAL", flags)


def fundamental_signal_for_case(ticker, T, horizon=2):
    """Compute the pure-fundamental signal for one (ticker, T) prediction
    at the given forward horizon (1 or 2 years).

    Returns dict with: signal, line_item_used, base, end, cagr, horizon, flags
    """
    items = load_line_items(ticker)
    if items is None:
        return {"signal": "DROP", "reason": "no_data_file", "horizon": horizon}

    T_end = T + horizon
    net_sales_T = annual_val(items, "net_sales", T)
    floor = max(ABS_FLOOR_JPY,
                REV_FRACTION_FLOOR * net_sales_T if net_sales_T else ABS_FLOOR_JPY)

    ord_T = annual_val(items, "ordinary_income", T)
    ord_T_end = annual_val(items, "ordinary_income", T_end)
    op_T = annual_val(items, "operating_income", T)
    op_T_end = annual_val(items, "operating_income", T_end)

    line_item = "ordinary_income"
    base, end = ord_T, ord_T_end
    fallback_used = False
    if base is None or end is None:
        if op_T is not None and op_T_end is not None:
            line_item = "operating_income"
            base, end = op_T, op_T_end
            fallback_used = True
        else:
            return {"signal": "DROP", "reason": "missing_endpoints", "horizon": horizon,
                    "missing_T_end_data": end is None and op_T_end is None}

    signal, flags = sign_transition(base, end, floor)
    flags["fallback_used"] = fallback_used
    flags["ordinary_op_divergence"] = False

    # Operating-income divergence cap — only meaningful at horizon=2 typically,
    # but apply at both windows for consistency.
    if line_item == "ordinary_income" and signal == "POSITIVE":
        op_signal, _ = sign_transition(op_T, op_T_end, floor)
        if op_signal == "NEGATIVE":
            flags["ordinary_op_divergence"] = True
            signal = "NEUTRAL"

    # Note: this is geometric mean CAGR; for horizon=1 it's a simple % change
    cagr = (end / base) ** (1/horizon) - 1 if (base and end and base > floor and end > floor) else None

    return {
        "signal": signal,
        "line_item_used": line_item,
        "base": base, "end": end,
        "cagr": cagr,
        "horizon": horizon,
        "floor_used": floor,
        "flags": flags,
        "ord_T": ord_T, "ord_T_end": ord_T_end,
        "op_T": op_T, "op_T_end": op_T_end,
    }


# ============================================================
# Label assembly (Phase A: no cash, no sector, no override)
# ============================================================
def label_from_signal(signal: str) -> str:
    """Phase A simplification: signal directly drives label."""
    if signal == "POSITIVE": return "POSITIVE"
    if signal == "NEGATIVE": return "NEGATIVE"
    if signal == "NEUTRAL": return "MIXED"
    return "DROP"  # UNKNOWN, etc.


def score_prediction(agent_verdict: str, label: str) -> str:
    """Standard lenient scoring."""
    if agent_verdict == "uncertain": return "abstain"
    if agent_verdict == "growth_likely" and label == "POSITIVE": return "hit"
    if agent_verdict == "growth_unlikely" and label == "NEGATIVE": return "hit"
    if label == "MIXED": return "abstain"  # outcome-side abstain
    return "miss"


def score_strict(agent_verdict: str, label: str) -> str:
    """Strict: MIXED counts as miss for confident calls."""
    if agent_verdict == "uncertain": return "abstain"
    if agent_verdict == "growth_likely" and label == "POSITIVE": return "hit"
    if agent_verdict == "growth_unlikely" and label == "NEGATIVE": return "hit"
    return "miss"


def parse_prediction_pair(pair_str: str) -> tuple[int, int]:
    """'FY2021->FY2022' -> (2021, 2022)"""
    parts = pair_str.replace("FY", "").split("->")
    return int(parts[0]), int(parts[1])


# ============================================================
# Main
# ============================================================
def main():
    with open(ROOT / "outputs" / "lenient_outcome_results.json", encoding="utf-8") as f:
        old = json.load(f)["rows"]

    print(f"Loaded {len(old)} existing predictions")
    print(f"Spec: Phase A — sign-transition on ordinary_income, T+2 window, no cash/sector/override\n")

    new_rows = []
    drop_reasons_t2 = Counter()
    drop_reasons_t1 = Counter()
    for r in old:
        prev_fy, curr_fy = parse_prediction_pair(r["prediction_pair"])
        T = curr_fy
        fund_t2 = fundamental_signal_for_case(r["ticker"], T, horizon=2)
        fund_t1 = fundamental_signal_for_case(r["ticker"], T, horizon=1)

        if fund_t2["signal"] == "DROP":
            drop_reasons_t2[fund_t2.get("reason", "unknown")] += 1
        if fund_t1["signal"] == "DROP":
            drop_reasons_t1[fund_t1.get("reason", "unknown")] += 1

        label_t2 = label_from_signal(fund_t2["signal"]) if fund_t2["signal"] != "DROP" else "DROP"
        label_t1 = label_from_signal(fund_t1["signal"]) if fund_t1["signal"] != "DROP" else "DROP"

        agent_verdict = r["llm_verdict"]
        new_rows.append({
            **r,
            "T": T, "T1": T+1, "T2": T+2,
            # T+2 track (other Claude's primary)
            "new_signal_t2": fund_t2["signal"],
            "new_label_t2": label_t2,
            "new_lenient_score_llm_t2": score_prediction(agent_verdict, label_t2) if label_t2 != "DROP" else "dropped",
            "new_strict_score_llm_t2": score_strict(agent_verdict, label_t2) if label_t2 != "DROP" else "dropped",
            "fundamental_detail_t2": fund_t2,
            # T+1 track (supplementary, captures more data)
            "new_signal_t1": fund_t1["signal"],
            "new_label_t1": label_t1,
            "new_lenient_score_llm_t1": score_prediction(agent_verdict, label_t1) if label_t1 != "DROP" else "dropped",
            "new_strict_score_llm_t1": score_strict(agent_verdict, label_t1) if label_t1 != "DROP" else "dropped",
            "fundamental_detail_t1": fund_t1,
        })

    # ============================================================
    # Need post-veto verdicts too. Pull from cache via enrichment.
    # ============================================================
    sys.path.insert(0, str(ROOT))
    from app.subagents.quiet_change import _enrich_pairs_with_confidence
    import copy, glob

    veto_map = {}
    for tk in set(r["ticker"] for r in old):
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
        for pair in result.get("pairs", []):
            if pair.get("history_only"): continue
            prev_fy = pair.get("prev_fiscal_year")
            curr_fy = pair.get("curr_fiscal_year")
            if prev_fy is None or curr_fy is None: continue
            key = (tk, f"FY{prev_fy}->FY{curr_fy}")
            veto_map[key] = pair.get("outlook_judgment")

    # Add post-veto scoring for both horizons
    for r in new_rows:
        key = (r["ticker"], r["prediction_pair"])
        post_veto = veto_map.get(key, r["llm_verdict"])
        r["post_veto_verdict"] = post_veto
        for horizon_tag, label_key in [("t2", "new_label_t2"), ("t1", "new_label_t1")]:
            lbl = r[label_key]
            if lbl == "DROP":
                r[f"new_lenient_score_postveto_{horizon_tag}"] = "dropped"
                r[f"new_strict_score_postveto_{horizon_tag}"] = "dropped"
            else:
                r[f"new_lenient_score_postveto_{horizon_tag}"] = score_prediction(post_veto, lbl)
                r[f"new_strict_score_postveto_{horizon_tag}"] = score_strict(post_veto, lbl)

    # ============================================================
    # Drop tracking + per-horizon scoreboards
    # ============================================================
    usable_t2 = [r for r in new_rows if r["new_label_t2"] != "DROP"]
    usable_t1 = [r for r in new_rows if r["new_label_t1"] != "DROP"]
    print("=" * 110)
    print("DROP TRACKING (per horizon)")
    print("=" * 110)
    print(f"\n  Total predictions: {len(new_rows)}")
    print(f"  T+2 usable: {len(usable_t2)} ({len(usable_t2)/len(old)*100:.0f}%)")
    print(f"  T+1 usable: {len(usable_t1)} ({len(usable_t1)/len(old)*100:.0f}%)")
    print(f"\n  T+2 drop reasons: {dict(drop_reasons_t2)}")
    print(f"  T+1 drop reasons: {dict(drop_reasons_t1)}")

    print("\n" + "=" * 110)
    print("HEADLINE: OLD METRIC vs NEW METRIC (T+1 supplementary)")
    print("=" * 110)
    print("\nT+1 captures more cases (1-year window, larger N) — supplementary track.\n")

    def print_block(label, rows, score_key, verdict_key, old_score_key="llm_lenient_score",
                    old_verdict_key="llm_verdict"):
        print(f"\n  {label}:")
        for cls in ("growth_likely", "growth_unlikely"):
            # NEW metric
            new_sub = [r for r in rows if r[verdict_key] == cls]
            new_h = sum(1 for r in new_sub if r[score_key] == "hit")
            new_m = sum(1 for r in new_sub if r[score_key] == "miss")
            new_n = new_h + new_m
            new_p = new_h/new_n*100 if new_n else None
            new_ci = _wilson(new_h, new_n)

            # OLD metric — same rows but old scoring
            old_h = sum(1 for r in new_sub if r[old_score_key] == "hit")
            old_m = sum(1 for r in new_sub if r[old_score_key] == "miss")
            old_n = old_h + old_m
            old_p = old_h/old_n*100 if old_n else None

            new_str = (f"{new_p:5.1f}% ({new_h}/{new_n}) CI[{new_ci[0]:.0f}-{new_ci[1]:.0f}]"
                       if new_p is not None else "n/a")
            old_str = f"{old_p:5.1f}% ({old_h}/{old_n})" if old_p is not None else "n/a"
            delta = f"{(new_p - old_p):+.1f}pp" if (new_p is not None and old_p is not None) else "n/a"
            print(f"    {cls:<18}  OLD: {old_str:<22}  NEW: {new_str:<28}  Δ={delta}")
        # All confident
        sub_all = [r for r in rows if r[verdict_key] in ("growth_likely", "growth_unlikely")]
        new_h = sum(1 for r in sub_all if r[score_key] == "hit")
        new_m = sum(1 for r in sub_all if r[score_key] == "miss")
        new_n = new_h + new_m
        new_p = new_h/new_n*100 if new_n else None
        new_ci = _wilson(new_h, new_n)
        old_h = sum(1 for r in sub_all if r[old_score_key] == "hit")
        old_m = sum(1 for r in sub_all if r[old_score_key] == "miss")
        old_n = old_h + old_m
        old_p = old_h/old_n*100 if old_n else None
        new_str = (f"{new_p:5.1f}% ({new_h}/{new_n}) CI[{new_ci[0]:.0f}-{new_ci[1]:.0f}]"
                   if new_p is not None else "n/a")
        old_str = f"{old_p:5.1f}% ({old_h}/{old_n})" if old_p is not None else "n/a"
        delta = f"{(new_p - old_p):+.1f}pp" if (new_p is not None and old_p is not None) else "n/a"
        print(f"    {'ALL CONFIDENT':<18}  OLD: {old_str:<22}  NEW: {new_str:<28}  Δ={delta}")
        n_abstain = sum(1 for r in rows if r[verdict_key] == "uncertain")
        print(f"    {'uncertain':<18}  n={n_abstain}")

    # T+1 (larger sample, supplementary)
    print(f"\n>>> T+1 TRACK (1-year forward, n_usable={len(usable_t1)})")
    print_block("  LLM raw (no vetoes)", usable_t1, "new_lenient_score_llm_t1", "llm_verdict",
                old_score_key="llm_lenient_score", old_verdict_key="llm_verdict")
    print_block("  Phase 1 (with vetoes)", usable_t1, "new_lenient_score_postveto_t1", "post_veto_verdict",
                old_score_key="llm_lenient_score", old_verdict_key="post_veto_verdict")

    # T+2 (primary per spec, smaller sample)
    print(f"\n\n>>> T+2 TRACK (2-year forward, n_usable={len(usable_t2)}) — PRIMARY per spec")
    print_block("  LLM raw (no vetoes)", usable_t2, "new_lenient_score_llm_t2", "llm_verdict",
                old_score_key="llm_lenient_score", old_verdict_key="llm_verdict")
    print_block("  Phase 1 (with vetoes)", usable_t2, "new_lenient_score_postveto_t2", "post_veto_verdict",
                old_score_key="llm_lenient_score", old_verdict_key="post_veto_verdict")

    # Disagreement matrix (T+1 sample — larger)
    print("\n" + "=" * 110)
    print("LABEL DISAGREEMENT: OLD outcome vs NEW label (T+1 sample)")
    print("=" * 110)
    print(f"\n  {'':<22}{'NEW:POSITIVE':<16}{'NEW:MIXED':<14}{'NEW:NEGATIVE'}")
    for old_out in ("positive", "mixed", "negative"):
        line = [f"  OLD:{old_out:<18}"]
        for new_lab in ("POSITIVE", "MIXED", "NEGATIVE"):
            n = sum(1 for r in usable_t1 if r["outcome_lenient"] == old_out
                                       and r["new_label_t1"] == new_lab)
            line.append(f"{n:<16}" if new_lab != "NEGATIVE" else f"{n}")
        print("".join(line))

    # Flag summary (T+1)
    print("\n" + "=" * 110)
    print("FLAG TALLY (T+1 usable cases)")
    print("=" * 110)
    flag_counts = Counter()
    for r in usable_t1:
        for fn, fv in r["fundamental_detail_t1"].get("flags", {}).items():
            if fv: flag_counts[fn] += 1
    for fn, n in flag_counts.most_common():
        print(f"  {fn}: {n}")

    out_path = ROOT / "outputs" / "robustness_pure_fundamental_v1.json"
    out_path.write_text(json.dumps({
        "methodology": "Phase A: sign-transition on ordinary_income, T+1 + T+2 tracks, no cash/sector/override",
        "n_input": len(old),
        "n_usable_t1": len(usable_t1),
        "n_usable_t2": len(usable_t2),
        "rows": new_rows,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}")


if __name__ == "__main__":
    main()
