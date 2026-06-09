# Prompt template — IT extension batch

When you research a company, follow this exact spec:

## Research
Use 5-7 web searches in Japanese (try terms: 決算短信, 業績予想, 上方修正, 適時開示, 格上げ, 目標株価, TOB). Find:
- Most recent completed fiscal year (revenue, op profit, net profit, dividend, current stock price, 12-month stock change)
- The catalysts behind business and stock movement

## Verification (mandatory before output)
For each headline number, pull a SECOND independent source.
- Match → use it. Disagree → both numbers in notes; main text uses the more authoritative one (IR > Nikkei > Yahoo Finance > aggregator).
- Disambiguate measures (consolidated vs segment, total vs international, etc.).
- Label fiscal-year scope in notes (e.g. "Revenue ¥X — FY2026 actual, source: [URL]").
- Flag unsourced claims as "unverified" in notes.

## Classification (pick ONE bucket)
- **Rev↑ + Stock↑** → tab="R+xS+", bucket from: `acceleration_rerating`, `activist_corporate_action`, `clean_grower`, `inbound_demographic_tailwind`, `profitability_inflection`, `recovery_caught_up`, `sector_specific_tailwind`, `sustained_compounder`
- **Rev↑ + Stock↓** → tab="R+xS-", bucket from: `ai_disrupted`, `all_up_stock_fell`, `durably_overlooked`, `mature_giant`, `orphan_no_coverage`, `profit_compressed`, `saas_derated`, `special_situation`
- **Rev↓** → tab="R-" (skip bucket, the entry will be excluded from the R+ view)

## Summary (4 sections in plain Japanese, **bold:** headers EXACTLY)
- `**会社概要:**` what the company actually does
- `**業績の動き:**` latest numbers explained plainly (with "what does this mean — big/small/normal?")
- `**業績が動いた理由:**` why business moved, with short "なぜなら…" clause linking cause→effect
- `**株価が動いた理由:**` why the stock moved over past year, with "なぜなら…" clauses

No finance jargon. Write like explaining to a smart colleague who's never heard of this company.

## Output (write STRICT JSON to `verification_batches/it_extension/{CODE}.json`)
```json
{
  "code": "{CODE}",
  "name": "{resolved company name in English, JP optional}",
  "tab": "R+xS+ | R+xS- | R-",
  "bucket": "<one key from above, or empty if R->",
  "rev_dir": "up | down | flat",
  "op_dir": "up | down | flat",
  "net_dir": "up | down | flat",
  "stock_yoy_estimate": "<short e.g. '+5% YoY' or '-20% from peak'>",
  "biz_classification": "<short bilingual label e.g. 'SaaS / Cloud subscription'>",
  "jp_summary": "<all 4 bolded sections concatenated, separated by blank lines>",
  "sources": ["<url1>", "<url2>", "..."],
  "notes": "<verification audit trail — what was cross-checked, discrepancies, fiscal-year labels>"
}
```

After writing the file, respond with ONE LINE only: `Wrote <CODE> <tab>/<bucket>`
