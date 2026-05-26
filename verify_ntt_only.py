"""NTT-only quiet-change verification for offset/mixed-driver rule fix."""
from dotenv import load_dotenv
load_dotenv()

import os, json, re
print("AWS_REGION:", os.getenv("AWS_REGION"))
print("BEDROCK_MODEL_ID:", os.getenv("BEDROCK_MODEL_ID"))

from app.subagents.quiet_change import analyze_company_multi_year

CODE = "9432"
FDATE_PREFIX = "2024-06-21"

print(f"\n===== analyze_company_multi_year({CODE}, min_year=2023) =====", flush=True)
out = analyze_company_multi_year(CODE, min_year=2023, run_tests=False)
if "error" in out:
    print("ERROR:", out["error"]); raise SystemExit(1)

pairs = out.get("pairs", [])
print(f"pairs: {len(pairs)}; curr_filing_dates: {[p['curr_filing_date'] for p in pairs]}")

# latest pair
pair = None
for p in pairs:
    if p.get("curr_filing_date", "").startswith(FDATE_PREFIX):
        pair = p; break
if pair is None and pairs:
    pair = pairs[-1]

en = pair.get("explanation_advanced_en", "")
ja = pair.get("explanation_advanced_ja", "")
warns = pair.get("narrative_coverage_warnings", [])

print(f"\ncurr_filing_date: {pair.get('curr_filing_date')}")
print(f"prev_filing_date: {pair.get('prev_filing_date')}")
print(f"\nnarrative_coverage_warnings: {warns}")
print(f"mixed_drivers_despite present: {'mixed_drivers_despite' in warns}")

PAT = re.compile(r"despite|ものの|にもかかわらず|一方で|反面|partially offset|offset by|相殺", re.IGNORECASE)
print("\n--- EN paired-construction matches ---")
for sent in re.split(r"(?<=[\.\!\?])\s+", en):
    if PAT.search(sent):
        print(f"  >> {sent.strip()}")
print("\n--- JA paired-construction matches ---")
for sent in re.split(r"(?<=[。！？])", ja):
    if PAT.search(sent):
        print(f"  >> {sent.strip()}")

print("\n\n========== FULL EN ==========")
print(en)
print("\n========== FULL JA ==========")
print(ja)

with open("verify_ntt_only_output.json", "w", encoding="utf-8") as f:
    json.dump({
        "curr_filing_date": pair.get("curr_filing_date"),
        "prev_filing_date": pair.get("prev_filing_date"),
        "narrative_coverage_warnings": warns,
        "explanation_advanced_en": en,
        "explanation_advanced_ja": ja,
    }, f, ensure_ascii=False, indent=2)
