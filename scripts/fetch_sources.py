#!/usr/bin/env python3
"""legalize-kr 저장소 → data/source/*.md (현행 시행본 + 시행 예정본) 추출

사용: python3 scripts/fetch_sources.py [legalize-kr 클론 경로] [기준일 YYYY-MM-DD]

배경: legalize-kr 의 각 커밋은 '공포 시점 누적본'이라, 최신 커밋이 아직 시행 전 개정(시행일자 > 기준일)을
이미 포함하고 있을 수 있다. 그래서 파일별로
  1) 시행일자가 기준일보다 늦은 커밋(= 시행 전 개정)을 찾고,
  2) 최신 본문에서 그 개정분(직전 커밋과의 차이)만 3-way 병합으로 되돌려 '기준일 현재 시행 중 본문'을 복원하고,
  3) 되돌린 개정분을 시행일 순으로 다시 쌓아 시행 예정본으로 따로 저장한다.
시행 전 개정이 없으면 최신 커밋을 그대로 현행본으로 쓴다. 충돌이 나면 중단한다(수작업 확인 필요).
결과의 요약은 data/source/versions.json 에 기록된다.
"""
import json, os, re, subprocess, sys, tempfile, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'source')
REPO = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/legalize-kr/legalize-kr'
TODAY = sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat()

# 출력 키 → 저장소 내 경로 (특수교육법 3종은 이미 data/source 에 있어 대상에서 제외)
TARGETS = {
    'early-act': 'kr/유아교육법/법률.md',
    'early-decree': 'kr/유아교육법/시행령.md',
    'early-rule': 'kr/유아교육법/시행규칙.md',
    'school-act': 'kr/초ㆍ중등교육법/법률.md',
    'school-decree': 'kr/초ㆍ중등교육법/시행령.md',
    'school-rule': 'kr/초ㆍ중등교육법/시행규칙.md',
    'higher-act': 'kr/고등교육법/법률.md',
    'higher-decree': 'kr/고등교육법/시행령.md',
    'welfare-act': 'kr/장애인복지법/법률.md',
    'welfare-decree': 'kr/장애인복지법/시행령.md',
    'welfare-rule': 'kr/장애인복지법/시행규칙.md',
    'antidisc-act': 'kr/장애인차별금지및권리구제등에관한법률/법률.md',
    'antidisc-decree': 'kr/장애인차별금지및권리구제등에관한법률/시행령.md',
}
ONLY = os.environ.get('ONLY')


def git(*args, check=True):
    r = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', REPO] + list(args), capture_output=True, text=True, encoding='utf-8')
    if check and r.returncode != 0:
        raise SystemExit('git 실패: %s\n%s' % (' '.join(args), r.stderr))
    return r


def show(commit, path):
    return git('show', '%s:%s' % (commit, path)).stdout


def split(text):
    m = re.match(r'^(---\n.*?\n---\n)', text, re.S)
    return m.group(1), text[m.end():]


def meta_of(fm):
    d = {}
    for k in ('공포일자', '공포번호', '시행일자'):
        m = re.search(r'^%s:\s*(.*)$' % k, fm, re.M)
        d[k] = m.group(1).strip().strip("'") if m else ''
    return d


RESOLVED_ALL = []
RESOLVED = []  # 규칙으로 해결한 충돌 기록 (검토용)


def _annot(l):
    return re.sub(r'\s*<[^>]*>\s*$', '', l)


def resolve(ours, theirs):
    """겹친 변경을 두 가지 유형만 규칙으로 해결한다. 그 외는 None(수작업)."""
    # (1) 개정 이력 표기(<개정 …>)에 날짜만 더 붙은 같은 줄 → 이후 개정이 반영된 ours 유지
    if len(ours) == 1 and len(theirs) == 1 and _annot(ours[0]) == _annot(theirs[0]):
        return ours, '개정이력 표기 차이 → 최신 표기 유지'
    # (2) 호 목록: 첫 항목은 되돌리고(theirs), 뒤에 덧붙은 항목은 유지(ours)
    num = lambda l: re.match(r'^\s*(\d+)\\\.', l)
    if len(theirs) == 1 and len(ours) > 1 and num(theirs[0]) and num(ours[0]) and num(theirs[0]).group(1) == num(ours[0]).group(1) \
            and all(num(l) for l in ours[1:]):
        return theirs + ours[1:], '호 목록: 해당 호만 되돌리고 뒤에 덧붙은 호는 유지'
    return None, ''


def merge(ours, base, theirs):
    """ours 에 (base→theirs) 변경을 적용한다. 규칙으로 못 푸는 충돌이면 None."""
    with tempfile.TemporaryDirectory() as td:
        paths = []
        for n, t in (('o', ours), ('b', base), ('t', theirs)):
            p = os.path.join(td, n); open(p, 'w', encoding='utf-8').write(t); paths.append(p)
        r = subprocess.run(['git', 'merge-file', '-p', '-L', 'o', '-L', 'b', '-L', 't'] + paths, capture_output=True, text=True, encoding='utf-8')
        if r.returncode == 0:
            return r.stdout
        out, pos = [], 0
        for m in re.finditer(r'<<<<<<< o\n(.*?)=======\n(.*?)>>>>>>> t\n', r.stdout, re.S):
            out.append(r.stdout[pos:m.start()]); pos = m.end()
            res, why = resolve(m.group(1).rstrip('\n').split('\n'), m.group(2).rstrip('\n').split('\n'))
            if res is None:
                return None
            RESOLVED.append({'why': why, 'ours': m.group(1)[:200], 'theirs': m.group(2)[:200]})
            out.append('\n'.join(res) + '\n')
        out.append(r.stdout[pos:])
        txt = ''.join(out)
        return None if '<<<<<<<' in txt else txt


def split_buchik(body):
    """본문 → (부칙 앞 본문, [(공포번호, 블록 텍스트)]). 부칙은 공포번호별 블록으로 나눈다."""
    m = re.search(r'^## 부칙[^\n]*\n', body, re.M)
    if not m:
        return body, []
    main, rest = body[:m.start()], body[m.end():]
    blocks, cur = [], None
    for line in rest.split('\n'):
        h = re.match(r'^부칙.*<제(\d+)호', line)
        if h:
            cur = [int(h.group(1)), [line]]; blocks.append(cur)
        elif cur is not None:
            cur[1].append(line)
        elif line.strip():
            cur = [0, [line]]; blocks.append(cur)
    return main, [(n, '\n'.join(ls)) for n, ls in blocks]


def join_buchik(main, blocks):
    return main + ('\n## 부칙\n' + '\n'.join(t for _, t in blocks) + '\n' if blocks else '')


def norm(t):
    return re.sub(r'\s+', '', t)


def process(key, path):
    commits = git('log', '--format=%H', '-n', '40', '--', path).stdout.split()  # 최신 → 과거
    vers = []
    for c in commits:
        fm, body = split(show(c, path))
        main, blocks = split_buchik(body)
        vers.append({'c': c, 'fm': fm, 'body': main, 'blocks': blocks, **meta_of(fm)})
    pend_idx = [i for i, v in enumerate(vers) if v['시행일자'] > TODAY]
    info = {'path': path, '기준일': TODAY}
    if not pend_idx:
        cur = vers[0]
        open(os.path.join(SRC, key + '.current.md'), 'w', encoding='utf-8').write(cur['fm'] + join_buchik(cur['body'], cur['blocks']))
        info.update({'current': {'commit': cur['c'][:8], **{k: cur[k] for k in ('공포일자', '공포번호', '시행일자')}}, 'upcoming': [], 'restored': False})
        return info
    oldest = max(pend_idx)  # 가장 오래된 시행 전 개정
    if oldest + 1 >= len(vers):
        raise SystemExit(key + ': 이력이 부족해 직전 커밋이 없음')
    # 현행 메타 = 시행 전 개정이 아닌 커밋 중 가장 최신
    cur_i = min(i for i in range(len(vers)) if i not in pend_idx)
    # 시행 전 개정분을 최신 본문에서 되돌린다 (최신 → 과거 순)
    text = vers[0]['body']
    for i in sorted(pend_idx):
        text = merge(text, vers[i]['body'], vers[i + 1]['body'])
        if text is None:
            raise SystemExit('%s: %s 되돌리기 충돌 — 수작업 확인 필요' % (key, vers[i]['c'][:8]))
    pure = text
    pend_nos = {int(vers[i]['공포번호']) for i in pend_idx}
    pure_blocks = [b for b in vers[0]['blocks'] if b[0] not in pend_nos]
    restored = norm(join_buchik(pure, pure_blocks)) != norm(join_buchik(vers[cur_i]['body'], vers[cur_i]['blocks']))
    # 시행 예정본: 시행일 순(동일하면 공포 순)으로 다시 쌓는다
    order = sorted(pend_idx, key=lambda i: (vers[i]['시행일자'], -i))
    up, cum, out, cum_blocks = [], pure, [], list(pure_blocks)
    for n, i in enumerate(order, 1):
        cum = merge(cum, vers[i + 1]['body'], vers[i]['body'])
        if cum is None:
            raise SystemExit('%s: %s 다시 쌓기 충돌 — 수작업 확인 필요' % (key, vers[i]['c'][:8]))
        fm = vers[i]['fm']
        added = [b for b in vers[i]['blocks'] if b[0] == int(vers[i]['공포번호'])]
        cum_blocks = cum_blocks + [b for b in added if b not in cum_blocks]
        open(os.path.join(SRC, '%s.upcoming-%d.md' % (key, n)), 'w', encoding='utf-8').write(fm + join_buchik(cum, cum_blocks))
        out.append({'commit': vers[i]['c'][:8], **{k: vers[i][k] for k in ('공포일자', '공포번호', '시행일자')}})
    # 정합성: 모든 시행 전 개정을 다시 쌓으면 저장소 최신 본문과 같아야 한다
    assert norm(cum) == norm(vers[0]['body']), key + ': 복원본에 개정분을 다시 쌓은 결과가 최신 본문과 다름'
    fm = vers[cur_i]['fm']
    if restored:
        fm = fm[:-4] + '복원처리: 시행 전 개정분을 되돌려 현행 시행본으로 복원\n---\n'
    open(os.path.join(SRC, key + '.current.md'), 'w', encoding='utf-8').write(fm + join_buchik(pure, pure_blocks))
    info.update({'current': {'commit': vers[cur_i]['c'][:8], **{k: vers[cur_i][k] for k in ('공포일자', '공포번호', '시행일자')}},
                 'upcoming': out, 'restored': restored})
    return info


def main():
    res = {}
    for key, path in TARGETS.items():
        if ONLY and key not in ONLY.split(','):
            continue
        info = process(key, path)
        res[key] = info
        info['규칙병합'] = len(RESOLVED); RESOLVED_ALL.extend((key, r) for r in RESOLVED); RESOLVED.clear()
        c = info['current']
        print('%-16s 현행 %s 시행 %s 제%s호 | 예정 %s | 복원 %s' % (
            key, c['commit'], c['시행일자'], c['공포번호'], [(u['시행일자'], u['공포번호']) for u in info['upcoming']], info['restored']))
    for k, r in RESOLVED_ALL:
        print('  [규칙병합] %s: %s\n    ours  : %s\n    theirs: %s' % (k, r['why'], r['ours'].strip()[:160], r['theirs'].strip()[:160]))
    if not ONLY:
        json.dump({'repoHead': git('rev-parse', 'HEAD').stdout.strip()[:8], 'files': res},
                  open(os.path.join(SRC, 'versions.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
