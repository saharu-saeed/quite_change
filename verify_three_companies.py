"""End-to-end verification for NTT (9432), Nissan (7201), Rakuten (4755)."""
from dotenv import load_dotenv
load_dotenv()

import os, sys, json, re
print("AWS_REGION:", os.getenv("AWS_REGION"))
print("BEDROCK_MODEL_ID:", os.getenv("BEDROCK_MODEL_ID"))
print("AWS_ACCESS_KEY_ID set:", bool(os.getenv("AWS_ACCESS_KEY_ID")))

from app.subagents.quiet_change import (
    analyze_company_multi_year, _COVERAGE_RULES,
    load_asr_series, ROOT,
)

# Today is 2026-04-28; curr_year = 2026 → min_year = 2025.
TARGETS = [
    ("9432", 2025),  # NTT
    ("7201", 2025),  # Nissan
    ("4755", 2025),  # Rakuten
]

JP_RE = re.compile(r"[぀-ヿ一-鿿]")
PREAMBLE_RE = re.compile(
    r"^\s*(step\s*\d|let me|i (?:will|'ll|scanned|checked|walk|need)|first[, ]|here is|here's|"
    r"i'm going to|to (?:answer|address)|the following|okay|ok[, ]|sure[, ]|"
    r"based on|analyzing|following the|per the|as requested)",
    re.IGNORECASE,
)

results = {}
for code, min_year in TARGETS:
    print(f"\n===== Running analyze_company_multi_year({code}, min_year={min_year}) =====", flush=True)
    try:
        out = analyze_company_multi_year(code, min_year=min_year, run_tests=False)
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        results[code] = {"error": str(e)}
        continue
    if "error" in out:
        print("  ERROR:", out["error"])
        results[code] = {"error": out["error"]}
        continue

    pairs = out.get("pairs", [])
    print(f"  pairs returned: {len(pairs)}; curr_filing_dates: {[p.get('curr_filing_date') for p in pairs]}")
    if not pairs:
        results[code] = {"error": "no pairs"}
        continue
    pair = pairs[-1]  # most recent

    # Get the source narrative (un-truncated) from the series
    series = load_asr_series(ROOT / "data" / "edinet" / code)
    curr_filing_date = pair.get("curr_filing_date", "")
    curr_series_entry = None
    for s in series:
        if s.get("filing_date", "") == curr_filing_date:
            curr_series_entry = s
            break
    qt_full = (curr_series_entry or {}).get("qualitative_text_full") or ""

    en = pair.get("explanation_advanced_en", "") or ""
    ja = pair.get("explanation_advanced_ja", "") or ""

    ja_has_jp = bool(JP_RE.search(ja))
    en_first80 = en[:80]
    ja_first80 = ja[:80]
    preamble_contaminated = bool(PREAMBLE_RE.match(en))

    # Per-rule classification
    rule_classification: dict[str, str] = {}
    rule_details: dict[str, dict] = {}
    out_str = en + " " + ja
    for rule in _COVERAGE_RULES:
        rid = rule["id"]
        if rule.get("narrative_must_contain") is not None:
            # inverted (no_expectations_invented)
            output_mention = bool(rule["output_re"].search(out_str))
            src_has = bool(rule["narrative_must_contain"].search(qt_full))
            if output_mention and not src_has:
                bucket = "FALSE POSITIVE"  # invented
            else:
                bucket = "TRIGGER ABSENT"
            rule_details[rid] = {"output_mention": output_mention, "src_has_consensus": src_has}
            rule_classification[rid] = bucket
            continue
        nre = rule["narrative_re"]
        in_src = bool(nre.search(qt_full))
        in_out = bool(rule["output_re"].search(out_str))
        m = nre.search(qt_full) if in_src else None
        rule_details[rid] = {
            "trigger_in_source": in_src,
            "trigger_match": m.group(0) if m else None,
            "output_mention": in_out,
        }
        if in_src and in_out:
            bucket = "FIRED CORRECTLY"
        elif in_src and not in_out:
            bucket = "RULE MISSED"
        elif (not in_src) and in_out:
            bucket = "FALSE POSITIVE"  # output mentions w/o trigger — could be legitimate
        else:
            bucket = "TRIGGER ABSENT"
        rule_classification[rid] = bucket

    results[code] = {
        "curr_filing_date": curr_filing_date,
        "prev_filing_date": pair.get("prev_filing_date"),
        "explanation_advanced_en": en,
        "explanation_advanced_ja": ja,
        "narrative_coverage_warnings": pair.get("narrative_coverage_warnings", []),
        "ja_has_japanese": ja_has_jp,
        "ja_nonempty": bool(ja.strip()),
        "ja_first80": ja_first80,
        "en_first80": en_first80,
        "preamble_contaminated": preamble_contaminated,
        "rule_classification": rule_classification,
        "rule_details": rule_details,
        "qt_full_len": len(qt_full),
    }

with open("verify_three_output.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n\n========== SUMMARY ==========")
for code, r in results.items():
    print(f"\n--- {code} ---")
    if "error" in r:
        print(f"  ERROR: {r['error']}")
        continue
    print(f"curr_filing_date: {r['curr_filing_date']}")
    print(f"qt_full_len: {r['qt_full_len']}")
    print(f"narrative_coverage_warnings: {r['narrative_coverage_warnings']}")
    print(f"JA nonempty: {r['ja_nonempty']}, has_japanese: {r['ja_has_japanese']}")
    print(f"JA first80: {r['ja_first80']!r}")
    print(f"EN first80: {r['en_first80']!r}")
    print(f"preamble_contaminated: {r['preamble_contaminated']}")
    print(f"rule_classification:")
    for rid, b in r["rule_classification"].items():
        print(f"  {rid}: {b}  details={r['rule_details'][rid]}")
    print(f"\nEN explanation:\n{r['explanation_advanced_en']}")
    print(f"\nJA explanation:\n{r['explanation_advanced_ja']}")
