"""Generate 4-quadrant classification tables from an agent backtest run.

Per the senior's 2026-05-12 framework (revenue / stock direction):
   売上○ 株価○   HEALTHY     — clean keeper
   売上○ 株価×   NOISE       — senior's primary filter target
   売上× 株価○   ANOMALY     — rare, market leads earnings
   売上× 株価×   DECLINE     — clear decline

Outputs:
  outputs/quadrant_tables/
    fy2020_2021.csv  /  .md
    fy2021_2022.csv  /  .md
    fy2022_2023.csv  /  .md
    fy2023_2024.csv  /  .md
    fy2024_2025.csv  /  .md
    aggregate.csv    /  .md   ← per-company quadrant pattern + agent verdict

Usage:
    python scripts/generate_quadrant_tables.py
    python scripts/generate_quadrant_tables.py --in outputs/backtest_option2_bounce_trend.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Helpers from the agent — these read CACHED Tempest data, no LLM cost.
from app.ingest.tempest_loader import load_asr_series   # noqa: E402
from app.subagents.quiet_change import _stock_5d_move   # noqa: E402
from app.tools.jpx_industries import lookup as _jpx_lookup   # noqa: E402


def resolve_name(code: str, fallback: str) -> str:
    """Look up the proper company name from JPX 33業種 table.
    Falls back to whatever was in the JSON if lookup fails."""
    rec = _jpx_lookup(code)
    if rec and rec.name and rec.name != code:
        return rec.name
    return fallback if fallback and fallback != code else code

# Quadrant labels (bilingual + compact). Order:
# (en_label, ja_label, tag_en, tag_ja, compact)
QUADRANT_LABELS = {
    "rs": ("Rev✓ Stock✓", "売上○ 株価○", "HEALTHY", "健全",   "oo"),
    "rn": ("Rev✓ Stock✗", "売上○ 株価×", "NOISE",   "ノイズ", "ox"),
    "ns": ("Rev✗ Stock✓", "売上× 株価○", "ANOMALY", "異常",   "xo"),
    "nn": ("Rev✗ Stock✗", "売上× 株価×", "DECLINE", "衰退",   "xx"),
    "na": ("Rev? Stock?", "売上? 株価?", "N/A",     "不明",   "--"),
}


def classify(rev_pct: float | None, stock_pct: float | None) -> str:
    if rev_pct is None or stock_pct is None:
        return "na"
    r_up = rev_pct > 0
    s_up = stock_pct > 0
    if r_up and s_up:   return "rs"
    if r_up and not s_up: return "rn"
    if not r_up and s_up: return "ns"
    return "nn"


def pattern_summary(quadrants: list[str]) -> str:
    """Compact-symbol pattern label for the aggregate column.

    Examples:
      [oo, oo, oo, oo]      → "4× oo"
      [oo, ox, oo, ox]      → "2× oo, 2× ox"
      [ox, ox, oo, ox]      → "3× ox"
      [oo, oo, oo]          → "3× oo"
      empty / all missing   → "—"
    """
    non_na = [q for q in quadrants if q != "na"]
    if not non_na:
        return "—"
    counts = {q: non_na.count(q) for q in set(non_na)}
    # Sort by count desc, then by quadrant key (rs < rn < ns < nn)
    sort_order = {"rs": 0, "rn": 1, "ns": 2, "nn": 3}
    sorted_qs = sorted(counts.items(),
                       key=lambda x: (-x[1], sort_order.get(x[0], 99)))
    # Convert each (quadrant_key, count) to "Nx <compact_symbol>"
    parts = []
    for q, count in sorted_qs:
        compact = QUADRANT_LABELS[q][4]   # 'oo' / 'ox' / 'xo' / 'xx'
        parts.append(f"{count}× {compact}")
    return ", ".join(parts)


def filter_recommendation(verdict: str) -> str:
    return {
        "growth_likely":   "KEEP",
        "growth_unlikely": "FILTER OUT",
        "uncertain":       "REVIEW",
    }.get(verdict, "?")


def aggregate_trend_aware(judgments: list[str]) -> str:
    """Mirror of the production trend_aware voting rule."""
    if not judgments:
        return "uncertain"
    latest = judgments[-1]
    if latest in ("growth_likely", "growth_unlikely"):
        return latest
    priors = judgments[:-1]
    if any(j == "growth_likely" for j in priors):
        return "growth_unlikely"
    if any(j == "growth_unlikely" for j in priors):
        return "growth_unlikely"
    return "uncertain"


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:   # BOM for Excel
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write_md(path: Path, title: str, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", ""]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="input_path",
                    default="outputs/backtest_option2_bounce_trend.json")
    ap.add_argument("--out-dir", default="outputs/quadrant_tables")
    args = ap.parse_args()

    in_path = ROOT / args.input_path
    if not in_path.exists():
        print(f"ERROR: input not found: {in_path}")
        return 1
    data = json.loads(in_path.read_text(encoding="utf-8"))
    rows = [r for r in data.get("rows", []) if "error" not in r]
    print(f"Loaded {len(rows)} companies from {in_path.name}")

    # Build per-pair index: {(prev_fy, curr_fy): [(ticker, name, rev, stock, pred), ...]}
    by_pair: dict[tuple[int, int], list[dict]] = defaultdict(list)
    # Also build per-ticker quadrant timeline for the aggregate
    ticker_quadrants: dict[str, dict] = {}

    for r in rows:
        code = r["code"]
        name = resolve_name(code, r.get("name") or code)
        ticker_quadrants[code] = {
            "code": code,
            "name": name,
            "pairs": {},   # (prev, curr) -> quadrant
            "judgments_by_pair": {},   # (prev, curr) -> judgment
            "final_verdict": None,
        }

        # Map judgments by (prev_fy, curr_fy) so we can attach them to the
        # rev/stock data we'll pull from cached Tempest below.
        for pp in r.get("per_pair_judgments", []):
            pair_label = pp.get("pair", "")
            try:
                parts = pair_label.replace("FY", "").split("->")
                prev_fy = int(parts[0])
                curr_fy = int(parts[1])
            except (ValueError, IndexError):
                continue
            ticker_quadrants[code]["judgments_by_pair"][(prev_fy, curr_fy)] = pp.get("judgment", "uncertain")

        # Pull per-pair revenue + stock data DIRECTLY from cached Tempest
        # (no LLM, no network — just JSON file reads). This gives us rev/stock
        # for BOTH decision and outcome pairs, unlike the backtest JSON which
        # only has it for outcome pairs.
        try:
            series = load_asr_series(code)
        except Exception:
            series = []
        for prev, curr in zip(series, series[1:]):
            prev_fy = int(prev["period_end"][:4])
            curr_fy = int(curr["period_end"][:4])
            prev_rev = prev.get("revenue") or 0
            curr_rev = curr.get("revenue") or 0
            rev_pct = ((curr_rev - prev_rev) / prev_rev * 100.0) if prev_rev > 0 else None
            try:
                stock = _stock_5d_move(code, curr["filing_date"])
                stock_pct = stock.get("stock_5d_return_pct")
            except Exception:
                stock_pct = None
            quad = classify(rev_pct, stock_pct)
            judgment = ticker_quadrants[code]["judgments_by_pair"].get(
                (prev_fy, curr_fy), "(outcome year — no agent prediction)")

            by_pair[(prev_fy, curr_fy)].append({
                "code": code,
                "name": name,
                "rev_pct": rev_pct,
                "stock_pct": stock_pct,
                "quadrant": quad,
                "judgment": judgment,
            })
            ticker_quadrants[code]["pairs"][(prev_fy, curr_fy)] = quad

        # Final verdict for aggregate
        ticker_quadrants[code]["final_verdict"] = r.get("by_strategy", {}).get(
            "trend_aware", {}).get("prediction", "uncertain")

    # --- write per-pair tables ---
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    sorted_pairs = sorted(by_pair.keys())
    print(f"Pair years found: {sorted_pairs}")

    for (prev_fy, curr_fy) in sorted_pairs:
        entries = sorted(by_pair[(prev_fy, curr_fy)], key=lambda e: e["code"])

        # Quadrant counts for this pair
        q_counts = {q: 0 for q in QUADRANT_LABELS}
        for e in entries:
            q_counts[e["quadrant"]] += 1

        title = f"FY{prev_fy} → FY{curr_fy} — Quadrant Classification ({len(entries)} companies)"
        subtitle = (f"Quadrant counts: "
                    f"○○={q_counts['rs']}  ○×={q_counts['rn']}  "
                    f"×○={q_counts['ns']}  ××={q_counts['nn']}  N/A={q_counts['na']}")

        header = ["Ticker", "Company", "Revenue Δ%", "Stock 5d %",
                  "Compact", "Quadrant (JA)", "Tag", "Agent prediction"]
        data_rows = []
        for e in entries:
            en_label, ja_label, tag_en, tag_ja, compact = QUADRANT_LABELS[e["quadrant"]]
            rev_s = "n/a" if e["rev_pct"] is None else f"{e['rev_pct']:+.2f}%"
            stock_s = "n/a" if e["stock_pct"] is None else f"{e['stock_pct']:+.2f}%"
            data_rows.append([
                e["code"], e["name"][:25], rev_s, stock_s,
                compact, ja_label, tag_en,
                e["judgment"].replace("_", " "),
            ])

        base = f"fy{prev_fy}_{curr_fy}"
        write_csv(out_dir / f"{base}.csv", header, data_rows)

        md_title = f"{title}\n\n{subtitle}"
        write_md(out_dir / f"{base}.md", md_title, header, data_rows)
        print(f"  wrote {base}.csv / .md  ({len(data_rows)} rows; {subtitle})")

    # --- aggregate table: per-company pattern across all years ---
    all_pairs = sorted_pairs
    agg_header = ["Ticker", "Company"] + [f"FY{p}→{c}" for (p, c) in all_pairs] + \
                 ["Pattern", "Agent verdict", "Filter rec."]
    agg_rows = []
    for code in sorted(ticker_quadrants.keys()):
        tq = ticker_quadrants[code]
        pair_quadrants = []
        for (prev_fy, curr_fy) in all_pairs:
            q = tq["pairs"].get((prev_fy, curr_fy), "na")
            # Use compact "oo / ox / xo / xx / --" notation per user request
            _, _, _, _, compact = QUADRANT_LABELS[q]
            pair_quadrants.append(compact)
        # Build quadrant timeline for the summary
        q_timeline = [tq["pairs"].get(k, "na") for k in all_pairs]
        pattern = pattern_summary(q_timeline)
        verdict = tq["final_verdict"] or "uncertain"
        rec = filter_recommendation(verdict)
        agg_rows.append([code, tq["name"][:25]] + pair_quadrants + [pattern, verdict.replace("_", " "), rec])

    # Summary line
    n_keep = sum(1 for r in agg_rows if r[-1] == "KEEP")
    n_drop = sum(1 for r in agg_rows if r[-1] == "FILTER OUT")
    n_rev = sum(1 for r in agg_rows if r[-1] == "REVIEW")
    summary = (f"Total: {len(agg_rows)} companies. "
               f"KEEP: {n_keep}  |  FILTER OUT: {n_drop}  |  REVIEW: {n_rev}")

    write_csv(out_dir / "aggregate.csv", agg_header, agg_rows)
    write_md(out_dir / "aggregate.md",
             f"Aggregate quadrant pattern — {len(agg_rows)} companies\n\n{summary}",
             agg_header, agg_rows)
    print(f"\nWrote aggregate.csv / .md")
    print(f"  {summary}")
    print(f"\nAll tables saved to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
