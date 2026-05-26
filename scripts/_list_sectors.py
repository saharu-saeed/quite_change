"""Print Tempest's available 33業種 sector names + sizes."""
import sys
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

from app.ingest.tempest_client import list_all_companies, list_sectors

# Try the /sectors endpoint first
try:
    sectors = list_sectors()
    print("From /sectors:")
    print(sectors)
    print()
except Exception as e:
    print(f"/sectors failed: {e}\n")

# Tally by listing all companies and grouping by sector_33_name.
print("Tallying via /companies (all)...")
all_co = list_all_companies()
from collections import Counter
sec_counts = Counter(c.get("sector_33_name") for c in all_co)
band = {"TOPIX Small 1", "TOPIX Small 2", "TOPIX Mid400"}
midcap_counts = Counter(
    c.get("sector_33_name") for c in all_co if c.get("scale_category") in band
)

print(f"\n{'Sector':<24} {'Total':<7} {'Midcap':<7}")
print("-" * 42)
for sec, total in sec_counts.most_common():
    mc = midcap_counts.get(sec, 0)
    print(f"{(sec or '?'):<24} {total:<7} {mc:<7}")
