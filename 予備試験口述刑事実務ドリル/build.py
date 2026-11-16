import json, re, glob, importlib, html, sys
from collections import Counter, defaultdict

cards = json.load(open('cards.json', encoding='utf-8'))
from arts import A

# ── 元データの手当て
DUP = {f'H29-{i:02d}': f'H29-{i+9:02d}' for i in range(1, 10)}  # 冒頭の重複・書きかけ
for c in cards:
    if c['id'] == 'H29-60':
        q0, rest = re.split(r'\s+', c['q'].strip(), maxsplit=1); c['q'], c['a'] = q0, rest
    if c['id'] == 'R1-28':
        q = c['q']
        c['q'], c['a'] = q.split('?', 1)[0] + '?', q.split('?', 1)[1].strip()
cards = [c for c in cards if c['id'] not in DUP]
assert all(c['q'] and c['a'] for c in cards), [c['id'] for c in cards if not (c['q'] and c['a'])]

import unicodedata
def md2html(s):
    s = s.replace('\\<', '<').replace('\\>', '>').replace('\\~', '~').replace('\\*', '*')
    s = re.sub(r'(\S)(\*{0,2})[\u309b\u3099]', lambda m: unicodedata.normalize('NFC', m.group(1) + '\u3099') + m.group(2), s)  # 分離した濁点
    s = html.escape(s, quote=False)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s, flags=re.S)
    s = s.replace('**', '')
    s = re.sub(r'[ \u3000]+\n', '\n', s)
    s = re.sub(r'\n[ \u3000]+', '\n', s)
    s = re.sub(r'\n{2,}', '\n', s)
    # 列挙の番号（「 2急速」「 2. 」「 ②」）の前で改行
    s = re.sub(r'(?<=[^\s>]) (?=(?:\d{1,2}(?:\.|：| )?|[①-⑳])[^\d\s条項号年月日時分秒歳ヶか万円%％ｍメキ倍回人名])', '\n', s)
    s = re.sub(r'(?<=[^\x00-\x7f]) (?=[^\x00-\x7f])', '', s)  # PDF由来の和文中スペース
    return s.strip().replace('\n', '<br>')

# ── 問題の読み込み
items = []
for f in sorted(glob.glob('items_*.py')):
    for it in importlib.import_module(f[:-3]).I:
        items.append(it)

ids = {c['id'] for c in cards}
errors = []
cover = defaultdict(list)
out_items = []
seq = Counter()
for src, t, q, a, e, arts in items:
    srcs = src.split(',')
    for s in srcs:
        if s not in ids:
            errors.append(f'出典IDが存在しない: {s} ({q[:20]})')
        cover[s].append(q)
    for k in arts:
        if k not in A:
            errors.append(f'条文キーがない: {k}')
    y = srcs[0].split('-')[0]
    seq[y] += 1
    iid = f'{y}-q{seq[y]:02d}'
    if 'R1-31' in srcs and '刑217' not in arts:
        arts = arts + ['刑217']
    d = {'id': iid, 'y': y, 'src': srcs, 't': t, 'q': q, 'e': e, 'arts': arts}
    if t == 'ox':
        assert isinstance(a, bool), q
        d['a'] = a
    else:
        assert isinstance(a, list) and len(a) == 4 and len(set(a)) == 4, q
        d['c'] = a
    out_items.append(d)

missing = [c['id'] for c in cards if c['id'] not in cover]

# 各カードに、それを出典とする問題の条文をひも付け
card_arts = defaultdict(list)
for d in out_items:
    for s in d['src']:
        for k in d['arts']:
            if k not in card_arts[s]:
                card_arts[s].append(k)

YL = {'H23': '平成23年', 'H24': '平成24年', 'H25': '平成25年', 'H26': '平成26年', 'H27': '平成27年', 'H28': '平成28年',
      'H29': '平成29年', 'H30': '平成30年', 'R1': '令和元年', 'R2': '令和2年', 'R3': '令和3年'}
scene_first = {}
out_cards = []
for c in cards:
    key = (c['y'], c['sn'])
    if key not in scene_first or '事例' in c['q'][:30] or len(c['q']) > 110:
        scene_first[key] = c['id']   # 直近で事例が示された問答
    out_cards.append({'id': c['id'], 'y': c['y'], 'sn': c['sn'], 'sc': c['scene'], 'q': md2html(c['q']), 'a': md2html(c['a']),
                      'arts': card_arts[c['id']], 'first': scene_first[key]})

# e-Govの条文リンク（スキル egov-article-link の手順：法令ID＋本則のArticle Num → #Mp-At_{Num}。項は条で止める）
LAW_ID = {'刑法': '140AC0000000045', '刑訴法': '323AC0000000131', '憲法': '321CONSTITUTION', '警職法': '323AC0000000136'}
NUMS = json.load(open('egov_nums.json', encoding='utf-8'))  # 各法令の本則にある Article Num（law_data API から取得）
def egov_url(law, no):
    if law not in LAW_ID:
        return ''  # 刑訴規則・職務基本規程はe-Gov未収録
    m = re.match(r'(\d+)条(?:の(\d+))?', no)
    num = m.group(1) + ('_' + m.group(2) if m.group(2) else '')
    if num not in NUMS[LAW_ID[law]]:
        errors.append(f'e-Govの本則に条番号がない: {law} {no} → {num}')
    return f'https://laws.e-gov.go.jp/law/{LAW_ID[law]}#Mp-At_{num}'
ART = {k: {'law': v[0], 'no': v[1], 'cap': v[2], 'text': v[3], 'url': egov_url(v[0], v[1])} for k, v in A.items()}
data = {'years': YL, 'cards': out_cards, 'items': out_items, 'arts': ART}

# ── 網羅チェックの報告
print('問答（カード）:', len(out_cards), ' 除外した重複:', len(DUP))
print('ゲーム問題:', len(out_items), Counter(d['t'] for d in out_items))
print('年度別  問答数 / 問題数 / 未カバー')
for y in YL:
    nc = sum(1 for c in out_cards if c['y'] == y)
    ni = sum(1 for d in out_items if d['y'] == y)
    nm = [m for m in missing if m.startswith(y + '-')]
    print(f'  {YL[y]:6} {nc:3} / {ni:3} / {nm}')
print('未カバーの問答:', missing)
print('エラー:', errors)
unused = sorted(set(A) - {k for d in out_items for k in d['arts']})
print('未使用の条文:', unused)

tpl = open('template.html', encoding='utf-8').read()
open('index.html', 'w', encoding='utf-8').write(tpl.replace('/*__DATA__*/', 'const DATA = ' + json.dumps(data, ensure_ascii=False) + ';'))
json.dump({'missing': missing, 'errors': errors}, open('coverage.json', 'w'), ensure_ascii=False)
if missing or errors:
    sys.exit(1)
