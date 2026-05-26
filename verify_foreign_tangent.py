"""Phase A foreign-tangent verification — fast variant.

Runs ONE recent YoY pair per company instead of multi-year. Prints progress
inline so we can see the script working. No EDINET auto-fetch, no yfinance
auto-fetch (yfinance still runs but is bounded by a short timeout).

Three companies: SoftBank Corp (9434), Sony (6758), Rakuten (4755) — the
filers the user named. For each, picks the MOST RECENT pair available
locally and prints the explanation + foreign-tangent classification.

Output: a markdown report on stdout. Three sections (one per bucket A/B/C)
followed by a verdict line.
"""
from __future__ import annotations
import sys, io, re, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

from dotenv import load_dotenv; load_dotenv()
from pathlib import Path
import time

# Skip EDINET auto-fetch entirely — local data only.
import app.ingest.edinet_fetcher as _ef
_ef.ensure_asr_years = lambda code, **kw: {
    "code": code, "downloaded_years": [], "still_missing_years": [],
    "skipped": True,
}

from app.ingest.edinet_loader import load_asr_series
from app.config import ROOT
from app.subagents.quiet_change import (
    analyze_company, _FOREIGN_TOKEN_RE,
    _FOREIGN_DRIVER_INDICATORS_RE, _NUMERIC_ATTRIBUTION_RE,
)


def classify_sentence(sent, narrative, segments):
    src_lower = (narrative or "").lower()
    seg_blob = " ".join(
        (s.get("name", "") + " " + s.get("name_ja", "")).lower()
        for s in (segments or [])
    )
    for m in _FOREIGN_TOKEN_RE.finditer(sent):
        tok = m.group(0).strip().lower()
        if tok and (tok in src_lower or tok in seg_blob):
            return "driver (token in source/segments)"
    if _FOREIGN_DRIVER_INDICATORS_RE.search(sent):
        return "driver (attribution verb / transaction noun / FX / revenue language)"
    if _NUMERIC_ATTRIBUTION_RE.search(sent):
        return "driver (numeric attribution in same sentence)"
    return "tangent (peer color / market context, no driver tie)"


def build_fund(code: str) -> dict | None:
    """Construct the fund dict analyze_company expects, picking the most
    recent locally-available YoY pair from the ASR series."""
    folder = ROOT / "data" / "edinet" / code
    if not folder.is_dir():
        return None
    series = load_asr_series(folder)
    if len(series) < 2:
        return None
    prev = series[-2]
    curr = series[-1]
    return {
        "code": code,
        "name": code,  # let analyze_company resolve the name from CONFIG
        "filing_type": "edinet_asr",
        "fiscal_period": curr.get("period_end", ""),
        "prev_filing": {"zip_path": prev["zip_path"],
                        "filing_date": prev["filing_date"]},
        "curr_filing": {"zip_path": curr["zip_path"],
                        "filing_date": curr["filing_date"]},
        "curr_text": curr.get("qualitative_text", ""),
        "curr_raw_text": curr.get("qualitative_text_full", ""),
    }


def report(code: str, name: str):
    print(f"\n## {code} {name}", flush=True)
    fund = build_fund(code)
    if fund is None:
        print(f"  (no usable ASR pair locally for {code})", flush=True)
        return None
    fy_label = f"{fund['prev_filing']['filing_date'][:4]}->{fund['curr_filing']['filing_date'][:4]}"
    print(f"  Pair: {fy_label}", flush=True)
    t0 = time.time()
    try:
        r = analyze_company(code, fund)
    except Exception as e:
        print(f"  ERROR: {e}", flush=True)
        traceback.print_exc()
        return None
    elapsed = time.time() - t0
    print(f"  Analysis time: {elapsed:.1f}s", flush=True)
    if r.get("error"):
        print(f"  ERROR: {r['error']}", flush=True)
        return None

    expl_en = r.get("explanation_advanced_en", "") or ""
    warnings = r.get("narrative_coverage_warnings", [])
    rule_fired = any(w["rule"] == "foreign_tangent_check" for w in warnings)
    other_warns = [w["rule"] for w in warnings if w["rule"] != "foreign_tangent_check"]
    print(f"  foreign_tangent_check fired: **{rule_fired}**", flush=True)
    if other_warns:
        print(f"  other warnings: {other_warns}", flush=True)

    sentences = re.split(r"(?<=[\.!?])\s+", expl_en)
    foreign_sentences = [s for s in sentences if _FOREIGN_TOKEN_RE.search(s)]
    if not foreign_sentences:
        print("  foreign-token sentences: none", flush=True)
        excerpt = expl_en[:400].replace("\n", " ")
        print(f"  Explanation excerpt: {excerpt}{'...' if len(expl_en) > 400 else ''}", flush=True)
        return {
            "code": code, "name": name, "fy": fy_label,
            "rule_fired": rule_fired, "any_tangent": False,
            "tangent_sentences": [],
        }

    print(f"  foreign-token sentences: {len(foreign_sentences)}", flush=True)
    narrative = fund.get("curr_raw_text", "")
    tangent_sents = []
    for i, sent in enumerate(foreign_sentences, 1):
        kind = classify_sentence(sent, narrative, r.get("segments", []))
        toks = sorted({m.group(0).strip() for m in _FOREIGN_TOKEN_RE.finditer(sent)})
        print(f"    {i}. [{kind}] tokens={toks}", flush=True)
        sent_clean = sent.strip().replace("\n", " ")
        print(f"       > {sent_clean[:300]}{'...' if len(sent_clean) > 300 else ''}", flush=True)
        if kind.startswith("tangent"):
            tangent_sents.append(sent_clean[:200])
    return {
        "code": code, "name": name, "fy": fy_label,
        "rule_fired": rule_fired,
        "any_tangent": bool(tangent_sents),
        "tangent_sentences": tangent_sents,
    }


def main():
    print("# Phase A foreign-tangent verification — fast variant\n", flush=True)
    print("Runs the most recent locally-available YoY pair for each of three "
          "mega-cap filers (the original SoftBank case + Sony + Rakuten). "
          "Three-bucket classification per the user's spec.\n", flush=True)

    targets = [
        ("9434", "SoftBank Corp"),
        ("6758", "Sony Group"),
        ("4755", "Rakuten Group"),
    ]
    results = []
    for code, name in targets:
        r = report(code, name)
        if r is not None:
            results.append(r)

    # Three-bucket summary.
    print("\n\n# Three-bucket summary\n", flush=True)
    bucket_a = [r for r in results if r["any_tangent"] and r["rule_fired"]]
    bucket_b = [r for r in results if not r["any_tangent"]]
    bucket_c = [r for r in results if r["any_tangent"] and not r["rule_fired"]]

    print(f"## A. Fired correctly  ({len(bucket_a)})", flush=True)
    for r in bucket_a:
        print(f"  - {r['code']} {r['name']} {r['fy']}", flush=True)
        for s in r["tangent_sentences"]:
            print(f"      \"{s}\"", flush=True)
    print(f"\n## B. Trigger absent  ({len(bucket_b)})", flush=True)
    for r in bucket_b:
        print(f"  - {r['code']} {r['name']} {r['fy']}", flush=True)
    print(f"\n## C. Trigger present but rule missed  ({len(bucket_c)})  <- regressions", flush=True)
    for r in bucket_c:
        print(f"  - {r['code']} {r['name']} {r['fy']}", flush=True)
        for s in r["tangent_sentences"]:
            print(f"      \"{s}\"", flush=True)

    print(f"\n## Verdict: {'PASS' if not bucket_c else 'FAIL'}", flush=True)


if __name__ == "__main__":
    main()
