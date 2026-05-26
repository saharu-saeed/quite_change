"""Beta estimator + α-adjusted outcome scoring.

Two-part script:
  PART A — estimate β per JGAAP ticker against TOPIX (1306) using the full
           available daily-price history. OLS, split-adjusted prices.
  PART B — re-compute the 5-day post-filing stock axis as α (= raw - β·TOPIX),
           re-run multi-axis outcome scoring, compare precision against the
           raw-stock version.

If part B shows precision improvement, this becomes the new outcome
metric. If it doesn't, document and move on. Pre-registration discipline.
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
PRICES_DIR = ROOT / "data" / "tempest"
TOPIX_TICKER = "1306"

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


def load_prices_adjusted(ticker):
    """Return {date_str: close_adj}. Split-adjusted via daily-ratio scan."""
    p = PRICES_DIR / ticker / "prices.json"
    if not p.exists(): return {}
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    rows = sorted(d["data"], key=lambda r: r["date"])
    closes = [float(r["close"]) for r in rows]
    dates = [r["date"] for r in rows]
    adj_factor = 1.0
    adjusted = [0.0] * len(closes)
    for i in range(len(closes) - 1, 0, -1):
        adjusted[i] = closes[i] * adj_factor
        ratio = closes[i] / closes[i - 1]
        if ratio < 0.5 or ratio > 2.0:
            adj_factor *= ratio
    adjusted[0] = closes[0] * adj_factor
    return {dates[i]: adjusted[i] for i in range(len(closes))}


def ols_beta(x, y):
    """Simple OLS: y = a + b*x. Returns (alpha, beta, r2, n)."""
    n = len(x)
    if n < 30: return None, None, None, n
    mx = sum(x)/n
    my = sum(y)/n
    cov = sum((x[i]-mx)*(y[i]-my) for i in range(n)) / n
    vx = sum((x[i]-mx)**2 for i in range(n)) / n
    vy = sum((y[i]-my)**2 for i in range(n)) / n
    if vx == 0: return None, None, None, n
    b = cov / vx
    a = my - b * mx
    r2 = (cov*cov) / (vx*vy) if vy > 0 else 0
    return a, b, r2, n


def daily_returns(prices_dict, ref_dates):
    """Given prices and a sorted list of trading-day dates, returns list of (date, return)."""
    sorted_dates = sorted([d for d in ref_dates if d in prices_dict])
    rets = []
    for i in range(1, len(sorted_dates)):
        d, dprev = sorted_dates[i], sorted_dates[i-1]
        if prices_dict[dprev] > 0:
            rets.append((d, prices_dict[d] / prices_dict[dprev] - 1))
    return rets


def nearest_on_or_after(prices, target):
    sorted_dates = sorted(prices.keys())
    for d in sorted_dates:
        if d >= target: return prices[d], d
    return None, None


def find_window_return(prices, start_date, days=5):
    """Return % return from start_date to ~5 trading days later."""
    start_px, start_actual = nearest_on_or_after(prices, start_date)
    if start_px is None: return None
    sorted_dates = sorted(prices.keys())
    try:
        idx = sorted_dates.index(start_actual)
    except ValueError:
        return None
    end_idx = idx + days
    if end_idx >= len(sorted_dates): return None
    end_px = prices[sorted_dates[end_idx]]
    return (end_px / start_px - 1) * 100


def multi_axis_outcome(rev_yoy, op_yoy, stock_axis_pct, has_bad_event):
    pos = neg = 0
    if rev_yoy is not None:
        if rev_yoy >= 3.0: pos += 1
        elif rev_yoy <= -3.0: neg += 1
    if op_yoy is not None:
        if op_yoy >= 5.0: pos += 1
        elif op_yoy <= -5.0: neg += 1
    if stock_axis_pct is not None:
        if stock_axis_pct >= 5.0: pos += 1
        elif stock_axis_pct <= -5.0: neg += 1
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


def main():
    print("Beta estimator + α-adjusted outcome scoring\n", flush=True)

    # ========================================================================
    # PART A — estimate β per ticker against TOPIX 1306
    # ========================================================================
    print("=" * 90, flush=True)
    print("PART A — Beta estimation per ticker (full sample, daily returns vs TOPIX 1306)", flush=True)
    print("=" * 90, flush=True)

    topix = load_prices_adjusted(TOPIX_TICKER)
    topix_dates = sorted(topix.keys())
    print(f"\nTOPIX 1306: {len(topix)} trading days  "
          f"({min(topix_dates)} → {max(topix_dates)})", flush=True)

    # TOPIX daily returns
    topix_rets = {}
    for i in range(1, len(topix_dates)):
        d, dp = topix_dates[i], topix_dates[i-1]
        if topix[dp] > 0:
            topix_rets[d] = topix[d] / topix[dp] - 1

    betas = {}
    print(f"\n{'Ticker':<8}{'β':<8}{'α (daily %)':<14}{'R²':<8}{'n_days':<8}", flush=True)
    print("-" * 50, flush=True)
    for tk in sorted(ALL_JGAAP):
        prices = load_prices_adjusted(tk)
        if not prices: continue
        ticker_dates = sorted(prices.keys())
        ticker_rets = {}
        for i in range(1, len(ticker_dates)):
            d, dp = ticker_dates[i], ticker_dates[i-1]
            if prices[dp] > 0:
                ticker_rets[d] = prices[d] / prices[dp] - 1
        # Align on common dates
        common = sorted(set(ticker_rets.keys()) & set(topix_rets.keys()))
        if len(common) < 60:
            print(f"{tk:<8}insufficient data ({len(common)} days)", flush=True)
            continue
        x = [topix_rets[d] for d in common]
        y = [ticker_rets[d] for d in common]
        a, b, r2, n = ols_beta(x, y)
        if b is None:
            print(f"{tk:<8}regression failed", flush=True)
            continue
        betas[tk] = {"alpha_daily_pct": a*100, "beta": b, "r2": r2, "n_days": n}
        print(f"{tk:<8}{b:<8.3f}{a*100:<14.4f}{r2:<8.3f}{n:<8}", flush=True)

    # Save betas
    beta_path = ROOT / "outputs" / "ticker_betas.json"
    beta_path.write_text(json.dumps(betas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {beta_path}", flush=True)

    avg_beta = sum(b["beta"] for b in betas.values()) / len(betas) if betas else 0
    print(f"\nAverage β across {len(betas)} tickers: {avg_beta:.3f}", flush=True)
    print("(β=1.0 means moves 1:1 with TOPIX; β>1 more volatile; β<1 less)", flush=True)

    # ========================================================================
    # PART B — compute α-5d for each prediction and re-run multi-axis
    # ========================================================================
    print("\n" + "=" * 90, flush=True)
    print("PART B — α-adjusted 5-day stock axis under multi-axis outcome", flush=True)
    print("=" * 90, flush=True)

    event_reg = defaultdict(list)
    for tk in ALL_JGAAP:
        for ev in detect_events(tk):
            event_reg[(ev[0], ev[1])].append(ev[2])

    # Load predictions
    all_preds = []
    for path in [ROOT/"outputs"/"rolling_window_backtest.json",
                 ROOT/"outputs"/"out_of_sample_rolling_window.json",
                 ROOT/"outputs"/"jgaap_extension_rolling_window.json"]:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        all_preds.extend(d["scored_predictions"])

    # Need filing date — pull from cached agent pairs
    def get_filing_date(ticker, pair_label):
        cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                           f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if not cache_files: return None
        with open(cache_files[-1], encoding="utf-8") as f:
            d = json.load(f)
        for pair in d.get("pairs", []):
            if pair.get("history_only"): continue
            lbl = f"FY{pair['prev_fiscal_year']}->FY{pair['curr_fiscal_year']}"
            if lbl == pair_label:
                return pair.get("curr_filing_date")
        return None

    def get_op_yoy_outcome(ticker, outcome_fy):
        cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                           f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if not cache_files: return None
        with open(cache_files[-1], encoding="utf-8") as f:
            d = json.load(f)
        for pair in d.get("pairs", []):
            if pair.get("history_only"): continue
            if pair.get("curr_fiscal_year") == outcome_fy:
                return pair.get("op_profit_delta_pct")
        return None

    price_cache = {}

    enriched = []
    for p in all_preds:
        tk = p["ticker"]
        if tk not in ALL_JGAAP: continue
        if tk not in betas: continue
        if p["judgment"] == "uncertain": continue
        if tk not in price_cache:
            price_cache[tk] = load_prices_adjusted(tk)
        prices = price_cache[tk]

        # Outcome filing date drives the 5-day window
        try: outcome_fy = int(p["outcome_pair"].split("->")[1].replace("FY", ""))
        except: outcome_fy = None
        outcome_filing = get_filing_date(tk, p["outcome_pair"])
        if outcome_filing is None: continue

        raw_5d = find_window_return(prices, outcome_filing, days=5)
        topix_5d = find_window_return(topix, outcome_filing, days=5)
        if raw_5d is None or topix_5d is None: continue

        beta = betas[tk]["beta"]
        alpha_5d = raw_5d - beta * topix_5d

        op_yoy = get_op_yoy_outcome(tk, outcome_fy)
        evs_2y = []
        if outcome_fy is not None:
            evs_2y = event_reg.get((tk, outcome_fy), []) + event_reg.get((tk, outcome_fy + 1), [])

        outcome_raw = multi_axis_outcome(p.get("rev_delta_pct"), op_yoy, raw_5d, bool(evs_2y))
        outcome_alpha = multi_axis_outcome(p.get("rev_delta_pct"), op_yoy, alpha_5d, bool(evs_2y))

        enriched.append({
            "ticker": tk, "prediction_pair": p["prediction_pair"],
            "outcome_pair": p["outcome_pair"], "outcome_filing": outcome_filing,
            "judgment": p["judgment"],
            "raw_5d": raw_5d, "topix_5d": topix_5d, "beta": beta, "alpha_5d": alpha_5d,
            "outcome_raw": outcome_raw, "outcome_alpha": outcome_alpha,
            "verdict_raw": score_pred(p["judgment"], outcome_raw),
            "verdict_alpha": score_pred(p["judgment"], outcome_alpha),
        })

    print(f"\nEnriched {len(enriched)} predictions with α-adjusted axis\n", flush=True)

    # Compare precision raw vs alpha
    for cls in ("growth_likely", "growth_unlikely"):
        sub = [e for e in enriched if e["judgment"] == cls]
        raw_h = sum(1 for r in sub if r["verdict_raw"] == "hit")
        raw_m = sum(1 for r in sub if r["verdict_raw"] == "miss")
        a_h = sum(1 for r in sub if r["verdict_alpha"] == "hit")
        a_m = sum(1 for r in sub if r["verdict_alpha"] == "miss")
        raw_c = raw_h + raw_m
        a_c = a_h + a_m
        raw_p = raw_h/raw_c*100 if raw_c else 0
        a_p = a_h/a_c*100 if a_c else 0
        raw_ci = _wilson(raw_h, raw_c)
        a_ci = _wilson(a_h, a_c)
        print(f"{cls}  n={len(sub)}", flush=True)
        print(f"  raw stock 5d:    {raw_p:5.1f}% ({raw_h}/{raw_c}) CI [{raw_ci[0]:.1f}-{raw_ci[1]:.1f}]", flush=True)
        print(f"  α-adjusted 5d:   {a_p:5.1f}% ({a_h}/{a_c}) CI [{a_ci[0]:.1f}-{a_ci[1]:.1f}]", flush=True)
        print(f"  Δ: {a_p - raw_p:+.1f}pp", flush=True)
        print()

    # How many outcomes flipped because of α?
    flipped = sum(1 for e in enriched if e["outcome_raw"] != e["outcome_alpha"])
    print(f"Outcomes that changed under α-adjustment: {flipped}/{len(enriched)} ({flipped/len(enriched)*100:.1f}%)", flush=True)

    # Save
    out_path = ROOT / "outputs" / "beta_alpha_results.json"
    out_path.write_text(json.dumps({
        "betas": betas, "n_enriched": len(enriched), "rows": enriched,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)


if __name__ == "__main__":
    main()
