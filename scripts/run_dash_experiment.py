"""Dash-tier experiment — does the pipeline still work outside TOPIX scale bands?

Per the post-sweep review: the "dash tier" (scale_category in {"-", None}) is
actually three subtypes mixed together —
  - TSE Growth   (formerly Mothers): young IPOs. Short history (<3y) kills the
                  quality screen. Attention here is retail/social, not
                  brokerage — our signal is calibrated wrong for them.
  - TSE Standard: established small-caps. Multi-year history exists. Both
                  signals should work, just on smaller / less liquid names.
  - Sub-TOPIX-Prime: Prime-listed names that didn't make the TOPIX 500 cut.
                     Surprisingly normal companies. Both signals work.

This experiment runs the existing pipeline on dash-tier chemicals (no scale
filter) and segments the output by `market_code` plus `years_of_history`, so
we can directly observe:
  - Do Growth-tier names with <3y history slip through the quality screen?
  - Do "low-attention" dash names have heavy retail chatter the signal missed?
  - Are Standard / sub-TOPIX-Prime names actually fine as Claude expects?

Output is a SEPARATE TRACK from the main watch-list — never blended with the
TOPIX-band results.

Usage:
    python scripts/run_dash_experiment.py 化学
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
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
    compute_watchlist_ranking,
    score_quality,
)
from app.subagents.quiet_change_v2 import (  # noqa: E402
    LOW_ATTENTION_CONFIRM_THRESHOLD,
    _compute_attention_score,
    _run_anomaly_news_search,
    _run_confirmation_search,
)
from scripts.universe_screen import _compute_revenue_yoy, _compute_stock_move  # noqa: E402

try:
    from serpapi import GoogleSearch
except ImportError:
    GoogleSearch = None

TEMPEST_DIR = ROOT / "data" / "tempest"
SERP_CACHE_DIR = ROOT / "outputs" / "quiet_change_v2" / "serpapi_cache"
OUT_ROOT = ROOT / "outputs" / "quiet_change_v2" / "dash_experiment"

MIN_REVENUE_GROWTH_PCT = 1.0
MAX_STOCK_MOVE_PCT = -3.0
SERP_SLEEP_S = 0.5
RETAIL_CHATTER_ATTN_CEILING = 8.0  # only run the retail-chatter probe on these


def _slugify(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip("_") or "sector"


def _name_lookup(ticker: str) -> tuple[str, str | None]:
    p = TEMPEST_DIR / ticker / "company.json"
    try:
        raw = json.load(open(p, encoding="utf-8"))
        d = raw.get("data", raw)
        if isinstance(d, list) and d:
            d = d[0]
        return (
            d.get("company_name") or d.get("company_name_ja") or "?",
            d.get("market_code"),
        )
    except Exception:
        return "?", None


def _years_of_history(ticker: str) -> int:
    """Count annual financial rows for the ticker (proxy for IPO recency)."""
    p = TEMPEST_DIR / ticker / "financials.json"
    if not p.exists():
        return 0
    try:
        fin = json.load(open(p, encoding="utf-8"))["data"]
    except Exception:
        return 0
    return sum(1 for r in fin if r.get("fiscal_quarter") in (None, "null"))


def _cached_search(ticker: str, kind: str, fn, serp_key: str) -> tuple[dict, str]:
    SERP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = SERP_CACHE_DIR / f"{ticker}_{kind}.json"
    if cache_path.exists():
        return json.load(open(cache_path, encoding="utf-8")), "cached"
    payload = fn(ticker, serp_key)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload, "fetched"


def _run_retail_chatter_search(ticker: str, serp_key: str) -> dict:
    """Targeted Google search for retail-forum chatter on this ticker.

    Probes 5ch / Yahoo 掲示板 / note.com — places retail investors talk that
    our brokerage-weighted attention score doesn't see.
    """
    if GoogleSearch is None:
        return {}
    params = {
        "q": f"{ticker} 株価 (5ch OR 掲示板 OR note.com)",
        "engine": "google",
        "google_domain": "google.co.jp",
        "gl": "jp",
        "hl": "ja",
        "num": "10",
        "api_key": serp_key,
    }
    search = GoogleSearch(params)
    return search.get_dict()


def _retail_chatter_count(payload: dict) -> int:
    """Count forum/note.com hits in the retail-chatter search result."""
    from urllib.parse import urlparse
    results = payload.get("organic_results", []) or []
    n = 0
    for r in results:
        url = r.get("link") or ""
        try:
            netloc = urlparse(url).netloc.lower().removeprefix("www.")
        except Exception:
            continue
        if any(d in netloc for d in ("5ch.net", "note.com", "yahoo.co.jp", "minkabu.jp")):
            # minkabu has a forum subsection too; count if the path contains /board or /forum
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sector", help="sector_33_name (e.g. 化学)")
    args = ap.parse_args(argv)
    sector = args.sector

    out_dir = OUT_ROOT / _slugify(sector)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    # Load the dash-tier manifest
    manifest_path = TEMPEST_DIR / "_meta" / f"{_slugify(sector)}_dash_manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found.", flush=True)
        print(f"       run: python scripts/fetch_sector.py '{sector}' --include-dash", flush=True)
        return 1

    manifest = json.load(open(manifest_path, encoding="utf-8"))
    all_tickers = manifest["fetched_tickers"]
    print(f"Loaded dash-inclusive manifest for {sector}: {len(all_tickers)} tickers")

    # Annotate each ticker with sector_info + market_code + years_of_history
    rows = []
    for ticker in all_tickers:
        info = load_sector_info(ticker)
        name, market_code = _name_lookup(ticker)
        rows.append({
            "ticker": ticker,
            "company_name": name,
            "scale_category": info.get("scale_category"),
            "market_code": market_code,
            "sector_33_name": info.get("sector_33_name"),
            "years_of_history": _years_of_history(ticker),
        })

    # We only want DASH-TIER names here (the original TOPIX-band 117 are
    # already covered by the main sweep).
    dash = [r for r in rows if r["scale_category"] in (None, "-")]
    print(f"  Dash-tier names: {len(dash)}\n")

    # Breakdown by market_code
    print("Dash-tier market_code distribution:")
    mc_counts = Counter((r["market_code"] or "?") for r in dash)
    for mc, n in mc_counts.most_common():
        print(f"  {mc:<14}: {n}")

    # Breakdown by years_of_history
    print("\nDash-tier years_of_history distribution:")
    hist_counts = Counter(r["years_of_history"] for r in dash)
    for hist, n in sorted(hist_counts.items(), reverse=True):
        tag = "  (mature, quality screen works)" if hist >= 3 else "  (TOO SHORT for quality screen)"
        print(f"  {hist} years: {n}{tag}")
    short_hist = sum(1 for r in dash if r["years_of_history"] < 3)
    print(f"\n  >>> {short_hist}/{len(dash)} names ({short_hist/max(len(dash),1)*100:.0f}%) have <3y history (Growth-tier / recent IPO).")

    # Apply universe filter
    keep = []
    for r in dash:
        stock = _compute_stock_move(r["ticker"])
        rev = _compute_revenue_yoy(r["ticker"])
        if stock is None or rev is None:
            r["filter_reason"] = "no stock/rev data"
            continue
        if rev["revenue_yoy_pct"] < MIN_REVENUE_GROWTH_PCT or stock["move_pct"] > MAX_STOCK_MOVE_PCT:
            continue
        r["revenue_yoy_pct"] = rev["revenue_yoy_pct"]
        r["stock_move_pct"] = stock["move_pct"]
        r["latest_fy_end"] = rev["latest_period_end"]
        keep.append(r)

    print(f"\nAfter rev↑+stock↓ filter: {len(keep)} (from {len(dash)})")

    # Split exclusion
    split_survivors = []
    for r in keep:
        sc = detect_possible_split(r["ticker"])
        r["split_check"] = sc
        if not sc["possible_split"]:
            split_survivors.append(r)
    print(f"After split exclusion:   {len(split_survivors)} ({len(keep)-len(split_survivors)} excluded)")

    # Quality screen (only computes for names with >=3y; others get data_ok=False)
    for r in split_survivors:
        qm = compute_quality_metrics(r["ticker"])
        qm["sector_33_name"] = r.get("sector_33_name")
        qm["scale_category"] = r.get("scale_category")
        r["quality"] = qm
    quality_valid = [r["quality"] for r in split_survivors if r["quality"].get("data_ok")]
    q_sector_norms = compute_sector_norms(quality_valid)
    q_global_norms = compute_global_norms(quality_valid)
    for r in split_survivors:
        if r["quality"].get("data_ok"):
            r["quality"]["quality_score"] = score_quality(r["quality"], q_sector_norms, q_global_norms)

    # SerpAPI attention
    serp_key = os.environ.get("SERP_API_KEY") or os.environ.get("SERPAPI_API_KEY")
    if not serp_key:
        raise RuntimeError("SERP_API_KEY not set")
    print(f"\nRunning SerpAPI on {len(split_survivors)} dash-tier survivors...")
    n_fetched = 0
    n_cached = 0
    for i, r in enumerate(split_survivors):
        ticker = r["ticker"]
        try:
            anomaly, st = _cached_search(ticker, "anomaly", _run_anomaly_news_search, serp_key)
        except Exception as e:
            r["attention_error"] = f"anomaly: {e}"
            print(f"  [{i+1}] {ticker} ANOMALY ERROR", flush=True)
            continue
        if st == "cached":
            n_cached += 1
        else:
            n_fetched += 1
            time.sleep(SERP_SLEEP_S)
        attention = _compute_attention_score(anomaly.get("news_results", []))
        if attention["score"] < LOW_ATTENTION_CONFIRM_THRESHOLD:
            try:
                conf, st2 = _cached_search(ticker, "confirm", _run_confirmation_search, serp_key)
                if st2 == "cached":
                    n_cached += 1
                else:
                    n_fetched += 1
                    time.sleep(SERP_SLEEP_S)
                attention = _compute_attention_score(
                    anomaly.get("news_results", []), conf.get("organic_results", [])
                )
            except Exception:
                pass
        r["attention_score"] = attention["score"]
        r["attention_counts"] = {k: attention.get(k, 0) for k in (
            "editorial", "brokerage", "aggregator_article", "aggregator_stub",
            "forum", "ir_official", "other", "recent_2026",
        )}
        print(f"  [{i+1}/{len(split_survivors)}] {ticker}  {r['company_name'][:18]:<18}  "
              f"stk={r['stock_move_pct']:+5.1f}%  attn={attention['score']:+5.1f}  "
              f"ed={attention['editorial']} br={attention['brokerage']} fo={attention['forum']}",
              flush=True)

    # Retail-chatter sub-search on LOW-attention survivors
    print(f"\nRunning retail-chatter probe on attn ≤ {RETAIL_CHATTER_ATTN_CEILING} survivors...")
    n_rc = 0
    for r in split_survivors:
        attn = r.get("attention_score")
        if attn is None or attn > RETAIL_CHATTER_ATTN_CEILING:
            continue
        try:
            rc, st = _cached_search(r["ticker"], "retail_chatter", _run_retail_chatter_search, serp_key)
        except Exception as e:
            r["retail_chatter_error"] = str(e)
            continue
        if st == "fetched":
            n_rc += 1
            time.sleep(SERP_SLEEP_S)
        count = _retail_chatter_count(rc)
        r["retail_chatter_hits"] = count
        print(f"    {r['ticker']:<7} {r['company_name'][:18]:<18}  attn={attn:+.1f}  retail_chatter_hits={count}",
              flush=True)

    cost = (n_fetched + n_rc) * 0.01
    print(f"\nSerpAPI: {n_fetched} attention + {n_rc} retail-chatter fetched, {n_cached} cached  ~${cost:.2f}")

    # Divergence within dash chemicals
    peer_baseline = compute_peer_baseline(split_survivors)
    print(f"\nPeer baseline (dash chemicals, CONDITIONED on rev↑+stock↓):")
    for s, base in peer_baseline.items():
        flag = "  ⚠ low-confidence" if base["low_confidence"] else ""
        print(f"  {s:<14} n={base['n']:>2}  median_3mo: {base['median_move']:+.2f}%{flag}")

    for r in split_survivors:
        r["sector_rel"] = classify_sector_relative(
            r["stock_move_pct"], r.get("sector_33_name"), peer_baseline
        )

    # Strict gate
    for r in split_survivors:
        if "attention_score" in r:
            r["dual_gate"] = quiet_change_dual_gate(r["attention_score"], r["sector_rel"])
        else:
            r["dual_gate"] = {"quiet_change_candidate": False, "reason": "attention error"}

    # Watch-list composite
    compute_watchlist_ranking(split_survivors)
    split_survivors.sort(key=lambda r: -(r.get("watchlist_composite") or 0))

    # ---------- Segmented report by market_code ----------
    print("\n" + "=" * 150)
    print(f"DASH-TIER WATCH-LIST — segmented by market_code (sector: {sector})")
    print("=" * 150)
    by_mc: dict[str, list] = {}
    for r in split_survivors:
        by_mc.setdefault(r.get("market_code") or "?", []).append(r)

    for mc, members in sorted(by_mc.items(), key=lambda kv: -len(kv[1])):
        print(f"\n--- market_code: {mc}  (n={len(members)}) ---")
        print(f"{'Rk':<4} {'Ticker':<7} {'Company':<22} {'YrsHist':<8} "
              f"{'Stk3m':<7} {'Div':<7} {'Attn':<6} {'Forum':<6} {'Retail':<7} "
              f"{'Qual':<6} {'Comp':<6} {'Note':<14}")
        print("-" * 150)
        for i, r in enumerate(members, 1):
            yr = r["years_of_history"]
            yr_flag = "<<TOO SHORT" if yr < 3 else ""
            sr = r["sector_rel"]
            rel = sr.get("sector_relative_pp")
            rel_str = f"{rel:+5.2f}" if rel is not None else "  -  "
            q = r.get("quality") or {}
            q_score = q.get("quality_score", {}).get("composite_score") if q.get("data_ok") else None
            q_str = f"{q_score:5.1f}" if q_score is not None else "  -  "
            attn = r.get("attention_score")
            attn_str = f"{attn:+5.1f}" if attn is not None else " err"
            forum = r.get("attention_counts", {}).get("forum", 0)
            retail = r.get("retail_chatter_hits")
            retail_str = str(retail) if retail is not None else "-"
            comp = r.get("watchlist_composite", 0)
            print(f"{i:<4} {r['ticker']:<7} {r['company_name'][:21]:<22} "
                  f"{yr} {yr_flag:<7} {r['stock_move_pct']:+5.1f}  {rel_str:<7} "
                  f"{attn_str:<6} {forum:<6} {retail_str:<7} {q_str:<6} {comp:5.1f}  ")

    # Diagnosis summary
    print("\n" + "=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    short_hist_survivors = [r for r in split_survivors if r["years_of_history"] < 3]
    print(f"  Short-history survivors (<3y, quality screen invalid): "
          f"{len(short_hist_survivors)}/{len(split_survivors)}")
    if short_hist_survivors:
        for r in short_hist_survivors[:10]:
            print(f"    {r['ticker']:<7} {r['company_name'][:24]:<24} hist={r['years_of_history']}y  "
                  f"market={r['market_code']}  comp={r.get('watchlist_composite',0):.1f}")

    low_attn_with_retail = [
        r for r in split_survivors
        if r.get("attention_score") is not None
        and r["attention_score"] <= RETAIL_CHATTER_ATTN_CEILING
        and (r.get("retail_chatter_hits") or 0) >= 3
    ]
    print(f"\n  Low-attention names WITH heavy retail chatter (signal-broken cases): "
          f"{len(low_attn_with_retail)}")
    for r in low_attn_with_retail:
        print(f"    {r['ticker']:<7} {r['company_name'][:24]:<24} attn={r['attention_score']:+.1f}  "
              f"retail_hits={r['retail_chatter_hits']}  market={r['market_code']}")

    # Save full output
    out = {
        "sector_33_name": sector,
        "experiment": "dash_tier_inclusion_probe",
        "screened_at": today,
        "stats": {
            "dash_tier_total": len(dash),
            "after_universe_filter": len(keep),
            "after_split_filter": len(split_survivors),
            "short_history_survivors": len(short_hist_survivors),
            "retail_chatter_broken_cases": len(low_attn_with_retail),
        },
        "market_code_breakdown": dict(mc_counts),
        "years_of_history_breakdown": dict(hist_counts),
        "peer_baseline": peer_baseline,
        "survivors": split_survivors,
        "serpapi_cost_estimate_usd": round(cost, 3),
    }
    out_path = out_dir / f"_dash_experiment_{today}.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull output saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
