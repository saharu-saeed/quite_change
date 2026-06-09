# Research module

This module contains the **locked lighter prompt** used to produce every entry in `data/company_research_*.json`, plus two small CLI tools that let you reproduce that pipeline on new tickers.

## What this is for

The R+ classification project (the `quite_change/` folder) builds a multi-sector dashboard of Japanese listed companies whose revenue grew in the latest fiscal year. For each company, an AI model (Claude Sonnet 4.6) is given a structured prompt + access to the web, researches the company across primary disclosures and news sources, runs a mandatory verification pass, and produces a JSON entry with:

- `jp_summary` — 4 plain-language Japanese sections explaining the company, the latest results, why business moved, why the stock moved
- 5 card-display fields (`rev_dir`, `op_dir`, `net_dir`, `stock_yoy_estimate`, `biz_classification`)
- `sources` — every URL the model actually used
- `notes` — verification audit trail (what was cross-checked, what couldn't be confirmed)

That JSON drops into `data/` and the build script (`build/build_unified_view.py`) renders it into the HTML dashboard at `deliverables/UNIFIED_VIEW.html`.

## Files

| File | Purpose |
|---|---|
| `prompts.py` | The locked prompt itself — `LIGHTER_PROMPT_EN`, `LIGHTER_PROMPT_JP`, and a `build_prompt()` helper that substitutes `{code}` and `{company_name}`. |
| `run_one_company.py` | CLI tool: research one company, print the resulting JSON. Use this to test the pipeline on 1-3 companies. |
| `run_sector.py` | CLI tool: research a list of companies in parallel, produce a single sector JSON file. Use for small sectors (3-15 companies). For the full ~2,900-company universe, use the Anthropic Batch API instead (50% discount, 24h turnaround). |
| `serve.py` | **Interactive web UI**. Run it, open a browser, type 4-digit codes, watch cards render in the same visual style as the main dashboard. Easiest way to test 1-3 companies without using the command line. Every successful result is auto-saved to `research/staging/{code}.json`. |
| `static/index.html` | The HTML/CSS/JS frontend served by `serve.py`. |
| `staging/` | Auto-save directory for results from the web UI. **Never auto-merged into `data/`.** Inspect, keep, or delete entries here freely. |
| `promote_staging.py` | CLI to list / show / delete staging entries, or promote a good one into a canonical sector file under `data/`. |

## Setup

```bash
# 1. Install dependencies (from quite_change/ directory)
python -m pip install -r research/requirements.txt

# 2. Get an API key from https://console.anthropic.com/ and set it
#    Linux/macOS:
export ANTHROPIC_API_KEY=sk-ant-...
#    Windows PowerShell:
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

> **Why `python -m pip` and not bare `pip`?** With multiple venvs on one machine, bare `pip` can resolve to a different venv than `python` does — Flask ends up in the wrong site-packages and `python -m research.serve` reports "Error importing flask". `python -m pip ...` always uses the currently-active Python's pip, so they stay in sync.
>
> Verify after install:
> ```bash
> python -c "import flask, anthropic; print(flask.__version__, anthropic.__version__)"
> ```

## Quickstart — interactive web UI (recommended for testing)

From the `quite_change/` directory:

```bash
python -m research.serve
# Then open http://localhost:5000 in a browser
```

In the UI:
1. Type 4-digit stock codes in the textarea (one per line, format: `7974 Nintendo` or just `7974`)
2. Click **Research**
3. Watch the status bar count up as each company completes (4-7 min each)
4. Click any card header to expand the full Japanese summary, sources, and verification audit trail
5. Toggle EN / 日本語 in the top-right at any time

Default max is 10 tickers per request (cost guardrail at ~$0.30/each). Change `MAX_TICKERS_PER_REQUEST` in `serve.py` if you need more for a single session.

### Where do the results go?

Every successful result is **auto-saved to `research/staging/{code}.json`**. The canonical sector files under `data/` are **never auto-touched** by the web UI — there is zero risk of overwriting existing dashboard entries with a bad test run.

| Where | What's there | When does it get written? |
|---|---|---|
| `research/staging/{code}.json` | Senior's test results | After each successful research call in the web UI |
| `data/company_research_*.json` | Canonical dashboard data | **Only** when you explicitly run `promote_staging.py --promote` |

### Reviewing and promoting staging entries

```bash
# List everything in staging:
python -m research.promote_staging

# Inspect a single staging entry (prints the full JSON):
python -m research.promote_staging --show 7974

# Promote a good one into a non-IT sector file:
python -m research.promote_staging --promote 1332 --to-sector AgriFishery

# Force-overwrite if the code already exists in the target sector:
python -m research.promote_staging --promote 1332 --to-sector AgriFishery --force

# Delete a bad staging entry:
python -m research.promote_staging --delete 7974

# Clear all staging entries (after promoting the keepers):
python -m research.promote_staging --clear-all --yes
```

Without `--force`, the script **refuses** to overwrite an existing entry in the target sector — so the senior's test runs cannot accidentally clobber data you've already validated.

### Special handling for the IT sector

The IT sector loads its data via `build/build_view.py` (a Python module), not a single JSON file. Promoting a code with `--to-sector IT` writes the entry to `data/it_staged_additions/{code}.json` instead — a parallel directory the build script can pick up later, leaving the existing IT data untouched.

## Quickstart — research one company

From the `quite_change/` directory:

```bash
python -m research.run_one_company 7974 "Nintendo"
```

Output: JSON printed to stdout. Add `--output nintendo.json` to write to a file instead.

Expected wall-clock: 4-7 minutes per company. Expected cost: ~$0.25-0.30 at real-time API rates (~$0.15-0.19 if submitted via the Batch API).

## Quickstart — research a list of companies

```bash
# Create an input file listing the companies to research:
cat > my_tickers.json <<EOF
[
  {"code": "7974", "name": "Nintendo"},
  {"code": "9201", "name": "Japan Airlines"},
  {"code": "1332", "name": "Nissui"}
]
EOF

# Run them in parallel:
python -m research.run_sector my_tickers.json \
    --output data/company_research_test_sector.json \
    --sector-name "Test Sector" \
    --concurrency 3
```

The output file matches the schema of the other `company_research_*.json` files in `data/` — drop it in, point the build script at it, and rebuild the HTML.

## What the prompt does (one-line summary)

The prompt instructs the model to: (1) research the company via web search using suggested Japanese catalyst-finding terms, (2) write a 4-section plain-language Japanese summary with bolded section markers, (3) explain each reason with a "because…" clause, (4) run a verification pass that cross-checks every headline number against a second independent source and logs any discrepancies in `notes`, and (5) output strict JSON with the prose plus 5 card-display tags.

See `prompts.py` for the full text. The Japanese version (`LIGHTER_PROMPT_JP`) is a faithful translation — the prompt's instructions can be sent in either language; the produced summary is always in Japanese.

## Notes on the web search tool

`run_one_company.py` uses Anthropic's hosted server-side `web_search_20250305` tool. If that tool version string has been updated in newer SDK releases, change the `"type"` field in `run_one_company.py`'s `tools=[...]` block to whatever the current version is — check `https://docs.anthropic.com/` for the latest.

## When to use the Batch API instead

These scripts call the Anthropic Messages API in real time. For one-off testing of 1-15 companies, that's fine.

For larger runs (sectors with 50+ companies, or the full ~2,900-company R+ universe), use the **Anthropic Batch API** instead:
- 50% discount on input + output tokens
- ~24-hour turnaround
- Same model, same prompt, same output — only the submission mechanism differs

A Batch API submission script is not included in this folder yet; if you need it, the Anthropic Python SDK exposes `client.messages.batches.create()` — wrap the same prompt + tool config in a JSONL of batch requests and submit.
