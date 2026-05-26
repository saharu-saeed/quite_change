"""Calibration: score the universe's attention WITHOUT calling Claude,
then check correlation with market cap (Claude's size-confound guardrail).

This is a cheap dry-run — only the 2-3 SerpAPI calls per ticker, NO LLM
calls. Used to verify the score is anomaly-attention, not size-attention.

Usage:
    python scripts/calibrate_attention.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.quiet_change_v2 import (  # noqa: E402
    _run_anomaly_news_search,
    _run_confirmation_search,
    _compute_attention_score,
    LOW_ATTENTION_CONFIRM_THRESHOLD,
)
from scripts.universe_screen import screen_universe  # noqa: E402

TEMPEST_DIR = ROOT / "data" / "tempest"
OUT = ROOT / "outputs" / "quiet_change_v2" / "calibration"


def _approx_market_cap(ticker: str) -> float | None:
    """Approximate market cap = latest_close × shares_outstanding.

    Shares outstanding derived from latest equity / book_value_per_share.
    Returns None if data missing.
    """
    try:
        prices = json.load(open(TEMPEST_DIR / ticker / "prices.json", encoding="utf-8"))["data"]
        fin = json.load(open(TEMPEST_DIR / ticker / "financials.json", encoding="utf-8"))["data"]
    except Exception:
        return None
    if not prices or not fin:
        return None
    latest_price = float(prices[0]["close"])
    annuals = [r for r in fin if r.get("fiscal_quarter") in (None, "null")]
    annuals.sort(key=lambda r: r.get("period_end") or "", reverse=True)
    if not annuals:
        return None
    eq = annuals[0].get("equity")
    bvps = annuals[0].get("book_value_per_share")
    if not eq or not bvps:
        return None
    try:
        shares = float(eq) / float(bvps)
    except (ZeroDivisionError, ValueError, TypeError):
        return None
    return latest_price * shares


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    dx2 = sum((x - mx) ** 2 for x in xs)
    dy2 = sum((y - my) ** 2 for y in ys)
    denom = (dx2 ** 0.5) * (dy2 ** 0.5)
    if denom == 0:
        return 0.0
    return num / denom


def _spearman(xs: list[float], ys: list[float]) -> float:
    """Rank-correlation; less sensitive to outliers than Pearson."""

    def _rank(arr: list[float]) -> list[float]:
        order = sorted(range(len(arr)), key=lambda i: arr[i])
        ranks = [0.0] * len(arr)
        for rank_idx, original_idx in enumerate(order):
            ranks[original_idx] = float(rank_idx + 1)
        return ranks

    return _pearson(_rank(xs), _rank(ys))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    serp_key = os.environ.get("SERP_API_KEY") or os.environ.get("SERPAPI_API_KEY")
    if not serp_key:
        raise RuntimeError("SERP_API_KEY not set")

    cands = screen_universe()
    print(f"Calibrating on {len(cands)} universe candidates "
          f"(NO LLM calls — just SerpAPI attention).\n")

    rows: list[dict] = []
    t0 = time.time()
    for i, c in enumerate(cands):
        ticker = c["ticker"]
        try:
            anomaly = _run_anomaly_news_search(ticker, serp_key)
        except Exception as e:
            print(f"[{i+1}/{len(cands)}] {ticker} ANOMALY ERROR: {e}")
            rows.append({**c, "error": str(e)})
            continue

        confirm_results: list = []
        attention = _compute_attention_score(anomaly.get("news_results", []))
        if attention["score"] < LOW_ATTENTION_CONFIRM_THRESHOLD:
            try:
                conf = _run_confirmation_search(ticker, serp_key)
                confirm_results = conf.get("organic_results", [])
                attention = _compute_attention_score(
                    anomaly.get("news_results", []), confirm_results
                )
            except Exception:
                pass

        mcap = _approx_market_cap(ticker)
        row = {
            **c,
            "attention_score": attention["score"],
            "editorial": attention["editorial"],
            "brokerage": attention["brokerage"],
            "agg_article": attention["aggregator_article"],
            "agg_stub": attention["aggregator_stub"],
            "recent_2026": attention["recent_2026"],
            "market_cap_jpy": mcap,
            "log_market_cap": (mcap ** 0.0001) if mcap and mcap > 0 else None,
        }
        rows.append(row)
        mcap_str = f"¥{mcap/1e9:.0f}B" if mcap else "—"
        print(f"[{i+1}/{len(cands)}] {ticker}  attention={attention['score']:+.2f}  "
              f"mcap={mcap_str}  ed={row['editorial']} br={row['brokerage']} "
              f"agg_a={row['agg_article']} agg_s={row['agg_stub']} r2026={row['recent_2026']}", flush=True)

    elapsed = time.time() - t0

    valid = [r for r in rows if "error" not in r and r.get("market_cap_jpy")]

    # Distribution
    print("\n\n" + "=" * 80)
    print("ATTENTION SCORE DISTRIBUTION")
    print("=" * 80)
    scores = sorted(r["attention_score"] for r in valid)
    if scores:
        for label, idx in [
            ("min", 0),
            ("p10", int(len(scores) * 0.10)),
            ("p25", int(len(scores) * 0.25)),
            ("median", len(scores) // 2),
            ("p75", int(len(scores) * 0.75)),
            ("p90", int(len(scores) * 0.90)),
            ("max", len(scores) - 1),
        ]:
            print(f"  {label:>8}: {scores[min(idx, len(scores)-1)]:+.2f}")

    # Size-correlation check (Claude's guardrail)
    print()
    print("=" * 80)
    print("CLAUDE'S GUARDRAIL: corr(attention_score, market_cap)")
    print("=" * 80)
    if len(valid) >= 5:
        xs = [r["attention_score"] for r in valid]
        ys = [r["market_cap_jpy"] for r in valid]
        pearson = _pearson(xs, ys)
        # log-cap for spearman (size is heavy-tailed)
        import math
        log_ys = [math.log(max(y, 1.0)) for y in ys]
        spearman = _spearman(xs, log_ys)
        print(f"  n = {len(valid)}")
        print(f"  Pearson (raw):       {pearson:+.3f}")
        print(f"  Spearman (vs logCap): {spearman:+.3f}")
        verdict = "OK (real anomaly attention)" if abs(spearman) < 0.5 else (
            "SUSPECT (size-confounded — iterate weights)" if abs(spearman) < 0.7
            else "BAD (mostly a size proxy)"
        )
        print(f"  Verdict: {verdict}")
    else:
        print(f"  Too few valid rows ({len(valid)}) to compute correlation.")

    # Threshold breakpoints
    print()
    print("=" * 80)
    print("CANDIDATE THRESHOLDS")
    print("=" * 80)
    if scores:
        p25 = scores[int(len(scores) * 0.25)]
        p75 = scores[int(len(scores) * 0.75)]
        print(f"  LOW (unnoticed) candidate cutoff:  score <= {p25:+.1f}  (p25)")
        print(f"  HIGH (noticed) candidate cutoff:   score >= {p75:+.1f}  (p75)")
        print()
        print(f"  Current code uses LOW={LOW_ATTENTION_CONFIRM_THRESHOLD}, HIGH=8.0.")
        print(f"  Suggest tuning to match distribution if these diverge.")

    # Print the LOW-attention tickers — these are quiet-change candidates
    print()
    print("=" * 80)
    print("LOW-ATTENTION (quiet-change candidates) — sorted by score ascending")
    print("=" * 80)
    low_candidates = sorted(
        [r for r in valid if r["attention_score"] <= LOW_ATTENTION_CONFIRM_THRESHOLD],
        key=lambda r: r["attention_score"]
    )
    print(f"{'Ticker':<8} {'Score':<8} {'Stock 3mo':<11} {'Rev YoY':<9} {'MarketCap':<12} {'Editorial':<10}")
    for r in low_candidates:
        mcap_str = f"¥{r['market_cap_jpy']/1e9:.0f}B" if r.get('market_cap_jpy') else "—"
        print(
            f"{r['ticker']:<8} "
            f"{r['attention_score']:+6.2f}  "
            f"{r['stock_move_pct']:+8.2f}   "
            f"{r['revenue_yoy_pct']:+6.2f}  "
            f"{mcap_str:<12} "
            f"{r['editorial']}"
        )

    out_path = OUT / f"_calibration_{today}.json"
    out_path.write_text(json.dumps({"rows": rows, "elapsed_s": elapsed}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull calibration data saved to: {out_path}")
    print(f"Wall time: {elapsed:.1f}s for {len(cands)} tickers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
