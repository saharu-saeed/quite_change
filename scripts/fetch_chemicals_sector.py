"""Ingest the 化学 (specialty chemicals) sector into data/tempest/.

Per PM steer (2026-05-22): pick one quiet, fragmented, narrative-light B2B
sector and feed the agent JUST that sector's data. Specialty chemicals
(化学) — the recommended pick — sits in the 'no dominant current narrative'
zone: many under-covered mid-caps, no single story moving them all.

This script:
  1. Calls Tempest /companies?sector_33_name=化学 (paginated)
  2. Filters to TOPIX scale bands of interest:
        {Small 1, Small 2, Mid400}     (the same mid-cap band the universe
                                         pre-filter and the divergence gate use)
     Core30 / Large70 (mega-caps) are skipped — those names are noticed.
  3. For each surviving ticker, fetches company / financials / prices
     and writes them to data/tempest/{ticker}/{file}.json — schema-
     compatible with the existing cache so the downstream pipeline (universe
     screen, quality screen, attention gate, divergence gate) runs unchanged.

The fetch is read-only on the cache: existing files are NOT overwritten
unless --force is passed, so re-running is cheap and idempotent.

Usage:
    python scripts/fetch_chemicals_sector.py
    python scripts/fetch_chemicals_sector.py --force      # re-fetch everything
"""
from __future__ import annotations

import argparse
import json
import sys
import time
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
    pass  # env vars must already be set

from app.ingest.tempest_client import (  # noqa: E402
    get_company,
    get_financials,
    get_indicators,
    get_prices,
    health,
    list_all_companies,
)

TEMPEST_DIR = ROOT / "data" / "tempest"
SECTOR_CHEMICALS = "化学"

# Mid-cap band — matches ACCEPTABLE_SCALE_CATEGORIES in quiet_change_peers.py.
ACCEPT_SCALES = {"TOPIX Small 1", "TOPIX Small 2", "TOPIX Mid400"}

# Polite pause between API calls to avoid hammering staging.
SLEEP_S = 0.15


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _maybe_fetch(ticker: str, fname: str, fetch_fn, force: bool) -> str:
    """Fetch + write one file. Returns 'cached', 'fetched', or 'empty'."""
    out = TEMPEST_DIR / ticker / fname
    if out.exists() and not force:
        return "cached"
    try:
        payload = fetch_fn(ticker)
    except Exception as e:
        return f"error: {e}"
    if not payload or not payload.get("data"):
        return "empty"
    _write(out, payload)
    return "fetched"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-fetch even if cached")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap number of tickers fetched (for smoke tests)")
    args = ap.parse_args(argv)

    print("Tempest API health check...", flush=True)
    h = health()
    print(f"  {h}", flush=True)

    print(f"\nListing all {SECTOR_CHEMICALS} companies...", flush=True)
    companies = list_all_companies(sector_33_name=SECTOR_CHEMICALS)
    print(f"  found {len(companies)} chemical tickers (all scales)", flush=True)

    # Filter to mid-cap band
    target = [c for c in companies if c.get("scale_category") in ACCEPT_SCALES]
    print(f"  {len(target)} in mid-cap band ({sorted(ACCEPT_SCALES)})", flush=True)

    # Scale breakdown
    from collections import Counter
    scale_counts = Counter(c.get("scale_category") for c in target)
    for sc, n in scale_counts.most_common():
        print(f"    {sc:<14}: {n}", flush=True)

    if args.limit:
        target = target[: args.limit]
        print(f"  (capped to {args.limit} for smoke test)", flush=True)

    print(f"\nFetching per-ticker data for {len(target)} tickers...", flush=True)
    summary: list[dict] = []
    t0 = time.time()
    for i, c in enumerate(target):
        ticker = c["ticker"]
        # company.json — write what we already have if it's the full record
        co_path = TEMPEST_DIR / ticker / "company.json"
        if (not co_path.exists()) or args.force:
            _write(co_path, {"data": c})
        results = {
            "company": "cached" if co_path.exists() and not args.force else "fetched",
            "financials": _maybe_fetch(ticker, "financials.json", get_financials, args.force),
            "prices": _maybe_fetch(ticker, "prices.json", get_prices, args.force),
            "indicators": _maybe_fetch(ticker, "indicators.json", get_indicators, args.force),
        }
        time.sleep(SLEEP_S)
        flags = "  ".join(f"{k}={v[:8]}" for k, v in results.items())
        print(f"  [{i+1}/{len(target)}] {ticker}  {c.get('company_name_ja') or c.get('company_name_en') or '?':<24}  {flags}",
              flush=True)
        summary.append({"ticker": ticker, **results})

    elapsed = time.time() - t0

    # Summary
    print(f"\nDone in {elapsed:.1f}s")
    from collections import Counter as C
    for key in ("financials", "prices", "indicators"):
        c = C(r[key] for r in summary)
        breakdown = ", ".join(f"{k}={v}" for k, v in c.most_common())
        print(f"  {key:<11}: {breakdown}")

    # Write a manifest for downstream scripts
    manifest = {
        "sector_33_name": SECTOR_CHEMICALS,
        "scale_filter": sorted(ACCEPT_SCALES),
        "fetched_tickers": [r["ticker"] for r in summary],
        "summary": summary,
    }
    manifest_path = TEMPEST_DIR / "_meta" / "chemicals_manifest.json"
    _write(manifest_path, manifest)
    print(f"\nManifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
