"""Comprehensive coverage audit — classify why each indicator is missing.

For each indicator, determine whether the missing data is:
  (a) GENUINELY ABSENT — original report didn't include it (conditional)
  (b) DATA-DEPTH LIMIT — Tempest API doesn't expose older years
  (c) DERIVATION GAP — underlying data is there, but our derivation isn't running
  (d) EXTRACTION BUG — data is in source, but our extractor missed it

Then estimate per-indicator recovery impact based on sensitivity analysis.
"""
from __future__ import annotations
import json
import sys
import io
import glob
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent

JGAAP_ALL = set(["3656","3760","3923","4385","4475","4477","4480","4684","4768","9684","9697",
                 "4063","4716","4751","6861",
                 "3626","3635","3697","3994","4194","4676","4704","4733","9401","9404","9468","9602","9759",
                 "2121","2317","2326","3636","3660","3661","3668","3765","3778","3844","4071","4384","4443","4686","4722","4776","4812"])


def load_raw_items(ticker):
    p = ROOT / "data" / "tempest" / ticker / "financials_line_items.json"
    if not p.exists(): return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)["data"]


def has_line_item(items, key, fy=None):
    for i in items:
        if i.get("line_item_key") != key: continue
        if i.get("fiscal_quarter") is not None: continue
        if fy is not None and i.get("fiscal_year") != fy: continue
        if i.get("is_consolidated") is False: continue
        return True
    return False


def main():
    print("Comprehensive indicator coverage audit\n", flush=True)

    # Load V2 results to know which predictions are missing which indicators
    with open(ROOT / "outputs" / "code_based_scorer_v2_results.json", encoding="utf-8") as f:
        v2 = json.load(f)

    # Cache raw items per ticker
    raw_items = {tk: load_raw_items(tk) for tk in JGAAP_ALL}

    # Cache agent cache files per ticker
    agent_cache = {}
    for tk in JGAAP_ALL:
        cache_files = sorted(glob.glob(str(ROOT / "outputs" / "agent_cache" /
                                           f"{tk}_min2020_simp1_cutoffnone_*_v5_*.json")))
        if cache_files:
            with open(cache_files[-1], encoding="utf-8") as f:
                agent_cache[tk] = json.load(f)

    rows = v2["rows"]

    # ========================================================================
    # AUDIT EACH INDICATOR
    # ========================================================================
    findings = {}

    # ------------------------------------------------------------------------
    # 1. DSO days (0% coverage)
    # ------------------------------------------------------------------------
    print("=" * 80, flush=True)
    print("DSO (days sales outstanding) — 0% coverage", flush=True)
    print("=" * 80, flush=True)
    # DSO needs: trade_receivables + revenue (annual)
    # Check raw data availability for these
    tr_present = 0; rev_present = 0; both_present = 0
    for r in rows:
        items = raw_items.get(r["ticker"], [])
        try:
            fy = int(r["prediction_pair"].split("->")[1].replace("FY",""))
        except: continue
        has_tr = has_line_item(items, "notes_and_accounts_receivable_trade", fy) or \
                 has_line_item(items, "trade_and_other_receivables", fy)
        has_rev = has_line_item(items, "net_sales", fy)
        if has_tr: tr_present += 1
        if has_rev: rev_present += 1
        if has_tr and has_rev: both_present += 1
    n = len(rows)
    print(f"\n  trade_receivables present in raw data: {tr_present}/{n} ({tr_present/n*100:.0f}%)", flush=True)
    print(f"  net_sales present:                     {rev_present}/{n} ({rev_present/n*100:.0f}%)", flush=True)
    print(f"  BOTH (DSO could be derived):           {both_present}/{n} ({both_present/n*100:.0f}%)", flush=True)
    if both_present > 0:
        cause = "DERIVATION GAP"
        print(f"\n  CAUSE: {cause} — underlying data is there, but DSO derivation isn't running", flush=True)
        recoverable = both_present
    else:
        cause = "GENUINELY ABSENT"
        recoverable = 0
    findings["DSO"] = {"cause": cause, "recoverable": recoverable, "total": n}

    # ------------------------------------------------------------------------
    # 2. inventory_days (31% coverage)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80, flush=True)
    print("inventory_days — 31% coverage", flush=True)
    print("=" * 80, flush=True)
    # Needs: inventory + COGS or revenue
    inv_present = 0; cogs_present = 0
    inv_zero_or_missing_by_ticker = {}
    for r in rows:
        items = raw_items.get(r["ticker"], [])
        try:
            fy = int(r["prediction_pair"].split("->")[1].replace("FY",""))
        except: continue
        has_inv = has_line_item(items, "inventories", fy) or has_line_item(items, "total_inventories", fy)
        has_cogs = has_line_item(items, "cost_of_sales", fy)
        if has_inv: inv_present += 1
        if has_cogs: cogs_present += 1
    # Check: how many tickers genuinely don't have inventory (software companies)?
    tickers_with_inv = 0; tickers_without_inv = 0
    for tk in JGAAP_ALL:
        items = raw_items.get(tk, [])
        any_inv = any(i.get("line_item_key") in ("inventories", "total_inventories") for i in items)
        if any_inv: tickers_with_inv += 1
        else: tickers_without_inv += 1
    print(f"\n  inventory present in raw data: {inv_present}/{n} ({inv_present/n*100:.0f}%)", flush=True)
    print(f"  cost_of_sales present:         {cogs_present}/{n} ({cogs_present/n*100:.0f}%)", flush=True)
    print(f"  Tickers with ANY inventory data: {tickers_with_inv}/{len(JGAAP_ALL)}", flush=True)
    print(f"  Tickers with NO inventory data: {tickers_without_inv}/{len(JGAAP_ALL)} (likely software co's)", flush=True)
    if tickers_without_inv > 10:
        cause = "MOSTLY CONDITIONAL (software cos don't carry inventory) + some derivation gap"
        recoverable_pct = (inv_present / n) * 100
    else:
        cause = "DERIVATION GAP"
        recoverable_pct = (inv_present / n) * 100
    print(f"\n  CAUSE: {cause}", flush=True)
    findings["inventory_days"] = {"cause": cause, "recoverable": inv_present, "total": n}

    # ------------------------------------------------------------------------
    # 3. equity_yoy_pred (37% coverage)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80, flush=True)
    print("equity_yoy_pred — 37% coverage", flush=True)
    print("=" * 80, flush=True)
    # Needs: total_equity for both prev_fy and curr_fy
    eq_pairs_available = 0
    for r in rows:
        items = raw_items.get(r["ticker"], [])
        try:
            curr_fy = int(r["prediction_pair"].split("->")[1].replace("FY",""))
            prev_fy = int(r["prediction_pair"].split("->")[0].replace("FY",""))
        except: continue
        has_curr = has_line_item(items, "total_equity", curr_fy)
        has_prev = has_line_item(items, "total_equity", prev_fy)
        if has_curr and has_prev: eq_pairs_available += 1
    print(f"\n  Both prev+curr equity available: {eq_pairs_available}/{n} ({eq_pairs_available/n*100:.0f}%)", flush=True)
    if eq_pairs_available > n * 0.5:
        cause = "DERIVATION GAP" if eq_pairs_available > 0 else "DATA-DEPTH LIMIT"
    else:
        cause = "DATA-DEPTH LIMIT (older years' equity missing)"
    findings["equity_yoy_pred"] = {"cause": cause, "recoverable": eq_pairs_available, "total": n}
    print(f"  CAUSE: {cause}", flush=True)

    # ------------------------------------------------------------------------
    # 4. net_margin_level (49% coverage)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80, flush=True)
    print("net_margin_level — 49% coverage", flush=True)
    print("=" * 80, flush=True)
    # net_margin_level comes from peer_comparison.my.net_margin_pct in agent cache
    # Need to check: are revenue + net profit both available?
    rev_ni_pairs = 0
    for r in rows:
        items = raw_items.get(r["ticker"], [])
        try:
            fy = int(r["prediction_pair"].split("->")[1].replace("FY",""))
        except: continue
        has_rev = has_line_item(items, "net_sales", fy)
        has_ni = (has_line_item(items, "profit_loss", fy) or
                  has_line_item(items, "profit_attributable_to_owners_of_parent", fy))
        if has_rev and has_ni: rev_ni_pairs += 1
    print(f"\n  Both revenue+net_income available: {rev_ni_pairs}/{n} ({rev_ni_pairs/n*100:.0f}%)", flush=True)
    if rev_ni_pairs > n * 0.7:
        cause = "DERIVATION GAP (peer_comparison block populates net_margin only when sector median computable)"
        recoverable = rev_ni_pairs
    else:
        cause = "DATA-DEPTH LIMIT"
        recoverable = rev_ni_pairs
    findings["net_margin_level"] = {"cause": cause, "recoverable": recoverable, "total": n}
    print(f"  CAUSE: {cause}", flush=True)

    # ------------------------------------------------------------------------
    # 5. CFO/NI ratio (50% — already deep-dived)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80, flush=True)
    print("CFO/NI ratio — 50% coverage (already deep-dived)", flush=True)
    print("=" * 80, flush=True)
    cfo_present = 0
    for r in rows:
        items = raw_items.get(r["ticker"], [])
        try:
            fy = int(r["prediction_pair"].split("->")[1].replace("FY",""))
        except: continue
        if has_line_item(items, "cash_flows_from_operating", fy):
            cfo_present += 1
    print(f"\n  cash_flows_from_operating in Tempest raw: {cfo_present}/{n} ({cfo_present/n*100:.0f}%)", flush=True)
    print(f"  CAUSE: DATA-DEPTH LIMIT — Tempest doesn't have CFO for fiscal years <2023", flush=True)
    print(f"  Could recover via EDINET XBRL (1-2 weeks engineering)", flush=True)
    findings["cfo_ni"] = {"cause": "DATA-DEPTH LIMIT", "recoverable": cfo_present, "total": n}

    # ------------------------------------------------------------------------
    # 6. goodwill (32% — already deep-dived)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80, flush=True)
    print("goodwill — 32% coverage (already deep-dived)", flush=True)
    print("=" * 80, flush=True)
    # Check how many tickers NEVER have goodwill (genuinely conditional)
    never_gw = 0; sometimes_gw = 0
    for tk in JGAAP_ALL:
        items = raw_items.get(tk, [])
        any_gw = any(i.get("line_item_key") == "goodwill" for i in items)
        if not any_gw: never_gw += 1
        else: sometimes_gw += 1
    print(f"\n  Tickers with goodwill in any year:  {sometimes_gw}/{len(JGAAP_ALL)}", flush=True)
    print(f"  Tickers with NO goodwill ever:       {never_gw}/{len(JGAAP_ALL)} (CONDITIONAL — never acquired)", flush=True)
    print(f"  CAUSE: ~{never_gw/len(JGAAP_ALL)*100:.0f}% GENUINELY ABSENT + rest DATA-DEPTH for older years", flush=True)
    findings["goodwill"] = {"cause": "MOSTLY CONDITIONAL + data-depth", "recoverable": "~5-10pp", "total": n}

    # ------------------------------------------------------------------------
    # 7. top_segment_share (77% coverage)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80, flush=True)
    print("top_segment_share — 77% coverage", flush=True)
    print("=" * 80, flush=True)
    # Check segment disclosure
    seg_data = ROOT / "data" / "tempest"
    tickers_with_segments = 0
    tickers_without_segments = 0
    for tk in JGAAP_ALL:
        seg_file = seg_data / tk / "segments.json"
        if seg_file.exists():
            try:
                with open(seg_file, encoding="utf-8") as f:
                    s = json.load(f)
                if s.get("data"):
                    tickers_with_segments += 1
                else:
                    tickers_without_segments += 1
            except:
                tickers_without_segments += 1
        else:
            tickers_without_segments += 1
    print(f"\n  Tickers with segment data: {tickers_with_segments}/{len(JGAAP_ALL)}", flush=True)
    print(f"  Tickers without:           {tickers_without_segments}/{len(JGAAP_ALL)}", flush=True)
    if tickers_without_segments > 5:
        cause = "MIXED — single-segment companies (legitimate absence) + some extraction gaps"
    else:
        cause = "EXTRACTION GAP"
    print(f"  CAUSE: {cause}", flush=True)
    findings["top_segment_share"] = {"cause": cause, "recoverable": "modest", "total": n}

    # ========================================================================
    # SUMMARY TABLE
    # ========================================================================
    print("\n" + "=" * 100, flush=True)
    print("SUMMARY — coverage cause classification", flush=True)
    print("=" * 100, flush=True)
    print(f"\n{'Indicator':<22}{'Cause':<50}{'Recoverable':<15}", flush=True)
    print("-" * 87, flush=True)
    for ind, info in findings.items():
        rec = info["recoverable"]
        rec_str = f"{rec}/{info['total']}" if isinstance(rec, int) else str(rec)
        print(f"  {ind:<20}{info['cause']:<50}{rec_str:<15}", flush=True)

    # Save
    out = ROOT / "outputs" / "coverage_audit_results.json"
    out.write_text(json.dumps(findings, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out}", flush=True)


if __name__ == "__main__":
    main()
