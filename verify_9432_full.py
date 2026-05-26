import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv()
from app.subagents.quiet_change import analyze_company_multi_year
r = analyze_company_multi_year("9432", min_year=2024, run_tests=False)
latest = r["pairs"][-1]
en = latest.get("explanation_advanced_en", "") or ""
ja = latest.get("explanation_advanced_ja", "") or ""
print("warnings:", [w["rule"] for w in latest.get("narrative_coverage_warnings", [])])
print("ja_nonempty:", bool(ja.strip()))
print("EN[:500]:", en[:500])
print("---")
for kw in ["acquisition", "divest", "despite", "subsidiary", "sold"]:
    if kw.lower() in en.lower(): print(f"EN mentions: {kw}")
for kw in ["買収", "取得", "譲渡", "売却", "支配喪失", "ものの", "相殺"]:
    if kw in ja: print(f"JA mentions: {kw}")
