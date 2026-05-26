import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv; load_dotenv()
from app.ingest.edinet_loader import load_asr_series
from pathlib import Path
series = load_asr_series(Path("data/edinet/9984"))
latest = series[-1]
text = latest.get("qualitative_text_full", "") or latest.get("qualitative_text", "")
print(f"narrative length: {len(text)}")
for kw in ["売却", "譲渡", "事業譲渡"]:
    for m in re.finditer(kw, text):
        i = m.start()
        snippet = text[max(0,i-60):i+120].replace("\n", " ")
        print(f"[{kw} @{i}] …{snippet}…")
