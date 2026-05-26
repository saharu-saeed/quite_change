"""Run the agent on ONE company fresh (no cache) via Anthropic Direct API
and report exactly which year-pairs hit the LLM, token counts per call,
and real $ cost.

Uses the production-optimised config:
  - skip_simplify=True (no bilingual rewrite call)
  - decision_cutoff_fy=2023 (skip LLM on outcome pairs FY2024+)
  - use_cache=False (forced fresh)
"""
from __future__ import annotations
import os
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(override=True)

# Sonnet 4.6 pricing per million tokens (Anthropic direct = same as Bedrock).
PRICE_INPUT_PER_M = 3.0
PRICE_OUTPUT_PER_M = 15.0

# Patch _call_anthropic_direct BEFORE importing the agent to capture every call.
import app.tools.bedrock as bedrock_module  # noqa: E402

_USAGE_LOG: list[dict] = []
_orig_call = bedrock_module._call_anthropic_direct


def _patched_call(prompt: str, max_tokens: int, system_prompt: str | None = None) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    kwargs: dict = {
        "model": bedrock_module._resolve_anthropic_model(),
        "max_tokens": max_tokens,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        kwargs["system"] = [{
            "type": "text", "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }]
    msg = client.messages.create(**kwargs)
    u = msg.usage
    _USAGE_LOG.append({
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_create": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read":   getattr(u, "cache_read_input_tokens", 0) or 0,
    })
    return msg.content[0].text.strip()


bedrock_module._call_anthropic_direct = _patched_call

from app.subagents.quiet_change import analyze_company_multi_year  # noqa: E402

TICKER = "9432"  # NTT


def _calc_cost(input_t: int, output_t: int, cache_read: int = 0) -> float:
    """Cost in USD. Cache reads charged at 10% of input price."""
    fresh_input = input_t - cache_read  # cache_read tokens are billed separately
    return (fresh_input * PRICE_INPUT_PER_M / 1e6
            + cache_read * PRICE_INPUT_PER_M * 0.1 / 1e6
            + output_t * PRICE_OUTPUT_PER_M / 1e6)


def main() -> int:
    print(f"Anthropic Direct API: {os.environ.get('ANTHROPIC_API_KEY','')[:18]}...", flush=True)
    print(f"Model: {bedrock_module._resolve_anthropic_model()}", flush=True)
    print(f"Ticker: {TICKER} (NTT)", flush=True)
    print(f"Config: skip_simplify=True, decision_cutoff_fy=2023, use_cache=False\n", flush=True)

    print("Running agent (this will hit the LLM)...\n", flush=True)
    result = analyze_company_multi_year(
        TICKER, min_year=2020, run_tests=False,
        skip_simplify=True,
        decision_cutoff_fy=2023,
        use_cache=False,
        use_prompt_caching=False,
    )

    if "error" in result:
        print(f"ERROR: {result['error']}", flush=True)
        return 1

    pairs = result.get("pairs", [])
    real_pairs = [p for p in pairs if not p.get("history_only")]
    print("\n" + "=" * 84, flush=True)
    print("YEAR-PAIRS — which got LLM calls?", flush=True)
    print("=" * 84, flush=True)
    print(f"\n  {'#':>2s}  {'pair':>20s}  {'curr_fy':>7s}  {'LLM?':>5s}  {'judgment':>16s}", flush=True)
    print(f"  {'-'*2}  {'-'*20}  {'-'*7}  {'-'*5}  {'-'*16}", flush=True)
    decision_pair_count = 0
    for i, p in enumerate(real_pairs, 1):
        prev_fy = p["prev_fiscal_year"]
        curr_fy = p["curr_fiscal_year"]
        label = f"FY{prev_fy}->FY{curr_fy}"
        is_outcome = curr_fy > 2023
        llm = "NO" if is_outcome else "YES"
        if not is_outcome:
            decision_pair_count += 1
        judgment = p.get("outlook_judgment", "") or "(skipped)"
        print(f"  {i:>2d}  {label:>20s}  {curr_fy:>7d}  {llm:>5s}  {judgment:>16s}", flush=True)

    print(f"\n  → Decision pairs (LLM-called): {decision_pair_count}", flush=True)
    print(f"  → Outcome pairs (skipped, raw numbers only): {len(real_pairs) - decision_pair_count}", flush=True)

    print("\n" + "=" * 84, flush=True)
    print("PER-CALL LLM USAGE + COST", flush=True)
    print("=" * 84, flush=True)
    print(f"\n  {'call#':>5s}  {'input_tokens':>13s}  {'output_tokens':>14s}  {'cache_read':>11s}  {'$ cost':>9s}", flush=True)
    print(f"  {'-'*5}  {'-'*13}  {'-'*14}  {'-'*11}  {'-'*9}", flush=True)
    total_in = total_out = total_cache_read = 0
    total_cost = 0.0
    for i, u in enumerate(_USAGE_LOG, 1):
        cost = _calc_cost(u["input_tokens"], u["output_tokens"], u["cache_read"])
        total_in += u["input_tokens"]
        total_out += u["output_tokens"]
        total_cache_read += u["cache_read"]
        total_cost += cost
        print(f"  {i:>5d}  {u['input_tokens']:>13,d}  {u['output_tokens']:>14,d}  "
              f"{u['cache_read']:>11,d}  ${cost:>7.5f}", flush=True)
    print(f"  {'-'*5}  {'-'*13}  {'-'*14}  {'-'*11}  {'-'*9}", flush=True)
    print(f"  {'TOTAL':>5s}  {total_in:>13,d}  {total_out:>14,d}  "
          f"{total_cache_read:>11,d}  ${total_cost:>7.5f}", flush=True)

    print(f"\n  Pricing: ${PRICE_INPUT_PER_M}/M input, ${PRICE_OUTPUT_PER_M}/M output (Sonnet 4.6)", flush=True)
    print(f"\n  TOTAL COST FOR THIS COMPANY: ${total_cost:.4f} (≈ ${total_cost:.2f})", flush=True)
    print(f"  LLM calls made: {len(_USAGE_LOG)}", flush=True)
    print(f"  Avg per call: ${total_cost/len(_USAGE_LOG):.4f}" if _USAGE_LOG else "", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
