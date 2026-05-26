"""End-to-end chemicals-sector run.

Free filters (cache-only, no API cost):
  1. Universe filter      : revenue YoY > +1%  AND  stock 3mo move <= -3%
  2. Stock-split exclusion: 30%-single-day-move heuristic
  3. Scale band           : {TOPIX Small 1, Small 2, Mid400}
  4. Quality screen       : sector-aware percentile composite (informational)

Paid step (SerpAPI ~$0.02/ticker for ~10-25 survivors):
  5. Per-ticker anomaly news search + low-attention confirmation search

In-memory finalization:
  6. Peer-median divergence WITHIN the chemicals sector
  7. Dual gate            : (low attention) AND (idiosyncratic divergence)
                            = quiet-change candidate

Report sorted by (quiet_change_candidate, divergence ascending, quality desc).

Usage:
    python scripts/run_chemicals_pipeline.py
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

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.subagents.quiet_change_peers import (  # noqa: E402
    ACCEPTABLE_SCALE_CATEGORIES,
    classify_sector_relative,
    compute_peer_baseline,
    detect_possible_split,
    load_sector_info,
    quiet_change_dual_gate,
)
from app.subagents.quality_screen import (  # noqa: E402
    compute_global_norms,
    compute_quality_metrics,
    compute_sector_norms,
    score_quality,
)
from app.subagents.quiet_change_v2 import (  # noqa: E402
    LOW_ATTENTION_CONFIRM_THRESHOLD,
    _compute_attention_score,
    _run_anomaly_news_search,
    _run_confirmation_search,
)
from scripts.universe_screen import _compute_revenue_yoy, _compute_stock_move  # noqa: E402

CHEMICALS_MANIFEST = ROOT / "data" / "tempest" / "_meta" / "chemicals_manifest.json"
OUT_DIR = ROOT / "outputs" / "quiet_change_v2" / "chemicals"

MIN_REVENUE_GROWTH_PCT = 1.0
MAX_STOCK_MOVE_PCT = -3.0
SERP_SLEEP_S = 0.5  # polite throttle between SerpAPI calls


def _serpapi_cost_estimate(n_anomaly: int, n_confirm: int) -> float:
    """SerpAPI Developer plan = $0.01 per search."""
    return (n_anomaly + n_confirm) * 0.01


def _name_lookup(ticker: str) -> str:
    """Best-effort company-name lookup from company.json."""
    p = ROOT / "data" / "tempest" / ticker / "company.json"
    try:
        raw = json.load(open(p, encoding="utf-8"))
        d = raw.get("data", raw)
        if isinstance(d, list) and d:
            d = d[0]
        return d.get("company_name") or d.get("company_name_ja") or "?"
    except Exception:
        return "?"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    # ---------- 1. Load chemicals ticker list ----------
    manifest = json.load(open(CHEMICALS_MANIFEST, encoding="utf-8"))
    all_tickers = manifest["fetched_tickers"]
    print(f"Chemicals (化学) pool: {len(all_tickers)} tickers (mid-cap band)")

    # ---------- 2. Universe filter (rev↑+stock↓) ----------
    rows: list[dict] = []
    for ticker in all_tickers:
        stock = _compute_stock_move(ticker)
        rev = _compute_revenue_yoy(ticker)
        if stock is None or rev is None:
            continue
        if (
            rev["revenue_yoy_pct"] >= MIN_REVENUE_GROWTH_PCT
            and stock["move_pct"] <= MAX_STOCK_MOVE_PCT
        ):
            rows.append({
                "ticker": ticker,
                "company_name": _name_lookup(ticker),
                "revenue_yoy_pct": rev["revenue_yoy_pct"],
                "stock_move_pct": stock["move_pct"],
                "stock_start_date": stock["start_date"],
                "stock_end_date": stock["end_date"],
                "latest_fy_end": rev["latest_period_end"],
            })
    print(f"After rev↑+stock↓ filter (rev>=+{MIN_REVENUE_GROWTH_PCT}%, stk<={MAX_STOCK_MOVE_PCT}%): {len(rows)}")

    # ---------- 3. Enrich with sector + scale; apply split + scale-band exclusions ----------
    for r in rows:
        info = load_sector_info(r["ticker"])
        r.update(info)
        r["split_check"] = detect_possible_split(r["ticker"])

    split_survivors = [r for r in rows if not r["split_check"]["possible_split"]]
    split_excluded = [r for r in rows if r["split_check"]["possible_split"]]
    print(f"After split exclusion: {len(split_survivors)} ({len(split_excluded)} excluded)")
    if split_excluded:
        for r in split_excluded:
            evts = r["split_check"]["events"]
            ex = evts[0] if evts else {}
            print(f"    {r['ticker']:<6} {r['company_name']:<22} {ex.get('date','?')} "
                  f"{ex.get('prev_close',0):.0f} → {ex.get('today_close',0):.0f}  "
                  f"({ex.get('delta_pct',0):+.1f}%)")

    band_survivors = [r for r in split_survivors if r.get("scale_category") in ACCEPTABLE_SCALE_CATEGORIES]
    band_excluded = [r for r in split_survivors if r.get("scale_category") not in ACCEPTABLE_SCALE_CATEGORIES]
    print(f"After scale band {sorted(ACCEPTABLE_SCALE_CATEGORIES)}: {len(band_survivors)}")
    if band_excluded:
        from collections import Counter
        ec = Counter(r.get("scale_category") for r in band_excluded)
        for sc, n in ec.most_common():
            print(f"    {sc or '?'}: {n}")

    if not band_survivors:
        print("\nNo candidates surviving free filters — nothing to send to SerpAPI.")
        return 0

    # ---------- 4. Quality screen (sector-aware percentile composite) ----------
    for r in band_survivors:
        qm = compute_quality_metrics(r["ticker"])
        qm["sector_33_name"] = r.get("sector_33_name")
        qm["scale_category"] = r.get("scale_category")
        r["quality"] = qm
    quality_valid = [r["quality"] for r in band_survivors if r["quality"].get("data_ok")]
    q_sector_norms = compute_sector_norms(quality_valid)
    q_global_norms = compute_global_norms(quality_valid)
    for r in band_survivors:
        if r["quality"].get("data_ok"):
            r["quality"]["quality_score"] = score_quality(
                r["quality"], q_sector_norms, q_global_norms
            )

    # ---------- 5. PAID: SerpAPI attention searches ----------
    serp_key = os.environ.get("SERP_API_KEY") or os.environ.get("SERPAPI_API_KEY")
    if not serp_key:
        raise RuntimeError("SERP_API_KEY not set in .env")

    print(f"\nRunning SerpAPI attention searches on {len(band_survivors)} chemicals survivors...")
    n_anomaly = 0
    n_confirm = 0
    t0 = time.time()
    for i, r in enumerate(band_survivors):
        ticker = r["ticker"]
        try:
            anomaly = _run_anomaly_news_search(ticker, serp_key)
            n_anomaly += 1
        except Exception as e:
            r["attention_error"] = f"anomaly: {e}"
            print(f"  [{i+1}/{len(band_survivors)}] {ticker}  ANOMALY ERROR: {e}", flush=True)
            continue
        attention = _compute_attention_score(anomaly.get("news_results", []))
        confirm_results: list = []
        if attention["score"] < LOW_ATTENTION_CONFIRM_THRESHOLD:
            try:
                conf = _run_confirmation_search(ticker, serp_key)
                n_confirm += 1
                confirm_results = conf.get("organic_results", [])
                attention = _compute_attention_score(
                    anomaly.get("news_results", []), confirm_results
                )
            except Exception:
                pass
        r["attention_score"] = attention["score"]
        r["editorial"] = attention["editorial"]
        r["brokerage"] = attention["brokerage"]
        r["agg_article"] = attention["aggregator_article"]
        r["agg_stub"] = attention["aggregator_stub"]
        r["recent_2026"] = attention["recent_2026"]
        time.sleep(SERP_SLEEP_S)
        print(
            f"  [{i+1}/{len(band_survivors)}] {ticker}  {r['company_name'][:18]:<18}  "
            f"stk={r['stock_move_pct']:+5.1f}%  attn={attention['score']:+5.1f}  "
            f"ed={r['editorial']} br={r['brokerage']} stub={r['agg_stub']}",
            flush=True,
        )
    elapsed_paid = time.time() - t0
    paid_cost = _serpapi_cost_estimate(n_anomaly, n_confirm)
    print(f"\nSerpAPI: {n_anomaly} anomaly + {n_confirm} confirm searches, "
          f"~${paid_cost:.2f}, {elapsed_paid:.1f}s")

    # ---------- 6. Divergence within chemicals sector ----------
    peer_baseline = compute_peer_baseline(band_survivors)
    print("\nPeer baselines (CONDITIONED on rev↑+stock↓ within chemicals):")
    for sector, base in peer_baseline.items():
        flag = "  ⚠ low-confidence" if base["low_confidence"] else ""
        print(f"  {sector:<14} n={base['n']:>2}  median_3mo: {base['median_move']:+.2f}%{flag}")

    for r in band_survivors:
        r["sector_rel"] = classify_sector_relative(
            r["stock_move_pct"], r.get("sector_33_name"), peer_baseline
        )

    # ---------- 7. Dual gate ----------
    for r in band_survivors:
        if "attention_score" in r:
            r["dual_gate"] = quiet_change_dual_gate(r["attention_score"], r["sector_rel"])
        else:
            r["dual_gate"] = {"quiet_change_candidate": False, "reason": "attention search failed"}

    # ---------- 8. Report ----------
    band_survivors.sort(key=lambda r: (
        not r["dual_gate"]["quiet_change_candidate"],
        r["sector_rel"].get("sector_relative_pp") or 999,
    ))

    print("\n" + "=" * 130)
    print("CHEMICALS RUN — FINAL RANKING")
    print("=" * 130)
    print(
        f"{'Ticker':<7} {'Company':<22} {'Scale':<14} "
        f"{'Stk3m':<7} {'PeerMed':<8} {'Diverge':<8} {'Attn':<6} {'Qual':<6} {'QuietChange?':<13}"
    )
    print("-" * 130)
    for r in band_survivors:
        sr = r["sector_rel"]
        rel = sr.get("sector_relative_pp")
        rel_str = f"{rel:+.2f}" if rel is not None else "n/a"
        med = sr.get("peer_median")
        med_str = f"{med:+.2f}" if med is not None else "n/a"
        q = r.get("quality") or {}
        q_score = q.get("quality_score", {}).get("composite_score") if q.get("data_ok") else None
        q_str = f"{q_score:5.1f}" if q_score is not None else "  -  "
        attn = r.get("attention_score")
        attn_str = f"{attn:+5.1f}" if attn is not None else "  err"
        verdict = "YES" if r["dual_gate"]["quiet_change_candidate"] else "no"
        print(
            f"{r['ticker']:<7} {r['company_name'][:21]:<22} {r.get('scale_category','?'):<14} "
            f"{r['stock_move_pct']:+5.1f}  {med_str:>7}  {rel_str:>7}  "
            f"{attn_str:<6} {q_str:<6} {verdict:<13}"
        )

    winners = [r for r in band_survivors if r["dual_gate"]["quiet_change_candidate"]]
    print("\n" + "=" * 80)
    print(f"QUIET-CHANGE CANDIDATES SURVIVING BOTH GATES: {len(winners)}")
    print("=" * 80)
    for r in winners:
        print(f"\n  {r['ticker']}  {r['company_name']}  ({r.get('sector_33_name')}, {r.get('scale_category')})")
        print(f"    Stock 3mo:        {r['stock_move_pct']:+.1f}%")
        print(f"    Chemicals peer med: {r['sector_rel']['peer_median']:+.1f}%  (n={r['sector_rel']['peer_n']})")
        print(f"    Divergence:       {r['sector_rel']['sector_relative_pp']:+.1f}pp idiosyncratic")
        print(f"    Attention score:  {r['attention_score']:+.1f}  (ed={r['editorial']} br={r['brokerage']})")
        print(f"    Revenue YoY:      {r['revenue_yoy_pct']:+.1f}%")
        q = r.get("quality") or {}
        if q.get("data_ok"):
            qs = q["quality_score"]
            print(
                f"    Quality score:    {qs['composite_score']:.1f}/100   "
                f"(CAGR3y={q['revenue_cagr_3y']:+.1f}%, OPmar={q['op_margin_latest']:+.1f}%, "
                f"OPtrnd={q['op_margin_trend_pp']:+.1f}pp, ROE={q['roe_latest']:+.1f}%, "
                f"EqRat={q['equity_ratio_latest']:+.1f}%)"
            )

    # ---------- save JSON ----------
    out = {
        "sector": "化学",
        "screened_at": today,
        "stats": {
            "pool_size": len(all_tickers),
            "after_universe_filter": len(rows),
            "after_split_filter": len(split_survivors),
            "after_scale_band": len(band_survivors),
            "quiet_change_candidates": len(winners),
        },
        "peer_baseline": peer_baseline,
        "split_excluded": [{"ticker": r["ticker"], "name": r["company_name"], "split_check": r["split_check"]} for r in split_excluded],
        "winners": winners,
        "all_band_survivors": band_survivors,
        "serpapi_cost_estimate_usd": round(paid_cost, 3),
    }
    out_path = OUT_DIR / f"_chemicals_run_{today}.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull output saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
