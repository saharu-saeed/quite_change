# -*- coding: utf-8 -*-
"""Run the locked lighter prompt against one company and print the JSON result.

Usage (from the quite_change/ directory):
    python -m research.run_one_company 7974 "Nintendo"

    # Save to file instead of stdout:
    python -m research.run_one_company 7974 "Nintendo" --output nintendo.json

    # Use the Japanese prompt (output prose still Japanese either way; the
    # difference is only the instructions sent to the model):
    python -m research.run_one_company 7974 "Nintendo" --lang jp

Requirements:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...     # or set in environment

Approximate cost per company (Sonnet 4.6, real-time API):
    ~$0.25-0.30 including web search fees, ~6 min wall-clock.
    Batched (50% off via Anthropic Batch API): ~$0.15-0.19.

This script is suitable for testing 1-3 companies. For the full ~2,900-company
batch, switch to the Anthropic Batch API (separate script not included here).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Force UTF-8 stdout/stderr — needed on Windows so that Japanese chars in the
# help text or output don't trigger UnicodeEncodeError under cp932/cp1252.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

try:
    from anthropic import Anthropic
except ImportError:
    print(
        "Error: the 'anthropic' package is not installed.\n"
        "Install it with:  pip install anthropic",
        file=sys.stderr,
    )
    sys.exit(1)

# Allow running both as a module (`python -m research.run_one_company`)
# and as a standalone script (`python research/run_one_company.py`).
if __package__:
    from .prompts import build_prompt
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from prompts import build_prompt  # type: ignore


MODEL_ID = "claude-sonnet-4-6"
MAX_TOKENS = 8000
MAX_WEB_SEARCHES = 7


def research_company(client: "Anthropic", code: str, company_name: str, lang: str = "en") -> dict:
    """Call the Anthropic API with the locked lighter prompt + web search tool.

    Returns the parsed JSON dict the model produced. Raises RuntimeError on
    failure to call the API or parse the response.
    """
    prompt = build_prompt(code, company_name, lang=lang)

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        tools=[
            {
                # Anthropic's hosted server-side web search tool.
                # Model uses it autonomously; no client-side tool result handling needed.
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": MAX_WEB_SEARCHES,
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    # Concatenate any text blocks in the final response (the model may interleave
    # text and tool_use blocks; we just want the final text content).
    parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    final_text = "\n".join(parts).strip()

    if not final_text:
        raise RuntimeError("Model returned no text content. Full response:\n" + repr(response))

    # The prompt asks for strict JSON. Extract the first {...} block.
    match = re.search(r"\{.*\}", final_text, re.DOTALL)
    if not match:
        raise RuntimeError(
            "Could not find a JSON object in the model output.\nResponse was:\n" + final_text
        )

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Model output contained malformed JSON: {e}\nExtracted block:\n{match.group(0)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Research one Japanese listed company using the locked lighter prompt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m research.run_one_company 7974 \"Nintendo\"\n"
            "  python -m research.run_one_company 9201 \"Japan Airlines\" --output jal.json\n"
            "  python -m research.run_one_company 1332 \"Nissui\" --lang jp\n"
        ),
    )
    parser.add_argument("code", help="4-digit stock code (e.g. 7974)")
    parser.add_argument("company_name", help="Company display name (e.g. 'Nintendo' or 'Nintendo / 任天堂')")
    parser.add_argument(
        "--lang",
        choices=("en", "jp"),
        default="en",
        help="Language of the prompt instructions sent to the model (default: en). "
             "Output prose will be Japanese either way.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Write JSON to this file. If omitted, JSON is printed to stdout.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY environment variable is not set.\n"
            "Get one from https://console.anthropic.com/ and:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        return 1

    client = Anthropic(api_key=api_key)

    print(f"Researching {args.code} ({args.company_name})…", file=sys.stderr)
    print(f"Model: {MODEL_ID}, web searches: up to {MAX_WEB_SEARCHES}", file=sys.stderr)
    print("This typically takes 4-7 minutes.", file=sys.stderr)
    print(file=sys.stderr)

    try:
        result = research_company(client, args.code, args.company_name, lang=args.lang)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Wrote {args.output} ({len(output_json):,} bytes)", file=sys.stderr)
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
