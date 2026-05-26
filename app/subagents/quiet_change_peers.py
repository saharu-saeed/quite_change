"""Peer-group helpers for Quiet Change Agent v2.

Provides the sector-relative divergence gate (Claude's review fix):
  - Tickers down roughly with their sector peers → noticed_by_sector
  - Tickers down materially more than peers → idiosyncratic divergence
    (only THESE plus low attention earn the "quiet change" label)

Also includes split-artifact detection so a stock-split-induced -50% close-to-
close doesn't masquerade as a real decline.

Important caveat (Claude's "conditioned baseline" point): when peer medians
are computed across a universe already pre-filtered to rev↑+stock↓, every
peer is already down by construction. The "true" sector baseline (including
flat and rising peers) is less negative, so the divergence values produced
here UNDERSTATE the real idiosyncrasy. To get unconditioned medians, screen
a broader universe before computing peers.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TEMPEST_DIR = ROOT / "data" / "tempest"

# Tickers in these scale bands are mid-caps suitable for quiet-change hunting.
# TOPIX Core30 are mega-caps (always noticed). Unlisted ones (None scale)
# don't have a JPX scale assignment and may be too small / illiquid.
ACCEPTABLE_SCALE_CATEGORIES = {
    "TOPIX Small 1",
    "TOPIX Small 2",
    "TOPIX Mid400",
}

# Sector-relative thresholds (in percentage points, applied to 3-month move).
# These are CONDITIONED-baseline thresholds — see module docstring.
SECTOR_CASUALTY_BAND = 3.0      # |move - peer_median| <= this → moves with sector
IDIOSYNCRATIC_DIVERGENCE = 5.0  # move <= peer_median - this → idiosyncratic drop

# Split detection: any single-day price move beyond this fraction triggers a
# split-artifact flag. Conservative: catches 1:2 (50%) and larger splits.
# Misses 2:3 (33%); we note that as a known limitation, per Claude.
SPLIT_SINGLE_DAY_THRESHOLD = 0.30


def load_sector_info(ticker: str) -> dict[str, str | None]:
    """Read sector_33_name + scale_category from Tempest company.json."""
    try:
        raw = json.load(open(TEMPEST_DIR / ticker / "company.json", encoding="utf-8"))
        data = raw.get("data", raw)
        if isinstance(data, list) and data:
            data = data[0]
        return {
            "sector_33_name": data.get("sector_33_name"),
            "sector_17_name": data.get("sector_17_name"),
            "scale_category": data.get("scale_category"),
            "market_code": data.get("market_code"),
        }
    except Exception:
        return {"sector_33_name": None, "sector_17_name": None,
                "scale_category": None, "market_code": None}


def detect_possible_split(ticker: str, lookback_days: int = 120) -> dict[str, Any]:
    """Heuristic split detection from raw price history (no corp-action field).

    Walks the trailing ~120 days of closes. Any day-over-day price change
    with absolute fraction > SPLIT_SINGLE_DAY_THRESHOLD is flagged.

    Known limitation per Claude: misses 2:3 splits (~33% drop); does not
    distinguish a real crash from a split without volume/corp-action data.
    A genuine -35% gap with normal subsequent volume would false-positive
    here. Use as a heuristic, not ground truth.
    """
    try:
        prices = json.load(open(TEMPEST_DIR / ticker / "prices.json", encoding="utf-8"))["data"]
    except Exception:
        return {"possible_split": False, "reason": "no prices file"}
    if len(prices) < 2:
        return {"possible_split": False, "reason": "insufficient data"}

    # prices are newest-first; check the trailing lookback_days
    series = prices[: lookback_days + 1]
    flagged: list[dict] = []
    for i in range(len(series) - 1):
        try:
            today_close = float(series[i]["close"])
            prev_close = float(series[i + 1]["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if prev_close <= 0:
            continue
        delta = (today_close / prev_close) - 1.0
        if abs(delta) >= SPLIT_SINGLE_DAY_THRESHOLD:
            flagged.append({
                "date": series[i]["date"],
                "prev_close": prev_close,
                "today_close": today_close,
                "delta_pct": round(delta * 100, 2),
            })
    return {
        "possible_split": bool(flagged),
        "events": flagged,
        "reason": (
            f"{len(flagged)} day(s) with |move| ≥ {SPLIT_SINGLE_DAY_THRESHOLD*100:.0f}%"
            if flagged else "no day exceeded threshold"
        ),
    }


def compute_peer_baseline(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group candidates by sector_33_name; compute median 3-month stock move per group.

    Each input row must have 'sector_33_name' and 'stock_move_pct'. Returns
    a dict keyed by sector with:
        { "median_move": float, "n": int, "moves": [...] }

    Sectors with n < 2 are still emitted but flagged as low-confidence
    (single-member sectors can't form a real peer baseline).
    """
    by_sector: dict[str, list[float]] = {}
    for r in candidates:
        sector = r.get("sector_33_name") or "_unknown"
        move = r.get("stock_move_pct")
        if move is None:
            continue
        by_sector.setdefault(sector, []).append(float(move))
    return {
        sector: {
            "median_move": statistics.median(moves),
            "n": len(moves),
            "moves": sorted(moves),
            "low_confidence": len(moves) < 2,
        }
        for sector, moves in by_sector.items()
    }


def classify_sector_relative(
    stock_move_pct: float,
    sector: str | None,
    peer_baseline: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Apply the sector-relative gate to one ticker.

    Returns:
        {
          "peer_median": float | None,
          "peer_n": int,
          "sector_relative_pp": float | None,   # this stock's move minus peer median
          "noticed_by_sector": bool | None,     # True if moves roughly with peers
          "idiosyncratic": bool | None,         # True if much worse than peers
        }
    """
    sector_data = peer_baseline.get(sector or "_unknown")
    if sector_data is None or sector_data["low_confidence"]:
        return {
            "peer_median": sector_data["median_move"] if sector_data else None,
            "peer_n": sector_data["n"] if sector_data else 0,
            "sector_relative_pp": None,
            "noticed_by_sector": None,
            "idiosyncratic": None,
            "note": "insufficient peers to compute baseline",
        }
    peer_med = sector_data["median_move"]
    rel = stock_move_pct - peer_med
    return {
        "peer_median": round(peer_med, 2),
        "peer_n": sector_data["n"],
        "sector_relative_pp": round(rel, 2),
        "noticed_by_sector": abs(rel) <= SECTOR_CASUALTY_BAND,
        "idiosyncratic": rel <= -IDIOSYNCRATIC_DIVERGENCE,
        "note": "baseline is CONDITIONED on rev↑+stock↓ universe — see quiet_change_peers docstring",
    }


def quiet_change_dual_gate(
    attention_score: float,
    sector_relative: dict[str, Any],
    attention_low_threshold: float = 8.0,
) -> dict[str, Any]:
    """Final decision per Claude's design: quiet_change requires BOTH gates pass.

    Gate 1 (attention): attention_score <= low threshold (under-covered)
    Gate 2 (divergence): idiosyncratic (much worse than sector peers)

    Returns:
        {
          "quiet_change_candidate": bool,
          "reason": str,
        }
    """
    low_attention = attention_score <= attention_low_threshold
    idio = sector_relative.get("idiosyncratic") is True
    noticed_sec = sector_relative.get("noticed_by_sector") is True

    if low_attention and idio:
        return {"quiet_change_candidate": True,
                "reason": "low attention AND idiosyncratic divergence"}
    if low_attention and noticed_sec:
        return {"quiet_change_candidate": False,
                "reason": "noticed by sector (move tracks peers)"}
    if low_attention and sector_relative.get("idiosyncratic") is None:
        return {"quiet_change_candidate": False,
                "reason": "low attention but insufficient peers for divergence check"}
    return {"quiet_change_candidate": False,
            "reason": "attention score above threshold"}
