import re, json, sys
src = sys.argv[1]
lines = open(src, encoding='utf-8').read().split('\n')
start = next(i for i, l in enumerate(lines) if l.startswith('# **平成23年**'))
lines = lines[start:]

def clean(h):
    return re.sub(r'\s*\{#.*\}\s*$', '', h).lstrip('#').strip().strip('*').strip()

YMAP = {'平成23年': 'H23', '平成24年': 'H24', '平成25年': 'H25', '平成26年': 'H26', '平成27年': 'H27',
        '平成28年': 'H28', '平成29年': 'H29', '平成30年': 'H30', '令和元年': 'R1', '令和2年': 'R2', '令和3年': 'R3'}

cards = []
year = scene = None
target = None  # (card, 'q'|'a')
buf = []
seq = {}
scene_idx = {}

def flush():
    global buf
    if target is not None:
        c, k = target
        t = '\n'.join(buf).strip()
        c[k] = (c[k] + '\n\n' + t).strip() if c[k] else t
    buf = []

for l in lines:
    if l.startswith('# ') and not l.startswith('## '):
        flush(); target = None
        year = clean(l); scene = None
        continue
    if l.startswith('## '):
        flush(); target = None
        scene = clean(l)
        continue
    m = re.match(r'^#### \*\*([QA])\d*\*\*', l)
    if m:
        flush()
        if m.group(1) == 'Q':
            y = YMAP[year]
            sk = (y, scene)
            if sk not in scene_idx:
                scene_idx[sk] = len([k for k in scene_idx if k[0] == y]) + 1
            seq[y] = seq.get(y, 0) + 1
            c = {'id': f'{y}-{seq[y]:02d}', 'y': y, 'yl': year, 'sn': scene_idx[sk], 'scene': scene, 'q': '', 'a': ''}
            cards.append(c)
            target = (c, 'q')
        else:
            target = (cards[-1], 'a')
        continue
    if target is not None:
        buf.append(l)
flush()

# 画像の参照などを除去
for c in cards:
    for k in ('q', 'a'):
        c[k] = re.sub(r'!\[\]\[image\d+\]', '', c[k]).strip()
        c[k] = re.sub(r'^\[image\d+\]: <data:.*$', '', c[k], flags=re.M).strip()

json.dump(cards, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
empty = [c['id'] for c in cards if not c['q'] or not c['a']]
print(len(cards), 'cards; empty:', empty)
from collections import Counter
print(Counter(c['y'] for c in cards))
print(sorted({(c['y'], c['sn'], c['scene']) for c in cards}))
