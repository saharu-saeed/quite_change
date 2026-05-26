"""Grand meta-analysis: original 20 + OOS 15 + extension 30 = 65 tickers.

Applies Recipe A v2 (op profit + event-based 2y window) to all three
samples and reports JGAAP cohort precision with combined confidence
intervals — the most rigorous validation we have.
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "outputs" / "agent_cache"
TEMPEST_DIR = ROOT / "data" / "tempest"

JGAAP_ORIG = ["3656", "3760", "3923", "4385", "4475", "4477", "4480", "4684", "4768", "9684", "9697"]
JGAAP_OOS = ["4063", "4716", "4751", "6861"]
JGAAP_EXT = ["3626", "3635", "3697", "3994", "4194", "4676", "4704", "4733",
             "9401", "9404", "9468", "9602", "9759",
             "2121", "2317", "2326", "3636", "3660", "3661", "3668", "3765",
             "3778", "3844", "4071", "4384", "4443", "4686", "4722", "4776", "4812"]
ALL_JGAAP = JGAAP_ORIG + JGAAP_OOS + JGAAP_EXT


def _wilson_ci(hits, n, z=1.96):
    if n == 0:
        return (None, None)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    rad = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, (center - rad) * 100), min(100.0, (center + rad) * 100))


def _f(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _load_line_items(ticker):
    p = TEMPEST_DIR / ticker / "financials_line_items.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)["data"]


def _annual_value(items, key, fy, std="Japan GAAP"):
    matches = [i for i in items if i["line_item_key"] == key
               and i["fiscal_year"] == fy
               and i.get("fiscal_quarter") is None
               and i.get("accounting_standard") == std]
    if not matches:
        return None
    return _f(matches[0]["value"])


def _detect_jgaap_events(ticker):
    items = _load_line_items(ticker)
    if not items:
        return []
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
            trig = False
            if prev_equity and prev_equity > 0 and impair / prev_equity * 100 >= 1.0:
                trig = True
            if not trig and prev_ni and abs(prev_ni) > 0 and impair / abs(prev_ni) * 100 >= 5.0:
                trig = True
            if trig:
                events.append({"ticker": ticker, "fy": fy, "type": "impairment", "magnitude": impair})
        extra = _annual_value(items, "extraordinary_loss", fy)
        if extra is not None and extra > 0:
            trig = False
            if rev and rev > 0 and extra / rev * 100 >= 5.0:
                trig = True
            if not trig and prev_ni and abs(prev_ni) > 0 and extra / abs(prev_ni) * 100 >= 10.0:
                trig = True
            if trig:
                events.append({"ticker": ticker, "fy": fy, "type": "extraordinary", "magnitude": extra})
    return events


def _load_pair_data(ticker):
    matches = sorted(glob.glob(str(CACHE_DIR / f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not matches:
        return []
    with open(matches[-1], encoding="utf-8") as f:
        d = json.load(f)
    return [p for p in d.get("pairs", []) if not p.get("history_only")]


def _score_v2(op_yoy, has_bad, thr=5.0):
    if op_yoy is None:
        return "n/a"
    if op_yoy <= -thr or has_bad:
        return "negative"
    if op_yoy >= thr:
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
        by_class[cls] = {"n": len(rows), "hit": h, "miss": m, "abstain": a,
                         "precision_pct": round(p, 1) if p is not None else None,
                         "ci_95_pct": (round(cic[0], 1), round(cic[1], 1)) if cic[0] is not None else None}
    return {"label": label, "n_total": len(scored), "hit": hit, "miss": miss, "abstain": abst,
            "confident": conf,
            "overall_precision_pct": round(prec, 1) if prec is not None else None,
            "overall_ci_95_pct": (round(ci[0], 1), round(ci[1], 1)) if ci[0] is not None else None,
            "by_class": by_class}


def main():
    print("GRAND META-ANALYSIS — original + OOS + extension on JGAAP cohort", flush=True)
    print(f"JGAAP cohort: {len(ALL_JGAAP)} tickers", flush=True)

    # Detect events
    print("\n[step 1] Detecting JGAAP events across all 30 cohort tickers…", flush=True)
    event_reg = defaultdict(list)
    all_events = []
    for tk in ALL_JGAAP:
        for ev in _detect_jgaap_events(tk):
            all_events.append(ev)
            event_reg[(ev["ticker"], ev["fy"])].append(ev)
    print(f"  Total events: {len(all_events)}", flush=True)

    # Load predictions from all three sources
    print("\n[step 2] Loading predictions…", flush=True)
    paths = [
        ROOT / "outputs" / "rolling_window_backtest.json",
        ROOT / "outputs" / "out_of_sample_rolling_window.json",
        ROOT / "outputs" / "jgaap_extension_rolling_window.json",
    ]
    all_preds = []
    sample_labels = ["original_20", "oos_15", "extension_30"]
    for p, label in zip(paths, sample_labels):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        for pred in d["scored_predictions"]:
            all_preds.append({**pred, "sample": label})
        print(f"  {label}: {len(d['scored_predictions'])} preds", flush=True)
    print(f"  Total: {len(all_preds)}", flush=True)

    # Enrich with op_profit_yoy + event lookup, filter to JGAAP cohort
    pair_cache = {}
    enriched = []
    for p in all_preds:
        tk = p["ticker"]
        if tk not in ALL_JGAAP:
            continue
        if tk not in pair_cache:
            pair_cache[tk] = _load_pair_data(tk)
        pairs = pair_cache[tk]
        out_pair = next(
            (pp for pp in pairs
             if f"FY{pp['prev_fiscal_year']}->FY{pp['curr_fiscal_year']}" == p["outcome_pair"]),
            None)
        op_yoy = out_pair.get("op_profit_delta_pct") if out_pair else None
        try:
            outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except Exception:
            outcome_fy = None
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
        enriched.append({**p, "op_profit_yoy_pct": op_yoy,
                         "has_bad_event_2y": bool(evs_2y), "events_2y": evs_2y})

    # Score
    print(f"\n[step 3] Scoring {len(enriched)} JGAAP predictions under Recipe A v2…", flush=True)
    scored = []
    for e in enriched:
        outcome = _score_v2(e["op_profit_yoy_pct"], e["has_bad_event_2y"])
        verdict = _score_pred(e["judgment"], outcome)
        scored.append({**e, "verdict": verdict, "outcome": outcome})

    # Aggregate by sample and grand total
    print("\n" + "=" * 110, flush=True)
    print("RECIPE A v2 — JGAAP COHORT, ALL THREE SAMPLES", flush=True)
    print("=" * 110, flush=True)
    aggs = {}
    for label in ["original_20", "oos_15", "extension_30"]:
        rows = [s for s in scored if s["sample"] == label]
        agg = _aggregate(rows, f"{label} (JGAAP only)")
        aggs[label] = agg
    aggs["GRAND_TOTAL"] = _aggregate(scored, "GRAND TOTAL JGAAP cohort")

    for key, agg in aggs.items():
        print(f"\n--- {agg['label']} ---", flush=True)
        print(f"  total={agg['n_total']}, confident={agg['confident']}, "
              f"hit={agg['hit']}, miss={agg['miss']}, abstain={agg['abstain']}", flush=True)
        op = agg["overall_precision_pct"]
        oc = agg["overall_ci_95_pct"]
        if op is not None:
            print(f"  Overall: {op}% CI [{oc[0]}-{oc[1]}]", flush=True)
        for cls, c in agg["by_class"].items():
            p = c["precision_pct"]; ci = c["ci_95_pct"]
            p_s = f"{p}%" if p is not None else "n/a"
            ci_s = f"[{ci[0]}-{ci[1]}]" if ci else ""
            print(f"    {cls:18s}: n={c['n']}, hit={c['hit']}, miss={c['miss']}, "
                  f"abstain={c['abstain']}, prec={p_s} {ci_s}", flush=True)

    out_path = ROOT / "outputs" / "grand_meta_results.json"
    out_path.write_text(json.dumps({
        "samples": ["original_20", "oos_15", "extension_30"],
        "jgaap_cohort_size": len(ALL_JGAAP),
        "n_events_detected": len(all_events),
        "results": aggs,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)


if __name__ == "__main__":
    main()
