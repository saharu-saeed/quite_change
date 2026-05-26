"""Aggregate the per-sector run JSONs into one cross-sector view.

Reads every outputs/quiet_change_v2/sectors/{slug}/_run_{date}.json and
produces:

  - PER-SECTOR SUMMARY: pool size, survivors, strict-gate hit count, top
    watch-list name + composite
  - GLOBAL EMPIRICAL FINDING: how many strict-gate hits across N sectors
    (this is the "literally-unnoticed + idiosyncratic" empty-set claim)
  - GLOBAL WATCH-LIST: top-N across all sectors by watchlist_composite,
    each row tagged with its sector

The watchlist composite is comparable across sectors only loosely (each
is a within-sector percentile composite), but it's good enough to surface
the strongest names per sector and to spot which sector has the most
compelling overall candidate.

Usage:
    python scripts/aggregate_sector_sweep.py
    python scripts/aggregate_sector_sweep.py --top 20
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.subagents.valuation_screen import (  # noqa: E402
    compute_global_valuation_norms,
    compute_sector_valuation_norms,
    compute_valuation_metrics,
    passes_profile_c_strict_gate,
    passes_profile_c_unseen_filter,
    score_valuation,
    valuation_sanity_flag,
)
from app.subagents.liquidity_mandate import (  # noqa: E402
    check_compliance,
    load_profile,
)

SECTORS_DIR = ROOT / "outputs" / "quiet_change_v2" / "sectors"
OUT_DIR = ROOT / "outputs" / "quiet_change_v2" / "sweep"
TEMPEST_DIR = ROOT / "data" / "tempest"
SERP_CACHE_DIR = ROOT / "outputs" / "quiet_change_v2" / "serpapi_cache"

# Alternative attention weight for Setting B output (per desk question 1).
# Current sector pipeline runs at 0.30; Setting B recomputes at 0.10 so the
# desk can see both rankings side-by-side and pick which fits their thesis.
SETTING_A_WEIGHTS = {"divergence": 0.35, "quality": 0.35, "attention": 0.30}
SETTING_B_WEIGHTS = {"divergence": 0.45, "quality": 0.45, "attention": 0.10}

# Fame heuristic: market cap above this threshold combined with low anomaly-
# attention almost certainly indicates a search-coverage failure rather than
# a genuinely-uncovered company. The anomaly search asks "is the SPECIFIC
# DROP being written about?" — a household-name mega-brand with a mild drop
# will look thin to that query while in fact being wall-to-wall covered.
# Pulled to ¥500B based on the observation that 日清食品 (¥828B, attn +4.0)
# is the clear false-thin case in this sweep; ¥500B excludes Mid400 mega-
# brands while keeping mid-cap Small 1 names like Justsystems (~¥250B) and
# 中国塗料 (~¥157B) in scope.
FAME_MARKET_CAP_JPY = 500e9
FAME_ATTN_CEILING = 8.0
# Softer "fame-suspect" band: Mid400-sized names (¥300–500B) with thin
# attention. Below the FAME_FAIL bar but still a household-name brand
# whose anomaly-search "thin" reading could plausibly be a search miss
# rather than genuine non-coverage. Flag, don't exclude — the analyst
# decides. This catches names that fall through the FAME_FAIL gap.
FAME_SUSPECT_MCAP_LOWER = 300e9
FAME_SUSPECT_ATTN_CEILING = 8.0   # matches LOW_ATTENTION_CONFIRM_THRESHOLD

# Divergence threshold that splits idiosyncratic-drop names (Profile A —
# fell materially more than sector peers, "why did THIS one fall harder?")
# from sector-move names (Profile B — moved roughly with peers, "is this an
# overlooked-quality name in a soft sector?"). The two profiles answer
# different desk questions; the rebalanced composite mixes them, so the
# aggregator splits them in the rendered output for transparency.
IDIOSYNCRATIC_PP_THRESHOLD = -5.0


def _approx_market_cap(ticker: str) -> float | None:
    """latest_close * shares_outstanding. Returns None if data unavailable."""
    try:
        prices = json.load(open(TEMPEST_DIR / ticker / "prices.json", encoding="utf-8"))["data"]
        inds = json.load(open(TEMPEST_DIR / ticker / "indicators.json", encoding="utf-8"))["data"]
    except Exception:
        return None
    if not prices or not inds:
        return None
    try:
        latest_close = float(prices[0]["close"])
    except (KeyError, TypeError, ValueError):
        return None
    inds = sorted(inds, key=lambda r: r.get("fiscal_year") or 0, reverse=True)
    so = inds[0].get("shares_outstanding")
    if not so:
        return None
    try:
        return latest_close * float(so)
    except (TypeError, ValueError):
        return None


def _fame_flag(market_cap: float | None, attention: float | None) -> str:
    if market_cap is None or attention is None:
        return ""
    if market_cap >= FAME_MARKET_CAP_JPY and attention <= FAME_ATTN_CEILING:
        return "FAME_FAIL"     # mega-brand looking thin — almost certainly search miss
    if market_cap >= FAME_MARKET_CAP_JPY:
        return "large"          # large but adequate attention — not a coverage gap
    if (
        FAME_SUSPECT_MCAP_LOWER <= market_cap < FAME_MARKET_CAP_JPY
        and attention <= FAME_SUSPECT_ATTN_CEILING
    ):
        return "fame_suspect"   # Mid400-sized brand with thin attn — verify before promoting
    return ""


def _classify_profile(row: dict) -> str:
    """Two-profile split for the watch-list output.

    Profile A — IDIOSYNCRATIC: fell materially more than sector peers
        (divergence <= -5pp). Desk question: "why did THIS one drop harder?"

    Profile B — SECTOR_MOVE_THIN: moved roughly with peers (small divergence)
        but lightly covered. Desk question: "is this an overlooked-quality
        name worth a sector-recovery bet?"

    OTHER: positive divergence (fell less than peers) or missing data —
        in the top-25 by composite but not the canonical target.
    """
    div = (row.get("sector_rel") or {}).get("sector_relative_pp")
    if div is None:
        return "OTHER"
    if div <= IDIOSYNCRATIC_PP_THRESHOLD:
        return "A_IDIOSYNCRATIC"
    if div >= -IDIOSYNCRATIC_PP_THRESHOLD:    # > +5pp, fell less than peers
        return "OTHER"
    return "B_SECTOR_MOVE_THIN"


def _latest_annual_revenue(ticker: str) -> float | None:
    """Most recent annual net_sales from cached financials.json."""
    p = TEMPEST_DIR / ticker / "financials.json"
    if not p.exists():
        return None
    try:
        fin = json.load(open(p, encoding="utf-8"))["data"]
    except Exception:
        return None
    annuals = [r for r in fin if r.get("fiscal_quarter") in (None, "null")]
    annuals.sort(key=lambda r: r.get("period_end") or "", reverse=True)
    if not annuals:
        return None
    try:
        return float(annuals[0].get("net_sales") or 0) or None
    except (TypeError, ValueError):
        return None


def _load_article_snippets(ticker: str, max_items: int = 3) -> list[dict]:
    """Pull title+snippet+date from cached SerpAPI anomaly+confirm results.

    These are the actual articles the attention search surfaced — what's being
    written about the drop, in the source's own words. Surface to the desk so
    they can read the explanation without re-running the search.
    """
    out: list[dict] = []
    seen_urls: set[str] = set()
    for kind in ("anomaly", "confirm"):
        cache_path = SERP_CACHE_DIR / f"{ticker}_{kind}.json"
        if not cache_path.exists():
            continue
        try:
            payload = json.load(open(cache_path, encoding="utf-8"))
        except Exception:
            continue
        # Pull from news_results (google_news engine) and organic_results
        items: list[dict] = []
        items.extend(payload.get("news_results", []) or [])
        items.extend(payload.get("organic_results", []) or [])
        for item in items:
            url = item.get("link") or item.get("url") or ""
            if not url or url in seen_urls:
                continue
            title = item.get("title", "").strip()
            snippet = item.get("snippet", "").strip()
            if not title and not snippet:
                continue
            # Skip pure aggregator stubs (minkabu, kabutan landing pages)
            stub_domains = ("minkabu.jp", "kabutan.jp", "irbank.net", "kabuyoho.jp")
            if any(d in url for d in stub_domains) and "/news/" not in url and "/article" not in url:
                continue
            seen_urls.add(url)
            out.append({
                "title": title,
                "snippet": snippet[:280],   # cap to keep output readable
                "url": url,
                "date": item.get("date", ""),
                "source_kind": kind,
            })
            if len(out) >= max_items:
                return out
    return out


# ----- Composite recompute (dual-weight) -----

def _percentile_in_sorted(value: float, sorted_values: list[float]) -> float:
    if not sorted_values:
        return 50.0
    below = sum(1 for v in sorted_values if v < value)
    equal = sum(1 for v in sorted_values if v == value)
    return ((below + equal / 2.0) / len(sorted_values)) * 100.0


def _recompute_composite_for_pool(rows: list[dict], weights: dict) -> None:
    """Recompute watchlist_composite_<setting> for each row using given weights.

    Operates on the per-sector pool — same percentile baselines as the original
    per-sector run produced. Writes:
        r['comp_setting_X'] where X derived from weights signature
    """
    divs = sorted(
        r["sector_rel"]["sector_relative_pp"]
        for r in rows
        if r.get("sector_rel", {}).get("sector_relative_pp") is not None
    )
    quals = sorted(
        (r["quality"]["quality_score"] or {}).get("composite_score")
        for r in rows
        if r.get("quality", {}).get("data_ok")
        and (r["quality"].get("quality_score") or {}).get("composite_score") is not None
    )
    attns = sorted(r["attention_score"] for r in rows if r.get("attention_score") is not None)

    setting_label = f"a{int(weights['attention']*100):02d}"  # e.g. a30, a10

    for r in rows:
        d = r.get("sector_rel", {}).get("sector_relative_pp")
        q = (r.get("quality") or {}).get("quality_score", {}).get("composite_score")
        a = r.get("attention_score")

        div_signal = (100 - _percentile_in_sorted(d, divs)) if d is not None else 50.0
        qual_signal = _percentile_in_sorted(q, quals) if q is not None else 50.0
        attn_signal = (100 - _percentile_in_sorted(a, attns)) if a is not None else 50.0

        composite = (
            weights["divergence"] * div_signal
            + weights["quality"] * qual_signal
            + weights["attention"] * attn_signal
        )
        r[f"comp_{setting_label}"] = round(composite, 1)


def _load_latest_runs() -> list[dict]:
    """Find the latest _run_*.json under each sector subdir."""
    out: list[dict] = []
    if not SECTORS_DIR.exists():
        return out
    for sec_dir in sorted(SECTORS_DIR.iterdir()):
        if not sec_dir.is_dir():
            continue
        runs = sorted(sec_dir.glob("_run_*.json"))
        if not runs:
            continue
        latest = runs[-1]
        data = json.load(open(latest, encoding="utf-8"))
        data["_source"] = str(latest)
        out.append(data)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20,
                    help="how many global watch-list names to print")
    args = ap.parse_args(argv)

    runs = _load_latest_runs()
    if not runs:
        print("No sector runs found under outputs/quiet_change_v2/sectors/.")
        return 1

    print("=" * 110)
    print(f"CROSS-SECTOR SWEEP — {len(runs)} sectors")
    print("=" * 110)
    print(
        f"{'Sector':<22} {'Pool':<6} {'Univ':<6} {'Band':<6} "
        f"{'Strict':<7} {'TopName':<24} {'TopComp':<7} {'TopDiv':<8} {'TopQ':<6} {'Attn':<6}"
    )
    print("-" * 110)

    total_pool = 0
    total_band = 0
    total_strict = 0
    global_watchlist: list[dict] = []

    for r in runs:
        s = r.get("sector_33_name", "?")
        st = r.get("stats", {})
        pool = st.get("pool_size", 0)
        univ = st.get("after_universe_filter", 0)
        band = st.get("after_scale_band", 0)
        strict = st.get("strict_dual_gate_hits", 0)
        total_pool += pool
        total_band += band
        total_strict += strict

        ranked = r.get("watchlist_ranked", [])
        top = ranked[0] if ranked else {}
        top_name = top.get("company_name", "-")[:23]
        top_comp = top.get("watchlist_composite")
        top_sr = top.get("sector_rel") or {}
        top_div = top_sr.get("sector_relative_pp")
        top_q = (top.get("quality") or {}).get("quality_score", {}).get("composite_score")
        top_attn = top.get("attention_score")

        comp_str = f"{top_comp:5.1f}" if top_comp is not None else "  -  "
        div_str = f"{top_div:+6.2f}" if top_div is not None else "   -  "
        q_str = f"{top_q:5.1f}" if top_q is not None else "  -  "
        attn_str = f"{top_attn:+5.1f}" if top_attn is not None else " -  "

        print(
            f"{s:<22} {pool:<6} {univ:<6} {band:<6} "
            f"{strict:<7} {top_name:<24} {comp_str:<7} {div_str:<8} {q_str:<6} {attn_str:<6}"
        )

        # Recompute composites at BOTH weight settings within this sector's pool
        # (per-sector percentiles are what the original run used; preserve that)
        _recompute_composite_for_pool(ranked, SETTING_A_WEIGHTS)   # writes comp_a30
        _recompute_composite_for_pool(ranked, SETTING_B_WEIGHTS)   # writes comp_a10

        for row in ranked:
            row["_sector"] = s
            global_watchlist.append(row)

    print("-" * 110)
    print(
        f"{'TOTAL':<22} {total_pool:<6} {'':<6} {total_band:<6} "
        f"{total_strict:<7}"
    )

    # ---------- Empirical finding ----------
    print("\n" + "=" * 80)
    print("EMPIRICAL FINDING — strict dual-gate across the sweep")
    print("=" * 80)
    print(f"  Sectors screened:                 {len(runs)}")
    print(f"  Total mid-cap tickers in pool:    {total_pool}")
    print(f"  Survived rev↑+stock↓ + band:      {total_band}")
    print(f"  Cleared strict gate (literal-")
    print(f"   unnoticed + idiosyncratic-down): {total_strict}")
    if total_band > 0:
        rate = total_strict / total_band * 100
        print(f"  Strict-gate hit rate (of survivors): {rate:.1f}%")

    # ---------- Annotate every name with market cap + fame flag + profile ----------
    # Also run liquidity + mandate compliance check (item B from 2026-05-24).
    # This is the advisor extension's "legwork" piece — pure arithmetic against
    # config/fund_profile.json. Does NOT render a verdict; just tells the desk
    # whether this name is actually tradeable at size and clears the mandate.
    fund_profile = load_profile()
    for r in global_watchlist:
        mcap = _approx_market_cap(r["ticker"])
        r["market_cap_jpy"] = mcap
        r["fame_flag"] = _fame_flag(mcap, r.get("attention_score"))
        r["profile"] = _classify_profile(r)
        # Translate aggregator field names to the keys check_compliance expects
        r["compliance"] = check_compliance(
            {
                "liq_jpy_daily": r.get("liquidity_jpy_daily"),
                "mcap_jpy": mcap,
                "sector_33_name": r.get("sector_33_name") or r.get("_sector"),
                "scale_category": r.get("scale_category"),
            },
            fund_profile,
        )

    # ---------- Generic per-row renderer (used by all profile/setting tables) ----------
    header_line = (
        f"{'Rk':<4} {'Ticker':<7} {'Company':<22} {'Sector':<14} {'Tier':<5} {'Scale':<14} "
        f"{'Stk3m':<7} {'Div':<7} {'Attn':<6} {'Rtl':<4} {'Qual':<6} {'MCap(¥B)':<10} "
        f"{'Liq(¥M/d)':<10} {'Comp':<6} {'Flag':<10}"
    )

    def _print_row(rank: int, r: dict, comp_field: str = "watchlist_composite") -> None:
        sec = r.get("_sector", "?")[:13]
        tier = r.get("tier", "?")
        scale = (r.get("scale_category") or "-")[:13]
        sr = r.get("sector_rel") or {}
        div = sr.get("sector_relative_pp")
        div_str = f"{div:+5.2f}" if div is not None else "  -  "
        q = (r.get("quality") or {}).get("quality_score", {}).get("composite_score")
        q_str = f"{q:5.1f}" if q is not None else "  -  "
        attn = r.get("attention_score")
        attn_str = f"{attn:+5.1f}" if attn is not None else "  -  "
        retail = r.get("retail_chatter", 0)
        retail_str = str(retail) if retail else " "
        comp = r.get(comp_field, r.get("watchlist_composite", 0))
        mcap = r.get("market_cap_jpy")
        mcap_str = f"¥{mcap/1e9:7.0f}B" if mcap else "    -   "
        liq = r.get("liquidity_jpy_daily")
        liq_str = f"¥{liq/1e6:7.0f}M" if liq else "    -    "
        flag = r.get("fame_flag", "") or ("YES_STRICT" if (r.get("dual_gate") or {}).get("quiet_change_candidate") else "")
        print(
            f"{rank:<4} {r['ticker']:<7} {r['company_name'][:21]:<22} {sec:<14} {tier:<5} {scale:<14} "
            f"{r['stock_move_pct']:+5.1f}  {div_str:<7} {attn_str:<6} {retail_str:<4} {q_str:<6} "
            f"{mcap_str:<10} {liq_str:<10} {comp:5.1f}  {flag:<10}"
        )

    def _print_snippets_for_top_3(rows: list[dict]) -> None:
        """Show what articles the search found for the top 3 leads — the desk
        needs to know what the existing analyst/news coverage actually says."""
        if not rows:
            return
        print("\n  --- What the search returned for the top 3 leads ---")
        for r in rows[:3]:
            snips = _load_article_snippets(r["ticker"], max_items=3)
            if not snips:
                print(f"\n  {r['ticker']} {r['company_name']}: (no usable article snippets in cache)")
                continue
            print(f"\n  {r['ticker']} {r['company_name']}:")
            for s in snips:
                title = s.get("title", "")[:80]
                snippet = s.get("snippet", "")[:200]
                date_str = s.get("date", "")
                kind = s.get("source_kind", "")
                print(f"    [{kind}] {title}")
                if date_str:
                    print(f"        ({date_str})")
                if snippet:
                    print(f"        {snippet}")

    def _render_setting(setting_label: str, weights: dict, comp_field: str, header_note: str) -> list[dict]:
        """Sort global_watchlist by the given comp_field, render the top-N split
        by profile, and return the rows displayed."""
        sorted_rows = sorted(global_watchlist, key=lambda r: -(r.get(comp_field) or 0))
        top_n = sorted_rows[: args.top]
        a_rows = [r for r in top_n if r["profile"] == "A_IDIOSYNCRATIC"]
        b_rows = [r for r in top_n if r["profile"] == "B_SECTOR_MOVE_THIN"]
        other_rows = [r for r in top_n if r["profile"] == "OTHER"]

        print("\n" + "█" * 175)
        print(f"SETTING {setting_label}  weights = divergence {weights['divergence']} / quality {weights['quality']} / attention {weights['attention']}")
        print(f"{header_note}")
        print("█" * 175)

        print("\n" + "=" * 175)
        print(f"  PROFILE A — IDIOSYNCRATIC FALLERS, COVERAGE SHOWN  ({len(a_rows)}/{len(top_n)})")
        print(f"  Desk Q: 'is the existing coverage enough to explain a {abs(IDIOSYNCRATIC_PP_THRESHOLD):.0f}pp+ overshoot, or is this an overreaction?'")
        print(f"  These names ARE moderately covered (snippets below). Profile A is NOT 'overlooked' — it's 'judge the overshoot.'")
        print("=" * 175)
        print(header_line)
        print("-" * 175)
        for i, r in enumerate(a_rows, 1):
            _print_row(i, r, comp_field)
        _print_snippets_for_top_3(a_rows)

        print("\n" + "=" * 175)
        print(f"  PROFILE B — MOVED WITH SECTOR  ({len(b_rows)}/{len(top_n)})  "
              f"|  desk Q: 'quality name worth a sector-recovery bet?'  (attention varies — check column)")
        print("=" * 175)
        print(header_line)
        print("-" * 175)
        for i, r in enumerate(b_rows, 1):
            _print_row(i, r, comp_field)
        _print_snippets_for_top_3(b_rows)

        if other_rows:
            print("\n" + "=" * 175)
            print(f"  OTHER  ({len(other_rows)} names — fell less than peers, not canonical target)")
            print("=" * 175)
            print(header_line)
            print("-" * 175)
            for i, r in enumerate(other_rows, 1):
                _print_row(i, r, comp_field)

        return top_n

    # ---------- Setting A (current — attention pulls down noisy names) ----------
    # NOTE: this is NOT "overlooked-thesis" in the literal-zero-coverage sense.
    # Top Profile A names here (e.g. 中国塗料, ヤマックス) still have +10 attention —
    # they're moderately covered. What Setting A does is *penalize* loud names
    # so the ranking favors less-noisy ones; the snippets next to each lead show
    # what coverage exists so the desk can judge overreaction vs justified.
    setting_a_top = _render_setting(
        "A (attention as filter — noisy names penalized)",
        SETTING_A_WEIGHTS,
        "comp_a30",
        "Attention is weighted into the rank so loud names get pulled down. Read the snippets to see what coverage exists."
    )

    # ---------- Setting B (alt — quality-faller thesis) ----------
    setting_b_top = _render_setting(
        "B (attention as tie-break only)",
        SETTING_B_WEIGHTS,
        "comp_a10",
        "Attention barely affects the rank. Use when interested in quality+divergence regardless of coverage."
    )

    # ---------- Fame failures (apply to both settings) ----------
    fame_fails = [r for r in setting_a_top if r.get("fame_flag") == "FAME_FAIL"]
    if fame_fails:
        print("\n" + "▲" * 175)
        print(f"FAME-FAILURE CASES in Setting A top-{args.top} (mcap ≥ ¥{FAME_MARKET_CAP_JPY/1e9:.0f}B AND attn ≤ {FAME_ATTN_CEILING}):")
        print("  Mega-brands the anomaly search reported as thin — almost certainly a search miss.")
        print("  Do NOT present these as 'unnoticed' to a desk.")
        for r in fame_fails:
            mcap = r["market_cap_jpy"]
            print(f"    {r['ticker']:<7} {r['company_name']}  ¥{mcap/1e9:.0f}B  attn={r['attention_score']:+.1f}")
        print("▲" * 175)

    # ---------- Profile C (genuinely-unseen-by-the-market quality growers) ----------
    print("\n" + "█" * 175)
    print(f"PROFILE C — UNSEEN BY THE MARKET, QUALITY GROWERS  |  desk Q: 'is this an under-recognised grower the market hasn't found?'")
    print(f"Important: 'unseen' here means 'unseen by INVESTOR COVERAGE' (attn ≤ 8 AND retail ≤ 2), NOT 'unknown to the public.'")
    print(f"  A famous consumer brand can still be investor-overlooked (e.g. フマキラー — everyone knows the bug spray, but analyst coverage is thin).")
    print(f"  That's still a legitimate mispricing find. Consumer fame ≠ fair price; investor coverage does.")
    print(f"Method: unseen filter → hard quality gate (3-of-3 OP positive, equity ≥30%, 3yr CAGR ≥3%, rev ≥¥3B) → rank by valuation (P/E + P/B sector-pct).")
    print(f"Cheapest of the verified-good AND verified-investor-unseen. Cap: top 5 per sector.")
    print("█" * 175)

    # Build Profile C from global_watchlist
    # First gate: must actually be UNSEEN (low attn + low retail + small/mid cap).
    # This is the gate that was missing in the previous run — without it, a
    # well-covered industrial leader (太平洋セメント, attn +10, ¥398B) and a
    # retail-pumped consumer brand (ブシロード, retail 4) ended up at the top
    # of a "genuinely-unseen" track, contradicting the label.
    # Second gate: strict quality (3-of-3 OP positive etc.) — only verified-good.
    # Then rank by valuation.
    profile_c_pool: list[dict] = []
    profile_c_excluded_by_unseen = 0
    profile_c_excluded_by_quality = 0
    for r in global_watchlist:
        # Unseen gate FIRST
        unseen_ok, unseen_reason = passes_profile_c_unseen_filter(
            r.get("attention_score"),
            r.get("retail_chatter"),
            r.get("market_cap_jpy"),
        )
        if not unseen_ok:
            r["_profile_c_excluded_reason"] = f"unseen filter: {unseen_reason}"
            profile_c_excluded_by_unseen += 1
            continue
        # Quality gate SECOND
        q = r.get("quality") or {}
        if not q.get("data_ok"):
            profile_c_excluded_by_quality += 1
            continue
        latest_rev = _latest_annual_revenue(r["ticker"])
        passed, reason = passes_profile_c_strict_gate(q, latest_rev)
        if not passed:
            r["_profile_c_excluded_reason"] = f"strict quality: {reason}"
            profile_c_excluded_by_quality += 1
            continue
        # Compute valuation
        val = compute_valuation_metrics(r["ticker"])
        if not val.get("data_ok"):
            r["_profile_c_excluded_reason"] = f"valuation: {val.get('reason', '?')}"
            continue
        val["sector_33_name"] = r.get("sector_33_name")
        val["sanity_flag"] = valuation_sanity_flag(val.get("pe_ratio"), val.get("pb_ratio"))
        r["valuation"] = val
        r["latest_annual_revenue_jpy"] = latest_rev
        profile_c_pool.append(r)

    print(f"\nProfile C funnel:")
    print(f"  Started with: {len(global_watchlist)} names across all sectors")
    print(f"  Excluded by UNSEEN filter (attn>8 OR retail>2 OR mcap≥¥200B): {profile_c_excluded_by_unseen}")
    print(f"  Excluded by STRICT QUALITY filter: {profile_c_excluded_by_quality}")

    # Sector-aware valuation ranking
    valuation_rows = [r["valuation"] for r in profile_c_pool]
    val_sector_norms = compute_sector_valuation_norms(valuation_rows)
    val_global_norms = compute_global_valuation_norms(valuation_rows)
    for r in profile_c_pool:
        r["valuation_score"] = score_valuation(r["valuation"], val_sector_norms, val_global_norms)

    # Sort by valuation composite (cheapest of verified-good first), top 5 per sector
    profile_c_pool.sort(key=lambda r: -(r["valuation_score"]["composite_valuation_score"]))
    profile_c_top_per_sector: dict[str, list[dict]] = {}
    for r in profile_c_pool:
        sec = r.get("_sector", "?")
        profile_c_top_per_sector.setdefault(sec, [])
        if len(profile_c_top_per_sector[sec]) < 5:
            profile_c_top_per_sector[sec].append(r)

    print(f"\nProfile C pool size (passed strict gate AND have valuation data): {len(profile_c_pool)}")

    pc_header = (
        f"{'Rk':<4} {'Ticker':<7} {'Company':<22} {'Sector':<14} {'Tier':<5} "
        f"{'Attn':<6} {'Rtl':<4} {'MCap':<8} "
        f"{'Rev¥B':<7} {'CAGR3y%':<8} {'OPmar%':<7} {'EqRat%':<7} "
        f"{'P/E':<6} {'P/B':<6} {'VRank':<6} {'Liq(¥M/d)':<10} {'Flag':<22}"
    )
    for sec in sorted(profile_c_top_per_sector.keys()):
        names = profile_c_top_per_sector[sec]
        if not names:
            continue
        print("\n" + "=" * 195)
        print(f"  Profile C — {sec}  (top {len(names)} cheapest of verified-good AND verified-unseen)")
        print("=" * 195)
        print(pc_header)
        print("-" * 195)
        for i, r in enumerate(names, 1):
            q = r["quality"]
            v = r["valuation"]
            vs = r["valuation_score"]
            rev = r.get("latest_annual_revenue_jpy")
            rev_str = f"¥{rev/1e9:5.1f}B" if rev else "    -"
            liq = r.get("liquidity_jpy_daily")
            liq_str = f"¥{liq/1e6:7.0f}M" if liq else "    -    "
            attn = r.get("attention_score")
            attn_str = f"{attn:+5.1f}" if attn is not None else "  -  "
            retail = r.get("retail_chatter", 0)
            retail_str = str(retail) if retail else " "
            mcap = r.get("market_cap_jpy")
            mcap_str = f"¥{mcap/1e9:5.0f}B" if mcap else "   -  "
            sanity = v.get("sanity_flag") or ""
            print(
                f"{i:<4} {r['ticker']:<7} {r['company_name'][:21]:<22} {sec[:13]:<14} "
                f"{r.get('tier','?'):<5} {attn_str:<6} {retail_str:<4} {mcap_str:<8} "
                f"{rev_str:<7} "
                f"{q['revenue_cagr_3y']:+6.2f}  {q['op_margin_latest']:+5.2f}  "
                f"{q['equity_ratio_latest']:+5.1f}  "
                f"{v['pe_ratio']:5.2f} {v['pb_ratio']:5.2f} "
                f"{vs['composite_valuation_score']:5.1f}  {liq_str:<10} {sanity:<22}"
            )

    # ---------- Save aggregated JSON ----------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = OUT_DIR / f"_sweep_{today}.json"
    out = {
        "screened_at": today,
        "n_sectors": len(runs),
        "totals": {
            "pool_size": total_pool,
            "after_scale_band": total_band,
            "strict_dual_gate_hits": total_strict,
        },
        "per_sector_summary": [
            {
                "sector_33_name": r.get("sector_33_name"),
                "stats": r.get("stats"),
                "top_watchlist": (r.get("watchlist_ranked") or [{}])[0],
            }
            for r in runs
        ],
        "setting_a_weights": SETTING_A_WEIGHTS,
        "setting_b_weights": SETTING_B_WEIGHTS,
        "global_watchlist_setting_a_top": setting_a_top,
        "global_watchlist_setting_b_top": setting_b_top,
        "profile_c_top_per_sector": {
            sec: [
                {
                    "ticker": r["ticker"], "company_name": r["company_name"], "tier": r["tier"],
                    "latest_annual_revenue_jpy": r["latest_annual_revenue_jpy"],
                    "quality": r["quality"], "valuation": r["valuation"],
                    "valuation_score": r["valuation_score"],
                    "liquidity_jpy_daily": r.get("liquidity_jpy_daily"),
                    "stock_move_pct": r.get("stock_move_pct"),
                    "market_cap_jpy": r.get("market_cap_jpy"),
                    "fame_flag": r.get("fame_flag"),
                    "scale_category": r.get("scale_category"),
                    "attention_score": r.get("attention_score"),
                    "retail_chatter": r.get("retail_chatter"),
                    "compliance": r.get("compliance"),
                }
                for r in names
            ]
            for sec, names in profile_c_top_per_sector.items()
        },
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull aggregated sweep saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
