"""LLM-as-judge for Quiet Change explanations.

Sonnet rates each generated explanation against a 4-dimension rubric
that is anchored to the actual prompt requirements. Scores 0-5.
"""
from __future__ import annotations

import json
import re

from app.tools.bedrock import invoke_text


JUDGE_PROMPT = """You are evaluating an automated financial-narrative
generator. The generator was given a fixed set of inputs (revenue numbers,
a segment table, a 5-day stock return, AND a narrative excerpt from the
filing) and produced an explanation. Your job is to score the explanation
against a rubric.

GENERATOR INPUTS (the only facts the generator was allowed to use):
  Revenue prev:  {prev_revenue:,.0f} JPY
  Revenue curr:  {curr_revenue:,.0f} JPY
  Revenue change: {revenue_delta_pct:+.2f}%  (status: {profit_status})
  Stock 5d return: {stock_pct_str}  (direction: {stock_direction})
  Segment table:
{segment_table}
  Narrative excerpt (Japanese, may be truncated):
<narrative>
{narrative}
</narrative>

GENERATED EXPLANATION ({kind}, language={language}):
<explanation>
{explanation_text}
</explanation>

RUBRIC — score each dimension 0-5 (5 = perfect, 0 = fails the rule).

  faithfulness: 5 if every number, segment name, and stock figure in the
                explanation appears in the inputs above (segment table OR
                narrative). 3 if minor paraphrase but no invented numbers.
                0 if it invents segment names, percentages, or stock
                figures not present anywhere in the inputs.
                IMPORTANT: facts mentioned in the narrative ARE allowed
                — the narrative is one of the inputs.

  completeness: 5 if the explanation (a) names the top 1-2 segments by
                |delta| (or, if segment table is empty, says so), AND
                (b) mentions the stock direction with a rough magnitude.
                3 if one of those is missing. 0 if both are missing or
                the explanation is generic ("revenue grew across the business").

  plain_language: ONLY for kind="simple". 5 if the explanation uses
                  everyday words and contains NONE of these jargon terms:
                  YoY, year-over-year (English short form), M&A, FX,
                  guidance, beat expectations, IFRS, GAAP, EBITDA,
                  consolidated, attributable to.
                  (Japanese banned terms: ガイダンス, IFRS-based,
                  英語の専門用語のカタカナ.)
                  3 if 1-2 jargon words slip through. 0 if it reads
                  like an analyst report. Set to -1 for kind="advanced".

  bilingual_fidelity: assume you will see this same generator's other
                     language output in a parallel call. For now, score 5
                     if the explanation is internally coherent and ready
                     to be matched against its sibling. (The harness
                     computes cross-language fidelity separately by
                     comparing both outputs in one judge call — see
                     judge_bilingual_pair below.)

Output ONLY this JSON (no prose, no code fences):
{{
  "faithfulness":   {{"score": 0-5, "comment": "<one short sentence>"}},
  "completeness":   {{"score": 0-5, "comment": "<one short sentence>"}},
  "plain_language": {{"score": 0-5 or -1, "comment": "<one short sentence>"}},
  "bilingual_fidelity": {{"score": 0-5, "comment": "<one short sentence>"}}
}}
"""


BILINGUAL_FIDELITY_PROMPT = """You are checking that an English explanation
and its Japanese counterpart say the SAME THING. Same numbers, same
segment names (one-to-one translation), same stock direction.

ENGLISH:
<en>
{en_text}
</en>

JAPANESE:
<ja>
{ja_text}
</ja>

Output ONLY this JSON:
{{
  "score": 0-5,
  "comment": "<one short sentence — flag any number, segment, or direction that differs>"
}}

Scoring guide:
  5 = perfect parity (same numbers, same segment names, same conclusions).
  3 = mostly aligned but one minor detail differs (e.g., one extra/missing point).
  0 = different content (different numbers, different drivers, or one is empty).
"""


def _parse_json(raw: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _format_segment_table(segments: list[dict]) -> str:
    if not segments:
        return "  (no segment-level breakdown available)"
    return "\n".join(
        f"  {s['name']}: {s['prev']:,.0f} -> {s['curr']:,.0f}  ({s.get('delta_pct', 0):+.2f}%)"
        for s in segments
    )


def judge_explanation(
    case_inputs: dict,
    explanation_text: str,
    kind: str,        # "simple" or "advanced"
    language: str,    # "en" or "ja"
) -> dict:
    """Score one explanation. Returns {faithfulness, completeness,
    plain_language, bilingual_fidelity} with score+comment per dim."""
    if not explanation_text or not explanation_text.strip():
        return {
            "faithfulness":       {"score": 0, "comment": "empty explanation"},
            "completeness":       {"score": 0, "comment": "empty explanation"},
            "plain_language":     {"score": 0 if kind == "simple" else -1, "comment": "empty"},
            "bilingual_fidelity": {"score": 0, "comment": "empty"},
        }
    stock_pct = case_inputs.get("stock_5d_return_pct_approx")
    prompt = JUDGE_PROMPT.format(
        prev_revenue=case_inputs["prev_revenue"],
        curr_revenue=case_inputs["curr_revenue"],
        revenue_delta_pct=case_inputs["revenue_delta_pct_approx"],
        profit_status=case_inputs["profit_status"],
        stock_pct_str="n/a" if stock_pct is None else f"{stock_pct:+.2f}%",
        stock_direction=case_inputs.get("stock_direction", "unknown"),
        segment_table=_format_segment_table(case_inputs.get("segments", [])),
        narrative=(case_inputs.get("narrative") or "(not captured)")[:2500],
        kind=kind,
        language=language,
        explanation_text=explanation_text[:3000],
    )
    raw = invoke_text(prompt, max_tokens=600)
    parsed = _parse_json(raw)
    return {
        "faithfulness":       parsed.get("faithfulness",       {"score": 0, "comment": "parse failed"}),
        "completeness":       parsed.get("completeness",       {"score": 0, "comment": "parse failed"}),
        "plain_language":     parsed.get("plain_language",     {"score": -1, "comment": ""}),
        "bilingual_fidelity": parsed.get("bilingual_fidelity", {"score": 0, "comment": "parse failed"}),
    }


def judge_bilingual_pair(en_text: str, ja_text: str) -> dict:
    """Score whether EN and JA say the same thing. Returns {score, comment}."""
    if not en_text or not ja_text:
        return {"score": 0, "comment": "one or both texts empty"}
    raw = invoke_text(
        BILINGUAL_FIDELITY_PROMPT.format(en_text=en_text[:2500], ja_text=ja_text[:2500]),
        max_tokens=300,
    )
    parsed = _parse_json(raw)
    return {
        "score": int(parsed.get("score", 0)),
        "comment": parsed.get("comment", "parse failed"),
    }
