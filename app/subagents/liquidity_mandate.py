"""Liquidity + mandate compliance for sector-pipeline rows.

This is the advisor extension's "legwork-not-verdict" piece. The agent
does NOT render a buy/sell verdict — it just computes, against the desk's
own stated rules, whether each name can actually be traded at size and
whether it clears the mandate. Pure arithmetic; no model; no thresholds
the agent could be wrong about. The desk supplies the rules, the agent
runs the check.

Rules live in config/fund_profile.json. Defaults are placeholders — edit
that file to reflect real AUM, position sizing, and mandate constraints.

Public surface:
    load_profile() -> dict
    check_compliance(row: dict, profile: dict) -> dict
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "config" / "fund_profile.json"


def load_profile() -> dict[str, Any]:
    """Load the fund profile, or return safe defaults if the file is missing."""
    if PROFILE_PATH.exists():
        return json.load(open(PROFILE_PATH, encoding="utf-8"))
    return {
        "aum_jpy": 10_000_000_000,
        "max_position_pct": 5.0,
        "target_position_jpy": None,
        "max_pct_of_daily_volume": 25.0,
        "max_days_to_build": 10,
        "max_days_to_exit": 10,
        "sector_exclusions": [],
        "mcap_floor_jpy": None,
        "scale_categories_allowed": None,
        "esg_exclusions": [],
    }


def _target_position(profile: dict) -> float:
    if profile.get("target_position_jpy"):
        return float(profile["target_position_jpy"])
    aum = float(profile.get("aum_jpy") or 0)
    pct = float(profile.get("max_position_pct") or 0)
    return aum * pct / 100.0


def check_compliance(row: dict, profile: dict | None = None) -> dict[str, Any]:
    """Run liquidity + mandate checks on a single screen row.

    Args:
        row: a row from the sector pipeline. Expected fields:
             - liq_jpy_daily (avg daily traded yen volume; may be None)
             - mcap_jpy (market cap in yen; may be None)
             - sector_33_name (str)
             - scale_category (str; may be None)
        profile: a fund profile dict (load_profile() to get one).

    Returns: a flat dict with the computed metrics + per-rule pass/fail +
        a final verdict in {"PASS", "FAIL", "NEEDS_REVIEW"}.

    Verdict rules:
        - PASS: all measurable rules pass and no required data is missing.
        - FAIL: at least one rule fails on data that IS present.
        - NEEDS_REVIEW: a rule's required input is missing (e.g. mcap is
          null and the profile has a mcap_floor). Don't fail silently on
          missing data — flag it for the human.
    """
    if profile is None:
        profile = load_profile()

    target_jpy = _target_position(profile)
    max_pct_dv = float(profile.get("max_pct_of_daily_volume") or 0)
    max_build_days = profile.get("max_days_to_build")
    max_exit_days = profile.get("max_days_to_exit")

    liq = row.get("liq_jpy_daily")
    mcap = row.get("mcap_jpy")
    sector = row.get("sector_33_name") or row.get("sector")
    scale = row.get("scale_category")

    # --- Liquidity math ---
    daily_capacity_jpy: float | None = None
    days_to_build: float | None = None
    days_to_exit: float | None = None
    if liq is not None and max_pct_dv > 0 and target_jpy > 0:
        daily_capacity_jpy = float(liq) * max_pct_dv / 100.0
        if daily_capacity_jpy > 0:
            days_to_build = target_jpy / daily_capacity_jpy
            days_to_exit = days_to_build  # symmetric assumption

    # --- Per-rule pass/fail (None = couldn't evaluate, data missing) ---
    failures: list[str] = []
    needs_review: list[str] = []

    if max_build_days is not None:
        if days_to_build is None:
            needs_review.append("liquidity_data_missing")
        elif days_to_build > float(max_build_days):
            failures.append(f"days_to_build={days_to_build:.1f}>max{max_build_days}")

    if max_exit_days is not None and days_to_exit is not None:
        if days_to_exit > float(max_exit_days):
            failures.append(f"days_to_exit={days_to_exit:.1f}>max{max_exit_days}")

    sector_excl = profile.get("sector_exclusions") or []
    if sector_excl and sector in sector_excl:
        failures.append(f"sector_excluded:{sector}")

    mcap_floor = profile.get("mcap_floor_jpy")
    if mcap_floor is not None:
        if mcap is None:
            needs_review.append("mcap_missing")
        elif float(mcap) < float(mcap_floor):
            failures.append(f"mcap={mcap/1e9:.1f}B<floor{mcap_floor/1e9:.1f}B")

    scale_allowed = profile.get("scale_categories_allowed")
    if scale_allowed:
        if scale is None:
            needs_review.append("scale_missing")
        elif scale not in scale_allowed:
            failures.append(f"scale={scale}_not_allowed")

    if failures:
        verdict = "FAIL"
    elif needs_review:
        verdict = "NEEDS_REVIEW"
    else:
        verdict = "PASS"

    return {
        "target_position_jpy": target_jpy,
        "daily_capacity_jpy": daily_capacity_jpy,
        "days_to_build": round(days_to_build, 1) if days_to_build is not None else None,
        "days_to_exit": round(days_to_exit, 1) if days_to_exit is not None else None,
        "verdict": verdict,
        "failures": failures,
        "needs_review": needs_review,
    }
