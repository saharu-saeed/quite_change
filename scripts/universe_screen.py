"""Universe screener: find rev↑+stock↓ candidates from Tempest cache, then
run the Quiet Change Agent v2 on each, then aggregate the distribution of
positive/negative/neutral classifications.

Usage:
    python scripts/universe_screen.py [N]

Where N is the max number of candidates to send to the agent (default 30).

Tempest cache is used ONLY for universe selection (which tickers to send).
The agent itself still only sees the ticker code and consults analyst
reports + news via SerpAPI — no raw financial data is fed in.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# analyze_ticker is imported lazily inside main() so that other scripts can
# `from scripts.universe_screen import screen_universe` without pulling in
# the SerpAPI runtime dependency.

TEMPEST_DIR = ROOT / "data" / "tempest"
OUT_DIR = ROOT / "outputs" / "quiet_change_v2" / "universe_screen"

STOCK_WINDOW_DAYS = 90
MIN_REVENUE_GROWTH_PCT = 1.0   # rev up at least 1% YoY
MAX_STOCK_MOVE_PCT = -3.0       # stock down at least 3%


def _list_cached_tickers() -> list[str]:
    """Return ticker codes that have both prices and financials cached."""
    out: list[str] = []
    for p in TEMPEST_DIR.iterdir():
        if not p.is_dir() or p.name.startswith("_"):
            continue
        if (p / "prices.json").exists() and (p / "financials.json").exists():
            out.append(p.name)
    return sorted(out)


def _compute_stock_move(ticker: str) -> dict | None:
    """Compute trailing-3mo close-to-close % move from cached prices."""
    try:
        prices = json.load(open(TEMPEST_DIR / ticker / "prices.json", encoding="utf-8"))["data"]
    except Exception:
        return None
    if not prices:
        return None
    # prices are sorted newest-first
    end = prices[0]
    end_date = datetime.fromisoformat(end["date"]).date()
    start_target = end_date - timedelta(days=STOCK_WINDOW_DAYS)
    # find oldest entry within or earliest after target
    start = None
    for row in prices:
        row_date = datetime.fromisoformat(row["date"]).date()
        if row_date <= start_target:
            start = row
            break
    if start is None:
        start = prices[-1]
    try:
        start_close = float(start["close"])
        end_close = float(end["close"])
    except (KeyError, TypeError, ValueError):
        return None
    if start_close <= 0:
        return None
    move_pct = (end_close / start_close - 1.0) * 100.0
    return {
        "start_date": start["date"],
        "end_date": end["date"],
        "start_close": round(start_close, 1),
        "end_close": round(end_close, 1),
        "move_pct": round(move_pct, 2),
    }


def _compute_revenue_yoy(ticker: str) -> dict | None:
    """Compute YoY revenue % from the two most recent fiscal years in financials.json."""
    try:
        fin = json.load(open(TEMPEST_DIR / ticker / "financials.json", encoding="utf-8"))["data"]
    except Exception:
        return None
    # Take only annual filings (no fiscal_quarter)
    annuals = [r for r in fin if r.get("fiscal_quarter") in (None, "null")]
    annuals.sort(key=lambda r: r.get("period_end") or "", reverse=True)
    if len(annuals) < 2:
        return None
    latest, prior = annuals[0], annuals[1]
    try:
        latest_sales = float(latest["net_sales"])
        prior_sales = float(prior["net_sales"])
    except (KeyError, TypeError, ValueError):
        return None
    if prior_sales <= 0:
        return None
    yoy_pct = (latest_sales / prior_sales - 1.0) * 100.0
    return {
        "latest_period_end": latest.get("period_end"),
        "latest_net_sales": latest_sales,
        "prior_net_sales": prior_sales,
        "revenue_yoy_pct": round(yoy_pct, 2),
    }


def screen_universe() -> list[dict]:
    """Return tickers that meet rev↑+stock↓ pre-filter, sorted by stock-drop magnitude."""
    candidates: list[dict] = []
    for ticker in _list_cached_tickers():
        stock = _compute_stock_move(ticker)
        rev = _compute_revenue_yoy(ticker)
        if stock is None or rev is None:
            continue
        if (
            rev["revenue_yoy_pct"] >= MIN_REVENUE_GROWTH_PCT
            and stock["move_pct"] <= MAX_STOCK_MOVE_PCT
        ):
            candidates.append({
                "ticker": ticker,
                "revenue_yoy_pct": rev["revenue_yoy_pct"],
                "stock_move_pct": stock["move_pct"],
                "stock_start_date": stock["start_date"],
                "stock_end_date": stock["end_date"],
                "latest_fy_end": rev["latest_period_end"],
            })
    # sort by biggest stock drop first
    candidates.sort(key=lambda c: c["stock_move_pct"])
    return candidates


def main(limit: int = 30) -> int:
    from app.subagents.quiet_change_v2 import analyze_ticker  # lazy: only needed when running screen end-to-end

    print(f"Screening Tempest universe (rev YoY >= {MIN_REVENUE_GROWTH_PCT}%, 3mo stock <= {MAX_STOCK_MOVE_PCT}%)...")
    candidates = screen_universe()
    print(f"Found {len(candidates)} candidates. Showing first {limit}:\n")
    print(f"{'Ticker':<8} {'RevYoY%':<10} {'Stock3mo%':<12} {'FY end':<12}")
    print("-" * 50)
    for c in candidates[:limit]:
        print(
            f"{c['ticker']:<8} "
            f"{c['revenue_yoy_pct']:+8.2f}  "
            f"{c['stock_move_pct']:+8.2f}    "
            f"{c['latest_fy_end']:<12}"
        )
    print()

    selected = candidates[:limit]
    if not selected:
        print("No candidates to send to agent.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    results: list[dict] = []
    t0 = time.time()

    for i, cand in enumerate(selected):
        ticker = cand["ticker"]
        print(f"\n[{i+1}/{len(selected)}] {ticker}  (universe: rev {cand['revenue_yoy_pct']:+.1f}%, stock {cand['stock_move_pct']:+.1f}%)", flush=True)
        try:
            res = analyze_ticker(ticker)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            results.append({**cand, "error": str(e)})
            continue
        out_path = OUT_DIR / f"{ticker}_{today}.json"
        out_path.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        classification = res.get("classification") or "ERROR"
        confidence = res.get("confidence") or "?"
        in_scope = res.get("in_scope")
        name = res.get("company_name_ja") or res.get("company_name_en") or "?"
        print(f"  -> {name} | {classification} / {confidence} | in_scope={in_scope}", flush=True)
        results.append({
            **cand,
            "company": name,
            "classification": classification,
            "confidence": confidence,
            "in_scope": in_scope,
            "rationale_en": (res.get("rationale_en") or "")[:300],
        })

    elapsed = time.time() - t0

    # report
    print("\n\n" + "=" * 96)
    print("UNIVERSE SCREENING REPORT")
    print("=" * 96)
    print(f"{'Ticker':<8} {'Company':<20} {'Cache rev%':<11} {'Cache stk%':<11} {'Class':<10} {'Conf':<7} {'InScp':<6}")
    print("-" * 96)
    for r in results:
        if "error" in r:
            print(f"{r['ticker']:<8} ERROR: {r['error']}")
            continue
        name = (r.get("company") or "")[:19]
        print(
            f"{r['ticker']:<8} "
            f"{name:<20} "
            f"{r['revenue_yoy_pct']:+9.2f}  "
            f"{r['stock_move_pct']:+9.2f}  "
            f"{r['classification']:<10} "
            f"{r['confidence'][:6]:<7} "
            f"{str(r['in_scope'])[:5]:<6}"
        )

    # aggregate
    print("-" * 96)
    valid = [r for r in results if "error" not in r]
    n = len(valid)
    if n > 0:
        for cls in ("positive", "negative", "neutral"):
            count = sum(1 for r in valid if r["classification"] == cls)
            print(f"  {cls:<10}: {count}/{n} = {count/n*100:.0f}%")
        in_scope_count = sum(1 for r in valid if r["in_scope"] is True)
        print(f"  in_scope=True: {in_scope_count}/{n} = {in_scope_count/n*100:.0f}%")

    print(f"\nWall time: {elapsed:.1f}s ({elapsed/max(n,1):.1f}s/ticker)")

    # neutrals are the TARGET — call them out
    neutrals = [r for r in valid if r.get("classification") == "neutral"]
    if neutrals:
        print(f"\n*** NEUTRAL CANDIDATES (QUICK targets — manually verify) ***")
        for r in neutrals:
            print(f"  {r['ticker']} {r.get('company')} — {r.get('confidence')} confidence")
            print(f"    rev YoY (cache): {r['revenue_yoy_pct']:+.1f}%, stock 3mo (cache): {r['stock_move_pct']:+.1f}%")
            print(f"    rationale: {r['rationale_en']}")
            print()

    # save full summary
    summary_path = OUT_DIR / f"_summary_{today}.json"
    summary_path.write_text(
        json.dumps({"limit": limit, "results": results, "elapsed_s": elapsed},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Full results saved to: {summary_path}")

    return 0


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    sys.exit(main(limit))
