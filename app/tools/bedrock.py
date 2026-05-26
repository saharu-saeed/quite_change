"""Minimal LLM text invocation wrapper.

Resolution order (same convention used elsewhere in the project):
  1. ANTHROPIC_API_KEY  → direct Anthropic API
  2. AWS credentials    → Bedrock (AnthropicBedrock SDK for Anthropic models,
                          boto3 converse for non-Anthropic Bedrock models)
  3. Neither            → RuntimeError (caller decides whether to skip / fail)

Usage tracking: every LLM call records input/output token counts in
module-level counters. Callers can call get_usage_stats() at any point
to see cumulative token usage and estimated cost. Pricing currently
assumes Bedrock Sonnet 4.6 ($3/M input, $15/M output, $0.30/M cache
read, $3.75/M cache write).
"""
from __future__ import annotations
import logging
import os

log = logging.getLogger(__name__)

# --- token usage tracker (cumulative across the process) ---
_USAGE: dict[str, int] = {
    "call_count": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
}

# Bedrock Sonnet 4.6 pricing (USD per million tokens)
_PRICE_INPUT_PER_MTOK = 3.0
_PRICE_OUTPUT_PER_MTOK = 15.0
_PRICE_CACHE_READ_PER_MTOK = 0.30  # 10% of normal input
_PRICE_CACHE_WRITE_PER_MTOK = 3.75  # 1.25x of normal input


def _track_usage(input_tokens: int, output_tokens: int,
                 cache_read: int = 0, cache_write: int = 0) -> None:
    _USAGE["call_count"] += 1
    _USAGE["input_tokens"] += input_tokens
    _USAGE["output_tokens"] += output_tokens
    _USAGE["cache_read_input_tokens"] += cache_read
    _USAGE["cache_creation_input_tokens"] += cache_write


def get_usage_stats() -> dict:
    """Return cumulative usage + estimated cost (Bedrock Sonnet 4.6 pricing)."""
    cost = (
        _USAGE["input_tokens"] * _PRICE_INPUT_PER_MTOK / 1e6
        + _USAGE["output_tokens"] * _PRICE_OUTPUT_PER_MTOK / 1e6
        + _USAGE["cache_read_input_tokens"] * _PRICE_CACHE_READ_PER_MTOK / 1e6
        + _USAGE["cache_creation_input_tokens"] * _PRICE_CACHE_WRITE_PER_MTOK / 1e6
    )
    return {**_USAGE, "estimated_cost_usd": round(cost, 4)}


def reset_usage_stats() -> None:
    """Zero out the cumulative counters (call at the start of a tracked run)."""
    for k in _USAGE:
        _USAGE[k] = 0


def _safe_track_from_msg(msg) -> None:
    """Extract usage from Anthropic SDK response and record. Defensive against missing fields."""
    try:
        u = getattr(msg, "usage", None)
        if u is None:
            return
        _track_usage(
            input_tokens=getattr(u, "input_tokens", 0) or 0,
            output_tokens=getattr(u, "output_tokens", 0) or 0,
            cache_read=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write=getattr(u, "cache_creation_input_tokens", 0) or 0,
        )
    except Exception:  # defensive — never let tracking break a call
        pass


def _is_anthropic_model(model_id: str) -> bool:
    return model_id.startswith("anthropic.") or model_id.startswith("us.anthropic.")


def _resolve_anthropic_model() -> str:
    if os.environ.get("ANTHROPIC_MODEL"):
        return os.environ["ANTHROPIC_MODEL"]
    bedrock_id = os.environ.get("BEDROCK_MODEL_ID", "")
    for prefix in ("us.anthropic.", "anthropic."):
        if bedrock_id.startswith(prefix):
            return bedrock_id[len(prefix):]
    return "claude-sonnet-4-6-20250929"


def _call_anthropic_direct(prompt: str, max_tokens: int,
                           system_prompt: str | None = None) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    kwargs: dict = {
        "model": _resolve_anthropic_model(),
        "max_tokens": max_tokens,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        kwargs["system"] = [{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }]
    msg = client.messages.create(**kwargs)
    _safe_track_from_msg(msg)
    return msg.content[0].text.strip()


def _call_bedrock_anthropic(model_id: str, prompt: str, max_tokens: int,
                            system_prompt: str | None = None) -> str:
    from anthropic import AnthropicBedrock
    client = AnthropicBedrock(
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        aws_access_key=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN") or None,
    )
    kwargs: dict = {
        "model": model_id,
        "max_tokens": max_tokens,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        # Prompt-caching: mark the system prompt as cacheable. Anthropic
        # charges 10% of normal price on cache reads (after the first call),
        # 1.25x on the first write. Cache TTL is 5 minutes for ephemeral.
        # Sonnet 4.6 requires the cached portion to be ≥1024 tokens to
        # actually cache; smaller system prompts are accepted but not cached.
        kwargs["system"] = [{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }]
    msg = client.messages.create(**kwargs)
    _safe_track_from_msg(msg)
    return msg.content[0].text.strip()


def _call_boto3_converse(model_id: str, prompt: str, max_tokens: int) -> str:
    import boto3
    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN") or None,
    )
    resp = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
    )
    # boto3 converse returns usage in a dict with camelCase keys.
    try:
        u = resp.get("usage", {}) or {}
        _track_usage(
            input_tokens=u.get("inputTokens", 0) or 0,
            output_tokens=u.get("outputTokens", 0) or 0,
            cache_read=u.get("cacheReadInputTokens", 0) or 0,
            cache_write=u.get("cacheWriteInputTokens", 0) or 0,
        )
    except Exception:
        pass
    return resp["output"]["message"]["content"][0]["text"].strip()


def invoke_text(prompt: str, max_tokens: int = 512,
                system_prompt: str | None = None) -> str:
    """Invoke the LLM. If `system_prompt` is provided, it is sent as a
    cache-marked system block (Anthropic prompt caching). Non-Anthropic
    models (e.g. Nova Pro via boto3 converse) currently ignore the system
    prompt — if you need it preserved for those, prefix it to `prompt`
    yourself before calling.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _call_anthropic_direct(prompt, max_tokens, system_prompt=system_prompt)
    if (os.environ.get("AWS_REGION")
            and os.environ.get("AWS_ACCESS_KEY_ID")
            and os.environ.get("AWS_SECRET_ACCESS_KEY")):
        model_id = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6-v1")
        if _is_anthropic_model(model_id):
            return _call_bedrock_anthropic(model_id, prompt, max_tokens,
                                           system_prompt=system_prompt)
        # boto3 converse path (non-Anthropic models): no cache support here;
        # fall back to a combined prompt for safety.
        combined = (system_prompt + "\n\n" + prompt) if system_prompt else prompt
        return _call_boto3_converse(model_id, combined, max_tokens)
    raise RuntimeError(
        "No LLM credentials configured (set ANTHROPIC_API_KEY or AWS_* env vars)."
    )
