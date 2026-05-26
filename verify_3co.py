from dotenv import load_dotenv; load_dotenv()
from app.subagents.quiet_change import analyze_company_multi_year
import json, re, sys

results = {}
for code, min_year in [("9432", 2023), ("7201", 2023), ("4755", 2023)]:
    try:
        r = analyze_company_multi_year(code, min_year=min_year, run_tests=False)
        latest = r["pairs"][-1] if r.get("pairs") else {}
        results[code] = {
            "warnings": latest.get("narrative_coverage_warnings", []),
            "en": (latest.get("explanation_advanced_en") or "")[:600],
            "ja": (latest.get("explanation_advanced_ja") or "")[:600],
            "ja_nonempty": bool(latest.get("explanation_advanced_ja", "").strip()),
            "ja_has_japanese": bool(re.search(r'[぀-ヿ一-鿿]', latest.get("explanation_advanced_ja") or "")),
            "en_starts_clean": (latest.get("explanation_advanced_en") or "")[:1] not in ["S", "I", "L"]
                              or not (latest.get("explanation_advanced_en") or "").startswith(("Step ", "I scanned", "Let me ")),
            "curr_year": latest.get("curr_fiscal_year"),
            "prev_year": latest.get("prev_fiscal_year"),
        }
        # Persist after each company so we don't lose progress on timeout.
        open("verify_3co_results.json", "w", encoding="utf-8").write(
            json.dumps(results, ensure_ascii=False, indent=2))
        print(f"{code} done: warnings={results[code]['warnings']}, "
              f"ja_nonempty={results[code]['ja_nonempty']}", flush=True)
    except Exception as e:
        results[code] = {"error": str(e)}
        open("verify_3co_results.json", "w", encoding="utf-8").write(
            json.dumps(results, ensure_ascii=False, indent=2))
        print(f"{code} ERROR: {e}", flush=True)
