"""Regression test for the Bedrock-routing default in quiet_change_v2.

The 2026-05-22 Bedrock leak happened because the module defaulted to Bedrock
unless explicitly disabled. The fix (2026-05-23) makes ANTHROPIC_API_KEY win
by default. This test pins that behavior across all four env combinations.

Run: python scripts/test_bedrock_routing.py
Exits 0 on success, 1 on any failure.

Note on env isolation: load_dotenv runs at module-import time and repopulates
ANTHROPIC_API_KEY from .env. We control env AFTER import (not via reimport)
so load_dotenv doesn't bleed the .env value back in mid-test.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Import once — load_dotenv fires here. After this we own the env.
from app.subagents.quiet_change_v2 import _resolve_use_bedrock  # noqa: E402


def _check(env_setup: dict[str, str], expected: bool, label: str) -> bool:
    for k in ("ANTHROPIC_API_KEY", "USE_BEDROCK"):
        os.environ.pop(k, None)
    os.environ.update(env_setup)
    actual = _resolve_use_bedrock()
    ok = actual == expected
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {label}: USE_BEDROCK={actual} (expected {expected})")
    return ok


def main() -> int:
    print("Bedrock routing regression tests:")
    results = [
        _check({"ANTHROPIC_API_KEY": "sk-test"},
               False, "API key set, no USE_BEDROCK -> direct API"),
        _check({"ANTHROPIC_API_KEY": "sk-test", "USE_BEDROCK": "true"},
               True, "API key set + USE_BEDROCK=true -> Bedrock"),
        _check({"USE_BEDROCK": "false"},
               False, "no API key + USE_BEDROCK=false -> direct API"),
        _check({},
               True, "no API key + no USE_BEDROCK -> Bedrock fallback"),
    ]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
