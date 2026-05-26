"""Generate a clean single-file HTML UI for the latest sweep output.

Reads outputs/quiet_change_v2/sweep/_sweep_*.json and renders it as a
self-contained HTML page with:
  - Top stat cards (sectors / companies / leads / strict hits)
  - Tab nav: Profile C  |  Setting A  |  Setting B  |  Per-sector
  - Per-lead cards with metrics, flags, and article snippets inline

Design: minimal, professional, scannable. White background, dark text,
subtle borders, accent blue for primary signals, amber/red for warnings.
System fonts so Japanese renders cleanly on any OS.

No external dependencies. Data is inlined as JSON; opens offline.

Usage:
    python scripts/generate_ui.py
    python scripts/generate_ui.py --date 2026-05-23
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SWEEP_DIR = ROOT / "outputs" / "quiet_change_v2" / "sweep"
SERP_CACHE_DIR = ROOT / "outputs" / "quiet_change_v2" / "serpapi_cache"
SECTORS_DIR = ROOT / "outputs" / "quiet_change_v2" / "sectors"
UI_DIR = ROOT / "outputs" / "ui"


def _latest_sweep() -> Path | None:
    if not SWEEP_DIR.exists():
        return None
    files = sorted(SWEEP_DIR.glob("_sweep_*.json"))
    return files[-1] if files else None


def _load_snippets(ticker: str, max_items: int = 3) -> list[dict]:
    """Pull a few article snippets per ticker from cached SerpAPI for inline display."""
    out: list[dict] = []
    seen: set[str] = set()
    for kind in ("anomaly", "confirm"):
        cache = SERP_CACHE_DIR / f"{ticker}_{kind}.json"
        if not cache.exists():
            continue
        try:
            payload = json.load(open(cache, encoding="utf-8"))
        except Exception:
            continue
        items = list(payload.get("news_results") or []) + list(payload.get("organic_results") or [])
        for it in items:
            url = (it.get("link") or it.get("url") or "").strip()
            if not url or url in seen:
                continue
            stub_doms = ("minkabu.jp", "kabutan.jp", "irbank.net", "kabuyoho.jp")
            if any(d in url for d in stub_doms) and "/news/" not in url and "/article" not in url:
                continue
            title = (it.get("title") or "").strip()
            snippet = (it.get("snippet") or "").strip()
            if not title and not snippet:
                continue
            seen.add(url)
            out.append({
                "title": title,
                "snippet": snippet[:240],
                "url": url,
                "date": it.get("date", "") or "",
                "kind": kind,
            })
            if len(out) >= max_items:
                return out
    return out


def _slim_row(r: dict, comp_field: str = "comp_a30") -> dict:
    """Compact a row for UI display — strip heavy nested objects we don't render."""
    q = r.get("quality") or {}
    qs = (q.get("quality_score") or {}) if q.get("data_ok") else {}
    sr = r.get("sector_rel") or {}
    dg = r.get("dual_gate") or {}
    v = r.get("valuation") or {}
    vs = r.get("valuation_score") or {}
    return {
        "ticker": r.get("ticker"),
        "company": r.get("company_name") or r.get("company") or "?",
        "sector": r.get("_sector") or r.get("sector_33_name") or "?",
        "tier": r.get("tier") or "?",
        "scale": r.get("scale_category") or "-",
        "stock_3m": r.get("stock_move_pct"),
        "div_pp": sr.get("sector_relative_pp"),
        "peer_med": sr.get("peer_median"),
        "attn": r.get("attention_score"),
        "retail": r.get("retail_chatter") or 0,
        "editorial": r.get("editorial") or 0,
        "brokerage": r.get("brokerage") or 0,
        "agg_stub": r.get("agg_stub") or 0,
        "quality_composite": qs.get("composite_score"),
        "revenue_cagr_3y": q.get("revenue_cagr_3y") if q.get("data_ok") else None,
        "op_margin_latest": q.get("op_margin_latest") if q.get("data_ok") else None,
        "op_margin_trend": q.get("op_margin_trend_pp") if q.get("data_ok") else None,
        "equity_ratio": q.get("equity_ratio_latest") if q.get("data_ok") else None,
        "roe": q.get("roe_latest") if q.get("data_ok") else None,
        "composite": r.get(comp_field) if comp_field in r else r.get("watchlist_composite"),
        "mcap_jpy": r.get("market_cap_jpy"),
        "liq_jpy_daily": r.get("liquidity_jpy_daily"),
        "fame_flag": r.get("fame_flag") or "",
        "profile": r.get("profile") or "",
        "strict_hit": bool(dg.get("quiet_change_candidate")),
        "pe": v.get("pe_ratio"),
        "pb": v.get("pb_ratio"),
        "valuation_rank": vs.get("composite_valuation_score"),
        "sanity_flag": v.get("sanity_flag") or "",
        "latest_revenue": r.get("latest_annual_revenue_jpy"),
        "snippets": _load_snippets(r.get("ticker", ""), max_items=3),
        # Liquidity + mandate compliance (item B, 2026-05-24).
        # Pure arithmetic against config/fund_profile.json — no model, no
        # threshold the agent could be wrong about.
        "compliance": r.get("compliance") or {},
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Quiet Change Agent — Sweep {date}</title>
<style>
  :root {{
    --bg: #f7f8fa;
    --surface: #ffffff;
    --border: #e4e6eb;
    --border-strong: #d0d3da;
    --text: #1a1d23;
    --text-muted: #6b7280;
    --text-faint: #9ca3af;
    --accent: #1d4ed8;
    --accent-light: #dbeafe;
    --positive: #047857;
    --positive-light: #d1fae5;
    --warning: #b45309;
    --warning-light: #fef3c7;
    --critical: #b91c1c;
    --critical-light: #fee2e2;
    --neutral: #4b5563;
    --neutral-light: #f3f4f6;
    --mono: ui-monospace, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace;
    --sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Hiragino Sans', 'Yu Gothic', 'Meiryo', sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}
  header.top {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 20px 32px;
  }}
  header.top h1 {{
    margin: 0 0 4px 0;
    font-size: 20px;
    font-weight: 600;
    letter-spacing: -0.01em;
  }}
  header.top .meta {{
    color: var(--text-muted);
    font-size: 13px;
  }}
  .stat-bar {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1px;
    background: var(--border);
    border-bottom: 1px solid var(--border);
  }}
  .stat {{
    background: var(--surface);
    padding: 16px 24px;
  }}
  .stat .num {{
    font-family: var(--mono);
    font-size: 22px;
    font-weight: 600;
    color: var(--text);
    letter-spacing: -0.02em;
  }}
  .stat .label {{
    color: var(--text-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 2px;
  }}
  nav.tabs {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 32px;
    display: flex;
    gap: 0;
    position: sticky;
    top: 0;
    z-index: 10;
  }}
  nav.tabs button {{
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 14px 18px;
    font-family: var(--sans);
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
    cursor: pointer;
    transition: color 0.1s, border-color 0.1s;
  }}
  nav.tabs button:hover {{ color: var(--text); }}
  nav.tabs button.active {{
    color: var(--accent);
    border-bottom-color: var(--accent);
  }}
  main {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px 32px 64px 32px;
  }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  .section-intro {{
    margin: 0 0 20px 0;
    padding: 16px 20px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
  }}
  .section-intro h2 {{
    margin: 0 0 6px 0;
    font-size: 16px;
    font-weight: 600;
  }}
  .section-intro p {{
    margin: 0;
    color: var(--text-muted);
    font-size: 13px;
  }}
  .section-intro p + p {{ margin-top: 6px; }}
  .subgroup-header {{
    margin: 24px 0 12px 0;
    display: flex;
    align-items: baseline;
    gap: 10px;
  }}
  .subgroup-header h3 {{
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .subgroup-header .count {{
    color: var(--text-muted);
    font-size: 12px;
    font-family: var(--mono);
  }}
  .subgroup-header .desk-q {{
    margin-left: auto;
    color: var(--text-muted);
    font-size: 12px;
    font-style: italic;
  }}
  .cards {{
    display: grid;
    grid-template-columns: 1fr;
    gap: 12px;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    transition: border-color 0.1s;
  }}
  .card:hover {{ border-color: var(--border-strong); }}
  .card.profile-c {{
    border-left: 3px solid var(--accent);
  }}
  .card .rank-row {{
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 8px;
  }}
  .card .rank {{
    font-family: var(--mono);
    font-size: 12px;
    color: var(--text-faint);
    min-width: 24px;
  }}
  .card .ticker {{
    font-family: var(--mono);
    font-size: 15px;
    font-weight: 600;
    color: var(--accent);
    margin-right: 4px;
  }}
  .card .company {{
    font-size: 16px;
    font-weight: 600;
    color: var(--text);
  }}
  .card .sector-tag {{
    margin-left: 8px;
    padding: 2px 8px;
    background: var(--neutral-light);
    border-radius: 4px;
    font-size: 11px;
    color: var(--neutral);
  }}
  .card .tier-badge {{
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-family: var(--mono);
    font-weight: 600;
    letter-spacing: 0.04em;
  }}
  .tier-BAND {{ background: var(--accent-light); color: var(--accent); }}
  .tier-DASH {{ background: var(--warning-light); color: var(--warning); }}
  .metrics {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
    gap: 12px;
    margin: 12px 0;
    padding: 12px 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
  }}
  .metric {{
    display: flex;
    flex-direction: column;
  }}
  .metric {{ position: relative; }}
  .metric .key {{
    font-size: 10px;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
  }}
  .metric .key[data-tip] {{
    cursor: help;
    border-bottom: 1px dotted var(--text-faint);
    display: inline-block;
  }}
  /* Custom CSS tooltip — appears below the label on hover, no JS */
  .metric .key[data-tip]:hover::after {{
    content: attr(data-tip);
    position: absolute;
    top: calc(100% + 8px);
    left: 0;
    width: 320px;
    max-width: 90vw;
    padding: 14px 16px;
    background: #1a1d23;
    color: #f7f8fa;
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.65;
    font-family: var(--mono);
    font-weight: 400;
    letter-spacing: 0;
    text-transform: none;
    white-space: pre-wrap;
    box-shadow: 0 6px 16px rgba(0,0,0,0.2);
    z-index: 1000;
    pointer-events: none;
  }}
  .metric .key[data-tip]:hover::before {{
    content: '';
    position: absolute;
    top: calc(100% + 2px);
    left: 12px;
    border: 6px solid transparent;
    border-bottom-color: #1a1d23;
    z-index: 1000;
    pointer-events: none;
  }}
  /* Right-edge variant — when JS detects the tip would overflow the viewport,
     it adds .tip-right which flips the tooltip to anchor on the right side. */
  [data-tip].tip-right:hover::after {{
    left: auto !important;
    right: 0 !important;
  }}
  [data-tip].tip-right:hover::before {{
    left: auto !important;
    right: 12px !important;
  }}
  /* Flags also get tooltips */
  .flag[data-tip] {{ cursor: help; position: relative; }}
  .flag[data-tip]:hover::after {{
    content: attr(data-tip);
    position: absolute;
    top: calc(100% + 8px);
    left: 0;
    width: 320px;
    max-width: 90vw;
    padding: 14px 16px;
    background: #1a1d23;
    color: #f7f8fa;
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.65;
    font-family: var(--mono);
    font-weight: 400;
    letter-spacing: 0;
    text-transform: none;
    white-space: pre-wrap;
    box-shadow: 0 6px 16px rgba(0,0,0,0.2);
    z-index: 1000;
    pointer-events: none;
  }}
  /* Tier badge tooltip */
  .tier-badge[data-tip] {{ cursor: help; position: relative; }}
  .tier-badge[data-tip]:hover::after {{
    content: attr(data-tip);
    position: absolute;
    top: calc(100% + 8px);
    left: 0;
    width: 320px;
    max-width: 90vw;
    padding: 14px 16px;
    background: #1a1d23;
    color: #f7f8fa;
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.65;
    font-family: var(--mono);
    font-weight: 400;
    letter-spacing: 0;
    text-transform: none;
    white-space: pre-wrap;
    box-shadow: 0 6px 16px rgba(0,0,0,0.2);
    z-index: 1000;
    pointer-events: none;
  }}
  .metric .val {{
    font-family: var(--mono);
    font-size: 14px;
    font-weight: 500;
    color: var(--text);
  }}
  .metric .val.neg {{ color: var(--critical); }}
  .metric .val.pos {{ color: var(--positive); }}
  .metric .val.warn {{ color: var(--warning); }}
  .metric .val.composite {{
    font-size: 16px;
    font-weight: 600;
  }}
  .flags {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin: 8px 0;
  }}
  .flag {{
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-family: var(--mono);
    font-weight: 500;
  }}
  .flag-strict {{ background: var(--positive-light); color: var(--positive); }}
  .flag-fame-fail {{ background: var(--critical-light); color: var(--critical); }}
  .flag-large {{ background: var(--neutral-light); color: var(--neutral); }}
  .flag-fame-suspect {{ background: var(--warning-light); color: var(--warning); }}
  .flag-retail {{ background: var(--warning-light); color: var(--warning); }}
  .flag-sanity {{ background: var(--critical-light); color: var(--critical); }}
  details.snippets {{
    margin-top: 8px;
  }}
  details.snippets summary {{
    cursor: pointer;
    color: var(--text-muted);
    font-size: 12px;
    padding: 4px 0;
    user-select: none;
  }}
  details.snippets summary:hover {{ color: var(--accent); }}
  details.snippets[open] summary {{ color: var(--accent); }}
  .snippet-list {{
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px dashed var(--border);
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .snippet {{
    padding-left: 12px;
    border-left: 2px solid var(--border);
  }}
  .snippet .snip-title {{
    font-size: 13px;
    color: var(--text);
    line-height: 1.4;
  }}
  .snippet .snip-meta {{
    font-size: 11px;
    color: var(--text-faint);
    margin-top: 2px;
  }}
  .snippet .snip-text {{
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
    line-height: 1.5;
  }}
  .snippet a {{ color: var(--accent); text-decoration: none; }}
  .snippet a:hover {{ text-decoration: underline; }}
  /* Per-sector table */
  table.sector-table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    margin-top: 8px;
  }}
  table.sector-table th, table.sector-table td {{
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
  }}
  table.sector-table th {{
    background: var(--neutral-light);
    color: var(--text-muted);
    font-weight: 500;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}
  table.sector-table tr:last-child td {{ border-bottom: none; }}
  table.sector-table td.num {{ font-family: var(--mono); text-align: right; }}
  /* Footer */
  footer {{
    text-align: center;
    color: var(--text-faint);
    font-size: 11px;
    padding: 20px;
    margin-top: 40px;
  }}
  /* Profile C cards: more prominent, more spacious */
  .profile-c-wrapper {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    gap: 16px;
  }}
  .profile-c-wrapper .card {{
    padding: 20px 24px;
  }}

  /* ---- One-click rejection logging ---- */
  .kill-btn {{
    margin-left: auto;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-faint);
    font-size: 18px;
    line-height: 1;
    width: 26px;
    height: 26px;
    border-radius: 4px;
    cursor: pointer;
    padding: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }}
  .kill-btn:hover {{
    background: var(--critical-light);
    color: var(--critical);
    border-color: var(--critical);
  }}
  .card.killed {{
    opacity: 0.4;
    background: var(--bg);
  }}
  .card.killed .ticker,
  .card.killed .company {{
    text-decoration: line-through;
    text-decoration-color: var(--critical);
  }}
  .card.killed .kill-btn {{
    background: var(--critical-light);
    color: var(--critical);
    border-color: var(--critical);
  }}
  .card.killed .kill-btn::after {{
    content: " killed";
    font-size: 10px;
    margin-left: 4px;
  }}
  .card.killed .kill-btn {{
    width: auto;
    padding: 0 8px;
  }}

  /* Modal */
  .kill-modal-backdrop {{
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    display: none;
    z-index: 9999;
    align-items: center;
    justify-content: center;
  }}
  .kill-modal-backdrop.visible {{
    display: flex;
  }}
  .kill-modal {{
    background: var(--surface);
    border-radius: 8px;
    padding: 24px 28px;
    width: 480px;
    max-width: 95vw;
    box-shadow: 0 12px 40px rgba(0,0,0,0.25);
  }}
  .kill-modal-header {{
    font-size: 16px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 4px;
  }}
  .kill-modal-sub {{
    font-size: 12px;
    color: var(--text-muted);
    margin-bottom: 18px;
  }}
  .kill-modal-sub .kbd {{
    font-family: var(--mono, ui-monospace, Menlo, monospace);
    background: var(--bg);
    padding: 1px 5px;
    border-radius: 3px;
  }}
  .kill-reason-options {{
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 14px;
  }}
  .kill-reason-option {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.12s;
  }}
  .kill-reason-option:hover {{
    background: var(--accent-light);
    border-color: var(--accent);
  }}
  .kill-reason-option input[type="radio"] {{
    margin-top: 2px;
  }}
  .kill-reason-option .label {{
    font-weight: 500;
    color: var(--text);
  }}
  .kill-reason-option .hint {{
    color: var(--text-muted);
    font-size: 12px;
    margin-top: 2px;
  }}
  .kill-note {{
    width: 100%;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 8px 10px;
    font-family: inherit;
    font-size: 13px;
    resize: vertical;
    min-height: 50px;
    box-sizing: border-box;
    margin-bottom: 14px;
  }}
  .kill-note:focus {{
    outline: none;
    border-color: var(--accent);
  }}
  .kill-modal-actions {{
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }}
  .kill-modal-actions button {{
    padding: 8px 16px;
    border-radius: 4px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    font-size: 13px;
    cursor: pointer;
  }}
  .kill-modal-actions .kill-submit {{
    background: var(--critical);
    color: white;
    border-color: var(--critical);
  }}
  .kill-modal-actions .kill-submit:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
  }}

  /* LOUD persistence-offline banner — deliberately hard to ignore.
     The whole point of this control is to make a silent failure visible,
     so the styling is aggressive: red, pulsing, sticky-top, thick border,
     full-width. If you ever feel tempted to "tone this down" — DON'T.
     A subtle banner is a banner you stop seeing. */
  .persistence-banner {{
    display: none;
    position: sticky;
    top: 0;
    z-index: 9998;
    background: #b91c1c;
    color: white;
    padding: 14px 24px;
    font-size: 15px;
    font-weight: 700;
    text-align: center;
    border-bottom: 4px solid #7f1d1d;
    box-shadow: 0 4px 12px rgba(185, 28, 28, 0.4);
    letter-spacing: 0.3px;
    animation: persistence-pulse 2.5s infinite;
  }}
  .persistence-banner.visible {{
    display: block;
  }}
  .persistence-banner code {{
    background: rgba(0,0,0,0.3);
    padding: 3px 9px;
    border-radius: 3px;
    font-family: var(--mono, ui-monospace, Menlo, monospace);
    font-size: 13px;
    color: #fef3c7;
    margin: 0 4px;
  }}
  .persistence-banner .unsynced-warn {{
    display: inline-block;
    margin-left: 12px;
    background: rgba(0,0,0,0.35);
    padding: 3px 10px;
    border-radius: 3px;
    color: #fee2e2;
    font-size: 13px;
  }}
  @keyframes persistence-pulse {{
    0%, 100% {{ background: #b91c1c; }}
    50% {{ background: #991b1b; }}
  }}

  /* Per-row sync indicator on the kill button */
  .card.killed.unsynced .kill-btn {{
    background: #fef3c7;
    color: #92400e;
    border-color: #f59e0b;
  }}
  .card.killed.unsynced .kill-btn::after {{
    content: " killed (unsynced)";
  }}
  .card.killed.synced .kill-btn::after {{
    content: " killed";
  }}

  /* Export controls in the header */
  .rejection-controls {{
    display: inline-flex;
    gap: 8px;
    align-items: center;
    margin-left: 16px;
  }}
  .rejection-controls button {{
    padding: 5px 10px;
    border-radius: 4px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    font-size: 12px;
    cursor: pointer;
  }}
  .rejection-controls button:hover {{
    background: var(--accent-light);
    border-color: var(--accent);
  }}
  .rejection-count {{
    font-weight: 600;
    color: var(--critical);
  }}

  /* Compliance row — liquidity + mandate verdict per card */
  .compliance {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
    padding: 6px 8px;
    background: var(--bg);
    border-radius: 4px;
    border: 1px solid var(--border);
    font-size: 12px;
    align-items: center;
  }}
  .comp-verdict {{
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 11px;
    letter-spacing: 0.3px;
    cursor: help;
  }}
  .comp-pass {{
    background: var(--positive-light);
    color: var(--positive);
  }}
  .comp-fail {{
    background: var(--critical-light);
    color: var(--critical);
  }}
  .comp-review {{
    background: var(--warning-light);
    color: var(--warning);
  }}
  .comp-metric {{
    color: var(--text-muted);
    font-family: var(--mono, ui-monospace, Menlo, monospace);
  }}
  .comp-fail-reason {{
    color: var(--critical);
    font-family: var(--mono, ui-monospace, Menlo, monospace);
    font-size: 11px;
  }}

  /* Pairwise quality comparison block (item E) — facts, not verdicts */
  .pairwise-quality {{
    background: var(--accent-light);
    border: 1px solid #bfdbfe;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 12px 0 16px 0;
  }}
  .pwq-header {{
    font-size: 12px;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: 0.4px;
    text-transform: uppercase;
    margin-bottom: 8px;
  }}
  .pwq-list {{
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}
  .pwq-list li {{
    font-size: 13px;
    color: var(--text);
    padding: 3px 0;
  }}
  .pwq-ticker {{
    color: var(--text-muted);
    font-family: var(--mono, ui-monospace, Menlo, monospace);
    font-size: 12px;
  }}
  .pwq-val {{
    font-family: var(--mono, ui-monospace, Menlo, monospace);
    background: rgba(255, 255, 255, 0.55);
    padding: 1px 5px;
    border-radius: 2px;
  }}
  .pwq-footer {{
    margin-top: 8px;
    font-size: 11px;
    color: var(--text-muted);
    font-style: italic;
  }}
</style>
</head>
<body>

<!-- LOUD persistence-offline banner. Hidden when the local receiver is reachable.
     Visible (red + pulsing + sticky) the moment a /health probe fails, with the
     exact command to start the receiver and a running count of unsynced kills. -->
<div class="persistence-banner" id="persistence-banner">
  &#9888; PERSISTENCE OFFLINE — kills are stored in this browser only and will be LOST on cache clear or device change.
  Start the receiver: <code>python scripts/rejection_server.py</code>
  <span class="unsynced-warn" id="unsynced-warn" style="display:none;"></span>
</div>

<header class="top">
  <h1>Quiet Change Agent — Cross-sector sweep</h1>
  <div class="meta">
    Screened {n_sectors} narrative-light Japanese mid-cap sectors on {date}
    <span class="rejection-controls">
      <span>Rejections logged: <span class="rejection-count" id="rejection-count">0</span></span>
      <button id="export-rejections-btn" title="Download all logged rejections as CSV">Export CSV</button>
      <button id="clear-rejections-btn" title="Clear the local rejection log (does not affect downloaded CSVs)">Clear</button>
    </span>
  </div>
</header>

<div class="stat-bar">
  <div class="stat"><div class="num">{n_sectors}</div><div class="label">Sectors screened</div></div>
  <div class="stat"><div class="num">{total_pool}</div><div class="label">Companies in pool</div></div>
  <div class="stat"><div class="num">{total_band}</div><div class="label">Survived free filters</div></div>
  <div class="stat"><div class="num">{strict_hits}</div><div class="label">Strict-gate hits</div></div>
  <div class="stat"><div class="num">{profile_c_count}</div><div class="label">Profile C (unseen)</div></div>
</div>

<nav class="tabs">
  <button class="tab-btn active" data-tab="profile-c">Profile C — Unseen by market</button>
  <button class="tab-btn" data-tab="setting-a">Setting A — Attention as filter</button>
  <button class="tab-btn" data-tab="setting-b">Setting B — Attention as tie-break</button>
  <button class="tab-btn" data-tab="sectors">Per-sector summary</button>
  <button class="tab-btn" data-tab="about">About this output</button>
</nav>

<main>

<!-- PROFILE C -->
<section id="tab-profile-c" class="tab-panel active">
  <div class="section-intro">
    <h2>Profile C — Unseen by the market, quality growers</h2>
    <p><strong>Desk question:</strong> is this an under-recognised grower the market hasn't found?</p>
    <p>Filter: <code>attention ≤ 8 AND retail ≤ 2 AND mcap &lt; ¥200B</code> (must be investor-unseen + small/mid)
    → strict quality gate (3-of-3 OP positive, equity ≥30%, 3yr CAGR ≥3%, rev ≥¥3B)
    → rank by valuation (P/E + P/B sector-percentile). <strong>{profile_c_count} survivors</strong> from {total_band} free-filter passers.</p>
    <p><em>"Unseen" means unseen by investor coverage, not unknown to the public. A famous consumer brand can still be investor-overlooked — that's a legitimate mispricing find. Consumer fame ≠ fair price; investor coverage does.</em></p>
  </div>

  {profile_c_section}
</section>

<!-- SETTING A -->
<section id="tab-setting-a" class="tab-panel">
  <div class="section-intro">
    <h2>Setting A — Attention as filter (current default)</h2>
    <p><strong>Weights:</strong> divergence 0.35 / quality 0.35 / attention 0.30. Loud names get pulled DOWN in the ranking.</p>
    <p>Use this view when hunting for under-followed names. Article snippets are inline so you can verify the coverage claim in 30 seconds.</p>
  </div>

  {setting_a_section}
</section>

<!-- SETTING B -->
<section id="tab-setting-b" class="tab-panel">
  <div class="section-intro">
    <h2>Setting B — Attention as tie-break only</h2>
    <p><strong>Weights:</strong> divergence 0.45 / quality 0.45 / attention 0.10. Attention barely affects the rank.</p>
    <p>Use this view when interested in quality-divergence regardless of coverage. Compare top-3 between A and B to see which names are "punished by attention" in Setting A.</p>
  </div>

  {setting_b_section}
</section>

<!-- PER-SECTOR -->
<section id="tab-sectors" class="tab-panel">
  <div class="section-intro">
    <h2>Per-sector summary</h2>
    <p>How many companies entered the funnel per sector and how many cleared each gate.</p>
  </div>

  <table class="sector-table">
    <thead>
      <tr>
        <th>Sector</th>
        <th class="num">Pool</th>
        <th class="num">After universe filter</th>
        <th class="num">After split + band</th>
        <th class="num">Strict-gate hits</th>
        <th>Top name (composite)</th>
      </tr>
    </thead>
    <tbody>
      {sector_rows}
    </tbody>
  </table>
</section>

<!-- ABOUT -->
<section id="tab-about" class="tab-panel">
  <div class="section-intro">
    <h2>About this output</h2>
    <p><strong>What the tool does:</strong> screens Japanese mid-cap companies whose revenue is up but stock is down, then classifies them across three desk-actionable profiles.</p>
    <p><strong>Profile A — Idiosyncratic fallers, coverage shown.</strong> Fell ≥5pp more than sector peers. Desk question: is the existing coverage enough to explain the overshoot, or is this an overreaction? Snippets are visible per lead.</p>
    <p><strong>Profile B — Moved with sector.</strong> Fell roughly in line with peers. Desk question: is this a quality name worth a sector-recovery bet?</p>
    <p><strong>Profile C — Unseen by the market.</strong> Investor-thin coverage AND small/mid AND verified-quality AND cheap. The mission-aligned "overlooked grower" target. Capped at top 5 per sector by valuation.</p>
    <p><strong>Flags:</strong></p>
    <ul style="color: var(--text-muted); font-size: 13px;">
      <li><span class="flag flag-strict">STRICT</span> — passes the literal-unnoticed strict gate (attn ≤ 8 AND idio div ≤ −5pp)</li>
      <li><span class="flag flag-fame-fail">FAME_FAIL</span> — mcap ≥ ¥500B AND attn ≤ 8: mega-brand looking thin = search miss, do NOT present as overlooked</li>
      <li><span class="flag flag-fame-suspect">fame-suspect</span> — ¥300–500B + low attn: Mid400 brand, verify before promoting</li>
      <li><span class="flag flag-large">large</span> — ≥ ¥500B with adequate attention (informational)</li>
      <li><span class="flag flag-retail">retail-heavy</span> — &gt;2 retail forum hits visible (5ch/Yahoo/note.com)</li>
      <li><span class="flag flag-sanity">PE_SUSPECT</span> — P/E &lt; 3, likely one-off earnings inflation, verify</li>
    </ul>
    <p><strong>Data:</strong> Tempest API (financials, prices) + SerpAPI Google.co.jp (attention, retail-chatter probes). LLM cost: $0. Total sweep cost: ~$2 first run, free on re-runs (per-ticker SerpAPI cache).</p>
    <p style="color: var(--text-faint); font-size: 12px; margin-top: 16px;">Source JSON: <code>outputs/quiet_change_v2/sweep/_sweep_{date}.json</code></p>
  </div>
</section>

</main>

<footer>Generated {date} • Quiet Change Agent v2 • Data inlined offline</footer>

<!-- Rejection logging modal (built once, reused for every kill click) -->
<div class="kill-modal-backdrop" id="kill-modal-backdrop">
  <div class="kill-modal" role="dialog" aria-modal="true" aria-labelledby="kill-modal-title">
    <div class="kill-modal-header" id="kill-modal-title">Reject <span id="kill-target-label"></span></div>
    <div class="kill-modal-sub">
      Pick the closest reason. This feeds the tuning loop: e.g. "11 of last 30 kills were 'too well-known' → tighten fame guard."
      Stored locally in your browser; export to CSV when you're ready to share.
    </div>
    <div class="kill-reason-options" id="kill-reason-options">
      <label class="kill-reason-option">
        <input type="radio" name="kill-reason" value="too_well_known">
        <span>
          <span class="label">Too well-known</span>
          <span class="hint">Fame guard missed it; coverage is wider than the attention score shows.</span>
        </span>
      </label>
      <label class="kill-reason-option">
        <input type="radio" name="kill-reason" value="liquidity_too_thin">
        <span>
          <span class="label">Liquidity too thin</span>
          <span class="hint">Can't trade meaningful size; daily yen volume too low for our mandate.</span>
        </span>
      </label>
      <label class="kill-reason-option">
        <input type="radio" name="kill-reason" value="valuation_artifact">
        <span>
          <span class="label">Valuation looks like a data artifact</span>
          <span class="hint">P/E or P/B looks "cheap" because of a one-off / accounting quirk, not real value.</span>
        </span>
      </label>
      <label class="kill-reason-option">
        <input type="radio" name="kill-reason" value="quality_not_real">
        <span>
          <span class="label">Quality isn't really there</span>
          <span class="hint">Score is inflated by an unusual year, restructuring gain, or M&A — not durable.</span>
        </span>
      </label>
      <label class="kill-reason-option">
        <input type="radio" name="kill-reason" value="mandate_excluded">
        <span>
          <span class="label">Mandate / sector excluded</span>
          <span class="hint">Outside our remit (ESG, sector exclusion, mcap floor, regulatory, etc).</span>
        </span>
      </label>
      <label class="kill-reason-option">
        <input type="radio" name="kill-reason" value="other">
        <span>
          <span class="label">Other</span>
          <span class="hint">Add a one-line note describing the rejection dimension we don't yet model.</span>
        </span>
      </label>
    </div>
    <textarea class="kill-note" id="kill-note" placeholder="Optional note (required if 'Other')"></textarea>
    <div class="kill-modal-actions">
      <button class="kill-cancel" id="kill-cancel">Cancel</button>
      <button class="kill-submit" id="kill-submit" disabled>Log rejection</button>
    </div>
  </div>
</div>

<script>
  (function() {{
    // ---- Tab switching ----
    const tabs = document.querySelectorAll('.tab-btn');
    const panels = document.querySelectorAll('.tab-panel');
    tabs.forEach(btn => {{
      btn.addEventListener('click', () => {{
        tabs.forEach(t => t.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        window.scrollTo({{top: 0, behavior: 'smooth'}});
      }});
    }});

    // ---- Tooltip edge-detection ----
    // On hover, check if a 320px-wide tooltip would overflow the viewport's
    // right edge. If yes, add .tip-right so the CSS flips it to right-align.
    // Pure CSS can't do this conditionally; this is the smallest workable JS.
    const TIP_WIDTH = 320;
    const EDGE_PADDING = 20;
    document.querySelectorAll('[data-tip]').forEach(el => {{
      el.addEventListener('mouseenter', () => {{
        const rect = el.getBoundingClientRect();
        const overflowsRight = rect.left + TIP_WIDTH > window.innerWidth - EDGE_PADDING;
        el.classList.toggle('tip-right', overflowsRight);
      }});
    }});

    // ---- One-click rejection logging ----
    // localStorage key — versioned so a future schema change doesn't break
    // existing logs without warning. If you change the row shape, bump this.
    const LOG_KEY = 'quietChangeRejectionLog_v1';
    const SWEEP_DATE = '{date}';
    const RECEIVER_URL = 'http://127.0.0.1:5057';  // matches scripts/rejection_server.py
    const PROBE_INTERVAL_MS = 30000;  // re-check receiver every 30s so a
                                       // mid-session "python scripts/rejection_server.py"
                                       // is picked up without a page reload

    const backdrop = document.getElementById('kill-modal-backdrop');
    const submitBtn = document.getElementById('kill-submit');
    const cancelBtn = document.getElementById('kill-cancel');
    const noteInput = document.getElementById('kill-note');
    const targetLabel = document.getElementById('kill-target-label');
    const countEl = document.getElementById('rejection-count');
    const exportBtn = document.getElementById('export-rejections-btn');
    const clearBtn = document.getElementById('clear-rejections-btn');
    const banner = document.getElementById('persistence-banner');
    const unsyncedWarn = document.getElementById('unsynced-warn');

    let pendingCard = null;     // the card being killed
    let persistenceOnline = false;  // updated by probeReceiver()

    function loadLog() {{
      try {{
        return JSON.parse(localStorage.getItem(LOG_KEY) || '[]');
      }} catch (e) {{
        return [];
      }}
    }}
    function saveLog(arr) {{
      localStorage.setItem(LOG_KEY, JSON.stringify(arr));
      countEl.textContent = arr.length;
      updateBanner();
    }}
    function updateBanner() {{
      const log = loadLog();
      const unsyncedCount = log.filter(r => !r._synced).length;
      if (!persistenceOnline) {{
        banner.classList.add('visible');
        if (unsyncedCount > 0) {{
          unsyncedWarn.textContent = unsyncedCount + ' unsynced kill' + (unsyncedCount === 1 ? '' : 's') + ' at risk';
          unsyncedWarn.style.display = 'inline-block';
        }} else {{
          unsyncedWarn.style.display = 'none';
        }}
      }} else {{
        banner.classList.remove('visible');
      }}
    }}
    async function probeReceiver() {{
      try {{
        const r = await fetch(RECEIVER_URL + '/health', {{
          method: 'GET',
          cache: 'no-store',
          signal: AbortSignal.timeout(2000)
        }});
        persistenceOnline = r.ok;
      }} catch (e) {{
        persistenceOnline = false;
      }}
      updateBanner();
    }}
    async function sendToReceiver(row) {{
      try {{
        const r = await fetch(RECEIVER_URL + '/log', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify(row),
          signal: AbortSignal.timeout(3000)
        }});
        if (r.ok) {{ persistenceOnline = true; return true; }}
        persistenceOnline = false;
        return false;
      }} catch (e) {{
        persistenceOnline = false;
        return false;
      }}
    }}
    function applyKilledClassesFromLog() {{
      const log = loadLog();
      const byTicker = new Map(log.map(r => [r.ticker, r]));
      document.querySelectorAll('.card[data-card-ticker]').forEach(card => {{
        const t = card.dataset.cardTicker;
        if (byTicker.has(t)) {{
          card.classList.add('killed');
          card.classList.add(byTicker.get(t)._synced ? 'synced' : 'unsynced');
        }}
      }});
      countEl.textContent = log.length;
    }}

    function openModal(btn) {{
      pendingCard = btn.closest('.card');
      targetLabel.textContent = btn.dataset.ticker + ' ' + btn.dataset.company;
      // Reset form
      noteInput.value = '';
      document.querySelectorAll('input[name="kill-reason"]').forEach(r => r.checked = false);
      submitBtn.disabled = true;
      backdrop.classList.add('visible');
    }}
    function closeModal() {{
      backdrop.classList.remove('visible');
      pendingCard = null;
    }}
    function checkSubmitEnabled() {{
      const reason = document.querySelector('input[name="kill-reason"]:checked');
      const note = noteInput.value.trim();
      if (!reason) {{ submitBtn.disabled = true; return; }}
      if (reason.value === 'other' && !note) {{ submitBtn.disabled = true; return; }}
      submitBtn.disabled = false;
    }}

    // Wire up kill buttons
    document.querySelectorAll('.kill-btn').forEach(btn => {{
      btn.addEventListener('click', (e) => {{
        e.stopPropagation();
        openModal(btn);
      }});
    }});

    // Wire up modal controls
    document.querySelectorAll('input[name="kill-reason"]').forEach(r => {{
      r.addEventListener('change', checkSubmitEnabled);
    }});
    noteInput.addEventListener('input', checkSubmitEnabled);
    cancelBtn.addEventListener('click', closeModal);
    backdrop.addEventListener('click', (e) => {{
      if (e.target === backdrop) closeModal();
    }});
    document.addEventListener('keydown', (e) => {{
      if (e.key === 'Escape' && backdrop.classList.contains('visible')) closeModal();
    }});

    submitBtn.addEventListener('click', async () => {{
      if (!pendingCard) {{ closeModal(); return; }}
      const btn = pendingCard.querySelector('.kill-btn');
      const reason = document.querySelector('input[name="kill-reason"]:checked').value;
      const note = noteInput.value.trim();
      submitBtn.disabled = true;
      const row = {{
        timestamp: new Date().toISOString(),
        sweep_date: SWEEP_DATE,
        ticker: btn.dataset.ticker,
        company: btn.dataset.company,
        sector: btn.dataset.sector,
        profile: btn.dataset.profile,
        rank: btn.dataset.rank,
        tier: btn.dataset.tier,
        composite_at_kill: btn.dataset.composite,
        stock_3m: btn.dataset.stock3m,
        div_pp: btn.dataset.divPp,
        attn: btn.dataset.attn,
        retail: btn.dataset.retail,
        mcap_jpy: btn.dataset.mcap,
        liq_jpy_daily: btn.dataset.liq,
        flags_at_kill: btn.dataset.flags,
        reason_code: reason,
        note: note
      }};
      // POST to receiver first (durable). Only mark synced on a 200 — the
      // server only returns 200 after flush + fsync, so synced=true means
      // the row is on disk, not just buffered somewhere.
      const synced = await sendToReceiver(row);
      row._synced = synced;
      const log = loadLog();
      const existingIdx = log.findIndex(r => r.ticker === row.ticker);
      if (existingIdx >= 0) log[existingIdx] = row; else log.push(row);
      saveLog(log);
      pendingCard.classList.add('killed');
      pendingCard.classList.add(synced ? 'synced' : 'unsynced');
      closeModal();
    }});

    // CSV export
    function toCsvCell(v) {{
      if (v === undefined || v === null) return '';
      const s = String(v);
      if (/[",\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
      return s;
    }}
    exportBtn.addEventListener('click', () => {{
      const log = loadLog();
      if (log.length === 0) {{ alert('No rejections logged yet.'); return; }}
      const cols = [
        'timestamp', 'sweep_date', 'ticker', 'company', 'sector', 'profile',
        'rank', 'tier', 'composite_at_kill', 'stock_3m', 'div_pp', 'attn',
        'retail', 'mcap_jpy', 'liq_jpy_daily', 'flags_at_kill',
        'reason_code', 'note'
      ];
      const lines = [cols.join(',')];
      log.forEach(r => lines.push(cols.map(c => toCsvCell(r[c])).join(',')));
      const blob = new Blob([lines.join('\n')], {{type: 'text/csv;charset=utf-8;'}});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'rejection_log_' + SWEEP_DATE + '.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }});

    clearBtn.addEventListener('click', () => {{
      const log = loadLog();
      if (log.length === 0) return;
      if (!confirm('Clear ' + log.length + ' logged rejection(s) from local browser storage? (Already-downloaded CSVs and rows already written to the local receiver are unaffected.)')) return;
      localStorage.removeItem(LOG_KEY);
      document.querySelectorAll('.card.killed').forEach(c => {{
        c.classList.remove('killed');
        c.classList.remove('synced');
        c.classList.remove('unsynced');
      }});
      countEl.textContent = '0';
      updateBanner();
    }});

    // Retry unsynced rows whenever we discover the receiver is online.
    // This is the "I started the server mid-session" recovery path: any
    // localStorage-only kills get pushed to disk as soon as we can reach it.
    async function retryUnsynced() {{
      if (!persistenceOnline) return;
      const log = loadLog();
      let changed = false;
      for (const row of log) {{
        if (row._synced) continue;
        const ok = await sendToReceiver(row);
        if (ok) {{ row._synced = true; changed = true; }}
        else {{ break; }}  // receiver went down again, stop hammering
      }}
      if (changed) {{
        saveLog(log);
        applyKilledClassesFromLog();
      }}
    }}

    // Initial probe + periodic re-probe. If the user starts the receiver
    // mid-session, the banner clears on the next tick and any unsynced
    // kills get pushed durable automatically.
    (async function initPersistence() {{
      await probeReceiver();
      await retryUnsynced();
      applyKilledClassesFromLog();
      setInterval(async () => {{
        await probeReceiver();
        await retryUnsynced();
      }}, PROBE_INTERVAL_MS);
    }})();
  }})();
</script>

</body>
</html>
"""


# -- Tooltips --
# Plain-language baselines shown on hover for every metric label.
# Kept short — one-line definition + value-zone interpretation + a warning if any.

METRIC_TIPS = {
    "Composite": (
        "Final ranking, 0–100\n"
        "\n"
        "Combines divergence + quality + attention\n"
        "using this setting's weights.\n"
        "\n"
        "Higher = stronger overall candidate."
    ),
    "Composite (cheap-of-good)": (
        "Profile C ranking, 0–100\n"
        "\n"
        "Within the verified-good pool, ranks names\n"
        "by valuation cheapness vs sector peers.\n"
        "\n"
        "Higher = cheaper."
    ),
    "Stock 3m": (
        "Stock price move, last 3 months\n"
        "\n"
        "Why this name entered the screen.\n"
        "Paired with rising revenue, it's the\n"
        "'something might be mispriced' signal."
    ),
    "Divergence (vs peers)": (
        "This stock's move minus sector peer median\n"
        "\n"
        "  ≤ −5pp    Idiosyncratic drop (Profile A)\n"
        "  ±5pp      Moved with sector (Profile B)\n"
        "\n"
        "Bigger negative = more company-specific."
    ),
    "Quality (sector pct)": (
        "0–100 percentile of quality within sector\n"
        "\n"
        "Composite of:\n"
        "  • 3yr revenue CAGR\n"
        "  • Operating profit margin\n"
        "  • Margin trend\n"
        "  • Equity ratio\n"
        "  • ROE\n"
        "\n"
        "Higher = stronger fundamentals vs peers."
    ),
    "Attention": (
        "Investor coverage of THIS stock's drop\n"
        "\n"
        "  ≤ 4       Essentially uncovered\n"
        "  4 – 8     Thin\n"
        "  8 – 15    Moderate\n"
        "  15 +      Noisy\n"
        "\n"
        "Built from brokerage + editorial + retail\n"
        "channels combined."
    ),
    "Retail": (
        "Hits on 5ch / Yahoo boards / note.com\n"
        "(retail-investor spaces)\n"
        "\n"
        "  0 – 2     No retail buzz\n"
        "  > 2       Retail-pumped (red flag)\n"
        "\n"
        "Catches names that look thin to brokerages\n"
        "but are loud on social."
    ),
    "Retail hits": (
        "Hits on 5ch / Yahoo boards / note.com\n"
        "(retail-investor spaces)\n"
        "\n"
        "  0 – 2     No retail buzz\n"
        "  > 2       Retail-pumped (red flag)\n"
        "\n"
        "Catches names that look thin to brokerages\n"
        "but are loud on social."
    ),
    "Market cap": (
        "Total company value\n"
        "= price × shares outstanding\n"
        "\n"
        "  < ¥30B           Micro-cap (often illiquid)\n"
        "  ¥30B – ¥200B     Small/mid (sweet spot)\n"
        "  ¥200B – ¥1T      Large\n"
        "  ¥1T +            Mega-cap"
    ),
    "Liquidity / day": (
        "Average daily traded value (¥ per day)\n"
        "\n"
        "  < ¥50M           Untradeable for funds\n"
        "  ¥50M – ¥500M     Small positions only\n"
        "  > ¥500M          Normal mid-cap fund range\n"
        "\n"
        "Decides whether the fund can actually\n"
        "build/exit a meaningful position."
    ),
    "P/E": (
        "Price ÷ Earnings per share\n"
        "\n"
        "Years of current profit you'd pay\n"
        "for the stock.\n"
        "\n"
        "  5 – 10     Cheap\n"
        "  10 – 20    Normal\n"
        "  20 +       Expensive (paying for growth)\n"
        "  < 3        Likely artifact (PE_SUSPECT)"
    ),
    "P/B": (
        "Price ÷ Book value per share\n"
        "\n"
        "What you pay vs the company's net assets.\n"
        "\n"
        "  < 1.0      Below breakup value\n"
        "  1.0 – 2.0  Normal\n"
        "  3.0 +      Paying premium for brand"
    ),
    "Revenue": (
        "Most recent annual sales (in yen)\n"
        "\n"
        "Company size indicator.\n"
        "\n"
        "Smaller revenue often means less\n"
        "analyst coverage — more potential\n"
        "to be overlooked."
    ),
    "3yr CAGR": (
        "Compound annual revenue growth\n"
        "over the last 3 years\n"
        "\n"
        "  < 3%       Barely growing (filtered out\n"
        "             of Profile C)\n"
        "  3 – 5%     Steady\n"
        "  5 – 10%    Good\n"
        "  10% +      Fast grower\n"
        "\n"
        "Multi-year smoothing protects against\n"
        "one-lucky-year flukes."
    ),
    "OP margin": (
        "Operating profit ÷ revenue (%)\n"
        "\n"
        "How much of each ¥100 in sales\n"
        "becomes operating profit.\n"
        "\n"
        "  < 3%       Thin (distributors)\n"
        "  8 – 15%    Healthy\n"
        "  20% +      High-margin business\n"
        "  < 0%       Losing money"
    ),
    "Equity ratio": (
        "Equity ÷ total assets (%)\n"
        "\n"
        "Balance-sheet strength.\n"
        "\n"
        "  < 20%      Heavily leveraged (risky)\n"
        "  30 – 50%   Healthy\n"
        "  60% +      Very conservative\n"
        "\n"
        "Profile C requires ≥ 30%."
    ),
    "ROE": (
        "Net profit ÷ equity (%)\n"
        "\n"
        "Return shareholders earn per\n"
        "¥ invested.\n"
        "\n"
        "  < 5%       Inefficient\n"
        "  5 – 10%    Average\n"
        "  10 – 15%   Good\n"
        "  15% +      Excellent\n"
        "\n"
        "Caveat: very high equity ratio drags\n"
        "ROE down even on great businesses."
    ),
}

# Tooltips for flags
FLAG_TIPS = {
    "STRICT": (
        "Passes the literal-unnoticed strict gate\n"
        "\n"
        "  Attention ≤ 8\n"
        "  AND\n"
        "  Divergence ≤ −5pp\n"
        "\n"
        "Rare combination — overlooked AND\n"
        "fell harder than peers."
    ),
    "FAME_FAIL": (
        "Mega-brand search-miss\n"
        "\n"
        "  Market cap ≥ ¥500B\n"
        "  AND\n"
        "  Attention ≤ 8\n"
        "\n"
        "The search missed coverage on a\n"
        "famous name.\n"
        "\n"
        "DO NOT present as 'overlooked.'"
    ),
    "fame-suspect": (
        "Mid400 brand with low attention\n"
        "\n"
        "  Market cap ¥300B – ¥500B\n"
        "  AND\n"
        "  Attention ≤ 8\n"
        "\n"
        "Soft fame-failure suspect.\n"
        "Verify manually before promoting."
    ),
    "large": (
        "Large name, attention adequate\n"
        "\n"
        "  Market cap ≥ ¥500B\n"
        "  Attention > 8\n"
        "\n"
        "Informational — not a failure,\n"
        "just noting it's a big name."
    ),
    "retail": (
        "Retail-pumped name\n"
        "\n"
        "  > 2 hits on 5ch / Yahoo / note.com\n"
        "\n"
        "Brokerage signal says 'thin' but\n"
        "social isn't. Attention score already\n"
        "counts retail hits, so demoted softly\n"
        "in the ranking."
    ),
    "PE_SUSPECT": (
        "Valuation artifact suspect\n"
        "\n"
        "  P/E < 3\n"
        "\n"
        "Almost always a one-off (gain on sale,\n"
        "deconsolidation, tax credit) inflating\n"
        "EPS temporarily, OR a stale price.\n"
        "\n"
        "The P/E + P/B composite can't catch this\n"
        "because both share the same price\n"
        "numerator. Verify before trusting."
    ),
}

# Tooltips for tier badges
TIER_TIPS = {
    "BAND": (
        "TOPIX-scaled name\n"
        "\n"
        "  Small 1, Small 2, or Mid400\n"
        "\n"
        "Mid-cap band — institutional analysts\n"
        "typically cover this tier.\n"
        "\n"
        "Liquidity usually adequate for\n"
        "fund-sized positions."
    ),
    "DASH": (
        "Unscaled by TOPIX\n"
        "\n"
        "  TSE Standard, TSE Growth, or\n"
        "  sub-TOPIX-500 Prime\n"
        "\n"
        "Genuinely small or specialty.\n"
        "Liquidity often thin — check the\n"
        "Liq/day column.\n"
        "\n"
        "Verified safe for B2B sectors.\n"
        "Consumer-sector dash names get\n"
        "the retail-chatter flag."
    ),
}


# -- Renderers --

def _fmt_num(v, *, signed=False, decimals=1, suffix=""):
    if v is None:
        return "—"
    try:
        v = float(v)
    except Exception:
        return "—"
    sign = "+" if (signed and v > 0) else ""
    return f"{sign}{v:.{decimals}f}{suffix}"


def _fmt_yen(v):
    if v is None or v == 0:
        return "—"
    if v >= 1e12:
        return f"¥{v/1e12:.1f}T"
    if v >= 1e9:
        return f"¥{v/1e9:.0f}B"
    if v >= 1e6:
        return f"¥{v/1e6:.0f}M"
    return f"¥{v:,.0f}"


def _key_html(label: str) -> str:
    """Render a metric label with its tooltip if one is defined."""
    tip = METRIC_TIPS.get(label, "")
    if tip:
        return f'<div class="key" data-tip="{html.escape(tip)}">{html.escape(label)}</div>'
    return f'<div class="key">{html.escape(label)}</div>'


def _val_class(v, *, positive_good=False, negative_bad=True):
    if v is None:
        return ""
    try:
        v = float(v)
    except Exception:
        return ""
    if positive_good and v > 0:
        return "pos"
    if negative_bad and v < 0:
        return "neg"
    return ""


def _render_pairwise_quality(rows: list[dict], profile_c: bool = False, max_compare: int = 3) -> str:
    """Pairwise quality comparison across top-N rows in a subgroup.

    Pure deterministic template (item E from 2026-05-24 build). For each
    metric the top-N rows have data on, identifies the leader and the
    second-place value. Outputs sentences like:
        "X leads on margin (12.0% vs 8.0%)"
        "Y leads on 3yr CAGR (9.0% vs 4.0%)"

    NO LLM and NO verdict — only facts about which name wins on which axis.
    The desk decides what "winning on margin" means for their thesis.
    Comparisons skipped when the spread between #1 and #2 is below a
    meaningfulness threshold (avoids noise like "wins by 0.1pp").
    """
    if len(rows) < 2:
        return ""
    pool = rows[:max_compare]

    # (field, label, suffix, decimals, higher_is_better, min_spread)
    metrics: list[tuple[str, str, str, int, bool, float]] = [
        ("op_margin_latest", "OP margin",   "%",   1, True,  2.0),
        ("revenue_cagr_3y", "3yr CAGR",     "%",   1, True,  1.5),
        ("equity_ratio",    "equity ratio", "%",   1, True,  5.0),
        ("roe",             "ROE",          "%",   1, True,  2.0),
        ("quality_composite","quality score","",   1, True,  3.0),
    ]
    if profile_c:
        metrics += [
            ("pe",              "P/E",       "x",   2, False, 1.0),
            ("pb",              "P/B",       "x",   2, False, 0.15),
            ("valuation_rank",  "valuation", "",    1, True,  3.0),
        ]

    sentences: list[str] = []
    for field, label, suffix, dp, higher_better, min_spread in metrics:
        scored = [(r.get(field), r) for r in pool if r.get(field) is not None]
        if len(scored) < 2:
            continue
        scored.sort(key=lambda x: x[0], reverse=higher_better)
        leader_val, leader_row = scored[0]
        runner_val, _ = scored[1]
        spread = abs(leader_val - runner_val)
        if spread < min_spread:
            continue
        leader_name = html.escape(leader_row.get("company", "?"))
        leader_ticker = html.escape(leader_row.get("ticker", ""))
        sentences.append(
            f'<li><strong>{leader_name}</strong> <span class="pwq-ticker">({leader_ticker})</span> '
            f'leads on <strong>{label}</strong> '
            f'(<span class="pwq-val">{leader_val:.{dp}f}{suffix}</span> '
            f'vs <span class="pwq-val">{runner_val:.{dp}f}{suffix}</span>)</li>'
        )
    if not sentences:
        return ""
    return f"""
    <div class="pairwise-quality">
      <div class="pwq-header">Where each leads (top {len(pool)} side-by-side)</div>
      <ul class="pwq-list">{"".join(sentences)}</ul>
      <div class="pwq-footer">Facts only — no verdict on which to pick. The desk weighs which dimension matters for the thesis.</div>
    </div>
    """


def _render_compliance(c: dict) -> str:
    """Render the liquidity + mandate compliance row inside a lead card.

    Plain facts the desk can act on: can we build this in N days, does it
    pass the encoded mandate. No verdicts on the investment itself — only
    arithmetic on the desk's stated rules.
    """
    if not c:
        return ""
    verdict = c.get("verdict") or "—"
    dtb = c.get("days_to_build")
    dte = c.get("days_to_exit")
    failures = c.get("failures") or []
    needs_review = c.get("needs_review") or []
    verdict_class = {
        "PASS": "comp-pass",
        "FAIL": "comp-fail",
        "NEEDS_REVIEW": "comp-review",
    }.get(verdict, "comp-pass")
    tip_lines = [
        f"Mandate compliance: {verdict}",
        "",
        "Pure arithmetic against config/fund_profile.json.",
        "Edit that file to change AUM, position size, mandate rules.",
    ]
    if failures:
        tip_lines.append("")
        tip_lines.append("Failures:")
        for f in failures:
            tip_lines.append(f"  - {html.escape(f)}")
    if needs_review:
        tip_lines.append("")
        tip_lines.append("Needs review (data missing):")
        for n in needs_review:
            tip_lines.append(f"  - {html.escape(n)}")
    tip = html.escape("\n".join(tip_lines))

    parts: list[str] = []
    parts.append(
        f'<span class="comp-verdict {verdict_class}" data-tip="{tip}">'
        f'mandate: {html.escape(verdict)}</span>'
    )
    if dtb is not None:
        parts.append(f'<span class="comp-metric">build: {dtb}d</span>')
    if dte is not None and dte != dtb:
        parts.append(f'<span class="comp-metric">exit: {dte}d</span>')
    if failures:
        first_fail = html.escape(failures[0])
        more = f' +{len(failures)-1} more' if len(failures) > 1 else ""
        parts.append(f'<span class="comp-fail-reason">{first_fail}{more}</span>')
    return f'<div class="compliance">{"".join(parts)}</div>'


def _flag_keys(row: dict) -> list[str]:
    """Semantic flag tokens for a row (data-attr companion to _render_flags)."""
    keys: list[str] = []
    if row.get("strict_hit"):
        keys.append("STRICT")
    ff = row.get("fame_flag", "")
    if ff in ("FAME_FAIL", "fame_suspect", "large"):
        keys.append(ff)
    if (row.get("retail") or 0) > 2:
        keys.append("RETAIL")
    if row.get("sanity_flag"):
        keys.append(str(row["sanity_flag"]))
    return keys


def _render_flags(row: dict) -> str:
    flags = []
    if row.get("strict_hit"):
        tip = html.escape(FLAG_TIPS["STRICT"])
        flags.append(f'<span class="flag flag-strict" data-tip="{tip}">STRICT</span>')
    ff = row.get("fame_flag", "")
    if ff == "FAME_FAIL":
        tip = html.escape(FLAG_TIPS["FAME_FAIL"])
        flags.append(f'<span class="flag flag-fame-fail" data-tip="{tip}">FAME_FAIL</span>')
    elif ff == "fame_suspect":
        tip = html.escape(FLAG_TIPS["fame-suspect"])
        flags.append(f'<span class="flag flag-fame-suspect" data-tip="{tip}">fame-suspect</span>')
    elif ff == "large":
        tip = html.escape(FLAG_TIPS["large"])
        flags.append(f'<span class="flag flag-large" data-tip="{tip}">large</span>')
    if (row.get("retail") or 0) > 2:
        tip = html.escape(FLAG_TIPS["retail"])
        flags.append(f'<span class="flag flag-retail" data-tip="{tip}">retail {row["retail"]}</span>')
    if row.get("sanity_flag"):
        tip = html.escape(FLAG_TIPS["PE_SUSPECT"])
        flags.append(f'<span class="flag flag-sanity" data-tip="{tip}">{html.escape(row["sanity_flag"])}</span>')
    return "".join(flags)


def _render_snippets(snippets: list[dict]) -> str:
    if not snippets:
        return ""
    items = []
    for s in snippets:
        title = html.escape(s.get("title", ""))[:200]
        snippet_text = html.escape(s.get("snippet", ""))
        url = html.escape(s.get("url", ""))
        date_str = html.escape(s.get("date", ""))
        kind = html.escape(s.get("kind", ""))
        title_part = (
            f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'
            if url else title
        )
        meta_parts = [kind] + ([date_str] if date_str else [])
        meta_str = " • ".join(meta_parts)
        snip_text_html = (
            f'<div class="snip-text">{snippet_text}</div>' if snippet_text else ""
        )
        items.append(f"""
        <div class="snippet">
          <div class="snip-title">{title_part}</div>
          <div class="snip-meta">{meta_str}</div>
          {snip_text_html}
        </div>""")
    return f"""
    <details class="snippets">
      <summary>▸ Show {len(snippets)} article snippet{'s' if len(snippets) != 1 else ''}</summary>
      <div class="snippet-list">{''.join(items)}</div>
    </details>"""


def _render_lead_card(rank: int, r: dict, profile_c: bool = False) -> str:
    klass = "card profile-c" if profile_c else "card"
    tier_class = f"tier-{html.escape(r.get('tier','?'))}"
    company = html.escape(r.get("company", "?"))
    ticker = html.escape(r.get("ticker", ""))
    sector = html.escape(r.get("sector", ""))

    # Data attributes for the one-click rejection logger. We capture the
    # composite score and key signals AT TIME OF KILL so that later analysis
    # can ask "what fraction of high-composite names got killed for reason X"
    # — the diagnostic that actually tunes a threshold. See
    # outputs/desk_review/REJECTION_LOG_TEMPLATE.csv for the matching schema.
    profile_label = "C_UNSEEN_QUALITY" if profile_c else (r.get("profile") or "OTHER")
    composite_val = r.get("valuation_rank") if profile_c else r.get("composite")
    kill_attrs = (
        f'data-ticker="{ticker}" '
        f'data-company="{company}" '
        f'data-sector="{sector}" '
        f'data-profile="{html.escape(str(profile_label))}" '
        f'data-rank="{rank}" '
        f'data-tier="{html.escape(r.get("tier", "?"))}" '
        f'data-composite="{composite_val if composite_val is not None else ""}" '
        f'data-stock-3m="{r.get("stock_3m") if r.get("stock_3m") is not None else ""}" '
        f'data-div-pp="{r.get("div_pp") if r.get("div_pp") is not None else ""}" '
        f'data-attn="{r.get("attn") if r.get("attn") is not None else ""}" '
        f'data-retail="{r.get("retail") or 0}" '
        f'data-mcap="{r.get("mcap_jpy") if r.get("mcap_jpy") is not None else ""}" '
        f'data-liq="{r.get("liq_jpy_daily") if r.get("liq_jpy_daily") is not None else ""}" '
        f'data-flags="{html.escape(",".join(_flag_keys(r)))}"'
    )

    # Metric rows — different for Profile C vs Setting A/B
    if profile_c:
        metric_html = f"""
        <div class="metrics">
          <div class="metric">{_key_html("Composite (cheap-of-good)")}
            <div class="val composite">{_fmt_num(r.get('valuation_rank'), decimals=1)}</div></div>
          <div class="metric">{_key_html("P/E")}
            <div class="val">{_fmt_num(r.get('pe'), decimals=2)}</div></div>
          <div class="metric">{_key_html("P/B")}
            <div class="val">{_fmt_num(r.get('pb'), decimals=2)}</div></div>
          <div class="metric">{_key_html("Revenue")}
            <div class="val">{_fmt_yen(r.get('latest_revenue'))}</div></div>
          <div class="metric">{_key_html("3yr CAGR")}
            <div class="val {_val_class(r.get('revenue_cagr_3y'), positive_good=True, negative_bad=False)}">{_fmt_num(r.get('revenue_cagr_3y'), signed=True, decimals=1, suffix='%')}</div></div>
          <div class="metric">{_key_html("OP margin")}
            <div class="val">{_fmt_num(r.get('op_margin_latest'), decimals=1, suffix='%')}</div></div>
          <div class="metric">{_key_html("Equity ratio")}
            <div class="val">{_fmt_num(r.get('equity_ratio'), decimals=1, suffix='%')}</div></div>
          <div class="metric">{_key_html("ROE")}
            <div class="val">{_fmt_num(r.get('roe'), decimals=1, suffix='%')}</div></div>
          <div class="metric">{_key_html("Attention")}
            <div class="val">{_fmt_num(r.get('attn'), signed=True, decimals=1)}</div></div>
          <div class="metric">{_key_html("Retail hits")}
            <div class="val">{r.get('retail', 0)}</div></div>
          <div class="metric">{_key_html("Market cap")}
            <div class="val">{_fmt_yen(r.get('mcap_jpy'))}</div></div>
          <div class="metric">{_key_html("Liquidity / day")}
            <div class="val {('warn' if (r.get('liq_jpy_daily') or 0) < 5e7 else '')}">{_fmt_yen(r.get('liq_jpy_daily'))}</div></div>
        </div>
        """
    else:
        metric_html = f"""
        <div class="metrics">
          <div class="metric">{_key_html("Composite")}
            <div class="val composite">{_fmt_num(r.get('composite'), decimals=1)}</div></div>
          <div class="metric">{_key_html("Stock 3m")}
            <div class="val {_val_class(r.get('stock_3m'))}">{_fmt_num(r.get('stock_3m'), signed=True, decimals=1, suffix='%')}</div></div>
          <div class="metric">{_key_html("Divergence (vs peers)")}
            <div class="val {_val_class(r.get('div_pp'))}">{_fmt_num(r.get('div_pp'), signed=True, decimals=1, suffix='pp')}</div></div>
          <div class="metric">{_key_html("Quality (sector pct)")}
            <div class="val">{_fmt_num(r.get('quality_composite'), decimals=1)}</div></div>
          <div class="metric">{_key_html("Attention")}
            <div class="val">{_fmt_num(r.get('attn'), signed=True, decimals=1)}</div></div>
          <div class="metric">{_key_html("Retail")}
            <div class="val">{r.get('retail', 0)}</div></div>
          <div class="metric">{_key_html("Market cap")}
            <div class="val">{_fmt_yen(r.get('mcap_jpy'))}</div></div>
          <div class="metric">{_key_html("Liquidity / day")}
            <div class="val {('warn' if (r.get('liq_jpy_daily') or 0) < 5e7 else '')}">{_fmt_yen(r.get('liq_jpy_daily'))}</div></div>
        </div>
        """

    flags_html = _render_flags(r)
    snippets_html = _render_snippets(r.get("snippets") or [])
    compliance_html = _render_compliance(r.get("compliance") or {})

    tier_str = r.get('tier','?')
    tier_tip = html.escape(TIER_TIPS.get(tier_str, ""))
    tier_tip_attr = f' data-tip="{tier_tip}"' if tier_tip else ""

    return f"""
    <div class="{klass}" data-card-ticker="{ticker}">
      <div class="rank-row">
        <span class="rank">#{rank}</span>
        <span class="ticker">{ticker}</span>
        <span class="company">{company}</span>
        <span class="sector-tag">{sector}</span>
        <span class="tier-badge {tier_class}"{tier_tip_attr}>{html.escape(tier_str)}</span>
        <button class="kill-btn" {kill_attrs} title="Reject this name (log a reason — feeds the desk's tuning loop)">&times;</button>
      </div>
      {metric_html}
      {f'<div class="flags">{flags_html}</div>' if flags_html else ''}
      {compliance_html}
      {snippets_html}
    </div>
    """


def _render_setting_section(top_rows: list[dict], comp_field: str) -> str:
    a_rows = [r for r in top_rows if r["profile"] == "A_IDIOSYNCRATIC"]
    b_rows = [r for r in top_rows if r["profile"] == "B_SECTOR_MOVE_THIN"]
    other_rows = [r for r in top_rows if r["profile"] == "OTHER"]

    parts = []

    parts.append(f"""
    <div class="subgroup-header">
      <h3>Profile A — Idiosyncratic fallers, coverage shown</h3>
      <span class="count">{len(a_rows)} names</span>
      <span class="desk-q">"Is the existing coverage enough to explain a 5pp+ overshoot, or is this an overreaction?"</span>
    </div>
    {_render_pairwise_quality(a_rows)}
    <div class="cards">
      {''.join(_render_lead_card(i+1, r) for i, r in enumerate(a_rows))}
    </div>
    """)

    parts.append(f"""
    <div class="subgroup-header">
      <h3>Profile B — Moved with sector</h3>
      <span class="count">{len(b_rows)} names</span>
      <span class="desk-q">"Is this a quality name worth a sector-recovery bet?"</span>
    </div>
    {_render_pairwise_quality(b_rows)}
    <div class="cards">
      {''.join(_render_lead_card(i+1, r) for i, r in enumerate(b_rows))}
    </div>
    """)

    if other_rows:
        parts.append(f"""
        <div class="subgroup-header">
          <h3>Other</h3>
          <span class="count">{len(other_rows)} names</span>
          <span class="desk-q">Positive divergence — fell less than peers</span>
        </div>
        <div class="cards">
          {''.join(_render_lead_card(i+1, r) for i, r in enumerate(other_rows))}
        </div>
        """)

    return "".join(parts)


def _render_profile_c_section(profile_c_per_sector: dict) -> str:
    if not profile_c_per_sector:
        return '<div class="section-intro"><p>No names passed both gates this run.</p></div>'

    parts = []
    for sector in sorted(profile_c_per_sector.keys()):
        names = profile_c_per_sector[sector]
        if not names:
            continue
        parts.append(f"""
        <div class="subgroup-header">
          <h3>{html.escape(sector)}</h3>
          <span class="count">{len(names)} name{'s' if len(names) != 1 else ''}</span>
        </div>
        {_render_pairwise_quality(names, profile_c=True)}
        <div class="profile-c-wrapper">
          {''.join(_render_lead_card(i+1, r, profile_c=True) for i, r in enumerate(names))}
        </div>
        """)
    return "".join(parts)


def _render_sector_rows(per_sector: list[dict]) -> str:
    rows = []
    for s in per_sector:
        name = html.escape(s.get("sector_33_name", "?"))
        st = s.get("stats") or {}
        top = s.get("top_watchlist") or {}
        top_name = html.escape(top.get("company_name") or "—")
        top_ticker = html.escape(top.get("ticker") or "")
        top_comp = top.get("watchlist_composite") or 0
        rows.append(f"""
        <tr>
          <td>{name}</td>
          <td class="num">{st.get('pool_size', '—')}</td>
          <td class="num">{st.get('after_universe_filter', '—')}</td>
          <td class="num">{st.get('after_scale_band', '—')}</td>
          <td class="num">{st.get('strict_dual_gate_hits', '—')}</td>
          <td><span style="font-family: var(--mono); color: var(--accent);">{top_ticker}</span> {top_name} <span style="color: var(--text-muted); font-family: var(--mono);">({top_comp:.1f})</span></td>
        </tr>
        """)
    return "".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="specific sweep date (YYYY-MM-DD). Default: latest.")
    args = ap.parse_args(argv)

    if args.date:
        sweep_path = SWEEP_DIR / f"_sweep_{args.date}.json"
        if not sweep_path.exists():
            print(f"ERROR: sweep file not found at {sweep_path}")
            return 1
    else:
        sweep_path = _latest_sweep()
        if not sweep_path:
            print("ERROR: no sweep JSON found.")
            return 1

    print(f"Loading sweep: {sweep_path}")
    sweep = json.load(open(sweep_path, encoding="utf-8"))
    sweep_date = sweep.get("screened_at") or date.today().isoformat()

    # Slim each row for display
    setting_a_rows = [_slim_row(r, "comp_a30") for r in sweep.get("global_watchlist_setting_a_top", [])]
    setting_b_rows = [_slim_row(r, "comp_a10") for r in sweep.get("global_watchlist_setting_b_top", [])]
    # Re-tag _sector field on Setting B rows (they're the same objects but profile attribute is the same)
    profile_c_per_sector_raw = sweep.get("profile_c_top_per_sector") or {}
    profile_c_per_sector: dict[str, list[dict]] = {}
    profile_c_count = 0
    for sector, names in profile_c_per_sector_raw.items():
        slim_names: list[dict] = []
        for n in names:
            # Profile C rows have _sector implicit from their dict key
            n["_sector"] = sector
            slim = _slim_row(n)
            slim["sector"] = sector
            slim_names.append(slim)
            profile_c_count += 1
        profile_c_per_sector[sector] = slim_names

    totals = sweep.get("totals") or {}

    html_out = HTML_TEMPLATE.format(
        date=sweep_date,
        n_sectors=sweep.get("n_sectors", 0),
        total_pool=totals.get("pool_size", 0),
        total_band=totals.get("after_scale_band", 0),
        strict_hits=totals.get("strict_dual_gate_hits", 0),
        profile_c_count=profile_c_count,
        profile_c_section=_render_profile_c_section(profile_c_per_sector),
        setting_a_section=_render_setting_section(setting_a_rows, "comp_a30"),
        setting_b_section=_render_setting_section(setting_b_rows, "comp_a10"),
        sector_rows=_render_sector_rows(sweep.get("per_sector_summary") or []),
    )

    UI_DIR.mkdir(parents=True, exist_ok=True)
    out_path = UI_DIR / f"sweep_{sweep_date}.html"
    out_path.write_text(html_out, encoding="utf-8")
    print(f"\nUI written to: {out_path}")
    print(f"Open in browser:  file:///{out_path.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
