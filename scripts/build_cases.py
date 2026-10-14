#!/usr/bin/env python3
"""legalize-kr/precedent-kr 마크다운 → 앱용 판례 JSON (data/source/cases/*.md → data/cases/*.json, index.json)

사용: python3 scripts/build_cases.py
- 판시사항·판결요지·참조조문·참조판례·판례내용을 원문 그대로 구조화한다 (요약·재작성 없음).
- tags 는 앱이 임의로 붙인 분류이며 판결 내용이 아니다 (TAGS 참조).
- 변환 후 원문 대조 검증(본문 글자 단위 일치)을 하고 어긋나면 비정상 종료한다.
"""
import hashlib, json, os, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'source', 'cases')
OUT = os.path.join(ROOT, 'data', 'cases')

# 판례일련번호 → 앱 분류 태그 (선별 기준: 특수교육·장애학생 교육·학교 관리자 책임·장애인 차별 쟁점)
TAGS = {
    '179163': ['학교 책임·안전', '장애학생 지도·학대'],   # 대법원 2015-08-27 2012다95134 (학교장·교사의 장애학생 보호감독의무)
    '225987': ['장애학생 지도·학대'],                  # 대법원 2020-01-16 2017도12742 (장애전담교사의 신체적 학대 판단 기준)
    '605769': ['학교 책임·안전'],                      # 대법원 2025-04-15 2024도20371 (장애아동 치료지원 중 사고)
    '179295': ['학교 책임·안전'],                      # 대구지법 포항지원 2015-09-25 2014가합1084 (장애학생 체육수업 중 사망, 학교안전공제)
    '190882': ['특수학교 설립'],                       # 대법원 2000-09-08 98두11854 (특수학교 설립계획 승인 재량)
    '120127': ['특수학교 설립'],                       # 서울지방법원 1996-02-21 96카합158 (특수학교 설립 공사방해 중지 가처분)
    '71053':  ['편의제공·차별', '고등교육'],            # 창원지법 2008-04-23 2007가단27413 (대학의 장애학생 배려의무)
    '219933': ['편의제공·차별'],                       # 대법원 2022-02-17 2019다217421 (정당한 편의제공 의무·적극적 조치)
    '609597': ['편의제공·차별'],                       # 대법원 2025-09-25 2024다207923 (일반 차별조항 포섭)
    '70483':  ['편의제공·차별'],                       # 대전지법 천안지원 2006-07-20 2005가합5440 (장애아동 보험인수 거부)
}
SECTIONS = ['판시사항', '판결요지', '참조조문', '참조판례', '판례내용']
LAW_KEYS = [  # 공백 제거 이름 → 표시 이름 (긴 이름 먼저)
    ('장애인등에대한특수교육법시행규칙', '장애인 등에 대한 특수교육법 시행규칙'),
    ('장애인등에대한특수교육법시행령', '장애인 등에 대한 특수교육법 시행령'),
    ('장애인등에대한특수교육법', '장애인 등에 대한 특수교육법'),
]
ART = r'제(\d+)조(?:의(\d+))?'


def parse_frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    meta = {}
    for line in m.group(1).split('\n'):
        k = re.match(r'^([^\s:-][^:]*):\s*(.*)$', line)
        if k and k.group(2) not in ('', '[]'):
            meta[k.group(1)] = k.group(2).strip().strip("'")
    return meta, text[m.end():]


def parse_sections(body):
    sec, cur = {}, None
    for raw in body.split('\n'):
        m = re.match(r'^## (.+)$', raw)
        if m and m.group(1).strip() in SECTIONS:
            cur = m.group(1).strip(); sec[cur] = []; continue
        if raw.startswith('# '):
            continue
        if cur is not None and raw.strip():
            sec[cur].append(raw.strip())
    return sec


def find_refs(lines):
    """참조조문에서 내장 법령(특수교육법 3종)의 인용을 법령 단위로 추출한다.
    인용 조문 번호는 판결 당시 기준이라 현행 조문과 다를 수 있으므로, 앱은 조문 단위로 연결하지 않고 법령 단위로만 연결한다."""
    text = re.sub(r'\s+', '', ''.join(lines))
    refs = {}
    for key, name in LAW_KEYS:
        for m in re.finditer(re.escape(key) + r'(?!시행)' + ART, text):
            chain = [(m.group(1), m.group(2))]
            pos = m.end()
            while True:
                n = re.match(r'(?:제\d+항)?(?:제\d+호)?[,·](?:' + ART + ')', text[pos:])
                if not n:
                    break
                chain.append((n.group(1), n.group(2))); pos += n.end()
            cited = refs.setdefault(name, [])
            for no, sub in chain:
                label = '제%s조%s' % (no, '의' + sub if sub else '')
                if label not in cited:
                    cited.append(label)
    return [{'law': k, 'cited': v} for k, v in refs.items()]


def norm(lines):
    return re.sub(r'\s+', '', ''.join(lines))


def main():
    os.makedirs(OUT, exist_ok=True)
    cases = []
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith('.md'):
            continue
        text = open(os.path.join(SRC, fn), encoding='utf-8').read()
        meta, body = parse_frontmatter(text)
        sec = parse_sections(body)
        seq = meta['판례일련번호']
        assert seq in TAGS or True
        # 원문 대조: 섹션별 본문을 모두 합친 글자가 원문(제목·섹션 머리말 제외)과 일치
        src_body = ''.join(l for l in body.split('\n') if not l.startswith('#'))
        assert norm([src_body]) == norm([l for s in SECTIONS for l in sec.get(s, [])]), seq + ' 본문 불일치'
        case = {
            'id': 'p' + seq, '판례일련번호': seq, '사건번호': meta['사건번호'], '사건명': meta['사건명'],
            '법원명': meta['법원명'], '선고일자': meta.get('선고일자', ''), '사건종류': meta['사건종류'],
            '출처': meta.get('출처', ''), 'tags': TAGS.get(seq, []),
        }
        for s in SECTIONS:
            case[s] = sec.get(s, [])
        case['refs'] = find_refs(case['참조조문'])
        cases.append(case)

    # 파일 저장: 목록(index)에는 본문 제외, 상세 파일에는 판례내용만
    index = {'generatedAt': datetime.date.today().isoformat(),
             'source': 'https://github.com/legalize-kr/precedent-kr (국가법령정보센터 OpenAPI 기반, 판례 원문은 공공저작물)',
             'tagNote': '분류 태그는 앱이 임의로 붙인 것이며 판결 내용이 아닙니다.', 'cases': []}
    for c in sorted(cases, key=lambda x: x['선고일자'], reverse=True):
        body = {'id': c['id'], '판례내용': c['판례내용']}
        raw = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
        open(os.path.join(OUT, c['id'] + '.json'), 'w', encoding='utf-8').write(raw)
        head = {k: v for k, v in c.items() if k != '판례내용'}
        head['file'] = 'cases/' + c['id'] + '.json'
        head['bodyChars'] = len(norm(c['판례내용']))
        index['cases'].append(head)
        print('%-8s %-12s %-14s %-12s refs=%s tags=%s' % (c['id'], c['법원명'][:8], c['사건번호'], c['선고일자'], [(r['law'][-6:], r['cited']) for r in c['refs']], c['tags']))
    index['rev'] = hashlib.sha1(json.dumps(index['cases'], ensure_ascii=False).encode()).hexdigest()[:10]
    json.dump(index, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('검증 통과: %d건' % len(cases))


if __name__ == '__main__':
    main()
