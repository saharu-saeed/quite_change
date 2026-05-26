"""Recipe C-Reduced backtest — event-based ground truth on JGAAP cohort.

Scores the 28 confident predictions against an event-based outcome:
  "Did a material bad event happen in the 1-2 year forward window?"

Bad events (locked thresholds):
  - Impairment loss   ≥ 1% of prior-FY equity  OR  ≥ 5% of prior-FY |NI|
  - Extraordinary loss ≥ 5% of revenue          OR  ≥ 10% of prior-FY |NI|

Cohort: 11 JGAAP tickers only. IFRS tickers explicitly excluded
(IFRS folds impairment/extraordinary into operating expenses — no
separate field). Documented at outputs/recipe_a_methodology.md.

Event lists are generated BLIND to the agent's verdict, then joined.
No LLM calls.
"""
from __future__ import annotations
import json
import sys
import io
from pathlib import Path
from collections import defaultdict
import math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "outputs" / "agent_cache"
ROLLING_PATH = ROOT / "outputs" / "rolling_window_backtest.json"
TEMPEST_DIR = ROOT / "data" / "tempest"
OUT_PATH = ROOT / "outputs" / "recipe_c_reduced_results.json"

# Locked cohort (JGAAP filers with impairment_loss or extraordinary_loss
# fields in financials_line_items.json). 4385 included for JGAAP years
# only — IFRS years are skipped event-wise.
JGAAP_COHORT = ["3656", "3760", "3923", "4385", "4475", "4477",
                "4480", "4684", "4768", "9684", "9697"]

# Locked thresholds
THR_IMPAIR_PCT_EQUITY = 1.0   # ≥1% of prior-FY equity
THR_IMPAIR_PCT_NI = 5.0       # ≥5% of prior-FY |NI|
THR_EXTRA_PCT_REV = 5.0       # ≥5% of revenue
THR_EXTRA_PCT_NI = 10.0       # ≥10% of prior-FY |NI|


def _wilson_ci(hits: int, n: int, z: float = 1.96):
    if n == 0:
        return (None, None)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    rad = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, (center - rad) * 100), min(100.0, (center + rad) * 100))


def _load_line_items(ticker: str) -> list[dict]:
    p = TEMPEST_DIR / ticker / "financials_line_items.json"
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    return d["data"]


def _annual_value(items: list[dict], key: str, fy: int,
                  accounting_standard: str | None = None) -> float | None:
    """Return annual value for line_item_key at FY (quarter=null = annual).

    If accounting_standard given, restricts to that standard.
    """
    matches = [i for i in items
               if i["line_item_key"] == key
               and i["fiscal_year"] == fy
               and i.get("fiscal_quarter") is None
               and (accounting_standard is None
                    or i.get("accounting_standard") == accounting_standard)]
    if not matches:
        return None
    v = matches[0]["value"]
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _detect_events_for_ticker(ticker: str) -> list[dict]:
    """Return list of bad events for this ticker, blind to any verdict.

    Each event: {fy, event_type, magnitude, denominator, denom_value, threshold_met, accounting_standard}
    """
    items = _load_line_items(ticker)
    events: list[dict] = []
    # Standard preference: JGAAP rows when present (4385 has both)
    # For 4385, only consider JGAAP-year impairment/extraordinary entries.
    stds_present = sorted(set(i.get("accounting_standard") for i in items
                              if i.get("accounting_standard")))
    use_std = "Japan GAAP" if "Japan GAAP" in stds_present else None

    # Collect all FYs that have data
    fys = sorted(set(i["fiscal_year"] for i in items
                     if i.get("fiscal_quarter") is None
                     and (use_std is None or i.get("accounting_standard") == use_std)))

    for fy in fys:
        # Look up prior-FY equity and prior-FY |NI| (for denominators)
        prev_equity = _annual_value(items, "total_equity", fy - 1, use_std)
        prev_ni = _annual_value(items, "profit_loss", fy - 1, use_std)
        if prev_ni is None:
            # JGAAP filers sometimes use 'profit_attributable_to_owners_of_parent'
            prev_ni = _annual_value(items, "profit_attributable_to_owners_of_parent",
                                    fy - 1, use_std)
        rev = _annual_value(items, "net_sales", fy, use_std)

        # Impairment check
        impair = _annual_value(items, "impairment_loss", fy, use_std)
        if impair is not None and impair > 0:
            triggered = False
            denom_used = None
            denom_val = None
            pct = None
            if prev_equity is not None and prev_equity > 0:
                pct_eq = impair / prev_equity * 100
                if pct_eq >= THR_IMPAIR_PCT_EQUITY:
                    triggered = True
                    denom_used = "prev_equity"
                    denom_val = prev_equity
                    pct = pct_eq
            if not triggered and prev_ni is not None and abs(prev_ni) > 0:
                pct_ni = impair / abs(prev_ni) * 100
                if pct_ni >= THR_IMPAIR_PCT_NI:
                    triggered = True
                    denom_used = "abs(prev_ni)"
                    denom_val = abs(prev_ni)
                    pct = pct_ni
            if triggered:
                events.append({
                    "ticker": ticker, "fy": fy, "event_type": "impairment",
                    "magnitude": impair, "denom_used": denom_used,
                    "denom_value": denom_val, "pct_of_denom": round(pct, 2) if pct else None,
                    "accounting_standard": use_std,
                })

        # Extraordinary loss check
        extra = _annual_value(items, "extraordinary_loss", fy, use_std)
        if extra is not None and extra > 0:
            triggered = False
            denom_used = None
            denom_val = None
            pct = None
            if rev is not None and rev > 0:
                pct_rev = extra / rev * 100
                if pct_rev >= THR_EXTRA_PCT_REV:
                    triggered = True
                    denom_used = "revenue"
                    denom_val = rev
                    pct = pct_rev
            if not triggered and prev_ni is not None and abs(prev_ni) > 0:
                pct_ni = extra / abs(prev_ni) * 100
                if pct_ni >= THR_EXTRA_PCT_NI:
                    triggered = True
                    denom_used = "abs(prev_ni)"
                    denom_val = abs(prev_ni)
                    pct = pct_ni
            if triggered:
                events.append({
                    "ticker": ticker, "fy": fy, "event_type": "extraordinary_loss",
                    "magnitude": extra, "denom_used": denom_used,
                    "denom_value": denom_val, "pct_of_denom": round(pct, 2) if pct else None,
                    "accounting_standard": use_std,
                })

    return events


def main() -> int:
    print("Recipe C-Reduced backtest — event-based ground truth", flush=True)
    print(f"JGAAP cohort (n={len(JGAAP_COHORT)}): {JGAAP_COHORT}", flush=True)
    print(f"Thresholds (locked):", flush=True)
    print(f"  Impairment ≥ {THR_IMPAIR_PCT_EQUITY}% of prev equity OR ≥ {THR_IMPAIR_PCT_NI}% of |prev NI|",
          flush=True)
    print(f"  Extraordinary loss ≥ {THR_EXTRA_PCT_REV}% of revenue OR ≥ {THR_EXTRA_PCT_NI}% of |prev NI|",
          flush=True)
    print()

    # Step 1: Generate event lists for all cohort tickers, BLIND to verdicts
    print("[step 1] Detecting bad events per ticker (blind to verdicts)…", flush=True)
    all_events: list[dict] = []
    events_by_ticker_fy: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for tk in JGAAP_COHORT:
        try:
            evs = _detect_events_for_ticker(tk)
        except Exception as e:
            print(f"  [{tk}] ERROR: {e}", flush=True)
            continue
        for ev in evs:
            all_events.append(ev)
            events_by_ticker_fy[(ev["ticker"], ev["fy"])].append(ev)
    print(f"  Detected {len(all_events)} bad events across cohort.", flush=True)
    print()
    print("Event log:", flush=True)
    for ev in sorted(all_events, key=lambda e: (e["ticker"], e["fy"])):
        mag_oku = ev["magnitude"] / 1e8
        print(f"  {ev['ticker']}  FY{ev['fy']}  {ev['event_type']:<20} "
              f"{mag_oku:>10.1f}億円  ({ev['pct_of_denom']:.1f}% of {ev['denom_used']})",
              flush=True)
    print()

    # Step 2: Load rolling-window predictions, restrict to cohort, score
    with open(ROLLING_PATH, encoding="utf-8") as f:
        roll = json.load(f)
    preds = [p for p in roll["scored_predictions"] if p["ticker"] in JGAAP_COHORT]
    print(f"[step 2] Cohort predictions: {len(preds)} (of {len(roll['scored_predictions'])} total)",
          flush=True)

    # For each prediction:
    #   pred_pair = "FY[N]->FY[N+1]" — the agent saw FY[N+1] report and predicted forward
    #   outcome_pair = "FY[N+1]->FY[N+2]"
    #   1-year window = events in FY[N+2]
    #   2-year window = events in FY[N+2] OR FY[N+3]
    # We need to extract N+2 from outcome_pair label.
    def _fys_from_outcome(label: str) -> int:
        """Outcome pair 'FY2022->FY2023' means the outcome FY is 2023."""
        try:
            return int(label.split("->")[1].replace("FY", ""))
        except Exception:
            return -1

    # Step 3: Score each prediction
    scored_1y: list[dict] = []
    scored_2y: list[dict] = []
    for p in preds:
        tk = p["ticker"]
        outcome_fy = _fys_from_outcome(p["outcome_pair"])
        if outcome_fy < 0:
            continue

        # 1-year window: events in outcome_fy
        evs_1y = events_by_ticker_fy.get((tk, outcome_fy), [])
        # 2-year window: events in outcome_fy or outcome_fy+1
        evs_2y = evs_1y + events_by_ticker_fy.get((tk, outcome_fy + 1), [])

        # Whether the (1y) or (2y) window has any bad event available in cache
        # (we need to know if outcome_fy+1 is even cached for 2y scoring)
        ticker_items = _load_line_items(tk)
        cached_fys = set(i["fiscal_year"] for i in ticker_items)
        has_2y_data = (outcome_fy + 1) in cached_fys

        # Score
        def _score(judgment, has_bad):
            if judgment == "uncertain":
                return "abstain"
            if judgment == "growth_unlikely":
                return "hit" if has_bad else "miss"
            if judgment == "growth_likely":
                return "miss" if has_bad else "hit"
            return "n/a"

        scored_1y.append({
            **p,
            "outcome_fy": outcome_fy,
            "events_in_window": evs_1y,
            "has_bad_event": bool(evs_1y),
            "verdict_c": _score(p["judgment"], bool(evs_1y)),
        })
        if has_2y_data:
            scored_2y.append({
                **p,
                "outcome_fy": outcome_fy,
                "events_in_window": evs_2y,
                "has_bad_event": bool(evs_2y),
                "verdict_c": _score(p["judgment"], bool(evs_2y)),
                "window_years": 2,
            })

    # Aggregate
    def _agg(scored, label):
        hit = sum(1 for s in scored if s["verdict_c"] == "hit")
        miss = sum(1 for s in scored if s["verdict_c"] == "miss")
        abst = sum(1 for s in scored if s["verdict_c"] == "abstain")
        conf = hit + miss
        prec = (hit / conf * 100) if conf else None
        ci = _wilson_ci(hit, conf)
        by_class = {}
        for cls in ("growth_likely", "growth_unlikely", "uncertain"):
            cls_rows = [s for s in scored if s["judgment"] == cls]
            cls_hit = sum(1 for s in cls_rows if s["verdict_c"] == "hit")
            cls_miss = sum(1 for s in cls_rows if s["verdict_c"] == "miss")
            cls_abs = sum(1 for s in cls_rows if s["verdict_c"] == "abstain")
            cls_conf = cls_hit + cls_miss
            cls_prec = (cls_hit / cls_conf * 100) if cls_conf else None
            cls_ci = _wilson_ci(cls_hit, cls_conf)
            by_class[cls] = {
                "n": len(cls_rows), "hit": cls_hit, "miss": cls_miss,
                "abstain": cls_abs,
                "precision_pct": round(cls_prec, 1) if cls_prec is not None else None,
                "ci_95_pct": (round(cls_ci[0], 1), round(cls_ci[1], 1))
                              if cls_ci[0] is not None else None,
            }
        return {
            "label": label, "n_total": len(scored), "hit": hit, "miss": miss,
            "abstain": abst, "confident": conf,
            "overall_precision_pct": round(prec, 1) if prec is not None else None,
            "overall_ci_95_pct": (round(ci[0], 1), round(ci[1], 1))
                                  if ci[0] is not None else None,
            "by_class": by_class,
            "scored_rows": scored,
        }

    agg_1y = _agg(scored_1y, "1-year window")
    agg_2y = _agg(scored_2y, "2-year window (where available)")

    # Print
    print("=" * 100, flush=True)
    print("RECIPE C-REDUCED RESULTS", flush=True)
    print("=" * 100, flush=True)

    for agg in (agg_1y, agg_2y):
        print(f"\n{agg['label']}: total={agg['n_total']}, confident={agg['confident']}",
              flush=True)
        print(f"  Hits: {agg['hit']}, Misses: {agg['miss']}, Abstains: {agg['abstain']}",
              flush=True)
        op = agg["overall_precision_pct"]
        oc = agg["overall_ci_95_pct"]
        op_s = f"{op:.1f}%" if op is not None else "n/a"
        oc_s = f"[{oc[0]:.1f}-{oc[1]:.1f}]" if oc else "n/a"
        print(f"  Overall precision: {op_s}  95% CI: {oc_s}", flush=True)
        print(f"  By class:", flush=True)
        for cls, c in agg["by_class"].items():
            p_s = f"{c['precision_pct']:.1f}%" if c["precision_pct"] is not None else "n/a"
            ci_s = f"[{c['ci_95_pct'][0]:.1f}-{c['ci_95_pct'][1]:.1f}]" if c["ci_95_pct"] else "n/a"
            print(f"    {cls:18s}: n={c['n']}, hit={c['hit']}, miss={c['miss']}, "
                  f"abstain={c['abstain']}, precision={p_s}, 95% CI={ci_s}", flush=True)

    # Per-prediction detail
    print("\n" + "=" * 100, flush=True)
    print("PER-PREDICTION DETAIL (1-year window)", flush=True)
    print("=" * 100, flush=True)
    for s in scored_1y:
        if s["judgment"] == "uncertain":
            continue
        evs_s = ", ".join(f"{e['event_type']}@FY{e['fy']} ({e['pct_of_denom']:.0f}% {e['denom_used']})"
                         for e in s["events_in_window"])
        if not evs_s:
            evs_s = "(no bad event)"
        print(f"  {s['ticker']:<6}{s['prediction_pair']:<22}{s['judgment']:<18}"
              f"outcome=FY{s['outcome_fy']}  {evs_s}  → {s['verdict_c'].upper()}",
              flush=True)

    OUT_PATH.write_text(json.dumps({
        "methodology": "recipe_a_methodology.md",
        "cohort": JGAAP_COHORT,
        "thresholds": {
            "impair_pct_equity": THR_IMPAIR_PCT_EQUITY,
            "impair_pct_ni": THR_IMPAIR_PCT_NI,
            "extra_pct_rev": THR_EXTRA_PCT_REV,
            "extra_pct_ni": THR_EXTRA_PCT_NI,
        },
        "all_events": all_events,
        "results_1y": agg_1y,
        "results_2y": agg_2y,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
