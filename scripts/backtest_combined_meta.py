"""Combined meta-analysis: original 20-ticker test set + 15 out-of-sample.

Loads both rolling-window backtests, applies Recipe A v2 (single-axis +
event trigger) and the old noisy methodology to:
  - Original 20 tickers alone
  - Out-of-sample 15 tickers alone
  - Combined ~35 tickers

Reports precision with Wilson 95% CIs at each level so we can see
whether the out-of-sample data tightens or widens our claim.
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
import os
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "outputs" / "agent_cache"

ORIG_PATH = ROOT / "outputs" / "rolling_window_backtest.json"
OOS_PATH = ROOT / "outputs" / "out_of_sample_rolling_window.json"
RECIPE_C_PATH = ROOT / "outputs" / "recipe_c_reduced_results.json"  # JGAAP events for orig
OUT_PATH = ROOT / "outputs" / "combined_meta_results.json"

JGAAP_ORIG = ["3656", "3760", "3923", "4385", "4475", "4477", "4480", "4684", "4768", "9684", "9697"]
JGAAP_OOS = ["4063", "4716", "4751", "6861"]
ALL_JGAAP = JGAAP_ORIG + JGAAP_OOS


def _wilson_ci(hits, n, z=1.96):
    if n == 0:
        return (None, None)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    rad = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, (center - rad) * 100), min(100.0, (center + rad) * 100))


def _load_pair_data(ticker):
    matches = sorted(glob.glob(str(CACHE_DIR / f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not matches:
        return []
    with open(matches[-1], encoding="utf-8") as f:
        d = json.load(f)
    pairs = [p for p in d.get("pairs", []) if not p.get("history_only")]
    pairs.sort(key=lambda p: p.get("curr_period_end", ""))
    return pairs


def _annual_value(items, key, fy):
    """Find annual JGAAP value for a line_item_key at given FY."""
    matches = [i for i in items
               if i["line_item_key"] == key
               and i["fiscal_year"] == fy
               and i.get("fiscal_quarter") is None
               and i.get("accounting_standard") == "Japan GAAP"]
    if not matches:
        return None
    v = matches[0]["value"]
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _detect_events_for_ticker(ticker):
    """Detect Recipe C bad events for one ticker (JGAAP only)."""
    p = ROOT / "data" / "tempest" / ticker / "financials_line_items.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    items = d["data"]
    stds = set(i.get("accounting_standard") for i in items if i.get("accounting_standard"))
    if "Japan GAAP" not in stds:
        return []
    fys = sorted(set(i["fiscal_year"] for i in items
                     if i.get("fiscal_quarter") is None
                     and i.get("accounting_standard") == "Japan GAAP"))
    events = []
    for fy in fys:
        prev_equity = _annual_value(items, "total_equity", fy - 1)
        prev_ni = _annual_value(items, "profit_loss", fy - 1) or \
                  _annual_value(items, "profit_attributable_to_owners_of_parent", fy - 1)
        rev = _annual_value(items, "net_sales", fy)
        impair = _annual_value(items, "impairment_loss", fy)
        if impair is not None and impair > 0:
            if (prev_equity and prev_equity > 0 and impair / prev_equity * 100 >= 1.0) or \
               (prev_ni and abs(prev_ni) > 0 and impair / abs(prev_ni) * 100 >= 5.0):
                events.append({"ticker": ticker, "fy": fy, "type": "impairment"})
        extra = _annual_value(items, "extraordinary_loss", fy)
        if extra is not None and extra > 0:
            if (rev and rev > 0 and extra / rev * 100 >= 5.0) or \
               (prev_ni and abs(prev_ni) > 0 and extra / abs(prev_ni) * 100 >= 10.0):
                events.append({"ticker": ticker, "fy": fy, "type": "extraordinary"})
    return events


# Build full event registry across orig + OOS JGAAP cohorts
def _build_event_registry():
    reg = defaultdict(list)
    all_events = []
    for tk in ALL_JGAAP:
        evs = _detect_events_for_ticker(tk)
        for ev in evs:
            reg[(ev["ticker"], ev["fy"])].append(ev)
            all_events.append(ev)
    return reg, all_events


def _score_v2(op_yoy, has_bad_event, threshold=5.0):
    """Recipe A v2: single-axis op profit + event-based negative trigger."""
    if op_yoy is None:
        return "n/a"
    if op_yoy <= -threshold or has_bad_event:
        return "negative"
    if op_yoy >= threshold:
        return "positive"
    return "mixed"


def _score_pred(judgment, outcome):
    if outcome == "n/a":
        return "n/a"
    if judgment == "uncertain":
        return "abstain"
    if judgment == "growth_likely" and outcome == "positive":
        return "hit"
    if judgment == "growth_unlikely" and outcome == "negative":
        return "hit"
    return "miss"


def _aggregate(scored, label):
    hit = sum(1 for s in scored if s["verdict"] == "hit")
    miss = sum(1 for s in scored if s["verdict"] == "miss")
    abst = sum(1 for s in scored if s["verdict"] == "abstain")
    conf = hit + miss
    prec = (hit / conf * 100) if conf else None
    ci = _wilson_ci(hit, conf)
    by_class = {}
    for cls in ("growth_likely", "growth_unlikely", "uncertain"):
        rows = [s for s in scored if s["judgment"] == cls]
        h = sum(1 for s in rows if s["verdict"] == "hit")
        m = sum(1 for s in rows if s["verdict"] == "miss")
        a = sum(1 for s in rows if s["verdict"] == "abstain")
        c = h + m
        p = (h / c * 100) if c else None
        cic = _wilson_ci(h, c)
        by_class[cls] = {
            "n": len(rows), "hit": h, "miss": m, "abstain": a,
            "precision_pct": round(p, 1) if p is not None else None,
            "ci_95_pct": (round(cic[0], 1), round(cic[1], 1)) if cic[0] is not None else None,
        }
    return {
        "label": label, "n_total": len(scored), "hit": hit, "miss": miss,
        "abstain": abst, "confident": conf,
        "overall_precision_pct": round(prec, 1) if prec is not None else None,
        "overall_ci_95_pct": (round(ci[0], 1), round(ci[1], 1)) if ci[0] is not None else None,
        "by_class": by_class,
    }


def main():
    print("Combined meta-analysis: original + out-of-sample", flush=True)
    with open(ORIG_PATH, encoding="utf-8") as f:
        orig = json.load(f)
    with open(OOS_PATH, encoding="utf-8") as f:
        oos = json.load(f)
    print(f"  Original: {len(orig['scored_predictions'])} preds, {orig['hits']} hits / "
          f"{orig['misses']} miss / {orig['abstains']} abstain", flush=True)
    print(f"  OOS:      {len(oos['scored_predictions'])} preds, {oos['hits']} hits / "
          f"{oos['misses']} miss / {oos['abstains']} abstain", flush=True)

    # Build event registry across full JGAAP cohort (original + OOS)
    print("\nDetecting Recipe C events across full JGAAP cohort…", flush=True)
    event_reg, all_events = _build_event_registry()
    print(f"  Total events detected: {len(all_events)}", flush=True)
    for ev in all_events:
        print(f"    {ev['ticker']} FY{ev['fy']} {ev['type']}", flush=True)

    # Enrich each prediction with op_profit_yoy AND event lookup
    pair_cache = {}
    def enrich(preds_list, label):
        out = []
        for p in preds_list:
            tk = p["ticker"]
            if tk not in pair_cache:
                pair_cache[tk] = _load_pair_data(tk)
            pairs = pair_cache[tk]
            def match(pp, lbl):
                return f"FY{pp['prev_fiscal_year']}->FY{pp['curr_fiscal_year']}" == lbl
            out_pair = next((pp for pp in pairs if match(pp, p["outcome_pair"])), None)
            op_yoy = out_pair.get("op_profit_delta_pct") if out_pair else None
            try:
                outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
            except Exception:
                outcome_fy = None
            evs_2y = []
            if outcome_fy is not None:
                evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
            out.append({
                **p, "op_profit_yoy_pct": op_yoy,
                "has_bad_event_2y": bool(evs_2y),
                "is_jgaap": tk in ALL_JGAAP,
                "sample": label,
            })
        return out

    orig_enriched = enrich(orig["scored_predictions"], "original")
    oos_enriched = enrich(oos["scored_predictions"], "out_of_sample")
    combined = orig_enriched + oos_enriched

    # Score under Recipe A v2
    # Variant 1: full sample, op-profit only (no event layer for IFRS)
    # Variant 2: JGAAP subset only, op-profit + event layer (2y window)
    print("\n" + "=" * 110, flush=True)
    print("RECIPE A v2 — SINGLE-AXIS + EVENT TRIGGER, COMBINED SAMPLE", flush=True)
    print("=" * 110, flush=True)

    aggs = {}
    for label, dataset in [("Original 20 (re-baseline)", orig_enriched),
                            ("Out-of-sample 15", oos_enriched),
                            ("COMBINED 35", combined)]:
        # Variant 1: op-profit only, FULL sample
        full = []
        for e in dataset:
            outcome = _score_v2(e["op_profit_yoy_pct"], False, threshold=5.0)  # no events
            verdict = _score_pred(e["judgment"], outcome)
            full.append({**e, "verdict": verdict, "outcome": outcome})
        # Variant 2: JGAAP only, op-profit + event layer (2y)
        jgaap = []
        for e in dataset:
            if not e["is_jgaap"]:
                continue
            outcome = _score_v2(e["op_profit_yoy_pct"], e["has_bad_event_2y"], threshold=5.0)
            verdict = _score_pred(e["judgment"], outcome)
            jgaap.append({**e, "verdict": verdict, "outcome": outcome})

        agg_full = _aggregate(full, f"{label} | op-profit only (full sample)")
        agg_jg = _aggregate(jgaap, f"{label} | op-profit + event (JGAAP cohort)")
        aggs[label] = {"full": agg_full, "jgaap": agg_jg}

        for variant in (agg_full, agg_jg):
            print(f"\n--- {variant['label']} ---", flush=True)
            print(f"  total={variant['n_total']}, confident={variant['confident']}, "
                  f"hit={variant['hit']}, miss={variant['miss']}, abstain={variant['abstain']}",
                  flush=True)
            op = variant["overall_precision_pct"]
            oc = variant["overall_ci_95_pct"]
            print(f"  Overall: {op}% [{oc[0]}-{oc[1]}]" if op is not None else "  Overall: n/a", flush=True)
            for cls, c in variant["by_class"].items():
                p = c["precision_pct"]; ci = c["ci_95_pct"]
                p_s = f"{p}%" if p is not None else "n/a"
                ci_s = f"[{ci[0]}-{ci[1]}]" if ci else ""
                print(f"    {cls:18s}: n={c['n']}, hit={c['hit']}, miss={c['miss']}, "
                      f"abstain={c['abstain']}, prec={p_s} {ci_s}", flush=True)

    OUT_PATH.write_text(json.dumps({
        "methodology": "Recipe A v2 single-axis + event trigger",
        "original_n_tickers": 20,
        "oos_n_tickers": 14,  # 4716 failed
        "combined_n_tickers": 34,
        "results": aggs,
        "events_detected": all_events,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
