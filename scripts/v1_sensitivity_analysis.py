"""V1 sensitivity analysis — comprehensive weight/threshold response surface.

Answers the PM's literal directive:
  「どこを動かすとどう精度が変化するかを見られる形にする」

Three views:
  1. 1D weight sensitivity — sweep each weight from 0 to 2x, hold others at default
  2. 1D threshold sensitivity — sweep score_pos and score_neg thresholds
  3. 2D sensitivity surface — peer_gap × profit_crash (the two strongest weights)

No new data. Pure replay over existing 111 predictions, varying V1's internal
weights and thresholds. Outputs ASCII visualization + JSON for downstream use.
"""
from __future__ import annotations
import json
import sys
import io
import math
import glob
import copy
from pathlib import Path
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent

JGAAP_ORIG = ["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697"]
JGAAP_OOS = ["4063","4716","4751","6861"]
JGAAP_EXT = ["3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
             "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"]
TRAIN_TICKERS = set(JGAAP_ORIG + JGAAP_OOS)
TEST_TICKERS = set(JGAAP_EXT)
ALL_JGAAP = TRAIN_TICKERS | TEST_TICKERS


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


def multi_axis_outcome(rev_yoy, op_yoy, stock_5d, has_bad):
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
    if has_bad: return "negative"
    if neg >= 2: return "negative"
    if pos >= 2: return "positive"
    return "mixed"


def score_pred(judgment, outcome):
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
    out = {k: None for k in ["peer_gap","op_margin_level","cfo_ni",
                              "op_profit_yoy_pred","op_profit_yoy_outcome"]}
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
            cfo_r = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
            out["cfo_ni"] = cfo_r.get("curr")
            out["op_profit_yoy_pred"] = pair.get("op_profit_delta_pct")
        if outcome_fy is not None and pair.get("curr_fiscal_year") == outcome_fy:
            out["op_profit_yoy_outcome"] = pair.get("op_profit_delta_pct")
    return out


def v1_with_config(ind, w_peer, w_margin, w_cfo, w_profit_crash, thr_pos, thr_neg):
    """V1 with fully tunable weights and thresholds."""
    score = 0.0
    if ind["peer_gap"] is not None:
        if ind["peer_gap"] > 10.0: score += w_peer
        elif ind["peer_gap"] < -5.0: score -= w_peer
    if ind["op_margin_level"] is not None:
        if ind["op_margin_level"] > 15.0: score += w_margin
        elif ind["op_margin_level"] < 5.0: score -= w_margin
    if ind["cfo_ni"] is not None:
        if ind["cfo_ni"] > 0.8: score += w_cfo
        elif ind["cfo_ni"] < 0.5: score -= w_cfo
    if ind["op_profit_yoy_pred"] is not None and ind["op_profit_yoy_pred"] < -10.0:
        score -= w_profit_crash
    if score >= thr_pos: return "growth_likely"
    if score <= thr_neg: return "growth_unlikely"
    return "uncertain"


def precision(rows, verdict, outcome_key):
    sub = [r for r in rows if r["verdict"] == verdict]
    h = sum(1 for r in sub if r[outcome_key] == "hit")
    m = sum(1 for r in sub if r[outcome_key] == "miss")
    c = h + m
    return (h/c*100 if c else None), h, c


def bar(value, scale=1.0, width=30):
    """Render a precision bar."""
    if value is None: return "n/a"
    n = int(value/100.0 * width)
    return "#" * n


def main():
    print("V1 sensitivity analysis — comprehensive weight/threshold response\n", flush=True)

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
        try: outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except: outcome_fy = None
        ind = extract_indicators(tk, p["prediction_pair"], outcome_fy)
        if ind is None: continue
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])
        outcome = multi_axis_outcome(p.get("rev_delta_pct"), ind["op_profit_yoy_outcome"],
                                     p.get("stock_5d_pct"), bool(evs_2y))
        enriched.append({
            "ticker": tk, "split": "train" if tk in TRAIN_TICKERS else "test",
            "ind": ind, "outcome": outcome,
        })

    test = [e for e in enriched if e["split"] == "test"]
    train = [e for e in enriched if e["split"] == "train"]

    DEFAULT = dict(w_peer=1.0, w_margin=1.0, w_cfo=1.0, w_profit_crash=1.5, thr_pos=1.5, thr_neg=-1.0)

    def eval_config(rows, **cfg):
        full_cfg = {**DEFAULT, **cfg}
        for r in rows:
            r["verdict"] = v1_with_config(r["ind"], **full_cfg)
            r["outcome_score"] = score_pred(r["verdict"], r["outcome"])
        return rows

    # ========================================================================
    # PART 1 — 1D weight sweeps
    # ========================================================================
    print("=" * 90, flush=True)
    print("PART 1 — 1D Weight Sweeps (TEST cohort, held-out)", flush=True)
    print("=" * 90, flush=True)
    print(f"\nBaseline (all weights default): w_peer=1.0, w_margin=1.0, w_cfo=1.0, w_profit_crash=1.5\n", flush=True)

    weight_sweeps = [
        ("w_peer",         [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]),
        ("w_margin",       [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]),
        ("w_cfo",          [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]),
        ("w_profit_crash", [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]),
    ]

    sweep_results = {}
    for w_name, values in weight_sweeps:
        print(f"\n--- Sweeping {w_name} (others at default) ---", flush=True)
        print(f"{'Value':<8}{'growth_likely TEST':<30}{'growth_unlikely TEST':<30}", flush=True)
        print("-" * 68, flush=True)
        sweep_results[w_name] = []
        for v in values:
            eval_config(test, **{w_name: v})
            gl_p, gl_h, gl_c = precision(test, "growth_likely", "outcome_score")
            gu_p, gu_h, gu_c = precision(test, "growth_unlikely", "outcome_score")
            gl_s = f"{gl_p:5.1f}% ({gl_h}/{gl_c})" if gl_p is not None else "n/a"
            gu_s = f"{gu_p:5.1f}% ({gu_h}/{gu_c})" if gu_p is not None else "n/a"
            marker = " ← default" if abs(v - DEFAULT[w_name]) < 0.01 else ""
            print(f"{v:<8.2f}{gl_s:<30}{gu_s:<30}{marker}", flush=True)
            sweep_results[w_name].append({
                "value": v, "gl_prec": gl_p, "gl_h": gl_h, "gl_c": gl_c,
                "gu_prec": gu_p, "gu_h": gu_h, "gu_c": gu_c,
            })

    # ========================================================================
    # PART 2 — Threshold sweeps
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("PART 2 — Threshold Sweeps (TEST cohort)", flush=True)
    print("=" * 90, flush=True)
    print(f"\nDefault: thr_pos=+1.5, thr_neg=-1.0\n", flush=True)

    thr_sweeps = [
        ("thr_pos", [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]),
        ("thr_neg", [-0.5, -0.75, -1.0, -1.25, -1.5, -2.0, -2.5]),
    ]
    for t_name, values in thr_sweeps:
        print(f"\n--- Sweeping {t_name} (others at default) ---", flush=True)
        print(f"{'Value':<8}{'growth_likely TEST':<30}{'growth_unlikely TEST':<30}", flush=True)
        print("-" * 68, flush=True)
        for v in values:
            eval_config(test, **{t_name: v})
            gl_p, gl_h, gl_c = precision(test, "growth_likely", "outcome_score")
            gu_p, gu_h, gu_c = precision(test, "growth_unlikely", "outcome_score")
            gl_s = f"{gl_p:5.1f}% ({gl_h}/{gl_c})" if gl_p is not None else "n/a"
            gu_s = f"{gu_p:5.1f}% ({gu_h}/{gu_c})" if gu_p is not None else "n/a"
            marker = " ← default" if abs(v - DEFAULT[t_name]) < 0.01 else ""
            print(f"{v:<8.2f}{gl_s:<30}{gu_s:<30}{marker}", flush=True)

    # ========================================================================
    # PART 3 — 2D sensitivity surface (peer_gap × profit_crash)
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("PART 3 — 2D surface: peer_gap weight × profit_crash weight (TEST cohort)", flush=True)
    print("=" * 90, flush=True)
    print("\nrows = w_peer, cols = w_profit_crash. Cell = growth_likely precision (and n)\n", flush=True)

    peer_vals = [0.0, 0.5, 1.0, 1.5, 2.0]
    crash_vals = [0.0, 0.5, 1.0, 1.5, 2.0]

    # Header
    hdr = "w_peer\\crash"
    print(f"{hdr:<14}", end="", flush=True)
    for c in crash_vals:
        print(f"{c:<14.1f}", end="", flush=True)
    print()
    print("-" * (14 + 14*len(crash_vals)), flush=True)

    for p in peer_vals:
        print(f"{p:<14.1f}", end="", flush=True)
        for c in crash_vals:
            eval_config(test, w_peer=p, w_profit_crash=c)
            gl_p, gl_h, gl_c = precision(test, "growth_likely", "outcome_score")
            if gl_p is None:
                cell = "n/a"
            else:
                cell = f"{gl_p:.0f}%({gl_h}/{gl_c})"
                if abs(p - 1.0) < 0.01 and abs(c - 1.5) < 0.01:
                    cell += "*"
            print(f"{cell:<14}", end="", flush=True)
        print()

    print("\n  * = default config")

    # Same for growth_unlikely
    print("\nSame surface for growth_unlikely:\n", flush=True)
    hdr2 = "w_peer\\crash"
    print(f"{hdr2:<14}", end="", flush=True)
    for c in crash_vals:
        print(f"{c:<14.1f}", end="", flush=True)
    print()
    print("-" * (14 + 14*len(crash_vals)), flush=True)
    for p in peer_vals:
        print(f"{p:<14.1f}", end="", flush=True)
        for c in crash_vals:
            eval_config(test, w_peer=p, w_profit_crash=c)
            gu_p, gu_h, gu_c = precision(test, "growth_unlikely", "outcome_score")
            if gu_p is None:
                cell = "n/a"
            else:
                cell = f"{gu_p:.0f}%({gu_h}/{gu_c})"
                if abs(p - 1.0) < 0.01 and abs(c - 1.5) < 0.01:
                    cell += "*"
            print(f"{cell:<14}", end="", flush=True)
        print()

    # ========================================================================
    # PART 4 — Robustness summary: how much does V1 fluctuate?
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("PART 4 — Robustness summary", flush=True)
    print("=" * 90, flush=True)

    print("\nFor each indicator weight, the precision RANGE seen across [0, 2.0] sweep:", flush=True)
    print(f"\n  {'Weight':<18}{'growth_likely range':<32}{'growth_unlikely range':<32}", flush=True)
    print("  " + "-" * 82, flush=True)
    for w_name in ("w_peer", "w_margin", "w_cfo", "w_profit_crash"):
        results = sweep_results[w_name]
        gl_vals = [r["gl_prec"] for r in results if r["gl_prec"] is not None]
        gu_vals = [r["gu_prec"] for r in results if r["gu_prec"] is not None]
        if gl_vals and gu_vals:
            print(f"  {w_name:<18}{min(gl_vals):.1f}% — {max(gl_vals):.1f}% "
                  f"(span {max(gl_vals)-min(gl_vals):.1f}pp){'':<10}"
                  f"{min(gu_vals):.1f}% — {max(gu_vals):.1f}% "
                  f"(span {max(gu_vals)-min(gu_vals):.1f}pp)", flush=True)

    # ========================================================================
    # PART 5 — best config search (just for reference, not adoption)
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("PART 5 — Reference: best growth_likely precision in the entire grid", flush=True)
    print("(NOT recommending adoption — this is in-sample optimization)", flush=True)
    print("=" * 90, flush=True)
    best_gl = -1
    best_cfg = None
    for wp in peer_vals:
        for wm in [0.0, 0.5, 1.0, 1.5, 2.0]:
            for wc in [0.0, 0.5, 1.0, 1.5, 2.0]:
                for wpc in crash_vals:
                    eval_config(test, w_peer=wp, w_margin=wm, w_cfo=wc, w_profit_crash=wpc)
                    gl_p, gl_h, gl_c = precision(test, "growth_likely", "outcome_score")
                    if gl_p is not None and gl_c >= 10 and gl_p > best_gl:
                        best_gl = gl_p
                        best_cfg = (wp, wm, wc, wpc, gl_h, gl_c)
    if best_cfg:
        wp, wm, wc, wpc, h, c = best_cfg
        print(f"\nBest TEST growth_likely precision: {best_gl:.1f}% ({h}/{c})", flush=True)
        print(f"  w_peer={wp}, w_margin={wm}, w_cfo={wc}, w_profit_crash={wpc}", flush=True)
        print(f"  (Default config: 57.9%. Best-found config: {best_gl:.1f}%. Lift: {best_gl-57.9:+.1f}pp)", flush=True)
        print(f"  CAVEAT: this is in-sample optimization. Real held-out lift = 0.", flush=True)

    out = ROOT / "outputs" / "v1_sensitivity_results.json"
    out.write_text(json.dumps({"sweeps": sweep_results, "default": DEFAULT},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
