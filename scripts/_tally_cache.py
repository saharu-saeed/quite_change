"""Quick tally of cached tickers by sector_33_name + scale_category."""
import json
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
TEMPEST = ROOT / "data" / "tempest"

secs: Counter = Counter()
scales: Counter = Counter()
pairs: Counter = Counter()
n = 0

for p in TEMPEST.iterdir():
    if not p.is_dir() or p.name.startswith("_"):
        continue
    cj = p / "company.json"
    if not cj.exists():
        continue
    n += 1
    raw = json.load(open(cj, encoding="utf-8"))
    d = raw.get("data", raw)
    if isinstance(d, list) and d:
        d = d[0]
    s = d.get("sector_33_name") or "?"
    sc = d.get("scale_category") or "?"
    secs[s] += 1
    scales[sc] += 1
    pairs[(s, sc)] += 1

print(f"tickers with company.json: {n}\n")
print("SECTORS:")
for k, v in secs.most_common():
    print(f"  {v:>3}  {k}")
print("\nSCALES:")
for k, v in scales.most_common():
    print(f"  {v:>3}  {k}")
print("\nSECTOR x SCALE (only sectors with >=2 tickers):")
multi = {s for s, c in secs.items() if c >= 2}
for (s, sc), c in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0][0])):
    if s in multi:
        print(f"  {c:>3}  {s:<14} {sc}")
