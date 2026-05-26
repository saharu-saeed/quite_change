"""Recipe A v2 — single-axis fundamentals + event-based negative trigger.

Built AFTER seeing Recipe A v1 results, motivated by:
  (1) Qualitative review of 7 demo cases (outputs/qualitative_review_demo_cases.md)
      showed the agent's actual claim is single-axis ("this company is healthy or
      troubled fundamentally"), not 2-axis conjunction ("op profit AND stock-vs-sector
      will BOTH move ≥+5%").
  (2) v1's 2-of-2 rule penalized cases where fundamentals were clearly up but
      sector-adjusted stock fell in the deadband — methodology mismatch.

Reported alongside Recipe A v1 (sector-adj 2-of-2), NOT as a replacement.
Both numbers shown side-by-side in client materials per transparency commitment.

Scoring rule (v2):
  - Positive outcome: op_profit YoY ≥ +5% AND no Recipe-C "bad event" in window
  - Negative outcome: op_profit YoY ≤ -5% OR bad event triggered
  - Mixed: op_profit in ±5% deadband AND no bad event

For IFRS tickers (n=9), bad-event detection unavailable per recipe_a_methodology.md
addendum. Report two subsets: JGAAP cohort (full v2 with events) and full-20
(op-profit-only, no event layer).

No LLM calls.
"""
from __future__ import annotations
import json
import sys
import io
import math
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "outputs" / "agent_cache"
ROLLING_PATH = ROOT / "outputs" / "rolling_window_backtest.json"
RECIPE_C_PATH = ROOT / "outputs" / "recipe_c_reduced_results.json"
OUT_PATH = ROOT / "outputs" / "recipe_a_v2_results.json"
THRESHOLDS = [3.0, 5.0, 10.0]

JGAAP_COHORT = ["3656", "3760", "3923", "4385", "4475", "4477",
                "4480", "4684", "4768", "9684", "9697"]


def _wilson_ci(hits: int, n: int, z: float = 1.96):
    if n == 0:
        return (None, None)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    rad = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, (center - rad) * 100), min(100.0, (center + rad) * 100))


def _load_pair_data(ticker):
    matches = sorted(CACHE_DIR.glob(f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json"))
    if not matches:
        return []
    with open(matches[-1], encoding="utf-8") as f:
        d = json.load(f)
    pairs = [p for p in d.get("pairs", []) if not p.get("history_only")]
    pairs.sort(key=lambda p: p.get("curr_period_end", ""))
    return pairs


def _score_v2_jgaap(op_yoy, has_bad_event, threshold):
    """Recipe A v2 for JGAAP cohort: fundamentals + event-based negative trigger."""
    if op_yoy is None:
        return "n/a"
    if op_yoy <= -threshold or has_bad_event:
        return "negative"
    if op_yoy >= threshold:
        return "positive"
    return "mixed"


def _score_v2_pure(op_yoy, threshold):
    """Recipe A v2 for full-20: op_profit only (no event layer for IFRS)."""
    if op_yoy is None:
        return "n/a"
    if op_yoy >= threshold:
        return "positive"
    if op_yoy <= -threshold:
        return "negative"
    return "mixed"


def _score_prediction(judgment, outcome):
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
    hit = sum(1 for s in scored if s["verdict_v2"] == "hit")
    miss = sum(1 for s in scored if s["verdict_v2"] == "miss")
    abst = sum(1 for s in scored if s["verdict_v2"] == "abstain")
    na = sum(1 for s in scored if s["verdict_v2"] == "n/a")
    conf = hit + miss
    prec = (hit / conf * 100) if conf else None
    ci = _wilson_ci(hit, conf)
    by_class = {}
    for cls in ("growth_likely", "growth_unlikely", "uncertain"):
        rows = [s for s in scored if s["judgment"] == cls]
        h = sum(1 for s in rows if s["verdict_v2"] == "hit")
        m = sum(1 for s in rows if s["verdict_v2"] == "miss")
        a = sum(1 for s in rows if s["verdict_v2"] == "abstain")
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
        "abstain": abst, "n_a": na, "confident": conf,
        "overall_precision_pct": round(prec, 1) if prec is not None else None,
        "overall_ci_95_pct": (round(ci[0], 1), round(ci[1], 1)) if ci[0] is not None else None,
        "by_class": by_class,
        "scored_rows": scored,
    }


def main() -> int:
    print("Recipe A v2 — single-axis fundamentals + event-based negative trigger", flush=True)
    print(f"Motivation: aligned to agent's actual claim per qualitative review", flush=True)
    print(f"Thresholds: ±{THRESHOLDS[0]}%, ±{THRESHOLDS[1]}%, ±{THRESHOLDS[2]}%\n", flush=True)

    # Load rolling-window predictions
    with open(ROLLING_PATH, encoding="utf-8") as f:
        roll = json.load(f)
    preds = roll["scored_predictions"]
    print(f"Loaded {len(preds)} predictions from rolling-window.\n", flush=True)

    # Load Recipe C event list — keyed by (ticker, outcome_fy)
    with open(RECIPE_C_PATH, encoding="utf-8") as f:
        cdata = json.load(f)
    events = cdata["all_events"]
    events_by_tk_fy: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for ev in events:
        events_by_tk_fy[(ev["ticker"], ev["fy"])].append(ev)
    print(f"Loaded {len(events)} bad events from Recipe C.\n", flush=True)

    # Enrich each prediction with op_profit_yoy from cached pair data
    pair_cache: dict[str, list[dict]] = {}
    enriched: list[dict] = []
    for p in preds:
        tk = p["ticker"]
        if tk not in pair_cache:
            pair_cache[tk] = _load_pair_data(tk)
        pairs = pair_cache[tk]

        def match(pp, label):
            return f"FY{pp['prev_fiscal_year']}->FY{pp['curr_fiscal_year']}" == label
        out_pair = next((pp for pp in pairs if match(pp, p["outcome_pair"])), None)
        op_yoy = out_pair.get("op_profit_delta_pct") if out_pair else None
        try:
            outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except Exception:
            outcome_fy = None

        # 1y and 2y window events (only meaningful for JGAAP cohort)
        evs_1y = events_by_tk_fy.get((tk, outcome_fy), []) if outcome_fy else []
        evs_2y = evs_1y + (events_by_tk_fy.get((tk, outcome_fy + 1), []) if outcome_fy else [])
        enriched.append({
            "ticker": tk,
            "prediction_pair": p["prediction_pair"],
            "outcome_pair": p["outcome_pair"],
            "judgment": p["judgment"],
            "op_profit_yoy_pct": op_yoy,
            "outcome_fy": outcome_fy,
            "has_bad_event_1y": bool(evs_1y),
            "has_bad_event_2y": bool(evs_2y),
            "is_jgaap_cohort": tk in JGAAP_COHORT,
            "events_1y": evs_1y,
            "events_2y": evs_2y,
        })

    # Score at each threshold
    summary: dict[str, dict] = {}
    for thr in THRESHOLDS:
        # JGAAP cohort with event layer (1y window)
        jg_scored_1y = []
        for e in enriched:
            if not e["is_jgaap_cohort"]:
                continue
            outcome = _score_v2_jgaap(e["op_profit_yoy_pct"], e["has_bad_event_1y"], thr)
            verdict = _score_prediction(e["judgment"], outcome)
            jg_scored_1y.append({**e, "outcome_v2": outcome, "verdict_v2": verdict})

        # JGAAP cohort with event layer (2y window)
        jg_scored_2y = []
        for e in enriched:
            if not e["is_jgaap_cohort"]:
                continue
            outcome = _score_v2_jgaap(e["op_profit_yoy_pct"], e["has_bad_event_2y"], thr)
            verdict = _score_prediction(e["judgment"], outcome)
            jg_scored_2y.append({**e, "outcome_v2": outcome, "verdict_v2": verdict})

        # Full 20 — op_profit only (no event layer for IFRS)
        full_scored = []
        for e in enriched:
            outcome = _score_v2_pure(e["op_profit_yoy_pct"], thr)
            verdict = _score_prediction(e["judgment"], outcome)
            full_scored.append({**e, "outcome_v2": outcome, "verdict_v2": verdict})

        summary[f"thr_{int(thr)}"] = {
            "threshold_pct": thr,
            "jgaap_1y": _aggregate(jg_scored_1y, f"JGAAP cohort (n=11), 1y events, ±{int(thr)}%"),
            "jgaap_2y": _aggregate(jg_scored_2y, f"JGAAP cohort (n=11), 2y events, ±{int(thr)}%"),
            "full_20": _aggregate(full_scored, f"Full 20 tickers, op_profit only, ±{int(thr)}%"),
        }

    # Print
    print("=" * 110, flush=True)
    print("RECIPE A v2 RESULTS — single-axis fundamentals + event trigger", flush=True)
    print("=" * 110, flush=True)
    for thr_key, s in summary.items():
        thr_lbl = f"±{int(s['threshold_pct'])}%"
        for variant_key in ("jgaap_1y", "jgaap_2y", "full_20"):
            agg = s[variant_key]
            print(f"\n[{thr_lbl}] {agg['label']}", flush=True)
            print(f"  total={agg['n_total']}, confident={agg['confident']}, "
                  f"hit={agg['hit']}, miss={agg['miss']}, abstain={agg['abstain']}",
                  flush=True)
            op = agg["overall_precision_pct"]
            oc = agg["overall_ci_95_pct"]
            op_s = f"{op:.1f}%" if op is not None else "n/a"
            oc_s = f"[{oc[0]:.1f}-{oc[1]:.1f}]" if oc else "n/a"
            print(f"  Overall: {op_s}  CI {oc_s}", flush=True)
            for cls, c in agg["by_class"].items():
                p = c["precision_pct"]
                ci = c["ci_95_pct"]
                p_s = f"{p:.1f}%" if p is not None else "n/a"
                ci_s = f"[{ci[0]:.1f}-{ci[1]:.1f}]" if ci else "n/a"
                print(f"    {cls:18s}: n={c['n']}, hit={c['hit']}, miss={c['miss']}, "
                      f"abstain={c['abstain']}, prec={p_s}, CI={ci_s}", flush=True)

    OUT_PATH.write_text(json.dumps({
        "methodology": "recipe_a_methodology.md (v2 single-axis, built post-v1)",
        "motivation": "Aligned to agent's single-axis claim per qualitative review of 7 demo cases",
        "thresholds_tested": THRESHOLDS,
        "n_predictions": len(enriched),
        "summary": summary,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
