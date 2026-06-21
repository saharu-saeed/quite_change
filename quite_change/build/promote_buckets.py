# -*- coding: utf-8 -*-
"""Automated reason-bucket promotion (PROPOSAL ONLY — does NOT modify the vocabulary).

Pipeline:
  1. DETECT  — load emergent-scan candidates (both years).
  2. CLUSTER — one LLM call: merge same-reason candidates across years (reuse one name),
               merge near-duplicates, map to the EXISTING vocabulary where semantically
               identical, and judge cause-grounded (cause-not-mention) + over-broad.
  3. THRESHOLD (deterministic code) per canonical reason:
        promote if cause-grounded AND distinct AND
            (unique companies >= 3)  OR  (>=30% of its sector with >=2 companies)
        exactly 2 -> EMERGING (watch)  ;  1 / below -> stays in "other".
  4. REPORT — proposed new buckets (name + count + sector size/share + filing evidence),
              merges (which->which + why), emerging (2-co), what stayed in other,
              and a distribution check (count per bucket both years + over-broad / near-dup flags).

Writes deliverables/quarterly/BUCKET_PROMOTION_PROPOSAL.md. Commits nothing.
"""
from __future__ import annotations
import json, glob, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'build'))
from run_it_batch import _env, MODEL
import anthropic

MIN_ABS, MIN_PROP, MIN_PROP_N, EMERGING_N = 3, 0.30, 2, 2

VOCAB_BIZ = ['one-off_cost_rolloff','one_off_gain','one_off_loss','one_off_gain_rolloff',
             'margin_expansion','margin_compression','volume_demand_growth','price_arpu_growth',
             'm&a_consolidation','fx_tailwind','fx_headwind','cyclical_recovery','other']
VOCAB_STOCK = ['capital_return_surprise','rerating_on_growth','consensus_miss','guidance_disappointment',
               'sector_narrative_cooling','valuation_too_high','muted_no_reaction','other']
EXISTING_THEMES = ['prior_year_cost_rolloff_discounted','cloud_transition_revenue_deferral',
                   'policy_shareholding_sale','post_covid_live_event_recovery',
                   'reputational_crisis_cost','dx_demand_wins']

def load():
    cands, pkt = [], {}
    for yr, stem in [('2024', 'it_q4_2024'), ('2025', 'it_q4_2025')]:
        f = ROOT / 'data' / 'quarterly' / f'{stem}_emergent_candidates.json'
        if f.exists():
            for c in json.loads(f.read_text(encoding='utf-8')).get('candidates', []):
                c['year'] = yr; cands.append(c)
    for d in ['_pkts', '_pkts_2024']:
        yr = '2025' if d == '_pkts' else '2024'
        for fp in glob.glob(str(ROOT / 'data' / 'quarterly' / d / '*.json')):
            p = json.loads(Path(fp).read_text(encoding='utf-8'))
            pkt[(yr, p['ticker'])] = {'sector': p.get('sector') or '情報・通信業',
                                      'ground': (p.get('tanshin_text') or p.get('why_text') or '')}
    return cands, pkt

SCHEMA = {'type': 'object', 'properties': {'clusters': {'type': 'array', 'items': {'type': 'object',
    'properties': {
        'canonical_name': {'type': 'string'}, 'display_name_ja': {'type': 'string'},
        'decision': {'type': 'string', 'enum': ['NEW', 'MERGE_EXISTING']},
        'merge_target': {'type': 'string'},
        'cause_grounded': {'type': 'string', 'enum': ['yes', 'partial', 'no']},
        'over_broad': {'type': 'boolean'}, 'rationale': {'type': 'string'},
        'members': {'type': 'array', 'items': {'type': 'string'}}},
    'required': ['canonical_name','display_name_ja','decision','merge_target','cause_grounded','over_broad','rationale','members'],
    'additionalProperties': False}}}, 'required': ['clusters'], 'additionalProperties': False}

def cluster_llm(cands):
    lines = []
    for c in cands:
        lines.append(f"[{c['year']}] {c.get('theme_name')} | groundable={c.get('announce_date_groundable')} | "
                     f"tickers={','.join(c.get('tickers', []))} | {c.get('description','')[:160]}")
    prompt = f"""既存の理由バケット語彙（これと意味が同じ候補は新規作成せず MERGE_EXISTING）：
business: {', '.join(VOCAB_BIZ)}
stock: {', '.join(VOCAB_STOCK)}
themes(決定済): {', '.join(EXISTING_THEMES)}

以下は2024・2025のemergent-scan候補（新しい共通理由）。これらを「正規の理由」にクラスタリングせよ：
規則：
 ・同じ理由が複数年に出ていれば1つに統合し、同一のcanonical_nameを付ける（年度間の一貫性）。
 ・near-duplicate同士も統合。
 ・既存語彙と意味的に同じものは decision=MERGE_EXISTING, merge_target=既存タグ名。新規性があれば decision=NEW。
 ・cause_grounded：その理由が決算資料で『株価・業績が動いた原因』として挙げられているか（単なる言及ではない）。
   全IT企業に当てはまるトートロジー（例：「DX需要で増収」を20社に付与）は over_broad=true かつ cause_grounded=partial/no とせよ。
 ・members：年度プレフィックス付きの全ティッカー和集合（例 "2024:9682","2025:3923"）。

候補：
{chr(10).join(lines)}"""
    c = anthropic.Anthropic(api_key=_env('ANTHROPIC_API_KEY'))
    m = c.messages.create(model=MODEL, max_tokens=8000, messages=[{'role': 'user', 'content': prompt}],
                          output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}})
    return json.loads(''.join(b.text for b in m.content if b.type == 'text')), (m.usage.input_tokens, m.usage.output_tokens)

def jp_terms(name_ja):
    """Meaningful Japanese fragments from the display name to search filings for."""
    raw = re.split(r'[・（）\(\)、。「」]|による|に伴う|での|の|と', name_ja)
    return [w.strip() for w in raw if len(w.strip()) >= 3]

def evidence(members, pkt, name_ja):
    for term in jp_terms(name_ja):
        for mm in members:
            try: yr, t = mm.split(':')
            except ValueError: continue
            g = pkt.get((yr, t), {}).get('ground', '')
            i = g.find(term)
            if i >= 0:
                return f"[{t}/{yr}, term「{term}」] …{g[max(0,i-30):i+90].strip()}…"
    return "(no keyword hit — LLM-judged; verify manually)"

def main():
    cands, pkt = load()
    cache = ROOT / 'data' / 'quarterly' / '_bucket_clusters_cache.json'
    if cache.exists() and '--refresh' not in sys.argv:
        res = json.loads(cache.read_text(encoding='utf-8')); ti = to = 0
        print('(using cached LLM clusters; pass --refresh to re-call)')
    else:
        res, (ti, to) = cluster_llm(cands)
        cache.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
    clusters = res.get('clusters', [])
    promote, merge, emerging, other = [], [], [], []
    for cl in clusters:
        members = sorted(set(cl.get('members', [])))
        utickers = sorted(set(m.split(':')[1] for m in members if ':' in m))
        n = len(utickers)
        per_year = {y: sum(1 for m in members if m.startswith(y + ':')) for y in ('2024', '2025')}
        secs = Counter(pkt.get((m.split(':')[0], m.split(':')[1]), {}).get('sector', '?') for m in members if ':' in m)
        dom_sec, dom_n = (secs.most_common(1)[0] if secs else ('?', 0))
        sec_total = sum(1 for k in pkt if k[1] in utickers)  # rough sector denom unavailable single-sector
        # sector share within dominant sector across the whole dataset
        all_in_sec = sum(1 for k, v in pkt.items() if v['sector'] == dom_sec)
        share = (dom_n / all_in_sec) if all_in_sec else 0
        cl.update({'_n': n, '_tickers': utickers, '_per_year': per_year, '_dom_sec': dom_sec,
                   '_share': share, '_all_in_sec': all_in_sec,
                   '_evidence': evidence(members, pkt, cl['display_name_ja'])})
        grounded = cl['cause_grounded'] in ('yes', 'partial') and not cl['over_broad']
        if cl['decision'] == 'MERGE_EXISTING':
            merge.append(cl)
        elif not grounded:
            cl['_why'] = f"cause_grounded={cl['cause_grounded']} over_broad={cl['over_broad']} -> stays in other"
            other.append(cl)
        elif n >= MIN_ABS:
            cl['_path'] = f'abs (n={n}>=3)'; promote.append(cl)
        elif share >= MIN_PROP and n >= MIN_PROP_N:
            cl['_path'] = f'proportional ({dom_n}/{all_in_sec}={share:.0%})'; promote.append(cl)
        elif n == EMERGING_N:
            emerging.append(cl)
        else:
            cl['_why'] = f'n={n} below threshold'; other.append(cl)

    L = ['# Reason-bucket promotion — PROPOSAL (review before committing; vocabulary NOT modified)',
         f'Candidates in: {len(cands)} (2024+2025) → clustered into {len(clusters)} canonical reasons.',
         f'Thresholds: promote if cause-grounded & distinct & (≥{MIN_ABS} cos OR ≥{MIN_PROP:.0%} of sector w/≥{MIN_PROP_N}); 2=emerging; else→other.',
         '', '## ✅ PROPOSED NEW BUCKETS']
    for c in promote:
        L += [f"\n### {c['canonical_name']}  —  {c['display_name_ja']}",
              f"- members: **{c['_n']}** ({c['_per_year']['2024']} in 2024, {c['_per_year']['2025']} in 2025) — {', '.join(c['_tickers'])}",
              f"- sector: {c['_dom_sec']} | share {c['_dom_sec']}: {c['_share']:.0%} of {c['_all_in_sec']} | promotion path: {c.get('_path')}",
              f"- cause_grounded: {c['cause_grounded']} | over_broad: {c['over_broad']}",
              f"- evidence: {c['_evidence']}",
              f"- rationale: {c['rationale'][:200]}"]
    L += ['', '## 🔁 MERGED INTO EXISTING (no new bucket — dedupe/cross-year)']
    for c in merge:
        L.append(f"- {c['display_name_ja']} ({c['_n']} cos) → **{c['merge_target']}** : {c['rationale'][:150]}")
    L += ['', '## 🟡 EMERGING (2-company watch — not a full bucket yet)']
    for c in emerging:
        L.append(f"- {c['canonical_name']} ({c['display_name_ja']}) — {', '.join(c['_tickers'])} : {c['rationale'][:120]}")
    L += ['', '## ⏳ STAYED IN "other" (below threshold or tautology — wait for recurrence)']
    for c in other:
        L.append(f"- {c['display_name_ja']} (n={c['_n']}) : {c.get('_why','')}")
    # distribution check across existing tags both years
    L += ['', '## 📊 DISTRIBUTION CHECK (current buckets, both years)']
    for yr, stem in [('2024', 'it_q4_2024'), ('2025', 'it_q4_2025')]:
        d = json.loads((ROOT / 'data' / 'quarterly' / f'{stem}.json').read_text(encoding='utf-8'))['companies']
        bz = Counter(c.get('business_reason_tag') for c in d.values())
        st = Counter(c.get('stock_reason_tag') for c in d.values())
        big = [f'{k}={v}' for k, v in (bz + st).most_common() if v >= 0.30 * len(d)]
        L.append(f"- {yr} ({len(d)} cos): biz={dict(bz.most_common())}")
        L.append(f"          stock={dict(st.most_common())}")
        if big: L.append(f"  ⚠️ possibly over-broad (≥30% of set): {big}")
    out = ROOT / 'deliverables' / 'quarterly' / 'BUCKET_PROMOTION_PROPOSAL.md'
    out.write_text('\n'.join(L), encoding='utf-8')
    cost = (ti / 1e6) * 3 + (to / 1e6) * 15
    print(f'PROPOSAL written: {out.name}')
    print(f'  promote={len(promote)} merge={len(merge)} emerging={len(emerging)} other={len(other)}  (LLM ${cost:.4f})')
    print(f'  proposed new buckets: ' + ', '.join(c['canonical_name'] for c in promote))

if __name__ == '__main__':
    main()
