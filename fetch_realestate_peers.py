"""Phase B ingest — real estate sector seed (JPX 8050 不動産業).

Major developers + a couple of mid-caps so the universe has size variation
when the Similar Company agent runs sector_code='8050'.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv()
from app.ingest.edinet_fetcher import ensure_asr_years
from app.config import ROOT

CODES = [
    "8801",   # 三井不動産
    "8802",   # 三菱地所
    "8830",   # 住友不動産
    "3289",   # 東急不動産ホールディングス
    "8804",   # 東京建物
    "1878",   # 大東建託 (housing-construction-adjacent; could be in 1850 instead, lookup decides)
    "3231",   # 野村不動産ホールディングス
    "8848",   # レオパレス21 (mid-cap reference)
]
MIN_YEAR = 2020
data_dir = ROOT / "data"

for code in CODES:
    print(f"\n=== {code} ===", flush=True)
    try:
        res = ensure_asr_years(code, min_year=MIN_YEAR, data_dir=data_dir)
        print(res, flush=True)
    except Exception as e:
        print(f"  ERROR: {e}", flush=True)
print("\nDONE", flush=True)
