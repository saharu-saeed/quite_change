"""Systematic misjudgment pattern extraction.

Goal: for every LLM miss under the multi-axis outcome metric, extract:
  - All indicator values at prediction time
  - LLM verdict and reasoning excerpt
  - Outcome breakdown (rev, op, stock, adverse event)
  - V1 code scorer verdict (for comparison)
  - Pattern category — which rule could have caught it

Then count patterns and identify the dominant noise sources.

This directly addresses the PM's directive:
  「利益が下がっているのに他指標がプラスでLLMがプラスと誤判定する」
  ケースを潰し、かつ4指標以外で見るべき変数がないかを洗う。
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
ALL_JGAAP = set(JGAAP_ORIG + JGAAP_OOS + JGAAP_EXT)


def _f(v):
    if v is None: return None
    try: return float(v)
    except: return None


def annual_val(items, key, fy):
    matches = [i for i in items if i["line_item_key"]==key and i["fiscal_year"]==fy
               and i.get("fiscal_quarter") is None and i.get("accounting_standard")=="Japan GAAP"]
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
    cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                       f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not cache_files: return None
    with open(cache_files[-1], encoding="utf-8") as f:
        d = json.load(f)
    out = {k: None for k in [
        "peer_gap","op_margin_level","goodwill","cfo_ni","op_margin_trend_pp",
        "rev_yoy_pred","top_segment_share","op_profit_yoy_pred",
        "op_profit_yoy_outcome","llm_reason_en","llm_reason_ja",
        "stock_response_anomaly", "stock_response_class",
    ]}
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
            out["op_margin_trend_pp"] = pc_my.get("op_margin_pp_delta")
            bs_hist = pair.get("bs_quality_history") or []
            if bs_hist:
                out["goodwill"] = bs_hist[-1].get("goodwill_to_equity_pct")
                out["top_segment_share"] = bs_hist[-1].get("top_segment_share_pct")
            cfo_r = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
            out["cfo_ni"] = cfo_r.get("curr")
            out["op_profit_yoy_pred"] = pair.get("op_profit_delta_pct")
            out["rev_yoy_pred"] = pair.get("revenue_delta_pct") or pc_my.get("revenue_yoy_pct")
            out["llm_reason_en"] = pair.get("outlook_reason_en", "")[:400]
            out["llm_reason_ja"] = pair.get("outlook_reason_ja", "")
            out["stock_response_anomaly"] = pair.get("stock_response_anomaly")
            out["stock_response_class"] = pair.get("stock_response_class")
        if outcome_fy is not None and pair.get("curr_fiscal_year") == outcome_fy:
            out["op_profit_yoy_outcome"] = pair.get("op_profit_delta_pct")
    return out


def categorize_growth_likely_miss(r):
    """For LLM growth_likely misses: what pattern could have caught it?
    Returns list of patterns that match (could be multiple)."""
    patterns = []
    if r.get("cfo_ni") is not None and r["cfo_ni"] < 0.5:
        patterns.append("EQ_DIVERGENCE")  # earnings quality (Mercari pattern)
    if r.get("op_margin_trend_pp") is not None and r["op_margin_trend_pp"] < -1.0:
        patterns.append("MARGIN_DECLINING")
    if r.get("peer_gap") is not None and r["peer_gap"] < -3.0:
        patterns.append("BELOW_PEER")
    if r.get("top_segment_share") is not None and r["top_segment_share"] > 80.0:
        patterns.append("CONCENTRATED")
    if r.get("goodwill") is not None and r["goodwill"] > 30.0:
        patterns.append("HIGH_GOODWILL")
    if r.get("rev_yoy_pred") is not None and r["rev_yoy_pred"] < 0:
        patterns.append("REVENUE_DECLINING")
    if r.get("op_profit_yoy_pred") is not None and r["op_profit_yoy_pred"] < -10.0:
        patterns.append("PROFIT_CRASHING")
    if r.get("has_adverse_event"):
        patterns.append("ADVERSE_EVENT_AFTER")
    if r.get("stock_5d_outcome") is not None and r["stock_5d_outcome"] < -10.0:
        patterns.append("STOCK_CRATERED")
    if not patterns:
        patterns.append("UNCAUGHT")
    return patterns


def categorize_growth_unlikely_miss(r):
    """For LLM growth_unlikely misses: what was actually strong?"""
    patterns = []
    if r.get("op_margin_level") is not None and r["op_margin_level"] > 15.0:
        patterns.append("MISSED_HIGH_MARGIN")
    if r.get("op_profit_yoy_outcome") is not None and r["op_profit_yoy_outcome"] > 20.0:
        patterns.append("ACTUALLY_GREW_PROFIT")
    if r.get("rev_yoy_outcome") is not None and r["rev_yoy_outcome"] > 15.0:
        patterns.append("ACTUALLY_GREW_REVENUE")
    if r.get("peer_gap") is not None and r["peer_gap"] > 10.0:
        patterns.append("MISSED_PEER_LEADER")
    if not patterns:
        patterns.append("OVERLY_PESSIMISTIC")
    return patterns


def main():
    print("Systematic misjudgment pattern analysis\n", flush=True)

    event_reg = defaultdict(list)
    for tk in ALL_JGAAP:
        for ev in detect_events(tk):
            event_reg[(ev[0], ev[1])].append(ev[2])

    all_preds = []
    for path in [ROOT/"outputs"/"rolling_window_backtest.json",
                 ROOT/"outputs"/"out_of_sample_rolling_window.json",
                 ROOT/"outputs"/"jgaap_extension_rolling_window.json"]:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        all_preds.extend(d["scored_predictions"])

    enriched = []
    for p in all_preds:
        tk = p["ticker"]
        if tk not in ALL_JGAAP: continue
        if p["judgment"] == "uncertain": continue
        try: outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except: outcome_fy = None
        ind = extract_indicators(tk, p["prediction_pair"], outcome_fy)
        if ind is None: continue
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
        outcome = multi_axis_outcome(p.get("rev_delta_pct"), ind["op_profit_yoy_outcome"],
                                     p.get("stock_5d_pct"), bool(evs_2y))
        verdict = score_pred(p["judgment"], outcome)
        enriched.append({
            "ticker": tk, "prediction_pair": p["prediction_pair"],
            "outcome_pair": p["outcome_pair"],
            "llm_verdict": p["judgment"],
            "outcome": outcome,
            "verdict_label": verdict,
            "rev_yoy_outcome": p.get("rev_delta_pct"),
            "stock_5d_outcome": p.get("stock_5d_pct"),
            "has_adverse_event": bool(evs_2y),
            **ind,
        })

    misses_gl = [e for e in enriched if e["llm_verdict"] == "growth_likely" and e["verdict_label"] == "miss"]
    misses_gu = [e for e in enriched if e["llm_verdict"] == "growth_unlikely" and e["verdict_label"] == "miss"]
    hits_gl = [e for e in enriched if e["llm_verdict"] == "growth_likely" and e["verdict_label"] == "hit"]
    hits_gu = [e for e in enriched if e["llm_verdict"] == "growth_unlikely" and e["verdict_label"] == "hit"]

    print(f"Confident calls scored: {len(enriched)}", flush=True)
    print(f"  growth_likely:    {len(hits_gl)} hit / {len(misses_gl)} miss "
          f"= {len(hits_gl)/(len(hits_gl)+len(misses_gl))*100:.1f}% precision", flush=True)
    print(f"  growth_unlikely:  {len(hits_gu)} hit / {len(misses_gu)} miss "
          f"= {len(hits_gu)/(len(hits_gu)+len(misses_gu))*100:.1f}% precision", flush=True)

    # ========================================================================
    # PART A — pattern distribution for growth_likely misses
    # ========================================================================
    print("\n" + "=" * 95, flush=True)
    print(f"PART A — Growth_likely misses ({len(misses_gl)} cases) — pattern distribution", flush=True)
    print("=" * 95, flush=True)
    pattern_counter = Counter()
    for m in misses_gl:
        m["miss_patterns"] = categorize_growth_likely_miss(m)
        for p in m["miss_patterns"]:
            pattern_counter[p] += 1
    print(f"\n{'Pattern':<26}{'Count':<8}{'% of misses':<12}", flush=True)
    print("-" * 46, flush=True)
    pattern_labels = {
        "EQ_DIVERGENCE":        "Earnings-quality div (CFO/NI<0.5)",
        "MARGIN_DECLINING":     "Op margin trend < -1pp",
        "BELOW_PEER":           "Below peer median (<-3pp)",
        "CONCENTRATED":         "Top segment >80% (concentrated)",
        "HIGH_GOODWILL":        "Goodwill/equity > 30%",
        "REVENUE_DECLINING":    "Revenue YoY < 0%",
        "PROFIT_CRASHING":      "Op profit YoY < -10%",
        "ADVERSE_EVENT_AFTER":  "Adverse event in next 2y",
        "STOCK_CRATERED":       "Stock 5d < -10%",
        "UNCAUGHT":             "No rule would have caught",
    }
    for pat, label in pattern_labels.items():
        n = pattern_counter.get(pat, 0)
        pct = n / len(misses_gl) * 100 if misses_gl else 0
        print(f"  {label:<40}{n:<8}{pct:5.1f}%", flush=True)

    # Cross-check: same patterns in HITS — how diagnostic are they really?
    hit_counter = Counter()
    for h in hits_gl:
        h["hit_patterns"] = categorize_growth_likely_miss(h)
        for p in h["hit_patterns"]:
            hit_counter[p] += 1
    print(f"\n{'Pattern':<40}{'Miss-rate when triggered':<30}", flush=True)
    print("(precision PRECISION drop if we used pattern as veto rule)", flush=True)
    print("-" * 70, flush=True)
    for pat, label in pattern_labels.items():
        if pat == "UNCAUGHT": continue
        n_miss = pattern_counter.get(pat, 0)
        n_hit = hit_counter.get(pat, 0)
        total = n_miss + n_hit
        if total == 0: continue
        miss_rate = n_miss / total * 100
        marker = " ★" if miss_rate >= 60 and total >= 4 else ""
        print(f"  {label:<40}{n_miss}/{total} = {miss_rate:.0f}% miss-rate{marker}", flush=True)

    # ========================================================================
    # PART B — print each growth_likely miss with diagnosis
    # ========================================================================
    print("\n" + "=" * 95, flush=True)
    print("PART B — Each growth_likely miss in detail (sorted by ticker)", flush=True)
    print("=" * 95, flush=True)
    for m in sorted(misses_gl, key=lambda x: (x["ticker"], x["prediction_pair"])):
        pats = ",".join(m["miss_patterns"])
        cfo = f"{m['cfo_ni']:.2f}" if m['cfo_ni'] is not None else "n/a"
        peer = f"{m['peer_gap']:+.1f}" if m['peer_gap'] is not None else "n/a"
        margin = f"{m['op_margin_level']:.1f}" if m['op_margin_level'] is not None else "n/a"
        trend = f"{m['op_margin_trend_pp']:+.1f}" if m['op_margin_trend_pp'] is not None else "n/a"
        op_y = f"{m['op_profit_yoy_pred']:+.0f}" if m['op_profit_yoy_pred'] is not None else "n/a"
        rev_y = f"{m['rev_yoy_pred']:+.0f}" if m['rev_yoy_pred'] is not None else "n/a"
        op_yo = f"{m['op_profit_yoy_outcome']:+.0f}" if m['op_profit_yoy_outcome'] is not None else "n/a"
        stk = f"{m['stock_5d_outcome']:+.0f}" if m['stock_5d_outcome'] is not None else "n/a"
        ev = "Y" if m['has_adverse_event'] else "."
        print(f"\n{m['ticker']} {m['prediction_pair']:<22} "
              f"peer={peer}pp marg={margin}% trend={trend}pp cfo={cfo} "
              f"pred_op_yoy={op_y}% pred_rev_yoy={rev_y}%", flush=True)
        print(f"  outcome: rev={m['rev_yoy_outcome']:+.0f}% op={op_yo}% stk={stk}% adv_event={ev} → {m['outcome']}", flush=True)
        print(f"  patterns flagged: [{pats}]", flush=True)
        if m['llm_reason_en']:
            reason = m['llm_reason_en'].replace("\n", " ")
            print(f"  LLM said: {reason[:200]}...", flush=True)

    # ========================================================================
    # PART C — same for growth_unlikely misses
    # ========================================================================
    print("\n" + "=" * 95, flush=True)
    print(f"PART C — Growth_unlikely misses ({len(misses_gu)} cases)", flush=True)
    print("=" * 95, flush=True)
    for m in misses_gu:
        m["miss_patterns"] = categorize_growth_unlikely_miss(m)
    pat_count_gu = Counter()
    for m in misses_gu:
        for p in m["miss_patterns"]:
            pat_count_gu[p] += 1
    print(f"\n{'Pattern':<40}{'Count':<10}", flush=True)
    for p, n in pat_count_gu.most_common():
        print(f"  {p:<40}{n}", flush=True)
    print()
    for m in sorted(misses_gu, key=lambda x: x["ticker"]):
        cfo = f"{m['cfo_ni']:.2f}" if m['cfo_ni'] is not None else "n/a"
        peer = f"{m['peer_gap']:+.1f}" if m['peer_gap'] is not None else "n/a"
        margin = f"{m['op_margin_level']:.1f}" if m['op_margin_level'] is not None else "n/a"
        op_yo = f"{m['op_profit_yoy_outcome']:+.0f}" if m['op_profit_yoy_outcome'] is not None else "n/a"
        rev_yo = f"{m['rev_yoy_outcome']:+.0f}" if m['rev_yoy_outcome'] is not None else "n/a"
        print(f"  {m['ticker']} {m['prediction_pair']:<22} "
              f"peer={peer} marg={margin}% outcome_op_yoy={op_yo}% outcome_rev_yoy={rev_yo}%", flush=True)
        print(f"    patterns: [{','.join(m['miss_patterns'])}]", flush=True)

    # ========================================================================
    # Save full miss dataset
    # ========================================================================
    out_path = ROOT / "outputs" / "misjudgment_analysis_results.json"
    out_path.write_text(json.dumps({
        "n_total_confident": len(enriched),
        "n_growth_likely_misses": len(misses_gl),
        "n_growth_unlikely_misses": len(misses_gu),
        "pattern_counts_gl": dict(pattern_counter),
        "pattern_counts_gu": dict(pat_count_gu),
        "growth_likely_misses": misses_gl,
        "growth_unlikely_misses": misses_gu,
        "growth_likely_hits": hits_gl,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)


if __name__ == "__main__":
    main()
