# -*- coding: utf-8 -*-
"""PHASE 1 — DETECTION (proposal only; classifies nobody; commits nothing).
Cluster the MD&A-grounded specific reasons already in the committed it_q4_2024/2025 (194 cos, all
quadrants) into a candidate set of SPECIFIC reason-buckets. Apply the promote_buckets threshold
(≥3 cos OR ≥30% of a group w/≥2). One-offs → mechanical-tag fallback. Market-narrative stock reasons
(sector/AI story, not in the report) → enrichment-needed, NOT forced into a fake bucket.
LLM via BEDROCK (same model, billed AWS). Output BUCKET_PROPOSAL.md, then STOP.
"""
from __future__ import annotations
import os, sys, json
from collections import Counter, defaultdict
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT.parent / '.env', override=True)
sys.path.insert(0, str(ROOT / 'build'))
from anthropic import AnthropicBedrock

MIN_ABS, MIN_PROP, MIN_PROP_N = 3, 0.30, 2
YEARS = [('2024', 'it_q4_2024.json', '_pkts_2024_mdna'), ('2025', 'it_q4_2025.json', '_pkts_mdna')]

def quad(pkt):
    rev = (pkt.get('numbers', {}) or {}).get('rev_pct'); sd = (pkt.get('prices', {}) or {}).get('stock_dir', 'flat')
    if sd == 'flat': return 'flat'
    return ('R+S+' if sd == 'up' else 'R+S-') if (rev or 0) > 0 else ('R-S+' if sd == 'up' else 'R-S-')

def load():
    rows = []
    for yr, of, pd in YEARS:
        o = json.loads((ROOT / 'data' / 'quarterly' / of).read_text(encoding='utf-8'))['companies']
        for t, cc in o.items():
            try: p = json.loads((ROOT / 'data' / 'quarterly' / pd / f'{t}.json').read_text(encoding='utf-8'))
            except Exception: continue
            rows.append({'yr': yr, 't': t, 'q': quad(p), 'btag': cc.get('business_reason_tag'),
                         'stag': cc.get('stock_reason_tag'),
                         'why_b': (cc.get('why_business_moved') or '')[:260],
                         'why_s': (cc.get('why_stock_moved') or '')[:160]})
    return rows

SCHEMA = {'type': 'object', 'properties': {'clusters': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'canonical_name': {'type': 'string'}, 'display_name_ja': {'type': 'string'},
    'kind': {'type': 'string', 'enum': ['business', 'stock_groundable', 'market_narrative']},
    'cause_grounded': {'type': 'string', 'enum': ['yes', 'partial', 'no']},
    'over_broad': {'type': 'boolean'}, 'rationale': {'type': 'string'},
    'members': {'type': 'array', 'items': {'type': 'string'}}},
    'required': ['canonical_name', 'display_name_ja', 'kind', 'cause_grounded', 'over_broad', 'rationale', 'members'],
    'additionalProperties': False}}}, 'required': ['clusters'], 'additionalProperties': False}

def cluster(rows):
    lines = [f"{r['yr']}:{r['t']} [{r['q']}] biz={r['btag']} stk={r['stag']} | {r['why_b']} || 株: {r['why_s']}" for r in rows]
    prompt = f"""あなたは日本株アナリスト。以下は194社（2024/2025のIT企業）の、決算短信MD&Aに基づく既出の理由文。
これらを「具体的な共通理由」のバケットにクラスタリングせよ（ゼロから抽出せず、既出の理由をまとめる）。

規則（厳守）:
1. 固定語彙化：各クラスタに canonical_name（英小文字スネーク）+ display_name_ja を付ける。会社ごとに新しい文言を作らない。
2. kind を判定：
   - business = 業績が動いた具体的原因（例：インボイス/電帳法特需、DX/IT投資需要、AI・GPU需要、ゲーム新規タイトル投入、既存ゲーム自然減、M&A連結、放送広告構造減 など）。短信MD&Aに原因として明記されるもの。
   - stock_groundable = 株価側だが報告書で裏が取れる具体理由（例：翌期ガイダンス上方/強気＝guidance_raise、大型還元）。
   - market_narrative = 報告書に書かれない市場解釈（セクター物色・AIストーリー・テーマ性。例：SoftBank/Arm）。→ これは具体バケットに【しない】。enrichment対象。
3. cause_grounded：その理由が報告書本文で『動いた原因』として named か（単なる言及・業界一般論は partial/no）。
4. over_broad：「DX需要で増収」を多数社に貼るようなトートロジーは over_broad=true。
5. members：該当する "year:ticker" を全て列挙（例 "2024:9682"）。1社しか該当しなくても、その理由のクラスタとして出してよい（閾値判定はこちら側で行う）。
6. ★重要★「企業DX・IT投資需要」のような全IT企業に当てはまる総称はバケットにしない（over_broad）。その配下の各社は、本文に明記されたより具体的な理由に割り当てよ：
   例 サイバーセキュリティ投資需要 / クラウド移行・クラウド売上成長 / SAP・ERP更改（2027年保守期限）需要 / 官公庁・公共IT需要 / 製造業向けIT・PLM需要 / 採算改善(margin_expansion) / 費用先行でマージン圧迫(margin_compression) / M&A連結 / SaaS・ARR拡大 など。
   各具体理由の members は【全194社】から数えること（DX21社の中だけで数えない。他バケットにいる該当社も含めて、その理由の真の総数を出す）。

194社：
{chr(10).join(lines)}"""
    cl = AnthropicBedrock(aws_region=os.environ['AWS_REGION'], aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
                          aws_secret_key=os.environ['AWS_SECRET_ACCESS_KEY'], aws_session_token=os.environ.get('AWS_SESSION_TOKEN') or None)
    m = cl.messages.create(model=os.environ['BEDROCK_MODEL_ID'], max_tokens=8000,
                           messages=[{'role': 'user', 'content': prompt}],
                           output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}})
    return json.loads(''.join(b.text for b in m.content if b.type == 'text')), (m.usage.input_tokens, m.usage.output_tokens)

def main():
    rows = load(); qof = {(r['yr'], r['t']): r['q'] for r in rows}
    print(f'clustering {len(rows)} committed MD&A reasons via Bedrock...')
    res, (ti, to) = cluster(rows)
    cache = ROOT / 'data' / 'quarterly' / '_specbucket_clusters.json'
    cache.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
    clusters = res['clusters']
    buckets, oneoff, market = [], [], []
    for c in clusters:
        mem = sorted(set(c['members']))
        tickers = sorted(set(m.split(':')[1] for m in mem if ':' in m)); n = len(tickers)
        quads = Counter(qof.get((m.split(':')[0], m.split(':')[1]), '?') for m in mem if ':' in m)
        per_year = {y: sum(1 for m in mem if m.startswith(y + ':')) for y in ('2024', '2025')}
        c.update({'_n': n, '_tickers': tickers, '_quads': dict(quads), '_py': per_year})
        if c['kind'] == 'market_narrative':
            market.append(c)
        elif n >= MIN_ABS and c['cause_grounded'] in ('yes', 'partial') and not c['over_broad']:
            c['_path'] = f'≥3 (n={n})'; buckets.append(c)
        elif n < MIN_ABS:
            oneoff.append(c)
        else:
            c['_why'] = f"over_broad={c['over_broad']} grounded={c['cause_grounded']}"; oneoff.append(c)
    buckets.sort(key=lambda c: -c['_n'])
    L = ['# PHASE 1 — Specific-reason BUCKET PROPOSAL (detection only; nobody classified, nothing committed)',
         f'Clustered {len(rows)} committed MD&A reasons → {len(clusters)} candidate reasons.',
         f'Threshold: bucket if grounded & not-over-broad & (≥{MIN_ABS} cos OR ≥{MIN_PROP:.0%}/group≥{MIN_PROP_N}); else one-off→mechanical tag. market-narrative→enrichment.',
         f'LLM: Bedrock {os.environ["BEDROCK_MODEL_ID"]} (billed AWS).', '',
         f'## ✅ PROPOSED SPECIFIC BUCKETS ({len(buckets)})',
         '| bucket | name(ja) | n | 2024/2025 | quadrants | grounded | 3 examples |',
         '|---|---|---|---|---|---|---|']
    for c in buckets:
        L.append(f"| `{c['canonical_name']}` | {c['display_name_ja']} | **{c['_n']}** | {c['_py']['2024']}/{c['_py']['2025']} | {c['_quads']} | {c['cause_grounded']} | {', '.join(c['_tickers'][:3])} |")
    L += ['', f'## 🟡 ONE-OFFS (<3 cos → fall back to mechanical tag) — {len(oneoff)}']
    for c in oneoff:
        L.append(f"- {c['display_name_ja']} (n={c['_n']}: {', '.join(c['_tickers'])}) — {c.get('_why','below threshold')}")
    L += ['', f'## 🌐 MARKET-NARRATIVE (not in report → enrichment layer, NOT a specific bucket) — {len(market)}']
    for c in market:
        L.append(f"- {c['display_name_ja']} (n={c['_n']}: {', '.join(c['_tickers'][:5])}) — {c['rationale'][:120]}")
    out = ROOT / 'deliverables' / 'quarterly' / 'BUCKET_PROPOSAL.md'
    out.write_text('\n'.join(L), encoding='utf-8')
    cost = (ti / 1e6) * 3 + (to / 1e6) * 15
    print(f'\nBUCKET_PROPOSAL.md written: {len(buckets)} buckets | {len(oneoff)} one-off | {len(market)} market-narrative')
    print(f'Bedrock tokens {ti}/{to} ≈ ${cost:.3f} (AWS). STOP — awaiting sign-off before Phase 2.')

if __name__ == '__main__':
    main()
