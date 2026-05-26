"""静かな変化 agent — segment-driven YoY revenue analysis on EDINET annual
securities reports (有価証券報告書), with a 5-trading-day post-filing stock
direction.

For each input company code we:
  1. Take the YoY pair of annual reports already resolved by edinet_loader.
  2. Compare current vs previous total revenue → profit / loss / flat.
  3. Extract the segment-revenue table from both ZIPs and join on segment
     name to produce per-segment YoY deltas.
  4. Ask the LLM to write a one-paragraph explanation grounded in the
     segment deltas plus the report's qualitative narrative.
  5. Look up close prices for the 5 trading days after the filing date and
     classify the move as positive / negative / unchanged with the % move.
"""
from __future__ import annotations
import hashlib
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import CONFIG, ROOT
# Source switch (2026-05-10): the agent now reads pre-parsed financials,
# segments, balance-sheet line items, MD&A text, and daily prices from the
# cached TempestAI Finance API JSON instead of opening EDINET XBRL zips
# and calling yfinance live. tempest_loader and the (now Tempest-backed)
# prices module preserve the same function signatures, so the rest of
# this file is unchanged.
from app.ingest.tempest_loader import (
    detect_revenue_scope,
    extract_operating_profit_from_zip_path,
    extract_revenue_from_zip_path,
    extract_revenue_history_from_zip_path,
    load_asr_series,
    load_quarterly_series,
    make_quarterly_yoy_pairs,
    extract_balance_sheet_from_zip_path,
    extract_pl_from_zip_path,
    extract_cashflow_from_zip_path,
    extract_segments,
    extract_text_section_from_zip_path,
    SECTION_BUSINESS_RISKS,
    SECTION_CORPORATE_GOVERNANCE,
)
from app.ingest import prices
import json as _json
import re as _re

from app.subagents.quiet_change_prompt import (
    build_advanced_prompt,
    build_advanced_v2,      # cacheable (system, user) split for Anthropic prompt caching
    build_simplify_prompt,
    build_prompt,           # backward-compat alias for any straggling caller
)
from app.tools.bedrock import invoke_text
from app.tools.jpx_industries import lookup as _jpx_lookup


# Lever 3 (added 2026-05-11) — sector cyclicality guidance map.
# Maps JPX 33業種 sector code → (JA name, EN name, prompt guidance).
# Only sectors with KNOWN cyclicality patterns are listed; companies in
# other sectors get no industry block (empty string from the prompt builder).
# Targeted at the cluster failure modes from the backtest:
#   - 3650 (semis: Advantest, Tokyo Electron, etc.) — chip cycle
#   - 3300 (chemicals: Shin-Etsu, etc.) — materials cycle
#   - 3700 (autos: Toyota, Honda) — supply chain + chip cycle
_CYCLICAL_SECTORS_MAP: dict[str, tuple[str, str, str]] = {
    "3650": (
        "電気機器", "Electric Machinery",
        "This is a CYCLICAL sector — semiconductor, electronics-equipment, "
        "and end-product cycles span 2-3 years. Single-year margin compression "
        "in this sector commonly REVERSES on the next cycle turn. Favor "
        "'uncertain' over 'growth_unlikely' when only the current pair shows "
        "compression and the prior year was healthy. Only call 'growth_unlikely' "
        "if margin has been declining for 2+ consecutive years OR a structural "
        "issue (e.g., loss of major customer, technology obsolescence) is named "
        "in the narrative.",
    ),
    "3700": (
        "輸送用機器", "Transport Equipment",
        "This is a CYCLICAL sector — auto industry margins swing on chip "
        "availability, raw material costs, and FX. Single-year margin "
        "compression often reverses within 1-2 years. Favor 'uncertain' over "
        "'growth_unlikely' for one-year compression unless the narrative names "
        "a structural cause (e.g., EV-transition demand collapse).",
    ),
    "3200": (
        "化学", "Chemicals",
        "This is a CYCLICAL sector — chemicals margins move with the materials "
        "cycle (raw inputs, end-market demand). Single-year compression often "
        "reverses on cycle turn. Favor 'uncertain' over 'growth_unlikely' for "
        "one-year dips.",
    ),
    "3300": (
        "石油・石炭製品", "Petroleum & Coal Products",
        "This is a CYCLICAL commodity sector — oil and coal product margins "
        "swing with crude prices and refinery spreads. Single-year compression "
        "commonly reverses. Favor 'uncertain' over 'growth_unlikely' for "
        "one-year dips.",
    ),
    "3500": (
        "鉄鋼", "Steel",
        "This is a CYCLICAL sector — steel industry depends on raw material "
        "costs and global infrastructure demand. Single-year compression "
        "commonly reverses. Favor 'uncertain' over 'growth_unlikely' for "
        "one-year dips.",
    ),
    "5050": (
        "鉱業", "Mining",
        "This is a CYCLICAL commodity-price sector. Single-year compression "
        "commonly reverses on commodity turn. Favor 'uncertain' over "
        "'growth_unlikely' for one-year dips.",
    ),
    "5100": (
        "海運業", "Marine Transportation",
        "This is a CYCLICAL freight-rate sector. Single-year compression often "
        "reverses on shipping-rate turn. Favor 'uncertain' over 'growth_unlikely' "
        "for one-year dips.",
    ),
}


def _build_industry_context_for_code(code: str) -> str | None:
    """Look up a 4-digit ticker's JPX 33業種 sector and return the cyclicality
    guidance block — or None if the sector isn't on the cyclical list (most
    companies). Pure function, just a dict lookup."""
    rec = _jpx_lookup(code)
    if rec is None:
        return None
    info = _CYCLICAL_SECTORS_MAP.get(rec.code33)
    if info is None:
        return None
    name_ja, name_en, guidance = info
    return (
        f"INDUSTRY CONTEXT (cyclicality guidance for sector {rec.code33} "
        f"{name_ja} / {name_en}):\n  {guidance}"
    )


_EMPTY_EXPLANATIONS = {
    "explanation_simple_en": "",
    "explanation_simple_ja": "",
    "explanation_advanced_en": "",
    "explanation_advanced_ja": "",
    "outlook_judgment": "uncertain",
    "outlook_reason_en": "",
    "outlook_reason_ja": "",
}

# Allowed outlook judgment values. Anything else from the LLM gets coerced
# to "uncertain" so downstream filtering code can rely on the enum.
_VALID_OUTLOOK_JUDGMENTS = frozenset({"growth_likely", "growth_unlikely", "uncertain"})


def _extract_balanced_json(raw: str) -> dict | None:
    """Walk `raw`, find every balanced `{...}` block, and return the LAST one
    that parses successfully AND contains an `explanation_en` key. Robust to
    preambles, trailing commentary, and nested braces inside string values.

    The model is instructed to emit ONLY the JSON, but occasionally narrates
    its checklist or apologises before/after the JSON. A naive greedy
    `{.*}` match would grab from the first stray brace in the preamble to
    the last brace in the JSON, producing invalid input.
    """
    cleaned = _re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=_re.MULTILINE)

    candidates: list[str] = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(cleaned):
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidates.append(cleaned[start:i + 1])
                    start = -1

    for cand in reversed(candidates):
        try:
            parsed = _json.loads(cand)
        except _json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "explanation_en" in parsed:
            return parsed
    return None


def _parse_bilingual_pair(raw: str) -> tuple[str, str]:
    """Backward-compat 2-tuple parser used by the simplify call.

    The simplify prompt still returns the original {explanation_en, explanation_ja}
    shape (no stock_reaction split) because its job is to rewrite already-combined
    text. Returns (raw, "") if no valid JSON is found — same fallback as before.
    """
    parsed = _extract_balanced_json(raw)
    if parsed is None:
        return raw, ""
    return parsed.get("explanation_en", ""), parsed.get("explanation_ja", "")


def _parse_advanced_septet(raw: str) -> tuple[str, str, str, str, str, str, str]:
    """Parse the seven required fields from the advanced LLM reply:
    (explanation_en, explanation_ja, stock_reaction_en, stock_reaction_ja,
     outlook_judgment, outlook_reason_en, outlook_reason_ja).

    Returns ("", "", "", "", "uncertain", "", "") with explanation_en
    fallback-set to `raw` when the JSON envelope is missing entirely (so
    the user still sees something rather than a blank pane).

    Missing individual fields default to empty strings; outlook_judgment
    that isn't one of the three valid enum values is coerced to 'uncertain'
    so downstream filtering can rely on the enum.
    """
    parsed = _extract_balanced_json(raw)
    if parsed is None:
        return raw, "", "", "", "uncertain", "", ""
    judgment = (parsed.get("outlook_judgment") or "uncertain").strip().lower()
    if judgment not in _VALID_OUTLOOK_JUDGMENTS:
        judgment = "uncertain"
    return (
        parsed.get("explanation_en", ""),
        parsed.get("explanation_ja", ""),
        parsed.get("stock_reaction_en", ""),
        parsed.get("stock_reaction_ja", ""),
        judgment,
        parsed.get("outlook_reason_en", ""),
        parsed.get("outlook_reason_ja", ""),
    )


# Backward-compat alias for any caller still importing the old name.
def _parse_advanced_quad(raw: str) -> tuple[str, str, str, str]:
    expl_en, expl_ja, stk_en, stk_ja, _, _, _ = _parse_advanced_septet(raw)
    return expl_en, expl_ja, stk_en, stk_ja


def _combine_advanced_text(outlook_reason: str, explanation: str,
                           stock_reaction: str) -> str:
    """Concatenate outlook + explanation + stock-reaction in display order.

    The split-into-fields design exists so each part survives prompt-budget
    pressure independently. Downstream consumers see one unified block — the
    outlook leads (it's the agent's headline filter signal), the
    non-table-visible explanation context comes second, and the past-stock
    reaction closes. Single space separators are enough — each piece is
    well-formed prose.
    """
    parts = [
        (outlook_reason or "").strip(),
        (explanation or "").strip(),
        (stock_reaction or "").strip(),
    ]
    return " ".join(p for p in parts if p)


def _combine_explanation_with_stock(explanation: str, stock_reaction: str) -> str:
    """Concatenate the explanation body with the dedicated stock-reaction
    paragraph. The split-into-fields design exists to GUARANTEE the stock
    paragraph survives even when the LLM's prose budget is tight — this
    function is what makes the split invisible to downstream consumers.

    Returns just `explanation` when `stock_reaction` is empty (rare —
    happens only when stock data was n/a or the LLM disobeyed and left
    the field blank, in which case the new coverage rule warns).
    """
    expl = (explanation or "").strip()
    stock = (stock_reaction or "").strip()
    if not stock:
        return expl
    if not expl:
        return stock
    # Single space separator is enough — both halves are well-formed prose.
    return f"{expl} {stock}"


def _explain_bilingual(advanced_prompt: str, skip_simplify: bool = True,
                       system_prompt: str | None = None) -> dict:
    """Two-call pipeline:
      1. Advanced (analyst-grade) explanation, bilingual.
         The advanced LLM returns FOUR fields:
           explanation_{en,ja}      — composition + drivers + scope note
           stock_reaction_{en,ja}   — dedicated stock-direction paragraph
         The split exists so the stock-reaction sentences cannot be silently
         dropped under prompt-budget pressure. The fields are concatenated
         here into the final advanced text — downstream consumers see the
         original unified shape.
      2. Simplify the (already-combined) advanced English into a layman
         version, bilingual. Simplify's source text always contains the
         stock paragraph because we've concatenated it before passing.

    Two smaller calls instead of one large four-paragraph call → no
    truncation, and Simple is GUARANTEED to exist whenever Advanced does.
    A failure in step 2 leaves only the simple fields empty.
    """
    out = dict(_EMPTY_EXPLANATIONS)

    # Step 1 — advanced. Asks for 7 fields.
    try:
        # 4500 (was 3500) — adding the outlook_judgment + bilingual
        # outlook_reason fields adds roughly another 4-6 sentences worth
        # of output. 4500 leaves headroom for mega-cap filings where the
        # outlook reasoning + macro framing can run long in Japanese.
        # When system_prompt is provided (V2 path), it is sent as a
        # cache-marked Anthropic system block; advanced_prompt becomes
        # the per-company user message.
        adv_raw = invoke_text(advanced_prompt, max_tokens=4500,
                              system_prompt=system_prompt)
    except Exception as e:
        log.warning("advanced LLM call failed: %s", e)
        return out
    (expl_en, expl_ja, stock_en, stock_ja,
     outlook_judgment, outlook_en, outlook_ja) = _parse_advanced_septet(adv_raw)
    final_adv_en = _combine_advanced_text(outlook_en, expl_en, stock_en)
    final_adv_ja = _combine_advanced_text(outlook_ja, expl_ja, stock_ja)
    out["explanation_advanced_en"] = final_adv_en
    out["explanation_advanced_ja"] = final_adv_ja
    out["outlook_judgment"] = outlook_judgment
    out["outlook_reason_en"] = outlook_en
    out["outlook_reason_ja"] = outlook_ja

    # Step 2 — simplify (skip if step 1 produced no English text,
    # OR if caller passed skip_simplify=True for backtest cost-savings).
    # Simplify is purely a UI rewrite layer; the outlook_judgment field
    # used for scoring is already populated from Step 1. Backtest mode
    # cuts LLM calls per pair from 2 → 1 (50% saving) by skipping this.
    if not final_adv_en or skip_simplify:
        return out
    try:
        # 1500 (was 900) — combined advanced now runs 9-13 sentences
        # (2-3 outlook + 1-3 explanation + 3-5 stock-reaction). The
        # simplified bilingual rewrite stays in the 3-5 sentence range
        # but needs headroom for JA.
        simp_raw = invoke_text(build_simplify_prompt(final_adv_en), max_tokens=1500)
    except Exception as e:
        log.warning("simplify LLM call failed: %s", e)
        return out
    simp_en, simp_ja = _parse_bilingual_pair(simp_raw)
    out["explanation_simple_en"] = simp_en
    out["explanation_simple_ja"] = simp_ja
    return out

log = logging.getLogger(__name__)

ANNUAL_FILING_TYPE = "edinet_asr"   # 有価証券報告書


def _classify_revenue(prev: float, curr: float) -> tuple[str, float]:
    if prev <= 0:
        return ("flat", 0.0)
    delta_pct = (curr - prev) / prev * 100.0
    if delta_pct > 0:
        return ("profit", delta_pct)
    if delta_pct < 0:
        return ("loss", delta_pct)
    return ("flat", 0.0)


def _op_profit_yoy(prev_zip: Path, curr_zip: Path) -> tuple[float | None, float | None, float | None]:
    """Pull operating profit from both ZIPs and compute YoY %.

    Returns (prev_op, curr_op, op_delta_pct). Any of the three may be None
    when the filer doesn't expose an op-profit tag (some pure-JGAAP filings)
    or when prev is zero (delta undefined).
    """
    prev_op = extract_operating_profit_from_zip_path(prev_zip)
    curr_op = extract_operating_profit_from_zip_path(curr_zip)
    if prev_op is None or curr_op is None:
        return prev_op, curr_op, None
    if prev_op == 0:
        return prev_op, curr_op, None
    return prev_op, curr_op, (curr_op - prev_op) / abs(prev_op) * 100.0


# Thresholds for the graded stock-response classification.
#
# The original divergence flag only fired when operating-profit and stock
# moved in opposite directions. But the user's actual mental model of the
# agent is broader: "profit went up but stock barely moved" is equally
# interesting (it's the under-reaction case the Lazy Prices research is
# actually about). The classification below captures both:
#
#   - divergence    : signs disagree (the original case)
#   - weak_response : same direction but stock magnitude is much smaller
#                     than profit magnitude — investors under-reacted
#                     relative to what the headline profit would suggest
#   - aligned       : profit and stock moved together, in proportion
#   - n/a           : missing data or both flat
#
# weak_response thresholds (tuned to avoid false positives):
#   - profit must have moved at least 5% YoY (avoid noise on flat profit)
#   - stock magnitude must be less than 30% of profit magnitude
#   - same sign required (otherwise it's divergence, not weak)
_WEAK_RESPONSE_PROFIT_THRESHOLD_PCT = 5.0
_WEAK_RESPONSE_STOCK_PROFIT_RATIO = 0.30
_DIVERGENCE_FLAT_THRESHOLD_PCT = 0.5


def _stock_response_class(op_delta_pct: float | None,
                          stock_pct: float | None,
                          revenue_delta_pct: float | None = None) -> str:
    """Classify the relationship between the company's headline result
    (operating-profit OR revenue YoY, whichever moved more) and the
    5-trading-day post-filing stock return.

    Returns one of:
      - "divergence"    : signs disagree, both ≥ 0.5%
      - "weak_response" : signs agree but stock << headline (Lazy Prices
                          under-reaction — company moved meaningfully but
                          stock barely budged in the same direction)
      - "aligned"       : signs agree and stock magnitude is proportional
      - "n/a"           : missing data or both essentially flat

    The "headline" is the LARGER absolute mover of (op_delta, revenue_delta).
    Operating profit is the analyst-grade signal but isn't reliably
    extracted for every filer-year (US-GAAP→IFRS transitions, JGAAP filers
    that don't expose the standard tag). Revenue fills the gap — and also
    matches the lay-investor reading of "company is creating profit"
    (which often conflates revenue and operating profit).

    Examples:
      op +12%, rev +5%, stock +1%   → headline=12, ratio=0.08 → weak_response
      op None, rev +9%, stock +1.2% → headline=9,  ratio=0.13 → weak_response
      op +0%,  rev +10%, stock -6%  → headline=10, signs disagree → divergence
      op +20%, rev +10%, stock +6%  → headline=20, ratio=0.30 → aligned
    """
    if stock_pct is None:
        return "n/a"
    candidates = [v for v in (op_delta_pct, revenue_delta_pct) if v is not None]
    if not candidates:
        return "n/a"
    headline = max(candidates, key=abs)

    if abs(headline) < _DIVERGENCE_FLAT_THRESHOLD_PCT and abs(stock_pct) < _DIVERGENCE_FLAT_THRESHOLD_PCT:
        return "n/a"
    # Sign disagreement is divergence.
    if abs(headline) >= _DIVERGENCE_FLAT_THRESHOLD_PCT and abs(stock_pct) >= _DIVERGENCE_FLAT_THRESHOLD_PCT:
        if (headline > 0) != (stock_pct > 0):
            return "divergence"
    # Same direction. Check for under-reaction.
    if abs(headline) >= _WEAK_RESPONSE_PROFIT_THRESHOLD_PCT:
        if abs(stock_pct) < abs(headline) * _WEAK_RESPONSE_STOCK_PROFIT_RATIO:
            return "weak_response"
    return "aligned"


def _divergence_flag(op_delta_pct: float | None, stock_pct: float | None) -> bool:
    """Backward-compat wrapper around _stock_response_class.

    Returns True iff operating-profit and stock direction strictly disagree.
    Existing call sites that only care about sign-disagreement (the
    original DIVERGENCE-FLAG semantics) continue to work unchanged.
    The new weak_response case is surfaced separately via _is_response_anomaly.
    """
    return _stock_response_class(op_delta_pct, stock_pct) == "divergence"


def _is_response_anomaly(op_delta_pct: float | None, stock_pct: float | None) -> bool:
    """True iff the stock response is an anomaly — either sign disagreement
    (divergence) OR same-direction under-reaction (weak_response).

    Both cases trigger the prompt's hedged-reconciliation rule and the
    post-check coverage warning. This is the broader screening signal
    that maps to the user's "profit up, stock not increasing or barely
    increasing" intuition.
    """
    return _stock_response_class(op_delta_pct, stock_pct) in ("divergence", "weak_response")


# Materiality thresholds for asterisking BS movers. The block is ALWAYS
# injected (per locked-in plan choice), but movers get a `*` so the LLM
# knows which items to reason about. We deliberately keep the bar high —
# normal year-over-year balance-sheet drift (a few % on a major line)
# should NOT be flagged, because the prompt's BS DISCIPLINE rule allows
# the LLM to cite asterisked items as divergence reasons; flagging too
# many gives it too many valid hooks and lets it pick anything that
# vaguely matches the explanation it wanted to write.
#
#   - abs(delta_pct) >= 15%                               → mover
#   - abs(delta_pct) >= 10% AND >= 2% of total assets     → mover
#     (catches double-digit moves on big balances; the assets gate keeps
#      tiny line items from triggering on swings the LLM shouldn't reason
#      about)
#   - impairment_loss > 0                                 → mover
#     (any positive writedown is by definition a divergence candidate)
_BS_MOVER_PCT_THRESHOLD = 15.0
_BS_MOVER_PCT_MINOR_THRESHOLD = 10.0
_BS_MOVER_ASSETS_THRESHOLD = 2.0


def _bs_yoy(prev_zip: Path, curr_zip: Path) -> dict:
    """Pull BS panels from prev + curr ZIPs and compute YoY deltas.

    Returns:
        {
          "items": {key: {prev, curr, delta_pct, pct_of_assets_curr, is_mover, framework_changed}},
          "framework_prev": str, "framework_curr": str, "framework_changed": bool,
          "prev_missing": [...], "curr_missing": [...],
        }

    `delta_pct` is None when prev is missing/zero or curr is missing.
    `pct_of_assets_curr` is None when total_assets_curr is missing.
    `framework_changed` is True for items where prev/curr come from different
    frameworks — those YoY deltas are apples-to-oranges and the prompt
    builder will render `n/a (framework changed)` instead of a delta.

    Pure function — never raises; bad ZIPs return empty dicts and the
    prompt builder degrades gracefully to an "BS data unavailable" line.
    """
    prev_bs = extract_balance_sheet_from_zip_path(prev_zip)
    curr_bs = extract_balance_sheet_from_zip_path(curr_zip)
    prev_items = prev_bs.get("items", {})
    curr_items = curr_bs.get("items", {})
    prev_fw = prev_bs.get("framework", "unknown")
    curr_fw = curr_bs.get("framework", "unknown")
    framework_changed = (
        prev_fw != "unknown" and curr_fw != "unknown" and prev_fw != curr_fw
    )

    total_assets_curr = curr_items.get("total_assets")

    all_keys = set(prev_items) | set(curr_items)
    items_out: dict[str, dict] = {}
    for key in all_keys:
        prev = prev_items.get(key)
        curr = curr_items.get(key)
        delta_pct: float | None = None
        if prev is not None and curr is not None and prev != 0 and not framework_changed:
            delta_pct = (curr - prev) / abs(prev) * 100.0
        pct_of_assets_curr: float | None = None
        if curr is not None and total_assets_curr and total_assets_curr != 0:
            pct_of_assets_curr = abs(curr) / total_assets_curr * 100.0

        is_mover = False
        if delta_pct is not None and abs(delta_pct) >= _BS_MOVER_PCT_THRESHOLD:
            is_mover = True
        elif (
            delta_pct is not None
            and pct_of_assets_curr is not None
            and abs(delta_pct) >= _BS_MOVER_PCT_MINOR_THRESHOLD
            and pct_of_assets_curr >= _BS_MOVER_ASSETS_THRESHOLD
        ):
            # Double-digit YoY on a balance that's at least 2% of total
            # assets — a meaningful move on a meaningful line. Smaller
            # single-digit moves are normal balance-sheet drift; flagging
            # them would give the LLM too many divergence candidates.
            is_mover = True
        if key == "impairment_loss" and curr is not None and curr > 0:
            is_mover = True

        items_out[key] = {
            "prev": prev,
            "curr": curr,
            "delta_pct": delta_pct,
            "pct_of_assets_curr": pct_of_assets_curr,
            "is_mover": is_mover,
            "framework_changed": framework_changed,
        }

    return {
        "items": items_out,
        "framework_prev": prev_fw,
        "framework_curr": curr_fw,
        "framework_changed": framework_changed,
        "prev_missing": prev_bs.get("missing", []),
        "curr_missing": curr_bs.get("missing", []),
    }


# Materiality thresholds for asterisking P/L movers. Same spirit as the BS
# rules but tuned for income-statement scale: net-income swings are routinely
# wider than balance-sheet drift, so the % bar is higher.
#   - abs(YoY %) >= 25  → mover (income lines often swing ±20% in normal years)
#   - abs(margin pp delta) >= 1.5  → mover (a 150bp margin move is meaningful)
#   - net_income flipped sign (loss in either year) → mover unconditionally
_PL_MOVER_PCT_THRESHOLD = 25.0
_PL_MOVER_MARGIN_PP_THRESHOLD = 1.5


def _pl_yoy(prev_zip: Path, curr_zip: Path) -> dict:
    """Pull P/L panels from prev + curr ZIPs and compute YoY deltas + margin
    point-changes.

    Returns:
        {
          "items": {key: {prev, curr, delta_pct, is_mover}},
          "margins": {margin_key: {prev, curr, pp_delta, is_mover}},
          "prev_missing": [...], "curr_missing": [...],
        }

    `delta_pct` is None when prev is missing/zero or curr is missing.
    `pp_delta` is the percentage-point change in the margin (curr_pct − prev_pct).
    `is_mover` flags items the LLM should reason about; non-movers are still
    rendered for context but should not be cited as a primary driver.

    Pure function. Bad ZIPs return empty dicts; downstream prompt builder
    degrades to "P/L data unavailable".
    """
    prev_pl = extract_pl_from_zip_path(prev_zip)
    curr_pl = extract_pl_from_zip_path(curr_zip)
    prev_items = prev_pl.get("items", {})
    curr_items = curr_pl.get("items", {})
    prev_derived = prev_pl.get("derived", {})
    curr_derived = curr_pl.get("derived", {})

    items_out: dict[str, dict] = {}
    for key in set(prev_items) | set(curr_items):
        prev = prev_items.get(key)
        curr = curr_items.get(key)
        delta_pct: float | None = None
        if prev is not None and curr is not None and prev != 0:
            delta_pct = (curr - prev) / abs(prev) * 100.0
        is_mover = False
        if delta_pct is not None and abs(delta_pct) >= _PL_MOVER_PCT_THRESHOLD:
            is_mover = True
        # Sign flip on net_income — loss in either year — is always material.
        if key == "net_income":
            if (prev is not None and prev < 0) or (curr is not None and curr < 0):
                is_mover = True
        items_out[key] = {
            "prev": prev, "curr": curr,
            "delta_pct": delta_pct, "is_mover": is_mover,
        }

    margins_out: dict[str, dict] = {}
    for key in set(prev_derived) | set(curr_derived):
        prev_pct = prev_derived.get(key)
        curr_pct = curr_derived.get(key)
        pp_delta = (curr_pct - prev_pct) if (prev_pct is not None and curr_pct is not None) else None
        is_mover = bool(pp_delta is not None and abs(pp_delta) >= _PL_MOVER_MARGIN_PP_THRESHOLD)
        margins_out[key] = {
            "prev": prev_pct, "curr": curr_pct,
            "pp_delta": pp_delta, "is_mover": is_mover,
        }

    return {
        "items": items_out,
        "margins": margins_out,
        "prev_missing": prev_pl.get("missing", []),
        "curr_missing": curr_pl.get("missing", []),
    }


def _pl_yoy_for_response(pl_yoy: dict | None) -> dict | None:
    """Shape the internal `_pl_yoy` dict into a JSON-friendly response payload
    for the UI's P/L panel. Drops nothing — same-shape mirror of the prompt's
    view of the data."""
    if not pl_yoy or (not pl_yoy.get("items") and not pl_yoy.get("margins")):
        return None
    return {
        "items": pl_yoy.get("items", {}),
        "margins": pl_yoy.get("margins", {}),
    }


# Earnings-quality threshold for the multi-year CFO/NI consistency flag.
# Below 0.8 means reported profit is not converting cleanly to operating cash —
# classic earnings-quality warning. Two CONSECUTIVE years below the bar is the
# pattern; a single year can be a working-capital one-off.
_CFO_TO_NI_LOW_THRESHOLD = 0.8


def _cashflow_yoy(prev_zip: Path, curr_zip: Path) -> dict:
    """Pull CF panels from prev + curr ZIPs and compute YoY deltas.

    Returns:
        {
          "items": {key: {prev, curr, delta_pct}},  # cfo, capex
          "derived": {key: {prev, curr, delta_pct}},  # fcf
          "ratios": {"cfo_to_ni": {prev, curr}},
          "prev_missing": [...], "curr_missing": [...],
        }

    Pure function. Bad ZIPs return empty items; downstream prompt builder
    degrades to "Cash-flow data unavailable for this filer".
    """
    prev_cf = extract_cashflow_from_zip_path(prev_zip)
    curr_cf = extract_cashflow_from_zip_path(curr_zip)
    prev_items = prev_cf.get("items", {})
    curr_items = curr_cf.get("items", {})
    prev_derived = prev_cf.get("derived", {})
    curr_derived = curr_cf.get("derived", {})

    items_out: dict[str, dict] = {}
    for key in ("cfo", "capex"):
        prev = prev_items.get(key)
        curr = curr_items.get(key)
        delta_pct: float | None = None
        if prev is not None and curr is not None and prev != 0:
            delta_pct = (curr - prev) / abs(prev) * 100.0
        items_out[key] = {"prev": prev, "curr": curr, "delta_pct": delta_pct}

    derived_out: dict[str, dict] = {}
    for key in ("fcf",):
        prev = prev_derived.get(key)
        curr = curr_derived.get(key)
        delta_pct: float | None = None
        if prev is not None and curr is not None and prev != 0:
            delta_pct = (curr - prev) / abs(prev) * 100.0
        derived_out[key] = {"prev": prev, "curr": curr, "delta_pct": delta_pct}

    ratios_out = {
        "cfo_to_ni": {
            "prev": prev_derived.get("cfo_to_ni_ratio"),
            "curr": curr_derived.get("cfo_to_ni_ratio"),
        }
    }

    # Phase 1 audit fix (2026-05-16) — surface the "loss-making but
    # positive CFO" signal per-period so the prompt block can highlight it.
    flags_out = {
        "prev_cfo_positive_despite_loss":
            bool(prev_derived.get("cfo_positive_despite_loss")),
        "curr_cfo_positive_despite_loss":
            bool(curr_derived.get("cfo_positive_despite_loss")),
    }

    return {
        "items": items_out,
        "derived": derived_out,
        "ratios": ratios_out,
        "flags": flags_out,
        "prev_missing": prev_cf.get("missing", []),
        "curr_missing": curr_cf.get("missing", []),
    }


def _cashflow_yoy_for_response(cf_yoy: dict | None) -> dict | None:
    """Shape internal `_cashflow_yoy` dict for the JSON API response."""
    if not cf_yoy or (not cf_yoy.get("items") and not cf_yoy.get("derived")):
        return None
    return {
        "items":   cf_yoy.get("items", {}),
        "derived": cf_yoy.get("derived", {}),
        "ratios":  cf_yoy.get("ratios", {}),
    }


_PEER_MIN_COUNT = 5  # min peers per sector to show the block at all
_SECTOR_MEDIAN_CACHE: dict[tuple[str, int], dict] = {}
_SECTOR_PEERS_CACHE: dict[str, list[str]] | None = None


def _list_local_tickers() -> list[str]:
    """All 4-digit tickers with a data/tempest/<code>/ directory."""
    base = ROOT / "data" / "tempest"
    if not base.exists():
        return []
    return sorted(d.name for d in base.iterdir()
                  if d.is_dir() and d.name.isdigit())


def _build_sector_peers() -> dict[str, list[str]]:
    """Map JPX 33業種 code → list of tickers in our local universe.

    Lazy-built once per process. Tickers without a JPX mapping are silently
    excluded — they have no peer set and the peer block will skip for them.
    """
    global _SECTOR_PEERS_CACHE
    if _SECTOR_PEERS_CACHE is not None:
        return _SECTOR_PEERS_CACHE
    out: dict[str, list[str]] = {}
    for t in _list_local_tickers():
        try:
            rec = _jpx_lookup(t)
        except Exception:
            rec = None
        code33 = getattr(rec, "code33", None)
        if not code33:
            continue
        out.setdefault(code33, []).append(t)
    _SECTOR_PEERS_CACHE = out
    return out


def _ticker_pl_for_fy(ticker: str, fy: int) -> dict | None:
    """Return {revenue, op_margin_pct, net_margin_pct, revenue_prev_fy} for one
    peer ticker at the requested fiscal year.

    `revenue_prev_fy` lets the caller compute YoY without re-loading. Returns
    None when the ticker has no ASR covering that FY or the PL extractor
    can't read revenue + op_income.
    """
    folder = ROOT / "data" / "tempest" / ticker
    if not folder.exists():
        return None
    try:
        series = load_asr_series(folder)
    except Exception:
        return None
    by_fy: dict[int, dict] = {}
    for s in series:
        try:
            pe = s.get("period_end", "")
            fy_here = int(pe[:4]) if pe else None
        except (TypeError, ValueError):
            continue
        if fy_here is None:
            continue
        by_fy[fy_here] = s
    curr = by_fy.get(fy)
    prev = by_fy.get(fy - 1)
    if curr is None:
        return None
    try:
        pl_curr = extract_pl_from_zip_path(Path(curr["zip_path"]))
    except Exception:
        return None
    items = pl_curr.get("items", {})
    derived = pl_curr.get("derived", {})
    rev_curr = items.get("revenue")
    op_curr = items.get("operating_income")
    if not (rev_curr and rev_curr > 0 and op_curr is not None):
        return None
    op_margin_curr = op_curr / rev_curr * 100.0
    net_margin_curr = derived.get("net_margin_pct")

    rev_prev = None
    op_margin_prev = None
    if prev is not None:
        try:
            pl_prev = extract_pl_from_zip_path(Path(prev["zip_path"]))
            items_p = pl_prev.get("items", {})
            r_p = items_p.get("revenue")
            o_p = items_p.get("operating_income")
            if r_p and r_p > 0:
                rev_prev = r_p
                if o_p is not None:
                    op_margin_prev = o_p / r_p * 100.0
        except Exception:
            pass

    out: dict = {
        "revenue":           rev_curr,
        "op_margin_pct":     op_margin_curr,
        "net_margin_pct":    net_margin_curr,
        "revenue_prev_fy":   rev_prev,
        "op_margin_prev_fy": op_margin_prev,
    }
    if rev_prev and rev_prev > 0:
        out["revenue_yoy_pct"] = (rev_curr - rev_prev) / rev_prev * 100.0
    if op_margin_prev is not None:
        out["op_margin_pp_delta"] = op_margin_curr - op_margin_prev
    return out


def _median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    if n % 2:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _sector_medians_for_fy(sector_code: str, fy: int,
                           exclude_ticker: str | None = None) -> dict | None:
    """Median peer metrics for the given sector at the given fiscal year.

    Cached per (sector_code, fy, exclude_ticker). Returns None when there
    are fewer than `_PEER_MIN_COUNT` peers EXCLUDING the target — that's
    the honest no-signal threshold (a 2-name median is just noise).

    `exclude_ticker` is the company being analysed; it is dropped from
    both the median computation and the peer count so a ticker is never
    compared against itself.
    """
    key = (sector_code, fy, exclude_ticker or "")
    cached = _SECTOR_MEDIAN_CACHE.get(key)
    if cached is not None:
        return cached if cached.get("__valid") else None

    peers = [t for t in _build_sector_peers().get(sector_code, [])
             if t != exclude_ticker]
    rev_yoys: list[float] = []
    op_margins: list[float] = []
    op_margin_pp_deltas: list[float] = []
    net_margins: list[float] = []
    contributing: list[str] = []
    for t in peers:
        m = _ticker_pl_for_fy(t, fy)
        if m is None:
            continue
        if m.get("revenue_yoy_pct") is not None:
            rev_yoys.append(m["revenue_yoy_pct"])
        op_margins.append(m["op_margin_pct"])
        if m.get("op_margin_pp_delta") is not None:
            op_margin_pp_deltas.append(m["op_margin_pp_delta"])
        if m.get("net_margin_pct") is not None:
            net_margins.append(m["net_margin_pct"])
        contributing.append(t)
    if len(contributing) < _PEER_MIN_COUNT:
        _SECTOR_MEDIAN_CACHE[key] = {"__valid": False, "peer_count": len(contributing)}
        return None
    medians = {
        "__valid": True,
        "sector_code":       sector_code,
        "fiscal_year":       fy,
        "peer_count":        len(contributing),  # already excludes self
        "peers":             contributing,
        "rev_yoy_median":    _median(rev_yoys),
        "op_margin_median":  _median(op_margins),
        "op_margin_pp_median": _median(op_margin_pp_deltas),
        "net_margin_median": _median(net_margins),
    }
    _SECTOR_MEDIAN_CACHE[key] = medians
    return medians


def _peer_block_inputs(code: str, curr_fy: int,
                       my_revenue_yoy: float | None,
                       my_op_margin: float | None,
                       my_op_margin_pp_delta: float | None,
                       my_net_margin: float | None) -> dict | None:
    """Build the dict consumed by `_build_peer_block`.

    Returns None when peer comparison cannot be shown — either the ticker
    has no JPX mapping or the sector has < 5 peers with data for this FY.
    The prompt builder treats a None block as "skip entirely" (no peer
    comparison shown to the LLM), per the explicit no-noisy-median rule.
    """
    try:
        rec = _jpx_lookup(code)
    except Exception:
        rec = None
    sector_code = getattr(rec, "code33", None)
    sector_name = getattr(rec, "label33", None)
    if not sector_code:
        return None
    medians = _sector_medians_for_fy(sector_code, curr_fy, exclude_ticker=code)
    if medians is None:
        return None
    return {
        "sector_code":   sector_code,
        "sector_name":   sector_name or "",
        "fiscal_year":   curr_fy,
        "peer_count_excl_self": medians.get("peer_count", 0),
        "peers":         medians.get("peers", []),
        "my": {
            "revenue_yoy_pct":     my_revenue_yoy,
            "op_margin_pct":       my_op_margin,
            "op_margin_pp_delta":  my_op_margin_pp_delta,
            "net_margin_pct":      my_net_margin,
        },
        "sector_median": {
            "rev_yoy_pct":         medians.get("rev_yoy_median"),
            "op_margin_pct":       medians.get("op_margin_median"),
            "op_margin_pp_delta":  medians.get("op_margin_pp_median"),
            "net_margin_pct":      medians.get("net_margin_median"),
        },
    }


def _detect_cfo_ni_low_quality(cashflow_history: list[dict],
                               curr_fiscal_year: int) -> dict:
    """Detect the '< 0.8 for 2+ consecutive years' earnings-quality pattern.

    `cashflow_history` shape (built by the caller, one entry per fiscal year):
        [{"fiscal_year": int, "cfo_to_ni_ratio": float | None}, ...]

    Returns:
        {
          "flagged": bool,
          "consecutive_low_years": int,        # streak ending at curr or earlier
          "ratios_window": [(fy, ratio), ...], # last up-to-3 years for prompt
        }

    `flagged` is True when the most-recent up-to-3 years ending at or before
    curr_fiscal_year contain at least 2 CONSECUTIVE years where CFO/NI is
    below 0.8. Insufficient data → flagged=False, no false positives.
    """
    if not cashflow_history:
        return {"flagged": False, "consecutive_low_years": 0, "ratios_window": []}
    # Restrict to years we can legitimately see at this pair's vintage.
    visible = [r for r in cashflow_history
               if r.get("fiscal_year") is not None
               and r["fiscal_year"] <= curr_fiscal_year
               and r.get("cfo_to_ni_ratio") is not None]
    visible.sort(key=lambda r: r["fiscal_year"])
    window = visible[-3:]
    streak = 0
    best_streak = 0
    for r in window:
        if r["cfo_to_ni_ratio"] < _CFO_TO_NI_LOW_THRESHOLD:
            streak += 1
            best_streak = max(best_streak, streak)
        else:
            streak = 0
    return {
        "flagged": best_streak >= 2,
        "consecutive_low_years": best_streak,
        "ratios_window": [(r["fiscal_year"], r["cfo_to_ni_ratio"]) for r in window],
    }


# Phase 5 (Tier 1, 2026-05-15) — qualitative disclosure signals.
# Truncation budget tuned to keep total added input tokens manageable:
#   risk section: 4000 chars × 2 years = 8000 chars (~2000 tokens)
#   governance:   2500 chars × 2 years = 5000 chars (~1250 tokens)
# Total addition: ~3250 input tokens per LLM call. At $3/M input that's
# ~$0.01 extra per pair on top of Phase 2's ~$0.04 — well worth it for
# year-over-year qualitative comparison.
_RISK_TEXT_BUDGET = 4000
_GOVERNANCE_TEXT_BUDGET = 2500


def _compute_bs_quality_history(raw_history: list[dict],
                                curr_fiscal_year: int | None = None) -> list[dict]:
    """Phase 6 (2026-05-16) — derive four structured balance-sheet-quality
    metrics per year from the raw history collected upstream.

    Input shape (from analyze_company_multi_year loop):
        [{"fiscal_year", "revenue", "goodwill", "equity", "inventory",
          "trade_receivables", "segment_shares"}, ...]

    Output shape:
        [{"fiscal_year", "top_segment_share_pct", "herfindahl_index",
          "goodwill_to_equity_pct", "dso_days", "inventory_days"}, ...]

    All metrics are None when the inputs they need are missing. The prompt
    block renders None as "—" rather than fabricating zero.

    Pure function. The Herfindahl index is reported on the conventional
    1-10000 scale (sum of squared shares × 10000). Above ~2500 = highly
    concentrated; below ~1500 = unconcentrated.

    `curr_fiscal_year` (when provided) trims the output to years ≤ curr so
    callers don't leak future data into a per-pair prompt.
    """
    out: list[dict] = []
    for r in sorted(raw_history, key=lambda x: x.get("fiscal_year", 0)):
        fy = r.get("fiscal_year")
        if fy is None:
            continue
        if curr_fiscal_year is not None and fy > curr_fiscal_year:
            continue
        rev = r.get("revenue")
        goodwill = r.get("goodwill")
        equity = r.get("equity")
        inventory = r.get("inventory")
        receivables = r.get("trade_receivables")
        shares = r.get("segment_shares") or []

        top_share_pct = None
        herf = None
        if shares:
            top_share_pct = max(shares) * 100.0
            herf = sum(s * s for s in shares) * 10000.0

        goodwill_to_equity_pct = None
        if goodwill is not None and equity is not None and equity > 0:
            goodwill_to_equity_pct = goodwill / equity * 100.0

        dso = None
        if receivables is not None and rev and rev > 0:
            dso = receivables / rev * 365.0

        inv_days = None
        if inventory is not None and rev and rev > 0:
            inv_days = inventory / rev * 365.0

        out.append({
            "fiscal_year":            fy,
            "top_segment_share_pct":  top_share_pct,
            "herfindahl_index":       herf,
            "goodwill_to_equity_pct": goodwill_to_equity_pct,
            "dso_days":               dso,
            "inventory_days":         inv_days,
        })
    return out


def _qualitative_signals_yoy(prev_zip: Path, curr_zip: Path) -> dict:
    """Pull risk-factor and corporate-governance text from prev + curr ASRs.

    Returns:
        {
          "risk_factors":          {"prev": str, "curr": str},
          "corporate_governance":  {"prev": str, "curr": str},
          "prev_has_risk":         bool,
          "curr_has_risk":         bool,
          "prev_has_governance":   bool,
          "curr_has_governance":   bool,
        }

    Both text values are TRUNCATED to the per-section budget defined above.
    Empty string means the section is absent for that filing; the prompt
    builder degrades gracefully (the block tells the LLM to note the
    absence rather than fabricate a comparison).

    Pure function — never raises; bad ZIPs return empty strings.
    """
    def _grab(zip_path: Path, section: str, budget: int) -> str:
        try:
            txt = extract_text_section_from_zip_path(zip_path, section)
        except Exception:
            return ""
        if not txt:
            return ""
        return txt if len(txt) <= budget else txt[:budget]

    prev_risk = _grab(prev_zip, SECTION_BUSINESS_RISKS, _RISK_TEXT_BUDGET)
    curr_risk = _grab(curr_zip, SECTION_BUSINESS_RISKS, _RISK_TEXT_BUDGET)
    prev_gov = _grab(prev_zip, SECTION_CORPORATE_GOVERNANCE, _GOVERNANCE_TEXT_BUDGET)
    curr_gov = _grab(curr_zip, SECTION_CORPORATE_GOVERNANCE, _GOVERNANCE_TEXT_BUDGET)

    return {
        "risk_factors":         {"prev": prev_risk, "curr": curr_risk},
        "corporate_governance": {"prev": prev_gov, "curr": curr_gov},
        "prev_has_risk":        bool(prev_risk),
        "curr_has_risk":        bool(curr_risk),
        "prev_has_governance":  bool(prev_gov),
        "curr_has_governance":  bool(curr_gov),
    }


def _qualitative_signals_for_response(qual: dict | None) -> dict | None:
    """Shape `_qualitative_signals_yoy` for the JSON API response.

    Drops the raw text bodies (they're huge and not needed by the UI) but
    keeps the presence flags + truncated previews so the UI can show "risk
    factors compared: yes" badges without re-loading the source.
    """
    if not qual:
        return None
    rf = qual.get("risk_factors", {})
    gv = qual.get("corporate_governance", {})

    def _preview(s: str | None, n: int = 400) -> str:
        s = s or ""
        return s if len(s) <= n else (s[:n] + " …[truncated]")

    return {
        "prev_has_risk":        qual.get("prev_has_risk", False),
        "curr_has_risk":        qual.get("curr_has_risk", False),
        "prev_has_governance":  qual.get("prev_has_governance", False),
        "curr_has_governance":  qual.get("curr_has_governance", False),
        "risk_factors_preview":         {"prev": _preview(rf.get("prev")), "curr": _preview(rf.get("curr"))},
        "corporate_governance_preview": {"prev": _preview(gv.get("prev")), "curr": _preview(gv.get("curr"))},
    }


def _segment_yoy(prev_zip: Path, curr_zip: Path) -> tuple[list[dict], float, float]:
    """Return (segments, total_prev, total_curr).

    `segments` is a list of dicts ready for the prompt and for the API
    response, sorted by |delta| descending. Segments missing on either side
    are kept (prev=0 or curr=0).
    """
    df_prev = extract_segments(prev_zip)
    df_curr = extract_segments(curr_zip)
    # Build prev/curr lookup keyed on EN name; carry JA in a side-map.
    prev_map: dict[str, float] = {}
    curr_map: dict[str, float] = {}
    name_ja_map: dict[str, str] = {}
    if not df_prev.empty:
        for _, r in df_prev.iterrows():
            prev_map[r["segment_name"]] = r["revenue"]
            name_ja_map.setdefault(r["segment_name"], r.get("segment_name_ja") or "")
    if not df_curr.empty:
        for _, r in df_curr.iterrows():
            curr_map[r["segment_name"]] = r["revenue"]
            # Prefer current-year JA label if both periods provide one.
            ja = r.get("segment_name_ja") or ""
            if ja:
                name_ja_map[r["segment_name"]] = ja

    # Cross-standard fallback. If the prev ZIP uses a different accounting
    # standard (e.g., Sony's US-GAAP→IFRS switch made the FY2020 ZIP's
    # segment tags unmatchable to the FY2021 IFRS taxonomy), prev_map will
    # be empty or share zero names with curr_map, and every segment would
    # spuriously show prev=0 → +100% YoY.
    #
    # The IFRS-mandated restated prior-year comparatives sit in the SAME
    # current-year ZIP under Prior1 contexts. Pull them from curr_zip
    # whenever the natural prev_map fails to overlap. Those are the same
    # restated numbers the company prints in its segment-table comparative
    # column (Sony FY2020-restated, etc.) — exactly what the LLM should see.
    overlap = set(prev_map) & set(curr_map)
    if curr_map and not overlap:
        df_prev_restated = extract_segments(curr_zip, period="prior")
        if not df_prev_restated.empty:
            prev_map = {}
            for _, r in df_prev_restated.iterrows():
                prev_map[r["segment_name"]] = r["revenue"]
                ja = r.get("segment_name_ja") or ""
                if ja:
                    name_ja_map.setdefault(r["segment_name"], ja)
            log.info("segment prev fallback: used curr_zip restated prior comparatives "
                     "(%d segments) — prev_zip extraction did not overlap curr_zip",
                     len(prev_map))

    rows: list[dict] = []
    for name in set(prev_map) | set(curr_map):
        prev = float(prev_map.get(name, 0.0))
        curr = float(curr_map.get(name, 0.0))
        delta = curr - prev
        delta_pct = (delta / prev * 100.0) if prev else (100.0 if curr else 0.0)
        rows.append({
            "name": name,
            "name_ja": name_ja_map.get(name, ""),
            "prev": prev,
            "curr": curr,
            "delta": delta,
            "delta_pct": delta_pct,
        })
    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
    # ALWAYS use headline consolidated revenue (Summary-of-Business-Results /
    # KeyFinancialData / IFRS / GAAP tags, in that priority). This matches
    # what the company itself reports in IR materials.
    total_prev = float(extract_revenue_from_zip_path(prev_zip) or 0.0)
    total_curr = float(extract_revenue_from_zip_path(curr_zip) or 0.0)
    if total_prev == 0:
        total_prev = sum(prev_map.values())
    if total_curr == 0:
        total_curr = sum(curr_map.values())
    return rows, total_prev, total_curr


def _build_revenue_scope_note(prev_zip: Path, curr_zip: Path,
                              total_prev: float, total_curr: float) -> dict | None:
    """Detect revenue-scope ambiguity in either filing and return a note
    structured for both the LLM prompt and the API response. Returns None
    if both filings are unambiguous (single revenue scope)."""
    prev_scope = detect_revenue_scope(prev_zip, total_prev)
    curr_scope = detect_revenue_scope(curr_zip, total_curr)
    if not prev_scope and not curr_scope:
        return None
    # Use the curr-year scope as the primary (it's the more recent disclosure).
    primary = curr_scope or prev_scope
    return {
        "ambiguous": True,
        "year_with_ambiguity": "current" if curr_scope else "previous",
        "picked_value": primary["picked_value"],
        "picked_tag": primary["picked_tag"],
        "picked_scope_en": primary["picked_scope_en"],
        "picked_scope_ja": primary["picked_scope_ja"],
        "alternatives": primary["alternatives"],
    }


def _classify_stock_direction(pct: float | None) -> str:
    """Pure helper — turns a percent return into 'positive' / 'negative' /
    'unchanged' / 'unknown'. Extracted from _stock_5d_move so unit tests
    don't need yfinance."""
    if pct is None:
        return "unknown"
    if pct > 0:
        return "positive"
    if pct < 0:
        return "negative"
    return "unchanged"


# Stock-reaction window in TRADING days. Senior's original spec was 5;
# extended briefly to 14 on 2026-05-10 to test whether wider window =
# less noise. Backtest 2026-05-10 showed 14-day actually reduced trend_aware
# hit rate from 61.9% → 50.0% (wider window introduced macro drift that
# drowned the filing-event signal). Reverted to 5 on 2026-05-11 — the
# original spec was empirically correct.
#
# The field name `stock_5d_return_pct` is preserved on the response payload
# for backwards compatibility with the UI / coverage rules / JSON consumers.
STOCK_REACTION_WINDOW_TRADING_DAYS = 5


def _stock_5d_move(code: str, filing_date: str) -> dict[str, Any]:
    """Close-to-close return over STOCK_REACTION_WINDOW_TRADING_DAYS trading
    days after the filing date.

    Function name retained for backwards compatibility — the value reflects
    the configured window (14 days as of 2026-05-10), not literally 5.
    """
    d = datetime.strptime(filing_date, "%Y-%m-%d")
    start = d.strftime("%Y-%m-%d")
    # Calendar-day buffer must cover the trading window + weekends + holidays.
    # 14 trading days ≈ 21 calendar days; pad to 35 to be safe across long
    # holiday clusters (Golden Week, year-end, Obon).
    end = (d + timedelta(days=35)).strftime("%Y-%m-%d")
    df = prices.fetch_prices_df(code, start, end)
    if df is None or df.empty:
        return {
            "stock_5d_return_pct": None,
            "stock_direction": "unknown",
            "anchor_date": None,
            "end_date": None,
        }
    closes = df["Close"].squeeze().dropna()
    if len(closes) < 2:
        return {
            "stock_5d_return_pct": None,
            "stock_direction": "unknown",
            "anchor_date": str(closes.index[0].date()) if len(closes) else None,
            "end_date": None,
        }
    anchor = float(closes.iloc[0])
    target_idx = min(STOCK_REACTION_WINDOW_TRADING_DAYS, len(closes) - 1)
    end_px = float(closes.iloc[target_idx])
    pct = (end_px - anchor) / anchor * 100.0
    return {
        "stock_5d_return_pct": round(pct, 3),
        "stock_direction": _classify_stock_direction(pct),
        "anchor_date": str(closes.index[0].date()),
        "end_date": str(closes.index[target_idx].date()),
    }


# --- Narrative-coverage post-check -----------------------------------------
#
# The LLM prompt asks for OFFSET / DRIVER COMPLETENESS / no-expectations
# discipline, but instructions only nudge — they don't enforce. This regex
# checker runs after the LLM call and flags cases where the source narrative
# contains a strong-signal trigger token but the explanation does not surface
# the corresponding concept. Belt and suspenders: prompt rules handle the
# average case, this catches regressions.
#
# Each rule pairs (a) a regex over the source Japanese narrative with
# (b) a regex over the bilingual LLM output that should appear when (a)
# fires. We deliberately accept either language on the output side because
# the agent emits both EN and JA; either match clears the rule.

_COVERAGE_RULES = (
    {
        "id": "explicit_offset",
        "narrative_re": _re.compile(r"(一部相殺|相殺されて|partially offset)"),
        "output_re": _re.compile(r"(offset|相殺|despite|もの の|にもかかわらず)", _re.IGNORECASE),
        "warning": "narrative contains 相殺/partially-offset clause but explanation does not mention an offset/headwind",
    },
    {
        "id": "mixed_drivers_despite",
        "narrative_re": _re.compile(r"(ものの[、。]|にもかかわらず|despite (?:a )?(?:lower|decline|decrease|fall))"),
        "output_re": _re.compile(r"(despite|ものの|にもかかわらず|even though|partially|一部)", _re.IGNORECASE),
        "warning": "narrative contains 〜ものの/despite clause but explanation does not preserve the mixed-driver framing",
    },
    {
        "id": "acquisition_driver",
        "narrative_re": _re.compile(r"(買収|取得した|完全子会社化|acquisition|acquired)"),
        "output_re": _re.compile(r"(acquisition|acquired|買収|取得|m&a)", _re.IGNORECASE),
        "warning": "narrative names a 買収/acquisition driver but explanation does not mention M&A",
    },
    {
        # Divestiture rule — tightened. Earlier version fired on any 売却 /
        # 譲渡 token, which over-flagged on conglomerate filings (SoftBank,
        # NTT) where 売却 appears 30+ times in routine portfolio activity:
        # "T-Mobile shares sold", "SVF investment disposals", CF-statement
        # boilerplate "投資有価証券の売却", etc. These are NOT divestitures.
        # We only want to flag genuine business-divestiture mentions:
        # subsidiary disposals (子会社株式の売却 / 全持分の譲渡 / 支配喪失),
        # business transfers (事業譲渡), or named-segment exits.
        "id": "divestiture_driver",
        "narrative_re": _re.compile(
            r"(事業譲渡|"
            r"子会社(?:株式|持分)?の(?:譲渡|売却)|"
            r"全(?:株式|持分)の(?:譲渡|売却)|"
            r"(?:支配の?喪失|連結除外)|"
            r"divest(?:ed|iture)|spun? off|sold (?:its|the|our) (?:subsidiary|business|stake|division|operation|arm))",
            _re.IGNORECASE,
        ),
        "output_re": _re.compile(
            r"(divestiture|divested|spin-?off|spun off|"
            r"sold (?:its|the|our|a) (?:subsidiary|business|stake|division|operation|arm)|"
            r"事業譲渡|子会社.{0,20}(?:譲渡|売却)|全(?:株式|持分).{0,20}(?:譲渡|売却)|"
            r"支配.{0,5}喪失|連結除外)",
            _re.IGNORECASE,
        ),
        "warning": "narrative names a business-divestiture / subsidiary-disposal driver but explanation does not mention it",
    },
    {
        "id": "volume_decline",
        "narrative_re": _re.compile(r"(販売台数(?:の)?減少|出荷(?:台数|数量)(?:の)?減少|unit sales declined|volume(?:s)? declined)"),
        "output_re": _re.compile(r"(unit|volume|台数|数量|despite (?:lower|fewer)|ものの)", _re.IGNORECASE),
        "warning": "narrative reports a 販売台数減少/unit-volume decline but explanation does not surface it",
    },
    {
        # Inverted rule with proximity guard. Earlier version flagged any
        # mention of "consensus" / "コンセンサス" — but the prompt itself asks
        # the model to write a caveat sentence like "this cannot be confirmed
        # without analyst consensus data", which legitimately uses the word.
        # We only want to flag cases where the model CLAIMS a beat/miss
        # against expectations, not cases where it DISCLAIMS knowledge of
        # expectations. So the regex now requires a comparator (beat / miss
        # / above / below / 上回 / 下回 / 予想以上 / 予想以下 / higher than /
        # lower than / better than / worse than) — the comparator is what
        # turns a hedge into a claim.
        "id": "no_expectations_invented",
        "narrative_re": None,  # always check
        "output_re": _re.compile(
            r"(beat (?:expectations|consensus|estimates)|"
            r"miss(?:ed)? (?:expectations|consensus|estimates)|"
            r"(?:higher|lower|better|worse) than expected|"
            r"(?:above|below|exceeded|fell short of) (?:consensus|expectations|estimates)|"
            r"市場予想を上回|市場予想を下回|予想以上|予想以下|"
            r"コンセンサス(?:予想)?を(?:上回|下回|超え|下))",
            _re.IGNORECASE,
        ),
        "narrative_must_contain": _re.compile(
            r"(コンセンサス|アナリスト予想|市場予想|"
            r"consensus|analyst (?:forecast|estimate|expectation))"
        ),
        "warning": "explanation invokes analyst/market expectations but the source narrative does not provide consensus/expectations data",
    },
)


# --- Phase A coverage rules ------------------------------------------------
#
# These run alongside _COVERAGE_RULES but need richer inputs than the
# (narrative, explanation) pair the regex rules accept. Each has its own
# helper returning either None (rule passed / didn't apply) or a warning dict.

# %-of-total share token, e.g. "46%", "46.2%", "46 %". The composition opener
# is required to land at least one such token within the first ~250 chars of
# either bilingual half.
_SHARE_PCT_RE = _re.compile(r"\b\d{1,3}(?:\.\d)?\s*%")

# Hedged-language tokens for the divergence reconciliation requirement. Both
# languages accepted; either side clears the rule.
_HEDGED_TOKEN_RE = _re.compile(
    r"(might|possibly|likely|may have|may reflect|may indicate|perhaps|"
    r"appears to|consistent with|可能性|おそらく|かもしれない|恐らく|"
    r"反映している可能性|と整合的)",
    _re.IGNORECASE,
)

# Foreign-tangent tokens. Conservative list: country names, mega-cap peers,
# and the most common geographic regions. Detection is the FIRST step — the
# rule below decides per-sentence whether the mention is tied to a real
# revenue/profit driver (allowed) or is bare peer/market color (flagged).
_FOREIGN_TOKEN_RE = _re.compile(
    r"\b(United States|U\.S\.|US |USA|American|Americans|"
    r"China|Chinese|Korea|Korean|India|Indian|Europe|European|Germany|"
    r"UK|British|Britain|France|French|Brazil|Brazilian|Mexico|Russian|"
    r"Apple|Google|Microsoft|Amazon|Meta|Nvidia|Tesla|Verizon|AT&T|"
    r"T-Mobile|Vodafone|Samsung|Huawei|Alibaba|Tencent|Baidu)\b",
    _re.IGNORECASE,
)

# Indicators that a sentence is doing revenue/profit ATTRIBUTION (driver
# context) rather than peer-comparison color. The presence of any of these in
# the same sentence as a foreign token means the mention is tied to where
# revenue or profit came from — keep it.
_FOREIGN_DRIVER_INDICATORS_RE = _re.compile(
    r"\b(acqui(?:red|sition|sitions|ring)|"
    r"subsidiar(?:y|ies)|merger|merged|joint venture|JV|"
    r"spin[- ]?off|spun off|divest(?:ed|iture|ment)|deconsolidat(?:ed|ion)|"
    r"IPO|listing|"
    r"drove|driven by|contributed|led by|boosted|accounted for|"
    r"resulting in|due to|thanks to|owing to|attributable to|on the back of|"
    r"FX|foreign[- ]exchange|exchange rate|"
    r"yen weakness|yen strength|currency (?:tailwind|headwind|impact|effect)|"
    r"weaker yen|stronger yen|"
    r"revenue from|sales in|sales to|operations in|customers in|market in|"
    r"business in|exposure to|presence in|expanded in|launched in|"
    r"operating segment|reportable segment|reporting segment)\b",
    _re.IGNORECASE,
)

# Numeric attribution — a sentence with a percentage or yen/dollar figure is
# almost always making a quantitative driver claim, not just citing a peer
# for color. Same effect as a driver verb: keep the mention.
_NUMERIC_ATTRIBUTION_RE = _re.compile(
    r"(\b\d+(?:\.\d+)?\s*%|"
    r"[¥$]\s*\d|"
    r"\b\d+(?:[,.]\d+)?\s*(?:billion|trillion|million|億|兆|億円|兆円))",
    _re.IGNORECASE,
)


def _check_composition_opener(explanation_en: str, explanation_ja: str,
                              segments_present: bool) -> dict | None:
    """Composition opener — NO LONGER REQUIRED.

    Earlier the prompt required the explanation to open with a sentence
    naming top segments by share-of-total (%). That requirement was
    dropped when the agent's output was tightened to focus on stock
    causation; the segment table in the UI shows shares directly, so
    re-narrating them in prose was redundant.

    This function is kept as a no-op for backward compatibility with
    callers that still pass it through `_check_narrative_coverage`.
    """
    return None


def _check_divergence_addressed(response_class: str, explanation_en: str,
                                explanation_ja: str) -> dict | None:
    """When the stock response is an anomaly (sign-disagreement OR
    same-direction under-reaction), the explanation must contain at least
    one hedged-reconciliation token. Belt-and-suspenders over the prompt's
    DIVERGENCE-REASONING RULE."""
    if response_class not in ("divergence", "weak_response"):
        return None
    out = (explanation_en or "") + " " + (explanation_ja or "")
    if _HEDGED_TOKEN_RE.search(out):
        return None
    msg_by_class = {
        "divergence": "operating-profit and post-filing stock moved in opposite directions but explanation does not propose a hedged reconciling reason",
        "weak_response": "profit moved meaningfully but the stock barely reacted (under-reaction) and the explanation does not propose a hedged reason for why the market discounted the result",
    }
    return {
        "rule": "divergence_addressed",
        "message": msg_by_class[response_class],
    }


# BS keyword regexes for the citation post-check. Each item key maps to
# a regex matching natural-language references in EITHER explanation half
# (EN + JA). When divergence is set and at least one mover exists, the
# explanation must contain at least one keyword from the mover items —
# otherwise the LLM ignored a load-bearing reconciliation candidate.
_BS_ITEM_KEYWORDS_RE = {
    "goodwill": _re.compile(r"\bgoodwill\b|のれん", _re.IGNORECASE),
    "impairment_loss": _re.compile(r"\bimpairment\b|減損|writedown|write-?down", _re.IGNORECASE),
    "tangible_fixed_assets": _re.compile(r"\btangible\b|\bproperty,? plant\b|有形(?:固定)?資産|設備", _re.IGNORECASE),
    "intangible_assets": _re.compile(r"\bintangible\b|無形(?:固定)?資産", _re.IGNORECASE),
    "inventory": _re.compile(r"\binventor(?:y|ies)\b|\bstock build\b|棚卸|在庫", _re.IGNORECASE),
    "trade_receivables": _re.compile(r"\breceivable(?:s)?\b|売掛|売上債権", _re.IGNORECASE),
    "cash_and_equivalents": _re.compile(r"\bcash\b|現金", _re.IGNORECASE),
    "interest_bearing_debt": _re.compile(r"\bdebt\b|\bborrowing(?:s)?\b|leverage\b|借入|有利子負債|社債", _re.IGNORECASE),
    "equity": _re.compile(r"\bequity\b|純資産|自己資本", _re.IGNORECASE),
    "total_assets": _re.compile(r"\btotal assets\b|総資産", _re.IGNORECASE),
    "extraordinary_loss_total": _re.compile(r"\bextraordinary loss\b|特別損失", _re.IGNORECASE),
}


def _check_bs_citation(divergence: bool, bs_yoy: dict | None,
                       explanation_en: str, explanation_ja: str) -> dict | None:
    """Divergence-only BS-grounding check.

    Two failure modes:
      (a) movers exist but none cited → "you had a real candidate, you ignored it"
      (b) a non-mover BS item IS cited → "you grabbed at noise" (the prompt
          explicitly forbids non-mover citation)

    Both are advisory warnings — they don't block the explanation, just
    surface a yellow badge so a maintainer can review whether the rule
    fired correctly. The hedged-language requirement is enforced
    separately by `_check_divergence_addressed`.
    """
    if not divergence:
        return None
    if not bs_yoy or not bs_yoy.get("items"):
        return None
    items = bs_yoy["items"]
    mover_keys = [k for k, v in items.items() if v.get("is_mover")]
    if not mover_keys:
        return None  # no candidates → can't fault the LLM for not citing one

    out = (explanation_en or "") + " " + (explanation_ja or "")
    cited_movers = [k for k in mover_keys
                    if k in _BS_ITEM_KEYWORDS_RE and _BS_ITEM_KEYWORDS_RE[k].search(out)]

    # (b) non-mover citation check.
    nonmover_keys = [k for k in items if not items[k].get("is_mover") and k in _BS_ITEM_KEYWORDS_RE]
    cited_nonmovers = [k for k in nonmover_keys if _BS_ITEM_KEYWORDS_RE[k].search(out)]

    # Prefer the (a) warning when both fire — citing-noise alongside
    # ignoring-mover is still primarily an "ignored a real candidate" issue.
    if not cited_movers:
        return {
            "rule": "bs_citation_missing",
            "message": (
                "operating-profit / stock divergence has BS reconciliation "
                "candidates but explanation does not cite them: "
                + ", ".join(sorted(mover_keys))
            ),
        }
    if cited_nonmovers and not cited_movers:
        # Only fires when ALL citations are non-movers (cited_movers is
        # empty); the previous branch already handled that. Kept for clarity
        # in case future refactors split the branches.
        pass
    if cited_nonmovers and cited_movers:
        # Mixed case — mover cited (good) AND non-mover also cited (mild
        # noise). Don't warn; the divergence reasoning is still grounded.
        return None
    return None


# --- Audit-driven Phase A rules ------------------------------------------
#
# These three rules close gaps surfaced by a manual cross-check of two Sony
# explanations against the actual EDINET filings (FY2020-21 and FY2021-22).
# The checks above catch coarse omissions ("any acquisition mentioned");
# these catch the finer failure modes the audit found:
#   - Named-acquisition omission (e.g. Crunchyroll)
#   - Music-segment growth attributed to AWAL when narrative leads with streaming
#   - Financial-segment decline attributed to subsidiary consolidation when
#     narrative actually attributes it to investment-account losses

# Named acquisitions in the narrative — capture the proper-noun name before
# 買収 / の取得 / 完全子会社化. Two patterns: bracketed JA names like
# 「AWAL」 or 「Som Livre」, and English proper nouns like Crunchyroll or
# Bungie.
#
# Why no \b around the English-name capture: Python's \b uses \w semantics,
# and kanji characters are word characters under Python 3's default Unicode
# treatment. So between an ASCII proper noun ("Crunchyroll") and the kanji
# 買 there is NO word boundary, and a closing \b would silently fail. We
# use an explicit non-ASCII-letter lookbehind on the start side and a
# greedy character class on the end side instead.
_NAMED_ACQUISITION_RE = _re.compile(
    r"(?:「([^」\n]{2,30})」|"
    r"(?<![A-Za-z0-9])([A-Z][A-Za-z0-9.&\-]{2,30}(?:\s+[A-Z][A-Za-z0-9.&\-]+){0,2}))"
    r"(?:[\s　]*社)?"
    r"[\s　]*(?:の|を)?[\s　]*"
    r"(?:買収|取得|完全子会社化)",
)

# Common false-positive captures to suppress (these aren't real company names
# even if the regex picks them up).
_ACQUISITION_NAME_STOPLIST = frozenset({
    "M&A", "IPO", "USD", "JPY", "EUR", "FX", "TV", "AI", "IoT",
    "USA", "UK", "EU", "PS5", "PS4", "PSP", "VR",
})


def _extract_named_acquisitions(narrative: str) -> list[str]:
    """Pull distinct proper-noun acquisition names from the narrative.

    Returns the list of names mentioned alongside 買収 / の取得 / 完全子会社化
    that look like real company / brand names (capitalized English or
    bracketed Japanese). Used to verify the explanation didn't drop any
    of them.
    """
    out: list[str] = []
    seen: set[str] = set()
    for m in _NAMED_ACQUISITION_RE.finditer(narrative or ""):
        name = (m.group(1) or m.group(2) or "").strip()
        if not name or name in _ACQUISITION_NAME_STOPLIST:
            continue
        # De-dupe case-insensitively so "Crunchyroll" and "crunchyroll" don't
        # both count as separate omissions.
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def _check_named_acquisition_completeness(narrative: str,
                                          explanation_en: str,
                                          explanation_ja: str) -> dict | None:
    """For each named acquisition in the narrative (Crunchyroll, Bungie,
    AWAL, Som Livre, etc.), check that the explanation mentions it.

    Tightens the existing `acquisition_driver` rule which only checks that
    SOME acquisition is mentioned. The audit found cases where the LLM
    cited one acquisition (or a divestiture giving a one-time gain) and
    silently dropped another named acquisition in the same segment.
    """
    if not narrative:
        return None
    names = _extract_named_acquisitions(narrative)
    if not names:
        return None
    out = (explanation_en or "") + " " + (explanation_ja or "")
    out_lower = out.lower()
    missing = [n for n in names if n.lower() not in out_lower]
    if not missing:
        return None
    # Only warn when at least 2 named acquisitions exist OR when 1 named
    # acquisition is missing AND the explanation does mention SOME
    # acquisition (suggests the LLM picked a different one). For the
    # zero-acquisition-mentioned case the existing acquisition_driver
    # rule already fires.
    return {
        "rule": "named_acquisition_omission",
        "message": (
            "named acquisition(s) in the narrative were not surfaced in the "
            "explanation: " + ", ".join(missing[:5])
            + (f" (+{len(missing)-5} more)" if len(missing) > 5 else "")
        ),
    }


# Music-segment streaming attribution. Streaming is the music industry's
# primary growth driver post-2018; when the narrative mentions streaming
# revenue alongside the music segment, the explanation should reflect it.
_MUSIC_SEGMENT_NARRATIVE_RE = _re.compile(
    r"(?:music|音楽(?:分野|事業)?)", _re.IGNORECASE,
)
_STREAMING_NARRATIVE_RE = _re.compile(
    r"(ストリーミング|有料会員|配信(?:収入|サービス|事業)|"
    r"streaming|paid (?:subscription|subscriber)|subscription (?:revenue|service))",
    _re.IGNORECASE,
)
_STREAMING_OUTPUT_RE = _re.compile(
    r"(streaming|stream|paid subscriber|subscription|"
    r"ストリーミング|有料会員|配信)",
    _re.IGNORECASE,
)


def _check_streaming_music_driver(narrative: str,
                                  explanation_en: str,
                                  explanation_ja: str) -> dict | None:
    """When the narrative mentions music + streaming, the explanation must
    surface streaming as a driver. Audit found cases where Music growth
    was attributed only to FX / acquisitions while the narrative led with
    paid-streaming and ad-streaming COVID recovery."""
    if not narrative:
        return None
    if not _MUSIC_SEGMENT_NARRATIVE_RE.search(narrative):
        return None
    if not _STREAMING_NARRATIVE_RE.search(narrative):
        return None
    out = (explanation_en or "") + " " + (explanation_ja or "")
    if not _MUSIC_SEGMENT_NARRATIVE_RE.search(out):
        return None  # explanation didn't engage with music segment at all
    if _STREAMING_OUTPUT_RE.search(out):
        return None
    return {
        "rule": "music_streaming_driver",
        "message": "narrative attributes music-segment growth to streaming / paid-subscription revenue but explanation does not mention streaming",
    }


# Financial-segment misattribution. The audit caught the LLM blaming a
# subsidiary consolidation event for a Financial Services revenue decline,
# when the narrative actually attributed the decline to investment-account
# losses (separate-account / 特別勘定 / 運用益). Consolidation events that
# happened in the prev period CANNOT mechanically explain the curr period's
# decline relative to prev — but the LLM frequently grabs at them anyway.
_FINANCIAL_SEGMENT_OUTPUT_RE = _re.compile(
    r"(financial(?:[- ]services)?(?: arm| segment| services| business)?|"
    r"金融(?:分野|ビジネス|事業))",
    _re.IGNORECASE,
)
_FINANCIAL_DECLINE_OUTPUT_RE = _re.compile(
    r"(declin|fell|decreas|shrank|shrunk|dropped|"
    r"減少|減収|落ち込)",
    _re.IGNORECASE,
)
_CONSOLIDATION_ATTRIBUTION_OUTPUT_RE = _re.compile(
    r"(consolidation|wholly[- ]owned|fully (?:owned|consolidated)|"
    r"subsidiary[- ]ization|完全子会社化|子会社化|"
    r"SFH|SFGI)",
    _re.IGNORECASE,
)
_INVESTMENT_INCOME_NARRATIVE_RE = _re.compile(
    r"(特別勘定|運用益.{0,40}減少|"
    r"separate account|investment.{0,30}(?:income|gain|loss).{0,40}declin)",
    _re.IGNORECASE,
)

# Driver-side tokens that COULD legitimately appear in the EXPLANATION
# when discussing a Financial-segment decline. If the explanation cites
# consolidation as the cause but mentions NONE of these operational
# drivers, the consolidation attribution is suspect (see audit findings).
_INVESTMENT_INCOME_OUTPUT_RE = _re.compile(
    r"(separate account|特別勘定|"
    r"investment.{0,30}(?:income|gain|loss|return)|"
    r"運用(?:益|収益|損失)|Sony Life|ソニー生命|"
    r"insurance premium|保険料(?:収入)?|"
    r"underwriting|claims|policyholder)",
    _re.IGNORECASE,
)


def _check_financial_attribution_mismatch(narrative: str,
                                          explanation_en: str,
                                          explanation_ja: str) -> dict | None:
    """When explanation attributes a Financial-segment decline to a
    subsidiary-consolidation event, warn unless the explanation also
    surfaces a real operational driver (separate account, Sony Life
    revenue change, premium income, etc.).

    Two failure modes both trigger this rule:
      (A) Narrative cites a different cause and explanation didn't reflect it.
      (B) Explanation cites consolidation as the SOLE attribution without
          any operational driver — even if the narrative excerpt the
          post-check sees is truncated past the actual driver tokens, this
          structural pattern is suspicious because consolidation events
          that happened in the prev base year cannot mechanically explain
          a curr-period decline.

    Mode (B) was added after the audit found cases where narrative
    truncation was hiding the real driver from the post-check, allowing
    consolidation-only attribution to slip through.
    """
    if not (explanation_en or explanation_ja):
        return None
    out = (explanation_en or "") + " " + (explanation_ja or "")
    # Trigger: explanation mentions Financial Services + decline + consolidation
    if not _FINANCIAL_SEGMENT_OUTPUT_RE.search(out):
        return None
    if not _FINANCIAL_DECLINE_OUTPUT_RE.search(out):
        return None
    if not _CONSOLIDATION_ATTRIBUTION_OUTPUT_RE.search(out):
        return None

    narrative_has_actual_driver = bool(_INVESTMENT_INCOME_NARRATIVE_RE.search(narrative or ""))
    explanation_has_driver_token = bool(_INVESTMENT_INCOME_OUTPUT_RE.search(out))

    if narrative_has_actual_driver and not explanation_has_driver_token:
        # Mode A: narrative explicitly cites a different cause; explanation missed it.
        return {
            "rule": "financial_attribution_mismatch",
            "message": (
                "explanation attributes Financial-segment decline to subsidiary "
                "consolidation but narrative cites investment-account / "
                "separate-account / 運用益 losses as the actual driver"
            ),
        }
    if not explanation_has_driver_token:
        # Mode B: consolidation cited as sole attribution, no operational driver
        # named. Even if the narrative excerpt is truncated past the real cause,
        # the structural pattern is suspect — prev-period consolidation events
        # can't mechanically explain curr-period declines.
        return {
            "rule": "financial_attribution_mismatch",
            "message": (
                "explanation attributes Financial-segment decline to subsidiary "
                "consolidation as the sole cause without naming an operational "
                "driver (Sony Life / 特別勘定 / 運用益 / premium income). "
                "Consolidation events from the prev base year cannot mechanically "
                "explain a curr-period decline — needs a real driver from the filing"
            ),
        }
    return None


# Unit-discipline check. The advanced prompt has a STRICT RULE saying
# "never write 'X billion' for a value that is actually X trillion (and
# vice versa)" — but prompts only nudge. The Sony FY2021-22 audit caught
# the LLM writing "¥9,921.5 trillion" when the value was ¥9.92 trillion
# (i.e., 9,921.5 billion). This regex catches the most common variant:
# a comma-formatted number paired with "trillion" / 兆. No real Japanese
# company is in the quadrillion-yen range, so any number with thousands
# separators paired with "trillion" is almost certainly a billion that
# got mislabeled. Same applies to 兆/兆円 in Japanese.
_UNIT_TRILLION_OVERRUN_RE = _re.compile(
    r"(?:¥\s*)?(\d{1,3}(?:,\d{3})+(?:\.\d+)?)\s*(?:trillion|兆円?)",
    _re.IGNORECASE,
)


def _check_unit_discipline(explanation_en: str, explanation_ja: str) -> dict | None:
    """Catch the trillion/billion confusion: any comma-formatted number
    paired with 'trillion' / 兆 is a unit error.

    Examples this catches:
      - '¥9,921.5 trillion'   → should be billion (9,921.5B = 9.92T)
      - '1,234.5 trillion'    → almost certainly billion
      - '9,921億5,000万兆円'  → garbled scale

    Examples this does NOT catch (correct usage):
      - '¥9.9 trillion'       → no comma → fine
      - '1.5 trillion JPY'    → no comma → fine
    """
    out = (explanation_en or "") + " " + (explanation_ja or "")
    if not out.strip():
        return None
    m = _UNIT_TRILLION_OVERRUN_RE.search(out)
    if m is None:
        return None
    return {
        "rule": "unit_discipline_trillion",
        "message": (
            f"unit error suspected: '{m.group(0).strip()}' uses 'trillion'/兆 with a "
            "comma-formatted number — almost certainly a billion that got mislabeled "
            "(real Japanese filers are not in the quadrillion-yen range)"
        ),
    }


# Outlook citation rule. Per the senior's directive (2026-05-10), the outlook
# reasoning MUST cite at least one accounting item (勘定科目). This regex
# matches the standard P/L / BS vocabulary in EITHER language. The rule fires
# only when the outlook reasoning is non-empty (the empty case is handled by
# the structural emptiness check downstream).
_ACCOUNTING_ITEM_RE = _re.compile(
    r"(operating margin|net margin|ordinary margin|gross margin|"
    r"operating (?:income|profit)|net income|ordinary income|gross profit|"
    r"revenue|net sales|EPS|earnings per share|"
    r"goodwill|inventor(?:y|ies)|impairment|"
    r"interest[- ]bearing debt|borrowing(?:s)?|equity|net assets|"
    r"trade receivable(?:s)?|cash and (?:cash )?equivalents|"
    r"tangible (?:fixed )?assets?|intangible assets?|"
    r"comprehensive income|extraordinary loss|"
    # JA accounting vocabulary
    r"営業利益|経常利益|当期利益|純利益|"  # 営業利益/経常利益/当期利益/純利益
    r"売上高|売上|粗利|粗利益|"            # 売上高/売上/粗利
    r"営業利益率|利益率|利黤率|"        # 営業利益率/利益率
    r"のれん|有形(?:固定)?資産|無形(?:固定)?資産|"  # のれん/有形固定資産/無形固定資産
    r"棚卸(?:資産)?|在庫|"                                    # 棚卸資産/在庫
    r"有利子負債|借入(?:金)?|社債|"           # 有利子負債/借入(金)/社債
    r"純資産|自己資本|"                                  # 純資産/自己資本
    r"減損|特別損失|売掛)",                           # 減損/特別損失/売掛
    _re.IGNORECASE,
)


def _check_outlook_completeness(judgment: str | None,
                                outlook_reason_en: str,
                                outlook_reason_ja: str) -> dict | None:
    """The outlook reasoning is the agent's headline filter signal — it MUST
    be both populated AND cite at least one named 勘定科目 (accounting item).

    Per the senior's 2026-05-10 directive: the agent must explain WHY it
    judged 伸びる/伸びない citing both 勘定科目 and macro context. This rule
    catches the failure mode where the LLM emits the judgment but produces
    pure hand-waving prose with no specific accounting-item reference.

    Two failure modes:
      (a) outlook_reason_* is empty → "judgment without reasoning"
      (b) reason exists but no accounting item is named → "judgment without
          accounting evidence"

    The macro-context requirement is enforced by the prompt rule, not the
    post-check — macro keywords are too varied to regex reliably.
    """
    if not judgment:
        return None
    combined = ((outlook_reason_en or "") + " " + (outlook_reason_ja or "")).strip()
    if not combined:
        return {
            "rule": "outlook_reason_missing",
            "message": (
                f"outlook_judgment '{judgment}' was set but no reasoning text "
                "was produced — downstream filter has nothing to audit"
            ),
        }
    if not _ACCOUNTING_ITEM_RE.search(combined):
        return {
            "rule": "outlook_no_accounting_item",
            "message": (
                f"outlook_judgment '{judgment}' was set but the reasoning does "
                "not cite any specific accounting item (勘定科目). "
                "Per the senior directive every outlook call must name at "
                "least one P/L or BS line (operating margin, net income, "
                "goodwill, inventory, debt, etc.) as evidence."
            ),
        }
    return None


_STOCK_MENTION_RE = _re.compile(
    r"(stock|share price|the share|株価|the market may|market appears|"
    r"trading days following|investor (?:reaction|response)|"
    r"following the filing|after the filing|"
    r"\+\d+(?:\.\d+)?%|−\d+(?:\.\d+)?%|-\d+(?:\.\d+)?%)",
    _re.IGNORECASE,
)


def _check_stock_reaction_present(stock_pct: float | None,
                                  explanation_en: str,
                                  explanation_ja: str) -> dict | None:
    """When stock data was provided to the prompt, the explanation MUST
    discuss it. Catches the failure mode where the LLM exhausts its
    sentence budget on driver narration and skips the stock-reaction
    paragraph — the user's headline analytical value.

    Detection is loose on purpose: any of {percent figure with +/−, the
    word 'stock' / 'share price' / 株価, hedged-market phrasing like
    'the market may', or 'trading days following'} clears the rule.
    Rendering issues (LLM dropped to 'n/a' wording in prose) still pass —
    the goal is to catch silent skipping, not police phrasing.
    """
    if stock_pct is None:
        return None  # nothing to discuss
    out = (explanation_en or "") + " " + (explanation_ja or "")
    if not out.strip():
        return None  # explanation failed entirely; other rules fire
    if _STOCK_MENTION_RE.search(out):
        return None
    return {
        "rule": "stock_reaction_missing",
        "message": (
            f"stock moved {stock_pct:+.2f}% but explanation does not "
            "discuss the stock reaction at all (likely budget-pressure "
            "skip — model spent sentences on drivers and ran out)"
        ),
    }


def _check_foreign_tangent(narrative: str, explanation_en: str,
                           segments: list[dict] | None) -> dict | None:
    """Sentence-level foreign-tangent rule.

    The rule we want: foreign companies / countries SHOULD be mentioned when
    they are tied to a revenue or profit driver — a US acquisition that drove
    a segment, a subsidiary that contributes revenue, an FX impact, a foreign
    market the company operates in. Tangents — bare peer comparisons, market
    color, "as US carriers have done"-style references that don't connect to
    the actual numbers being explained — are what the user flagged.

    The test (verbatim from the user): "does removing this foreign-company
    sentence change the reader's understanding of where revenue/profit came
    from?" If no, it's a tangent and gets flagged. If yes, it's a driver and
    stays.

    Implementation: split the explanation into sentences. For each sentence
    containing a foreign token:
      (a) source / segment backing — if the token appears in the filing's
          narrative or segment names, the mention is anchored. Allow.
      (b) sentence-level driver context — attribution verbs (drove,
          contributed, led by), transaction nouns (acquisition, subsidiary,
          divestiture), exchange-rate tokens (FX, yen weakness), explicit
          revenue language ("revenue from US", "operations in China"), or
          a numeric figure in the same sentence. Any of these means the
          mention is doing attribution, not peer-color. Allow.
      (c) otherwise — bare comparison or market color. Flag, with the
          offending sentence quoted in the message so the maintainer can
          judge whether the heuristic was right.

    JA half is intentionally not checked: 米国/欧州/中国 etc. transliterate
    differently and our ASCII regex misses them; the EN check catches the
    same drift since the model writes both halves from the same scratchpad.
    """
    if not explanation_en:
        return None
    if not _FOREIGN_TOKEN_RE.search(explanation_en):
        return None  # no foreign tokens at all — fast path

    src_lower = (narrative or "").lower()
    seg_blob = " ".join(
        (s.get("name", "") + " " + s.get("name_ja", "")).lower()
        for s in (segments or [])
    )

    # Sentence-split. Rough — cuts on terminal punctuation followed by space,
    # which is fine for the LLM's prose. Edge cases (abbreviations, "U.S.")
    # mean we sometimes split a single semantic sentence into two halves;
    # since both halves get the same allow-list checks that's harmless.
    sentences = _re.split(r"(?<=[\.!?])\s+", explanation_en)

    flagged: list[tuple[str, list[str]]] = []
    for sent in sentences:
        hits = list(_FOREIGN_TOKEN_RE.finditer(sent))
        if not hits:
            continue

        # (a) Source / segment backing.
        backed = False
        for m in hits:
            tok = m.group(0).strip().lower()
            if tok and (tok in src_lower or tok in seg_blob):
                backed = True
                break
        if backed:
            continue

        # (b) Driver context at the sentence level.
        if _FOREIGN_DRIVER_INDICATORS_RE.search(sent):
            continue
        if _NUMERIC_ATTRIBUTION_RE.search(sent):
            continue

        # (c) Bare comparison / market color — flag.
        flagged.append((sent.strip(), [m.group(0).strip() for m in hits]))

    if not flagged:
        return None

    tokens = sorted({tok for _, toks in flagged for tok in toks})
    snippet = flagged[0][0]
    if len(snippet) > 120:
        snippet = snippet[:120] + "…"
    return {
        "rule": "foreign_tangent_check",
        "message": (
            "explanation references foreign company / market not tied to a "
            "revenue/profit driver (peer comparison or market color, not in "
            "filing): "
            + ", ".join(tokens[:5])
            + (f' — e.g. "{snippet}"' if snippet else "")
        ),
    }


def _check_narrative_coverage(
    narrative: str,
    explanation_en: str,
    explanation_ja: str,
    *,
    segments: list[dict] | None = None,
    divergence: bool = False,
    bs_yoy: dict | None = None,
    stock_pct: float | None = None,
    response_class: str | None = None,
    outlook_judgment: str | None = None,
    outlook_reason_en: str | None = None,
    outlook_reason_ja: str | None = None,
) -> list[dict]:
    """Run regex rules against (narrative, output) and return a list of
    coverage warnings. Empty list means the explanation passed every rule.

    Each warning: {"rule": str, "message": str}.
    """
    warnings: list[dict] = []
    src = narrative or ""
    out = (explanation_en or "") + " " + (explanation_ja or "")
    for rule in _COVERAGE_RULES:
        # Inverted rule: hallucinated-content check (output mentions consensus
        # without source backing).
        if rule.get("narrative_must_contain") is not None:
            if rule["output_re"].search(out) and not rule["narrative_must_contain"].search(src):
                warnings.append({"rule": rule["id"], "message": rule["warning"]})
            continue
        # Standard rule: narrative trigger must produce an output mention.
        nre = rule["narrative_re"]
        if nre is None:
            continue
        if nre.search(src) and not rule["output_re"].search(out):
            warnings.append({"rule": rule["id"], "message": rule["warning"]})

    # Phase A rules — richer inputs than the regex pairs above.
    # `response_class` derives the anomaly check; fall back to the legacy
    # boolean `divergence` for callers that haven't been updated yet.
    rc = response_class if response_class is not None else (
        "divergence" if divergence else "aligned"
    )
    is_anomaly = rc in ("divergence", "weak_response")
    for w in (
        _check_composition_opener(explanation_en, explanation_ja, bool(segments)),
        _check_divergence_addressed(rc, explanation_en, explanation_ja),
        _check_foreign_tangent(narrative, explanation_en, segments),
        _check_bs_citation(is_anomaly, bs_yoy, explanation_en, explanation_ja),
        _check_stock_reaction_present(stock_pct, explanation_en, explanation_ja),
        _check_named_acquisition_completeness(narrative, explanation_en, explanation_ja),
        _check_streaming_music_driver(narrative, explanation_en, explanation_ja),
        _check_financial_attribution_mismatch(narrative, explanation_en, explanation_ja),
        _check_unit_discipline(explanation_en, explanation_ja),
        _check_outlook_completeness(outlook_judgment, outlook_reason_en or "",
                                    outlook_reason_ja or ""),
    ):
        if w is not None:
            warnings.append(w)
    return warnings


def _bs_yoy_for_response(bs_yoy: dict | None) -> dict | None:
    """Shape the internal `_bs_yoy` dict into a JSON-friendly response payload.

    Drops nothing — the UI uses this to render the BS table with
    movers asterisked. Item ordering matches the prompt's display order
    (assets → tangible → intangible → goodwill → inventory → receivables
    → cash → debt → equity → impairment → extraordinary loss). Items the
    extractor didn't find are simply absent from `items`.
    """
    if not bs_yoy or not bs_yoy.get("items"):
        return None
    return {
        "items": bs_yoy["items"],
        "framework_prev": bs_yoy.get("framework_prev", "unknown"),
        "framework_curr": bs_yoy.get("framework_curr", "unknown"),
        "framework_changed": bs_yoy.get("framework_changed", False),
    }


def analyze_company(code: str, fund: dict[str, Any]) -> dict[str, Any]:
    if fund.get("filing_type") != ANNUAL_FILING_TYPE:
        return {
            "code": code,
            "name": fund.get("name", code),
            "error": f"not an annual securities report (filing_type={fund.get('filing_type')!r})",
        }

    prev_zip = Path(fund["prev_filing"]["zip_path"])
    curr_zip = Path(fund["curr_filing"]["zip_path"])
    filing_date = fund["curr_filing"]["filing_date"]

    segments, total_prev, total_curr = _segment_yoy(prev_zip, curr_zip)
    profit_status, revenue_delta_pct = _classify_revenue(total_prev, total_curr)
    scope_note = _build_revenue_scope_note(prev_zip, curr_zip, total_prev, total_curr)
    prev_op, curr_op, op_delta_pct = _op_profit_yoy(prev_zip, curr_zip)
    bs_yoy = _bs_yoy(prev_zip, curr_zip)
    pl_yoy = _pl_yoy(prev_zip, curr_zip)

    narrative = fund.get("curr_text", "") or fund.get("curr_raw_text", "") or ""
    stock = _stock_5d_move(code, filing_date)
    response_class = _stock_response_class(
        op_delta_pct, stock.get("stock_5d_return_pct"),
        revenue_delta_pct=revenue_delta_pct,
    )
    divergence = response_class == "divergence"
    response_anomaly = response_class in ("divergence", "weak_response")
    curr_period_end = fund.get("curr_filing", {}).get("period_end", "")
    try:
        expl = _explain_bilingual(
            build_prompt(total_prev, total_curr, revenue_delta_pct,
                         profit_status, segments, narrative,
                         stock.get("stock_5d_return_pct"), stock.get("stock_direction", ""),
                         scope_note=scope_note,
                         narrative_full=fund.get("curr_raw_text") or narrative,
                         prev_op=prev_op, curr_op=curr_op, op_delta_pct=op_delta_pct,
                         bs_yoy=bs_yoy, pl_yoy=pl_yoy,
                         curr_period_end=curr_period_end),
        )
    except Exception as e:
        log.warning("%s: LLM synthesis failed: %s", code, e)
        expl = dict(_EMPTY_EXPLANATIONS)

    coverage_warnings = _check_narrative_coverage(
        fund.get("curr_raw_text") or narrative,
        expl.get("explanation_advanced_en", ""),
        expl.get("explanation_advanced_ja", ""),
        segments=segments,
        divergence=divergence,
        bs_yoy=bs_yoy,
        stock_pct=stock.get("stock_5d_return_pct"),
        response_class=response_class,
        outlook_judgment=expl.get("outlook_judgment"),
        outlook_reason_en=expl.get("outlook_reason_en"),
        outlook_reason_ja=expl.get("outlook_reason_ja"),
    )
    if coverage_warnings:
        log.warning("%s narrative-coverage flags: %s",
                    code, [w["rule"] for w in coverage_warnings])

    return {
        "code": code,
        "name": fund.get("name", code),
        "fiscal_period": fund.get("fiscal_period", ""),
        "filing_date": filing_date,
        "prev_filing_date": fund["prev_filing"]["filing_date"],
        "prev_revenue": total_prev,
        "curr_revenue": total_curr,
        "revenue_delta_pct": round(revenue_delta_pct, 3),
        "profit_status": profit_status,
        "prev_op_profit": prev_op,
        "curr_op_profit": curr_op,
        "op_profit_delta_pct": round(op_delta_pct, 3) if op_delta_pct is not None else None,
        "profit_stock_divergence": divergence,
        "stock_response_class": response_class,
        "stock_response_anomaly": response_anomaly,
        # Forward-looking filter signal — primary downstream consumer.
        "outlook_judgment": expl.get("outlook_judgment", "uncertain"),
        "segments": [
            {
                "name": s["name"],
                "name_ja": s.get("name_ja", ""),
                "prev": s["prev"],
                "curr": s["curr"],
                "delta": s["delta"],
                "delta_pct": round(s["delta_pct"], 3),
            }
            for s in segments
        ],
        # Backward-compat shorthand (advanced English).
        "explanation": expl["explanation_advanced_en"],
        "explanation_en": expl["explanation_advanced_en"],
        "explanation_ja": expl["explanation_advanced_ja"],
        "revenue_scope_note": scope_note,
        "narrative_coverage_warnings": coverage_warnings,
        "bs_yoy": _bs_yoy_for_response(bs_yoy),
        "pl_yoy": _pl_yoy_for_response(pl_yoy),
        **expl,
        **stock,
        "source": "edinet_asr",
    }


def _name_for(code: str, fallback: str | None = None) -> str:
    for c in CONFIG.companies:
        if c.code == code:
            return c.name
    return fallback or code


# --- On-disk result cache ----------------------------------------------------
# Bump when agent behavior changes substantively (prompt rewrites, voting rule
# changes, new BS/PL extractors, etc.). Old cache files stay on disk; new
# cache_key won't match, so they're silently ignored.
_AGENT_CACHE_VERSION = "v5_2026-05-16_bs_quality"
_AGENT_CACHE_DIR = ROOT / "outputs" / "agent_cache"


def _agent_cache_key(code: str, min_year: int, skip_simplify: bool,
                     decision_cutoff_fy: int | None,
                     use_prompt_caching: bool = False) -> str:
    """Cache key includes a hash of the prompt template + AGENT_CACHE_VERSION,
    so a prompt edit auto-invalidates old results without manual cleanup.
    V2 (prompt-caching) results are stored under a separate key so an A/B
    test can read both V1 and V2 results without overwriting either."""
    from app.subagents.quiet_change_prompt import ADVANCED_PROMPT
    h = hashlib.sha256(ADVANCED_PROMPT.encode("utf-8")).hexdigest()[:12]
    cutoff_tag = "none" if decision_cutoff_fy is None else str(decision_cutoff_fy)
    v_tag = "v2cache" if use_prompt_caching else "v1"
    return (f"{code}_min{min_year}_simp{int(skip_simplify)}_"
            f"cutoff{cutoff_tag}_{v_tag}_{h}_{_AGENT_CACHE_VERSION}")


def _compute_confidence_for_pair(pair: dict) -> dict:
    """Compute a 3-factor confidence label for a confident verdict pair.

    Path C from Idea 4 diagnostic (2026-05-18): post-hoc confidence
    layer based on empirical predictors found from 56-call analysis.
    Pure post-processing; no LLM calls.

    Returns dict with confidence_label ("HIGH" / "MEDIUM" / "LOW" / None
    for uncertain verdicts) and confidence_factors detailing the three
    factor checks.
    """
    judgment = pair.get("outlook_judgment")
    if judgment not in ("growth_likely", "growth_unlikely"):
        return {"confidence_label": None, "confidence_factors": None}

    # Extract factors from structured data
    pc = pair.get("peer_comparison") or {}
    pc_my = pc.get("my") or {}
    pc_median = pc.get("sector_median") or {}
    peer_gap_pp = None
    if pc_my.get("op_margin_pct") is not None and pc_median.get("op_margin_pct") is not None:
        peer_gap_pp = pc_my["op_margin_pct"] - pc_median["op_margin_pct"]

    bs_hist = pair.get("bs_quality_history") or []
    goodwill_pct = bs_hist[-1].get("goodwill_to_equity_pct") if bs_hist else None

    cfo_ratios = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
    cfo_ni_ratio = cfo_ratios.get("curr")

    peer_pass = peer_gap_pp is not None and peer_gap_pp > 10.0
    goodwill_pass = (goodwill_pct is None or goodwill_pct < 30.0)
    cfo_pass = cfo_ni_ratio is not None and cfo_ni_ratio > 0.8

    score = int(peer_pass) + int(goodwill_pass) + int(cfo_pass)
    if score == 3:
        label = "HIGH"
    elif score == 2:
        label = "MEDIUM"
    else:
        label = "LOW"

    return {
        "confidence_label": label,
        "confidence_factors": {
            "score_out_of_3": score,
            "peer_level_gap_pp": round(peer_gap_pp, 2) if peer_gap_pp is not None else None,
            "peer_gap_passed_10pp": peer_pass,
            "goodwill_to_equity_pct": round(goodwill_pct, 2) if goodwill_pct is not None else None,
            "goodwill_under_30pct": goodwill_pass,
            "cfo_to_ni_ratio": round(cfo_ni_ratio, 3) if cfo_ni_ratio is not None else None,
            "cfo_over_0_8": cfo_pass,
        },
    }


def _compute_veto_for_pair(pair: dict) -> dict:
    """Asymmetric post-hoc veto rules (Phase 1, 2026-05-20).

    Pre-registered from misjudgment analysis on 56-call cohort:
      - GL Rule 5: growth_likely + (peer_gap <= 0 OR cfo_ni < 0.5) -> uncertain
        (catches 9/20 GL misses, 3/21 hits sacrificed, +10.9pp precision)
      - GL Rule 6: growth_likely + op_profit_yoy > +50% AND peer_gap < +10pp -> uncertain
        (catches 4 additional GL misses on top of R5, 0 hits sacrificed,
         brings GL precision to 72.0% on FULL, 68.4% on held-out TEST cohort.
         Intuition: very large op-profit jump from a non-peer-dominant
         position is a one-time surge, not structural growth.)
      - GU Rule 2: growth_unlikely + peer_gap > +5pp -> uncertain
        (catches 1/5 GU misses, 0 hits sacrificed)

    Veto only downgrades to "uncertain"; never upgrades. The pre-veto
    judgment is preserved in `original_judgment` for traceability.
    """
    judgment = pair.get("outlook_judgment")
    if judgment not in ("growth_likely", "growth_unlikely"):
        return {"veto_triggered": False, "veto_rule": None, "veto_reason": None,
                "original_judgment": judgment}

    pc = pair.get("peer_comparison") or {}
    pc_my = pc.get("my") or {}
    pc_med = pc.get("sector_median") or {}
    my_op = pc_my.get("op_margin_pct")
    med_op = pc_med.get("op_margin_pct")
    peer_gap = (my_op - med_op) if (my_op is not None and med_op is not None) else None

    cf_ratios = (pair.get("cashflow_yoy") or {}).get("ratios", {}).get("cfo_to_ni", {})
    cfo_ni = cf_ratios.get("curr")

    op_yoy = pair.get("op_profit_delta_pct")

    if judgment == "growth_likely":
        if peer_gap is not None and peer_gap <= 0.0:
            return {"veto_triggered": True, "veto_rule": "GL-R5-peer_gap",
                    "veto_reason": f"peer_gap={peer_gap:+.2f}pp ≤ 0 (below sector median)",
                    "original_judgment": judgment}
        if cfo_ni is not None and cfo_ni < 0.5:
            return {"veto_triggered": True, "veto_rule": "GL-R5-cfo_ni",
                    "veto_reason": f"cfo_ni={cfo_ni:.2f} < 0.5 (poor cash conversion)",
                    "original_judgment": judgment}
        if (op_yoy is not None and op_yoy > 50.0
                and peer_gap is not None and peer_gap < 10.0):
            return {"veto_triggered": True, "veto_rule": "GL-R6-unsustainable_surge",
                    "veto_reason": f"op_yoy={op_yoy:+.1f}% > 50% with peer_gap={peer_gap:+.2f}pp < 10pp "
                                   f"(one-time surge, not structural)",
                    "original_judgment": judgment}
        bs_hist = pair.get("bs_quality_history") or []
        gw_eq = bs_hist[-1].get("goodwill_to_equity_pct") if bs_hist else None
        if gw_eq is not None and gw_eq > 15.0:
            return {"veto_triggered": True, "veto_rule": "GL-R7-goodwill_exposure",
                    "veto_reason": f"goodwill/equity={gw_eq:.1f}% > 15% (impairment exposure)",
                    "original_judgment": judgment}
        # R8: op-margin trend declining. trend computed by caller against
        # the prior pair's my.op_margin_pct (None on first-year pairs).
        op_margin_trend = pair.get("op_margin_trend_pp")
        if op_margin_trend is not None and op_margin_trend < -1.0:
            return {"veto_triggered": True, "veto_rule": "GL-R8-margin_declining",
                    "veto_reason": f"op_margin_trend={op_margin_trend:+.2f}pp < -1.0pp (margin declining)",
                    "original_judgment": judgment}
    elif judgment == "growth_unlikely":
        if peer_gap is not None and peer_gap > 5.0:
            return {"veto_triggered": True, "veto_rule": "GU-R2-peer_gap",
                    "veto_reason": f"peer_gap={peer_gap:+.2f}pp > +5pp (strong peer dominance)",
                    "original_judgment": judgment}

    return {"veto_triggered": False, "veto_rule": None, "veto_reason": None,
            "original_judgment": judgment}


def _populate_op_margin_trend(result: dict) -> None:
    """Compute op_margin_trend_pp on each pair = current.my.op_margin -
    prior pair's my.op_margin for the same ticker. Sets None on the
    earliest pair (no prior to diff against). Used by GL-R8 veto.
    """
    pairs = []
    for pair in result.get("pairs", []):
        if pair.get("history_only"):
            continue
        curr_fy = pair.get("curr_fiscal_year")
        if curr_fy is None:
            continue
        pc = pair.get("peer_comparison") or {}
        my = pc.get("my") or {}
        pairs.append((curr_fy, my.get("op_margin_pct"), pair))
    pairs.sort(key=lambda x: x[0])
    prior_op_m = None
    for curr_fy, op_m, pair in pairs:
        if "op_margin_trend_pp" not in pair:
            pair["op_margin_trend_pp"] = (op_m - prior_op_m) \
                if (op_m is not None and prior_op_m is not None) else None
        prior_op_m = op_m


def _enrich_pairs_with_confidence(result: dict) -> dict:
    """Add confidence_label + confidence_factors + veto fields to each pair.

    Idempotent: pairs already enriched are left unchanged. Applied to both
    fresh runs and cache-loaded results so older cache files pick up the
    fields on next read.

    Veto application: if a veto fires, `outlook_judgment` is replaced with
    "uncertain" and the original verdict is preserved in `original_judgment`.
    """
    _populate_op_margin_trend(result)
    for pair in result.get("pairs", []):
        if "confidence_label" not in pair:
            enrichment = _compute_confidence_for_pair(pair)
            pair.update(enrichment)
        if "veto_triggered" not in pair:
            veto = _compute_veto_for_pair(pair)
            pair.update(veto)
            if veto["veto_triggered"]:
                pair["outlook_judgment"] = "uncertain"
    return result


def _load_agent_cache(key: str) -> dict | None:
    p = _AGENT_CACHE_DIR / f"{key}.json"
    if not p.exists():
        return None
    try:
        import json as _j
        return _j.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_agent_cache(key: str, result: dict) -> None:
    _AGENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _AGENT_CACHE_DIR / f"{key}.json"
    try:
        import json as _j
        p.write_text(_j.dumps(result, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    except Exception as e:
        log.warning("agent cache write failed for %s: %s", key, e)


def analyze_company_multi_year(
    code: str, min_year: int = 2020, run_tests: bool = False,
    skip_simplify: bool = True,
    decision_cutoff_fy: int | None = None,
    use_cache: bool = True,
    use_prompt_caching: bool = False,
) -> dict[str, Any]:
    """Walk every annual securities report (有価証券報告書) for `code`, build
    a per-year revenue series, and produce one row per consecutive YoY pair
    with: revenue delta, profit/loss/flat status, segments, LLM 'why'
    explanation, and 5-trading-day post-filing stock direction.

    Years before `min_year` (period_end year) are dropped — agent default
    is 2020 onward (covers 2020 through whatever the most-recent ASR is).

    On-disk result cache (use_cache=True, default): the full result dict is
    persisted under outputs/agent_cache/. Re-runs on the same ticker with
    the same args + prompt template return cached output, saving 100% of
    LLM cost. Set use_cache=False to force a fresh run.
    """
    cache_key = _agent_cache_key(code, min_year, skip_simplify, decision_cutoff_fy,
                                 use_prompt_caching=use_prompt_caching)
    if use_cache:
        cached = _load_agent_cache(cache_key)
        if cached is not None:
            log.info("agent cache HIT for %s (key=%s)", code, cache_key[:30])
            cached["_from_cache"] = True
            # Path C (Idea 4): enrich pairs with confidence_label if missing
            cached = _enrich_pairs_with_confidence(cached)
            return cached
    # Source switch (2026-05-10): the EDINET auto-fetch is disabled because
    # ASR data is already populated by ``fetch_tempest.py`` into the Tempest
    # cache. ``load_asr_series`` accepts a bare ticker (the .name of the
    # folder path) and reads ``data/tempest/<code>/``, so the folder argument
    # below is a synthetic Path — never created on disk, just used to carry
    # the code through the legacy interface.
    folder = ROOT / "data" / "tempest" / code
    fetch_report: dict | None = None

    full_series = load_asr_series(folder)
    series = [s for s in full_series if int(s["period_end"][:4]) >= min_year]
    if len(series) < 2:
        msg = f"need >=2 annual reports from {min_year}+, found {len(series)}"
        if fetch_report and fetch_report.get("still_missing_years"):
            msg += f". EDINET search did not find ASRs for FY{fetch_report['still_missing_years']} — verify the company filed in those years."
        return {"code": code, "error": msg}

    # Pull the restated multi-year revenue history from the LATEST ASR. This
    # gives us a single consistent accounting basis (e.g., post-IFRS 17
    # restatement for Sony) — same numbers the company quotes in IR materials
    # and that appear in the latest filing's 主要な経営指標等の推移 table.
    # When this lookup succeeds, prev/curr revenue values come from this
    # restated history (matching the latest PDF). Falls back to per-ASR
    # extraction if the latest ASR doesn't expose a multi-year summary.
    latest_zip = Path(series[-1]["zip_path"])
    history_list = extract_revenue_history_from_zip_path(latest_zip)
    history_by_year: dict[int, float] = {h["fiscal_year"]: h["revenue"] for h in history_list}
    using_restated = bool(history_by_year)

    # Build the per-year revenue snapshot table (used by the chart). Start
    # from the per-ZIP series, then layer in any history-only years that fall
    # in the requested window (≥min_year) but have no local ZIP — these come
    # from the latest ASR's 5-year-history table. They get charted but no
    # YoY pair (no prev ZIP → no segments / no LLM).
    series_years = {int(s["period_end"][:4]) for s in series}
    years: list[dict[str, Any]] = [
        {
            "fiscal_year": int(s["period_end"][:4]),
            "filing_date": s["filing_date"],
            "period_end": s["period_end"],
            "revenue": history_by_year.get(int(s["period_end"][:4]), s["revenue"]),
            "chart_only": False,
        }
        for s in series
    ]
    history_only_years: list[int] = []
    for h in history_list:
        yr = h["fiscal_year"]
        if yr >= min_year and yr not in series_years:
            years.append({
                "fiscal_year": yr,
                "filing_date": "",
                "period_end": h["period_end"],
                "revenue": h["revenue"],
                "chart_only": True,
            })
            history_only_years.append(yr)
    years.sort(key=lambda y: y["fiscal_year"])
    history_only_years.sort()

    # Lever 3 (2026-05-11) — sector cyclicality guidance, looked up ONCE per
    # ticker. None when the company isn't in a cyclical sector (most companies).
    industry_context = _build_industry_context_for_code(code)

    # Lever 2 (2026-05-11) — pre-compute the multi-year operating-margin
    # trajectory ONCE per ticker so it can be passed into every pair's
    # prompt. Iterates the cached PL extracts for each year in the series;
    # no LLM calls.
    #
    # 2026-05-15 (Phase 1 broader-context) — extended to also collect
    # revenue, net-margin %, and CFO/NI ratio per year so the prompt block
    # can show revenue YoY % + op margin + net margin in one table, and
    # the cash-flow block can flag the '< 0.8 for 2+ consecutive years'
    # earnings-quality pattern. Tempest CF coverage starts ~FY2023 for
    # most filers, so older years will have cfo_to_ni_ratio = None — the
    # detector skips them, no false positives.
    margin_trajectory: list[dict[str, Any]] = []
    cashflow_history: list[dict[str, Any]] = []
    bs_quality_history: list[dict[str, Any]] = []  # Phase 6 (2026-05-16)
    for s in series:
        zp = Path(s["zip_path"])
        fy = int(s["period_end"][:4])
        try:
            pl = extract_pl_from_zip_path(zp)
        except Exception:
            pl = {"items": {}, "derived": {}}
        items = pl.get("items", {})
        derived = pl.get("derived", {})
        rev = items.get("revenue")
        op = items.get("operating_income")
        if rev and rev > 0 and op is not None:
            margin_trajectory.append({
                "fiscal_year":    fy,
                "revenue":        rev,
                "op_margin_pct":  op / rev * 100.0,
                "net_margin_pct": derived.get("net_margin_pct"),
            })
        try:
            cf = extract_cashflow_from_zip_path(zp)
            cashflow_history.append({
                "fiscal_year":       fy,
                "cfo_to_ni_ratio":   cf.get("derived", {}).get("cfo_to_ni_ratio"),
            })
        except Exception:
            cashflow_history.append({"fiscal_year": fy, "cfo_to_ni_ratio": None})

        # Phase 6 (2026-05-16) — collect per-year BS items + segment shares
        # for downstream balance-sheet-quality + concentration trend
        # computation. All extractors are cache-hits (no LLM, no API call).
        try:
            bs = extract_balance_sheet_from_zip_path(zp)
        except Exception:
            bs = {"items": {}}
        bs_items = bs.get("items", {})
        try:
            seg_rows, _seg_prev_total, seg_curr_total = _segment_yoy(zp, zp)
            # `_segment_yoy(zp, zp)` returns the current-year segment shares;
            # we only need `curr` shares so prev==curr is fine here.
            seg_shares = []
            if seg_curr_total and seg_curr_total > 0:
                for r in seg_rows:
                    s_val = r.get("curr") or 0.0
                    if s_val > 0:
                        seg_shares.append(s_val / seg_curr_total)
        except Exception:
            seg_shares = []
        bs_quality_history.append({
            "fiscal_year":         fy,
            "revenue":             rev,
            "goodwill":            bs_items.get("goodwill"),
            "equity":              bs_items.get("equity"),
            "inventory":           bs_items.get("inventory"),
            "trade_receivables":   bs_items.get("trade_receivables"),
            "segment_shares":      seg_shares,   # list of fractions summing to ~1
        })

    # Per-pair analysis.
    pairs: list[dict[str, Any]] = []
    pair_zips: list[tuple[str, str]] = []   # for self-tests below
    for prev, curr in zip(series, series[1:]):
        prev_zip = Path(prev["zip_path"])
        curr_zip = Path(curr["zip_path"])
        pair_zips.append((str(prev_zip), str(curr_zip)))
        segments, total_prev, total_curr = _segment_yoy(prev_zip, curr_zip)
        # Prefer the headline revenue we already extracted (matches the chart).
        if total_prev == 0:
            total_prev = prev["revenue"]
        if total_curr == 0:
            total_curr = curr["revenue"]
        # Override with restated history values when available — this is the
        # whole point of the restated-history lookup above. Comparison years
        # are then on the same accounting basis.
        #
        # IMPORTANT: history_by_year is keyed by Tempest's fiscal_year field,
        # which uses the Japanese "year-started" convention (FY2024 = period
        # ending March 2025). The user-facing labels below still use
        # period_end[:4] (calendar-year convention, "FY2025" = Mar 2025) to
        # match the UI's formatFY() — but the LOOKUP must use fiscal_year or
        # the keys won't match and we'll silently fall through to the FY-N+1
        # row's revenue (the bug that produced revenue Δ +0.00% on the
        # latest year of the backtest, 2026-05-10).
        hist_key_prev = prev.get("fiscal_year")
        hist_key_curr = curr.get("fiscal_year")
        if hist_key_prev is not None and hist_key_prev in history_by_year:
            total_prev = history_by_year[hist_key_prev]
        if hist_key_curr is not None and hist_key_curr in history_by_year:
            total_curr = history_by_year[hist_key_curr]
        profit_status, revenue_delta_pct = _classify_revenue(total_prev, total_curr)
        scope_note = _build_revenue_scope_note(prev_zip, curr_zip, total_prev, total_curr)
        prev_op, curr_op, op_delta_pct = _op_profit_yoy(prev_zip, curr_zip)
        bs_yoy = _bs_yoy(prev_zip, curr_zip)
        pl_yoy = _pl_yoy(prev_zip, curr_zip)
        cf_yoy = _cashflow_yoy(prev_zip, curr_zip)
        narrative = curr["qualitative_text"]
        stock = _stock_5d_move(code, curr["filing_date"])
        response_class = _stock_response_class(
            op_delta_pct, stock.get("stock_5d_return_pct"),
            revenue_delta_pct=revenue_delta_pct,
        )
        divergence = response_class == "divergence"
        response_anomaly = response_class in ("divergence", "weak_response")
        # Trim trajectory to years <= curr_year so we don't leak future data
        # into the LLM's view of historical context.
        curr_fy = int(curr["period_end"][:4])
        traj_for_pair = [r for r in margin_trajectory if r["fiscal_year"] <= curr_fy]
        cfo_quality = _detect_cfo_ni_low_quality(cashflow_history, curr_fy)

        # Phase 2 (2026-05-15) — peer comparison. Pull this ticker's
        # current-FY metrics from the trajectory we already built, then
        # ask for sector medians at the same FY. Returns None when peer
        # set < 5 (min-peer-count rule) → prompt skips the block entirely.
        my_curr_traj = next((r for r in traj_for_pair if r["fiscal_year"] == curr_fy),
                            None)
        my_prev_traj = next((r for r in traj_for_pair
                             if r["fiscal_year"] == curr_fy - 1), None)
        my_rev_yoy = None
        my_op_pp = None
        if (my_curr_traj is not None and my_prev_traj is not None
                and my_prev_traj.get("revenue") and my_prev_traj["revenue"] > 0):
            my_rev_yoy = ((my_curr_traj["revenue"] - my_prev_traj["revenue"])
                          / my_prev_traj["revenue"] * 100.0)
            if my_curr_traj.get("op_margin_pct") is not None and \
               my_prev_traj.get("op_margin_pct") is not None:
                my_op_pp = my_curr_traj["op_margin_pct"] - my_prev_traj["op_margin_pct"]
        peer_data = _peer_block_inputs(
            code=code, curr_fy=curr_fy,
            my_revenue_yoy=my_rev_yoy,
            my_op_margin=(my_curr_traj or {}).get("op_margin_pct"),
            my_op_margin_pp_delta=my_op_pp,
            my_net_margin=(my_curr_traj or {}).get("net_margin_pct"),
        )
        # Phase 5 (qualitative text injection) was rolled back 2026-05-16
        # after a 12-ticker A/B showed ~4% real citation rate. The helper
        # functions `_qualitative_signals_yoy` and `_build_qualitative_
        # signals_block` are intentionally retained for a future structured-
        # diff retry, but are NOT called in the production pipeline. The
        # call here used to do wasted file I/O every pair — removed
        # 2026-05-16 audit cleanup.

        # Phase 6 (2026-05-16) — derive structured balance-sheet quality +
        # segment-concentration trend for the current pair's window. Trimmed
        # to years <= curr_fy so we don't leak future data.
        bs_quality_for_pair = _compute_bs_quality_history(
            bs_quality_history, curr_fiscal_year=curr_fy,
        )
        # Backtest cost saver: outcome pairs (after the decision cutoff) are
        # only used for raw revenue + stock numbers when scoring HIT/MISS;
        # their LLM judgment is never consumed. Skip the LLM call entirely
        # for those pairs. Halves backtest LLM cost on a typical 4-pair
        # company with cutoff FY2023.
        is_outcome_only = (decision_cutoff_fy is not None
                           and curr_fy > decision_cutoff_fy)
        if is_outcome_only:
            expl = dict(_EMPTY_EXPLANATIONS)
        else:
            try:
                if use_prompt_caching:
                    system_text, user_text = build_advanced_v2(
                        total_prev, total_curr, revenue_delta_pct,
                        profit_status, segments, narrative,
                        stock.get("stock_5d_return_pct"), stock.get("stock_direction", ""),
                        scope_note=scope_note,
                        narrative_full=curr.get("qualitative_text_full") or narrative,
                        prev_op=prev_op, curr_op=curr_op, op_delta_pct=op_delta_pct,
                        bs_yoy=bs_yoy, pl_yoy=pl_yoy,
                        cashflow_yoy=cf_yoy, cfo_quality=cfo_quality,
                        peer_data=peer_data,
                        bs_quality_history=bs_quality_for_pair,
                        curr_period_end=curr["period_end"],
                        margin_trajectory=traj_for_pair,
                        curr_fiscal_year=curr_fy,
                        industry_context=industry_context,
                    )
                    expl = _explain_bilingual(
                        user_text, skip_simplify=skip_simplify,
                        system_prompt=system_text,
                    )
                else:
                    expl = _explain_bilingual(
                        build_prompt(total_prev, total_curr, revenue_delta_pct,
                                     profit_status, segments, narrative,
                                     stock.get("stock_5d_return_pct"), stock.get("stock_direction", ""),
                                     scope_note=scope_note,
                                     narrative_full=curr.get("qualitative_text_full") or narrative,
                                     prev_op=prev_op, curr_op=curr_op, op_delta_pct=op_delta_pct,
                                     bs_yoy=bs_yoy, pl_yoy=pl_yoy,
                                     cashflow_yoy=cf_yoy, cfo_quality=cfo_quality,
                                     peer_data=peer_data,
                                     bs_quality_history=bs_quality_for_pair,
                                     curr_period_end=curr["period_end"],
                                     margin_trajectory=traj_for_pair,
                                     curr_fiscal_year=curr_fy,
                                     industry_context=industry_context),
                        skip_simplify=skip_simplify,
                    )
            except Exception as e:
                log.warning("%s %s LLM failed: %s", code, curr["filing_date"], e)
                expl = dict(_EMPTY_EXPLANATIONS)
        coverage_warnings = _check_narrative_coverage(
            curr.get("qualitative_text_full") or narrative,
            expl.get("explanation_advanced_en", ""),
            expl.get("explanation_advanced_ja", ""),
            segments=segments,
            divergence=divergence,
            bs_yoy=bs_yoy,
            stock_pct=stock.get("stock_5d_return_pct"),
            response_class=response_class,
            outlook_judgment=expl.get("outlook_judgment"),
            outlook_reason_en=expl.get("outlook_reason_en"),
            outlook_reason_ja=expl.get("outlook_reason_ja"),
        )
        if coverage_warnings:
            log.warning("%s %s narrative-coverage flags: %s",
                        code, curr["filing_date"],
                        [w["rule"] for w in coverage_warnings])
        pairs.append({
            "prev_fiscal_year": int(prev["period_end"][:4]),
            "curr_fiscal_year": int(curr["period_end"][:4]),
            "prev_period_end":  prev["period_end"],
            "curr_period_end":  curr["period_end"],
            "prev_filing_date": prev["filing_date"],
            "curr_filing_date": curr["filing_date"],
            "prev_revenue": total_prev,
            "curr_revenue": total_curr,
            "revenue_delta_pct": round(revenue_delta_pct, 3),
            "profit_status": profit_status,
            "prev_op_profit": prev_op,
            "curr_op_profit": curr_op,
            "op_profit_delta_pct": round(op_delta_pct, 3) if op_delta_pct is not None else None,
            "profit_stock_divergence": divergence,
            "stock_response_class": response_class,
            "stock_response_anomaly": response_anomaly,
            "outlook_judgment": expl.get("outlook_judgment", "uncertain"),
            "segments": [
                {"name": s["name"], "name_ja": s.get("name_ja", ""),
                 "prev": s["prev"], "curr": s["curr"],
                 "delta": s["delta"], "delta_pct": round(s["delta_pct"], 3)}
                for s in segments
            ],
            "explanation": expl["explanation_advanced_en"],   # backward-compat
            "explanation_en": expl["explanation_advanced_en"],
            "explanation_ja": expl["explanation_advanced_ja"],
            "revenue_scope_note": scope_note,
            "narrative_coverage_warnings": coverage_warnings,
            "bs_yoy": _bs_yoy_for_response(bs_yoy),
            "pl_yoy": _pl_yoy_for_response(pl_yoy),
            "cashflow_yoy": _cashflow_yoy_for_response(cf_yoy),
            "cfo_quality_flag": cfo_quality,
            "peer_comparison": peer_data,
            "bs_quality_history": bs_quality_for_pair,
            **expl,
            **stock,
        })
        if not is_outcome_only:
            time.sleep(1)

    # Synthesize "history-only" pairs for years where we lack a local ZIP but
    # the latest ASR's 5-year-history table exposes the revenue. These give
    # the user a visible row + Δ% for FY2022→FY2023 even when only the 2023+
    # ZIPs are downloaded. No segments / no LLM / no stock — UI flags the
    # row as partial.
    real_pair_years = {(p["prev_fiscal_year"], p["curr_fiscal_year"]) for p in pairs}
    if history_by_year:
        sorted_hist_years = sorted(history_by_year.keys())
        for prev_year, curr_year in zip(sorted_hist_years, sorted_hist_years[1:]):
            if prev_year < min_year:
                continue
            if (prev_year, curr_year) in real_pair_years:
                continue
            tp = float(history_by_year[prev_year])
            tc = float(history_by_year[curr_year])
            ps, dp = _classify_revenue(tp, tc)
            pairs.append({
                "prev_fiscal_year": prev_year, "curr_fiscal_year": curr_year,
                "prev_period_end": f"{prev_year}-03-31", "curr_period_end": f"{curr_year}-03-31",
                "prev_filing_date": "", "curr_filing_date": "",
                "prev_revenue": tp, "curr_revenue": tc,
                "revenue_delta_pct": round(dp, 3), "profit_status": ps,
                "prev_op_profit": None, "curr_op_profit": None,
                "op_profit_delta_pct": None, "profit_stock_divergence": False,
                "stock_response_class": "n/a", "stock_response_anomaly": False,
                "outlook_judgment": "uncertain",
                "outlook_reason_en": "", "outlook_reason_ja": "",
                "segments": [], "revenue_scope_note": None,
                "bs_yoy": None,
                "pl_yoy": None,
                "explanation": "", "explanation_en": "", "explanation_ja": "",
                "explanation_simple_en": "", "explanation_simple_ja": "",
                "explanation_advanced_en": "", "explanation_advanced_ja": "",
                "stock_5d_return_pct": None, "stock_direction": "unknown",
                "anchor_date": None, "end_date": None,
                "history_only": True,
            })
            pair_zips.append((None, None))
    pairs.sort(key=lambda p: p["curr_fiscal_year"])
    # Re-align pair_zips to the now-sorted pairs order. History-only pairs map
    # to (None, None); real pairs look up their ZIP paths via filing_date.
    fd_to_zip = {s["filing_date"]: s["zip_path"] for s in series}
    pair_zips = [
        (None, None) if p.get("history_only")
        else (fd_to_zip.get(p["prev_filing_date"]), fd_to_zip.get(p["curr_filing_date"]))
        for p in pairs
    ]

    # Optional self-tests — internal-consistency checks per pair.
    if run_tests:
        from app.subagents.quiet_change_tests import run_pair_tests
        for p, (pz, cz) in zip(pairs, pair_zips):
            if p.get("history_only"):
                # Skip per-pair tests for synthetic history-only rows — no
                # segments/LLM/stock to check. Surface a single informational
                # check so the test panel still renders.
                p["test_results"] = {
                    "checks": [{
                        "name": "History-only pair — full analysis skipped",
                        "name_ja": "履歴のみのペア — 完全な分析はスキップ",
                        "passed": True,
                        "detail": "", "detail_ja": "",
                        "evidence": {
                            "reason": "no local ZIP for FY{0} → no segments / no LLM / no stock data".format(p["prev_fiscal_year"]),
                            "prev_revenue (JPY)": f"{p['prev_revenue']:,.0f}",
                            "curr_revenue (JPY)": f"{p['curr_revenue']:,.0f}",
                            "source": "latest ASR's 5-year-history table",
                        },
                    }],
                    "passed": 1, "total": 1, "all_passed": True,
                }
                continue
            p["test_results"] = run_pair_tests(
                code, p, prev_zip=pz, curr_zip=cz,
                latest_zip=str(latest_zip) if using_restated else None,
                history_by_year=history_by_year if using_restated else None,
            )

    # Surface gaps so the UI can tell the user "you asked for FY2022 but
    # don't have that ZIP downloaded — chart shows it from history table".
    earliest_pair_year = pairs[0]["prev_fiscal_year"] if pairs else None
    result = {
        "code": code,
        "name": _name_for(code),
        "min_year": min_year,
        "years": years,
        "pairs": pairs,
        "history_only_years": history_only_years,
        "earliest_pair_year": earliest_pair_year,
        "fetch_report": fetch_report,
        # When True, prev/curr revenues come from the latest ASR's restated
        # 5-year-history (matches the IR/news convention). When False, we fell
        # back to per-ASR as-reported values (e.g., latest ASR didn't expose
        # a multi-year summary tag).
        "using_restated_history": using_restated,
        "source": "edinet_asr",
    }
    # Path C (Idea 4): enrich pairs with confidence_label
    result = _enrich_pairs_with_confidence(result)
    # Save to on-disk cache. Errors aren't cached (the early-return error
    # path above skips this block). Re-runs return this dict instantly.
    if use_cache:
        _save_agent_cache(cache_key, result)
    return result


# ----------------------------------------------------------------------------
# Quarterly mode (mid-year reports). Per senior 2026-05-10: 四半期報告書 +
# 半期報告書 give 2-3× more decision points per ticker per year, catching
# margin compression / recovery faster than the annual-only pipeline. Reuses
# the same prompt / coverage rules / outlook fields as annual; the only
# difference is that segments and full BS are typically NOT in quarterly
# filings — the prompt's empty-fallback wording handles those gracefully.
# ----------------------------------------------------------------------------
_PL_MOVER_PCT_THRESHOLD_Q = 25.0          # Same as annual — quarterly swings are wider so ≥25% is meaningful
_PL_MOVER_MARGIN_PP_THRESHOLD_Q = 1.5      # Same threshold; pp moves in quarterly margins compress like annual


def _pl_yoy_from_quarterly_pair(prev: dict, curr: dict) -> dict:
    """Build the same `pl_yoy` dict shape `_pl_yoy` returns, but from two
    quarterly snapshots (one per same-quarter-prior-year + current).

    Quarterly Tempest data exposes net_sales, operating_profit, net income,
    EPS, total_assets, equity. We map the four most analyst-relevant onto
    the prompt's PL panel; segments and granular BS items aren't available
    quarterly so the prompt sees only PL + margin trend.
    """
    items: dict[str, dict] = {}
    margins: dict[str, dict] = {}

    pairs_to_compare = [
        ("revenue",          prev.get("revenue"),          curr.get("revenue")),
        ("operating_income", prev.get("operating_profit"), curr.get("operating_profit")),
        ("net_income",       prev.get("net_income"),       curr.get("net_income")),
        ("basic_eps",        prev.get("eps"),              curr.get("eps")),
    ]
    for key, prev_v, curr_v in pairs_to_compare:
        if prev_v is None and curr_v is None:
            continue
        delta_pct: float | None = None
        if prev_v is not None and curr_v is not None and prev_v != 0:
            delta_pct = (curr_v - prev_v) / abs(prev_v) * 100.0
        is_mover = False
        if delta_pct is not None and abs(delta_pct) >= _PL_MOVER_PCT_THRESHOLD_Q:
            is_mover = True
        if key == "net_income":
            if (prev_v is not None and prev_v < 0) or (curr_v is not None and curr_v < 0):
                is_mover = True
        items[key] = {"prev": prev_v, "curr": curr_v,
                      "delta_pct": delta_pct, "is_mover": is_mover}

    rev_prev = prev.get("revenue")
    rev_curr = curr.get("revenue")
    if rev_prev and rev_prev > 0 and rev_curr and rev_curr > 0:
        for num_key, margin_key in (
            ("operating_profit", "op_margin_pct"),
            ("net_income",       "net_margin_pct"),
        ):
            prev_num = prev.get(num_key)
            curr_num = curr.get(num_key)
            if prev_num is None or curr_num is None:
                continue
            prev_pct = prev_num / rev_prev * 100.0
            curr_pct = curr_num / rev_curr * 100.0
            pp_delta = curr_pct - prev_pct
            is_mover = bool(abs(pp_delta) >= _PL_MOVER_MARGIN_PP_THRESHOLD_Q)
            margins[margin_key] = {"prev": prev_pct, "curr": curr_pct,
                                   "pp_delta": pp_delta, "is_mover": is_mover}
    return {"items": items, "margins": margins,
            "prev_missing": [], "curr_missing": []}


def analyze_company_quarterly(code: str, min_year: int = 2020) -> dict[str, Any]:
    """Walk every quarterly YoY pair (Q_N vs Q_N prior year) for `code`,
    build a per-quarter outlook judgment via the same LLM prompt the annual
    pipeline uses.

    Returns the same shape as `analyze_company_multi_year` but with one
    entry per quarterly pair rather than per annual pair, plus extra
    `prev_fiscal_quarter` / `curr_fiscal_quarter` fields. Segments and BS
    panels are not available quarterly — passed as empty so the prompt's
    fallback wording fires.
    """
    series = load_quarterly_series(code)
    series = [s for s in series if int(s["period_end"][:4]) >= min_year]
    pair_list = make_quarterly_yoy_pairs(series)
    if not pair_list:
        return {"code": code, "name": _name_for(code),
                "error": f"no quarterly YoY pairs available from {min_year}+"}

    out_pairs: list[dict[str, Any]] = []
    for prev_q, curr_q in pair_list:
        revenue_delta_pct = (curr_q["revenue"] - prev_q["revenue"]) / prev_q["revenue"] * 100.0 if prev_q["revenue"] else 0.0
        profit_status = "profit" if revenue_delta_pct > 0 else ("loss" if revenue_delta_pct < 0 else "flat")

        prev_op = prev_q.get("operating_profit")
        curr_op = curr_q.get("operating_profit")
        op_delta_pct: float | None = None
        if prev_op is not None and curr_op is not None and prev_op != 0:
            op_delta_pct = (curr_op - prev_op) / abs(prev_op) * 100.0

        pl_yoy = _pl_yoy_from_quarterly_pair(prev_q, curr_q)
        stock = _stock_5d_move(code, curr_q["filing_date"])
        response_class = _stock_response_class(
            op_delta_pct, stock.get("stock_5d_return_pct"),
            revenue_delta_pct=revenue_delta_pct,
        )

        try:
            expl = _explain_bilingual(
                build_prompt(prev_q["revenue"], curr_q["revenue"], revenue_delta_pct,
                             profit_status, [], "",   # no segments / no narrative quarterly
                             stock.get("stock_5d_return_pct"),
                             stock.get("stock_direction", ""),
                             scope_note=None,
                             narrative_full=None,
                             prev_op=prev_op, curr_op=curr_op, op_delta_pct=op_delta_pct,
                             bs_yoy=None,            # not available quarterly
                             pl_yoy=pl_yoy,
                             curr_period_end=curr_q["period_end"]),
            )
        except Exception as e:
            log.warning("%s %s quarterly LLM failed: %s",
                        code, curr_q["filing_date"], e)
            expl = dict(_EMPTY_EXPLANATIONS)

        out_pairs.append({
            "prev_fiscal_year":    prev_q["fiscal_year"],
            "curr_fiscal_year":    curr_q["fiscal_year"],
            "prev_fiscal_quarter": prev_q["fiscal_quarter"],
            "curr_fiscal_quarter": curr_q["fiscal_quarter"],
            "prev_period_end":     prev_q["period_end"],
            "curr_period_end":     curr_q["period_end"],
            "curr_filing_date":    curr_q["filing_date"],
            "document_type":       curr_q.get("document_type", ""),
            "prev_revenue":        prev_q["revenue"],
            "curr_revenue":        curr_q["revenue"],
            "revenue_delta_pct":   round(revenue_delta_pct, 3),
            "profit_status":       profit_status,
            "prev_op_profit":      prev_op,
            "curr_op_profit":      curr_op,
            "op_profit_delta_pct": round(op_delta_pct, 3) if op_delta_pct is not None else None,
            "stock_response_class": response_class,
            "outlook_judgment":    expl.get("outlook_judgment", "uncertain"),
            "outlook_reason_en":   expl.get("outlook_reason_en", ""),
            "outlook_reason_ja":   expl.get("outlook_reason_ja", ""),
            "explanation_en":      expl.get("explanation_advanced_en", ""),
            "explanation_ja":      expl.get("explanation_advanced_ja", ""),
            "pl_yoy":              _pl_yoy_for_response(pl_yoy),
            **stock,
        })
        time.sleep(1)

    return {
        "code": code,
        "name": _name_for(code),
        "min_year": min_year,
        "pairs": out_pairs,
        "source": "edinet_quarterly",
    }


# ----------------------------------------------------------------------------
# H1 (Semi-annual) overlay — Option B per user 2026-05-11
# ----------------------------------------------------------------------------
# Bidirectional re-check of an annual judgment using the most recent semi-
# annual (半期報告書) data:
#   - TURNAROUND ARM (loose): annual=growth_unlikely AND H1 shows recovery
#       → un-filter (override to growth_likely). Catches Honda-type chip-
#         shortage recoveries 6+ months before the next annual filing.
#   - DETERIORATION ARM (strict): annual=growth_likely AND H1 shows BOTH
#     revenue AND op profit dropping meaningfully → re-filter (override
#     to growth_unlikely). Catches mid-year deterioration before the
#     next annual filing.
#
# Asymmetric thresholds because filter-out errors are more costly than
# filter-keep errors (per user 2026-05-11, "Conservative" pick):
#   Turnaround: any non-trivial positive YoY on revenue OR op profit
#   Deterioration: BOTH revenue ≤ -5% AND op profit ≤ -10% required
# Initial loose thresholds (rev ≥ 2% OR op ≥ 5%) fired on 12 of 24 tickers
# in the 2026-05-11 backtest, breaking as many cases as it fixed (net 0 hit
# rate change). Tightened to BOTH lines required positive AND ≥ 5% — same
# spirit as the conservative deterioration arm. This prevents firing on
# Toyota-style cases where revenue rose but op profit was still negative.
H1_TURNAROUND_REVENUE_PCT_THRESHOLD = 5.0
H1_TURNAROUND_OP_PROFIT_PCT_THRESHOLD = 5.0
H1_DETERIORATION_REVENUE_PCT_THRESHOLD = -5.0
H1_DETERIORATION_OP_PROFIT_PCT_THRESHOLD = -10.0


def apply_h1_overlay(code: str, annual_judgment: str,
                     max_h1_fy: int | None = None) -> dict[str, Any]:
    """Apply the H1 (semi-annual) re-check overlay on top of an annual
    outlook judgment. Returns whether the annual call was overridden by
    H1 data, plus the H1 YoY evidence for audit.

    `max_h1_fy`: cap the H1 lookup to ≤ this fiscal year (Tempest's
    fiscal_year convention — FY2024 = period ending 2025-03-31, so an
    H1 with fiscal_year=2024 means period_end ≈ 2024-09-30). Used by
    the backtest to enforce the temporal boundary (don't peek at H1
    data published after the outcome window started).

    Returns:
        {
            "final_judgment":  "growth_likely" | "growth_unlikely" | "uncertain",
            "override_applied": bool,
            "override_arm":    "turnaround" | "deterioration" | None,
            "h1_evidence":     {curr_h1_period, prev_h1_period,
                                revenue_yoy_pct, op_profit_yoy_pct} | None,
            "reason":          str (one-line explanation of the decision),
        }
    """
    no_override = lambda reason: {
        "final_judgment": annual_judgment,
        "override_applied": False,
        "override_arm": None,
        "h1_evidence": None,
        "reason": reason,
    }

    series = load_quarterly_series(code)
    if not series:
        return no_override("no quarterly/H1 data available for this ticker")

    # Filter to semi-annual rows (fiscal_quarter == 2 = first-half / 半期報告書)
    h1_rows = [r for r in series if r.get("fiscal_quarter") == 2]
    if max_h1_fy is not None:
        h1_rows = [r for r in h1_rows if r.get("fiscal_year", 0) <= max_h1_fy]
    if not h1_rows:
        return no_override("no H1 (semi-annual) data within the lookback window")

    h1_rows.sort(key=lambda r: r["period_end"])
    curr_h1 = h1_rows[-1]
    prior_fy = curr_h1.get("fiscal_year", 0) - 1
    prev_h1 = next((r for r in h1_rows if r.get("fiscal_year") == prior_fy), None)
    if prev_h1 is None:
        return no_override(
            f"no prior-year H1 for FY{prior_fy} — cannot compute YoY")

    rev_yoy: float | None = None
    if prev_h1.get("revenue") and prev_h1["revenue"] != 0:
        rev_yoy = (curr_h1["revenue"] - prev_h1["revenue"]) / abs(prev_h1["revenue"]) * 100.0

    op_yoy: float | None = None
    if (prev_h1.get("operating_profit") is not None
            and curr_h1.get("operating_profit") is not None
            and prev_h1["operating_profit"] != 0):
        op_yoy = ((curr_h1["operating_profit"] - prev_h1["operating_profit"])
                  / abs(prev_h1["operating_profit"]) * 100.0)

    evidence = {
        "curr_h1_period":   curr_h1["period_end"],
        "prev_h1_period":   prev_h1["period_end"],
        "revenue_yoy_pct":  round(rev_yoy, 2) if rev_yoy is not None else None,
        "op_profit_yoy_pct": round(op_yoy, 2) if op_yoy is not None else None,
    }

    # TURNAROUND arm — tightened 2026-05-11 to require BOTH lines positive
    # (was loose OR; backtest showed loose fired too often on false dawns).
    if annual_judgment == "growth_unlikely":
        rev_recovering = rev_yoy is not None and rev_yoy >= H1_TURNAROUND_REVENUE_PCT_THRESHOLD
        op_recovering = op_yoy is not None and op_yoy >= H1_TURNAROUND_OP_PROFIT_PCT_THRESHOLD
        if rev_recovering and op_recovering:
            return {
                "final_judgment": "growth_likely",
                "override_applied": True,
                "override_arm": "turnaround",
                "h1_evidence": evidence,
                "reason": (
                    f"H1 recovery detected (rev YoY {evidence['revenue_yoy_pct']}%, "
                    f"op-profit YoY {evidence['op_profit_yoy_pct']}%) — un-filtered "
                    "from growth_unlikely back to growth_likely."
                ),
            }

    # DETERIORATION arm — STRICT threshold (filter-out error is expensive)
    elif annual_judgment == "growth_likely":
        rev_dropping = rev_yoy is not None and rev_yoy <= H1_DETERIORATION_REVENUE_PCT_THRESHOLD
        op_dropping = op_yoy is not None and op_yoy <= H1_DETERIORATION_OP_PROFIT_PCT_THRESHOLD
        # CONSERVATIVE: BOTH must be true
        if rev_dropping and op_dropping:
            return {
                "final_judgment": "growth_unlikely",
                "override_applied": True,
                "override_arm": "deterioration",
                "h1_evidence": evidence,
                "reason": (
                    f"H1 deterioration on BOTH lines (rev YoY "
                    f"{evidence['revenue_yoy_pct']}%, op-profit YoY "
                    f"{evidence['op_profit_yoy_pct']}%) — re-filtered "
                    "from growth_likely to growth_unlikely."
                ),
            }

    return {
        "final_judgment": annual_judgment,
        "override_applied": False,
        "override_arm": None,
        "h1_evidence": evidence,
        "reason": (
            f"H1 within thresholds (rev {evidence['revenue_yoy_pct']}%, "
            f"op {evidence['op_profit_yoy_pct']}%) — annual call kept."
        ),
    }


def run_quarterly(codes: list[str], min_year: int = 2020) -> list[dict[str, Any]]:
    out: list[dict] = []
    for code in codes:
        try:
            out.append(analyze_company_quarterly(code, min_year=min_year))
        except Exception as e:
            log.exception("quarterly quiet_change failed for %s", code)
            out.append({"code": code, "error": str(e)})
    return out


def run_multi_year(
    codes: list[str], min_year: int = 2020, run_tests: bool = False,
) -> list[dict[str, Any]]:
    out: list[dict] = []
    for code in codes:
        try:
            out.append(analyze_company_multi_year(code, min_year=min_year, run_tests=run_tests))
        except Exception as e:
            log.exception("multi-year quiet_change failed for %s", code)
            out.append({"code": code, "error": str(e)})
    return out


def run(codes: list[str]) -> list[dict[str, Any]]:
    """Analyze each requested code; per-company errors don't fail the batch."""
    from app.ingest.loader import load_edinet_only

    funds = load_edinet_only(codes)
    out: list[dict] = []
    for code in codes:
        fund = funds.get(code)
        if fund is None:
            out.append({"code": code, "error": "no EDINET annual report pair available"})
            continue
        try:
            out.append(analyze_company(code, fund))
        except Exception as e:
            log.exception("quiet_change failed for %s", code)
            out.append({"code": code, "error": str(e)})
        time.sleep(1)   # gentle pacing for the LLM call
    return out
