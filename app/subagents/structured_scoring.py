"""Phase 2: Structured per-indicator scoring + code combiner.

ARCHITECTURE (2026-05-20):
This module is a parallel evaluation path to the existing
quiet_change.py holistic-verdict pipeline. It is intentionally isolated:
  - Uses the Anthropic SDK directly (NOT AWS Bedrock — see memory note)
  - Asks Claude to score 5 explicit axes (1-5) with brief reasoning
  - Combines those scores in code with explicit, tunable weights
  - Produces a deterministic verdict that can be traced score-by-score

The goal is to satisfy Mr. Nakamachi's directive: "weighting should be
in code, not buried in LLM prompts, so we can explicitly trace
'if we multiply indicator X by factor Y, how does the result change.'"

Default model: claude-haiku-4-5 (cheap iteration). Final holdout run
may switch to claude-sonnet-4-6 if A/B reliability test warrants it.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Any


# ============================================================
# System prompt — cached across all calls (saves on input tokens)
# ============================================================
SCORING_SYSTEM_PROMPT = """You are a Japanese-equities analyst rating five structural axes for a single fiscal year of a company.

Your ONLY job is to output a JSON object with 5 integer scores and brief reasoning. Do not produce any other text.

The 5 axes (all scored 1-5, where 5 is strongest signal for sustainable growth):

1. peer_dominance — How strongly is the company outperforming its 33-industry peer median?
   5 = operating margin >+15pp above sector median (clearly dominant)
   4 = +5 to +15pp above (meaningfully ahead)
   3 = -2 to +5pp (parity)
   2 = -5 to -2pp (lagging)
   1 = below -5pp (clearly underperforming)

2. margin_quality — Is the operating margin both high AND trending in the right direction?
   5 = margin >20% AND trend +1pp+ YoY (high-quality, improving)
   4 = margin >15% AND trend ≥ 0 (good and stable)
   3 = margin 10-15% with stable trend (acceptable)
   2 = margin <10% OR trend declining 1-3pp YoY (concerning)
   1 = margin <5% OR trend declining >3pp YoY (deteriorating)

3. cash_conversion — Are reported profits actually converting to operating cash?
   5 = CFO/NI ratio >1.5x (very strong)
   4 = 1.0 to 1.5x (healthy)
   3 = 0.8 to 1.0x (acceptable)
   2 = 0.5 to 0.8x (weak)
   1 = <0.5x or negative (red flag — profits aren't cash)

4. growth_durability — Is the operating-profit jump structural or a one-time surge?
   5 = moderate steady growth (+10 to +30% op-profit YoY) backed by revenue growth (+10%+)
   4 = strong growth (+30 to +50% op-profit) with proportional revenue growth
   3 = either revenue OR profit growing but not both (mixed signal)
   2 = very large op-profit jump (>+50%) NOT matched by revenue growth (likely one-time)
   1 = extreme outsized op-profit jump (>+100%) from a weak peer position (clearly unsustainable)

5. concentration_risk — How exposed is the company to a single business segment failing?
   5 = no segment >40% of revenue (well-diversified)
   4 = top segment 40-60%
   3 = top segment 60-75% (moderate concentration)
   2 = top segment 75-90% (high concentration)
   1 = top segment >90% OR effectively single-segment (existential exposure)

Critical instructions:
- Use ONLY the structured numbers provided. Do NOT add information from prior training knowledge about the company.
- If an axis cannot be determined from provided data, set score = 3 (neutral) and reasoning = "insufficient data".
- Reasoning per axis: 1-2 sentences max. Cite specific numbers.
- Return STRICT JSON ONLY. No prose before or after.

Output schema:
{
  "peer_dominance":     {"score": <1-5>, "reasoning": "<1-2 sentences>"},
  "margin_quality":     {"score": <1-5>, "reasoning": "<1-2 sentences>"},
  "cash_conversion":    {"score": <1-5>, "reasoning": "<1-2 sentences>"},
  "growth_durability":  {"score": <1-5>, "reasoning": "<1-2 sentences>"},
  "concentration_risk": {"score": <1-5>, "reasoning": "<1-2 sentences>"}
}
"""


# ============================================================
# Default weights and verdict thresholds (Nakamachi-tunable)
# ============================================================
DEFAULT_WEIGHTS = {
    "peer_dominance":     1.0,
    "margin_quality":     1.0,
    "cash_conversion":    1.0,
    "growth_durability":  1.0,
    "concentration_risk": 0.5,  # less heavily weighted — concentration amplifies
                                # direction but doesn't predict it (see Phase 1
                                # top_segment_share analysis)
}

# Verdict thresholds on the weighted sum.
# With 5 axes scored 1-5 and weights summing to 4.5:
#   min weighted score = 1*4.5 = 4.5
#   max weighted score = 5*4.5 = 22.5
DEFAULT_THRESHOLDS = {
    "growth_likely_min":   18.0,  # roughly "4+ on most axes"
    "growth_unlikely_max": 10.0,  # roughly "2 or less on most axes"
}

# Hard-floor rules: if any axis is at the extreme low, force uncertain/unlikely
# regardless of overall sum. Mirrors the asymmetric vetoes from Phase 1.
HARD_FLOORS = {
    "cash_conversion_min_for_likely":   3,  # cfo_ni < 0.8 (score ≤ 2) → can't be likely
    "margin_quality_min_for_likely":    3,  # margin declining >1pp → can't be likely
    "peer_dominance_min_for_likely":    3,  # below peers → can't be likely
}


# ============================================================
# Input formatting
# ============================================================
def build_user_message(pair: dict) -> str:
    """Build the structured input message for one pair.

    Pulls ONLY the indicator data from the pair — no narrative.
    Output should be ~1.5-2K tokens.
    """
    pc = pair.get("peer_comparison") or {}
    my = pc.get("my") or {}
    med = pc.get("sector_median") or {}

    bs_hist = pair.get("bs_quality_history") or []
    bs_latest = bs_hist[-1] if bs_hist else {}

    cf_yoy = pair.get("cashflow_yoy") or {}
    cf_ratios = cf_yoy.get("ratios", {}).get("cfo_to_ni", {})

    segs = pair.get("segments") or []
    top_seg_pct = None
    if segs:
        total = sum((s.get("curr") or 0) for s in segs)
        if total > 0:
            top_seg_pct = max((s.get("curr") or 0) for s in segs) / total * 100

    op_margin_trend = pair.get("op_margin_trend_pp")

    lines = [
        f"=== Company: ticker {pair.get('ticker', '?')} ===",
        f"=== Fiscal year: FY{pair.get('curr_fiscal_year', '?')} (prediction window: next 1-2 years) ===",
        "",
        "PEER COMPARISON (this company vs 33-industry sector median):",
        f"  Operating margin:        company={_fmt(my.get('op_margin_pct'))}%  "
        f"sector_median={_fmt(med.get('op_margin_pct'))}%  "
        f"gap={_fmt(_diff(my.get('op_margin_pct'), med.get('op_margin_pct')))}pp",
        f"  Net margin:              company={_fmt(my.get('net_margin_pct'))}%  "
        f"sector_median={_fmt(med.get('net_margin_pct'))}%  "
        f"gap={_fmt(_diff(my.get('net_margin_pct'), med.get('net_margin_pct')))}pp",
        f"  Revenue growth YoY:      company={_fmt(my.get('revenue_growth_pct'))}%  "
        f"sector_median={_fmt(med.get('revenue_growth_pct'))}%",
        "",
        "MARGIN TRAJECTORY:",
        f"  Op margin this FY:       {_fmt(my.get('op_margin_pct'))}%",
        f"  Op margin YoY change:    {_fmt(op_margin_trend)}pp",
        f"  Op profit YoY change:    {_fmt(pair.get('op_profit_delta_pct'))}%",
        f"  Revenue YoY change:      {_fmt(pair.get('revenue_delta_pct'))}%",
        "",
        "CASH QUALITY:",
        f"  CFO / Net Income (this FY):    {_fmt(cf_ratios.get('curr'))}",
        f"  CFO / Net Income (prior FY):   {_fmt(cf_ratios.get('prev'))}",
        "",
        "BALANCE SHEET QUALITY:",
        f"  Goodwill / equity:       {_fmt(bs_latest.get('goodwill_to_equity_pct'))}%",
        f"  Debt / equity:           {_fmt(bs_latest.get('debt_to_equity_pct'))}%",
        "",
        "SEGMENT CONCENTRATION:",
        f"  Top segment share:       {_fmt(top_seg_pct)}%  (of total revenue)",
        f"  Number of segments:      {len(segs)}",
        "",
        "TASK: Output the structured JSON scoring object now.",
    ]
    return "\n".join(lines)


def _fmt(v):
    if v is None:
        return "n/a"
    if isinstance(v, (int, float)):
        return f"{v:+.2f}" if isinstance(v, float) else str(v)
    return str(v)


def _diff(a, b):
    if a is None or b is None:
        return None
    return a - b


# ============================================================
# Claude API call
# ============================================================
@dataclass
class ScoringResult:
    scores: dict[str, dict[str, Any]]  # raw per-axis scores + reasoning
    weighted_sum: float
    verdict: str  # "growth_likely" / "growth_unlikely" / "uncertain"
    verdict_reason: str
    model_used: str
    raw_response: str


def score_pair(
    pair: dict,
    model: str = "claude-haiku-4-5-20251001",
    weights: dict[str, float] | None = None,
    thresholds: dict[str, float] | None = None,
    api_key: str | None = None,
) -> ScoringResult:
    """Call Claude API to score 5 axes, then combine in code.

    Uses the Anthropic SDK directly (NOT Bedrock).

    Set ANTHROPIC_API_KEY in env or pass api_key argument.
    """
    import anthropic

    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in env and not passed")

    client = anthropic.Anthropic(api_key=api_key)

    user_text = build_user_message(pair)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SCORING_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # cache the system prompt
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )

    raw = response.content[0].text
    # Strict JSON parse — the system prompt requires JSON-only output.
    scores = _parse_json(raw)
    return combine_scores(scores, weights=weights, thresholds=thresholds, raw_response=raw, model=model)


def _parse_json(raw: str) -> dict:
    """Robust JSON extraction — strips any leading/trailing prose."""
    raw = raw.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    # Find first { and last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"No JSON object in response: {raw[:200]}")
    return json.loads(raw[start:end + 1])


# ============================================================
# Code combiner — explicit weights, traceable verdict
# ============================================================
def combine_scores(
    scores: dict,
    weights: dict[str, float] | None = None,
    thresholds: dict[str, float] | None = None,
    raw_response: str = "",
    model: str = "",
) -> ScoringResult:
    """Deterministic combination of per-axis scores.

    Steps:
      1. Compute weighted sum = sum(score * weight) over all axes
      2. Apply hard floors (any single axis can veto growth_likely)
      3. Compare weighted sum to thresholds for final verdict

    Returns ScoringResult with full traceability.
    """
    weights = weights or DEFAULT_WEIGHTS
    thresholds = thresholds or DEFAULT_THRESHOLDS

    # Validate and extract integer scores
    axis_scores = {}
    for axis in DEFAULT_WEIGHTS:
        v = scores.get(axis, {})
        s = v.get("score") if isinstance(v, dict) else v
        if not isinstance(s, int) or s < 1 or s > 5:
            raise ValueError(f"Invalid score for {axis}: {s} (must be int 1-5)")
        axis_scores[axis] = s

    weighted = sum(axis_scores[a] * weights[a] for a in axis_scores)

    # Hard floors — asymmetric vetoes encoded as score thresholds
    floor_blocks = []
    if axis_scores["cash_conversion"] < HARD_FLOORS["cash_conversion_min_for_likely"]:
        floor_blocks.append(f"cash_conversion={axis_scores['cash_conversion']} (<3)")
    if axis_scores["margin_quality"] < HARD_FLOORS["margin_quality_min_for_likely"]:
        floor_blocks.append(f"margin_quality={axis_scores['margin_quality']} (<3)")
    if axis_scores["peer_dominance"] < HARD_FLOORS["peer_dominance_min_for_likely"]:
        floor_blocks.append(f"peer_dominance={axis_scores['peer_dominance']} (<3)")

    if floor_blocks:
        verdict = "uncertain" if weighted >= thresholds["growth_unlikely_max"] else "growth_unlikely"
        reason = f"hard floor: {', '.join(floor_blocks)}; weighted_sum={weighted:.1f}"
    elif weighted >= thresholds["growth_likely_min"]:
        verdict = "growth_likely"
        reason = f"weighted_sum={weighted:.1f} ≥ {thresholds['growth_likely_min']} (all hard floors clear)"
    elif weighted <= thresholds["growth_unlikely_max"]:
        verdict = "growth_unlikely"
        reason = f"weighted_sum={weighted:.1f} ≤ {thresholds['growth_unlikely_max']}"
    else:
        verdict = "uncertain"
        reason = f"weighted_sum={weighted:.1f} in uncertain zone [{thresholds['growth_unlikely_max']}, {thresholds['growth_likely_min']})"

    return ScoringResult(
        scores=scores,
        weighted_sum=weighted,
        verdict=verdict,
        verdict_reason=reason,
        model_used=model,
        raw_response=raw_response,
    )
