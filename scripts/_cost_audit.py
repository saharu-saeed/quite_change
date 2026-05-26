"""Aggregate LLM cost from all output JSON files."""
import json
import sys
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"

# Pricing (USD per million tokens)
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

totals = defaultdict(lambda: {"calls": 0, "in_tok": 0, "out_tok": 0,
                              "cache_r": 0, "cache_w": 0, "files": 0})

# Walk all JSONs in outputs/
for f in OUTPUTS.rglob("*.json"):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(d, dict):
        continue

    # Case A: usage_stats / final_usage_stats block (old backtest format)
    for key in ("usage_stats", "final_usage_stats"):
        u = d.get(key)
        if isinstance(u, dict) and "input_tokens" in u:
            bucket = totals["sonnet-4-6_tracked"]
            bucket["calls"]   += u.get("call_count", 0) or 0
            bucket["in_tok"]  += u.get("input_tokens", 0) or 0
            bucket["out_tok"] += u.get("output_tokens", 0) or 0
            bucket["cache_r"] += u.get("cache_read_input_tokens", 0) or 0
            bucket["cache_w"] += u.get("cache_creation_input_tokens", 0) or 0
            bucket["files"]   += 1

    # Case B: per-ticker v2 file (single `usage` block + `model` field)
    u = d.get("usage")
    if isinstance(u, dict) and "input_tokens" in u:
        model_class = classify_model(d.get("model", ""))
        key = f"{model_class}_v2"
        bucket = totals[key]
        bucket["calls"]   += 1
        bucket["in_tok"]  += u.get("input_tokens", 0) or 0
        bucket["out_tok"] += u.get("output_tokens", 0) or 0
        bucket["cache_r"] += u.get("cache_read_input_tokens", 0) or 0
        bucket["cache_w"] += u.get("cache_creation_input_tokens", 0) or 0
        bucket["files"]   += 1

grand_in = grand_out = grand_cost = 0.0
print(f"{'bucket':30s} {'files':>6s} {'calls':>6s} {'in_tok':>10s} {'out_tok':>10s} {'cost_usd':>10s}")
print("-" * 80)
for bucket_name, vals in sorted(totals.items()):
    model_class = bucket_name.split("_")[0]
    px = PRICING.get(model_class, PRICING["unknown"])
    cost = (vals["in_tok"]   * px["in"]      / 1e6 +
            vals["out_tok"]  * px["out"]     / 1e6 +
            vals["cache_r"]  * px["cache_r"] / 1e6 +
            vals["cache_w"]  * px["cache_w"] / 1e6)
    grand_in   += vals["in_tok"]
    grand_out  += vals["out_tok"]
    grand_cost += cost
    print(f"{bucket_name:30s} {vals['files']:6d} {vals['calls']:6d} "
          f"{vals['in_tok']:10d} {vals['out_tok']:10d} {cost:10.4f}")
print("-" * 80)
print(f"{'TOTAL':30s} {'':6s} {'':6s} {int(grand_in):10d} {int(grand_out):10d} {grand_cost:10.4f}")
