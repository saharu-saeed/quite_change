import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
p = ROOT / "outputs" / "quiet_change_v2" / "sectors" / "ガラス･土石製品" / "_run_2026-05-23.json"
d = json.load(open(p, encoding="utf-8"))
r = next(r for r in d["watchlist_ranked"] if r["ticker"] == "5233")
keys = ["attention_score", "editorial", "brokerage", "agg_article", "agg_stub", "retail_chatter", "recent_2026"]
print("5233 太平洋セメント attention breakdown:")
for k in keys:
    print(f"  {k}: {r.get(k)}")
