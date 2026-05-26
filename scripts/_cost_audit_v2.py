"""Aggregate LLM cost split by Bedrock vs direct Anthropic API, focused on
last-48h spend.

Heuristic:
  - model starts with "us.anthropic." or "anthropic."  → AWS Bedrock
  - everything else (e.g. "claude-haiku-4-5-20251001") → direct Anthropic API
"""
import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"

PRICING = {
    "sonnet-4-6": {"in": 3.0, "out": 15.0, "cache_r": 0.30, "cache_w": 3.75},
    "haiku-4-5":  {"in": 1.0, "out":  5.0, "cache_r": 0.10, "cache_w": 1.25},
    "haiku-3-5":  {"in": 0.80, "out": 4.0, "cache_r": 0.08, "cache_w": 1.0},
    "opus-4":     {"in":15.0, "out": 75.0, "cache_r": 1.50, "cache_w":18.75},
    "unknown":    {"in": 3.0, "out": 15.0, "cache_r": 0.30, "cache_w": 3.75},
}

def classify_model(name: str) -> str:
    n = (name or "").lower()
    if "sonnet-4-6" in n or "sonnet-4.6" in n: return "sonnet-4-6"
    if "haiku-4-5" in n or "haiku-4.5" in n:   return "haiku-4-5"
    if "haiku-3-5" in n or "haiku-3.5" in n:   return "haiku-3-5"
    if "opus-4" in n:                          return "opus-4"
    return "unknown"

def is_bedrock(model: str) -> bool:
    m = (model or "").lower()
    return m.startswith("us.anthropic.") or m.startswith("anthropic.")

def cost_of(model_class, in_tok, out_tok, cr=0, cw=0):
    p = PRICING.get(model_class, PRICING["unknown"])
    return (in_tok*p["in"] + out_tok*p["out"] + cr*p["cache_r"] + cw*p["cache_w"]) / 1e6

# Aggregate: (date, api, model_class) -> totals
buckets = defaultdict(lambda: {"calls": 0, "in_tok": 0, "out_tok": 0,
                               "cache_r": 0, "cache_w": 0, "files": []})

for f in OUTPUTS.rglob("*.json"):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(d, dict):
        continue

    # Per-ticker v2 files
    u = d.get("usage")
    if isinstance(u, dict) and "input_tokens" in u:
        model = d.get("model", "")
        api = "bedrock" if is_bedrock(model) else "direct"
        mc = classify_model(model)
        as_of = d.get("as_of") or d.get("screened_at") or "unknown"
        key = (as_of, api, mc)
        b = buckets[key]
        b["calls"]   += 1
        b["in_tok"]  += u.get("input_tokens", 0) or 0
        b["out_tok"] += u.get("output_tokens", 0) or 0
        b["cache_r"] += u.get("cache_read_input_tokens", 0) or 0
        b["cache_w"] += u.get("cache_creation_input_tokens", 0) or 0
        b["files"].append(str(f.relative_to(OUTPUTS)))

    # Old backtest aggregates (no model field — assume Bedrock Sonnet 4.6,
    # which is what the in-code estimator was using)
    for stats_key in ("usage_stats", "final_usage_stats"):
        u = d.get(stats_key)
        if isinstance(u, dict) and "input_tokens" in u:
            # Derive date from file mtime as fallback
            as_of = "2026-05-18-or-earlier"
            key = (as_of, "bedrock?", "sonnet-4-6")
            b = buckets[key]
            b["calls"]   += u.get("call_count", 0) or 0
            b["in_tok"]  += u.get("input_tokens", 0) or 0
            b["out_tok"] += u.get("output_tokens", 0) or 0
            b["cache_r"] += u.get("cache_read_input_tokens", 0) or 0
            b["cache_w"] += u.get("cache_creation_input_tokens", 0) or 0
            b["files"].append(str(f.relative_to(OUTPUTS)))

print(f"{'date':25s} {'api':10s} {'model':12s} {'files':>6s} {'calls':>6s} "
      f"{'in_tok':>10s} {'out_tok':>10s} {'cost_usd':>10s}")
print("-" * 100)

bedrock_total = direct_total = 0.0
for (as_of, api, mc), v in sorted(buckets.items()):
    c = cost_of(mc, v["in_tok"], v["out_tok"], v["cache_r"], v["cache_w"])
    if api == "bedrock":
        bedrock_total += c
    elif api == "direct":
        direct_total += c
    print(f"{as_of:25s} {api:10s} {mc:12s} {len(v['files']):6d} {v['calls']:6d} "
          f"{v['in_tok']:10d} {v['out_tok']:10d} {c:10.4f}")

print("-" * 100)
print(f"BEDROCK total (incl. old 'bedrock?' tracked):  ${bedrock_total:.4f}")
print(f"DIRECT Anthropic API total:                    ${direct_total:.4f}")
print()
print("=== LAST 48H ONLY (2026-05-22 + 2026-05-23) ===")
last48 = {"2026-05-22", "2026-05-23"}
b_48 = d_48 = 0.0
for (as_of, api, mc), v in buckets.items():
    if as_of not in last48: continue
    c = cost_of(mc, v["in_tok"], v["out_tok"], v["cache_r"], v["cache_w"])
    if api == "bedrock":
        b_48 += c
    elif api == "direct":
        d_48 += c
print(f"  Bedrock cost (last 48h):  ${b_48:.4f}")
print(f"  Direct API cost (last 48h): ${d_48:.4f}")
