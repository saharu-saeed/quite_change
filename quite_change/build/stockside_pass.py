# -*- coding: utf-8 -*-
"""Combined post-Phase-2 STOCK-SIDE pass (path-shape + beat/raise + consensus_miss un-dump).

ONE targeted re-run of the stock side only. For each company it:
  1. Fetches the 14-day daily path (free; price_feed already returns it) → shape + timing.
  2. Reads the beat/raise signal from packet.numbers (rev/op/net YoY + prior-year base)
     and the staged guidance_overlay.
  3. Re-derives stock_reason_tag with the un-dump logic — consensus_miss is no longer a
     soft default: an on-print reaction that fits a clean story becomes rerating_on_growth /
     guidance_disappointment / capital_return_surprise; a DELAYED, report-silent move becomes
     delayed_unexplained (needs_enrichment=true); consensus_miss is kept ONLY for genuine
     on-print beat/miss reactions that fit no clean story.
  4. Re-writes why_stock_moved (+ _en) path-aware, holding the rail: shape/timing = fact from
     prices; cause needs the filing; delayed + report-silent → "later/market", never invented.

UNTOUCHED: specific_bucket / business_reason_tag / why_business_moved / stock_dir / the feed
quadrant. Deterministic tags (muted ≤1% abs, market-beta ≤1% rel) are kept without LLM spend.
Stores path_pct / path_shape / path_timing / needs_enrichment for the later renderer sparkline.
Staged files only; committed files untouched.

  python build/stockside_pass.py --year 2025 --limit 4   # smoke
  python build/stockside_pass.py --year 2025             # one year
  python build/stockside_pass.py                          # all 4 years
  python build/stockside_pass.py --dry                    # report only, no write
"""
from __future__ import annotations
import os, sys, json, glob
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'research'))
sys.stdout.reconfigure(encoding='utf-8')
import price_feed as pf
from dotenv import load_dotenv
load_dotenv(ROOT.parent / '.env', override=True)
from anthropic import AnthropicBedrock

YEARS = {'2022': '_pkts_2022_mdna', '2023': '_pkts_2023_mdna', '2024': '_pkts_2024_mdna', '2025': '_pkts_mdna'}
MUTED_ABS = 1.0      # |net| ≤ this → muted_no_reaction (deterministic)
BETA_REL = 1.0       # |relative| ≤ this (and a real abs move) → other / market-beta (deterministic)

SHAPE_JP = {
    'immediate_and_held': '発表直後(1〜2営業日)に動き以後ほぼ横ばいで維持',
    'delayed': '発表直後は小動きで、数営業日後に大きく動いた(発表への直接反応ではない可能性)',
    'pop_then_faded': '一旦上昇したあと戻した(初動が後半に減衰)',
    'drop_then_recovered': '一旦下落したあと戻した',
    'round_trip_volatile': '上下に大きく振れて往復した',
    'steady_drift': '一日の急変なく緩やかに推移した',
    'muted_flat': 'ほぼ無反応(小幅)',
}


def path_features(series):
    items = sorted(series.items())
    if len(items) < 4:
        return None
    c = [v for _, v in items]
    p0 = c[0]
    cum = [(x / p0 - 1) * 100 for x in c]
    net = cum[-1]
    react = cum[2] if len(cum) > 2 else cum[-1]
    mx, mn = max(cum), min(cum)
    i_mx, i_mn = cum.index(mx), cum.index(mn)
    rng = mx - mn
    a = abs(net)
    if a < 1.5 and rng < 3:
        shape = 'muted_flat'
    elif mx >= 2 and mn <= -2:
        shape = 'round_trip_volatile'
    elif net > 0 and (mx - net) >= 2.5:
        shape = 'pop_then_faded'
    elif net < 0 and (net - mn) >= 2.5:
        shape = 'drop_then_recovered'
    elif a >= 1.5 and abs(react) / max(a, 0.1) >= 0.6:
        shape = 'immediate_and_held'
    elif a >= 1.5 and abs(react) / max(a, 0.1) <= 0.35:
        shape = 'delayed'
    else:
        shape = 'steady_drift'
    return {'net': round(net, 2), 'react_2d': round(react, 2), 'ratio': round(abs(react) / max(a, 0.1) * 100),
            'max_up': round(mx, 2), 'max_up_day': i_mx, 'max_dn': round(mn, 2), 'max_dn_day': i_mn,
            'shape': shape, 'path_pct': [round(x, 2) for x in cum], 'n_days': len(cum)}


TAGS = ['rerating_on_growth', 'guidance_disappointment', 'consensus_miss',
        'capital_return_surprise', 'delayed_unexplained']
SCHEMA = {
    'type': 'object',
    'properties': {
        'stock_reason_tag': {'type': 'string', 'enum': TAGS},
        'why_stock_moved': {'type': 'string'},
        'why_stock_moved_en': {'type': 'string'},
        'timing_basis': {'type': 'string', 'enum': ['on_print', 'delayed', 'accumulated', 'mixed']},
        'needs_enrichment': {'type': 'boolean'},
        'confidence': {'type': 'string', 'enum': ['high', 'med', 'low']},
    },
    'required': ['stock_reason_tag', 'why_stock_moved', 'why_stock_moved_en',
                 'timing_basis', 'needs_enrichment', 'confidence'],
    'additionalProperties': False,
}


def build_prompt(ticker, name, pr, f, num, guid, ground):
    when = (f"最大{'上昇' if abs(f['max_up']) >= abs(f['max_dn']) else '下落'}は"
            f"{max(f['max_up_day'], f['max_dn_day'])}営業日目付近")
    py = (num or {}).get('prior_year_yoy', {}) or {}
    return f"""あなたは日本株アナリスト。{ticker} {name} の決算後の株価反応を再評価する。
目的(2つ): (A) why_stock_moved を「14日間の値動きの形・タイミング」を踏まえて書き直す。
(B) stock_reason_tag を厳格に再判定し、consensus_miss の安易な既定値化を解消する。

【確定事実(覆さない・方向は固定)】
P0={pr.get('p0_date')}({pr.get('p0')}円) → P1={pr.get('p1_date')}({pr.get('p1')}円)
ネット{pr.get('pct_change')}% / 対TOPIX{pr.get('relative_pct')}% / 方向={pr.get('stock_dir')}

【14日間の値動きの形(株価データから機械算出した事実)】
形: {SHAPE_JP.get(f['shape'], f['shape'])}
初動(発表後1〜2営業日): {f['react_2d']}%（netの約{f['ratio']}%を初動が占める）
期間中 最大上昇{f['max_up']}% / 最大下落{f['max_dn']}%（{when}）

【今期実績(beat/raise材料・決算短信の数値)】
売上 {num.get('rev_pct')}% / 営業利益 {num.get('op_pct')}% / 純利益 {num.get('net_pct')}%
前年同期の伸び(高ベース確認): 営業{py.get('op_pct')}% / 純{py.get('net_pct')}%
ガイダンス: {guid}（raise=会社予想が強気/上方, disappointment=失望/弱気, none=中立）

【決算短信 本文(原因の根拠はここだけ・PIT厳守)】
{ground}

【stock_reason_tag 再判定ルール(厳格・consensus_miss を安売りしない)】
・rerating_on_growth … 上昇が【発表時点(on print)】の好実績/上方ガイダンスで説明できる(成長の再評価)。
・guidance_disappointment … 下落が【発表時点】のガイダンス失望/減益で説明できる。
・capital_return_surprise … 自社株買い・大幅増配等の株主還元サプライズが主因。
・delayed_unexplained … 大きな値動きが【発表当日でなく数営業日後】に起き、短信に遅行の理由が明記されていない
   → 決算への直接反応ではない。needs_enrichment=true。原因を捏造しない。
・consensus_miss … 値動きが【on print】に起きた beat/miss への反応だが上記の明確な型に当てはまらない"残余"。
   ★on print の時のみ使用。遅行(delayed)なら必ず delayed_unexplained にする。

【why_stock_moved 執筆ルール】
1. 形・タイミングは"事実"として明記してよい(例「上昇の大半は発表◯営業日後に起きた」「初動で動き以後横ばい」)。
2. "原因"は短信に明記がある時だけ結びつける。
3. 遅行かつ短信に説明が無い → 「決算発表への直接反応ではなく後日の市場・外部要因の可能性が高い」と正直に。捏造しない。
4. 平易な日本語2〜4文。why_stock_moved_en は同内容の自然な英語(数値・社名は正確に)。

返却(JSON): stock_reason_tag, why_stock_moved, why_stock_moved_en, timing_basis, needs_enrichment, confidence"""


def process(client, model, y, pk, comp, dry):
    t = pk['ticker']
    pr = pk.get('prices', {}) or {}
    ab = pr.get('pct_change'); rel = pr.get('relative_pct')
    name = (lambda nj, nn: nj if (nj and nj != 'False') else nn)(pk.get('name_jp'), pk.get('name')) or t
    # path features for the record / sparkline (cheap, all companies)
    feat = None
    if pr.get('p0_date') and pr.get('p1_date'):
        try:
            s = pf.fetch_tempest(t, datetime.strptime(pr['p0_date'], '%Y-%m-%d'), datetime.strptime(pr['p1_date'], '%Y-%m-%d'))
            feat = path_features(s)
        except Exception:
            feat = None
    rec = {'ticker': t, 'name': name}
    if feat:
        rec['path'] = {k: feat[k] for k in ('shape', 'net', 'react_2d', 'max_up', 'max_dn', 'path_pct')}
    # ── deterministic gate (no LLM): non-movers keep their tag + existing prose ──
    if ab is None:
        rec['action'] = 'skip_no_price'; return y, t, rec, None
    if abs(ab) <= MUTED_ABS:
        rec['new_tag'] = 'muted_no_reaction'; rec['action'] = 'det_muted'; return y, t, rec, ('det', rec)
    if rel is not None and abs(rel) <= BETA_REL:
        rec['new_tag'] = 'other'; rec['action'] = 'det_market_beta'; return y, t, rec, ('det', rec)
    if not feat:                              # mover but path unavailable → keep tag, flag
        rec['new_tag'] = comp.get('stock_reason_tag'); rec['action'] = 'no_path'; return y, t, rec, ('det', rec)
    # ── company-specific mover with a path → LLM re-derive ──
    ground = (pk.get('tanshin_text') or pk.get('why_text') or '')[:6000]
    msg = client.messages.create(model=model, max_tokens=1100,
        messages=[{'role': 'user', 'content': build_prompt(t, name, pr, feat, pk.get('numbers', {}) or {}, comp.get('guidance_overlay'), ground)}],
        output_config={'format': {'type': 'json_schema', 'schema': SCHEMA}})
    r = json.loads(''.join(b.text for b in msg.content if b.type == 'text'))
    rec.update({'old_tag': comp.get('stock_reason_tag'), 'new_tag': r['stock_reason_tag'],
                'timing': r['timing_basis'], 'needs_enrichment': r['needs_enrichment'], 'action': 'llm'})
    return y, t, rec, ('llm', r, feat)


def main():
    args = sys.argv[1:]
    dry = '--dry' in args
    limit = int(args[args.index('--limit') + 1]) if '--limit' in args else None
    tickers = args[args.index('--tickers') + 1].split(',') if '--tickers' in args else None
    yrs = [args[args.index('--year') + 1]] if '--year' in args else list(YEARS)

    model = os.environ['BEDROCK_MODEL_ID']
    client = AnthropicBedrock(aws_region=os.environ['AWS_REGION'], aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_key=os.environ['AWS_SECRET_ACCESS_KEY'], aws_session_token=os.environ.get('AWS_SESSION_TOKEN') or None)

    from collections import Counter
    for y in yrs:
        d = YEARS[y]
        sp = ROOT / 'data' / 'quarterly' / f'it_q4_{y}.staged.json'
        data = json.loads(sp.read_text(encoding='utf-8'))
        comps = data['companies']
        before = Counter(c.get('stock_reason_tag') for c in comps.values())
        jobs = []
        for f in glob.glob(str(ROOT / 'data' / 'quarterly' / d / '*.json')):
            pk = json.loads(Path(f).read_text(encoding='utf-8'))
            t = pk['ticker']
            if t in comps and comps[t].get('specific_bucket'):
                if tickers and t not in tickers:
                    continue
                jobs.append((pk, comps[t]))
        if limit:
            jobs = jobs[:limit]
        print(f'[{y}] stock-side pass on {len(jobs)} companies...', flush=True)

        results = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = [ex.submit(process, client, model, y, pk, comp, dry) for pk, comp in jobs]
            for fut in as_completed(futs):
                results.append(fut.result())

        moved, undumped, enrich = [], [], []
        for (yy, t, rec, payload) in results:
            c = comps[t]
            old = c.get('stock_reason_tag')
            if payload and payload[0] == 'llm':
                _, r, feat = payload
                # RAIL: a delayed move is by definition NOT a print reaction → its cause is not in
                # the report → delayed_unexplained, regardless of which directional tag the LLM chose.
                tag = 'delayed_unexplained' if r['timing_basis'] == 'delayed' else r['stock_reason_tag']
                c['stock_reason_tag'] = tag
                c['why_stock_moved'] = r['why_stock_moved']
                c['why_stock_moved_en'] = r['why_stock_moved_en']
                c['timing_basis'] = r['timing_basis']
                c['needs_enrichment'] = (tag == 'delayed_unexplained')   # enrichment ≡ delayed_unexplained
                c['path_shape'] = feat['shape']
                c['path_pct'] = feat['path_pct']
                if tag != old:
                    undumped.append((t, rec['name'], old, tag, r['timing_basis']))
                    moved.append((t, old, tag))
                if c['needs_enrichment']:
                    enrich.append((t, rec['name'], r['timing_basis']))
            elif payload and payload[0] == 'det':
                if rec.get('new_tag') and rec['new_tag'] != old:
                    c['stock_reason_tag'] = rec['new_tag']
                    moved.append((t, old, rec['new_tag']))
                if 'path' in rec:
                    c['path_shape'] = rec['path']['shape']
                    c['path_pct'] = rec['path']['path_pct']

        after = Counter(c.get('stock_reason_tag') for c in comps.values())
        print(f"\n[{y}] consensus_miss {before.get('consensus_miss',0)} → {after.get('consensus_miss',0)}   "
              f"delayed_unexplained 0 → {after.get('delayed_unexplained',0)}")
        print(f"[{y}] tag dist NOW:", dict(after))
        print(f"[{y}] tag changes: {len(moved)}   needs_enrichment(delayed/report-silent): {len(enrich)}")
        for t, nm, o, n, tb in sorted(undumped, key=lambda x: x[3]):
            print(f"   {t} {nm[:22]:22} {o} → {n}  ({tb})")
        if enrich:
            print(f"  ENRICHMENT-routed (measurable by timing): {[e[0] for e in enrich]}")

        if not dry:
            sp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"[{y}] written to staged (committed untouched).")
        else:
            print(f"[{y}] --dry: not written.")


if __name__ == '__main__':
    main()
