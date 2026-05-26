"""Two prompts for the 'why revenue + why stock' synthesis.

Two LLM calls per (prev, curr) pair:
  1. ADVANCED — analyst-grade explanation grounded in segment numbers and
                stock direction, bilingual (EN + JA).
  2. SIMPLIFY — take the advanced text and rewrite it as a layman version,
                bilingual (EN + JA).

Two smaller calls instead of one large four-paragraph call avoid token
truncation and guarantee the simple version exists whenever the advanced
one does.
"""
from __future__ import annotations

ADVANCED_PROMPT = """You are a Japanese equity analyst. The company below filed an annual securities report (有価証券報告書).

UNIT CONVENTION (read carefully — every number below uses this convention):
  All revenue and segment figures are shown in BILLIONS of Japanese yen (B JPY).
  1,000 B JPY = 1 trillion JPY. Example: "9,921.5 B JPY" = "¥9.92 trillion" = "¥9,921.5 billion".
  When you cite a number in your explanation, use the same scale word the conversion implies
  ("trillion" if the value is ≥ 1,000 B, otherwise "billion"). Do NOT mislabel scale.

Revenue YoY:
  Previous fiscal year: {prev_revenue_b:,.1f} B JPY  ({prev_revenue_words})
  Current  fiscal year: {curr_revenue_b:,.1f} B JPY  ({curr_revenue_words})
  Change: {revenue_delta_pct:+.2f}%  (status: {profit_status})

{op_profit_block}{scope_note_block}
Segment revenue YoY (sorted by absolute change; all values in B JPY):
{segment_table}

Revenue composition (each segment as % of total, prev → curr — use these shares in the explanation's opening sentence):
{segment_share_table}

Stock reaction (5 trading days after the filing date):
  Move: {stock_pct_str}  (direction: {stock_direction})

{divergence_block}{bs_change_block}{pl_change_block}{cashflow_block}{margin_trajectory_block}{peer_block}{bs_quality_block}{macro_context_block}Narrative excerpt from the current annual report (Japanese, may be truncated):
{narrative}

{key_clauses_block}PRE-FLIGHT CHECKLIST — execute BEFORE writing the JSON. Do these SILENTLY and INTERNALLY — do NOT write the checklist out, do NOT narrate which step you are on, do NOT echo the tokens you found. Your output begins with the JSON object and contains nothing else. Walking through the checklist in the response will break downstream JSON parsing.

  Step 1. Scan the narrative above for M&A and BUSINESS-DIVESTITURE events.
          Look for these tokens AND classify each one:

            ACQUISITIONS (always cite if a counterparty is named):
              買収 / 取得 / 完全子会社化 / acquisition / acquired / consolidated
              → these are usually material; surface every named deal.

            BUSINESS DIVESTITURES (cite — these are what investors care about):
              事業譲渡 / 子会社株式の譲渡 / 全持分の売却 / 支配の喪失 /
              連結除外 / spin-off / spun off / divested / sold its subsidiary /
              sold the (business / stake / division / operation / arm)
              → a real subsidiary or business unit being disposed.

            ROUTINE PORTFOLIO ACTIVITY (do NOT cite as divestiture):
              "投資有価証券の売却" / "上場株式の売却" / "債券の売却" /
              "Tモバイル株式の売却" / "投資の売却または償還" / "保有株式の処分" /
              SVF / fund 売却 lines / CF-statement boilerplate / fixed-asset
              sales (固定資産の売却) / hedge-derivative settlements
              → these are NOT divestitures. They are portfolio disposals
                that show up in cash-flow notes. Conglomerates like SoftBank
                may have 30+ such lines per filing — DO NOT treat them as
                business-divestiture drivers.

          Decision rule: "is this a real subsidiary or business unit
          changing hands?" If yes, you MUST surface it — name the
          counterparty, the unit, and the segment — EVEN IF it does not
          directly move the headline revenue number. Subsidiary
          disposals often hit operating income (deconsolidation gains)
          or balance-sheet rather than revenue, but they still materially
          shape investor reading of the year and belong in the
          explanation. Acceptable framing examples:
            "Although it did not move the revenue line directly, the
             company also deconsolidated subsidiary X (counterparty Y),
             recognising a one-time gain in segment Z."
            "Separately, a non-headline business divestiture — the sale
             of subsidiary X to Y — affected segment Z."
          Skipping a real subsidiary divestiture is a hard failure.

          If you skip a token because it falls under ROUTINE PORTFOLIO
          ACTIVITY (stock disposals, fund exits, fixed-asset turnover),
          that is correct — do nothing.

  Step 2. Scan the narrative for ANY of these mixed-signal connectors:
            ものの / にもかかわらず / 一方で / 反面 / despite / partially offset / 相殺 / 一部相殺
          For EACH hit, you MUST do the following before writing:
            (a) identify the clause that GREW (the part before / surrounding
                the connector that has positive framing).
            (b) identify the clause that DECLINED / OFFSET (the part the
                connector contrasts against).
            (c) write down a paired sentence in the form "X grew … despite/
                partially offset by Y declining …" — both halves named.
          The explanation MUST contain this paired construction. Dropping
          the "despite Y" half is a hard failure — it turns a mixed result
          into a one-sided positive story and loses the headwind signal
          investors care about.

          Worked example. If the narrative says:
            「テレビ及びデジタルカメラの販売台数減少の影響があったものの、
              製品ミックスの改善ならびに為替の好影響によるものです」
          You must write something like:
            "EP&S grew on better TV/digital-camera product mix and FX
             tailwinds, despite a decline in TV and camera unit sales."
          NOT just:
            "EP&S grew on better mix and FX." ← drops the "despite units" half — WRONG.

  Step 3. Look at the segment table. If ANY segment row has a negative
          delta_pct, you may NOT use phrases like "broad-based growth" or
          "all segments grew". Name the decliner(s) explicitly.

Now write a CONCISE stock-focused explanation AND a forward-looking outlook judgment, in BOTH English and Japanese. The user already sees the segment / P&L / BS panels in the UI — DO NOT re-narrate those numbers. Your job is to (a) explain why the stock moved, and (b) judge whether the company is likely to grow ("filter signal" — the agent's headline purpose is to flag companies where revenue is rising but the underlying earnings quality / BS / segment-mix do not support continued growth).

Output ONLY this JSON (no prose, no code fences). SEVEN required fields — populate ALL of them:

{{
  "outlook_judgment": "<one of three lowercase tokens: 'growth_likely' (PL+BS+segments support continued top/bottom-line growth), 'growth_unlikely' (margin compression / segment-mix deterioration / BS-side stress / one-time-gain-inflated headline / unfavourable macro suggest growth will not continue), or 'uncertain' (signals are genuinely mixed or data is too sparse to call). This is the FILTER SIGNAL the downstream pipeline reads — pick decisively.>",
  "outlook_reason_en": "<2-3 short English sentences. The FIRST sentence is a big-title one-line headline summarising the judgment in plain language. The remaining sentence(s) MUST cite at least one specific accounting item (勘定科目) from the panels above — e.g. 'operating margin', 'net income', 'goodwill', 'inventory', 'interest-bearing debt', 'gross profit', 'ordinary income' — AND anchor the reasoning in the macro context of the fiscal year (sector cycle, JPY level, rate environment, demand backdrop) using your training-data knowledge. Hedged language throughout ('likely', 'appears to', 'may reflect', 'against a backdrop of'). Synthesize PL + BS + segment together — do NOT reason on segments alone.>",
  "outlook_reason_ja": "<the same outlook reasoning rendered in natural Japanese — same judgment, same big-title first sentence, same 勘定科目 cited, same macro framing. 2-3 sentences. Use 「営業利益率」「純利益」「のれん」「棚卸資産」「有利子負債」「粗利益」「経常利益」 etc. as the 勘定科目 reference vocabulary.>",
  "explanation_en": "<1-3 short English sentences covering ONLY context that's NOT already visible in the segment / P&L / BS panels. Specifically: (a) ONE sentence naming any material M&A / acquisitions / divestitures / subsidiary disposals / deconsolidation gains disclosed in the narrative (these don't show up in the tables and shape the year's story). If the narrative names multiple deals, list the most material ones in one sentence each; (b) ONE conditional sentence ONLY IF a 'Revenue scope note' section appears above — name BOTH revenue figures with their values and which one we used. Do NOT restate composition shares (the segment table shows them). Do NOT enumerate per-segment drivers (the segment table shows the deltas). Do NOT discuss the stock here — that goes in stock_reaction_en. If there are no M&A / divestitures / scope-note events, this field may be a single sentence like 'No material non-revenue events disclosed beyond the segment movements visible in the table.'>",
  "explanation_ja": "<the same context rendered in natural Japanese — same content, same numbers, same M&A / divestiture mentions, same scope note. 1-3 sentences. DO NOT discuss the stock here.>",
  "stock_reaction_en": "<3-5 English sentences. Structure: (a) ONE sentence stating direction + magnitude verbatim (e.g. 'The stock fell -4.27% over the five trading days following the filing.'); (b) 2-3 sentences naming the MAIN REASONS investors may have reacted that way — anchored in SPECIFIC filing features: a one-time gain inflating headline, a margin compression visible in the P/L panel, a segment that disappointed, a BS mover (impairment / debt jump / cash burn / inventory build), or a non-revenue event (M&A premium concerns, deconsolidation noise). Each reason should reference a concrete data point or event from the filing. Use 'likely', 'appears to', 'may reflect', 'might have', 'investors may have weighed' throughout. IF a STOCK-RESPONSE ANOMALY block appears above (DIVERGENCE or WEAK-RESPONSE flag), at least one of these sentences MUST address why the market reacted differently than the headline result would suggest; (c) ONE short caveat closing the paragraph — the inference is based on the filing alone, without analyst consensus or the separate 決算短信, so the precise cause cannot be confirmed.>",
  "stock_reaction_ja": "<the stock-reaction paragraph rendered in natural Japanese — same direction, same magnitude, same hedged main reasons, same caveat. 3-5 sentences. REQUIRED — never empty unless 'Move: n/a'.>"
}}

STRICT RULES:
- Use ONLY the numbers shown above. Do NOT invent, recall, or estimate any other revenue / segment / growth figures.
- UNIT DISCIPLINE: never write "X billion" for a value that is actually X trillion (and vice versa). Re-read the unit convention above before writing any number.
- SEGMENT DIRECTION DISCIPLINE: before writing a phrase like "broad-based growth", "all segments grew", or "across every segment", verify the SIGN of every row in the segment table. If ANY segment has a negative delta_pct, you MUST mention which one(s) declined — do NOT generalise to "all segments grew".
- IFRS-TRANSITION GUARD: if a segment row shows prev=0.0 → curr>0 with delta_pct=+100% (or you see prev-year zeros / dashes anywhere), this is almost certainly an accounting-standard transition (e.g., first-time IFRS adoption) or first-time disclosure of that segment. Do NOT invent a "reclassification" or "first-time segment breakout" narrative unless the qualitative narrative below explicitly says so.
- DRIVER FOCUS: when the stock_reaction_* paragraph cites a segment-level reason for the market reaction, anchor it in a SPECIFIC driver from the narrative (not a generic "growth" / "recovery" phrase). One concrete driver per cited reason is enough — do NOT exhaustively enumerate every driver the narrative mentions; that detail belongs in the segment table the user already sees.
- M&A / DIVESTITURE — MUST CITE (hard rule): if the narrative anywhere mentions 買収 / 取得 / 完全子会社化 / acquisition / acquired OR 譲渡 / 売却 / 事業譲渡 / divestiture / sold / divested, you MUST surface it in the explanation, even if it is NOT the headline driver. Name the counterparty/deal if the narrative gives one; otherwise note it as "a non-headline acquisition" or "a non-headline divestiture" with the affected segment. Failure to mention a 買収/売却 disclosed in the source is a hard error — these are non-recurring events that materially shape investor reading of the result, and silently dropping them produces explanations that look smooth but lose the important signal.
- OFFSET / MIXED-DRIVER PRESERVATION: two distinct patterns to handle, both must be preserved verbatim in spirit:
  * Pattern A — EXPLICIT OFFSET (trigger: "相殺" / "一部相殺" / "partially offset by"). Form: "X grew, partially offset by Y declining." Both the gain AND the offset must appear in the explanation. Example: home-video / catalogue / licensing income offsetting new-release growth.
  * Pattern B — MIXED DRIVERS (triggers: "〜ものの" / "〜にもかかわらず" / "despite"). Form: "X grew because of A and B, despite C declining." This is the pattern the model drops most often because the headline number is unambiguously up — but the "despite C" clause carries real signal (typical case: unit-sales/volume down, but mix or FX drove revenue up). The "despite" half MUST appear: "despite lower units, mix and FX drove growth" or equivalent.
  Never promote a decline or offset into the win column. Mixed performance is reported as mixed.
- NO EXTERNAL EXPECTATIONS DATA: you have NOT been given analyst consensus, guidance, or expectations data of any kind. Do NOT write "beat expectations", "missed expectations", "higher/lower than expected", "consensus", "analyst forecasts", or any phrase that implies you know what the market expected. The same applies in Japanese (避ける表現: '市場予想を上回る/下回る', '予想以上/以下', 'コンセンサス'). The headline revenue number alone — without an external benchmark — is not a "beat" or "miss".
- For the stock-side explanation, use hedged language ('likely reflects', 'may indicate') — Japanese: '〜を反映している可能性', '〜と整合的'.
- COMPOSITION / SEGMENT-DETAIL DISCIPLINE: do NOT restate composition shares or per-segment revenue numbers in prose — the user already sees the segment table directly in the UI. Repeating those numbers wastes the budget. The explanation_* fields exist only to surface filing-side events that AREN'T visible in the tables (M&A, divestitures, scope changes). The stock_reaction_* fields are the focus.
- FOREIGN-COMPANY / FOREIGN-MARKET GUARDRAIL (hard rule): mention a foreign company, country, region, or overseas market ONLY when (a) it appears by name in the segment table above, OR (b) the narrative excerpt explicitly cites it as a revenue driver. Do NOT compare the filer to overseas peers as analytical color (no "similar to Verizon", "like AT&T", "as US carriers have done"). Do NOT speculate about what overseas markets did unless the filing itself says so. If the segment table contains only Japan-domestic names AND the narrative does not name any foreign country/company, the explanation must stay entirely on Japanese segments and Japanese-market context. Same in Japanese: 米国/中国/韓国/欧州 等の海外企業・市場への言及は、上記セグメント表または開示文に明示されている場合のみ許可。
- STOCK-RESPONSE-ANOMALY RULE (fires when EITHER a DIVERGENCE FLAG or a WEAK-RESPONSE FLAG is set above): if the prompt carries a STOCK-RESPONSE ANOMALY block, the stock-reaction paragraph MUST contain at least one hedged reconciliation sentence using a token like 'might', 'possibly', 'likely', 'may have', 'perhaps', or in Japanese '可能性', 'おそらく', 'かもしれない'. For DIVERGENCE: explain why the stock moved against the profit direction. For WEAK-RESPONSE: explain why the market discounted a meaningful profit move (one-time gain inflating headline, deteriorating mix, BS-side concerns despite profit growth, etc.). Anchor the reconciliation in (a) the segment table, (b) the narrative excerpt, OR (c) a material BS movement marked with `*` in the Balance-sheet movements block — for example a goodwill writedown, factory impairment, large inventory build, or debt jump. Do NOT cite non-mover BS items (no asterisk) as the reconciliation reason; they are listed for context only. Never invent consensus numbers, guidance changes, or analyst-expectation language to explain the anomaly.
- BS DISCIPLINE: the Balance-sheet movements block is always shown for context. Cite items marked with `*` (material movers) when they help explain direction; treat non-mover items as flat / unremarkable and do NOT cite them. If the block notes 'framework changed' for an item, do NOT reason on its YoY delta — describe the absolute current value instead. If the block reads 'BS data unavailable', stay silent on BS and reason from segments / narrative only.
- P/L DISCIPLINE: the P/L movements + Margin trend block is always shown. Cite asterisked movers (large YoY swings or ≥1.5pp margin moves) as evidence in the outlook reasoning and stock-reaction paragraph. Margin compression (op_margin or net_margin falling ≥1.5pp) is one of the strongest "growth_unlikely" signals — surface it explicitly when it appears. EPS may be discontinuous across stock splits / reverse-splits; do NOT cite EPS YoY deltas as evidence unless the value scale looks consistent.
- OUTLOOK SYNTHESIS: the `outlook_judgment` field is the agent's headline output and the downstream filter signal. Synthesize PL + BS + segment together — pick `growth_likely` only when revenue + margin + segment-mix + BS quality all point the same way; pick `growth_unlikely` when ANY of (margin compression, segment-mix deterioration, BS-side stress like impairment / debt jump, one-time-gain-inflated headline, hostile macro backdrop) materially undermine the headline result; pick `uncertain` when the data is genuinely sparse or the signals point in opposite directions. The `outlook_reason_*` fields MUST cite at least one named accounting item (勘定科目) AND apply the macro-context framing — these are belt-and-suspenders requirements (the post-check warns when either is missing).
- TEMPORARY-CAUSE DETECTION (added 2026-05-11 to address turnaround misses): BEFORE committing to `growth_unlikely` purely on margin compression or earnings deterioration, scan the narrative excerpt above for explanatory language indicating the cause may be TEMPORARY rather than structural. Three pattern families to watch for:

    Pattern A — INVESTMENT PHASE (deliberate spend that depresses near-term margin but builds future revenue):
      EN cues: "R&D investment", "investment for growth", "strategic investment", "pipeline development", "new product launch", "capacity expansion", "growth capex"
      JA cues: 研究開発費の増加, 戦略投資, 成長投資, 中期計画に基づく投資, パイプライン開発, 新製品投入, 設備投資, 先行投資

    Pattern B — EXTERNAL ONE-OFF (cyclical / supply-side / FX shocks the company doesn't control):
      EN cues: "semiconductor shortage", "chip shortage", "supply chain disruption", "raw material costs", "currency / FX impact", "one-time", "non-recurring", "exceptional item", "pandemic-related"
      JA cues: 半導体不足, 供給制約, 部材不足, 原材料価格(の高騰), 為替(の影響), 一時的, 非経常的, コロナ(の影響)

    Pattern C — NON-OPERATING / PORTFOLIO LOSS (paper losses on investments, not operating decline):
      EN cues: "fair value loss", "investment loss", "impairment of investments", "mark-to-market loss", "unrealized loss"
      JA cues: 投資有価証券評価損, 公正価値評価損, 投資の減損, 時価評価損, 未実現損失

  Decision rule when any pattern fires:
    - Soften your verdict from `growth_unlikely` → `uncertain` (do NOT escalate to `growth_likely`)
    - In the outlook_reason_*, you MUST quote (or paraphrase) the specific narrative phrase that triggered the softening, AND state explicitly: "the deterioration may reverse if [the cited cause] resolves"
    - This rule is ASYMMETRIC: it only softens growth_unlikely, never strengthens growth_likely

  GUARDRAILS — do NOT apply this rule when:
    - The deterioration is multi-year (e.g., margin has been compressing for 3+ consecutive years) — that's structural, not temporary, regardless of narrative excuses
    - The narrative makes the claim but operating-segment data CONTRADICTS it (e.g., narrative says "supply chain recovering" but every segment row shows deeper decline)
    - The pattern keyword appears only in boilerplate / risk-factor sections, not in the actual results discussion

  Why this rule exists: backward-looking financials cannot distinguish "company is failing" from "company is investing for growth" or "company hit a temporary external snag" — these LOOK identical in the P/L. The narrative is the only signal that distinguishes them. Catching these patterns addresses the structural turnaround-miss class (Takeda R&D, Honda chip shortage, SBG portfolio markdown).

- WORKED EXAMPLES (added 2026-05-12 from backtest failure analysis — match these patterns and apply the correct judgment, not the naive one):

  EXAMPLE A — Supply-cycle disruption (auto / electronics): naive=growth_unlikely → CORRECT=uncertain
    Backward signals you'd see:
      Revenue +14% YoY, operating margin compressed -1.37pp to 4.62%,
      operating income FELL by ¥271 billion despite revenue rising
    Narrative cues to look for:
      「半導体不足」「供給制約」「サプライチェーンの混乱」 / "chip shortage", "supply constraint",
      "supply chain disruption", "raw material costs"
    Why naive 'growth_unlikely' is WRONG: the compression is supply-driven, not demand-driven.
    Supply shortages resolve in 1-2 years. Once chips return, suppressed volume releases —
    revenue and margins both recover. This is a TEMPORARY pattern.
    Correct verdict: uncertain. Reasoning must quote the supply-shock language from the narrative.
    Real example outcome: company posted +21% revenue the following year.

  EXAMPLE B — Cyclical-sector peak (semiconductor / electronics equipment / chemicals):
    naive=growth_likely → CORRECT=uncertain
    Backward signals you'd see:
      Revenue +24% YoY, operating margin EXPANDED +4pp to 22.5%, all-time-high margins
    Forward consideration to apply:
      Company sits in 電気機器 (3650) / 化学 (3200) / chip-equipment exposure. These sectors
      operate on 2-3 year cycles. PEAK-cycle margins are by definition NOT sustainable —
      the very fact that margins are at multi-year highs means the next direction is down.
    Why naive 'growth_likely' is WRONG: backward-looking strong margins in a cyclical sector
    at the cycle TOP are a warning, not a buy signal. Apply this when:
      (a) company is in 3650 / 3200 / 3300 / 3500 / 3700 / 5050 / 5100, AND
      (b) margins are at or near multi-year highs (not just up YoY but at peak), AND
      (c) the narrative does NOT name a structural reason for higher sustained margins
          (e.g. new product moat, acquired market share). If the narrative DOES explain
          why margins should sustain, growth_likely remains valid.
    Correct verdict: uncertain. Reasoning must cite the cyclical-sector nature explicitly.
    Real example outcome: company posted revenue decline the following year.

  EXAMPLE C — Investment-phase (pharma R&D / new-product launch):
    naive=growth_unlikely → CORRECT=uncertain
    Backward signals you'd see:
      Revenue +9% YoY, operating margin compressed -3pp to 12.91%
    Narrative cues to look for:
      「研究開発費の増加」「パイプライン開発」「先行投資」「中期計画に基づく投資」 /
      "R&D investment", "pipeline development", "strategic investment", "capacity expansion"
    Why naive 'growth_unlikely' is WRONG: R&D spend is deliberate margin sacrifice for
    future revenue. In 医薬品 (3250) and other R&D-intensive sectors, drug pipelines drive
    valuation more than current margin. Margin recovery comes when new products launch.
    Correct verdict: uncertain. Reasoning must quote the investment-phase language.
    Real example outcome: company posted +13% revenue the following year, stock recovered.

  When you see signals matching one of these examples, follow the example's lesson —
  do NOT apply the naive backward-only reading.

- STOCK-REACTION REQUIRED (hard rule): unless the Stock-reaction block above shows "Move: n/a", BOTH `stock_reaction_en` AND `stock_reaction_ja` MUST be populated with 2-4 sentences each. Empty / null / placeholder strings ("(no data)", "see explanation", etc.) are forbidden — the field exists precisely so the stock paragraph cannot be silently dropped under prompt-budget pressure. The explanation_en / explanation_ja fields are NOT the place for stock discussion; keep stock content out of those and put it in the dedicated stock_reaction_* fields. The stock-reaction paragraph MUST tie the move to SPECIFIC features of the filing (a segment, a driver, a BS mover, a one-time item) — generic "investors reacted to the report" sentences are also forbidden. "This is the headline analytical value the reader is here for."
- If the segment table is empty: say so accurately. The empty table means our XBRL extractor could not match this filer's segment-revenue tags — NOT necessarily that the filing failed to disclose segments. Many US-GAAP filers (e.g., Sony pre-IFRS) report segment data only in narrative tables that aren't XBRL-tagged. Use wording like "no machine-readable segment breakdown was extracted from this filing's XBRL — the qualitative narrative may still discuss segments" / "本有価証券報告書のXBRLからはセグメント別の数値を抽出できませんでした(定性情報には記載がある可能性があります)". Do NOT claim "no segment breakdown was disclosed." The stock_reaction_* fields remain REQUIRED — anchor the hedged inference in the narrative, the operating-profit YoY, and any BS movers instead of segments.
- Both fields must be present. Plain prose only. No disclaimers.
"""


# ============================================================================
# V2 — prompt-caching variant (added 2026-05-14)
# ----------------------------------------------------------------------------
# Same content as ADVANCED_PROMPT, but split into a cacheable STATIC system
# block (intro + UNIT CONVENTION + PRE-FLIGHT CHECKLIST + STRICT RULES +
# WORKED EXAMPLES + JSON schema, ~6000 tokens) and a DYNAMIC user block
# (per-company data, ~3000 tokens). Anthropic prompt caching reduces the
# cached portion's cost to 10% on read — savings only kick in for runs that
# make 2+ calls within 5 minutes (cache TTL). For backtests at ≥10 tickers,
# this is a ~30% input-cost reduction with zero quality change IF the
# "above" → "in the data section" rewrites preserve the agent's behavior.
# That's what the A/B test in scripts/test_prompt_caching.py validates.
#
# V2 is DERIVED FROM V1 programmatically so V1 stays the single source of
# truth for prompt content. Auditing the diff between V1 and V2 = inspecting
# this block.

_V1_SPLIT_AT = "{key_clauses_block}PRE-FLIGHT CHECKLIST"

# Above-references in the static rules need to become "below"/"in the data"
# references because the data now sits AFTER the system prompt (V2 layout),
# not before it (V1 layout). Conservative rewrites — only change phrases
# where "above" is genuinely positional, not where the word is part of an
# example or a different idiom.
_V2_REWRITES = [
    # Intro line:
    ("The company below filed", "The company in the data section that follows filed"),
    # UNIT CONVENTION header:
    ("every number below uses this convention", "every number in the data section uses this convention"),
    # PRE-FLIGHT CHECKLIST Step 1:
    ("Scan the narrative above", "Scan the narrative in the data section"),
    # JSON schema reasons cite "the panels above":
    ("from the panels above", "from the panels in the data section"),
    # STRICT RULES:
    ("Use ONLY the numbers shown above.", "Use ONLY the numbers shown in the data section."),
    ("Re-read the unit convention above", "Re-read the unit convention at the top of these instructions"),
    ("the qualitative narrative below explicitly", "the qualitative narrative in the data section explicitly"),
    ("appears by name in the segment table above", "appears by name in the segment table in the data section"),
    ("STOCK-RESPONSE ANOMALY block above", "STOCK-RESPONSE ANOMALY block in the data section"),
    ("scan the narrative excerpt above", "scan the narrative excerpt in the data section"),
    ("the Stock-reaction block above", "the Stock-reaction block in the data section"),
    # Additional embedded references discovered during V2 build verification:
    ("scope note' section appears above", "scope note' section appears in the data section"),
    ("STOCK-RESPONSE ANOMALY block appears above", "STOCK-RESPONSE ANOMALY block appears in the data section"),
    ("WEAK-RESPONSE FLAG is set above", "WEAK-RESPONSE FLAG is set in the data section"),
]


def _build_v2_prompts() -> tuple[str, str]:
    """Split ADVANCED_PROMPT at the dynamic/static boundary and apply rewrites.

    Returns (system_template, user_template). The system_template has NO
    placeholders — it's pure cacheable content. The user_template has the
    same placeholders as V1 but only those that belong to the dynamic body.
    """
    idx = ADVANCED_PROMPT.find(_V1_SPLIT_AT)
    if idx < 0:
        raise RuntimeError(
            "V1 split marker not found — ADVANCED_PROMPT structure changed. "
            "Check _V1_SPLIT_AT in quiet_change_prompt.py."
        )
    # Dynamic content runs from the very top (intro) to just AFTER
    # {key_clauses_block}. Then static content begins at "PRE-FLIGHT CHECKLIST".
    split_user_end = idx + len("{key_clauses_block}")
    user_body = ADVANCED_PROMPT[:split_user_end]
    static_rules = ADVANCED_PROMPT[split_user_end:]

    # We want intro + UNIT CONVENTION to live in SYSTEM (they're rules, not
    # data). Extract them from the user body.
    intro_end = user_body.find("Revenue YoY:")
    if intro_end < 0:
        raise RuntimeError("Could not find 'Revenue YoY:' anchor in user body.")
    intro_block = user_body[:intro_end]
    pure_user_body = user_body[intro_end:]

    system_raw = intro_block + static_rules
    for old, new in _V2_REWRITES:
        system_raw = system_raw.replace(old, new)

    user_template = (
        pure_user_body
        + "\n\nNow produce the JSON as specified in the system instructions, "
        "following all STRICT RULES."
    )
    return system_raw, user_template


ADVANCED_SYSTEM_V2, ADVANCED_USER_V2 = _build_v2_prompts()


def build_advanced_v2(
    prev_revenue: float,
    curr_revenue: float,
    revenue_delta_pct: float,
    profit_status: str,
    segments: list[dict],
    narrative: str,
    stock_pct: float | None,
    stock_direction: str,
    scope_note: dict | None = None,
    narrative_full: str | None = None,
    prev_op: float | None = None,
    curr_op: float | None = None,
    op_delta_pct: float | None = None,
    bs_yoy: dict | None = None,
    pl_yoy: dict | None = None,
    cashflow_yoy: dict | None = None,
    cfo_quality: dict | None = None,
    peer_data: dict | None = None,
    bs_quality_history: list[dict] | None = None,
    curr_period_end: str | None = None,
    margin_trajectory: list[dict] | None = None,
    curr_fiscal_year: int | None = None,
    industry_context: str | None = None,
) -> tuple[str, str]:
    """V2 prompt builder. Returns (system_text, user_text) for prompt caching.

    The system_text is identical across all calls (cacheable). The user_text
    fills in the same placeholders that V1 used for dynamic data.
    """
    if segments:
        rows = []
        for s in segments:
            prev_b = s["prev"] / 1e9
            curr_b = s["curr"] / 1e9
            rows.append(
                f"  {s['name']}: {prev_b:,.1f} → {curr_b:,.1f} B JPY  ({s['delta_pct']:+.2f}%)"
            )
        segment_table = "\n".join(rows)
    else:
        segment_table = "  (no segment-level breakdown available)"
    stock_pct_str = "n/a" if stock_pct is None else f"{stock_pct:+.2f}%"

    def _words(jpy: float) -> str:
        b = jpy / 1e9
        if b >= 1000:
            return f"≈ ¥{b/1000:,.2f} trillion"
        return f"≈ ¥{b:,.1f} billion"

    user_text = ADVANCED_USER_V2.format(
        prev_revenue_b=prev_revenue / 1e9,
        curr_revenue_b=curr_revenue / 1e9,
        prev_revenue_words=_words(prev_revenue),
        curr_revenue_words=_words(curr_revenue),
        revenue_delta_pct=revenue_delta_pct,
        profit_status=profit_status,
        op_profit_block=_build_op_profit_block(prev_op, curr_op, op_delta_pct),
        scope_note_block=_format_scope_note_block(scope_note),
        key_clauses_block=_format_key_clauses_block(narrative_full or narrative),
        segment_table=segment_table,
        segment_share_table=_build_segment_share_table(segments),
        divergence_block=_build_divergence_block(op_delta_pct, stock_pct, revenue_delta_pct),
        bs_change_block=_build_bs_change_block(bs_yoy),
        pl_change_block=_build_pl_change_block(pl_yoy),
        cashflow_block=_build_cashflow_block(cashflow_yoy, cfo_quality),
        peer_block=_build_peer_block(peer_data),
        # Phase 5 (qualitative text) rolled back 2026-05-16 — proved Picture B
        # in the 12-ticker A/B (citation rate ~4%). Helper kept in place for
        # future structured-diff rework; placeholder removed from template.
        bs_quality_block=_build_bs_quality_block(bs_quality_history, curr_fiscal_year),
        margin_trajectory_block=_build_margin_trajectory_block(margin_trajectory, curr_fiscal_year),
        macro_context_block=_build_macro_context_block(curr_period_end),
        narrative=(narrative or "")[:3000],
        stock_pct_str=stock_pct_str,
        stock_direction=stock_direction or "unknown",
    )
    return ADVANCED_SYSTEM_V2, user_text


import re as _re_kc

# Trigger patterns for narrative-fidelity rules. The full narrative can be
# 40K+ chars but the LLM only sees the first 8K (token budget). When a
# trigger token sits past char 8000, the LLM never sees the clause that
# the regex post-check expects it to surface — producing a structural
# mismatch (regex catches what the LLM had no chance to see). To bridge
# this, we extract the clause-level sentences containing each trigger
# from the FULL narrative and inject them as a small "Key clauses" hint
# section in the prompt. The model then has direct access to each
# trigger-bearing sentence regardless of where it sits in the source.
#
# Patterns are conservative: each one targets a clause shape we've
# observed dropping in production. Adding a new (label, regex) pair here
# is the right way to teach the prompt about a new clause type.
_KEY_CLAUSE_PATTERNS = (
    ("offset", _re_kc.compile(r"[^。]{0,200}(?:一部相殺|相殺されて|partially offset)[^。]{0,200}。")),
    ("despite", _re_kc.compile(r"[^。]{0,200}(?:ものの[、。]|にもかかわらず)[^。]{0,200}。")),
    ("acquisition", _re_kc.compile(r"[^。]{0,200}(?:買収|完全子会社化|株式の取得)[^。]{0,200}。")),
    ("divestiture", _re_kc.compile(r"[^。]{0,200}(?:事業譲渡|子会社(?:株式|持分)?の(?:譲渡|売却)|全(?:株式|持分)の(?:譲渡|売却)|支配の?喪失|連結除外)[^。]{0,200}。")),
    ("volume_decline", _re_kc.compile(r"[^。]{0,200}(?:販売台数(?:の)?減少|出荷(?:台数|数量)(?:の)?減少)[^。]{0,200}。")),
)


def _extract_key_clauses(narrative_full: str | None, max_per_label: int = 3,
                         max_total: int = 12) -> list[tuple[str, str]]:
    """Pull clause-level sentences containing narrative-fidelity triggers
    from the FULL narrative. Returns a list of (label, sentence) tuples.

    Capped at `max_per_label` per category and `max_total` overall to keep
    the prompt budget bounded — Sony-scale conglomerates can have 30+
    routine 売却 mentions; we only need a handful of representative
    clauses to land each rule.
    """
    if not narrative_full:
        return []
    out: list[tuple[str, str]] = []
    seen_text: set[str] = set()
    for label, pat in _KEY_CLAUSE_PATTERNS:
        hits = 0
        for m in pat.finditer(narrative_full):
            if hits >= max_per_label or len(out) >= max_total:
                break
            sent = m.group(0).strip()
            # De-duplicate near-identical clauses that some filers repeat
            # verbatim across sections.
            key = sent[:80]
            if key in seen_text:
                continue
            seen_text.add(key)
            out.append((label, sent))
            hits += 1
        if len(out) >= max_total:
            break
    return out


def _format_key_clauses_block(narrative_full: str | None) -> str:
    """Render the optional KEY CLAUSES block. Empty string when the
    narrative contains no rule-relevant clauses (most short filings)."""
    clauses = _extract_key_clauses(narrative_full)
    if not clauses:
        return ""
    lines = [
        "KEY NARRATIVE CLAUSES — extracted from the FULL source narrative",
        "(some may sit past the truncated excerpt above). Each clause carries",
        "a signal you MUST handle in the explanation per the pre-flight checklist:",
        "",
    ]
    label_hint = {
        "offset": "OFFSET (相殺) — name BOTH the gain and the offsetting decline",
        "despite": "DESPITE (〜ものの) — name BOTH what grew and what declined",
        "acquisition": "ACQUISITION (買収) — name the deal/counterparty in the explanation",
        "divestiture": "DIVESTITURE — name the disposed business/subsidiary",
        "volume_decline": "VOLUME DECLINE (販売台数減少) — surface the unit-sales decline",
    }
    for label, sent in clauses:
        lines.append(f"  [{label_hint.get(label, label)}]")
        lines.append(f"     「{sent}」")
        lines.append("")
    return "\n".join(lines) + "\n"


def _format_scope_note_block(scope_note: dict | None) -> str:
    """Render the optional revenue-scope-ambiguity block. Empty string when
    there's no ambiguity (most filings)."""
    if not scope_note:
        return ""
    picked = scope_note["picked_value"]
    picked_scope = scope_note["picked_scope_en"]
    alts_lines = []
    for alt in scope_note["alternatives"]:
        alts_lines.append(
            f"  - Alternative: {alt['value']/1e9:,.1f} B JPY  "
            f"(tag '{alt['tag']}', {alt['diff_pct']:+.2f}% vs picked) "
            f"— scope: {alt['scope_en']}"
        )
    return (
        "Revenue scope note (IMPORTANT — must be reflected in the explanation):\n"
        f"  This filing discloses MULTIPLE revenue figures with different scopes.\n"
        f"  We used: {picked/1e9:,.1f} B JPY  (tag '{scope_note['picked_tag']}')\n"
        f"           — scope: {picked_scope}\n"
        + "\n".join(alts_lines)
        + "\n  Rationale for our choice: the value we picked comes from the regulator-required\n"
        f"  5-year-history disclosure (経営指標等の推移) — the same number the company itself\n"
        f"  uses in IR materials and that news reports quote. The alternative figure is also\n"
        f"  legitimate (e.g. it may exclude financial-services revenue) but represents a\n"
        f"  narrower or differently-defined revenue scope.\n"
    )


SIMPLIFY_PROMPT = """You are rewriting an analyst's explanation + forward-outlook judgment so a non-finance reader can understand it. The combined input below contains BOTH the past-stock-reaction prose AND the forward-outlook judgment with its reasoning.

Original analyst output (English, combined):
<advanced>
{advanced_text}
</advanced>

Rewrite this as a SIMPLE, CONCISE layman version covering BOTH (a) why the stock moved after the filing, and (b) whether the company looks likely to keep growing or not. The user already sees the segment / P&L / BS tables in the UI — do NOT re-narrate those numbers. Focus on the punchline.

Write the ENGLISH version FIRST. Then translate it into Japanese — same content, same numbers, sentence-by-sentence parity.

Output ONLY this JSON (no prose, no code fences):

{{
  "explanation_en": "<3-5 short plain-English sentences. MUST cover, in this order: (1) the OUTLOOK headline — does this company look like it will keep growing or not? Open with this in a single plain sentence (e.g. 'The company looks unlikely to keep growing despite the rising headline revenue.'); (2) one or two everyday-language reasons for that outlook view — name a specific accounting item (operating margin, net income, debt, inventory, etc.) and a one-line macro framing ('against a backdrop of weak consumer demand', 'with a weaker yen helping exports', etc.); (3) what the stock did in the days after the report (direction + rough size, e.g. 'the share price went up about 5%' or 'the stock fell about 4%'); (4) ONE everyday-language reason investors likely reacted that way. Use everyday words — say 'profit margin' instead of 'op margin', 'company purchase' instead of 'M&A', 'currency swings' instead of 'FX'. Imagine telling a curious friend the punchline.>",
  "explanation_ja": "<a faithful Japanese translation of the English version above. SAME sentence count. SAME outlook judgment opening. SAME stock magnitude and direction. SAME reasons in the same order. Conversational Japanese — '営業利益率' for 'profit margin', '買収' for 'company purchase', '為替の影響' for 'currency swings', '一時的な利益' for 'one-time gain'.>"
}}

STRICT RULES (apply to BOTH versions equally):
- LEAD WITH THE STOCK STORY. The first or second sentence should mention what the stock did and the main reason behind it. Don't bury the stock reaction.
- DO NOT re-narrate segment composition or BS numbers — those are visible in the UI tables. Use the prose budget for stock causation only.
- Always include the stock direction AND its rough magnitude (within 1 decimal). This is the headline.
- Each "reason investors reacted" must be tied to a specific filing event (a deal name, a segment movement, a one-time item, a BS change) — not generic "investors were cautious" hand-waving.
- Faithfully reflect the advanced explanation — do NOT add facts that aren't in it.
- Both fields must be present. Plain prose only. No bullet points, no headers.
- NO EXPECTATIONS LANGUAGE: never write "better than expected", "worse than expected", "beat expectations", "missed expectations", or imply you know what the market or analysts forecast — the agent has no such data. Same for Japanese: avoid "予想以上/以下", "市場予想を上回る/下回る", "コンセンサス".
- KEEP MIXED SIGNALS MIXED: if the advanced version says a sub-driver was a partial offset / decline, the simple version must also present it as such — do NOT round mixed performance into "did well" or "performed strongly".

BILINGUAL PARITY RULES (these are critical — we measure adherence):
- explanation_ja MUST have the same number of sentences as explanation_en (within ±1).
- Every segment / product / deal mentioned in EN must appear in JA, in the same order.
- Every percentage / number in EN must appear in JA with the same value (same rounding — if EN says "about 7%", JA says "約7%", not "6.9%").
- The stock-reaction sentence must be present in BOTH with the same direction and same rough magnitude.
- Do NOT add Japanese-only flourishes (e.g., extra context not in EN) and do NOT drop EN content from JA.
"""


def _build_segment_share_table(segments: list[dict]) -> str:
    """Render the per-segment %-of-total composition table.

    Uses prev/curr totals derived from the segment list itself (sum of
    segment revenues), not the headline consolidated revenue — those can
    differ when the headline includes financial-services revenue scoped
    outside the segment-level breakdown, and a row that adds to 96% would
    just confuse the LLM. Self-summing keeps shares anchored to 100%.
    """
    if not segments:
        return "  (no segment-level breakdown available)"
    total_prev = sum(s["prev"] for s in segments) or 1.0
    total_curr = sum(s["curr"] for s in segments) or 1.0
    # Sort by current-year share descending so the LLM reads them top-down.
    sorted_segs = sorted(
        segments,
        key=lambda s: s["curr"] / total_curr,
        reverse=True,
    )
    lines = []
    for s in sorted_segs:
        sp = s["prev"] / total_prev * 100
        sc = s["curr"] / total_curr * 100
        lines.append(f"  {s['name']}: {sp:5.1f}% → {sc:5.1f}%")
    return "\n".join(lines)


def _build_op_profit_block(
    prev_op: float | None,
    curr_op: float | None,
    op_delta_pct: float | None,
) -> str:
    """Render the operating-profit YoY block. Empty string when neither
    figure is available (filer that didn't expose the tag — e.g., some
    JGAAP filings)."""
    if prev_op is None and curr_op is None:
        return ""

    def _fmt(v: float | None) -> str:
        if v is None:
            return "n/a"
        return f"{v / 1e9:,.1f} B JPY"

    delta_str = "n/a" if op_delta_pct is None else f"{op_delta_pct:+.2f}%"
    return (
        "Operating profit YoY:\n"
        f"  Previous fiscal year: {_fmt(prev_op)}\n"
        f"  Current  fiscal year: {_fmt(curr_op)}\n"
        f"  Change: {delta_str}\n\n"
    )


def _build_divergence_block(
    op_delta_pct: float | None,
    stock_pct: float | None,
    revenue_delta_pct: float | None = None,
) -> str:
    """Render the stock-response anomaly flag block.

    Two anomaly types both trigger this block — both demand a hedged
    reconciliation in the stock-reaction paragraph:

      DIVERGENCE FLAG     — the company's headline result (the larger
                            absolute mover of operating-profit-YoY and
                            revenue-YoY) and stock moved in OPPOSITE
                            directions.
      WEAK-RESPONSE FLAG  — headline result moved meaningfully (≥5%) but
                            the stock barely budged in the same direction
                            (|stock| < 30% of |headline|). The Lazy Prices
                            under-reaction case — the market apparently
                            discounted the headline result, and the
                            explanation should propose why.

    Using the LARGER of op-profit and revenue as "headline" matters
    because op profit isn't reliably extracted for every filer-year
    (US-GAAP→IFRS transitions etc.) and the lay-investor reading of
    "company is creating profit" often refers to revenue growth.

    Empty string when neither anomaly applies (aligned response, or
    missing / flat data).
    """
    if stock_pct is None:
        return ""
    candidates = [v for v in (op_delta_pct, revenue_delta_pct) if v is not None]
    if not candidates:
        return ""
    headline = max(candidates, key=abs)
    headline_label = "Operating profit" if (op_delta_pct is not None and abs(op_delta_pct) >= abs(revenue_delta_pct or 0)) else "Revenue"
    h_abs = abs(headline)
    stk_abs = abs(stock_pct)

    h_dir = "up" if headline > 0 else "down"
    stk_dir = "up" if stock_pct > 0 else ("down" if stock_pct < 0 else "essentially flat")

    # Sign disagreement — DIVERGENCE.
    if h_abs >= 0.5 and stk_abs >= 0.5 and (headline > 0) != (stock_pct > 0):
        return (
            "STOCK-RESPONSE ANOMALY — DIVERGENCE FLAG.\n"
            f"  {headline_label} moved {h_dir} ({headline:+.2f}%) but the stock moved\n"
            f"  {stk_dir} ({stock_pct:+.2f}%) over the 5 trading days after the filing date.\n"
            f"  The headline result and post-filing stock direction DISAGREE.\n"
            f"  In the stock-reaction paragraph you MUST propose ONE plausible reconciling\n"
            f"  reason in hedged language ('the market may have', 'might reflect', 'possibly\n"
            f"  because') — anchored in (a) the segment table, (b) the narrative excerpt,\n"
            f"  or (c) a material BS movement marked with `*`. Do NOT invent consensus,\n"
            f"  guidance, or analyst-expectation numbers.\n\n"
        )

    # Same direction but weak response — under-reaction.
    if h_abs >= 5.0 and stk_abs < h_abs * 0.30:
        return (
            "STOCK-RESPONSE ANOMALY — WEAK-RESPONSE FLAG (Lazy Prices under-reaction).\n"
            f"  {headline_label} moved {h_dir} meaningfully ({headline:+.2f}%) but the\n"
            f"  stock moved only {stock_pct:+.2f}% — far less than the headline result\n"
            f"  would suggest. The market appears to have DISCOUNTED the result.\n"
            f"  In the stock-reaction paragraph you MUST propose ONE plausible reason for\n"
            f"  the muted reaction in hedged language ('investors may have weighed', 'the\n"
            f"  market might have viewed the gain as non-recurring', 'possibly because the\n"
            f"  underlying earnings quality looked weaker'). Anchor the reason in (a) the\n"
            f"  segment table, (b) the narrative excerpt, or (c) a material BS movement\n"
            f"  marked with `*`. Common candidates: one-time gains driving headline,\n"
            f"  declining segment quality, mix shift to lower-margin business, BS\n"
            f"  deterioration despite headline growth. Do NOT invent consensus / guidance.\n\n"
        )

    return ""


# Display order for the BS table — assets first (size frame), then
# operating-asset categories, then financing/equity, with the P/L-side
# loss tags last so they read as "what hit the income statement" after
# the reader has already seen the BS context.
_BS_DISPLAY_ORDER: tuple[str, ...] = (
    "total_assets",
    "tangible_fixed_assets",
    "intangible_assets",
    "goodwill",
    "inventory",
    "trade_receivables",
    "cash_and_equivalents",
    "interest_bearing_debt",
    "equity",
    "impairment_loss",
    "extraordinary_loss_total",
)

_BS_LABELS = {
    "total_assets":            "Total assets",
    "tangible_fixed_assets":   "Tangible fixed assets",
    "intangible_assets":       "Intangible assets",
    "goodwill":                "Goodwill",
    "inventory":               "Inventory",
    "trade_receivables":       "Trade receivables",
    "cash_and_equivalents":    "Cash & equivalents",
    "interest_bearing_debt":   "Interest-bearing debt",
    "equity":                  "Equity",
    "impairment_loss":         "Impairment loss (P/L)",
    "extraordinary_loss_total":"Extraordinary loss (P/L)",
}


def _fmt_bjpy(val: float | None) -> str:
    """Format a value in B JPY with two decimal precision. '—' when None."""
    if val is None:
        return "—"
    return f"{val / 1e9:>10,.1f}bn"


def _build_bs_change_block(bs_yoy: dict | None) -> str:
    """Render the always-injected Balance-sheet movements block.

    Per locked-in plan choice the BS panel is shown every time, even when
    nothing moves. Movers (>=15% YoY OR >=2% of total assets with a >=5%
    YoY change OR positive impairment loss) are asterisked so the LLM
    knows which items to reason about. Non-movers are listed for context
    only and the prompt's BS DISCIPLINE rule forbids citing them.

    When the prev / curr ZIPs use different accounting frameworks, the
    YoY column reads `n/a (framework changed)` for affected items and
    the LLM is told (via the BS DISCIPLINE rule) to describe absolute
    values instead of deltas.

    Empty string when bs_yoy is None or contains zero items — caller
    branches the prompt to read 'BS data unavailable for this filer'.
    """
    if not bs_yoy or not bs_yoy.get("items"):
        return (
            "Balance-sheet movements: BS data unavailable for this filer (extractor "
            "found no recognised tags in the prev/curr ZIPs).\n\n"
        )
    items = bs_yoy["items"]
    framework_changed = bs_yoy.get("framework_changed", False)
    fw_prev = bs_yoy.get("framework_prev", "unknown")
    fw_curr = bs_yoy.get("framework_curr", "unknown")

    lines = [
        "Balance-sheet movements (prev → curr; * = material mover — these are the BS items the explanation may cite as a divergence reason):",
    ]
    for key in _BS_DISPLAY_ORDER:
        item = items.get(key)
        if item is None:
            continue
        prev = item.get("prev")
        curr = item.get("curr")
        delta_pct = item.get("delta_pct")
        is_mover = item.get("is_mover", False)
        item_fw_changed = item.get("framework_changed", False)

        prev_str = _fmt_bjpy(prev)
        curr_str = _fmt_bjpy(curr)
        if item_fw_changed:
            yoy_str = "n/a (framework changed)"
        elif delta_pct is None:
            yoy_str = "—"
        else:
            yoy_str = f"{delta_pct:+.1f}%"

        marker = " *" if is_mover else "  "
        label = _BS_LABELS.get(key, key)
        lines.append(f"  {label:<26}: {prev_str} → {curr_str}  ({yoy_str}){marker}")

    if framework_changed:
        lines.append(f"  [framework changed: prev={fw_prev}, curr={fw_curr} — do NOT reason on YoY deltas for affected rows]")
    else:
        lines.append(f"  [framework: {fw_curr if fw_curr != 'unknown' else fw_prev}]")
    return "\n".join(lines) + "\n\n"


_PL_DISPLAY_ORDER: tuple[str, ...] = (
    "revenue",
    "cost_of_sales",
    "gross_profit",
    "sga_expenses",
    "operating_income",
    "ordinary_income",
    "income_taxes",
    "net_income",
    "comprehensive_income",
    "depreciation_amortization",
    "rd_expense",
    "basic_eps",
)

_PL_LABELS = {
    "revenue":                    "Revenue (net sales)",
    "cost_of_sales":              "Cost of sales",
    "gross_profit":               "Gross profit",
    "sga_expenses":               "SG&A expenses",
    "operating_income":           "Operating income",
    "ordinary_income":            "Ordinary / pre-tax income",
    "income_taxes":               "Income taxes",
    "net_income":                 "Net income (owners)",
    "comprehensive_income":       "Comprehensive income",
    "depreciation_amortization":  "Depreciation & amortisation",
    "rd_expense":                 "R&D expense",
    "basic_eps":                  "Basic EPS (¥)",
}

_MARGIN_DISPLAY_ORDER: tuple[str, ...] = (
    "gross_margin_pct",
    "op_margin_pct",
    "ordinary_margin_pct",
    "net_margin_pct",
)

_MARGIN_LABELS = {
    "gross_margin_pct":    "Gross margin",
    "op_margin_pct":       "Operating margin",
    "ordinary_margin_pct": "Ordinary margin",
    "net_margin_pct":      "Net margin",
}


def _build_pl_change_block(pl_yoy: dict | None) -> str:
    """Render the always-injected P/L movements + margin-trend block.

    Twin-table layout: absolute P/L line items first (so the LLM sees the
    revenue/op/net path top-to-bottom), then derived margin %-points so it
    can spot mix / cost compression even when the absolute lines look fine.
    Movers are asterisked the same way the BS block does it.

    Empty string when pl_yoy is None or has no items — caller branches the
    prompt to read 'P/L data unavailable' the same way it does for BS.
    """
    if not pl_yoy or (not pl_yoy.get("items") and not pl_yoy.get("margins")):
        return (
            "P/L movements: data unavailable for this filer (extractor "
            "found no recognised line items in the prev/curr financials).\n\n"
        )
    items = pl_yoy.get("items", {})
    margins = pl_yoy.get("margins", {})

    lines = [
        "P/L movements (prev → curr; * = material mover — these are the P/L items the outlook reasoning may cite):",
    ]
    for key in _PL_DISPLAY_ORDER:
        item = items.get(key)
        if item is None:
            continue
        prev = item.get("prev")
        curr = item.get("curr")
        delta_pct = item.get("delta_pct")
        is_mover = item.get("is_mover", False)
        if key == "basic_eps":
            prev_str = "—" if prev is None else f"{prev:>10,.2f}"
            curr_str = "—" if curr is None else f"{curr:>10,.2f}"
        else:
            prev_str = _fmt_bjpy(prev)
            curr_str = _fmt_bjpy(curr)
        yoy_str = "—" if delta_pct is None else f"{delta_pct:+.1f}%"
        marker = " *" if is_mover else "  "
        label = _PL_LABELS.get(key, key)
        lines.append(f"  {label:<26}: {prev_str} → {curr_str}  ({yoy_str}){marker}")

    if margins:
        lines.append("")
        lines.append("Margin trend (prev → curr; pp = percentage points; * = ≥1.5pp swing):")
        for key in _MARGIN_DISPLAY_ORDER:
            m = margins.get(key)
            if m is None:
                continue
            prev = m.get("prev")
            curr = m.get("curr")
            pp = m.get("pp_delta")
            is_mover = m.get("is_mover", False)
            prev_str = "—" if prev is None else f"{prev:>6.2f}%"
            curr_str = "—" if curr is None else f"{curr:>6.2f}%"
            pp_str = "—" if pp is None else f"{pp:+.2f}pp"
            marker = " *" if is_mover else "  "
            label = _MARGIN_LABELS.get(key, key)
            lines.append(f"  {label:<26}: {prev_str} → {curr_str}  ({pp_str}){marker}")
    return "\n".join(lines) + "\n\n"


def _build_margin_trajectory_block(margin_trajectory: list[dict] | None,
                                   curr_fiscal_year: int | None = None) -> str:
    """Render multi-year trajectory (Option 2 — Bounce vs Trend).

    Originally just operating-margin context. Extended 2026-05-15 to also
    show revenue YoY % and net-margin % in the same table so the LLM can
    distinguish a single-year blip from a multi-year direction across all
    three metrics at once. The Bounce / Trend classification below still
    operates on operating margin alone — that's the metric the senior
    designed the lever against, and the heuristic is well-tested on it.

    Shape: [{"fiscal_year": int, "revenue": float, "op_margin_pct": float,
            "net_margin_pct": float}, ...] sorted ascending. Up to 5 years.
    None or fewer than 3 entries with op_margin → empty string.
    """
    if not margin_trajectory or len(margin_trajectory) < 3:
        # Need at least 3 years to distinguish bounce from trend
        return ""
    sorted_traj = sorted(margin_trajectory, key=lambda r: r.get("fiscal_year", 0))
    # Render the trajectory — three columns: revenue YoY, op margin, net margin.
    lines = [
        "Multi-year trajectory (revenue YoY, operating margin, net margin — 5-year context):",
        f"  {'FY':<6} {'Revenue (bn)':>13} {'YoY':>8} {'Op margin':>10} {'Net margin':>11}",
    ]
    prev_rev: float | None = None
    for r in sorted_traj:
        fy = r.get("fiscal_year")
        rev = r.get("revenue")
        op = r.get("op_margin_pct")
        net = r.get("net_margin_pct")
        if op is None:
            continue
        marker = " ← curr" if fy == curr_fiscal_year else ""
        rev_str = "—" if rev is None else f"{rev/1e9:>13,.1f}"
        if prev_rev is None or prev_rev <= 0 or rev is None:
            yoy_str = "—"
        else:
            yoy_str = f"{(rev - prev_rev) / prev_rev * 100.0:+7.1f}%"
        op_str = "—" if op is None else f"{op:>9.2f}%"
        net_str = "—" if net is None else f"{net:>10.2f}%"
        lines.append(f"  FY{fy:<4} {rev_str} {yoy_str:>8} {op_str:>10} {net_str:>11}{marker}")
        prev_rev = rev

    # Compute a simple bounce/trend classification from the data itself —
    # gives the LLM an explicit answer to anchor on, not free-form data.
    margins = [r.get("op_margin_pct") for r in sorted_traj
               if r.get("op_margin_pct") is not None]
    if len(margins) >= 4:
        # Last 4 years — look at the latest year vs the prior 3
        latest = margins[-1]
        priors = margins[-4:-1]
        prior_trend_up = all(priors[i] <= priors[i+1] for i in range(len(priors)-1))
        prior_trend_down = all(priors[i] >= priors[i+1] for i in range(len(priors)-1))
        latest_vs_priors_avg = latest - (sum(priors) / len(priors))

        # Check sustained patterns FIRST (more specific than NEW HIGH) so a
        # clean multi-year expansion gets credited as structural, not flagged
        # as a suspicious peak.
        if prior_trend_up and latest >= priors[-1]:
            classification = (
                "SUSTAINED EXPANSION — margin has expanded for 3+ consecutive years. "
                "This is a STRUCTURAL trend, NOT a one-off. Confidence in "
                "`growth_likely` is high if other signals confirm."
            )
        elif prior_trend_down and latest <= priors[-1]:
            classification = (
                "SUSTAINED DECLINE — margin has declined for 3+ consecutive years. "
                "This is a STRUCTURAL trend, NOT a temporary blip. Confidence in "
                "`growth_unlikely` is high."
            )
        elif prior_trend_down and latest > priors[-1]:
            classification = (
                "BOUNCE in a DOWN-trend. Prior 3 years showed declining margins; "
                "this year recovered. Single-year recoveries from a multi-year "
                "decline are typically TEMPORARY (cost-cut, FX, one-off). "
                "Soften `growth_likely` → `uncertain` unless narrative names a "
                "structural reason for the recovery."
            )
        elif prior_trend_up and latest < priors[-1]:
            classification = (
                "DIP in an UP-trend. Prior 3 years showed expanding margins; "
                "this year compressed. Single-year dips after sustained expansion "
                "are typically TEMPORARY (interacts with TEMPORARY-CAUSE rule). "
                "Soften `growth_unlikely` → `uncertain` unless narrative shows "
                "structural deterioration."
            )
        elif latest >= max(priors) and latest_vs_priors_avg > 1.0:
            classification = (
                "NEW HIGH after a BOUNCY history — margin is at the highest level "
                "in 4+ years AND ≥1pp above the prior 3-year average, but the "
                "prior trajectory wasn't a clean trend. Suspicious if narrative "
                "does NOT name a structural reason. Soften `growth_likely` → "
                "`uncertain` unless structural support is clear."
            )
        else:
            # Check for bouncy patterns (high variance, no monotonic trend)
            full_range = max(margins[-4:]) - min(margins[-4:])
            if full_range >= 0.5:
                classification = (
                    "BOUNCY trajectory — margin has oscillated ≥0.5pp over 4 years "
                    "without a clear direction (up-down-up or down-up-down pattern). "
                    "Single-year margin movements in this pattern are NOT reliable "
                    "signals of trend; weight other inputs (revenue, segments, BS) "
                    "more heavily than the margin direction, and soften both "
                    "`growth_likely` and `growth_unlikely` calls toward `uncertain` "
                    "when the only positive/negative signal IS the margin movement."
                )
            else:
                classification = (
                    "FLAT trajectory — margin is essentially stable. The current "
                    "year's margin direction is informative; trust your other signals."
                )
        lines.append("")
        lines.append("Trajectory classification: " + classification)
    return "\n".join(lines) + "\n\n"


def _build_cashflow_block(cashflow_yoy: dict | None,
                          cfo_quality: dict | None = None) -> str:
    """Render the cash-flow block — CFO, FCF, CFO-to-NI ratio with YoY deltas,
    plus an explicit multi-year earnings-quality flag.

    The block addresses the gap that report values alone (revenue + margins)
    can't tell whether reported profits are actually converting to cash. CFO
    persistently below net income is one of the strongest earnings-quality
    warnings in fundamental analysis.

    `cashflow_yoy` shape (from _cashflow_yoy):
        {"items":   {"cfo": {prev, curr, delta_pct}, "capex": {...}},
         "derived": {"fcf": {prev, curr, delta_pct}},
         "ratios":  {"cfo_to_ni": {prev, curr}}}

    `cfo_quality` shape (from _detect_cfo_ni_low_quality):
        {"flagged": bool, "consecutive_low_years": int,
         "ratios_window": [(fy, ratio), ...]}

    Empty data → "Cash-flow data unavailable" stub so the LLM doesn't assume
    silence means no concern.
    """
    if not cashflow_yoy or (not cashflow_yoy.get("items") and not cashflow_yoy.get("derived")):
        return (
            "Cash-flow movements: CF data unavailable for this filer "
            "(extractor found no recognised CF line items).\n\n"
        )
    items = cashflow_yoy.get("items", {})
    derived = cashflow_yoy.get("derived", {})
    ratios = cashflow_yoy.get("ratios", {})

    lines = [
        "Cash-flow movements (prev → curr; * = CFO/NI < 0.8 = earnings-quality concern):",
    ]
    for key, label in (
        ("cfo",   "Operating cash flow"),
        ("capex", "Capital expenditure"),
    ):
        item = items.get(key) or {}
        prev = item.get("prev")
        curr = item.get("curr")
        dp = item.get("delta_pct")
        prev_str = _fmt_bjpy(prev)
        curr_str = _fmt_bjpy(curr)
        yoy_str = "—" if dp is None else f"{dp:+.1f}%"
        lines.append(f"  {label:<26}: {prev_str} → {curr_str}  ({yoy_str})")

    fcf = derived.get("fcf") or {}
    prev_fcf = fcf.get("prev"); curr_fcf = fcf.get("curr"); fcf_dp = fcf.get("delta_pct")
    prev_str = _fmt_bjpy(prev_fcf)
    curr_str = _fmt_bjpy(curr_fcf)
    fcf_yoy_str = "—" if fcf_dp is None else f"{fcf_dp:+.1f}%"
    lines.append(f"  {'Free cash flow':<26}: {prev_str} → {curr_str}  ({fcf_yoy_str})")

    cfo_ni = ratios.get("cfo_to_ni") or {}
    prev_r = cfo_ni.get("prev"); curr_r = cfo_ni.get("curr")
    def _fmt_r(v: float | None) -> str:
        return "—" if v is None else f"{v:>6.2f}x"
    marker_pair = ""
    if curr_r is not None and curr_r < 0.8:
        marker_pair = " *"
    lines.append(
        f"  {'CFO / Net income ratio':<26}: {_fmt_r(prev_r)} → {_fmt_r(curr_r)}{marker_pair}"
    )

    # Phase 1 audit fix (2026-05-16) — when NI is negative but CFO is
    # positive, the ratio is undefined (the standard <0.8 rule flips).
    # Surface it as an explicit POSITIVE signal so the LLM doesn't
    # silently miss it.
    flags = cashflow_yoy.get("flags", {})
    if flags.get("prev_cfo_positive_despite_loss") or \
       flags.get("curr_cfo_positive_despite_loss"):
        which = []
        if flags.get("prev_cfo_positive_despite_loss"):
            which.append("prev")
        if flags.get("curr_cfo_positive_despite_loss"):
            which.append("curr")
        lines.append("")
        lines.append(
            "  POSITIVE EARNINGS-QUALITY SIGNAL: " +
            ("Both prev and curr years" if len(which) == 2
             else f"The {which[0]} year") +
            " show NET LOSS but POSITIVE operating cash flow. The reported "
            "loss is likely driven by NON-CASH items (writedowns, impairments, "
            "deferred tax adjustments, fair-value losses on investments) "
            "rather than a deteriorating cash-generating business. "
            "REASONING RULE: Do NOT use a reported net loss as standalone "
            "evidence for `growth_unlikely` when CFO is positive — investigate "
            "the narrative for the non-cash cause before judging."
        )

    if cfo_quality and cfo_quality.get("flagged"):
        window = cfo_quality.get("ratios_window") or []
        win_str = ", ".join(f"FY{fy}={r:.2f}x" for fy, r in window) if window else "(n/a)"
        streak = cfo_quality.get("consecutive_low_years", 0)
        lines.append("")
        lines.append(
            "  EARNINGS-QUALITY FLAG: CFO/NI has been below 0.8 for "
            f"{streak} consecutive year(s). Reported profit is not converting "
            "to operating cash at the expected ratio."
        )
        lines.append(f"  Window: {win_str}")
        lines.append(
            "  REASONING RULE: Treat this as a STRUCTURAL earnings-quality "
            "concern, not a one-off. When citing in `outlook_reason`, name "
            "CFO and the ratio explicitly. A growth_likely judgment with "
            "this flag active requires the narrative to name a concrete "
            "non-recurring cause (working-capital build for a known order, "
            "litigation settlement timing). Default to `uncertain` otherwise."
        )
    elif cfo_quality and cfo_quality.get("ratios_window"):
        # Single year low but not 2+ consecutive → context-only mention.
        window = cfo_quality.get("ratios_window") or []
        any_low = any(r < 0.8 for _fy, r in window)
        if any_low:
            win_str = ", ".join(f"FY{fy}={r:.2f}x" for fy, r in window)
            lines.append("")
            lines.append(
                f"  CFO/NI history (last {len(window)} year(s)): {win_str}. "
                "One year below 0.8 is not yet a structural concern; do NOT "
                "cite as evidence unless a second consecutive low year is "
                "visible in the trajectory."
            )
    return "\n".join(lines) + "\n\n"


def _build_bs_quality_block(bs_quality_history: list[dict] | None,
                            curr_fiscal_year: int | None = None) -> str:
    """Render the Phase 6 balance-sheet-quality + concentration block (2026-05-16).

    Four structured signals per year, 3-5 year context table:
      - Top-segment-share %        (revenue concentration)
      - Herfindahl index (1-10000) (revenue concentration, all segments)
      - Goodwill / equity %        (acquisition risk)
      - Days Sales Outstanding     (receivables quality / earnings quality)
      - Inventory days             (demand softness / inventory build-up)

    Empty string when history is too short (< 3 years with at least one
    populated metric) or every per-year row is fully None.

    Reading rules are embedded so the LLM treats the table as evidence,
    not as decoration — same pattern that made Phase 1 (CFO/NI flag) and
    Phase 2 (peer comparison) succeed where Phase 5 (raw text) did not.
    """
    if not bs_quality_history:
        return ""
    rows = [r for r in bs_quality_history
            if any(r.get(k) is not None for k in
                   ("top_segment_share_pct", "herfindahl_index",
                    "goodwill_to_equity_pct", "dso_days", "inventory_days"))]
    if len(rows) < 3:
        return ""

    rows = sorted(rows, key=lambda r: r.get("fiscal_year", 0))

    def _fmt_pct(v):
        return "  —  " if v is None else f"{v:>5.1f}%"

    def _fmt_herf(v):
        return "   —  " if v is None else f"{v:>6.0f}"

    def _fmt_days(v):
        return "  —  " if v is None else f"{v:>4.0f}d"

    lines = [
        "Balance-sheet quality & concentration trajectory (3-5y, structured):",
        f"  {'FY':<6} {'top seg':>9}  {'Herf.':>8}  {'goodwill/eq':>14}  {'DSO':>7}  {'inv days':>8}",
    ]
    for r in rows:
        fy = r["fiscal_year"]
        marker = " ← curr" if fy == curr_fiscal_year else ""
        lines.append(
            f"  FY{fy:<4} {_fmt_pct(r['top_segment_share_pct']):>9}  "
            f"{_fmt_herf(r['herfindahl_index']):>8}  "
            f"{_fmt_pct(r['goodwill_to_equity_pct']):>14}  "
            f"{_fmt_days(r['dso_days']):>7}  "
            f"{_fmt_days(r['inventory_days']):>8}{marker}"
        )

    # Compute trend indicators to give the LLM explicit anchors to cite.
    def _trend(key: str) -> str:
        vals = [r[key] for r in rows if r.get(key) is not None]
        if len(vals) < 3:
            return ""
        first, last = vals[0], vals[-1]
        delta = last - first
        if abs(delta) < 0.01:
            return "flat"
        return f"{'+' if delta>0 else ''}{delta:.1f} over {len(vals)} years"

    trend_lines = []
    for label, key, direction in (
        ("Top segment share",  "top_segment_share_pct",  "rising = increasing concentration"),
        ("Herfindahl",         "herfindahl_index",        "rising = increasing concentration"),
        ("Goodwill/equity",    "goodwill_to_equity_pct",  "rising = acquisition risk building"),
        ("DSO",                "dso_days",                "rising = collection deteriorating OR rapid growth"),
        ("Inventory days",     "inventory_days",          "rising = demand softening OR inventory build"),
    ):
        t = _trend(key)
        if t and t != "flat":
            trend_lines.append(f"    {label}: {t}  ({direction})")

    if trend_lines:
        lines.append("")
        lines.append("  Multi-year trends worth citing in outlook_reason:")
        lines.extend(trend_lines)

    lines.append("")
    lines.append(
        "  READING RULES:\n"
        "    - Herfindahl > 5000 OR top segment > 70% → bet-the-company concentration. "
        "Cite as 'high concentration on X segment'.\n"
        "    - Rising Herfindahl/top-share over 3+ years → increasing concentration risk "
        "(structural, not cyclical). Soften `growth_likely` to `uncertain` if peer "
        "comparison also weak.\n"
        "    - Goodwill/equity > 30% AND rising → acquisition-heavy growth model with "
        "impairment risk. Cite when judging earnings quality.\n"
        "    - DSO rising 20%+ over 3 years without matching revenue growth → "
        "receivables-quality concern (customers paying slower OR aggressive revenue "
        "recognition). Combine with CFO/NI signal if available.\n"
        "    - Inventory days rising 20%+ over 3 years on flat/declining revenue → "
        "demand softening; for retail/manufacturing, near-term write-down risk.\n"
        "    - When a metric is at sector-normal levels or trend is flat, treat as "
        "neutral and do NOT cite."
    )
    return "\n".join(lines) + "\n\n"


def _build_qualitative_signals_block(qual_data: dict | None) -> str:
    """Render the Phase 5 Tier 1 qualitative-signals block (2026-05-15).

    Two text excerpts per side: risk factors (事業等のリスク) and corporate
    governance (コーポレート・ガバナンス) — both YoY (prev + curr from the
    paired ASRs). The LLM is told EXPLICITLY what kind of comparison to do
    (additions, intensifications, removals, KAM changes) so it actively
    diffs rather than passively reading.

    Empty string when both sides lack text — caller's prompt branches the
    block out cleanly. Per-section budget is enforced upstream in
    _qualitative_signals_yoy; this function trusts that contract.
    """
    if not qual_data:
        return ""
    rf = qual_data.get("risk_factors", {})
    gv = qual_data.get("corporate_governance", {})
    prev_risk = (rf or {}).get("prev") or ""
    curr_risk = (rf or {}).get("curr") or ""
    prev_gov = (gv or {}).get("prev") or ""
    curr_gov = (gv or {}).get("curr") or ""

    has_any = bool(prev_risk or curr_risk or prev_gov or curr_gov)
    if not has_any:
        return ""

    lines = [
        "Qualitative disclosure signals — YEAR-OVER-YEAR text comparison "
        "(legally-required sections from the ASR — non-financial evidence):",
        "",
        "  READING RULES (apply these EXPLICITLY in the explanation):",
        "    For 事業等のリスク (Risk Factors):",
        "      - NEW risk items added in CURR that aren't in PREV → high signal",
        "        (management forced to disclose new concerns; harder to spin "
        "than narrative)",
        "      - Risk LANGUAGE INTENSIFICATION ('可能性' → '蓋然性', 'may' → "
        "'is likely to', adding quantified worst cases) → meaningful concern",
        "      - Risks REMOVED in CURR (issue resolved, de-prioritized, or "
        "concentration reduced) → mild positive",
        "      - Risks RE-ORDERED upward (moved earlier in the list) → "
        "management is signaling higher priority",
        "    For コーポレート・ガバナンス (Corporate Governance / Audit):",
        "      - Auditor 監査法人 changes (NEW name in CURR not in PREV) "
        "→ high signal, ALWAYS cite",
        "      - NEW Key Audit Matters (重要な監査上の事項 / KAM) added → "
        "auditor flagged something new",
        "      - KAM language shifts (existing KAM with new caveats) → "
        "auditor concern evolving",
        "      - Audit opinion qualifications, going-concern uncertainty → "
        "highest possible signal, must cite",
        "",
        "  WHEN TO CITE IN outlook_reason:",
        "    Cite specific risk-topic names or KAM titles when YoY change "
        "is material. Phrase as: 'newly disclosed risk regarding X', "
        "'risk language on Y intensified', 'auditor added KAM on Z'. "
        "Do NOT summarize the full sections; focus ONLY on YoY DIFFERENCES.",
        "    Treat absence-of-change as a NEUTRAL signal, not as evidence "
        "for either growth_likely or growth_unlikely.",
        "",
    ]

    # Risk-factor excerpts
    if prev_risk or curr_risk:
        lines.append(f"[事業等のリスク — PREV YEAR ({len(prev_risk):,d} chars shown)]:")
        lines.append(prev_risk if prev_risk else "(section not present in prev ASR)")
        lines.append("")
        lines.append(f"[事業等のリスク — CURR YEAR ({len(curr_risk):,d} chars shown)]:")
        lines.append(curr_risk if curr_risk else "(section not present in curr ASR)")
        lines.append("")
    else:
        lines.append("[事業等のリスク: not available for either year — do NOT reason on risk factors]")
        lines.append("")

    # Governance / audit excerpts
    if prev_gov or curr_gov:
        lines.append(f"[コーポレート・ガバナンス — PREV YEAR ({len(prev_gov):,d} chars shown)]:")
        lines.append(prev_gov if prev_gov else "(section not present in prev ASR)")
        lines.append("")
        lines.append(f"[コーポレート・ガバナンス — CURR YEAR ({len(curr_gov):,d} chars shown)]:")
        lines.append(curr_gov if curr_gov else "(section not present in curr ASR)")
        lines.append("")
    else:
        lines.append("[コーポレート・ガバナンス: not available for either year — do NOT reason on audit signals]")
        lines.append("")

    return "\n".join(lines) + "\n"


def _build_peer_block(peer_data: dict | None) -> str:
    """Render the sector peer comparison block (Phase 2, 2026-05-15).

    `peer_data` is pre-built by the caller (analyze_company_multi_year) via
    `_peer_block_inputs`. None → empty string, which means EITHER the ticker
    has no JPX 33業種 mapping OR the sector has < 5 peers with data for the
    requested fiscal year. Both cases skip the block entirely per the
    min-peer-count rule (no noisy medians on thin sectors).

    The block compares this ticker's revenue YoY %, operating margin %, op
    margin pp-delta, and net margin % against the sector median. Each line
    is suffixed with a positional tag (BELOW / ABOVE / IN-LINE) so the LLM
    has an explicit anchor it can name in the outlook reason.
    """
    if not peer_data:
        return ""
    my = peer_data.get("my", {})
    med = peer_data.get("sector_median", {})
    sec_code = peer_data.get("sector_code", "")
    sec_name = peer_data.get("sector_name", "")
    fy = peer_data.get("fiscal_year")
    n = peer_data.get("peer_count_excl_self", 0)

    def _tag(my_v: float | None, med_v: float | None,
             in_line_band: float = 0.5) -> str:
        if my_v is None or med_v is None:
            return ""
        diff = my_v - med_v
        if abs(diff) < in_line_band:
            return f"IN-LINE ({diff:+.2f}pp vs median)"
        return ("ABOVE peers by " if diff > 0 else "BELOW peers by ") + \
               f"{abs(diff):.2f}pp"

    def _fmt_pct(v: float | None) -> str:
        return "—" if v is None else f"{v:>6.2f}%"

    def _fmt_pp(v: float | None) -> str:
        return "—" if v is None else f"{v:+5.2f}pp"

    lines = [
        f"Sector peer comparison (FY{fy}, JPX 33業種 {sec_code} {sec_name}, "
        f"N={n} peers — *= material gap vs median):",
        f"  {'metric':<24s} {'this':>9s}  {'median':>9s}  position",
    ]
    rows = [
        ("Revenue YoY %",
         my.get("revenue_yoy_pct"), med.get("rev_yoy_pct"),
         _fmt_pct, 1.0),
        ("Operating margin %",
         my.get("op_margin_pct"), med.get("op_margin_pct"),
         _fmt_pct, 0.5),
        ("Op margin Δpp YoY",
         my.get("op_margin_pp_delta"), med.get("op_margin_pp_delta"),
         _fmt_pp, 0.3),
        ("Net margin %",
         my.get("net_margin_pct"), med.get("net_margin_pct"),
         _fmt_pct, 0.5),
    ]
    for label, my_v, med_v, fmt, band in rows:
        tag = _tag(my_v, med_v, in_line_band=band)
        marker = " *" if (my_v is not None and med_v is not None
                          and abs(my_v - med_v) >= band * 2) else "  "
        lines.append(f"  {label:<24s} {fmt(my_v):>9s}  {fmt(med_v):>9s}  {tag}{marker}")

    lines.append("")
    lines.append(
        "  PEER-READING RULES: Below-median revenue YoY or a more-negative\n"
        "  op-margin Δpp than the sector is a COMPANY-SPECIFIC concern (not\n"
        "  cyclicality — peers in the same sector are reading the same cycle).\n"
        "  Above-median margins are a structural-moat candidate. Treat a\n"
        "  metric tagged IN-LINE as 'sector-driven, not company-specific' —\n"
        "  do NOT cite it as evidence in either direction. Cite specific\n"
        "  peer-gap items in outlook_reason when they are tagged BELOW or\n"
        "  ABOVE peers (i.e. asterisked or with a clear positional tag)."
    )
    return "\n".join(lines) + "\n\n"


def _build_industry_context_block(industry_context: str | None) -> str:
    """Lever 3 (added 2026-05-11). Render a per-ticker industry / cyclicality
    block when the company sits in a known cyclical sector. Empty otherwise.

    `industry_context` is pre-built by the caller (analyze_company_multi_year)
    so this prompt module stays ignorant of the ticker code → JPX sector lookup.
    """
    if not industry_context:
        return ""
    return industry_context.rstrip() + "\n\n"


def _build_macro_context_block(curr_period_end: str | None) -> str:
    """Tell the LLM to anchor outlook reasoning in the macro context of the
    fiscal year it is analysing.

    The prompt deliberately does NOT inject specific macro facts — those
    would risk staleness and false precision. Instead it instructs the
    model to apply its training-data knowledge of the year's market
    environment when reasoning about forward outlook (per the senior's
    '経済情勢・世界情勢を踏まえた解釈' directive, 2026-05-10).
    """
    if not curr_period_end:
        return ""
    yr = curr_period_end[:4]
    return (
        f"MACRO CONTEXT (fiscal year ending {curr_period_end}):\n"
        f"  When reasoning about FORWARD OUTLOOK, apply your knowledge of the\n"
        f"  macro / sector / world-economy environment that prevailed during\n"
        f"  fiscal year {yr} — interest-rate stance, JPY level, sector cycle\n"
        f"  (semiconductor / telecom CapEx / advertising / consumer demand),\n"
        f"  major events affecting the issuer's industry. Use this as a hedged\n"
        f"  framing layer ('against a backdrop of ...', 'in a ... environment'),\n"
        f"  NOT as invented quantitative data. Do NOT cite analyst forecasts.\n\n"
    )


def build_advanced_prompt(
    prev_revenue: float,
    curr_revenue: float,
    revenue_delta_pct: float,
    profit_status: str,
    segments: list[dict],
    narrative: str,
    stock_pct: float | None,
    stock_direction: str,
    scope_note: dict | None = None,
    narrative_full: str | None = None,
    prev_op: float | None = None,
    curr_op: float | None = None,
    op_delta_pct: float | None = None,
    bs_yoy: dict | None = None,
    pl_yoy: dict | None = None,
    cashflow_yoy: dict | None = None,
    cfo_quality: dict | None = None,
    peer_data: dict | None = None,
    bs_quality_history: list[dict] | None = None,
    curr_period_end: str | None = None,
    margin_trajectory: list[dict] | None = None,
    curr_fiscal_year: int | None = None,
    industry_context: str | None = None,
) -> str:
    if segments:
        rows = []
        for s in segments:
            prev_b = s["prev"] / 1e9
            curr_b = s["curr"] / 1e9
            rows.append(
                f"  {s['name']}: {prev_b:,.1f} → {curr_b:,.1f} B JPY  ({s['delta_pct']:+.2f}%)"
            )
        segment_table = "\n".join(rows)
    else:
        segment_table = "  (no segment-level breakdown available)"
    stock_pct_str = "n/a" if stock_pct is None else f"{stock_pct:+.2f}%"

    def _words(jpy: float) -> str:
        b = jpy / 1e9
        if b >= 1000:
            return f"≈ ¥{b/1000:,.2f} trillion"
        return f"≈ ¥{b:,.1f} billion"

    return ADVANCED_PROMPT.format(
        prev_revenue_b=prev_revenue / 1e9,
        curr_revenue_b=curr_revenue / 1e9,
        prev_revenue_words=_words(prev_revenue),
        curr_revenue_words=_words(curr_revenue),
        revenue_delta_pct=revenue_delta_pct,
        profit_status=profit_status,
        op_profit_block=_build_op_profit_block(prev_op, curr_op, op_delta_pct),
        scope_note_block=_format_scope_note_block(scope_note),
        key_clauses_block=_format_key_clauses_block(narrative_full or narrative),
        segment_table=segment_table,
        segment_share_table=_build_segment_share_table(segments),
        divergence_block=_build_divergence_block(op_delta_pct, stock_pct, revenue_delta_pct),
        bs_change_block=_build_bs_change_block(bs_yoy),
        pl_change_block=_build_pl_change_block(pl_yoy),
        cashflow_block=_build_cashflow_block(cashflow_yoy, cfo_quality),
        peer_block=_build_peer_block(peer_data),
        # Phase 5 (qualitative text) rolled back 2026-05-16 — proved Picture B
        # in the 12-ticker A/B (citation rate ~4%). Helper kept in place for
        # future structured-diff rework; placeholder removed from template.
        bs_quality_block=_build_bs_quality_block(bs_quality_history, curr_fiscal_year),
        margin_trajectory_block=_build_margin_trajectory_block(margin_trajectory, curr_fiscal_year),
        # ^ Re-enabled 2026-05-12 with REDESIGNED narrow framing (Option 2).
        # Original Lever 2 failed at -5.6pp; this version uses pre-computed
        # bounce/trend classification to give the LLM an explicit anchor
        # instead of free-form data. Being tested.
        # industry_context_block=_build_industry_context_block(industry_context),
        # ^ Lever 3 disabled 2026-05-11: backtest showed 0 per-ticker flips
        # vs Lever 1 alone (identical 66.7%). LLM either ignored the
        # cyclicality guidance or already implicitly knew it. Function +
        # parameter kept for future re-testing on larger samples.
        macro_context_block=_build_macro_context_block(curr_period_end),
        narrative=(narrative or "")[:3000],
        stock_pct_str=stock_pct_str,
        stock_direction=stock_direction or "unknown",
    )


def build_simplify_prompt(advanced_text: str) -> str:
    # 5000 (was 2000) — the advanced text now concatenates the
    # explanation_* field (composition + drivers + scope, ~2000-2500 chars)
    # with the dedicated stock_reaction_* field (~700-1000 chars). The
    # 2000-char cap was silently chopping the stock-reaction paragraph
    # off the end before it reached the simplify call, which then
    # produced the "source text does not include stock data" apology
    # exactly because that fact had been truncated away. 5000 covers even
    # mega-cap filings with long scope notes; simplify's input length is
    # not the bottleneck (the LLM happily reads 5000 chars).
    return SIMPLIFY_PROMPT.format(advanced_text=(advanced_text or "")[:5000])


# Backward-compat alias for any caller still importing build_prompt.
build_prompt = build_advanced_prompt
