"""Quiet-change generalization verification for NTT (9432) and Fast Retailing (9983)."""
from dotenv import load_dotenv
load_dotenv()

import os, sys, json, re
print("AWS_REGION:", os.getenv("AWS_REGION"))
print("BEDROCK_MODEL_ID:", os.getenv("BEDROCK_MODEL_ID"))
print("AWS_ACCESS_KEY_ID set:", bool(os.getenv("AWS_ACCESS_KEY_ID")))

from app.subagents.quiet_change import analyze_company_multi_year, _COVERAGE_RULES

TARGETS = [
    # (code, min_year, target curr ZIP basename, target curr_filing_date prefix)
    ("9432", 2023, "S100TPQI", "2024-06-21"),
    ("9983", 2024, "S100X6X6", "2025-11-28"),
]

def find_target_pair(pairs, fdate_prefix):
    for p in pairs:
        if p.get("curr_filing_date", "").startswith(fdate_prefix):
            return p
    return None

results = {}
for code, min_year, zip_token, fdate in TARGETS:
    print(f"\n===== Running analyze_company_multi_year({code}, min_year={min_year}) =====", flush=True)
    out = analyze_company_multi_year(code, min_year=min_year, run_tests=False)
    if "error" in out:
        print("ERROR:", out["error"])
        continue
    pairs = out.get("pairs", [])
    print(f"  pairs returned: {len(pairs)}; curr_filing_dates: {[p['curr_filing_date'] for p in pairs]}")
    pair = find_target_pair(pairs, fdate)
    if pair is None:
        print(f"  TARGET PAIR with curr_filing_date {fdate}* NOT FOUND")
        continue

    # Get the source narrative (untruncated) directly from the series
    from app.subagents.quiet_change import load_asr_series, ROOT
    series = load_asr_series(ROOT / "data" / "edinet" / code)
    curr_series_entry = None
    for s in series:
        if zip_token in s.get("zip_path", "") or s.get("filing_date", "").startswith(fdate):
            curr_series_entry = s
            break
    qt_full = (curr_series_entry or {}).get("qualitative_text_full") or ""
    qt = (curr_series_entry or {}).get("qualitative_text") or ""
    print(f"  qualitative_text_full length: {len(qt_full)}; qualitative_text length: {len(qt)}")

    # Trigger checks against the un-truncated source
    trig_results = {}
    for rule in _COVERAGE_RULES:
        rid = rule["id"]
        if rule.get("narrative_must_contain") is not None:
            # inverted: source doesn't need trigger; just check output
            out_en = pair.get("explanation_advanced_en", "") + " " + pair.get("explanation_advanced_ja", "")
            invented = rule["output_re"].search(out_en) and not rule["narrative_must_contain"].search(qt_full)
            trig_results[rid] = {"trigger_in_source": False, "output_mention": bool(rule["output_re"].search(out_en)), "invented": bool(invented)}
            continue
        nre = rule["narrative_re"]
        in_src = bool(nre.search(qt_full)) if nre else False
        out_str = pair.get("explanation_advanced_en", "") + " " + pair.get("explanation_advanced_ja", "")
        in_out = bool(rule["output_re"].search(out_str))
        # capture matched trigger text
        m = nre.search(qt_full) if nre and in_src else None
        trig_results[rid] = {
            "trigger_in_source": in_src,
            "trigger_match": m.group(0) if m else None,
            "output_mention": in_out,
        }

    results[code] = {
        "pair_curr_filing_date": pair["curr_filing_date"],
        "prev_filing_date": pair["prev_filing_date"],
        "explanation_advanced_en": pair.get("explanation_advanced_en", ""),
        "explanation_advanced_ja": pair.get("explanation_advanced_ja", ""),
        "narrative_coverage_warnings": pair.get("narrative_coverage_warnings", []),
        "trigger_results": trig_results,
        "qt_full_len": len(qt_full),
    }

# Save full output for review
with open("verify_quiet_change_output.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n\n========== SUMMARY ==========")
for code, r in results.items():
    print(f"\n--- {code} (curr_filing_date={r['pair_curr_filing_date']}) ---")
    print(f"qt_full_len: {r['qt_full_len']}")
    print(f"narrative_coverage_warnings: {r['narrative_coverage_warnings']}")
    print(f"trigger_results:")
    for rid, tr in r["trigger_results"].items():
        print(f"  {rid}: {tr}")
    print(f"\nEN explanation:\n{r['explanation_advanced_en']}")
    print(f"\nJA explanation:\n{r['explanation_advanced_ja']}")
