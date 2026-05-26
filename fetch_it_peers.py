import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv()
from pathlib import Path
from app.ingest.edinet_fetcher import ensure_asr_years
from app.config import ROOT

CODES = ["9433", "9434", "9613", "4307", "4684", "4716", "4751", "4689"]
MIN_YEAR = 2020   # widened from 2024 → 2020 so the trajectory-similarity score
                  # has ≥3 overlapping growth-years for these recently-ingested
                  # peers. Idempotent — already-downloaded ASRs are skipped.
data_dir = ROOT / "data"

for code in CODES:
    print(f"\n=== {code} ===", flush=True)
    try:
        res = ensure_asr_years(code, min_year=MIN_YEAR, data_dir=data_dir)
        print(res, flush=True)
    except Exception as e:
        print(f"  ERROR: {e}", flush=True)
print("\nDONE", flush=True)
