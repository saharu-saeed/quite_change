# -*- coding: utf-8 -*-
"""The locked lighter prompt — English and Japanese versions.

This is the canonical prompt for the R+ classification project. It produces:
  - A 4-section bold-headered Japanese summary (jp_summary)
  - 5 card-display tags (rev_dir, op_dir, net_dir, stock_yoy_estimate,
    biz_classification)
  - A list of sources used (sources)
  - A verification audit trail (notes)

The prompt enforces a mandatory verification pass before output: every
headline number is checked against a second independent source, and any
discrepancies are logged in the notes field.

Two template variables to substitute per company:
    {code}          — 4-digit stock code (e.g. "7974")
    {company_name}  — Company name (English or bilingual, e.g. "Nintendo / 任天堂")
"""

LIGHTER_PROMPT_EN: str = """You're helping someone quickly understand a Japanese listed company and why
its business and stock have moved. Write the way you'd explain it to a
smart colleague who has never heard of this company and is reading this
once — plain, clear, easy to get on the first read. No finance jargon.
Whenever you give a number, add a few words on what it means (big or
small? good, bad, or normal?). Keep each section to a short paragraph
or two — tight and readable, not a wall of text.

Research stock code {code} ({company_name}) using web search.

For the NUMBERS, use the most recent report. But for the REASONS, look
wider — the real cause is often a trend or chain of events over the
past several quarters or the past year.

Searching tip — useful Japanese terms when hunting for catalysts:
レーティング / 格上げ / 格下げ / 目標株価 / TOB / M&A /
業績予想修正 / 上方修正 / 下方修正 / 適時開示

Cover these four sections, in plain Japanese. Each section MUST start with its
header wrapped in **bold:** markdown so the renderer displays it as bold —
write the headers EXACTLY like this:

  **会社概要:** [What the company actually does.]
  **業績の動き:** [Latest results and guidance, numbers explained plainly.]
  **業績が動いた理由:** [WHY business moved that way.]
  **株価が動いた理由:** [WHY the stock moved over the past year.]

(Do NOT use 【会社概要】 brackets, ALL-CAPS headers, or plain headers without
**...**  — only `**Header:**` will render as bold in the HTML view.)

EXPLAIN, don't just NAME: after each reason, add a short "because…"
linking cause to effect in plain everyday terms.

Two limits, so "explaining" never becomes "making things up":
- General common-sense logic is fine (how tariffs work, what PBR<1
  means, etc.) — that's general knowledge.
- Do NOT invent company-specific facts or motives unless a source
  says so. If you don't know the mechanism, explain only the general
  logic and stop.

VERIFICATION PASS — MANDATORY BEFORE OUTPUT:
1. Re-read each headline number against the source you cited.
2. Pull a SECOND source for the most consequential numbers (latest FY
   actuals, dividend, current stock price). If they MATCH, use the
   number. If they DISAGREE, write BOTH in notes and use the more
   authoritative source (IR > Nikkei > Yahoo Finance > aggregator).
3. Disambiguate measures with multiple valid definitions (e.g.
   passenger count: total / domestic / international). State which.
4. Flag any specific claim (named broker action, named M&A, dated
   event) you can't point to a source for. Either remove or move to
   notes as "unverified."
5. Label each headline number in notes with fiscal-year scope:
   "Revenue ¥X — FY2026 actual, source: [URL]" etc.

Two rules: Use the web for everything. Only give a reason if a source
actually says it. If you can't find why, say so plainly — never invent.

ALSO output these compact tags (used for the card display in the UI):
- rev_dir:             "up" | "down" | "flat"   — revenue direction YoY
- op_dir:              "up" | "down" | "flat"   — operating profit direction YoY
- net_dir:             "up" | "down" | "flat"   — net profit direction YoY
- stock_yoy_estimate:  short string like "-20% from peak" or "+5% YoY"
                       — direction & rough magnitude of the past-12-month stock move
- biz_classification:  short bilingual label like
                       "フルサービス大手 / Full-service major"
                       — what kind of business this is, in one phrase

Output strict JSON:
{{ jp_summary, rev_dir, op_dir, net_dir, stock_yoy_estimate,
  biz_classification, sources, notes }}
(Japanese summary only — no English summary is produced.)"""


LIGHTER_PROMPT_JP: str = """あなたは、日本の上場企業について、その事業と株価がなぜ動いたかを誰かに
素早く理解してもらう手助けをしています。この企業を初めて聞く頭の良い同
僚に、一度読むだけで分かるように説明する書き方をしてください — 平易で明
瞭、初見で頭に入る文章にすること。金融専門用語は使わない。数字を出すた
びに、それが何を意味するかを短く添えること(大きいか小さいか? 良いか悪
いか普通か?)。各セクションは短い段落1〜2つ — 読みやすくコンパクトに、
文章の壁にならないように。

証券コード {code}({company_name})をWeb検索でリサーチしてください。

数値は最新の決算レポートを使用すること。ただし「理由」についてはもっと
広く見ること — 真の原因は過去数四半期や過去1年にわたるトレンドや出来事
の連鎖にあることが多いから。

検索ヒント — 触媒(カタリスト)を探す際に有用な日本語キーワード:
レーティング / 格上げ / 格下げ / 目標株価 / TOB / M&A /
業績予想修正 / 上方修正 / 下方修正 / 適時開示

以下の4つのセクションを、平易な日本語でカバーしてください。各セクション
は必ず **bold:** マークダウンでヘッダーをラップすること(レンダラーが太字
として表示するため) — ヘッダーは正確に下記の形式で記述すること:

  **会社概要:** [この会社が実際に何をしているか]
  **業績の動き:** [直近の決算と現在のガイダンス、数字を平易に説明]
  **業績が動いた理由:** [事業がなぜそう動いたか]
  **株価が動いた理由:** [株価が過去1年でなぜ動いたか]

(【会社概要】の角括弧、ALL-CAPS、**...**なしの平文ヘッダーは使用しない
こと — `**Header:**` 形式のみがHTMLビューで太字レンダリングされます。)

「説明する」のであって「名前を挙げる」だけではない: 各理由の後に、原因
と結果を結ぶ「なぜなら…」を1〜2文で短く付け加えること。

「説明」が「捏造」にならないための2つの制限:
- 一般的・常識的なロジック(関税の仕組み、PBR<1の意味など)はOK —
  これは一般知識であり、企業固有の主張ではない。
- ソースが明示していない限り、企業固有の事実や動機を捏造しないこと。
  メカニズムが分からない場合は、一般ロジックのみ説明して止めること。

検証パス(MANDATORY、出力前に必ず実施):
1. 述べる各主要数値を、引用ソースに対して再読確認すること。
2. 最も重要な数値(直近FY実績、配当、現在の株価)について、2つ目の
   独立ソースを引いて確認すること。一致すればその数値を使用; 不一致
   なら両方の数値をnotesに記入し、より権威のあるソース
   (IR > 日経 > Yahoo Finance > アグリゲーター)を本文で使用すること。
3. 複数の有効な定義がある指標を明確化(例: 旅客数 — 全体/国内/国際の
   どれか)。どれを指しているか明示すること。
4. 特定の主張(名指しの証券会社アクション、名指しのM&A、日付付き
   イベント)で、ソースを指せないものはnotesに「unverified」として
   移動するか削除すること。
5. 各主要数値をnotesで会計年度スコープと共にラベル付け:
   「売上 ¥X — FY2026実績、ソース: [URL]」など。

2つの重要なルール: 何でもWebで調べること。ソースが実際に言っている
理由のみを述べること。もしなぜか分からない場合は、平易にそう言うこと
— 決して捏造しないこと。

以下のコンパクトタグも出力すること(UIのカード表示で使用):
- rev_dir:             "up" | "down" | "flat"   — 売上の前年同期比方向
- op_dir:              "up" | "down" | "flat"   — 営業利益の前年同期比方向
- net_dir:             "up" | "down" | "flat"   — 純利益の前年同期比方向
- stock_yoy_estimate:  「-20% from peak」「+5% YoY」のような短い文字列
                       — 過去12か月の株価動向の方向と概略の大きさ
- biz_classification:  「フルサービス大手 / Full-service major」のような
                       短い日英ラベル — どのような事業かを一言で

厳密JSONで出力:
{{ jp_summary, rev_dir, op_dir, net_dir, stock_yoy_estimate,
  biz_classification, sources, notes }}
(日本語要約のみ — 英語要約は生成しません)"""


def build_prompt(code: str, company_name: str, lang: str = "en") -> str:
    """Substitute the {code} and {company_name} placeholders in the locked prompt.

    Args:
        code: 4-digit stock code, e.g. "7974"
        company_name: Display name, e.g. "Nintendo" or "Nintendo / 任天堂"
        lang: "en" (default) or "jp" — chooses which prompt template

    Returns:
        The fully substituted prompt string, ready to send to the model.
    """
    if lang not in ("en", "jp"):
        raise ValueError(f"lang must be 'en' or 'jp', got {lang!r}")
    template = LIGHTER_PROMPT_EN if lang == "en" else LIGHTER_PROMPT_JP
    return template.replace("{code}", code).replace("{company_name}", company_name)
