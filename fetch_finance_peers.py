"""Phase B ingest — finance sector seed (banks + securities + insurance).

Mirrors fetch_it_peers.py but seeds non-IT codes so the Similar Company agent
has a viable universe under JPX 7050 / 7100 / 7150 once these ZIPs land.

Run from the repo root with EDINET_API_KEY in .env. Idempotent — already-
downloaded ASRs are skipped. Picks fail safely (CyberAgent-style Sept FY
filers can be re-tried later by tweaking MIN_YEAR / scan windows).
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv()
from app.ingest.edinet_fetcher import ensure_asr_years
from app.config import ROOT

# JPX 7050 銀行業 (Banking) — three megabanks + Aozora as a mid-cap stress test
# JPX 7100 証券、商品先物取引業 (Securities) — Nomura + Daiwa
# JPX 7150 保険業 (Insurance) — three majors
# All March year-end except Daiwa (also March). The 5-year window is enough
# for trajectory similarity (≥3 overlapping growth-years).
CODES = [
    # Banking
    "8306",   # 三菱UFJフィナンシャル・グループ
    "8316",   # 三井住友フィナンシャルグループ
    "8411",   # みずほフィナンシャルグループ
    "8304",   # あおぞら銀行 (smaller, mid-cap reference)
    # Securities
    "8604",   # 野村ホールディングス
    "8601",   # 大和証券グループ本社
    # Insurance
    "8725",   # MS&ADインシュアランスグループHD
    "8630",   # SOMPOホールディングス
    "8766",   # 東京海上ホールディングス
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
