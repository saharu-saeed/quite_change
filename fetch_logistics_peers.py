"""Phase B ingest — transport / logistics seed.

JPX 33業種 splits this across three codes:
  5050 陸運業 (Land Transport) — JR, トラック, etc.
  5100 海運業 (Marine Transport) — 商船, 川崎汽船, etc.
  5150 空運業 (Air Transport) — ANA, JAL
  5200 倉庫・運輸関連業 (Warehousing & Transport-related)

When the Similar Company agent is run with sector_code in {5050, 5100, 5150,
5200}, only the matching subset is in the universe. Seeding all four sub-
sectors gives the user the option to pick any one.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv()
from app.ingest.edinet_fetcher import ensure_asr_years
from app.config import ROOT

CODES = [
    # 陸運業 5050
    "9020",   # JR東日本
    "9021",   # JR西日本
    "9022",   # JR東海
    "9064",   # ヤマトホールディングス
    "9143",   # SGホールディングス (佐川急便)
    "9147",   # NIPPON EXPRESS HOLDINGS (日本通運)
    # 海運業 5100
    "9101",   # 日本郵船
    "9104",   # 商船三井
    "9107",   # 川崎汽船
    # 空運業 5150
    "9201",   # 日本航空
    "9202",   # ANAホールディングス
    # 倉庫・運輸関連業 5200
    "9301",   # 三菱倉庫
    "9302",   # 三井倉庫ホールディングス
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
