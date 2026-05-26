import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()
from app.subagents.quiet_change import analyze_company_multi_year
import re
r = analyze_company_multi_year("4755", min_year=2024, run_tests=False)
latest = r["pairs"][-1] if r.get("pairs") else {}
print("curr/prev:", latest.get("curr_fiscal_year"), latest.get("prev_fiscal_year"))
print("warnings:", latest.get("narrative_coverage_warnings", []))
ja = latest.get("explanation_advanced_ja", "")
en = latest.get("explanation_advanced_en", "")
print("ja_nonempty:", bool(ja.strip()))
print("ja_has_japanese:", bool(re.search(r'[぀-ヿ一-鿿]', ja)))
print("en_starts_clean:", not en.startswith(("```", "Step ", "I scanned", "Let me ")))
print("EN[:300]:", en[:300])
print("---")
print("JA[:300]:", ja[:300])
