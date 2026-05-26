"""Option A smoke test — run analyze_company_quarterly() on NTT only.

Single-ticker test to verify:
  - The function executes without errors
  - Quarterly LLM judgments look sensible (not garbage)
  - Compare reasoning depth to the annual agent's output

Budget: ~$0.36 (9 LLM calls × ~$0.04). Wall time: ~10 min.
Bedrock Sonnet 4.6; no Anthropic Direct.
"""
from __future__ import annotations
import json
import os
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()
assert not os.environ.get("ANTHROPIC_API_KEY"), \
    "ANTHROPIC_API_KEY must remain unset — user paused it. Aborting."

from app.subagents.quiet_change import analyze_company_quarterly  # noqa: E402


def main() -> int:
    print("Option A — analyze_company_quarterly() on NTT (9432)", flush=True)
    print(f"BEDROCK_MODEL_ID: {os.environ.get('BEDROCK_MODEL_ID')}", flush=True)
    print(flush=True)

    import time
    t0 = time.time()
    result = analyze_company_quarterly("9432", min_year=2020)
    elapsed = time.time() - t0
    print(f"Wall time: {elapsed:.1f}s\n", flush=True)

    if "error" in result:
        print(f"ERROR: {result['error']}", flush=True)
        return 1

    pairs = result.get("pairs", [])
    print(f"Total pairs: {len(pairs)}", flush=True)
    print(flush=True)

    print("=" * 90, flush=True)
    print("PER-QUARTER OUTPUT")
    print("=" * 90, flush=True)
    for i, p in enumerate(pairs, 1):
        pair_lbl = f"FY{p['prev_fiscal_year']}Q{p['prev_fiscal_quarter']} -> FY{p['curr_fiscal_year']}Q{p['curr_fiscal_quarter']}"
        rev_d = p.get("revenue_delta_pct")
        op_d = p.get("op_profit_delta_pct")
        stk = p.get("stock_5d_return_pct")
        doc_t = p.get("document_type", "?")
        j = p.get("outlook_judgment", "?")
        print(f"\n[{i}] {pair_lbl}  [{doc_t}]  ({p.get('curr_filing_date','?')})")
        print(f"    revenue Δ: {rev_d:+.1f}%  op Δ: {op_d:+.1f}% (None if missing)  stock 5d: {stk}")
        print(f"    judgment: {j}")
        reason = p.get("outlook_reason_en", "")[:400]
        print(f"    reason: {reason}")

    out_path = ROOT / "outputs" / "quarterly_smoke_ntt.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                   default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
