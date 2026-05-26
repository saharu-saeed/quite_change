"""Recipe A v2 extended — JGAAP direct event detection + IFRS proxy event detection.

Adds IFRS coverage via PROXY signals (goodwill writedowns, op profit
sharp drops, margin contraction) since IFRS doesn't expose impairment
as a structured line item.

Thresholds pre-registered at outputs/ifrs_event_proxy_methodology.md
BEFORE this script runs. No LLM calls.

Reports separately:
  - JGAAP cohort (direct event detection, original Recipe A v2)
  - IFRS cohort (proxy event detection, NEW)
  - Combined cohort (full universe)
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
ORIG_PATH = ROOT / "outputs" / "rolling_window_backtest.json"
OOS_PATH = ROOT / "outputs" / "out_of_sample_rolling_window.json"
OUT_PATH = ROOT / "outputs" / "recipe_a_v2_with_ifrs_results.json"

JGAAP_COHORT = ["3656", "3760", "3923", "4385", "4475", "4477",
                "4480", "4684", "4768", "9684", "9697", "4063", "4716", "4751", "6861"]
IFRS_COHORT = ["3659", "4307", "4483", "4689", "9432", "9433", "9434", "9719", "9984",
               "2371", "4502", "4519", "4755", "6098", "6501", "6701", "6702",
               "6758", "6857", "7203"]

# Locked thresholds
JGAAP_THR_IMPAIR_EQUITY = 1.0
JGAAP_THR_IMPAIR_NI = 5.0
JGAAP_THR_EXTRA_REV = 5.0
JGAAP_THR_EXTRA_NI = 10.0

IFRS_THR_GOODWILL_REL_DECLINE = 10.0     # goodwill drop >=10% YoY
IFRS_THR_GOODWILL_PCT_EQUITY = 1.0       # OR drop >=1% of prior equity
IFRS_THR_OP_DROP = 15.0                  # op profit YoY drop >=15%
IFRS_THR_MARGIN_CONTRACT_PP = 3.0        # operating margin drop >=3pp


def _wilson_ci(hits, n, z=1.96):
    if n == 0:
        return (None, None)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    rad = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, (center - rad) * 100), min(100.0, (center + rad) * 100))


def _load_line_items(ticker):
    p = TEMPEST_DIR / ticker / "financials_line_items.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)["data"]


def _annual_value(items, key, fy, std=None):
    matches = [i for i in items
               if i["line_item_key"] == key
               and i["fiscal_year"] == fy
               and i.get("fiscal_quarter") is None
               and (std is None or i.get("accounting_standard") == std)]
    if not matches:
        return None
    v = matches[0]["value"]
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _load_financials_summary(ticker):
    """Return list of annual rows from financials.json (has operating_profit, equity, etc.)."""
    p = TEMPEST_DIR / ticker / "financials.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)["data"]


def _annual_summary(rows, fy):
    return next((r for r in rows if r.get("fiscal_year") == fy), None)


def _f(v):
    """Coerce to float; return None if not coercible."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _detect_jgaap_events(ticker):
    """Direct event detection for JGAAP filers (impairment + extraordinary loss)."""
    items = _load_line_items(ticker)
    if not items:
        return []
    stds = set(i.get("accounting_standard") for i in items if i.get("accounting_standard"))
    if "Japan GAAP" not in stds:
        return []
    use_std = "Japan GAAP"
    fys = sorted(set(i["fiscal_year"] for i in items
                     if i.get("fiscal_quarter") is None
                     and i.get("accounting_standard") == use_std))
    events = []
    for fy in fys:
        prev_equity = _annual_value(items, "total_equity", fy - 1, use_std)
        prev_ni = _annual_value(items, "profit_loss", fy - 1, use_std) or \
                  _annual_value(items, "profit_attributable_to_owners_of_parent", fy - 1, use_std)
        rev = _annual_value(items, "net_sales", fy, use_std)
        impair = _annual_value(items, "impairment_loss", fy, use_std)
        if impair is not None and impair > 0:
            trig = False
            if prev_equity and prev_equity > 0 and impair / prev_equity * 100 >= JGAAP_THR_IMPAIR_EQUITY:
                trig = True
            if not trig and prev_ni and abs(prev_ni) > 0 and impair / abs(prev_ni) * 100 >= JGAAP_THR_IMPAIR_NI:
                trig = True
            if trig:
                events.append({"ticker": ticker, "fy": fy, "type": "jgaap_impairment",
                               "magnitude": impair, "detector": "JGAAP direct"})
        extra = _annual_value(items, "extraordinary_loss", fy, use_std)
        if extra is not None and extra > 0:
            trig = False
            if rev and rev > 0 and extra / rev * 100 >= JGAAP_THR_EXTRA_REV:
                trig = True
            if not trig and prev_ni and abs(prev_ni) > 0 and extra / abs(prev_ni) * 100 >= JGAAP_THR_EXTRA_NI:
                trig = True
            if trig:
                events.append({"ticker": ticker, "fy": fy, "type": "jgaap_extraordinary",
                               "magnitude": extra, "detector": "JGAAP direct"})
    return events


def _detect_ifrs_events(ticker):
    """Proxy event detection for IFRS filers (goodwill decline + op-profit footprint)."""
    items = _load_line_items(ticker)
    summary = _load_financials_summary(ticker)
    if not items or not summary:
        return []
    stds = set(i.get("accounting_standard") for i in items if i.get("accounting_standard"))
    if "IFRS" not in stds:
        return []
    use_std = "IFRS"
    fys = sorted(set(s.get("fiscal_year") for s in summary if s.get("fiscal_year") is not None))
    events = []
    for fy in fys:
        # 1. Goodwill writedown check
        gw_curr = _annual_value(items, "goodwill", fy, use_std)
        gw_prev = _annual_value(items, "goodwill", fy - 1, use_std)
        equity_prev = _annual_value(items, "total_equity", fy - 1, use_std)
        if gw_curr is not None and gw_prev is not None and gw_prev > 0:
            delta = gw_curr - gw_prev
            pct_change = delta / gw_prev * 100
            pct_of_equity = (delta / equity_prev * 100) if equity_prev and equity_prev > 0 else None
            triggered = False
            if pct_change <= -JGAAP_THR_IMPAIR_EQUITY * 10:  # using 10% relative threshold per methodology
                triggered = True
            if pct_of_equity is not None and pct_of_equity <= -IFRS_THR_GOODWILL_PCT_EQUITY:
                triggered = True
            if triggered:
                events.append({
                    "ticker": ticker, "fy": fy, "type": "ifrs_goodwill_writedown",
                    "magnitude": delta, "pct_change": round(pct_change, 2),
                    "pct_of_prev_equity": round(pct_of_equity, 2) if pct_of_equity is not None else None,
                    "detector": "IFRS proxy",
                })

        # 2. Op profit sharp drop
        curr_row = _annual_summary(summary, fy)
        prev_row = _annual_summary(summary, fy - 1)
        if curr_row and prev_row:
            op_curr = _f(curr_row.get("operating_profit"))
            op_prev = _f(prev_row.get("operating_profit"))
            if op_curr is not None and op_prev is not None and op_prev != 0:
                yoy_pct = (op_curr - op_prev) / abs(op_prev) * 100
                if yoy_pct <= -IFRS_THR_OP_DROP:
                    events.append({
                        "ticker": ticker, "fy": fy, "type": "ifrs_op_profit_sharp_drop",
                        "magnitude": op_curr - op_prev, "yoy_pct": round(yoy_pct, 2),
                        "detector": "IFRS proxy",
                    })
            # 3. Operating margin contraction
            rev_curr = _f(curr_row.get("net_sales"))
            rev_prev = _f(prev_row.get("net_sales"))
            if (rev_curr and rev_prev and rev_curr > 0 and rev_prev > 0
                    and op_curr is not None and op_prev is not None):
                margin_curr = op_curr / rev_curr * 100
                margin_prev = op_prev / rev_prev * 100
                margin_delta_pp = margin_curr - margin_prev
                if margin_delta_pp <= -IFRS_THR_MARGIN_CONTRACT_PP:
                    events.append({
                        "ticker": ticker, "fy": fy, "type": "ifrs_margin_contraction",
                        "margin_curr_pct": round(margin_curr, 2),
                        "margin_delta_pp": round(margin_delta_pp, 2),
                        "detector": "IFRS proxy",
                    })
    return events


def _load_pair_data(ticker):
    matches = sorted(glob.glob(str(CACHE_DIR / f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
    if not matches:
        return []
    with open(matches[-1], encoding="utf-8") as f:
        d = json.load(f)
    pairs = [p for p in d.get("pairs", []) if not p.get("history_only")]
    pairs.sort(key=lambda p: p.get("curr_period_end", ""))
    return pairs


def _score_v2(op_yoy, has_bad_event, threshold=5.0):
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
    print("Recipe A v2 EXTENDED — JGAAP direct + IFRS proxy event detection", flush=True)
    print(f"Methodology: outputs/ifrs_event_proxy_methodology.md (LOCKED)\n", flush=True)

    # Step 1: build full event registry
    print("[step 1] Detecting events across all cohorts (BLIND to verdicts)…", flush=True)
    all_events = []
    event_reg = defaultdict(list)
    for tk in JGAAP_COHORT:
        for ev in _detect_jgaap_events(tk):
            all_events.append(ev)
            event_reg[(ev["ticker"], ev["fy"])].append(ev)
    for tk in IFRS_COHORT:
        for ev in _detect_ifrs_events(tk):
            all_events.append(ev)
            event_reg[(ev["ticker"], ev["fy"])].append(ev)

    jgaap_evs = [e for e in all_events if e["detector"].startswith("JGAAP")]
    ifrs_evs = [e for e in all_events if e["detector"].startswith("IFRS")]
    print(f"  JGAAP events: {len(jgaap_evs)}", flush=True)
    print(f"  IFRS proxy events: {len(ifrs_evs)}", flush=True)

    # Step 2: load predictions
    with open(ORIG_PATH, encoding="utf-8") as f:
        orig = json.load(f)
    with open(OOS_PATH, encoding="utf-8") as f:
        oos = json.load(f)
    all_preds = orig["scored_predictions"] + oos["scored_predictions"]
    print(f"\n[step 2] Combined predictions: {len(all_preds)} from {len(set(p['ticker'] for p in all_preds))} tickers",
          flush=True)

    # Step 3: enrich + score each prediction
    pair_cache = {}
    enriched = []
    for p in all_preds:
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
        cohort = "JGAAP" if tk in JGAAP_COHORT else ("IFRS" if tk in IFRS_COHORT else "OTHER")
        enriched.append({
            **p, "op_profit_yoy_pct": op_yoy, "cohort": cohort,
            "has_bad_event_2y": bool(evs_2y),
            "events_2y": evs_2y,
        })

    # Step 4: score under different cuts
    print("\n[step 4] Scoring under Recipe A v2 (op profit + event 2y)…\n", flush=True)
    scored_all = []
    for e in enriched:
        outcome = _score_v2(e["op_profit_yoy_pct"], e["has_bad_event_2y"])
        verdict = _score_pred(e["judgment"], outcome)
        scored_all.append({**e, "verdict": verdict, "outcome": outcome})

    jgaap_rows = [s for s in scored_all if s["cohort"] == "JGAAP"]
    ifrs_rows = [s for s in scored_all if s["cohort"] == "IFRS"]
    combined = jgaap_rows + ifrs_rows

    agg_jgaap = _aggregate(jgaap_rows, "JGAAP cohort (direct event detection)")
    agg_ifrs = _aggregate(ifrs_rows, "IFRS cohort (PROXY event detection)")
    agg_combined = _aggregate(combined, "COMBINED cohort (JGAAP direct + IFRS proxy)")

    print("=" * 110, flush=True)
    for agg in (agg_jgaap, agg_ifrs, agg_combined):
        print(f"\n--- {agg['label']} ---", flush=True)
        print(f"  total={agg['n_total']}, confident={agg['confident']}, "
              f"hit={agg['hit']}, miss={agg['miss']}, abstain={agg['abstain']}", flush=True)
        op = agg["overall_precision_pct"]; oc = agg["overall_ci_95_pct"]
        if op is not None:
            print(f"  Overall: {op}% CI [{oc[0]}-{oc[1]}]", flush=True)
        for cls, c in agg["by_class"].items():
            p = c["precision_pct"]; ci = c["ci_95_pct"]
            p_s = f"{p}%" if p is not None else "n/a"
            ci_s = f"[{ci[0]}-{ci[1]}]" if ci else ""
            print(f"    {cls:18s}: n={c['n']}, hit={c['hit']}, miss={c['miss']}, "
                  f"abstain={c['abstain']}, prec={p_s} {ci_s}", flush=True)

    # IFRS event log
    print("\n[IFRS proxy event log]", flush=True)
    for ev in sorted(ifrs_evs, key=lambda e: (e["ticker"], e["fy"])):
        print(f"  {ev['ticker']} FY{ev['fy']} {ev['type']}", flush=True)

    OUT_PATH.write_text(json.dumps({
        "methodology": "ifrs_event_proxy_methodology.md (LOCKED)",
        "jgaap_events": jgaap_evs,
        "ifrs_events": ifrs_evs,
        "results": {
            "jgaap": agg_jgaap,
            "ifrs": agg_ifrs,
            "combined": agg_combined,
        },
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
