"""Code-based weighting prototype — addresses PM's main task.

Implements an explicit, traceable code-only verdict scorer using the 4
empirical indicators that emerged from diagnostic analysis. The point is NOT
to replace the LLM yet — it's to make weighting visible and tunable so we
can show Mr. Nakamachi exactly how moving a weight or threshold changes
the result.

4 indicators:
  1. Peer LEVEL gap = op_margin_pct - sector_median_op_margin_pct (current FY)
  2. Operating margin LEVEL = absolute op_margin_pct (current FY)
  3. Goodwill / equity ratio (asymmetric — only negative signal)
  4. CFO / NI ratio
  5. (bonus) Profit-down override — penalises the Q3 antipattern

Each indicator gets an explicit threshold and weight. Score = signed
weighted sum. Verdict = thresholded score. Everything is configurable
in one dict so we can sweep parameters.

No LLM calls. Pure cache analysis. Compares code-only verdict against:
  (a) the existing LLM verdict
  (b) the multi-axis outcome (rev + op profit + stock + adverse event)
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
import copy
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent

JGAAP_ORIG = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697"]
JGAAP_OOS = ["4063","4716","4751","6861"]
JGAAP_EXT = ["3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
             "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"]
ALL_JGAAP = set(JGAAP_ORIG + JGAAP_OOS + JGAAP_EXT)


def _f(v):
    if v is None: return None
    try: return float(v)
    except: return None


def _wilson(hits, n, z=1.96):
    if n == 0: return (None, None)
    p = hits/n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    r = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den
    return (max(0.0,(c-r)*100), min(100.0,(c+r)*100))


def annual_val(items, key, fy, std="Japan GAAP"):
    matches = [i for i in items if i["line_item_key"]==key and i["fiscal_year"]==fy
               and i.get("fiscal_quarter") is None and i.get("accounting_standard")==std]
    if not matches: return None
    return _f(matches[0]["value"])


def detect_events(ticker):
    p = ROOT / "data" / "tempest" / ticker / "financials_line_items.json"
    if not p.exists(): return []
    with open(p, encoding="utf-8") as f:
        items = json.load(f)["data"]
    fys = sorted(set(i["fiscal_year"] for i in items if i.get("fiscal_quarter") is None
                     and i.get("accounting_standard")=="Japan GAAP"))
    events = []
    for fy in fys:
        prev_eq = annual_val(items, "total_equity", fy-1)
        prev_ni = annual_val(items, "profit_loss", fy-1) or annual_val(items, "profit_attributable_to_owners_of_parent", fy-1)
        rev = annual_val(items, "net_sales", fy)
        impair = annual_val(items, "impairment_loss", fy)
        if impair and impair > 0:
            if (prev_eq and prev_eq>0 and impair/prev_eq*100>=1.0) or (prev_ni and abs(prev_ni)>0 and impair/abs(prev_ni)*100>=5.0):
                events.append((ticker, fy, "impairment"))
        extra = annual_val(items, "extraordinary_loss", fy)
        if extra and extra > 0:
            if (rev and rev>0 and extra/rev*100>=5.0) or (prev_ni and abs(prev_ni)>0 and extra/abs(prev_ni)*100>=10.0):
                events.append((ticker, fy, "extraordinary"))
    return events


# ============================================================================
# CONFIG — every weight and threshold lives here, explicit and tunable.
# ============================================================================
DEFAULT_CONFIG = {
    "thresholds": {
        # Indicator 1: peer LEVEL gap (pp above/below sector median op margin)
        "peer_gap_pos": 10.0,
        "peer_gap_neg": -5.0,
        # Indicator 2: absolute op margin level (%)
        "margin_pos": 15.0,
        "margin_neg": 5.0,
        # Indicator 3: goodwill/equity (%) — asymmetric, only negative
        "goodwill_neg": 30.0,
        # Indicator 4: CFO/NI ratio
        "cfo_pos": 0.8,
        "cfo_neg": 0.5,
        # Bonus: profit-down antipattern override
        "profit_crash": -10.0,
        # Verdict thresholds
        "score_pos_threshold": 1.5,
        "score_neg_threshold": -1.0,
    },
    "weights": {
        "peer_gap": 1.0,
        "margin": 1.0,
        "goodwill": 0.5,
        "cfo": 1.0,
        "profit_crash": 1.5,
    },
}


def code_based_verdict(peer_gap_pp, op_margin_level, goodwill_pct, cfo_ni, op_profit_yoy, cfg):
    """Pure-code verdict. Returns dict with verdict, score, signal breakdown."""
    th = cfg["thresholds"]
    w = cfg["weights"]
    signals = {}
    score = 0.0

    # (1) Peer LEVEL gap
    if peer_gap_pp is not None:
        if peer_gap_pp > th["peer_gap_pos"]:
            signals["peer_gap"] = "+"; score += w["peer_gap"]
        elif peer_gap_pp < th["peer_gap_neg"]:
            signals["peer_gap"] = "-"; score -= w["peer_gap"]
        else:
            signals["peer_gap"] = "0"

    # (2) Op margin LEVEL
    if op_margin_level is not None:
        if op_margin_level > th["margin_pos"]:
            signals["margin"] = "+"; score += w["margin"]
        elif op_margin_level < th["margin_neg"]:
            signals["margin"] = "-"; score -= w["margin"]
        else:
            signals["margin"] = "0"

    # (3) Goodwill (asymmetric)
    if goodwill_pct is not None:
        if goodwill_pct > th["goodwill_neg"]:
            signals["goodwill"] = "-"; score -= w["goodwill"]
        else:
            signals["goodwill"] = "0"

    # (4) CFO/NI
    if cfo_ni is not None:
        if cfo_ni > th["cfo_pos"]:
            signals["cfo"] = "+"; score += w["cfo"]
        elif cfo_ni < th["cfo_neg"]:
            signals["cfo"] = "-"; score -= w["cfo"]
        else:
            signals["cfo"] = "0"

    # Bonus: profit-down override (Q3 antipattern)
    if op_profit_yoy is not None and op_profit_yoy < th["profit_crash"]:
        signals["profit_crash"] = "-"; score -= w["profit_crash"]

    if score >= th["score_pos_threshold"]:
        verdict = "growth_likely"
    elif score <= th["score_neg_threshold"]:
        verdict = "growth_unlikely"
    else:
        verdict = "uncertain"

    return {"verdict": verdict, "score": round(score, 2), "signals": signals}


def multi_axis_outcome(rev_yoy, op_yoy, stock_5d, has_bad_event):
    pos = neg = 0
    if rev_yoy is not None:
        if rev_yoy >= 3.0: pos += 1
        elif rev_yoy <= -3.0: neg += 1
    if op_yoy is not None:
        if op_yoy >= 5.0: pos += 1
        elif op_yoy <= -5.0: neg += 1
    if stock_5d is not None:
        if stock_5d >= 5.0: pos += 1
        elif stock_5d <= -5.0: neg += 1
    if has_bad_event: return "negative"
    if neg >= 2: return "negative"
    if pos >= 2: return "positive"
    return "mixed"


def score_pred(judgment, outcome):
    if outcome == "n/a": return "n/a"
    if judgment == "uncertain": return "abstain"
    if judgment == "growth_likely" and outcome == "positive": return "hit"
    if judgment == "growth_unlikely" and outcome == "negative": return "hit"
    return "miss"


def extract_indicators(ticker, pred_pair_label, outcome_fy):
    """Pull all needed values per pair from the agent cache."""
    cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                       f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not cache_files:
        return None
    with open(cache_files[-1], encoding="utf-8") as f:
        d = json.load(f)

    out = {"peer_gap": None, "op_margin_level": None, "goodwill": None,
           "cfo_ni": None, "op_profit_yoy_pred": None,
           "op_profit_yoy_outcome": None}
    for pair in d.get("pairs", []):
        if pair.get("history_only"): continue
        lbl = f"FY{pair['prev_fiscal_year']}->FY{pair['curr_fiscal_year']}"
        if lbl == pred_pair_label:
            pc = pair.get("peer_comparison") or {}
            pc_my = pc.get("my") or {}
            pc_med = pc.get("sector_median") or {}
            if pc_my.get("op_margin_pct") is not None and pc_med.get("op_margin_pct") is not None:
                out["peer_gap"] = pc_my["op_margin_pct"] - pc_med["op_margin_pct"]
            out["op_margin_level"] = pc_my.get("op_margin_pct")
            bs_hist = pair.get("bs_quality_history") or []
            if bs_hist:
                out["goodwill"] = bs_hist[-1].get("goodwill_to_equity_pct")
            cfo_r = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
            out["cfo_ni"] = cfo_r.get("curr")
            out["op_profit_yoy_pred"] = pair.get("op_profit_delta_pct")
        if outcome_fy is not None and pair.get("curr_fiscal_year") == outcome_fy:
            out["op_profit_yoy_outcome"] = pair.get("op_profit_delta_pct")
    return out


def precision_block(rows, verdict_col, outcome_col_or_fn=None):
    """Compute hit/miss/precision for a verdict column against scored outcome."""
    h = sum(1 for r in rows if r[verdict_col] == "hit")
    m = sum(1 for r in rows if r[verdict_col] == "miss")
    c = h + m
    prec = h/c*100 if c else None
    ci = _wilson(h, c)
    return {"hit": h, "miss": m, "n_scored": c, "n_total": len(rows),
            "precision_pct": prec, "ci_lo": ci[0], "ci_hi": ci[1]}


def fmt_prec(b):
    if b["precision_pct"] is None: return "n/a"
    return f"{b['precision_pct']:5.1f}% ({b['hit']}/{b['n_scored']}) CI [{b['ci_lo']:.1f}-{b['ci_hi']:.1f}]"


def main():
    print("Code-based weighting prototype — explicit, tunable, traceable\n", flush=True)

    # Build event registry once
    event_reg = defaultdict(list)
    for tk in ALL_JGAAP:
        for ev in detect_events(tk):
            event_reg[(ev[0], ev[1])].append(ev[2])

    # Load all predictions
    all_preds = []
    for path in [ROOT/"outputs"/"rolling_window_backtest.json",
                 ROOT/"outputs"/"out_of_sample_rolling_window.json",
                 ROOT/"outputs"/"jgaap_extension_rolling_window.json"]:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        all_preds.extend(d["scored_predictions"])

    # Enrich every prediction with the 4 indicators + outcome
    enriched = []
    for p in all_preds:
        tk = p["ticker"]
        if tk not in ALL_JGAAP: continue
        try:
            outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except: outcome_fy = None
        ind = extract_indicators(tk, p["prediction_pair"], outcome_fy)
        if ind is None: continue
        # Adverse events
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
        outcome = multi_axis_outcome(p.get("rev_delta_pct"), ind["op_profit_yoy_outcome"],
                                     p.get("stock_5d_pct"), bool(evs_2y))
        enriched.append({
            "ticker": tk,
            "prediction_pair": p["prediction_pair"],
            "outcome_pair": p["outcome_pair"],
            "llm_verdict": p["judgment"],
            "outcome_multi_axis": outcome,
            "has_adverse_event": bool(evs_2y),
            "rev_yoy_outcome": p.get("rev_delta_pct"),
            "stock_5d": p.get("stock_5d_pct"),
            **ind,
        })

    print(f"Total enriched predictions: {len(enriched)} (across {len({e['ticker'] for e in enriched})} tickers)\n",
          flush=True)

    # ========================================================================
    # PART 1: Apply default config — code-based verdict on every prediction
    # ========================================================================
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    for e in enriched:
        cb = code_based_verdict(
            e["peer_gap"], e["op_margin_level"], e["goodwill"],
            e["cfo_ni"], e["op_profit_yoy_pred"], cfg,
        )
        e["code_verdict"] = cb["verdict"]
        e["code_score"] = cb["score"]
        e["code_signals"] = cb["signals"]
        e["llm_v_outcome"] = score_pred(e["llm_verdict"], e["outcome_multi_axis"])
        e["code_v_outcome"] = score_pred(e["code_verdict"], e["outcome_multi_axis"])

    # ========================================================================
    # PART 2: Headline comparison — LLM vs code under SAME outcome metric
    # ========================================================================
    print("=" * 100, flush=True)
    print("PART 1 — LLM verdict vs Code-only verdict, same multi-axis outcome", flush=True)
    print("=" * 100, flush=True)
    print(f"\n{'Class':<22}{'LLM precision':<42}{'Code-only precision':<42}", flush=True)
    print("-" * 106, flush=True)
    for cls in ("growth_likely", "growth_unlikely"):
        llm_rows = [e for e in enriched if e["llm_verdict"] == cls]
        code_rows = [e for e in enriched if e["code_verdict"] == cls]
        llm_b = precision_block(llm_rows, "llm_v_outcome")
        code_b = precision_block(code_rows, "code_v_outcome")
        print(f"{cls:<22}{fmt_prec(llm_b):<42}{fmt_prec(code_b):<42}", flush=True)

    # ========================================================================
    # PART 3: Agreement matrix
    # ========================================================================
    print("\n" + "=" * 100, flush=True)
    print("PART 2 — Agreement matrix (LLM verdict × Code verdict)", flush=True)
    print("=" * 100, flush=True)
    classes = ("growth_likely", "growth_unlikely", "uncertain")
    matrix = {(a, b): 0 for a in classes for b in classes}
    for e in enriched:
        matrix[(e["llm_verdict"], e["code_verdict"])] += 1
    print(f"\n{'':<24}{'Code: growth_likely':<22}{'Code: growth_unlikely':<22}{'Code: uncertain':<18}", flush=True)
    print("-" * 86, flush=True)
    for a in classes:
        row = f"LLM: {a:<18}"
        for b in classes:
            row += f"{matrix[(a,b)]:<22}" if b != "uncertain" else f"{matrix[(a,b)]:<18}"
        print(row, flush=True)

    total = len(enriched)
    agree = sum(matrix[(c,c)] for c in classes)
    print(f"\nAgreement rate: {agree}/{total} = {agree/total*100:.1f}%", flush=True)

    # ========================================================================
    # PART 4: Where they disagree — show the cases
    # ========================================================================
    print("\n" + "=" * 100, flush=True)
    print("PART 3 — Disagreement cases: LLM growth_likely, Code growth_unlikely", flush=True)
    print("=" * 100, flush=True)
    disagree = [e for e in enriched
                if e["llm_verdict"] == "growth_likely" and e["code_verdict"] == "growth_unlikely"]
    print(f"n = {len(disagree)}\n", flush=True)
    for e in disagree[:10]:
        sigs = ",".join(f"{k}{v}" for k, v in (e["code_signals"] or {}).items())
        op_y = e["op_profit_yoy_pred"]
        op_s = f"{op_y:+.1f}%" if op_y is not None else "n/a"
        peer = f"{e['peer_gap']:+.1f}pp" if e['peer_gap'] is not None else "n/a"
        marg = f"{e['op_margin_level']:.1f}%" if e['op_margin_level'] is not None else "n/a"
        gw = f"{e['goodwill']:.0f}%" if e['goodwill'] is not None else "n/a"
        cfo = f"{e['cfo_ni']:.2f}" if e['cfo_ni'] is not None else "n/a"
        print(f"  {e['ticker']:<6} {e['prediction_pair']:<22} "
              f"peer={peer:>8} marg={marg:>6} gw={gw:>5} cfo={cfo:>5} op_yoy={op_s:>8} "
              f"score={e['code_score']:+5.1f} outcome={e['outcome_multi_axis']:<8} "
              f"LLM={e['llm_v_outcome']}", flush=True)

    print("\n" + "=" * 100, flush=True)
    print("PART 3b — Disagreement cases: LLM growth_unlikely, Code growth_likely", flush=True)
    print("=" * 100, flush=True)
    disagree2 = [e for e in enriched
                 if e["llm_verdict"] == "growth_unlikely" and e["code_verdict"] == "growth_likely"]
    print(f"n = {len(disagree2)}\n", flush=True)
    for e in disagree2[:10]:
        op_y = e["op_profit_yoy_pred"]
        op_s = f"{op_y:+.1f}%" if op_y is not None else "n/a"
        peer = f"{e['peer_gap']:+.1f}pp" if e['peer_gap'] is not None else "n/a"
        marg = f"{e['op_margin_level']:.1f}%" if e['op_margin_level'] is not None else "n/a"
        gw = f"{e['goodwill']:.0f}%" if e['goodwill'] is not None else "n/a"
        cfo = f"{e['cfo_ni']:.2f}" if e['cfo_ni'] is not None else "n/a"
        print(f"  {e['ticker']:<6} {e['prediction_pair']:<22} "
              f"peer={peer:>8} marg={marg:>6} gw={gw:>5} cfo={cfo:>5} op_yoy={op_s:>8} "
              f"score={e['code_score']:+5.1f} outcome={e['outcome_multi_axis']:<8} "
              f"LLM={e['llm_v_outcome']}", flush=True)

    # ========================================================================
    # PART 5: Sweep over profit_crash weight — does penalising the
    # Q3 antipattern improve LLM growth_likely precision when used as filter?
    # ========================================================================
    print("\n" + "=" * 100, flush=True)
    print("PART 4 — Hybrid mode: code as guard-rail on LLM growth_likely", flush=True)
    print("=" * 100, flush=True)
    print("Rule: keep LLM growth_likely only if code does NOT vote growth_unlikely.", flush=True)
    print("Sweep over profit_crash weight to show parameter sensitivity.\n", flush=True)

    print(f"{'profit_crash_w':<18}{'kept':<10}{'filtered':<12}{'precision (kept)':<36}", flush=True)
    print("-" * 76, flush=True)
    for w_crash in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0):
        cfg2 = copy.deepcopy(DEFAULT_CONFIG)
        cfg2["weights"]["profit_crash"] = w_crash
        kept = []
        filtered = []
        for e in enriched:
            if e["llm_verdict"] != "growth_likely": continue
            cb = code_based_verdict(e["peer_gap"], e["op_margin_level"], e["goodwill"],
                                    e["cfo_ni"], e["op_profit_yoy_pred"], cfg2)
            if cb["verdict"] == "growth_unlikely":
                filtered.append(e)
            else:
                kept.append(e)
        kb = precision_block(kept, "llm_v_outcome")
        print(f"{w_crash:<18}{len(kept):<10}{len(filtered):<12}{fmt_prec(kb):<36}", flush=True)

    print(f"\nFor reference — baseline (no filter) LLM growth_likely:", flush=True)
    base = [e for e in enriched if e["llm_verdict"] == "growth_likely"]
    base_b = precision_block(base, "llm_v_outcome")
    print(f"  {fmt_prec(base_b)}", flush=True)

    # ========================================================================
    # PART 6: Sweep on growth_unlikely side
    # ========================================================================
    print("\n" + "=" * 100, flush=True)
    print("PART 5 — Hybrid mode: code as guard-rail on LLM growth_unlikely", flush=True)
    print("=" * 100, flush=True)
    print("Rule: keep LLM growth_unlikely only if code does NOT vote growth_likely.", flush=True)
    print("Sweep over score_pos_threshold (how strong does positive evidence need to be to override).\n", flush=True)
    print(f"{'pos_threshold':<18}{'kept':<10}{'filtered':<12}{'precision (kept)':<36}", flush=True)
    print("-" * 76, flush=True)
    for pos_th in (1.0, 1.5, 2.0, 2.5, 3.0, 99.0):
        cfg2 = copy.deepcopy(DEFAULT_CONFIG)
        cfg2["thresholds"]["score_pos_threshold"] = pos_th
        kept = []; filtered = []
        for e in enriched:
            if e["llm_verdict"] != "growth_unlikely": continue
            cb = code_based_verdict(e["peer_gap"], e["op_margin_level"], e["goodwill"],
                                    e["cfo_ni"], e["op_profit_yoy_pred"], cfg2)
            if cb["verdict"] == "growth_likely":
                filtered.append(e)
            else:
                kept.append(e)
        kb = precision_block(kept, "llm_v_outcome")
        print(f"{pos_th:<18}{len(kept):<10}{len(filtered):<12}{fmt_prec(kb):<36}", flush=True)

    print(f"\nFor reference — baseline (no filter) LLM growth_unlikely:", flush=True)
    base = [e for e in enriched if e["llm_verdict"] == "growth_unlikely"]
    base_b = precision_block(base, "llm_v_outcome")
    print(f"  {fmt_prec(base_b)}", flush=True)

    # ========================================================================
    # PART 7: Indicator coverage — how often is each indicator available?
    # ========================================================================
    print("\n" + "=" * 100, flush=True)
    print("PART 6 — Indicator coverage across enriched cohort", flush=True)
    print("=" * 100, flush=True)
    n = len(enriched)
    for ind_name in ("peer_gap", "op_margin_level", "goodwill", "cfo_ni", "op_profit_yoy_pred"):
        present = sum(1 for e in enriched if e[ind_name] is not None)
        print(f"  {ind_name:<24}{present}/{n} = {present/n*100:.0f}%", flush=True)

    # Save full enriched dataset for downstream work
    out_path = ROOT / "outputs" / "code_based_scorer_results.json"
    payload = {
        "config_default": DEFAULT_CONFIG,
        "n_enriched": len(enriched),
        "rows": enriched,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)


if __name__ == "__main__":
    main()
