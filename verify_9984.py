import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()
from app.subagents.quiet_change import analyze_company_multi_year
import re, json
r = analyze_company_multi_year("9984", min_year=2024, run_tests=False)
latest = r["pairs"][-1] if r.get("pairs") else {}
en = latest.get("explanation_advanced_en", "") or ""
ja = latest.get("explanation_advanced_ja", "") or ""
out = {
    "curr_year": latest.get("curr_fiscal_year"),
    "prev_year": latest.get("prev_fiscal_year"),
    "warnings": latest.get("narrative_coverage_warnings", []),
    "ja_nonempty": bool(ja.strip()),
    "ja_has_japanese": bool(re.search(r'[぀-ヿ一-鿿]', ja)),
    "en_starts_clean": not en.startswith(("```", "Step ", "I scanned", "Let me ")),
    "ma_mentions_en": [w for w in ["acquisition","acquired","divest","sold","sale of","M&A"] if w.lower() in en.lower()],
    "ma_mentions_ja": [w for w in ["買収","取得","完全子会社化","譲渡","売却"] if w in ja],
    "en_first_300": en[:300],
    "ja_first_300": ja[:300],
}
print(json.dumps(out, ensure_ascii=False, indent=2))
