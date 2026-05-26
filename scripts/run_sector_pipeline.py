"""End-to-end run for one sector_33_name.

Generalized from run_chemicals_pipeline.py. Adds:
  - SerpAPI result caching (per-ticker JSON) so reruns are free
  - Watch-list composite ranking (divergence + quality, attention as
    tie-break) — replaces the strict YES/no dual gate as the *primary*
    output, per the post-chemicals review
  - Strict gate verdict KEPT as annotation for the empirical finding
    ("does any name in this sector clear the literal-unnoticed bar?")

Free filters (cache-only, no API cost):
  1. Universe filter      : revenue YoY > +1%  AND  stock 3mo move <= -3%
  2. Stock-split exclusion: 30%-single-day-move heuristic
  3. Scale band           : {TOPIX Small 1, Small 2, Mid400}
  4. Quality screen       : sector-aware percentile composite

Paid step (SerpAPI ~$0.01-0.02/ticker for survivors, cached on rerun):
  5. Per-ticker anomaly + low-attention confirmation searches

Ranking:
  6. Peer-median divergence WITHIN this sector
  7. Watch-list composite = 0.45*divergence_signal + 0.45*quality_signal
                          + 0.10*attention_signal
     (all signals are 0-100 percentile, oriented so high = stronger candidate)
  8. Strict dual_gate verdict retained as column

Usage:
    python scripts/run_sector_pipeline.py 化学
    python scripts/run_sector_pipeline.py "ゴム製品"
    python scripts/run_sector_pipeline.py "金属製品" --no-cache    # force re-search
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
    compute_watchlist_ranking,
    score_quality,
)
from app.subagents.quiet_change_v2 import (  # noqa: E402
    LOW_ATTENTION_CONFIRM_THRESHOLD,
    _compute_attention_score,
    _run_anomaly_news_search,
    _run_confirmation_search,
    _run_retail_chatter_search,
)
from scripts.universe_screen import _compute_revenue_yoy, _compute_stock_move  # noqa: E402

OUT_ROOT = ROOT / "outputs" / "quiet_change_v2" / "sectors"
SERP_CACHE_DIR = ROOT / "outputs" / "quiet_change_v2" / "serpapi_cache"
ATTENTION_SNAPSHOT_DIR = ROOT / "data" / "attention_snapshots"

MIN_REVENUE_GROWTH_PCT = 1.0
MAX_STOCK_MOVE_PCT = -3.0
SERP_SLEEP_S = 0.5

# Frozen at v1.0 on 2026-05-23. If you change ANY of FROZEN_QUERY_TEMPLATES
# below, or the shape of the snapshot record, bump SNAPSHOT_SCHEMA_VERSION.
# Old snapshots stay frozen; the version field lets future backtests know
# which methodology produced each row in the time series. Silently changing
# the query turns the archive into apples-to-oranges.
SNAPSHOT_SCHEMA_VERSION = "v1.0-2026-05-23"
FROZEN_QUERY_TEMPLATES = {
    "anomaly": "{code} 株価 下落 理由 2026",
    "confirm": "{code} なぜ下落 株価 業績 説明 2026",
    "retail_chatter": "{code} 株価 (5ch OR 掲示板 OR note.com)",
}


def _slugify(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip("_") or "sector"


def _name_lookup(ticker: str) -> str:
    p = ROOT / "data" / "tempest" / ticker / "company.json"
    try:
        raw = json.load(open(p, encoding="utf-8"))
        d = raw.get("data", raw)
        if isinstance(d, list) and d:
            d = d[0]
        return d.get("company_name") or d.get("company_name_ja") or "?"
    except Exception:
        return "?"


def _avg_daily_yen_volume(ticker: str, days: int = 60) -> float | None:
    """Approximate average daily traded value (close × volume) in JPY over the
    last N trading days, from cached prices.json. Returns None on missing data.

    This is the liquidity proxy surfaced as a column so the analyst can judge
    whether a dash-tier candidate is actually tradeable at meaningful size.
    A fund that needs to move ¥500M in/out per name should treat anything
    below ~¥100M daily as effectively untradeable.
    """
    p = ROOT / "data" / "tempest" / ticker / "prices.json"
    if not p.exists():
        return None
    try:
        prices = json.load(open(p, encoding="utf-8"))["data"]
    except Exception:
        return None
    if not prices:
        return None
    series = prices[:days]
    total = 0.0
    n = 0
    for row in series:
        try:
            close = float(row.get("close") or 0)
            vol = float(row.get("volume") or 0)
        except (TypeError, ValueError):
            continue
        if close > 0 and vol > 0:
            total += close * vol
            n += 1
    if n == 0:
        return None
    return total / n


def _write_attention_snapshot(ticker: str, kind: str, payload: dict) -> None:
    """Persist raw SerpAPI response to a dated folder for future backtesting.

    Idempotent per (ticker, kind, today): if today's snapshot already exists,
    no-op. Lets re-runs on the same date stay free without producing duplicates.

    The point: in ~2 years, this archive turns the "unseenness" axis into
    something a backtest can use point-in-time. The discipline is that
    FROZEN_QUERY_TEMPLATES and this record shape must NOT change silently —
    bump SNAPSHOT_SCHEMA_VERSION if they do, or the time series dies.
    """
    today = date.today().isoformat()
    snap_dir = ATTENTION_SNAPSHOT_DIR / today
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"{ticker}_{kind}.json"
    if snap_path.exists():
        return  # already snapshotted today; preserve first-write-wins
    record = {
        "_schema": {
            "version": SNAPSHOT_SCHEMA_VERSION,
            "ticker": ticker,
            "kind": kind,
            "snapshot_date": today,
            "query_template": FROZEN_QUERY_TEMPLATES.get(kind, "unknown"),
        },
        "_raw_response": payload,
    }
    snap_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _cached_search(ticker: str, kind: str, fn, serp_key: str, use_cache: bool) -> tuple[dict, str]:
    """Wrap a SerpAPI call with a per-ticker JSON cache.

    `kind` is one of 'anomaly' | 'confirm' | 'retail_chatter'. Cache key does
    NOT include date so re-runs within a screening cycle are free; pass
    --no-cache to bypass.

    Side effect: writes a dated snapshot to ATTENTION_SNAPSHOT_DIR / today /
    {ticker}_{kind}.json on every call (idempotent — first write wins per day).
    """
    SERP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = SERP_CACHE_DIR / f"{ticker}_{kind}.json"
    if use_cache and cache_path.exists():
        payload = json.load(open(cache_path, encoding="utf-8"))
        _write_attention_snapshot(ticker, kind, payload)
        return payload, "cached"
    payload = fn(ticker, serp_key)
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_attention_snapshot(ticker, kind, payload)
    return payload, "fetched"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sector", help="sector_33_name to run (e.g. 化学)")
    ap.add_argument("--no-cache", action="store_true",
                    help="bypass SerpAPI cache and re-fetch searches")
    ap.add_argument(
        "--include-dash",
        action="store_true",
        help=(
            "Include dash-tier names (TSE Standard / TSE Growth / unscaled)"
            " alongside TOPIX-band names in the same ranked output. Verified"
            " safe for B2B/industrial sectors (chemicals: 0%% retail-signal"
            " failure); NOT yet safe for consumer/themed sectors until the"
            " retail-chatter channel is built into the attention score."
            " Requires `fetch_sector.py --include-dash` to have populated the"
            " {sector}_dash_manifest.json beforehand."
        ),
    )
    args = ap.parse_args(argv)
    use_cache = not args.no_cache
    sector = args.sector

    out_dir = OUT_ROOT / _slugify(sector)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    # ---------- 1. Load sector ticker list(s) from manifest(s) ----------
    band_manifest_path = ROOT / "data" / "tempest" / "_meta" / f"{_slugify(sector)}_manifest.json"
    if not band_manifest_path.exists():
        legacy = ROOT / "data" / "tempest" / "_meta" / "chemicals_manifest.json"
        if sector == "化学" and legacy.exists():
            band_manifest_path = legacy
        else:
            print(f"ERROR: manifest not found at {band_manifest_path}", flush=True)
            print(f"       run: python scripts/fetch_sector.py {sector!r}", flush=True)
            return 1

    band_manifest = json.load(open(band_manifest_path, encoding="utf-8"))
    band_tickers = list(band_manifest["fetched_tickers"])
    ticker_tier = {t: "BAND" for t in band_tickers}
    all_tickers = list(band_tickers)

    if args.include_dash:
        dash_manifest_path = ROOT / "data" / "tempest" / "_meta" / f"{_slugify(sector)}_dash_manifest.json"
        if not dash_manifest_path.exists():
            print(f"ERROR: --include-dash requires {dash_manifest_path}", flush=True)
            print(f"       run: python scripts/fetch_sector.py {sector!r} --include-dash", flush=True)
            return 1
        dash_manifest = json.load(open(dash_manifest_path, encoding="utf-8"))
        # The dash manifest contains BOTH band + dash names (since fetch was a
        # superset). Pull only the dash-tier additions to add to our pool.
        for t in dash_manifest["fetched_tickers"]:
            if t not in ticker_tier:
                ticker_tier[t] = "DASH"
                all_tickers.append(t)
        print(f"Sector {sector!r}: {len(band_tickers)} band + "
              f"{sum(1 for v in ticker_tier.values() if v == 'DASH')} dash "
              f"= {len(all_tickers)} total tickers")
    else:
        print(f"Sector {sector!r}: {len(all_tickers)} tickers (mid-cap band only)")

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
                "tier": ticker_tier.get(ticker, "BAND"),
                "liquidity_jpy_daily": _avg_daily_yen_volume(ticker),
                "revenue_yoy_pct": rev["revenue_yoy_pct"],
                "stock_move_pct": stock["move_pct"],
                "stock_start_date": stock["start_date"],
                "stock_end_date": stock["end_date"],
                "latest_fy_end": rev["latest_period_end"],
            })
    print(f"After rev↑+stock↓ filter (rev>=+{MIN_REVENUE_GROWTH_PCT}%, stk<={MAX_STOCK_MOVE_PCT}%): {len(rows)}")

    # ---------- 3. Sector enrichment + split + scale band ----------
    for r in rows:
        info = load_sector_info(r["ticker"])
        r.update(info)
        r["split_check"] = detect_possible_split(r["ticker"])

    split_survivors = [r for r in rows if not r["split_check"]["possible_split"]]
    split_excluded = [r for r in rows if r["split_check"]["possible_split"]]
    print(f"After split exclusion: {len(split_survivors)} ({len(split_excluded)} excluded)")

    # Scale band check applies to BAND-tier names only. DASH-tier names are
    # admitted by construction (they were in the dash manifest, which means
    # they're TSE Standard / Growth / unscaled — outside the TOPIX scale bands
    # by definition but verified safe for B2B sectors).
    band_survivors = [
        r for r in split_survivors
        if r.get("tier") == "DASH"
        or r.get("scale_category") in ACCEPTABLE_SCALE_CATEGORIES
    ]
    tier_counts = Counter(r["tier"] for r in band_survivors)
    print(f"After scale band: {len(band_survivors)}  "
          f"(BAND={tier_counts.get('BAND', 0)}, DASH={tier_counts.get('DASH', 0)})")

    if not band_survivors:
        print("\nNo candidates surviving free filters.")
        return 0

    # ---------- 4. Quality screen ----------
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

    # ---------- 5. PAID: SerpAPI (with per-ticker cache) ----------
    serp_key = os.environ.get("SERP_API_KEY") or os.environ.get("SERPAPI_API_KEY")
    if not serp_key:
        raise RuntimeError("SERP_API_KEY not set in .env")

    print(f"\nRunning SerpAPI on {len(band_survivors)} survivors (cache={'on' if use_cache else 'off'})...")
    n_fetched = 0
    n_cached = 0
    t0 = time.time()
    for i, r in enumerate(band_survivors):
        ticker = r["ticker"]
        try:
            anomaly, anomaly_status = _cached_search(
                ticker, "anomaly", _run_anomaly_news_search, serp_key, use_cache
            )
        except Exception as e:
            r["attention_error"] = f"anomaly: {e}"
            print(f"  [{i+1}/{len(band_survivors)}] {ticker}  ANOMALY ERROR: {e}", flush=True)
            continue
        if anomaly_status == "cached":
            n_cached += 1
        else:
            n_fetched += 1
            time.sleep(SERP_SLEEP_S)

        # Always run the retail-chatter probe — it's now a standard attention
        # channel, not just an experiment. Cached on first run; free thereafter.
        retail_results: list = []
        try:
            retail_payload, retail_status = _cached_search(
                ticker, "retail_chatter", _run_retail_chatter_search, serp_key, use_cache
            )
            if retail_status == "cached":
                n_cached += 1
            else:
                n_fetched += 1
                time.sleep(SERP_SLEEP_S)
            retail_results = retail_payload.get("organic_results", []) or []
        except Exception:
            pass

        confirm_results: list = []
        # First-pass score (no confirmation) to decide whether to run the confirm guard.
        first_pass = _compute_attention_score(
            anomaly.get("news_results", []),
            None,
            retail_results,
        )
        if first_pass["score"] < LOW_ATTENTION_CONFIRM_THRESHOLD:
            try:
                conf, conf_status = _cached_search(
                    ticker, "confirm", _run_confirmation_search, serp_key, use_cache
                )
                if conf_status == "cached":
                    n_cached += 1
                else:
                    n_fetched += 1
                    time.sleep(SERP_SLEEP_S)
                confirm_results = conf.get("organic_results", [])
            except Exception:
                pass

        attention = _compute_attention_score(
            anomaly.get("news_results", []),
            confirm_results,
            retail_results,
        )

        r["attention_score"] = attention["score"]
        r["editorial"] = attention["editorial"]
        r["brokerage"] = attention["brokerage"]
        r["agg_article"] = attention["aggregator_article"]
        r["agg_stub"] = attention["aggregator_stub"]
        r["retail_chatter"] = attention["retail_chatter"]
        r["recent_2026"] = attention["recent_2026"]
        print(
            f"  [{i+1}/{len(band_survivors)}] {ticker}  {r['company_name'][:18]:<18}  "
            f"stk={r['stock_move_pct']:+5.1f}%  attn={attention['score']:+5.1f}  "
            f"ed={r['editorial']} br={r['brokerage']} retail={r['retail_chatter']} stub={r['agg_stub']}",
            flush=True,
        )
    elapsed_paid = time.time() - t0
    cost = n_fetched * 0.01
    print(f"\nSerpAPI: {n_fetched} fetched (~${cost:.2f}) + {n_cached} cached, {elapsed_paid:.1f}s")

    # ---------- 6. Divergence within sector ----------
    peer_baseline = compute_peer_baseline(band_survivors)
    print(f"\nPeer baselines (within {sector}, CONDITIONED on rev↑+stock↓):")
    for s, base in peer_baseline.items():
        flag = "  ⚠ low-confidence" if base["low_confidence"] else ""
        print(f"  {s:<14} n={base['n']:>2}  median_3mo: {base['median_move']:+.2f}%{flag}")

    for r in band_survivors:
        r["sector_rel"] = classify_sector_relative(
            r["stock_move_pct"], r.get("sector_33_name"), peer_baseline
        )

    # ---------- 7. Strict gate (kept as annotation, NOT primary ranking) ----------
    for r in band_survivors:
        if "attention_score" in r:
            r["dual_gate"] = quiet_change_dual_gate(r["attention_score"], r["sector_rel"])
        else:
            r["dual_gate"] = {"quiet_change_candidate": False, "reason": "attention search failed"}

    # ---------- 8. Watch-list composite ranking ----------
    compute_watchlist_ranking(band_survivors)

    # Sort by watchlist composite desc
    band_survivors.sort(key=lambda r: -(r.get("watchlist_composite") or 0))

    # ---------- 9. Report ----------
    print("\n" + "=" * 170)
    print(f"{sector} — WATCH-LIST RANKING (divergence + quality, attention as tie-break)")
    print("=" * 170)
    print(
        f"{'Rank':<5} {'Ticker':<7} {'Company':<22} {'Tier':<5} {'Scale':<14} "
        f"{'Stk3m':<7} {'PeerMed':<8} {'Diverge':<8} {'Attn':<6} {'Retail':<7} "
        f"{'Qual':<6} {'Liq(¥M/d)':<10} {'Comp':<6} {'StrictHit':<10}"
    )
    print("-" * 170)
    for i, r in enumerate(band_survivors, 1):
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
        retail = r.get("retail_chatter", 0)
        retail_str = f"{retail}" if retail else " "
        comp = r.get("watchlist_composite", 0)
        strict = "YES" if r["dual_gate"]["quiet_change_candidate"] else "no"
        liq = r.get("liquidity_jpy_daily")
        liq_str = f"¥{liq/1e6:7.0f}M" if liq else "    -    "
        print(
            f"{i:<5} {r['ticker']:<7} {r['company_name'][:21]:<22} {r.get('tier','?'):<5} "
            f"{(r.get('scale_category') or '-'):<14} "
            f"{r['stock_move_pct']:+5.1f}  {med_str:>7}  {rel_str:>7}  "
            f"{attn_str:<6} {retail_str:<7} {q_str:<6} {liq_str:<10} {comp:5.1f}  {strict:<10}"
        )

    strict_hits = [r for r in band_survivors if r["dual_gate"]["quiet_change_candidate"]]
    print(f"\nStrict dual-gate hits (literal-unnoticed + idiosyncratic): {len(strict_hits)}")
    if strict_hits:
        for r in strict_hits:
            print(f"  {r['ticker']} {r['company_name']}  watchlist={r['watchlist_composite']:.1f}")

    # ---------- 10. Save JSON ----------
    out = {
        "sector_33_name": sector,
        "screened_at": today,
        "include_dash": bool(args.include_dash),
        "stats": {
            "pool_size": len(all_tickers),
            "after_universe_filter": len(rows),
            "after_split_filter": len(split_survivors),
            "after_scale_band": len(band_survivors),
            "tier_breakdown_in_band_survivors": dict(tier_counts),
            "strict_dual_gate_hits": len(strict_hits),
        },
        "peer_baseline": peer_baseline,
        "watchlist_ranked": band_survivors,
        "split_excluded": [
            {"ticker": r["ticker"], "name": r["company_name"], "split_check": r["split_check"]}
            for r in split_excluded
        ],
        "serpapi_cost_estimate_usd": round(cost, 3),
    }
    out_path = out_dir / f"_run_{today}.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull output saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
