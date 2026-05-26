import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv()
from app.subagents.quiet_change import analyze_company_multi_year
import re
r = analyze_company_multi_year("6758", min_year=2021, run_tests=False)
# Find the FY2021 -> FY2022 pair
target = next((p for p in r.get("pairs", []) if p.get("curr_fiscal_year") == 2022 and p.get("prev_fiscal_year") == 2021), None)
if not target:
    print("PAIR NOT FOUND")
    print("available pairs:", [(p.get("prev_fiscal_year"), p.get("curr_fiscal_year")) for p in r.get("pairs", [])])
    sys.exit(0)
en = target.get("explanation_advanced_en", "") or ""
ja = target.get("explanation_advanced_ja", "") or ""
print("=== warnings ===")
for w in target.get("narrative_coverage_warnings", []):
    print(" -", w["rule"])
print("\n=== EN (first 800) ===")
print(en[:800])
print("\n=== contains checks ===")
for kw in ["Crunchyroll", "Spider-Man", "GSN", "home entertainment", "theatrical", "acquisition", "M&A", "divest", "sold"]:
    if kw.lower() in en.lower():
        print(f"  EN mentions: {kw}")
for kw in ["Crunchyroll", "スパイダーマン", "GSN", "ホームエンタテインメント", "劇場", "買収", "取得", "譲渡", "売却", "相殺", "ものの"]:
    if kw in ja:
        print(f"  JA mentions: {kw}")
