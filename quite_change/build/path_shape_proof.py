# -*- coding: utf-8 -*-
"""PROOF: 14-day path shape vs the 2-point endpoint, and how it changes why_stock_moved.

Free part: fetch the daily close path over each company's P0→P1 window (the feed
already returns it; the pipeline just kept 2 points), derive deterministic path
features + a shape label. Then for a few DELIBERATELY-chosen shapes (delayed,
round-trip, immediate-and-held, drift), re-write why_stock_moved with the path in
context — keeping the rail: shape/timing = fact from prices; cause needs the
filing; a late report-unexplained move → "later/market catalyst", never invented.

  python build/path_shape_proof.py            # scan 2025, pick 5, show OLD vs NEW
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

YEAR = '2025'
PKT = ROOT / 'data' / 'quarterly' / '_pkts_mdna'
STAGED = ROOT / 'data' / 'quarterly' / f'it_q4_{YEAR}.staged.json'


def features(series: dict):
    """series = {date: close}. Return path features (deterministic, from prices only)."""
    items = sorted(series.items())
    if len(items) < 4:
        return None
    dates = [d for d, _ in items]
    c = [v for _, v in items]
    p0 = c[0]
    cum = [(x / p0 - 1) * 100 for x in c]
    net = cum[-1]
    react = cum[2] if len(cum) > 2 else cum[-1]          # move over first ~2 sessions after print
    mx, mn = max(cum), min(cum)
    i_mx, i_mn = cum.index(mx), cum.index(mn)
    rng = mx - mn
    # ── shape classification ──
    a_net = abs(net)
    if a_net < 1.5 and rng < 3:
        shape = 'muted_flat'
    elif mx >= 2 and mn <= -2:
        shape = 'round_trip_volatile'
    elif net > 0 and (mx - net) >= 2.5:
        shape = 'pop_then_faded'
    elif net < 0 and (net - mn) >= 2.5:
        shape = 'drop_then_recovered'
    elif a_net >= 1.5 and abs(react) / max(a_net, 0.1) >= 0.6:
        shape = 'immediate_and_held'
    elif a_net >= 1.5 and abs(react) / max(a_net, 0.1) <= 0.35:
        shape = 'delayed'
    else:
        shape = 'steady_drift'
    return {'net': round(net, 2), 'react_2d': round(react, 2),
            'max_up': round(mx, 2), 'max_up_day': i_mx, 'max_dn': round(mn, 2), 'max_dn_day': i_mn,
            'range': round(rng, 2), 'shape': shape, 'n_days': len(cum),
            'path': [round(x, 2) for x in cum], 'dates': dates}


SHAPE_JP = {
    'immediate_and_held': '発表直後（1〜2営業日）に動き、その後はほぼ横ばいで維持',
    'delayed': '発表直後は小動きで、数営業日後に大きく動いた（発表への直接反応ではない可能性）',
    'pop_then_faded': '一旦上昇したあと戻した（初動が後半に減衰）',
    'drop_then_recovered': '一旦下落したあと戻した',
    'round_trip_volatile': '上下に大きく振れて往復した',
    'steady_drift': '一日の急変なく緩やかに推移した',
    'muted_flat': 'ほぼ無反応（小幅）',
}


def fetch_feat(ticker, p0s, p1s):
    try:
        s = pf.fetch_tempest(ticker, datetime.strptime(p0s, '%Y-%m-%d'), datetime.strptime(p1s, '%Y-%m-%d'))
        return ticker, features(s)
    except Exception as e:
        return ticker, None


NEW_SCHEMA = {'type': 'object', 'properties': {'why_stock_moved': {'type': 'string'}},
              'required': ['why_stock_moved'], 'additionalProperties': False}


def new_why(client, model, c, pk, f, rel_net):
    pr = pk.get('prices', {})
    name = pk.get('name_jp') or pk.get('name') or c['ticker']
    ground = (pk.get('tanshin_text') or pk.get('why_text') or '')[:5500]
    when = f"最大{'上昇' if abs(f['max_up'])>=abs(f['max_dn']) else '下落'}は{max(f['max_up_day'],f['max_dn_day'])}営業日目付近"
    prompt = f"""あなたは日本株アナリスト。{c['ticker']} {name} の決算後の株価反応について why_stock_moved を書き直す。

【確定事実（覆さない）】発表日P0={pr.get('p0_date')}（{pr.get('p0')}円）→10営業日後={pr.get('p1_date')}（{pr.get('p1')}円）、ネット{f['net']}%。

【14日間の値動きの"形"（株価データから機械的に算出した事実）】
・タイミング: {SHAPE_JP.get(f['shape'], f['shape'])}
・初動（発表後1〜2営業日）: {f['react_2d']}%／期間中の最大上昇 {f['max_up']}%・最大下落 {f['max_dn']}%（{when}）
・対TOPIX（同期間ネット）: {rel_net}%

【決算短信 本文（原因の根拠はここだけ・PIT厳守）】
{ground}

【ルール（厳守）】
1. 値動きの"形・タイミング"は株価データの事実なので明記してよい（例「下落は発表◯営業日後に起きた」「初動で動いて以後横ばい」）。
2. "原因"は決算短信に明記がある時だけ書く。形と整合する原因が短信にあれば結びつける。
3. 動きが発表から遅れて起き短信に説明が無い場合は「決算発表への直接反応ではなく、後日の市場・外部要因による可能性が高い」と正直に書く。原因を捏造しない。
4. 平易な日本語2〜4文。

返却: why_stock_moved（日本語）のみ。"""
    msg = client.messages.create(model=model, max_tokens=700,
        messages=[{'role': 'user', 'content': prompt}],
        output_config={'format': {'type': 'json_schema', 'schema': NEW_SCHEMA}})
    return json.loads(''.join(b.text for b in msg.content if b.type == 'text'))['why_stock_moved']


def main():
    comps = json.loads(STAGED.read_text(encoding='utf-8'))['companies']
    jobs = []
    for f in glob.glob(str(PKT / '*.json')):
        pk = json.loads(Path(f).read_text(encoding='utf-8'))
        t = pk['ticker']
        pr = pk.get('prices', {})
        if t in comps and pr.get('p0_date') and pr.get('p1_date'):
            jobs.append((t, pr['p0_date'], pr['p1_date'], pk))
    print(f'Fetching daily paths for {len(jobs)} companies (free)...', flush=True)
    feats = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_feat, t, a, b): t for t, a, b, _ in jobs}
        for fut in as_completed(futs):
            t, f = fut.result()
            if f:
                feats[t] = f
    from collections import Counter
    dist = Counter(f['shape'] for f in feats.values())
    print('\nSHAPE DISTRIBUTION (2025):')
    for s, n in dist.most_common():
        print(f'  {n:3d}  {s}')

    # pick examples: guarantee delayed + a reversal + immediate_and_held, plus drift + one more reversal/volatile
    pk_by = {t: pk for t, _, _, pk in jobs}
    def pick(shape):
        cands = [(t, f) for t, f in feats.items() if f['shape'] == shape]
        cands.sort(key=lambda x: -abs(x[1]['net']))   # most pronounced first
        return cands[0][0] if cands else None
    wanted = ['delayed', 'pop_then_faded', 'drop_then_recovered', 'round_trip_volatile', 'immediate_and_held', 'steady_drift']
    chosen = []
    for s in wanted:
        t = pick(s)
        if t and t not in chosen:
            chosen.append(t)
        if len(chosen) >= 5:
            break
    print(f'\nChosen {len(chosen)} for OLD-vs-NEW proof:', chosen, flush=True)

    model = os.environ['BEDROCK_MODEL_ID']
    client = AnthropicBedrock(aws_region=os.environ['AWS_REGION'], aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_key=os.environ['AWS_SECRET_ACCESS_KEY'], aws_session_token=os.environ.get('AWS_SESSION_TOKEN') or None)

    out = []
    for t in chosen:
        f = feats[t]; pk = pk_by[t]; c = comps[t]
        rel_net = round(f['net'] - (pk.get('prices', {}).get('market_pct') or 0), 2)
        new = new_why(client, model, c, pk, f, pk.get('prices', {}).get('relative_pct', rel_net))
        out.append({'ticker': t, 'name': pk.get('name_jp') or pk.get('name'), 'shape': f['shape'],
                    'net': f['net'], 'react_2d': f['react_2d'], 'max_up': f['max_up'], 'max_dn': f['max_dn'],
                    'path': f['path'], 'old': c.get('why_stock_moved', ''), 'new': new})
    rep = ROOT / 'data' / 'quarterly' / '_path_proof_2025.json'
    rep.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n' + '=' * 78)
    for r in out:
        print(f"\n■ {r['ticker']} {r['name']}  —  shape={r['shape']}  net={r['net']}%  initial(2d)={r['react_2d']}%  max+{r['max_up']}/{r['max_dn']}")
        print(f"  path%: {r['path']}")
        print(f"  OLD (endpoint-only): {r['old'][:300]}")
        print(f"  NEW (path-aware)   : {r['new'][:300]}")
    print(f"\nWrote {rep.name}")


if __name__ == '__main__':
    main()
