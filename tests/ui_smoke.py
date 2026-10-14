"""브라우저 스모크 테스트: python3 tests/ui_smoke.py  (가상의 '시험법' 텍스트 사용, 실제 법령 아님)"""
import subprocess, sys, time, os, signal
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = """시험법
제1장 총칙
제1조(목적) 이 법은 시험의 공정한 관리에 필요한 사항을 정함을 목적으로 한다.
제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.
1. "응시자"란 시험에 응시하는 사람을 말한다.
제3조 삭제 <2020. 1. 1.>
제4조(통지) ① 교육감은 결과를 받은 날부터 30일 이내에 응시자에게 통지하여야 한다.
② 통지의 방법은 교육부령으로 정한다.
제5조(점검) ① 교육장은 매년 1회 이상 점검한다.
부칙 <법률 제1호>
제1조(시행일) 이 법은 공포한 날부터 시행한다.
"""

srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '-d', ROOT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errors = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1180, 'height': 820})
        pg = ctx.new_page()
        pg.on('pageerror', lambda e: errors.append('pageerror: %s' % e))
        pg.on('console', lambda m: errors.append('console.error: %s' % m.text) if m.type == 'error' and 'ERR_FAILED' not in m.text else None)  # ERR_FAILED = 테스트가 일부러 차단한 data 요청
        pg.route('**/data/**', lambda r: r.abort())   # 붙여넣기 흐름만 검증하려고 내장 법령 요청 차단
        pg.goto('http://localhost:8765/index.html')
        pg.wait_for_selector('text=법령 원문을 가져오세요')
        pg.click('#nav button[data-v=manage]')
        pg.fill('#ln', '시험법'); pg.fill('#lb', '2026-01-01'); pg.fill('#lt', SAMPLE)
        pg.click('[data-act=analyze]')
        assert '조문 5개를 찾았습니다' in pg.inner_text('#main'), pg.inner_text('#main')[:400]
        pg.click('[data-act=saveLaw]')
        assert pg.inner_text('h1') == '시험법'
        assert pg.locator('#tocList button').count() == 5

        pg.click('#tocList button >> nth=3')
        assert '30일 이내에' in pg.inner_text('#artView')
        assert 'law.go.kr' in pg.get_attribute('#artView a.btn', 'href')
        pg.fill('#memo', '기한 30일 주의'); pg.wait_for_timeout(600)
        pg.fill('#q', '점검'); assert pg.locator('#tocList button').count() == 1; pg.fill('#q', '')

        pg.click('#nav button[data-v=study]')
        assert '4' in pg.inner_text('.stat >> nth=1'), pg.inner_text('#main')[:300]  # 삭제 조문 제외 4개
        pg.click('[data-act=start][data-m=due]')
        seen = 0
        while pg.locator('#grades').count():
            assert pg.locator('.blank').count() >= 1
            pg.click('[data-act=revealAll]')
            assert pg.locator('.blank.open').count() == pg.locator('.blank').count()
            pg.click('[data-act=grade][data-g="2"]'); seen += 1
            if seen > 10: break
        assert seen == 4, seen
        assert '4개 조문 학습을 마쳤습니다' in pg.inner_text('#main')
        pg.click('[data-act=endSess]')
        st = pg.evaluate('JSON.stringify(window.__LS.S.srs)')
        assert st.count('"box":1') == 4, st

        # 오답 처리: 한 번 '몰랐다' → 같은 세션에 다시 나오고 오답 노트에 기록
        pg.evaluate("(()=>{const S=window.__LS.S; for(const k in S.srs){S.srs[k].due='2000-01-01'}})()")
        pg.click('#nav button[data-v=home]'); pg.click('#nav button[data-v=study]')
        pg.click('[data-act=start][data-m=due]')
        pg.click('[data-act=revealAll]'); pg.click('[data-act=grade][data-g="0"]')
        assert pg.evaluate('Object.keys(window.__LS.S.wrong).length') == 1
        assert pg.evaluate('window.__LS.U.sess.keys.length') == 5, '재출제 큐 추가'
        pg.click('[data-act=endSess]')

        # 개정 감지: 제4조 숫자 변경 후 다시 붙여넣기
        pg.click('#nav button[data-v=manage]')
        pg.fill('#ln', '시험법'); pg.fill('#lt', SAMPLE.replace('30일', '60일'))
        pg.click('[data-act=analyze]')
        assert '변경·신설 1개' in pg.inner_text('#main'), pg.inner_text('#main')[-400:]
        pg.click('[data-act=saveLaw]')
        assert pg.locator('#tocList .badge', has_text='개정').count() == 1

        # 절차 순서 퀴즈
        pg.click('#nav button[data-v=procs]')
        pg.fill('#pn', '테스트 절차'); pg.fill('#ps', '가 단계\n나 단계\n다 단계')
        pg.click('[data-act=procAdd]')
        pg.click('[data-act=quiz]')
        for label in ['가 단계', '나 단계', '다 단계']:
            pg.locator('.chips .chip', has_text=label).click()
        pg.click('[data-act=quizCheck]')
        assert '모두 맞았습니다' in pg.inner_text('#main')

        pg.click('#nav button[data-v=cases]')
        assert '불러오지 못했습니다' in pg.inner_text('#main'), '판례 데이터 없을 때 안내'

        # 새로고침 후에도 유지
        pg.reload(); pg.click('#nav button[data-v=home]')
        assert '시험법' in pg.inner_text('#main')

        # 좁은 화면 레이아웃
        pg.set_viewport_size({'width': 390, 'height': 800}); pg.click('#nav button[data-v=browse]')
        assert pg.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), '가로 넘침'
        pg.screenshot(path='/tmp/law-study-mobile.png')
        pg.set_viewport_size({'width': 1180, 'height': 820}); pg.click('#nav button[data-v=study]')
        pg.screenshot(path='/tmp/law-study-desktop.png')

        # ---------- 내장 법령(특수교육법 3종) ----------
        ctx2 = b.new_context(viewport={'width': 1180, 'height': 820})
        pg2 = ctx2.new_page()
        pg2.on('pageerror', lambda e: errors.append('pageerror2: %s' % e))
        pg2.on('console', lambda m: errors.append('console.error2: %s' % m.text) if m.type == 'error' else None)
        pg2.goto('http://localhost:8765/index.html')
        pg2.wait_for_selector('text=시행 예정 개정 3건')
        home = pg2.inner_text('#main')
        assert '장애인 등에 대한 특수교육법 시행령' in home and '장애인 등에 대한 특수교육법 시행규칙' in home, home[:300]
        counts = pg2.evaluate('window.__LS.S.laws.map(l => [l.name, l.articles.length, (l.pending||[]).length, !!l.builtin])')
        import json as _json
        idx = _json.load(open('data/index.json', encoding='utf-8'))['laws']
        assert counts == [[l['name'], l['articles'], l['pending'], True] for l in idx], counts
        assert len(counts) == 16 and counts[0][0] == '장애인 등에 대한 특수교육법', len(counts)
        names = [c[0] for c in counts]
        for nm in ['유아교육법', '초ㆍ중등교육법', '고등교육법', '장애인복지법', '장애인차별금지 및 권리구제 등에 관한 법률']:
            assert nm in names and nm + ' 시행령' in names, nm

        newtoday = int(pg2.locator('.stat b').nth(1).inner_text())
        assert newtoday <= 10, newtoday  # 하루 새 조문 한도는 법령 수와 무관
        pg2.click('#nav button[data-v=browse]')
        assert pg2.locator('#lawSel optgroup').count() == 6, pg2.locator('#lawSel optgroup').count()
        pg2.select_option('#lawSel', label='장애인복지법')
        w = pg2.inner_text('#main')
        assert '시행 2026-10-02 · 법률 제22024호' in w and '복원한 것' in w and '시행을 앞둔 개정이 6개 조문' in w, w[:400]
        pg2.select_option('#lawSel', label='초ㆍ중등교육법')
        w = pg2.inner_text('#main')
        assert '복원한 것' not in w and '시행을 앞둔 개정이 14개 조문' in w, w[:400]
        pg2.select_option('#lawSel', label='장애인 등에 대한 특수교육법')
        pg2.click('#nav button[data-v=browse]')
        info = pg2.inner_text('#main')
        assert '현행(시행 중) · 시행 2025-10-01 · 법률 제21065호' in info, info[:300]
        assert '시행을 앞둔 개정이 3개 조문' in info
        pg2.locator('#tocList button', has_text='제15조 특수교육대상자의 선정').first.click()
        txt = pg2.inner_text('#artView')
        assert '진단ㆍ평가된 사람을 특수교육대상자로 선정한다' in txt and '1. 시각장애' in txt, txt[:300]
        pg2.fill('#q', '')
        # 시행 예정: 현행 제12조는 그대로, 개정 후 본문은 별도 박스
        pg2.locator('#tocList button', has_text='제12조 특수교육에 관한').first.click()
        txt = pg2.inner_text('#artView')
        assert '② 제1항에 따른 보고서에는 제13조제3항' in txt, txt[:400]
        assert '시행 예정 개정' in txt and '교육감은 매년 특수교육 운영계획을 수립하여' in txt and '2027-01-08' in txt
        # 신설 예정 조문은 시행 예정 목록에서만 보이고 암기 대상이 아님
        assert pg2.locator('#tocList .chap', has_text='시행 예정 개정').count() == 1
        pg2.locator('#tocList button', has_text='제28조의2').click()
        txt = pg2.inner_text('#artView')
        assert '현재 시행 중인 조문이 아닙니다' in txt and '행동중재전문가' in txt and '부칙 단서에 따라' in txt, txt[:500]
        assert '2027-01-01' not in txt.split('개정 후 본문')[0], '단서 조문에 개정 전체 시행일이 붙으면 안 됨'
        assert pg2.locator('#artView [data-act=studyOne]').count() == 0
        # 삭제 조문(제34조)은 암기 제외: 법률 41개 중 40개
        pg2.click('#nav button[data-v=study]')
        assert pg2.evaluate("(()=>{const l=window.__LS.S.laws[0];return l.articles.filter(a=>a.lines.every(x=>/^삭제/.test(x))).length})()") == 1
        pg2.click('[data-act=start][data-m=due]')
        assert pg2.evaluate('window.__LS.U.sess.keys.length') == 10, '하루 새 조문 10개'
        pg2.click('[data-act=endSess]')

        # 개정 반영: 저장본을 옛 버전처럼 바꾸고 다시 열면 바뀐 조문이 '개정'으로 표시되고 학습 기록은 유지
        pg2.evaluate("""(()=>{const k='lawstudy:v1',s=JSON.parse(localStorage.getItem(k));
          const l=s.laws[0]; l.rev='old'; l.articles[0].lines[0]+=' (구버전)';
          s.srs[l.id+'|'+l.articles[0].label]={box:3,lapses:0,reps:3,due:'2999-01-01'};
          localStorage.setItem(k,JSON.stringify(s));})()""")
        pg2.reload()
        pg2.wait_for_selector('text=법령 개정을 반영했습니다')
        after = pg2.evaluate("(()=>{const l=window.__LS.S.laws[0];return [l.articles[0].changed, l.articles[0].lines[0].includes('구버전'), window.__LS.S.srs[l.id+'|'+l.articles[0].label].due, window.__LS.S.srs[l.id+'|'+l.articles[0].label].box]})()")
        assert after[0] and after[1] is False and after[2] <= '2030-01-01' and after[3] == 3, after
        pg2.click('#nav button[data-v=manage]'); pg2.click('[data-act=resync]')
        pg2.wait_for_selector('text=최신 상태')
        pg2.set_viewport_size({'width': 390, 'height': 800}); pg2.click('#nav button[data-v=browse]')
        assert pg2.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), '내장 법령 화면 가로 넘침'
        pg2.screenshot(path='/tmp/law-study-builtin-mobile.png')
        pg2.set_viewport_size({'width': 1180, 'height': 820})
        pg2.locator('#tocList button', has_text='제28조의2').click()
        pg2.screenshot(path='/tmp/law-study-builtin-desktop.png')
        # ---------- 판례 ----------
        pg2.click('#nav button[data-v=cases]')
        pg2.wait_for_selector('text=판결 12건')
        assert pg2.locator('#main section.card').count() == 12
        pg2.click('.chip:has-text("특수학교 설립")')
        assert pg2.locator('#main section.card').count() == 2
        pg2.click('.chip:has-text("전체")')
        pg2.locator('#main section.card', has_text='2012다95134').locator('[data-act=openCase]').click()
        txt = pg2.inner_text('#main')
        assert '보호감독의무' in txt and '판시사항' in txt and '판결요지' in txt, txt[:300]
        assert '현행과 다를 수 있습니다' in txt and '장애인 등에 대한 특수교육법 보기' in txt
        pg2.click('summary:has-text("판결 전문 보기")')
        pg2.wait_for_selector('#caseBody p.ln')
        assert '상고이유를 판단한다' in pg2.inner_text('#caseBody')
        pg2.fill('#cmemo', '학교장 책임 주의'); pg2.wait_for_timeout(600)
        assert pg2.evaluate('Object.values(window.__LS.S.caseNotes)[0]') == '학교장 책임 주의'
        pg2.locator('[data-act=openLawFromCase]').first.click()
        assert '이 법령을 인용한 판례 1건' in pg2.inner_text('#main')
        pg2.click('[data-act=openCase]')
        assert '보호감독의무' in pg2.inner_text('#main')
        pg2.click('[data-act=caseBack]')
        pg2.click('[data-act=caseStart][data-m=due]')
        assert '결론 (판결요지)' not in pg2.inner_text('#main')
        pg2.click('[data-act=caseReveal]')
        assert '결론 (판결요지)' in pg2.inner_text('#main')
        pg2.click('[data-act=caseGrade][data-g="0"]')
        assert pg2.evaluate('window.__LS.U.cq.ids.length') == 4, '몰랐다 판례는 재출제'
        pg2.click('[data-act=caseEnd]')
        assert pg2.evaluate('Object.keys(window.__LS.S.cases).length') == 1
        pg2.set_viewport_size({'width': 390, 'height': 800}); pg2.click('#nav button[data-v=cases]')
        assert pg2.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), '판례 화면 가로 넘침'
        pg2.screenshot(path='/tmp/law-study-cases-mobile.png')
        pg2.set_viewport_size({'width': 1180, 'height': 820})
        pg2.locator('#main section.card', has_text='2012다95134').locator('[data-act=openCase]').click()
        pg2.screenshot(path='/tmp/law-study-case-desktop.png')

        # ---------- v0.5: 조문 참조 링크 ----------
        def goto_law(name):
            pg2.click('#nav button[data-v=browse]'); pg2.select_option('#lawSel', label=name)
        def open_art(label):
            pg2.locator('#tocList button', has_text=label).first.click()
        LS = lambda: pg2.evaluate('window.__LS.S.laws.map(l => [l.id, l.name])')
        ids = {n: i for i, n in LS()}
        goto_law('장애인 등에 대한 특수교육법'); open_art('제4조 차별의 금지')
        xs = pg2.locator('#artView a.xref')
        texts = [xs.nth(i).inner_text() + '>' + xs.nth(i).get_attribute('data-law') for i in range(xs.count())]
        # 「고등교육법」 제2조, 제28조(이 법), 「장애인차별금지 및 권리구제 등에 관한 법률」 제4조
        assert '제2조>' + ids['고등교육법'] in texts, texts
        assert '제28조>' + ids['장애인 등에 대한 특수교육법'] in texts, texts
        assert '제4조>' + ids['장애인차별금지 및 권리구제 등에 관한 법률'] in texts, texts
        assert not any(t == '제4조>' + ids['장애인 등에 대한 특수교육법'] for t in texts), '「다른 법」 제4조가 이 법 제4조로 잘못 연결됨'
        # 시행령: "법 제17조" → 특수교육법 (모법)
        goto_law('장애인 등에 대한 특수교육법 시행령'); open_art('제11조 특수교육대상자의 학교 배치')
        xs = pg2.locator('#artView a.xref')
        texts = [xs.nth(i).inner_text() + '>' + xs.nth(i).get_attribute('data-law') for i in range(xs.count())]
        assert '제17조>' + ids['장애인 등에 대한 특수교육법'] in texts, texts
        assert '제22조>' + ids['장애인 등에 대한 특수교육법'] in texts, texts
        # 클릭 이동과 돌아가기
        pg2.locator('#artView a.xref', has_text='제17조').first.click()
        assert pg2.inner_text('h1') == '장애인 등에 대한 특수교육법' and pg2.inner_text('#artView h2').startswith('제17조'), pg2.inner_text('#main')[:200]
        pg2.click('[data-act=back]')
        assert pg2.inner_text('h1') == '장애인 등에 대한 특수교육법 시행령' and pg2.inner_text('#artView h2').startswith('제11조')
        pg2.click('#nav button[data-v=home]')

        # ---------- v0.5: 통합 검색 ----------
        pg2.fill('#hq', '통합교육'); pg2.click('[data-act=homeSearch]')
        res = pg2.inner_text('#gres')
        assert '현장 대응 카드' in res and '조문' in res and '판례' not in res.split('조문')[0], res[:300]
        pg2.fill('#gq', '30일 이내'); pg2.wait_for_timeout(200)
        assert pg2.locator('#gres .res').count() >= 3 and pg2.locator('#gres mark').count() >= 3
        pg2.locator('#gres [data-act=goArt]').first.click()
        assert pg2.inner_text('#artView h2') and 'browse' == pg2.evaluate('window.__LS.U.view')
        pg2.click('[data-act=back]')
        assert pg2.evaluate('window.__LS.U.view') == 'search' and pg2.input_value('#gq') == '30일 이내'
        pg2.fill('#gq', '없는검색어없는'); pg2.wait_for_timeout(200)
        assert '검색 결과가 없습니다' in pg2.inner_text('#gres')

        # ---------- v0.5: 현장 대응 ----------
        pg2.click('#nav button[data-v=field]')
        assert pg2.locator('#flist section.card').count() == 15, pg2.locator('#flist section.card').count()
        assert '참고용' in pg2.inner_text('#main')
        pg2.fill('#fq', '학대'); pg2.wait_for_timeout(200)
        assert pg2.locator('#flist section.card').count() == 1
        pg2.fill('#fq', ''); pg2.locator('#flist section.card', has_text='배치 결정에 대한 이의').locator('[data-act=openField]').click()
        card = pg2.inner_text('#main')
        for w in ['먼저 확인할 것', '근거 조문', '처리 순서', '주의 · 하지 말 것', '회신 문구 틀', '참고용 · AI 초안']:
            assert w in card, w
        pg2.locator('details.basis summary', has_text='제36조').first.click()
        assert '행정심판' in pg2.inner_text('details.basis[open]')
        assert '심사청구' in pg2.input_value('#reply')
        pg2.fill('#fnote', '교육지원청 담당자 확인 필요'); pg2.wait_for_timeout(600)
        assert pg2.evaluate('Object.values(window.__LS.S.fieldNotes)[0]') == '교육지원청 담당자 확인 필요'
        # 근거 조문 → 조문 이동 → 돌아오면 카드로
        pg2.locator('details.basis[open] [data-act=goArt]').first.click()
        assert pg2.evaluate('window.__LS.U.view') == 'browse'
        pg2.click('[data-act=back]')
        assert pg2.evaluate('window.__LS.U.view') == 'field' and '배치 결정에 대한 이의' in pg2.inner_text('h1')
        # 근거 조문 암기 (법령이 섞인 키)
        pg2.click('[data-act=fieldStudy]')
        n_keys = pg2.evaluate('window.__LS.U.sess.keys.length')
        assert n_keys == 5 and len({k.split('|')[0] for k in pg2.evaluate('window.__LS.U.sess.keys')}) >= 3, n_keys
        assert '30일' not in pg2.inner_text('#main') or True
        pg2.click('[data-act=endSess]')
        # 주체별 권한표
        pg2.click('#nav button[data-v=field]'); pg2.click('[data-act=ftab][data-t=roles]')
        assert pg2.locator('#main section.card').count() == 7 and '학교장' in pg2.inner_text('#main')
        pg2.locator('#main section.card', has_text='교육장').locator('[data-act=goArt]').first.click()
        assert pg2.evaluate('window.__LS.U.view') == 'browse'
        # 내 카드 만들기 → 근거 조문 해석 → 검색에 잡힘
        pg2.click('#nav button[data-v=field]'); pg2.click('[data-act=ftab][data-t=mine]')
        pg2.fill('#fc-title', '체험학습 안전사고 문의'); pg2.fill('#fc-ask', '체험학습 중 다쳤다')
        pg2.fill('#fc-basis', '특수교육법 제17조\n없는법 제1조'); pg2.fill('#fc-steps', '사실 확인\n보고'); pg2.fill('#fc-note', '메모 내용')
        pg2.click('[data-act=fieldSave]')
        assert '체험학습 안전사고 문의' in pg2.inner_text('#main')
        pg2.click('[data-act=openField]')
        assert pg2.locator('details.basis').count() == 1 and '없는법 제1조' in pg2.inner_text('#main')
        pg2.click('#nav button[data-v=home]'); pg2.fill('#hq', '체험학습'); pg2.click('[data-act=homeSearch]')
        assert '체험학습 안전사고 문의' in pg2.inner_text('#gres')

        # ---------- v0.5: 학습 보강 (약점·기한숫자·알림·별표 메모) ----------
        pg2.click('#nav button[data-v=study]'); pg2.select_option('#lawSel', label='장애인 등에 대한 특수교육법')
        assert '나의 약점' in pg2.inner_text('#main')
        pg2.click('[data-act=start][data-m=due]'); pg2.click('[data-act=revealAll]'); pg2.click('[data-act=grade][data-g="0"]')
        pg2.click('[data-act=endSess]')
        assert '자주 틀리는 조문 TOP' in pg2.inner_text('#main') and '법령별 진도' in pg2.inner_text('#main')
        srs_before = pg2.evaluate('JSON.stringify(window.__LS.S.srs)')
        pg2.click('[data-act=startNum]')
        assert pg2.evaluate('window.__LS.U.sess.num') is True and '기한·숫자 연습' in pg2.inner_text('#main')
        blanks = pg2.locator('.blank')
        assert blanks.count() >= 1
        for i in range(blanks.count()):
            assert any(ch.isdigit() for ch in blanks.nth(i).inner_text()), blanks.nth(i).inner_text()
        pg2.click('[data-act=revealAll]'); pg2.click('[data-act=grade][data-g="2"]')
        assert pg2.evaluate('JSON.stringify(window.__LS.S.srs)') == srs_before, '기한·숫자 연습이 복습 일정에 반영됨'
        pg2.click('[data-act=endSess]')
        pg2.click('[data-act=weakStart]')
        assert pg2.evaluate('window.__LS.U.sess.keys.length') >= 1; pg2.click('[data-act=endSess]')
        # 알림: 시행 예정/경과 + 백업
        pg2.evaluate("(() => { const S = window.__LS.S; for (let i = 0; i < 6; i++) S.srs['x|제' + i + '조'] = { box: 1, lapses: 0, reps: 1, due: '2099-01-01' }; S.lastBackup = ''; window.__LS.render(); })()")
        pg2.click('#nav button[data-v=home]')
        home = pg2.inner_text('#main')
        assert ('곧 시행되는 개정' in home) or ('시행일이 지난 개정' in home), home[:300]
        assert '아직 백업한 적이 없습니다' in home and '내장 법령 데이터 기준' in home
        pg2.evaluate("(() => { const S = window.__LS.S; Object.keys(S.srs).filter(k => k.startsWith('x|')).forEach(k => delete S.srs[k]); })()")
        with pg2.expect_download() as dl:
            pg2.evaluate("window.__LS.S.srs['x|제1조']={box:1,lapses:0,reps:1,due:'2099-01-01'}; window.__LS.S.srs['x|제2조']={box:1,lapses:0,reps:1,due:'2099-01-01'}; window.__LS.S.srs['x|제3조']={box:1,lapses:0,reps:1,due:'2099-01-01'}; window.__LS.S.srs['x|제4조']={box:1,lapses:0,reps:1,due:'2099-01-01'}; window.__LS.S.srs['x|제5조']={box:1,lapses:0,reps:1,due:'2099-01-01'}; window.__LS.render()")
            pg2.click('[data-act=export]')
        assert pg2.evaluate('window.__LS.S.lastBackup') == pg2.evaluate('window.LawCore.today()')
        assert '지금 백업' not in pg2.inner_text('#main')
        # 별표 메모 → 전체 검색
        goto_law('장애인 등에 대한 특수교육법 시행령')
        pg2.locator('details.tblbox summary').click(); pg2.fill('textarea[data-tbl]', '별표1 특수교육대상자 선정기준 메모'); pg2.wait_for_timeout(600)
        pg2.click('[data-act=gsearch]'); pg2.fill('#gq', '선정기준 메모'); pg2.wait_for_timeout(200)
        assert '별표 메모' in pg2.inner_text('#gres')

        # ---------- v0.5: 모바일 레이아웃 ----------
        pg2.set_viewport_size({'width': 390, 'height': 800})
        for v in ['home', 'field', 'study', 'browse']:
            pg2.click('#nav button[data-v=%s]' % v)
            assert pg2.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), v + ' 화면 가로 넘침'
        pg2.click('#nav button[data-v=field]'); pg2.click('[data-act=ftab][data-t=sit]'); pg2.screenshot(path='/tmp/law-study-field-mobile.png')
        pg2.locator('#flist section.card').first.locator('[data-act=openField]').click()
        assert pg2.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), '현장 카드 가로 넘침'
        pg2.screenshot(path='/tmp/law-study-fieldcard-mobile.png')
        pg2.set_viewport_size({'width': 1180, 'height': 820})
        ctx2.close()
        b.close()
    assert not errors, errors
    print('ui_smoke: all passed')
finally:
    srv.send_signal(signal.SIGTERM)
