"""Extended window-sensitivity scorer (free — no LLM).

Combines existing backtests:
  - backtest_lever1plus_fewshot.json  (24 mixed-sector tickers)
  - backtest_20_it_5250.json          (20 IT/telecom tickers)

Deduplicates by ticker (later run wins). Re-scores predictions against
stock-outcome returns computed at 1d / 3d / 5d / 10d / 20d / 30d / 60d
post-filing windows.

Each ticker's prediction was made under whatever prompt config was running
when its backtest ran — that's held constant per row. The window-sensitivity
question ("which outcome window best validates the agent's predictions?")
is per-row, so combining different-config rows is valid.
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

DATA_DIR = ROOT / "data" / "tempest"
WINDOWS = [1, 3, 5, 10, 20, 30, 60]
BASELINE_WINDOW = 5

# Order matters: later file overrides earlier on ticker collision.
SOURCE_FILES = [
    ROOT / "outputs" / "backtest_lever1plus_fewshot.json",
    ROOT / "outputs" / "backtest_20_it_5250.json",
]


def _load_disclosures(ticker: str) -> list[dict]:
    p = DATA_DIR / ticker / "disclosures.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("data", [])
    except json.JSONDecodeError:
        return []


def _find_asr_submit_date(ticker: str, target_end_fy: int) -> str | None:
    rows = _load_disclosures(ticker)
    asrs = [r for r in rows if r.get("doc_type_code") == "120"]
    for r in asrs:
        pe = r.get("period_end") or ""
        if pe[:4] == str(target_end_fy):
            sd = r.get("submit_datetime") or ""
            return sd[:10] if sd else None
    return None


def _stock_return_at_window(ticker: str, filing_date: str, window: int) -> float | None:
    if not filing_date:
        return None
    d = datetime.strptime(filing_date, "%Y-%m-%d")
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


def _classify(outcome_pairs: list[dict], window: int) -> str:
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
    # Load + dedupe (later file wins)
    combined: dict[str, dict] = {}
    source_of: dict[str, str] = {}
    for f in SOURCE_FILES:
        if not f.exists():
            print(f"missing: {f}", flush=True)
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for r in d["rows"]:
            if "error" in r:
                continue
            combined[r["code"]] = r
            source_of[r["code"]] = f.name
    print(f"Combined unique tickers: {len(combined)}", flush=True)
    by_src: dict[str, int] = {}
    for src in source_of.values():
        by_src[src] = by_src.get(src, 0) + 1
    for src, n in by_src.items():
        print(f"  {src}: {n} tickers (after dedupe)", flush=True)

    rows = list(combined.values())

    # Step 1: stock returns at every window for every outcome year
    print(f"\n[step 1] computing stock returns at windows {WINDOWS}...", flush=True)
    skipped = 0
    for r in rows:
        ticker = r["code"]
        for od in r.get("outcome_detail", []):
            fy = od["fy"]
            filing_date = _find_asr_submit_date(ticker, fy)
            od["filing_date"] = filing_date
            for w in WINDOWS:
                od[f"stock_{w}d_pct"] = _stock_return_at_window(ticker, filing_date, w)
            if not filing_date:
                skipped += 1
    if skipped:
        print(f"  warning: {skipped} outcome years missing filing date (will score n/a)", flush=True)

    # Step 2: re-score each window per strategy
    print(f"[step 2] re-scoring against each window...\n", flush=True)
    summary: dict[int, dict] = {}
    for w in WINDOWS:
        for_window = {"recency_weighted": {"hit": 0, "miss": 0, "abstain": 0, "n/a": 0},
                      "trend_aware":      {"hit": 0, "miss": 0, "abstain": 0, "n/a": 0}}
        outcomes = {}
        for r in rows:
            actual = _classify(r.get("outcome_detail", []), w)
            outcomes[r["code"]] = actual
            for strat in for_window:
                pred = r["by_strategy"][strat]["prediction"]
                v = _score(pred, actual)
                for_window[strat][v] += 1
        # Precision per class
        for strat in for_window:
            fo_hit = fo_miss = ke_hit = ke_miss = 0
            for r in rows:
                pred = r["by_strategy"][strat]["prediction"]
                actual = outcomes[r["code"]]
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
            for_window[strat]["filter_out_precision"] = (
                fo_hit/(fo_hit+fo_miss) if (fo_hit+fo_miss) else None
            )
            for_window[strat]["keep_precision"] = (
                ke_hit/(ke_hit+ke_miss) if (ke_hit+ke_miss) else None
            )
        summary[w] = {"counts": for_window, "outcomes": outcomes}

    # Flips vs 5d
    base = summary[BASELINE_WINDOW]["outcomes"]
    for w in WINDOWS:
        flips = sum(1 for c, o in summary[w]["outcomes"].items()
                    if base.get(c) and o != "n/a" and o != base[c])
        summary[w]["flips_vs_5d"] = flips

    # ---- Print
    print("=" * 105, flush=True)
    print(f"EXTENDED WINDOW SENSITIVITY (n={len(rows)} unique tickers, "
          f"24 mixed-sector + 20 IT, deduped to {len(rows)})", flush=True)
    print("=" * 105, flush=True)
    for strat in ("trend_aware", "recency_weighted"):
        print(f"\nStrategy: {strat}\n", flush=True)
        print(f"  {'win':>5s} {'hit':>4s} {'miss':>4s} {'abs':>4s} {'n/a':>4s}  "
              f"{'hit_rate':>9s}  {'FO_prec':>8s}  {'KEEP_prec':>10s}  {'flips_vs_5d':>11s}", flush=True)
        print(f"  {'-'*5} {'-'*4} {'-'*4} {'-'*4} {'-'*4}  {'-'*9}  {'-'*8}  {'-'*10}  {'-'*11}", flush=True)
        for w in WINDOWS:
            c = summary[w]["counts"][strat]
            denom = c["hit"] + c["miss"]
            hr = f"{c['hit']/denom*100:5.1f}%" if denom else "  n/a "
            fo = c["filter_out_precision"]
            ke = c["keep_precision"]
            fo_s = f"{fo*100:5.1f}%" if fo is not None else "  n/a"
            ke_s = f"{ke*100:5.1f}%" if ke is not None else "   n/a"
            tag = " (baseline)" if w == BASELINE_WINDOW else ""
            print(f"  {w:>4d}d {c['hit']:>4d} {c['miss']:>4d} {c['abstain']:>4d} {c['n/a']:>4d}    "
                  f"{hr:>6s}    {fo_s:>5s}     {ke_s:>6s}        {summary[w]['flips_vs_5d']:>4d}{tag}",
                  flush=True)

    # CSV/MD output
    out_csv = ROOT / "outputs" / "window_sensitivity_extended.csv"
    with out_csv.open("w", encoding="utf-8") as f:
        f.write("strategy,window,hit,miss,abstain,na,hit_rate_pct,filter_out_precision_pct,keep_precision_pct,flips_vs_5d\n")
        for strat in ("trend_aware", "recency_weighted"):
            for w in WINDOWS:
                c = summary[w]["counts"][strat]
                denom = c["hit"] + c["miss"]
                hr = c["hit"]/denom*100 if denom else ""
                fo = c["filter_out_precision"]*100 if c["filter_out_precision"] is not None else ""
                ke = c["keep_precision"]*100 if c["keep_precision"] is not None else ""
                f.write(f"{strat},{w},{c['hit']},{c['miss']},{c['abstain']},{c['n/a']},"
                        f"{hr},{fo},{ke},{summary[w]['flips_vs_5d']}\n")
    print(f"\n[saved] {out_csv}", flush=True)

    out_md = ROOT / "outputs" / "window_sensitivity_extended.md"
    with out_md.open("w", encoding="utf-8") as f:
        f.write(f"# Extended window sensitivity (n={len(rows)} unique tickers)\n\n")
        f.write(f"Combined: 24 mixed-sector + 20 IT/telecom backtests, deduped.\n\n")
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
