"""Window-sensitivity scorer (no LLM calls).

Re-scores the existing 20-ticker IT backtest by varying ONLY the post-filing
stock-reaction window used in the OUTCOME classification. The agent's
predictions (per_pair_judgments) are reused as-is — we do NOT re-run the
LLM, we only ask: "does a different outcome window change which predictions
look correct?"

Outcome rule (matches backtest_quiet_change.py):
    growth iff revenue_delta_pct > 0 AND stock_window_return_pct > 0
    in the MAJORITY of outcome pairs.

Reads:
    outputs/backtest_20_it_5250.json   (predictions per strategy)
    data/tempest/{ticker}/disclosures.json   (filing dates)
    data/tempest/{ticker}/prices.json   (close prices)

Writes:
    outputs/window_sensitivity.csv
    outputs/window_sensitivity.md
"""
from __future__ import annotations
import json
import sys
import io
from pathlib import Path
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ingest import prices  # noqa: E402

BACKTEST_FILE = ROOT / "outputs" / "backtest_20_it_5250.json"
DATA_DIR = ROOT / "data" / "tempest"
WINDOWS = [1, 3, 5, 10, 20, 30, 60]
BASELINE_WINDOW = 5


def _load_disclosures(ticker: str) -> list[dict]:
    p = DATA_DIR / ticker / "disclosures.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("data", [])
    except json.JSONDecodeError:
        return []


def _find_asr_submit_date(ticker: str, target_end_fy: int) -> str | None:
    """Find the annual-report (doc_type_code=120) submit date where
    period_end year matches `target_end_fy`. The agent's `curr_fiscal_year`
    field follows the period-end-year convention (FY2025 ≈ period_end 2025-03-31).
    Returns YYYY-MM-DD or None."""
    rows = _load_disclosures(ticker)
    asrs = [r for r in rows if r.get("doc_type_code") == "120"]
    for r in asrs:
        pe = r.get("period_end") or ""
        if pe[:4] == str(target_end_fy):
            sd = r.get("submit_datetime") or ""
            return sd[:10] if sd else None
    return None


def _stock_return_at_window(ticker: str, filing_date: str, window: int) -> float | None:
    """Close-to-close return over `window` trading days after filing.
    Matches the agent's _stock_5d_move logic exactly, just parameterised."""
    if not filing_date:
        return None
    d = datetime.strptime(filing_date, "%Y-%m-%d")
    # Pad calendar days to cover up to 60 trading days through holiday clusters.
    pad = max(35, int(window * 1.7) + 20)
    end = (d + timedelta(days=pad)).strftime("%Y-%m-%d")
    df = prices.fetch_prices_df(ticker, filing_date, end)
    if df is None or df.empty:
        return None
    closes = df["Close"].squeeze().dropna()
    if len(closes) < 2:
        return None
    anchor = float(closes.iloc[0])
    target_idx = min(window, len(closes) - 1)
    end_px = float(closes.iloc[target_idx])
    return round((end_px - anchor) / anchor * 100.0, 3)


def _classify_actual_outcome(outcome_pairs: list[dict], window: int) -> str:
    """Majority rule: growth iff revenue ↑ AND stock_window ↑ in majority of pairs."""
    growth_votes = 0
    scored = 0
    for p in outcome_pairs:
        rev = p.get("revenue_delta_pct")
        stk = p.get(f"stock_{window}d_pct")
        if rev is None or stk is None:
            continue
        scored += 1
        if rev > 0 and stk > 0:
            growth_votes += 1
    if scored == 0:
        return "n/a"
    return "growth" if (growth_votes * 2 > scored) else "no_growth"


def _score(prediction: str, actual: str) -> str:
    if actual == "n/a":
        return "n/a"
    if prediction == "uncertain":
        return "abstain"
    if prediction == "growth_likely" and actual == "growth":
        return "hit"
    if prediction == "growth_unlikely" and actual == "no_growth":
        return "hit"
    return "miss"


def main() -> int:
    if not BACKTEST_FILE.exists():
        print(f"missing: {BACKTEST_FILE}", flush=True)
        return 1
    bt = json.loads(BACKTEST_FILE.read_text(encoding="utf-8"))
    rows = bt["rows"]
    print(f"loaded {len(rows)} tickers from {BACKTEST_FILE.name}", flush=True)

    # Step 1: For each ticker × outcome, fill in stock returns at every window.
    print(f"\n[step 1] computing stock returns at windows {WINDOWS}...", flush=True)
    for r in rows:
        if "error" in r:
            continue
        ticker = r["code"]
        for od in r.get("outcome_detail", []):
            fy = od["fy"]
            filing_date = _find_asr_submit_date(ticker, fy)
            od["filing_date"] = filing_date
            for w in WINDOWS:
                od[f"stock_{w}d_pct"] = _stock_return_at_window(ticker, filing_date, w)

    # Step 2: For each window, classify actuals and re-score every strategy.
    print(f"[step 2] re-scoring against each window...\n", flush=True)
    summary: dict[int, dict] = {}
    for w in WINDOWS:
        for_window = {"recency_weighted": {"hit": 0, "miss": 0, "abstain": 0, "n/a": 0},
                      "trend_aware":      {"hit": 0, "miss": 0, "abstain": 0, "n/a": 0}}
        per_ticker_outcome = {}
        for r in rows:
            if "error" in r:
                continue
            actual = _classify_actual_outcome(r.get("outcome_detail", []), w)
            per_ticker_outcome[r["code"]] = actual
            for strat in for_window:
                pred = r["by_strategy"][strat]["prediction"]
                verdict = _score(pred, actual)
                for_window[strat][verdict] += 1
        summary[w] = {"counts": for_window, "outcomes": per_ticker_outcome}

    # Step 3: Flip detection — how many tickers' outcome flipped vs baseline 5d?
    baseline_outcomes = summary[BASELINE_WINDOW]["outcomes"]
    for w in WINDOWS:
        flips = sum(
            1 for code, o in summary[w]["outcomes"].items()
            if baseline_outcomes.get(code) and o != "n/a" and o != baseline_outcomes[code]
        )
        summary[w]["flips_vs_5d"] = flips

    # Step 4: Per-strategy precision on filter-out (growth_unlikely → no_growth)
    #         and keep (growth_likely → growth)
    for w in WINDOWS:
        for strat in ("recency_weighted", "trend_aware"):
            fo_hit = fo_miss = ke_hit = ke_miss = 0
            for r in rows:
                if "error" in r:
                    continue
                pred = r["by_strategy"][strat]["prediction"]
                actual = summary[w]["outcomes"][r["code"]]
                if actual == "n/a":
                    continue
                if pred == "growth_unlikely":
                    if actual == "no_growth":
                        fo_hit += 1
                    else:
                        fo_miss += 1
                elif pred == "growth_likely":
                    if actual == "growth":
                        ke_hit += 1
                    else:
                        ke_miss += 1
            fo_prec = fo_hit / (fo_hit + fo_miss) if (fo_hit + fo_miss) else None
            ke_prec = ke_hit / (ke_hit + ke_miss) if (ke_hit + ke_miss) else None
            summary[w]["counts"][strat]["filter_out_precision"] = fo_prec
            summary[w]["counts"][strat]["keep_precision"] = ke_prec

    # ---- Print summary table -------------------------------------------------
    print("=" * 100, flush=True)
    print(f"WINDOW SENSITIVITY (n={sum(1 for r in rows if 'error' not in r)} tickers)", flush=True)
    print("=" * 100, flush=True)
    for strat in ("trend_aware", "recency_weighted"):
        print(f"\nStrategy: {strat}\n", flush=True)
        print(f"  {'win':>5s} {'hit':>4s} {'miss':>4s} {'abs':>4s} {'n/a':>4s}  "
              f"{'hit_rate':>9s}  {'FO_prec':>8s}  {'KEEP_prec':>10s}  {'flips_vs_5d':>11s}", flush=True)
        print(f"  {'-'*5} {'-'*4} {'-'*4} {'-'*4} {'-'*4}  {'-'*9}  {'-'*8}  {'-'*10}  {'-'*11}", flush=True)
        for w in WINDOWS:
            c = summary[w]["counts"][strat]
            hit = c["hit"]
            miss = c["miss"]
            denom = hit + miss
            hr = f"{hit/denom*100:5.1f}%" if denom else "  n/a "
            fo = c["filter_out_precision"]
            ke = c["keep_precision"]
            fo_s = f"{fo*100:5.1f}%" if fo is not None else "  n/a"
            ke_s = f"{ke*100:5.1f}%" if ke is not None else "   n/a"
            flips = summary[w]["flips_vs_5d"]
            tag = " (baseline)" if w == BASELINE_WINDOW else ""
            print(f"  {w:>4d}d {hit:>4d} {miss:>4d} {c['abstain']:>4d} {c['n/a']:>4d}    "
                  f"{hr:>6s}    {fo_s:>5s}     {ke_s:>6s}        {flips:>4d}{tag}", flush=True)

    # ---- Per-ticker outcome flips: which companies flipped at which window? ---
    print("\n" + "=" * 100, flush=True)
    print("PER-TICKER OUTCOME BY WINDOW (lookup: where do outcomes change?)", flush=True)
    print("=" * 100, flush=True)
    hdr = ["ticker"] + [f"{w}d" for w in WINDOWS] + ["pred(trend)"]
    print("  " + "  ".join(f"{h:>10s}" for h in hdr), flush=True)
    print("  " + "  ".join("-" * 10 for _ in hdr), flush=True)
    for r in rows:
        if "error" in r:
            continue
        code = r["code"]
        cells = [code]
        for w in WINDOWS:
            o = summary[w]["outcomes"].get(code, "n/a")
            short = {"growth": "GROW", "no_growth": "NO-GR", "n/a": "n/a"}[o]
            cells.append(short)
        cells.append(r["by_strategy"]["trend_aware"]["prediction"][:10])
        print("  " + "  ".join(f"{c:>10s}" for c in cells), flush=True)

    # ---- Write CSV + MD ------------------------------------------------------
    out_csv = ROOT / "outputs" / "window_sensitivity.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8") as f:
        f.write("strategy,window,hit,miss,abstain,na,hit_rate_pct,filter_out_precision_pct,keep_precision_pct,flips_vs_5d\n")
        for strat in ("trend_aware", "recency_weighted"):
            for w in WINDOWS:
                c = summary[w]["counts"][strat]
                denom = c["hit"] + c["miss"]
                hr = c["hit"]/denom*100 if denom else ""
                fo = c["filter_out_precision"]*100 if c["filter_out_precision"] is not None else ""
                ke = c["keep_precision"]*100 if c["keep_precision"] is not None else ""
                flips = summary[w]["flips_vs_5d"]
                f.write(f"{strat},{w},{c['hit']},{c['miss']},{c['abstain']},{c['n/a']},"
                        f"{hr},{fo},{ke},{flips}\n")
    print(f"\n[saved] {out_csv}", flush=True)

    # MD report
    out_md = ROOT / "outputs" / "window_sensitivity.md"
    with out_md.open("w", encoding="utf-8") as f:
        f.write(f"# Window-sensitivity scoring (n={sum(1 for r in rows if 'error' not in r)} tickers)\n\n")
        f.write(f"Predictions are the existing 20-ticker IT backtest. Only the "
                f"OUTCOME stock-window is varied.\n\n")
        for strat in ("trend_aware", "recency_weighted"):
            f.write(f"## Strategy: `{strat}`\n\n")
            f.write("| Window | Hit | Miss | Abstain | n/a | Hit rate | Filter-out precision | Keep precision | Flips vs 5d |\n")
            f.write("|---|---|---|---|---|---|---|---|---|\n")
            for w in WINDOWS:
                c = summary[w]["counts"][strat]
                denom = c["hit"] + c["miss"]
                hr = f"{c['hit']/denom*100:.1f}%" if denom else "n/a"
                fo = f"{c['filter_out_precision']*100:.1f}%" if c["filter_out_precision"] is not None else "n/a"
                ke = f"{c['keep_precision']*100:.1f}%" if c["keep_precision"] is not None else "n/a"
                tag = " **(baseline)**" if w == BASELINE_WINDOW else ""
                f.write(f"| {w}d{tag} | {c['hit']} | {c['miss']} | {c['abstain']} | {c['n/a']} | {hr} | {fo} | {ke} | {summary[w]['flips_vs_5d']} |\n")
            f.write("\n")
    print(f"[saved] {out_md}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
