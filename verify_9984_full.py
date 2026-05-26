import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv()
from app.subagents.quiet_change import analyze_company_multi_year
r = analyze_company_multi_year("9984", min_year=2024, run_tests=False)
latest = r["pairs"][-1]
en = latest.get("explanation_advanced_en", "")
ja = latest.get("explanation_advanced_ja", "")
print("=== EN (full) ===")
print(en)
print("\n=== JA (full) ===")
print(ja)
print("\n=== checks ===")
import re
for kw in ["Fortress", "Mubadala", "deconsolidat", "subsidiary", "divest", "spin"]:
    if kw.lower() in en.lower():
        print(f"EN mentions: {kw}")
for kw in ["フォートレス", "Fortress", "Mubadala", "支配喪失", "支配の喪失", "子会社", "連結除外"]:
    if kw in ja:
        print(f"JA mentions: {kw}")
