"""Per-class indicator weighting — pattern analysis + class-specific scorer.

Methodology pre-registered at outputs/per_class_weights_methodology.md
(LOCKED before this script ran).

Steps:
  1. For each indicator × class × vote: count hits/misses on TRAIN cohort.
  2. Derive class-specific weights from TRAIN patterns.
  3. Build V1-cs scorer with class-specific weights.
  4. Evaluate on TRAIN and held-out TEST. Compare to vanilla V1 and LLM.
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
TRAIN_TICKERS = set(JGAAP_ORIG + JGAAP_OOS)
TEST_TICKERS = set(JGAAP_EXT)
ALL_JGAAP = TRAIN_TICKERS | TEST_TICKERS


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


def score(judgment, outcome):
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
    out = {k: None for k in ["peer_gap","op_margin_level","goodwill","cfo_ni",
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
            bs_hist = pair.get("bs_quality_history") or []
            if bs_hist:
                out["goodwill"] = bs_hist[-1].get("goodwill_to_equity_pct")
            cfo_r = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
            out["cfo_ni"] = cfo_r.get("curr")
            out["op_profit_yoy_pred"] = pair.get("op_profit_delta_pct")
        if outcome_fy is not None and pair.get("curr_fiscal_year") == outcome_fy:
            out["op_profit_yoy_outcome"] = pair.get("op_profit_delta_pct")
    return out


# ============================================================================
# Indicator vote functions — each returns "pos", "neg", or "neutral"
# ============================================================================
def vote_peer_gap(v):
    if v is None: return "neutral"
    if v > 10.0: return "pos"
    if v < -5.0: return "neg"
    return "neutral"


def vote_margin(v):
    if v is None: return "neutral"
    if v > 15.0: return "pos"
    if v < 5.0: return "neg"
    return "neutral"


def vote_goodwill(v):
    if v is None: return "neutral"
    if v > 30.0: return "neg"
    return "neutral"  # asymmetric


def vote_cfo(v):
    if v is None: return "neutral"
    if v > 0.8: return "pos"
    if v < 0.5: return "neg"
    return "neutral"


def vote_profit_crash(v):
    if v is None: return "neutral"
    if v < -10.0: return "neg"
    return "neutral"  # asymmetric


VOTE_FNS = {
    "peer_gap": vote_peer_gap,
    "op_margin_level": vote_margin,
    "goodwill": vote_goodwill,
    "cfo_ni": vote_cfo,
    "profit_crash": vote_profit_crash,
}


def get_votes(ind):
    """Return dict of indicator → vote (pos/neg/neutral)."""
    return {
        "peer_gap": vote_peer_gap(ind["peer_gap"]),
        "op_margin_level": vote_margin(ind["op_margin_level"]),
        "goodwill": vote_goodwill(ind["goodwill"]),
        "cfo_ni": vote_cfo(ind["cfo_ni"]),
        "profit_crash": vote_profit_crash(ind["op_profit_yoy_pred"]),
    }


def precision_block(rows, score_key):
    h = sum(1 for r in rows if r[score_key] == "hit")
    m = sum(1 for r in rows if r[score_key] == "miss")
    c = h + m
    return h, m, c, (h/c*100 if c else None)


def main():
    print("Per-class indicator weighting — analysis + scorer\n", flush=True)
    print("Methodology: outputs/per_class_weights_methodology.md (LOCKED)\n", flush=True)

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
        votes = get_votes(ind)
        enriched.append({
            "ticker": tk, "prediction_pair": p["prediction_pair"],
            "split": "train" if tk in TRAIN_TICKERS else "test",
            "llm_verdict": p["judgment"],
            "outcome": outcome,
            "llm_score": score(p["judgment"], outcome),
            "votes": votes,
            **ind,
        })

    train = [e for e in enriched if e["split"] == "train"]
    test = [e for e in enriched if e["split"] == "test"]

    # ========================================================================
    # STEP 1 — Pattern analysis on TRAIN
    # ========================================================================
    print("=" * 100, flush=True)
    print("STEP 1 — Indicator × class × vote hit-rate analysis on TRAIN", flush=True)
    print("=" * 100, flush=True)

    indicators = list(VOTE_FNS.keys())
    # For each class, baseline hit rate
    baselines = {}
    for cls in ("growth_likely", "growth_unlikely"):
        sub = [e for e in train if e["llm_verdict"] == cls]
        h = sum(1 for e in sub if e["llm_score"] == "hit")
        c = sum(1 for e in sub if e["llm_score"] in ("hit", "miss"))
        baselines[cls] = h/c*100 if c else 0
        print(f"\n  TRAIN baseline LLM {cls}: {baselines[cls]:.1f}% ({h}/{c})", flush=True)

    print(f"\n{'Indicator':<20}{'Vote':<10}{'Class':<22}{'n':<6}{'hits':<6}{'hit-rate':<12}{'vs base':<10}", flush=True)
    print("-" * 86, flush=True)

    indicator_class_votes = {}  # (ind, vote, class) -> (h, c, rate, delta)
    for ind_name in indicators:
        for vote in ("pos", "neg", "neutral"):
            for cls in ("growth_likely", "growth_unlikely"):
                sub = [e for e in train if e["votes"][ind_name] == vote and e["llm_verdict"] == cls]
                h = sum(1 for e in sub if e["llm_score"] == "hit")
                c = sum(1 for e in sub if e["llm_score"] in ("hit", "miss"))
                if c == 0: continue
                rate = h/c*100
                delta = rate - baselines[cls]
                indicator_class_votes[(ind_name, vote, cls)] = (h, c, rate, delta)
                marker = " ★" if abs(delta) >= 10 and c >= 3 else ""
                print(f"  {ind_name:<18}{vote:<10}{cls:<22}{c:<6}{h:<6}"
                      f"{rate:5.1f}%      {delta:+5.1f}pp{marker}", flush=True)

    # ========================================================================
    # STEP 2 — Derive class-specific weights from TRAIN patterns
    # ========================================================================
    print("\n" + "=" * 100, flush=True)
    print("STEP 2 — Derive class-specific weights from TRAIN", flush=True)
    print("=" * 100, flush=True)
    print("\nRule (locked): weight_for_class = max(0, hit-rate-when-aligned-vote − baseline)/baseline, clamped to [0, 2.0]", flush=True)
    print("Where 'aligned vote' = pos for growth_likely / neg for growth_unlikely.\n", flush=True)

    weights_bullish = {}
    weights_bearish = {}
    for ind_name in indicators:
        # Bullish weight: how much does POS vote help growth_likely?
        key = (ind_name, "pos", "growth_likely")
        if key in indicator_class_votes:
            h, c, rate, delta = indicator_class_votes[key]
            if c >= 3 and delta > 0:
                w_bull = min(2.0, delta / 25.0 + 0.5)  # scale: +25pp lift → weight 1.5
            else:
                w_bull = 0.0
        else:
            w_bull = 0.0
        # Bearish weight: how much does NEG vote help growth_unlikely?
        key = (ind_name, "neg", "growth_unlikely")
        if key in indicator_class_votes:
            h, c, rate, delta = indicator_class_votes[key]
            if c >= 3 and delta > 0:
                w_bear = min(2.0, delta / 25.0 + 0.5)
            else:
                w_bear = 0.0
        else:
            w_bear = 0.0
        weights_bullish[ind_name] = round(w_bull, 2)
        weights_bearish[ind_name] = round(w_bear, 2)
        print(f"  {ind_name:<20}bullish weight = {w_bull:.2f}    bearish weight = {w_bear:.2f}", flush=True)

    # ========================================================================
    # STEP 3 — Build class-specific scorer
    # ========================================================================
    def verdict_cs(votes, w_bull, w_bear, thresh_bull=1.5, thresh_bear=1.5):
        bull_score = sum(w_bull[i] for i, v in votes.items() if v == "pos")
        bear_score = sum(w_bear[i] for i, v in votes.items() if v == "neg")
        # Allow growth_likely only if bullish is strong AND bearish isn't
        if bull_score >= thresh_bull and bear_score < thresh_bear:
            return "growth_likely", bull_score, bear_score
        if bear_score >= thresh_bear and bull_score < thresh_bull:
            return "growth_unlikely", bull_score, bear_score
        return "uncertain", bull_score, bear_score

    for e in enriched:
        v, bs, brs = verdict_cs(e["votes"], weights_bullish, weights_bearish)
        e["cs_verdict"] = v
        e["cs_bull"] = bs
        e["cs_bear"] = brs
        e["cs_score"] = score(v, e["outcome"])

    # ========================================================================
    # STEP 4 — Evaluate
    # ========================================================================
    print("\n" + "=" * 100, flush=True)
    print("STEP 4 — V1-cs (class-specific) vs vanilla V1 vs LLM", flush=True)
    print("=" * 100, flush=True)

    # Need vanilla V1 verdicts — re-load from v2 results
    with open(ROOT / "outputs" / "code_based_scorer_v2_results.json", encoding="utf-8") as f:
        v2 = json.load(f)
    v1_lookup = {(r["ticker"], r["prediction_pair"]): r["code_v1_verdict"] for r in v2["rows"]}
    for e in enriched:
        e["v1_verdict"] = v1_lookup.get((e["ticker"], e["prediction_pair"]), "uncertain")
        e["v1_score"] = score(e["v1_verdict"], e["outcome"])

    def report(cohort, label):
        print(f"\n  {label}  (n={len(cohort)})", flush=True)
        print(f"  {'Source':<14}{'Class':<22}{'precision':<32}", flush=True)
        print("  " + "-" * 68, flush=True)
        for src, key in [("LLM", ("llm_verdict","llm_score")),
                         ("V1", ("v1_verdict","v1_score")),
                         ("V1-cs", ("cs_verdict","cs_score"))]:
            for cls in ("growth_likely", "growth_unlikely"):
                sub = [e for e in cohort if e[key[0]] == cls]
                h, m, c, p = precision_block(sub, key[1])
                if c > 0:
                    ci = _wilson(h, c)
                    print(f"  {src:<14}{cls:<22}{p:5.1f}% ({h}/{c}) CI [{ci[0]:.1f}-{ci[1]:.1f}]", flush=True)
                else:
                    print(f"  {src:<14}{cls:<22}n/a (n=0)", flush=True)

    report(train, "TRAIN")
    report(test, "TEST — held-out")
    report(enriched, "FULL")

    # Save
    out = ROOT / "outputs" / "per_class_weights_results.json"
    out.write_text(json.dumps({
        "weights_bullish": weights_bullish,
        "weights_bearish": weights_bearish,
        "baselines": baselines,
        "indicator_class_votes": {f"{k[0]}|{k[1]}|{k[2]}": v for k,v in indicator_class_votes.items()},
        "n_total": len(enriched),
        "rows": enriched,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
