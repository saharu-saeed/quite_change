# -*- coding: utf-8 -*-
"""Tempest API data-fetcher — builds a clean 'data packet' per company (FREE, no LLM).

Pulls numbers + prices + the relevant disclosure text section from the internal TempestAI
Finance API, so the reasoning LLM can work over clean structured data instead of reading PDFs.

Usage:
    python -m research.tempest_fetch 9433 2025-05-14 2025-03-31
    (ticker, announce_date, fiscal_period_end)
"""
from __future__ import annotations
import json, sys, urllib.request, urllib.error
from datetime import datetime, timedelta
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try: _s.reconfigure(encoding="utf-8")
        except Exception: pass

ROOT = Path(__file__).parent.parent.parent  # repo root holding .env
def _load_env():
    env = {}
    for p in [ROOT/".env", Path.cwd()/".env"]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
            break
    return env
ENV = _load_env()
BASE = ENV.get("TEMPEST_API_URL", "").rstrip("/")
KEY = ENV.get("TEMPEST_API_KEY", "")

def api(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

JP_HOLIDAYS = set()  # prices come pre-dated from API; we just pick by date

def _add_trading_days(prices_sorted, p0_date, n):
    """Given sorted available dates, return the date n trading rows after p0_date."""
    if p0_date not in prices_sorted: return None
    i = prices_sorted.index(p0_date)
    j = i + n
    return prices_sorted[j] if j < len(prices_sorted) else prices_sorted[-1]

def fetch_prices(ticker, announce_date, days=10, flat=1.0):
    a = datetime.strptime(announce_date, "%Y-%m-%d")
    frm = (a - timedelta(days=10)).strftime("%Y-%m-%d")
    to = (a + timedelta(days=35)).strftime("%Y-%m-%d")
    d = api(f"/companies/{ticker}/prices?from={frm}&to={to}&limit=100")
    rows = {r["date"]: float(r["close"]) for r in d.get("data", []) if r.get("close") is not None}
    if not rows: return {}
    asc = sorted(rows)  # ascending dates
    # P0 = announce date close, or last trading day on/before
    p0d = announce_date if announce_date in rows else None
    if p0d is None:
        prior = [x for x in asc if x <= announce_date]
        p0d = prior[-1] if prior else None
    if not p0d: return {}
    p1d = _add_trading_days(asc, p0d, days)
    p0, p1 = rows[p0d], rows[p1d]
    pct = (p1 - p0) / p0 * 100
    direction = "flat" if abs(pct) <= flat else ("up" if pct > 0 else "down")
    return {"p0": p0, "p0_date": p0d, "p1": p1, "p1_date": p1d,
            "pct_change": round(pct, 2), "stock_dir": direction, "source": "tempest"}

def _pct(c, p, field):
    try:
        cv, pv = float(c[field]), float(p[field])
        return round((cv - pv) / abs(pv) * 100, 1)
    except Exception: return None

def fetch_numbers(ticker, period_end):
    """Annual financials ending `period_end`; flag if restated; include PRIOR-year YoY
    so a 'dip then rebound' (one-off rolloff) pattern is visible to the reasoner."""
    yr = int(period_end[:4])
    d = api(f"/companies/{ticker}/financials?from_fy={yr-3}&to_fy={yr}&limit=20")
    rows = [r for r in d.get("data", []) if r.get("period_end")]
    cur  = next((r for r in rows if r["period_end"] == period_end), None)
    prev = next((r for r in rows if r["period_end"] == f"{yr-1}{period_end[4:]}"), None)
    prev2= next((r for r in rows if r["period_end"] == f"{yr-2}{period_end[4:]}"), None)
    out = {"restated": False}
    if cur:
        out["doc_type"] = cur.get("document_type")
        out["restated"] = "訂正" in str(cur.get("document_type", ""))
        out["net_sales"] = cur.get("net_sales"); out["operating_profit"] = cur.get("operating_profit"); out["profit"] = cur.get("profit")
        if prev:
            out["rev_pct"] = _pct(cur, prev, "net_sales")
            out["op_pct"]  = _pct(cur, prev, "operating_profit")
            out["net_pct"] = _pct(cur, prev, "profit")
        # PRIOR year's own YoY (FY-1 vs FY-2) — reveals a one-off dip in the comparison year
        if prev and prev2:
            out["prior_year_yoy"] = {"period_end": prev.get("period_end"),
                                     "op_pct": _pct(prev, prev2, "operating_profit"),
                                     "net_pct": _pct(prev, prev2, "profit")}
    return out

MDNA_KW = ["経営成績", "経営者による"]          # the results "why" section(s)
ONEOFF_TERMS = ["減損", "リース債権", "MPT", "特別損", "売却益", "為替差損", "のれん", "引当金"]

def _window(text, terms, radius=500):
    """Return focused excerpts around one-off terms (avoids dumping the whole section)."""
    out = []
    for t in terms:
        i = text.find(t)
        if i >= 0:
            out.append(text[max(0, i-radius):i+radius])
    # dedupe overlapping windows crudely
    return "\n…\n".join(dict.fromkeys(out))

def fetch_why_text(ticker, period_end, max_chars=4500):
    """Find the ORIGINAL (non-amended) annual report; pull MD&A + a focused one-off excerpt."""
    yr = int(period_end[:4])
    disc = api(f"/companies/{ticker}/disclosures?from={yr}-04-01&to={yr+1}-09-30&limit=50")
    orig = [r for r in disc.get("data", [])
            if r.get("is_amendment") is False and r.get("period_end") == period_end
            and "有価証券報告書" in str(r.get("doc_description", ""))]
    if not orig: return {"text": "", "doc_id": None}
    did = orig[0]["doc_id"]
    detail = api(f"/disclosures/{did}")
    secs = detail.get("texts", []) or []
    parts = []
    # 1) MD&A — the company's own results discussion
    for s in secs:
        nm = str(s.get("section_name", ""))
        if any(k in nm for k in MDNA_KW):
            parts.append(f"【{nm}】\n{str(s.get('content',''))[:2000]}")
    # 2) one-off excerpt — focused window around impairment / special-item terms, from ANY section
    for s in secs:
        nm = str(s.get("section_name", "")); c = str(s.get("content", ""))
        if "事業の内容" in nm:
            continue  # skip the plain business-description section
        if any(t in c for t in ["減損", "リース債権", "MPT", "為替差損", "売却益", "特別損"]):
            w = _window(c, ONEOFF_TERMS, 450)
            if w:
                parts.append(f"【{nm}（一過性関連抜粋）】\n{w}")
            break
    blob = "\n\n".join(parts)[:max_chars]
    return {"text": blob, "doc_id": did}

def build_packet(ticker, announce_date, period_end):
    info = {}
    try: info = api(f"/companies/{ticker}")
    except Exception: pass
    nums = fetch_numbers(ticker, period_end)
    prices = fetch_prices(ticker, announce_date)
    why = fetch_why_text(ticker, period_end)
    pkt = {
        "ticker": ticker, "announce_date": announce_date, "period_end": period_end,
        "name": info.get("name") or info.get("company_name"),
        "sector": info.get("sector_33_name") or info.get("sector"),
        "numbers": nums, "prices": prices,
        "why_doc_id": why["doc_id"], "why_text": why["text"],
    }
    # If profit grew much faster than revenue (or net diverges), pull the PRIOR-year report's
    # one-off excerpt too — so 'last year had the charge, this year it's gone' is explicit.
    op, rev, net = nums.get("op_pct"), nums.get("rev_pct"), nums.get("net_pct")
    divergent = (op is not None and rev is not None and abs(op - rev) >= 10) or \
                (net is not None and rev is not None and (abs(net - rev) >= 15 or (net > 0) != (rev > 0)))
    if divergent:
        prior_pe = f"{int(period_end[:4])-1}{period_end[4:]}"
        try:
            pw = fetch_why_text(ticker, prior_pe, max_chars=2500)
            pkt["prior_year_oneoff_text"] = pw["text"]
            pkt["prior_year_period_end"] = prior_pe
        except Exception:
            pkt["prior_year_oneoff_text"] = ""
    # ── period-aware fallback contract ──
    # Tempest numbers are usable only if: the EXACT period is present, fields are non-null,
    # and it's NOT a restated filing (restated = not point-in-time → use the tanshin original).
    n = pkt["numbers"]
    numbers_ok = bool(n.get("net_sales")) and (n.get("rev_pct") is not None) and not n.get("restated")
    pkt["tempest_numbers_ok"] = numbers_ok
    pkt["needs_tanshin"] = not numbers_ok
    pkt["needs_tanshin_reason"] = ("" if numbers_ok else
        ("restated_use_original" if n.get("restated")
         else ("numbers_missing_for_period" if not n.get("net_sales") else "incomplete")))
    return pkt

if __name__ == "__main__":
    t, a, pe = sys.argv[1], sys.argv[2], sys.argv[3]
    pkt = build_packet(t, a, pe)
    print(json.dumps(pkt, ensure_ascii=False, indent=2))
