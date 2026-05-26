"""Recipe A — sector-adjusted variant.

Same as backtest_recipe_a.py but uses **sector-adjusted return** as Axis 2,
matching the locked methodology spec at outputs/recipe_a_methodology.md.

Sector-adj = raw filing-to-filing return − median return of OTHER cached
tickers in the same JPX 33業種 sector over the same calendar window.

The 20-ticker test set is overwhelmingly in 情報・通信業 (Information &
Communication): 19/20 cached tickers, plus 9719 SCSK treated as 情報・通信業
(missing JPX classification — business is clearly IT services).

Reports side-by-side with TOPIX-adj Recipe A so the difference between
the two denoising methods is visible.
"""
from __future__ import annotations
import json
import sys
import io
import math
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.tools.jpx_industries import lookup as jpx_lookup  # noqa: E402

CACHE_DIR = ROOT / "outputs" / "agent_cache"
ROLLING_PATH = ROOT / "outputs" / "rolling_window_backtest.json"
OUT_PATH = ROOT / "outputs" / "recipe_a_sector_results.json"
PRICES_DIR = ROOT / "data" / "tempest"
THRESHOLDS = [3.0, 5.0, 10.0]
SECTOR_LABEL = "情報・通信業"
# 9719 SCSK is IT services but lacks JPX classification in our master snapshot
SECTOR_OVERRIDES = {"9719": SECTOR_LABEL}


def _load_prices_adjusted(ticker: str) -> dict[str, float]:
    p = PRICES_DIR / ticker / "prices.json"
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    rows = sorted(d["data"], key=lambda r: r["date"])
    closes = [float(r["close"]) for r in rows]
    dates = [r["date"] for r in rows]
    adj_factor = 1.0
    adjusted: list[float] = [0.0] * len(closes)
    for i in range(len(closes) - 1, 0, -1):
        adjusted[i] = closes[i] * adj_factor
        ratio = closes[i] / closes[i - 1]
        if ratio < 0.5 or ratio > 2.0:
            adj_factor *= ratio
    adjusted[0] = closes[0] * adj_factor
    return {dates[i]: adjusted[i] for i in range(len(closes))}


def _nearest_price_on_or_after(prices: dict[str, float], target: str) -> float | None:
    keys = sorted(k for k in prices.keys() if k >= target)
    return prices[keys[0]] if keys else None


def _wilson_ci(hits: int, n: int, z: float = 1.96):
    if n == 0:
        return (None, None)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    rad = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, (center - rad) * 100), min(100.0, (center + rad) * 100))


def _load_pair_data(ticker: str) -> list[dict]:
    matches = sorted(CACHE_DIR.glob(f"{ticker}_min2020_simp1_cutoffnone_*_v5_*.json"))
    if not matches:
        raise FileNotFoundError(f"No cached pair data for {ticker}")
    with open(matches[-1], encoding="utf-8") as f:
        d = json.load(f)
    pairs = [p for p in d.get("pairs", []) if not p.get("history_only")]
    pairs.sort(key=lambda p: p.get("curr_period_end", ""))
    return pairs


def _ticker_sector(tk: str) -> str | None:
    if tk in SECTOR_OVERRIDES:
        return SECTOR_OVERRIDES[tk]
    rec = jpx_lookup(tk)
    return rec.label33 if rec else None


def _build_sector_peers() -> dict[str, list[str]]:
    """Map sector label → list of tickers in our cache."""
    out: dict[str, list[str]] = {}
    for d in PRICES_DIR.iterdir():
        if not d.is_dir() or not d.name.isdigit():
            continue
        s = _ticker_sector(d.name)
        if s:
            out.setdefault(s, []).append(d.name)
    return out


def _score_outcome(op_yoy, sec_adj_ret, threshold):
    if op_yoy is None or sec_adj_ret is None:
        return "n/a"
    if op_yoy >= threshold and sec_adj_ret >= threshold:
        return "positive"
    if op_yoy <= -threshold and sec_adj_ret <= -threshold:
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


def main() -> int:
    print("Recipe A — sector-adjusted variant", flush=True)
    print(f"Sector: {SECTOR_LABEL}", flush=True)
    print(f"Thresholds: ±{THRESHOLDS[0]}%, ±{THRESHOLDS[1]}%, ±{THRESHOLDS[2]}%\n", flush=True)

    with open(ROLLING_PATH, encoding="utf-8") as f:
        roll = json.load(f)
    preds_in = roll["scored_predictions"]
    print(f"Loaded {len(preds_in)} predictions.\n", flush=True)

    # Build peer cohort
    peers_by_sector = _build_sector_peers()
    info_comm_peers = peers_by_sector.get(SECTOR_LABEL, [])
    print(f"{SECTOR_LABEL} peer cohort: {len(info_comm_peers)} tickers", flush=True)
    print(f"  {info_comm_peers}\n", flush=True)

    # Load prices for all peers
    print("Loading prices for peer cohort…", flush=True)
    peer_prices: dict[str, dict[str, float]] = {}
    for tk in info_comm_peers:
        peer_prices[tk] = _load_prices_adjusted(tk)
    print(f"  Loaded {len(peer_prices)} peer price series.\n", flush=True)

    pair_cache: dict[str, list[dict]] = {}
    enriched: list[dict] = []
    for row in preds_in:
        tk = row["ticker"]
        if tk not in pair_cache:
            try:
                pair_cache[tk] = _load_pair_data(tk)
            except FileNotFoundError:
                continue
        pairs = pair_cache[tk]

        def match(p, label):
            return f"FY{p['prev_fiscal_year']}->FY{p['curr_fiscal_year']}" == label

        pred_pair = next((p for p in pairs if match(p, row["prediction_pair"])), None)
        out_pair = next((p for p in pairs if match(p, row["outcome_pair"])), None)
        if pred_pair is None or out_pair is None:
            continue

        op_yoy = out_pair.get("op_profit_delta_pct")
        start_date = pred_pair.get("curr_filing_date")
        end_date = out_pair.get("curr_filing_date")
        stock_ret = None
        peer_returns: list[float] = []
        sec_med = None
        sec_adj = None

        if start_date and end_date and start_date < end_date:
            # Own return
            if tk in peer_prices:
                own_prices = peer_prices[tk]
                p_start = _nearest_price_on_or_after(own_prices, start_date)
                p_end = _nearest_price_on_or_after(own_prices, end_date)
                if p_start and p_end:
                    stock_ret = (p_end / p_start - 1) * 100

            # Peer cohort returns (excluding self)
            for peer in info_comm_peers:
                if peer == tk:
                    continue
                pp = peer_prices.get(peer)
                if not pp:
                    continue
                p_s = _nearest_price_on_or_after(pp, start_date)
                p_e = _nearest_price_on_or_after(pp, end_date)
                if p_s and p_e:
                    peer_returns.append((p_e / p_s - 1) * 100)
            if peer_returns:
                peer_returns_sorted = sorted(peer_returns)
                n = len(peer_returns_sorted)
                sec_med = (peer_returns_sorted[n // 2] if n % 2
                           else (peer_returns_sorted[n // 2 - 1] + peer_returns_sorted[n // 2]) / 2)
            if stock_ret is not None and sec_med is not None:
                sec_adj = stock_ret - sec_med

        enriched.append({
            "ticker": tk,
            "prediction_pair": row["prediction_pair"],
            "outcome_pair": row["outcome_pair"],
            "judgment": row["judgment"],
            "old_verdict": row.get("verdict"),
            "op_profit_yoy_pct": op_yoy,
            "filing_start": start_date,
            "filing_end": end_date,
            "raw_stock_ret_pct": round(stock_ret, 2) if stock_ret is not None else None,
            "sector_median_ret_pct": round(sec_med, 2) if sec_med is not None else None,
            "sector_adj_ret_pct": round(sec_adj, 2) if sec_adj is not None else None,
            "n_peers_used": len(peer_returns),
        })

    summary: dict[str, dict] = {}
    for thr in THRESHOLDS:
        scored = []
        for e in enriched:
            outcome = _score_outcome(e["op_profit_yoy_pct"], e["sector_adj_ret_pct"], thr)
            verdict = _score_prediction(e["judgment"], outcome)
            scored.append({**e, "outcome_at_thr": outcome, "verdict_at_thr": verdict})

        total = len(scored)
        n_a = sum(1 for s in scored if s["verdict_at_thr"] == "n/a")
        abstain = sum(1 for s in scored if s["verdict_at_thr"] == "abstain")
        hit = sum(1 for s in scored if s["verdict_at_thr"] == "hit")
        miss = sum(1 for s in scored if s["verdict_at_thr"] == "miss")
        confident = hit + miss
        overall_prec = (hit / confident * 100) if confident else None
        overall_ci = _wilson_ci(hit, confident)

        by_class: dict[str, dict] = {}
        for cls in ("growth_likely", "growth_unlikely", "uncertain"):
            cls_rows = [s for s in scored if s["judgment"] == cls]
            cls_hit = sum(1 for s in cls_rows if s["verdict_at_thr"] == "hit")
            cls_miss = sum(1 for s in cls_rows if s["verdict_at_thr"] == "miss")
            cls_abs = sum(1 for s in cls_rows if s["verdict_at_thr"] == "abstain")
            cls_conf = cls_hit + cls_miss
            cls_prec = (cls_hit / cls_conf * 100) if cls_conf else None
            cls_ci = _wilson_ci(cls_hit, cls_conf)
            cls_na = sum(1 for s in cls_rows if s["verdict_at_thr"] == "n/a")
            by_class[cls] = {
                "n": len(cls_rows), "hit": cls_hit, "miss": cls_miss,
                "abstain": cls_abs, "n_a": cls_na,
                "precision_pct": round(cls_prec, 1) if cls_prec is not None else None,
                "ci_95_pct": (round(cls_ci[0], 1), round(cls_ci[1], 1))
                              if cls_ci[0] is not None else None,
            }

        summary[f"thr_{int(thr)}"] = {
            "threshold_pct": thr, "total": total,
            "hit": hit, "miss": miss, "abstain": abstain, "n_a": n_a,
            "confident": confident,
            "overall_precision_pct": round(overall_prec, 1) if overall_prec is not None else None,
            "overall_ci_95_pct": (round(overall_ci[0], 1), round(overall_ci[1], 1))
                                  if overall_ci[0] is not None else None,
            "by_class": by_class,
            "rows": scored,
        }

    print("=" * 100, flush=True)
    print("RECIPE A — SECTOR-ADJUSTED RESULTS", flush=True)
    print("=" * 100, flush=True)
    print(f"\n{'Threshold':<12}{'Class':<20}{'N':<5}{'Hit':<5}{'Miss':<5}"
          f"{'Abst':<6}{'N/A':<5}{'Prec':<8}{'95% CI':<20}", flush=True)
    print("-" * 100, flush=True)
    for thr_key, s in summary.items():
        thr_lbl = f"±{int(s['threshold_pct'])}%"
        prec = s["overall_precision_pct"]
        ci = s["overall_ci_95_pct"]
        prec_s = f"{prec:.1f}%" if prec is not None else "n/a"
        ci_s = f"[{ci[0]:.1f}-{ci[1]:.1f}]" if ci else "n/a"
        print(f"{thr_lbl:<12}{'OVERALL':<20}{s['total']:<5}{s['hit']:<5}{s['miss']:<5}"
              f"{s['abstain']:<6}{s['n_a']:<5}{prec_s:<8}{ci_s:<20}", flush=True)
        for cls, c in s["by_class"].items():
            prec = c["precision_pct"]
            ci = c["ci_95_pct"]
            prec_s = f"{prec:.1f}%" if prec is not None else "n/a"
            ci_s = f"[{ci[0]:.1f}-{ci[1]:.1f}]" if ci else "n/a"
            print(f"{'':<12}{cls:<20}{c['n']:<5}{c['hit']:<5}{c['miss']:<5}"
                  f"{c['abstain']:<6}{c['n_a']:<5}{prec_s:<8}{ci_s:<20}", flush=True)
        print("-" * 100, flush=True)

    OUT_PATH.write_text(json.dumps({
        "methodology": "recipe_a_methodology.md (sector-adjusted as locked)",
        "thresholds_tested": THRESHOLDS,
        "sector_label": SECTOR_LABEL,
        "n_predictions": len(enriched),
        "stock_window": "filing-to-filing",
        "summary": summary,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
