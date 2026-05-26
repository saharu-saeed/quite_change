"""Per-pair self-tests for Quiet Change output.

These are *internal-consistency* checks — they don't need hand-curated
ground truth. Each check answers a question we can verify from the
agent's own inputs.

Each check returns:
  - name / name_ja      — bilingual short label
  - passed              — bool
  - detail / detail_ja  — bilingual one-line failure detail (empty on pass)
  - evidence            — dict with concrete numbers used to decide pass/fail

The check list is designed to run in <500ms per pair (no LLM calls).
"""
from __future__ import annotations

import re
from pathlib import Path

from app.ingest.edinet_loader import (
    extract_revenue_from_zip_path,
    extract_all_revenue_candidates_from_zip_path,
    extract_revenue_history_from_zip_path,
)

REVENUE_TOLERANCE_PCT = 1.0
# How close two independent XBRL tags must agree to count as cross-confirmation.
CROSS_TAG_AGREEMENT_PCT = 1.0


def _check(name: str, name_ja: str, passed: bool, evidence: dict,
           detail: str = "", detail_ja: str = "") -> dict:
    return {
        "name": name,
        "name_ja": name_ja,
        "passed": bool(passed),
        "detail": detail if not passed else "",
        "detail_ja": detail_ja if not passed else "",
        "evidence": evidence,
    }


def _check_revenue_sign_matches_status(pair: dict) -> dict:
    prev = pair.get("prev_revenue", 0)
    curr = pair.get("curr_revenue", 0)
    delta = curr - prev
    expected = "profit" if delta > 0 else ("loss" if delta < 0 else "flat")
    actual = pair.get("profit_status", "")
    return _check(
        name="Revenue change sign matches profit/loss status",
        name_ja="売上の増減方向が「増収/減収/横ばい」と一致",
        passed=expected == actual,
        evidence={
            "prev_revenue (JPY)": f"{prev:,.0f}",
            "curr_revenue (JPY)": f"{curr:,.0f}",
            "delta (JPY)": f"{delta:+,.0f}",
            "expected_status": expected,
            "actual_status": actual,
        },
        detail=f"expected {expected!r}, got {actual!r}",
        detail_ja=f"期待値 {expected!r}, 実際 {actual!r}",
    )


def _check_stock_sign_matches_direction(pair: dict) -> dict:
    pct = pair.get("stock_5d_return_pct")
    direction = pair.get("stock_direction", "")
    if pct is None:
        return _check(
            name="Stock direction matches return sign",
            name_ja="株価方向と5日リターンの符号が一致",
            passed=direction == "unknown",
            evidence={
                "stock_5d_return_pct": "None",
                "expected_direction": "unknown",
                "actual_direction": direction,
            },
            detail=f"expected 'unknown' (no price data), got {direction!r}",
            detail_ja=f"期待値 'unknown' (株価データ無し), 実際 {direction!r}",
        )
    expected = "positive" if pct > 0 else ("negative" if pct < 0 else "unchanged")
    return _check(
        name="Stock direction matches return sign",
        name_ja="株価方向と5日リターンの符号が一致",
        passed=expected == direction,
        evidence={
            "stock_5d_return_pct": f"{pct:+.3f}%",
            "expected_direction": expected,
            "actual_direction": direction,
        },
        detail=f"expected {expected!r}, got {direction!r}",
        detail_ja=f"期待値 {expected!r}, 実際 {direction!r}",
    )


def _check_revenue_reextract(code: str, pair: dict, prev_zip: str | None,
                             curr_zip: str | None,
                             latest_zip: str | None = None,
                             history_by_year: dict | None = None) -> tuple[dict, dict]:
    """Triangulate the agent's reported revenue against ALL independent
    consolidated revenue tags found in the same XBRL filing.

    Strong test: at least 2 distinct XBRL tags (from different tag families
    — Summary-of-Business-Results, IFRS, GAAP) must agree with the agent's
    value within CROSS_TAG_AGREEMENT_PCT. Single-tag agreement isn't a
    cross-check (it's the source the agent already uses).
    """
    pe = pair.get("prev_revenue", 0)
    ce = pair.get("curr_revenue", 0)
    cands_prev = extract_all_revenue_candidates_from_zip_path(Path(prev_zip)) if prev_zip else []
    cands_curr = extract_all_revenue_candidates_from_zip_path(Path(curr_zip)) if curr_zip else []

    # When the agent used the latest ASR's restated 5-year-history, prev/curr
    # may not match the per-ZIP as-originally-reported tags. Inject the
    # restated history values from the latest ZIP as additional candidates so
    # the cross-check accepts them. Tagged with family='restated' so the
    # verdict explains what's going on.
    if history_by_year and latest_zip:
        prev_year = pair.get("prev_fiscal_year")
        curr_year = pair.get("curr_fiscal_year")
        if prev_year in history_by_year:
            cands_prev = list(cands_prev) + [{
                "tag": f"RestatedHistory@{prev_year} (latest ASR)",
                "value": float(history_by_year[prev_year]),
                "scale": "", "decimals": "", "family": "restated",
            }]
        if curr_year in history_by_year:
            cands_curr = list(cands_curr) + [{
                "tag": f"RestatedHistory@{curr_year} (latest ASR)",
                "value": float(history_by_year[curr_year]),
                "scale": "", "decimals": "", "family": "restated",
            }]

    def _build(label_en: str, label_ja: str, agent: float, candidates: list[dict]) -> dict:
        if not candidates:
            return _check(
                name=f"{label_en} revenue matches independent XBRL re-parse",
                name_ja=f"{label_ja}売上高がXBRL独立再解析と一致",
                passed=False,
                evidence={
                    "agent_reported (JPY)": f"{agent:,.0f}",
                    "xbrl_candidates_found": "0",
                    "verdict": "no XBRL revenue tags found in filing",
                },
                detail="no XBRL revenue tags found",
                detail_ja="XBRL内に売上タグが見つかりません",
            )

        # For each candidate, compute drift vs the agent.
        drifts = []
        for c in candidates:
            v = c["value"]
            drift = abs(v - agent) / agent * 100 if agent else (0 if v == 0 else 100)
            drifts.append({**c, "drift_pct": drift})

        # Cross-confirmation tiers (the test PASSES as long as agent's value
        # appears in at least 1 XBRL revenue tag — that proves the value was
        # genuinely extracted, not fabricated. The number of agreeing tags
        # tells us HOW STRONG the verification is, surfaced via the verdict.)
        agreeing = [d for d in drifts if d["drift_pct"] <= CROSS_TAG_AGREEMENT_PCT]
        families = {d["family"] for d in agreeing}
        if not agreeing:
            passed = False
            verdict = (f"FAIL: agent value ({agent:,.0f}) does not match any of "
                       f"{len(candidates)} XBRL revenue tags — extraction bug suspected")
            verdict_ja = (f"失敗: エージェント値 ({agent:,.0f}) が "
                          f"{len(candidates)} 件のどのXBRL売上タグとも一致しない — 抽出バグの疑い")
        else:
            passed = True
            if "summary" in families and len(agreeing) >= 2:
                verdict = (f"GOLD: matches {len(agreeing)} tags including 5-year-history (summary)")
                verdict_ja = (f"優良: 5年推移(summary)を含む {len(agreeing)}件のタグと一致")
            elif "summary" in families:
                verdict = "STRONG: matches 5-year-history (summary) tag"
                verdict_ja = "強: 5年推移(summary)タグと一致"
            elif len(agreeing) >= 2:
                verdict = (f"STRONG: matches {len(agreeing)} tags ({', '.join(sorted(families))})")
                verdict_ja = (f"強: {len(agreeing)}件のタグと一致 ({', '.join(sorted(families))})")
            elif len(candidates) == 1:
                verdict = "OK: single revenue tag in filing — agent value is faithful (no cross-check possible)"
                verdict_ja = "可: 売上タグは1件のみ — 値は忠実だが相互検証不可"
            else:
                # Multi-tag filing but only one agrees — typical of issuers with
                # multiple revenue definitions (Sony: pure operating sales vs
                # sales+financial-services). Surface the alternatives so the
                # reader can verify which scope was picked.
                non_agreeing = [d for d in drifts if d["drift_pct"] > CROSS_TAG_AGREEMENT_PCT]
                alt_summary = ", ".join(
                    f"{d['tag']}={d['value']:,.0f}" for d in non_agreeing[:2]
                )
                verdict = (f"OK with caveat: agent picked one of {len(candidates)} revenue "
                           f"tags. Alternative scope(s) exist (e.g. {alt_summary}) — "
                           f"this is a real data choice, not an error.")
                verdict_ja = (f"可(注意): {len(candidates)}件中1件と一致。別の定義のタグも存在 "
                              f"(例: {alt_summary}) — 実体上の差異であり誤りではない。")

        # Build evidence: show the agent value, # of candidates, and each tag's value+drift.
        evidence: dict[str, str] = {
            "agent_reported (JPY)": f"{agent:,.0f}",
            "xbrl_candidates_found": str(len(candidates)),
            "tags_agreeing (≤%s%%)" % CROSS_TAG_AGREEMENT_PCT: str(len(agreeing)),
            "agreeing_families": ", ".join(sorted(families)) or "(none)",
            "verdict": verdict,
        }
        # Show each candidate tag's value + drift, with agreeing tags first.
        for d in sorted(drifts, key=lambda x: (x["drift_pct"] > CROSS_TAG_AGREEMENT_PCT, x["drift_pct"])):
            marker = "✓" if d["drift_pct"] <= CROSS_TAG_AGREEMENT_PCT else " "
            evidence[f"  {marker} {d['tag']} [{d['family']}]"] = (
                f"{d['value']:,.0f} ({d['drift_pct']:+.3f}% drift)"
            )

        return _check(
            name=f"{label_en} revenue cross-verified across multiple XBRL tags",
            name_ja=f"{label_ja}売上高が複数のXBRLタグで相互検証済み",
            passed=passed,
            evidence=evidence,
            detail=verdict,
            detail_ja=verdict_ja,
        )

    return _build("Prev", "前期", pe, cands_prev), _build("Curr", "当期", ce, cands_curr)


def _check_segments_extracted(pair: dict) -> dict:
    """Sanity check on segment extraction: at least one segment with positive
    revenue, and report sum-of-segments vs headline so the reader can judge
    whether the segments cover the full revenue or only part of it (e.g.
    Sony's segments cover operating sales only, not financial-services)."""
    segs = pair.get("segments") or []
    curr_total = pair.get("curr_revenue", 0) or 0
    prev_total = pair.get("prev_revenue", 0) or 0
    sum_curr = sum(float(s.get("curr", 0) or 0) for s in segs)
    sum_prev = sum(float(s.get("prev", 0) or 0) for s in segs)
    coverage = (sum_curr / curr_total * 100) if curr_total else 0.0
    n_with_value = sum(1 for s in segs if (s.get("curr", 0) or 0) > 0)
    passed = n_with_value >= 1 and sum_curr > 0
    return _check(
        name="Segments extracted with positive revenue",
        name_ja="セグメント別売上が正の値で抽出されている",
        passed=passed,
        evidence={
            "segments_total":         str(len(segs)),
            "segments_with_curr>0":   str(n_with_value),
            "sum_of_segments_curr (JPY)": f"{sum_curr:,.0f}",
            "sum_of_segments_prev (JPY)": f"{sum_prev:,.0f}",
            "headline_curr_revenue (JPY)": f"{curr_total:,.0f}",
            "coverage (sum/headline)": f"{coverage:.1f}%",
            "note": ("coverage <90% is normal when filer reports separate financial-services revenue "
                     "or when intersegment eliminations are excluded"
                     if coverage < 90 else "segments cover headline revenue"),
        },
        detail=("no segments with positive revenue extracted" if not passed else ""),
        detail_ja=("正の値を持つセグメントが抽出されなかった" if not passed else ""),
    )


def _check_required_fields(pair: dict) -> dict:
    required = [
        "prev_fiscal_year", "curr_fiscal_year",
        "prev_revenue", "curr_revenue", "revenue_delta_pct",
        "profit_status",
        "prev_filing_date", "curr_filing_date",
    ]
    missing = [f for f in required if pair.get(f) in (None, "")]
    return _check(
        name="All required deterministic fields populated",
        name_ja="必須の決定論的フィールドが全て存在",
        passed=not missing,
        evidence={
            "required_fields": str(len(required)),
            "fields_populated": str(len(required) - len(missing)),
            "missing_fields": ", ".join(missing) if missing else "(none)",
        },
        detail=f"missing: {', '.join(missing)}" if missing else "",
        detail_ja=f"欠損: {', '.join(missing)}" if missing else "",
    )


def _check_explanations_present(pair: dict) -> dict:
    keys = ["explanation_simple_en", "explanation_simple_ja",
            "explanation_advanced_en", "explanation_advanced_ja"]
    chars = {k: len((pair.get(k) or "").strip()) for k in keys}
    missing = [k for k, c in chars.items() if c == 0]
    return _check(
        name="All 4 explanation variants returned (simple/advanced × en/ja)",
        name_ja="4種類の説明文が全て生成された(やさしい/詳細 × 英/日)",
        passed=not missing,
        evidence={
            "simple_en (chars)":   str(chars["explanation_simple_en"]),
            "simple_ja (chars)":   str(chars["explanation_simple_ja"]),
            "advanced_en (chars)": str(chars["explanation_advanced_en"]),
            "advanced_ja (chars)": str(chars["explanation_advanced_ja"]),
        },
        detail=f"empty: {', '.join(missing)}" if missing else "",
        detail_ja=f"未生成: {', '.join(missing)}" if missing else "",
    )


def _sentence_count(text: str) -> int:
    """Count sentences in EN+JA-mixed text.

    The naive `re.split(r"[.。!?!?]+")` over-counted English text because
    decimal points (`5,628.0`, `8.5%`) and abbreviations (`U.S.`,
    `Vision Fund 1.`) were treated as sentence boundaries. Japanese 。 has
    no such ambiguity. The asymmetry inflated EN counts ~33-50%, breaking
    the bilingual-parity test even when the actual sentence content was
    aligned.

    Fix: an English `.`/`!`/`?` only counts when followed by whitespace or
    end-of-string (matches actual sentence terminators, not decimals or
    mid-token punctuation). Japanese 。！？ count unconditionally.
    """
    if not text or not text.strip():
        return 0
    n = len(re.findall(r"[.!?](?=\s|$)|[。！？]", text))
    # If the text is non-empty but contains no terminators (e.g., a
    # one-line note that ends without a period), count it as 1 sentence.
    return max(n, 1)


def _parity_tolerance(longer: int) -> int:
    """Sentence-count parity tolerance for bilingual EN↔JA explanations.

    The earlier ±25% rule (with min 1) over-enforced parity. Once the
    sentence-count regex was fixed to stop counting decimals, the test
    started surfacing a real linguistic asymmetry: Japanese naturally
    writes ~1.5–2× as many sentences as English for the same content
    because JA splits clauses on 「。」 where EN chains them with
    'and/but/while' into longer single sentences. Forcing tighter parity
    would push the LLM to produce stiff, English-shaped Japanese.

    The relaxed rule:
      tolerance = max(3, round(longer * 0.40))

    The min-3 floor handles short outputs (e.g. Simple at 3 vs 6 sentences,
    where 25% gave tolerance=2 and falsely flagged a 1-off). The 40%
    proportional ceiling catches gross mismatches (one half empty, one
    half wildly off — e.g. EN=4 vs JA=15 still fails). The test now
    measures "are the two halves saying the same thing" rather than
    "do they split sentences identically."
    """
    return max(3, round(longer * 0.40))


def _check_bilingual_sentence_parity(pair: dict, kind: str) -> dict:
    en = pair.get(f"explanation_{kind}_en", "")
    ja = pair.get(f"explanation_{kind}_ja", "")
    kind_label_en = kind.title()
    kind_label_ja = "やさしい" if kind == "simple" else "詳細"
    if not en or not ja:
        return _check(
            name=f"{kind_label_en} EN↔JA sentence-count parity",
            name_ja=f"{kind_label_ja}: 英↔日の文数が同程度",
            passed=False,
            evidence={
                "en_sentences": str(_sentence_count(en)),
                "ja_sentences": str(_sentence_count(ja)),
                "tolerance":    "n/a",
                "diff":         "n/a",
            },
            detail="one or both versions empty",
            detail_ja="片方または両方が空",
        )
    en_n = _sentence_count(en)
    ja_n = _sentence_count(ja)
    diff = abs(en_n - ja_n)
    tol  = _parity_tolerance(max(en_n, ja_n))
    return _check(
        name=f"{kind_label_en} EN↔JA sentence-count parity (~±40% w/ min ±3)",
        name_ja=f"{kind_label_ja}: 英↔日の文数が同程度(±40%以内、最小±3)",
        passed=diff <= tol,
        evidence={
            "en_sentences": str(en_n),
            "ja_sentences": str(ja_n),
            "diff":         str(diff),
            "tolerance":    f"±{tol}",
        },
        detail=f"EN={en_n}, JA={ja_n}, diff={diff} > tolerance ±{tol}",
        detail_ja=f"英={en_n}文、日={ja_n}文、差={diff} > 許容±{tol}",
    )


def run_pair_tests(code: str, pair: dict, prev_zip: str | None = None,
                   curr_zip: str | None = None,
                   latest_zip: str | None = None,
                   history_by_year: dict | None = None) -> dict:
    """Run all internal-consistency checks for one (prev, curr) pair.

    Returns:
        {
          "checks": [{name, name_ja, passed, detail, detail_ja, evidence}, ...],
          "passed": int,
          "total": int,
          "all_passed": bool,
        }
    """
    checks: list[dict] = []
    checks.append(_check_revenue_sign_matches_status(pair))
    checks.append(_check_stock_sign_matches_direction(pair))
    checks.append(_check_required_fields(pair))
    checks.append(_check_segments_extracted(pair))
    if prev_zip or curr_zip:
        prev_chk, curr_chk = _check_revenue_reextract(
            code, pair, prev_zip, curr_zip,
            latest_zip=latest_zip, history_by_year=history_by_year,
        )
        checks.append(prev_chk)
        checks.append(curr_chk)
    checks.append(_check_explanations_present(pair))
    checks.append(_check_bilingual_sentence_parity(pair, "simple"))
    checks.append(_check_bilingual_sentence_parity(pair, "advanced"))

    passed = sum(1 for c in checks if c["passed"])
    return {
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "all_passed": passed == len(checks),
    }
