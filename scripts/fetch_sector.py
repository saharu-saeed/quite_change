"""Ingest one sector_33_name's worth of mid-cap tickers into data/tempest/.

Generalized from fetch_chemicals_sector.py — takes the sector as an argument
so the same script can pull 化学, ゴム製品, 金属製品, その他製品, etc.

Each fetch is idempotent: existing per-ticker files are not re-written
unless --force is passed.

Usage:
    python scripts/fetch_sector.py 化学
    python scripts/fetch_sector.py "ゴム製品"
    python scripts/fetch_sector.py "金属製品" --force
    python scripts/fetch_sector.py "その他製品" --limit 5    # smoke test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
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

from app.ingest.tempest_client import (  # noqa: E402
    get_financials,
    get_indicators,
    get_prices,
    health,
    list_all_companies,
)

TEMPEST_DIR = ROOT / "data" / "tempest"

# Same mid-cap band the divergence gate and universe screen use.
ACCEPT_SCALES = {"TOPIX Small 1", "TOPIX Small 2", "TOPIX Mid400"}

SLEEP_S = 0.15


def _slugify(name: str) -> str:
    """Make a filesystem-safe key for the sector name. Keeps Japanese chars."""
    # Only strip Windows-unsafe filesystem chars; Unicode (incl. kanji) is fine.
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip("_") or "sector"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _maybe_fetch(ticker: str, fname: str, fetch_fn, force: bool) -> str:
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
    ap.add_argument("sector", help="sector_33_name to fetch (e.g. 化学, ゴム製品)")
    ap.add_argument("--force", action="store_true", help="re-fetch even if cached")
    ap.add_argument("--limit", type=int, default=None, help="cap number of tickers")
    ap.add_argument(
        "--include-dash",
        action="store_true",
        help=(
            "ALSO pull unscaled (dash-tier) names — TSE Standard / TSE Growth /"
            " sub-TOPIX-500 Prime. Used by the dash-experiment to probe"
            " whether the tool's signals work in this tier."
        ),
    )
    args = ap.parse_args(argv)

    sector = args.sector
    print("Tempest API health check...", flush=True)
    h = health()
    print(f"  {h}\n", flush=True)

    print(f"Listing all tickers in sector_33_name={sector!r}...", flush=True)
    companies = list_all_companies(sector_33_name=sector)
    print(f"  found {len(companies)} tickers (all scales)", flush=True)

    if args.include_dash:
        target = [
            c for c in companies
            if c.get("scale_category") in ACCEPT_SCALES
            or c.get("scale_category") in (None, "-")
        ]
        print(f"  {len(target)} in mid-cap band + dash-tier (--include-dash on)", flush=True)
    else:
        target = [c for c in companies if c.get("scale_category") in ACCEPT_SCALES]
        print(f"  {len(target)} in mid-cap band ({sorted(ACCEPT_SCALES)})", flush=True)

    sc_counts = Counter(c.get("scale_category") for c in target)
    for sc, n in sc_counts.most_common():
        print(f"    {(sc or 'None'):<16}: {n}", flush=True)

    if args.limit:
        target = target[: args.limit]
        print(f"  (capped to {args.limit} for smoke test)", flush=True)

    print(f"\nFetching per-ticker data for {len(target)} tickers...", flush=True)
    summary: list[dict] = []
    t0 = time.time()
    for i, c in enumerate(target):
        ticker = c["ticker"]
        co_path = TEMPEST_DIR / ticker / "company.json"
        co_action = "cached"
        if (not co_path.exists()) or args.force:
            _write(co_path, {"data": c})
            co_action = "fetched"
        results = {
            "company": co_action,
            "financials": _maybe_fetch(ticker, "financials.json", get_financials, args.force),
            "prices": _maybe_fetch(ticker, "prices.json", get_prices, args.force),
            "indicators": _maybe_fetch(ticker, "indicators.json", get_indicators, args.force),
        }
        time.sleep(SLEEP_S)
        flags = "  ".join(f"{k}={v[:8]}" for k, v in results.items())
        name = c.get("company_name") or c.get("company_name_ja") or "?"
        print(f"  [{i+1}/{len(target)}] {ticker}  {name[:22]:<22}  {flags}", flush=True)
        summary.append({"ticker": ticker, "name": name, **results})

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    for key in ("financials", "prices", "indicators"):
        c = Counter(r[key] for r in summary)
        breakdown = ", ".join(f"{k}={v}" for k, v in c.most_common())
        print(f"  {key:<11}: {breakdown}")

    manifest = {
        "sector_33_name": sector,
        "scale_filter": sorted(ACCEPT_SCALES) if not args.include_dash else "ALL_INCL_DASH",
        "include_dash": bool(args.include_dash),
        "fetched_tickers": [r["ticker"] for r in summary],
        "summary": summary,
    }
    suffix = "_dash" if args.include_dash else ""
    manifest_path = TEMPEST_DIR / "_meta" / f"{_slugify(sector)}{suffix}_manifest.json"
    _write(manifest_path, manifest)
    print(f"\nManifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
