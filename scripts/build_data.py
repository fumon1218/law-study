#!/usr/bin/env python3
"""legalize-kr 마크다운 → 앱용 JSON 변환 (data/source/*.md → data/laws/*.json, data/index.json)

사용: python3 scripts/build_data.py
- 현행본(시행 중) 조문을 articles 로, 이후 공포된 시행 예정 개정은 pending 으로 분리한다.
- 변환 후 원문 대조 검증(조문 수, 본문 글자 단위 일치)을 수행하고 실패하면 비정상 종료한다.
"""
import hashlib, json, os, re, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'source')
OUT = os.path.join(ROOT, 'data', 'laws')

# 법령별 입력: current = 시행 중 버전, upcoming = 이후 공포(미시행) 버전을 공포 순서대로
LAWS = [
    {'file': 'special-edu-act.json', 'current': 'act.current.md', 'upcoming': ['act.upcoming-1.md', 'act.upcoming-2.md']},
    {'file': 'special-edu-decree.json', 'current': 'decree.current.md', 'upcoming': []},
    {'file': 'special-edu-rule.json', 'current': 'rule.current.md', 'upcoming': []},
]
# scripts/fetch_sources.py 가 만든 파일들 (현행 + 시행 예정). (키, 출력 파일명, 시행 예정본 개수는 versions.json 에서 읽는다)
_VERS = os.path.join(SRC, 'versions.json')
_V = json.load(open(_VERS, encoding='utf-8'))['files'] if os.path.exists(_VERS) else {}
for _key, _out in [
    ('early-act', 'early-act.json'), ('early-decree', 'early-decree.json'), ('early-rule', 'early-rule.json'),
    ('school-act', 'school-act.json'), ('school-decree', 'school-decree.json'), ('school-rule', 'school-rule.json'),
    ('higher-act', 'higher-act.json'), ('higher-decree', 'higher-decree.json'),
    ('welfare-act', 'welfare-act.json'), ('welfare-decree', 'welfare-decree.json'), ('welfare-rule', 'welfare-rule.json'),
    ('antidisc-act', 'antidisc-act.json'), ('antidisc-decree', 'antidisc-decree.json'),
]:
    LAWS.append({'file': _out, 'current': _key + '.current.md',
                 'upcoming': ['%s.upcoming-%d.md' % (_key, n + 1) for n in range(len(_V.get(_key, {}).get('upcoming', [])))]})
NOTES = {
    '장애인 등에 대한 특수교육법 시행령': ['별표(특수교육대상자 선정 기준 등 표)는 원문 데이터에 포함되어 있지 않습니다. 「원문 법령」 링크에서 확인하세요.'],
    '장애인 등에 대한 특수교육법 시행규칙': ['별표·서식은 원문 데이터에 포함되어 있지 않습니다. 「원문 법령」 링크에서 확인하세요.'],
}
BYEOLPYO = '별표·서식은 원문 데이터에 포함되어 있지 않을 수 있습니다. 「원문 법령」 링크에서 확인하세요.'
RESTORE_NOTE = ('이 법령은 원천 데이터의 최신본에 아직 시행되지 않은 개정이 이미 섞여 있어, 그 개정분만 되돌려 현재 시행 중인 본문으로 복원한 것입니다(기계적 처리, 개정 이력 표기는 최신 기준). '
                '시행 전 개정은 「시행 예정」으로 따로 표시됩니다. 업무에 적용하기 전에는 「원문 법령」 링크로 확인하세요.')

ART_RE = re.compile(r'^#####\s+(제(\d+)조(?:의(\d+))?)\s*(?:\((.*)\))?\s*$')
CHAP_RE = re.compile(r'^(#{2,4})\s+(제\d+(?:의\d+)?[편장절관].*)$')
ANNOT = re.compile(r'\s*<[^>]*>\s*$')


def unescape(s):
    return re.sub(r'\\([\\`*_{}\[\]()#+\-.!<>~|])', r'\1', s)


def read_meta(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        raise SystemExit('frontmatter 없음')
    meta = {}
    for line in m.group(1).split('\n'):
        k = re.match(r'^([^\s:-][^:]*):\s*(.*)$', line)
        if k and k.group(2) != '':
            meta[k.group(1)] = k.group(2).strip().strip("'")
    return meta, text[m.end():]


def clean_line(raw):
    s = raw.strip()
    s = re.sub(r'^\*\*([①-⑳㉑-㉟]+)\*\*\s*', r'\1 ', s)
    return unescape(s)


def parse(path):
    text = open(path, encoding='utf-8').read()
    meta, body = read_meta(text)
    arts, chapter, cur, buchik = [], '', None, []
    heads = {}  # 제목 단계(##=장, ###=절, ####=관) → 제목
    in_buchik = False
    for raw in body.split('\n'):
        if raw.startswith('## 부칙'):
            in_buchik = True; cur = None; continue
        if in_buchik:
            if raw.strip():
                buchik.append(unescape(raw.strip()))
            continue
        m = CHAP_RE.match(raw)
        if m:
            lv = len(m.group(1))
            heads[lv] = ANNOT.sub('', m.group(2)).strip()
            for k in [k for k in heads if k > lv]:
                del heads[k]
            chapter = ' › '.join(heads[k] for k in sorted(heads)); cur = None; continue
        m = ART_RE.match(raw)
        if m:
            cur = {'no': int(m.group(2)), 'sub': int(m.group(3) or 0), 'label': m.group(1),
                   'title': (m.group(4) or '').strip(), 'chapter': chapter, 'lines': []}
            arts.append(cur); continue
        if raw.startswith('#'):
            if raw.startswith('# '):
                continue  # 법령명
            raise SystemExit('알 수 없는 제목 줄: ' + raw[:60])
        if cur is not None and raw.strip():
            cur['lines'].append(clean_line(raw))
    return {'meta': meta, 'articles': arts, 'buchik': buchik, 'body': body}


def buchik_block(buchik, gongpo_no):
    """부칙 목록에서 해당 공포번호(<제21719호,...>) 블록만 추출"""
    n = int(gongpo_no)
    start = None
    for i, l in enumerate(buchik):
        m = re.match(r'^부칙.*<제(\d+)호', l)
        if m:
            if start is not None:
                return buchik[start:i]
            if int(m.group(1)) == n:
                start = i
    return buchik[start:] if start is not None else []


def by_label(arts):
    return {a['label']: a for a in arts}


def for_label(amend, label):
    """부칙의 '다만 …제N조의 개정규정은 …' 단서가 이 조문을 언급하면 개정 전체의 시행일을 그대로 쓰지 않는다."""
    mention = re.compile(re.escape(label) + r'(?!\d|의\d)')  # '제13조'가 '제13조의2'에 걸리지 않게
    exc = any('다만' in l and mention.search(l) for l in amend['부칙'])
    a = dict(amend)
    if exc:
        a['시행일자'] = ''
        a['시행메모'] = '부칙 단서에 따라 이 조문의 시행일은 다릅니다. 아래 부칙 원문을 확인하세요.'
    return a


def build(entry):
    cur = parse(os.path.join(SRC, entry['current']))
    versions = [cur] + [parse(os.path.join(SRC, f)) for f in entry['upcoming']]
    cm = cur['meta']
    pending = {}   # label -> dict
    order = []
    for i in range(1, len(versions)):
        old, new = by_label(versions[i - 1]['articles']), by_label(versions[i]['articles'])
        nm = versions[i]['meta']
        amend = {'공포일자': nm['공포일자'], '공포번호': nm['공포번호'].lstrip('0'), '시행일자': nm['시행일자'],
                 '부칙': buchik_block(versions[i]['buchik'], nm['공포번호'])}
        for label, a in new.items():
            o = old.get(label)
            if o is None or o['lines'] != a['lines'] or o['title'] != a['title']:
                p = pending.setdefault(label, {'amendments': []})
                p.update({'label': label, 'title': a['title'], 'chapter': a['chapter'], 'lines': a['lines'], 'no': a['no'], 'sub': a['sub']})
                p['amendments'].append(for_label(amend, label))
                if label not in order: order.append(label)
        for label, o in old.items():
            if label not in new:
                p = pending.setdefault(label, {'amendments': []})
                p.update({'label': label, 'title': o['title'], 'chapter': o['chapter'], 'lines': [], 'removed': True, 'no': o['no'], 'sub': o['sub']})
                p['amendments'].append(for_label(amend, label))
                if label not in order: order.append(label)
    cur_labels = {a['label'] for a in cur['articles']}
    plist = []
    for label in sorted(order, key=lambda l: (pending[l]['no'], pending[l]['sub'])):
        p = pending[label]
        if label not in cur_labels:
            p['isNew'] = True
        for k in ('no', 'sub'):
            p.pop(k, None)
        plist.append(p)
    gk = cm.get('법령구분', '')
    data = {
        'name': cm['제목'],
        'meta': {'법령구분': gk, '공포일자': cm['공포일자'], '공포번호': cm['공포번호'].lstrip('0'), '시행일자': cm['시행일자'],
                 '소관부처': cm.get('소관부처', '교육부'), '출처': cm.get('출처', '')},
        'notes': NOTES.get(cm['제목'], ([BYEOLPYO] if gk in ('대통령령', '교육부령', '보건복지부령', '총리령') or cm['제목'].endswith(('시행령', '시행규칙')) else [])) + ([RESTORE_NOTE] if cm.get('복원처리') else []),
        'articles': [{k: a[k] for k in ('no', 'sub', 'label', 'title', 'chapter', 'lines')} for a in cur['articles']],
        'pending': plist,
    }
    return data, cur


def verify(data, cur):
    """원문 대조: 조문 수와 본문(공백 제거)이 마크다운 원문과 글자 단위로 일치하는지"""
    body = cur['body'].split('\n## 부칙')[0]
    n_heads = len(re.findall(r'^#####\s', body, re.M))
    assert n_heads == len(data['articles']), '조문 수 불일치 %d != %d' % (n_heads, len(data['articles']))
    labels = [a['label'] for a in data['articles']]
    assert len(set(labels)) == len(labels), '조문 라벨 중복'
    src = ''.join(l for l in body.split('\n') if not l.startswith('#'))
    src = re.sub(r'\*\*([①-⑳㉑-㉟]+)\*\*', r'\1', src)
    src = unescape(src)
    src = re.sub(r'\s+', '', src)
    out = re.sub(r'\s+', '', ''.join(''.join(a['lines']) for a in data['articles']))
    assert src == out, '본문 불일치 (원문 %d자 / 변환 %d자)' % (len(src), len(out))
    for a in data['articles']:
        for l in a['lines']:
            assert '**' not in l and '\\' not in l, '마크다운 잔여물: ' + l[:40]


def main():
    os.makedirs(OUT, exist_ok=True)
    index = {'generatedAt': datetime.date.today().isoformat(),
             'source': 'https://github.com/legalize-kr/legalize-kr (국가법령정보센터 OpenAPI 기반, 법령 원문은 공공저작물)',
             'laws': []}
    for e in LAWS:
        data, cur = build(e)
        verify(data, cur)
        raw = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        open(os.path.join(OUT, e['file']), 'w', encoding='utf-8').write(raw)
        rev = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:10]
        index['laws'].append({'name': data['name'], 'file': 'laws/' + e['file'], 'rev': rev,
                              'kind': data['meta']['법령구분'], '시행일자': data['meta']['시행일자'],
                              '공포번호': data['meta']['공포번호'], 'articles': len(data['articles']), 'pending': len(data['pending'])})
        print('%-28s 조문 %3d · 시행예정 %d · 시행 %s · %s제%s호 · rev %s' % (
            data['name'], len(data['articles']), len(data['pending']), data['meta']['시행일자'], data['meta']['법령구분'], data['meta']['공포번호'], rev))
    json.dump(index, open(os.path.join(ROOT, 'data', 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('검증 통과')


if __name__ == '__main__':
    main()
