"""Verify each sector's fetched cache has only the intended scale bands.

Compares:
  - What the Tempest API says exists for each sector + scale
  - What we actually have on disk (data/tempest/{ticker}/company.json)
  - Whether any name leaked outside the {Small 1, Small 2, Mid400} band
"""
import json
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.ingest.tempest_client import list_all_companies

SECTORS = ["化学", "食料品", "その他製品", "金属製品", "ガラス･土石製品", "繊維製品"]
ACCEPT = {"TOPIX Small 1", "TOPIX Small 2", "TOPIX Mid400"}
ALL_SCALES = {"TOPIX Core30", "TOPIX Large70", "TOPIX Mid400",
              "TOPIX Small 1", "TOPIX Small 2", None}
TEMPEST = ROOT / "data" / "tempest"


def _cache_scale(ticker: str) -> str | None:
    p = TEMPEST / ticker / "company.json"
    if not p.exists():
        return None
    raw = json.load(open(p, encoding="utf-8"))
    d = raw.get("data", raw)
    if isinstance(d, list) and d:
        d = d[0]
    return d.get("scale_category")


for sector in SECTORS:
    print("=" * 70)
    print(f"Sector: {sector}")
    print("=" * 70)
    api_rows = list_all_companies(sector_33_name=sector)
    api_total = len(api_rows)

    api_by_scale = Counter(c.get("scale_category") for c in api_rows)
    api_in_band = sum(api_by_scale[s] for s in ACCEPT)

    api_tickers_in_band = {c["ticker"] for c in api_rows if c.get("scale_category") in ACCEPT}
    cached_tickers = {c["ticker"] for c in api_rows if (TEMPEST / c["ticker"] / "company.json").exists()}

    missing = api_tickers_in_band - cached_tickers
    extra = cached_tickers - api_tickers_in_band  # things we cached but aren't in-band

    print(f"  API total for sector:        {api_total}")
    print(f"  API in target band:          {api_in_band}")
    print(f"  Cached tickers from sector:  {len(cached_tickers)}")
    print(f"  Missing (in-band, not cached): {len(missing)}")
    print(f"  Extra   (cached, not in-band): {len(extra)}")

    print(f"\n  API scale breakdown:")
    for s, n in sorted(api_by_scale.items(), key=lambda kv: -kv[1]):
        marker = "  <-- target" if s in ACCEPT else ""
        print(f"    {(s or 'None'):<16}: {n}{marker}")

    if extra:
        print(f"\n  ⚠ Extras (cached but outside target band):")
        for t in sorted(extra):
            sc = _cache_scale(t)
            print(f"    {t}  scale={sc}")
    if missing:
        print(f"\n  ⚠ Missing (in-band but not cached):")
        for t in sorted(list(missing))[:10]:
            api_row = next((c for c in api_rows if c["ticker"] == t), {})
            print(f"    {t}  {api_row.get('company_name','?')[:24]:<24}  scale={api_row.get('scale_category')}")
        if len(missing) > 10:
            print(f"    ... and {len(missing)-10} more")
    print()
