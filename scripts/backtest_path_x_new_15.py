"""Path X: Run existing Bedrock pipeline on 15 NEW info/comm JGAAP tickers
not in our current 45-ticker cohort. Apply Phase 1 vetoes (automatic via
_enrich_pairs_with_confidence). Compare new-cohort precision to existing.

Expected cost: ~$1.50-2.50 (Bedrock Sonnet 4.6, ~25-40 LLM calls).
Wall time: ~25-40 minutes.

NO Claude API calls — Bedrock only. Per user directive.
"""
from __future__ import annotations
import json
import os
import sys
import io
import time
import math
import subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(dotenv_path=ROOT / ".env")

from app.subagents.quiet_change import analyze_company_multi_year  # noqa: E402
from app.tools.bedrock import get_usage_stats, reset_usage_stats  # noqa: E402

# 15 NEW info/comm JGAAP tickers — all locally cached, none in current cohort.
# Sub-sector mix: broadcasters, IT services, entertainment, weather-data, streaming.
TICKERS = [
    "4825",  # Weathernews
    "5032",  # ANYCOLOR (VTuber)
    "7595",  # Argo Graphics
    "7860",  # Avex
    "9409",  # TV Asahi HD
    "9412",  # SKY Perfect JSAT
    "9413",  # TV Tokyo HD
    "9416",  # Vision
    "9418",  # U-NEXT HOLDINGS
    "9601",  # Shochiku
    "9605",  # Toei
    "9682",  # DTS
    "9692",  # CEC
    "9746",  # TKC
    "9889",  # JBCC HD
]


def _wilson(hits, n, z=1.96):
    if n == 0: return (None, None)
    p = hits/n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    r = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den
    return (max(0.0,(c-r)*100), min(100.0,(c+r)*100))


def _f(v):
    if v is None: return None
    try: return float(v)
    except: return None


def annual_val(items, key, fy):
    matches = [i for i in items if i["line_item_key"]==key and i["fiscal_year"]==fy
               and i.get("fiscal_quarter") is None and i.get("accounting_standard")=="Japan GAAP"]
    if not matches: return None
    return _f(matches[0]["value"])


def _ni_usable_for_threshold(prev_ni, current_revenue):
    """NI denominator is meaningless when prev NI <= 0 or tiny vs revenue.
    Correctness patch 2026-05-21."""
    if prev_ni is None or prev_ni <= 0:
        return False
    if current_revenue and current_revenue > 0:
        if abs(prev_ni) < 0.005 * current_revenue:
            return False
    return True


def detect_adverse_events(ticker, outcome_fy):
    """Lenient methodology event detector — mirrors lenient_outcome_scoring.py.

    NI-zero correctness patch applied: only use NI-based threshold when
    prior-year NI is positive AND >= 0.5% of current revenue.
    """
    p = ROOT / "data" / "tempest" / ticker / "financials_line_items.json"
    if not p.exists(): return False
    with open(p, encoding="utf-8") as f:
        items = json.load(f)["data"]
    for fy in (outcome_fy, outcome_fy + 1):
        prev_eq = annual_val(items, "total_equity", fy - 1)
        prev_ni = (annual_val(items, "profit_loss", fy - 1)
                   or annual_val(items, "profit_attributable_to_owners_of_parent", fy - 1))
        rev = annual_val(items, "net_sales", fy)
        ni_usable = _ni_usable_for_threshold(prev_ni, rev)
        impair = annual_val(items, "impairment_loss", fy)
        if impair and impair > 0:
            equity_leg = (prev_eq and prev_eq > 0 and impair/prev_eq*100 >= 1.0)
            ni_leg = (ni_usable and impair/abs(prev_ni)*100 >= 5.0)
            if equity_leg or ni_leg:
                return True
        extra = annual_val(items, "extraordinary_loss", fy)
        if extra and extra > 0:
            rev_leg = (rev and rev > 0 and extra/rev*100 >= 5.0)
            ni_leg = (ni_usable and extra/abs(prev_ni)*100 >= 10.0)
            if rev_leg or ni_leg:
                return True
    return False


def lenient_outcome(rev_yoy, op_yoy, stock_5d, has_bad):
    """PRE-REGISTERED in outputs/lenient_outcome_methodology.md."""
    pos = neg = 0
    if rev_yoy is not None:
        if rev_yoy >= 3.0: pos += 1
        elif rev_yoy <= -3.0: neg += 1
    if op_yoy is not None:
        if op_yoy >= 5.0: pos += 1
        elif op_yoy <= -5.0: neg += 1
    if stock_5d is not None:
        if stock_5d >= 5.0: pos += 1
        elif stock_5d <= -5.0: neg += 1
    if has_bad: return "negative"
    if neg >= 1:
        return "mixed" if pos >= 1 else "negative"
    if pos >= 1: return "positive"
    return "mixed"


def score_prediction(verdict, outcome):
    if verdict == "uncertain": return "abstain"
    if verdict == "growth_likely" and outcome == "positive": return "hit"
    if verdict == "growth_unlikely" and outcome == "negative": return "hit"
    return "miss"


def fetch_tempest_data(tickers: list[str]) -> None:
    """Refresh Tempest data (uses local cache if < 168h old)."""
    print(f"[step 1] Tempest data refresh for {len(tickers)} tickers (cache-friendly)…",
          flush=True)
    cmd = [sys.executable, str(ROOT / "fetch_tempest.py"),
           "--tickers", ",".join(tickers),
           "--max-age-hours", "168"]
    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=300)
        if result.stdout: print(result.stdout[-2000:], flush=True)
        if result.returncode != 0:
            print(f"  ⚠️  fetch_tempest exited {result.returncode}", flush=True)
            if result.stderr: print(f"  STDERR: {result.stderr[-1000:]}", flush=True)
    except FileNotFoundError:
        print("  ⚠️  fetch_tempest.py not found — relying on existing local cache", flush=True)
    except subprocess.TimeoutExpired:
        print("  ⚠️  Tempest fetch timed out — relying on local cache", flush=True)
    print(f"  fetch step done in {time.time()-t0:.1f}s\n", flush=True)


def main() -> int:
    print("=" * 100, flush=True)
    print(f"PATH X — 15 NEW info/comm JGAAP tickers (Bedrock only, no Claude API)", flush=True)
    print("=" * 100, flush=True)
    print(f"Tickers: {TICKERS}", flush=True)
    print(f"Bedrock model: {os.environ.get('BEDROCK_MODEL_ID', 'default')}\n", flush=True)

    reset_usage_stats()
    fetch_tempest_data(TICKERS)

    print("[step 2] Running quiet_change agent on each ticker…\n", flush=True)
    results: dict[str, dict] = {}
    t0 = time.time()
    prev_cost = 0.0
    prev_calls = 0
    for i, code in enumerate(TICKERS, 1):
        print(f"  [{i}/{len(TICKERS)}] {code}: running…", end="", flush=True)
        ts = time.time()
        try:
            r = analyze_company_multi_year(
                code, min_year=2020, run_tests=False,
                skip_simplify=True,
                decision_cutoff_fy=None,
                use_cache=True,
                use_prompt_caching=False,
            )
            n_real = len([p for p in r.get("pairs", []) if not p.get("history_only")])
            stats = get_usage_stats()
            delta_cost = stats["estimated_cost_usd"] - prev_cost
            delta_calls = stats["call_count"] - prev_calls
            prev_cost = stats["estimated_cost_usd"]
            prev_calls = stats["call_count"]
            print(f" ok ({n_real} pair(s), {time.time()-ts:.1f}s, "
                  f"+{delta_calls} calls, +${delta_cost:.3f}, total ${stats['estimated_cost_usd']:.3f})",
                  flush=True)
        except Exception as e:
            print(f" CRASHED: {type(e).__name__}: {e}", flush=True)
            r = {"error": str(e)}
        results[code] = r
    print(f"\n  total wall time: {time.time()-t0:.1f}s\n", flush=True)

    final_stats = get_usage_stats()
    print("=" * 100, flush=True)
    print(f"FINAL COST: ${final_stats['estimated_cost_usd']:.3f}  "
          f"({final_stats['call_count']} Bedrock calls, "
          f"{final_stats['input_tokens']:,} input, {final_stats['output_tokens']:,} output tokens)",
          flush=True)
    print("=" * 100, flush=True)

    # ====================================================================
    # Step 3: score predictions with lenient outcome metric + Phase 1 vetoes
    # ====================================================================
    print("\n[step 3] Scoring predictions (lenient outcome, Phase 1 vetoes auto-applied)…",
          flush=True)
    scored = []
    for code in TICKERS:
        r = results.get(code, {})
        if "error" in r: continue
        # Already-enriched pairs: outlook_judgment is post-veto, original_judgment is pre-veto
        pairs = [p for p in r.get("pairs", []) if not p.get("history_only")]
        pairs.sort(key=lambda p: p.get("curr_period_end") or "")
        for i in range(len(pairs) - 1):
            pred = pairs[i]
            outcome_pair = pairs[i + 1]
            pred_fy = pred.get("curr_fiscal_year")
            outcome_fy = outcome_pair.get("curr_fiscal_year")
            pred_label = f"FY{pred.get('prev_fiscal_year')}->FY{pred_fy}"
            outcome_label = f"FY{outcome_pair.get('prev_fiscal_year')}->FY{outcome_fy}"
            llm_raw = pred.get("original_judgment", pred.get("outlook_judgment"))
            post_veto = pred.get("outlook_judgment")
            veto_rule = pred.get("veto_rule")
            rev_d = outcome_pair.get("revenue_delta_pct")
            stock = outcome_pair.get("stock_5d_return_pct")
            op_d = outcome_pair.get("op_profit_delta_pct")
            has_bad = detect_adverse_events(code, outcome_fy) if outcome_fy else False
            outcome = lenient_outcome(rev_d, op_d, stock, has_bad)
            scored.append({
                "ticker": code,
                "prediction_pair": pred_label,
                "outcome_pair": outcome_label,
                "llm_raw_verdict": llm_raw,
                "post_veto_verdict": post_veto,
                "veto_rule": veto_rule,
                "outcome_lenient": outcome,
                "llm_raw_score": score_prediction(llm_raw, outcome),
                "post_veto_score": score_prediction(post_veto, outcome),
                "rev_yoy_outcome": rev_d,
                "op_yoy_outcome": op_d,
                "stock_5d_outcome": stock,
                "has_adverse_event": has_bad,
            })

    # ====================================================================
    # Step 4: scoreboard
    # ====================================================================
    print(f"  Total predictions scored: {len(scored)}\n", flush=True)
    print("=" * 100, flush=True)
    print("PATH X RESULTS — new 15-ticker cohort", flush=True)
    print("=" * 100, flush=True)
    for stage_label, verdict_key, score_key in [
        ("LLM raw (no vetoes)", "llm_raw_verdict", "llm_raw_score"),
        ("Phase 1 (vetoes)",    "post_veto_verdict", "post_veto_score"),
    ]:
        print(f"\n  {stage_label}:")
        for cls in ("growth_likely", "growth_unlikely"):
            sub = [r for r in scored if r[verdict_key] == cls]
            h = sum(1 for r in sub if r[score_key] == "hit")
            m = sum(1 for r in sub if r[score_key] == "miss")
            c = h + m
            p = h/c*100 if c else None
            ci = _wilson(h, c)
            if p is not None:
                print(f"    {cls:<17} {h}/{c} = {p:5.1f}%  CI[{ci[0]:.0f}-{ci[1]:.0f}]")
            else:
                print(f"    {cls:<17} (no confident calls)")
        # Total
        sub_all = [r for r in scored if r[verdict_key] in ("growth_likely", "growth_unlikely")]
        h = sum(1 for r in sub_all if r[score_key] == "hit")
        m = sum(1 for r in sub_all if r[score_key] == "miss")
        c = h + m
        p = h/c*100 if c else None
        ci = _wilson(h, c)
        if p is not None:
            print(f"    {'ALL CONFIDENT':<17} {h}/{c} = {p:5.1f}%  CI[{ci[0]:.0f}-{ci[1]:.0f}]")
        abstain = sum(1 for r in scored if r[verdict_key] == "uncertain")
        print(f"    {'abstain':<17} {abstain}")

    # Veto firing detail
    print(f"\n  Veto firings on new cohort:", flush=True)
    from collections import Counter
    rule_counts = Counter(r["veto_rule"] for r in scored if r["veto_rule"])
    if not rule_counts:
        print("    (no vetoes fired)")
    for rule, n in rule_counts.most_common():
        print(f"    {rule}: {n}")

    out_path = ROOT / "outputs" / "path_x_new_15_results.json"
    out_path.write_text(json.dumps({
        "tickers": TICKERS,
        "methodology": "lenient_outcome, Phase 1 vetoes auto-applied via _enrich_pairs_with_confidence",
        "n_predictions": len(scored),
        "scored_predictions": scored,
        "final_usage_stats": final_stats,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
