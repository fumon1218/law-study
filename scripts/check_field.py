#!/usr/bin/env python3
"""data/field/situations.json 의 근거 조문·판례가 내장 데이터에 실제로 있는지 검증 (없으면 비정상 종료)"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
laws = {}
for e in json.load(open(os.path.join(ROOT, 'data', 'index.json'), encoding='utf-8'))['laws']:
    d = json.load(open(os.path.join(ROOT, 'data', e['file']), encoding='utf-8'))
    laws[d['name']] = {a['label'] for a in d['articles']}
cases = {c['id'] for c in json.load(open(os.path.join(ROOT, 'data', 'cases', 'index.json'), encoding='utf-8'))['cases']}
f = json.load(open(os.path.join(ROOT, 'data', 'field', 'situations.json'), encoding='utf-8'))
bad = []
refs = [(s['id'], b) for s in f['situations'] for b in s['basis']] + [(r['actor'], d) for r in f['roles'] for d in r['does']]
for who, b in refs:
    if b['law'] not in laws: bad.append('%s: 법령 없음 %s' % (who, b['law']))
    elif b['label'] not in laws[b['law']]: bad.append('%s: 조문 없음 %s %s' % (who, b['law'], b['label']))
for s in f['situations']:
    for c in s['cases']:
        if c not in cases: bad.append('%s: 판례 없음 %s' % (s['id'], c))
    for k in ('title', 'ask', 'check', 'basis', 'steps', 'dont', 'reply', 'tags'):
        if not s.get(k): bad.append('%s: %s 비어 있음' % (s['id'], k))
if bad:
    print('\n'.join(bad)); sys.exit(1)
print('field 검증 통과: 상황 %d · 근거 %d건 · 권한표 %d주체' % (len(f['situations']), len(refs), len(f['roles'])))
