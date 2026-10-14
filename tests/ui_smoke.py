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
        assert counts == [['장애인 등에 대한 특수교육법', 41, 3, True], ['장애인 등에 대한 특수교육법 시행령', 41, 0, True], ['장애인 등에 대한 특수교육법 시행규칙', 11, 0, True]], counts

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
        pg2.wait_for_selector('text=판결 10건')
        assert pg2.locator('#main section.card').count() == 10
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
        pg2.click('[data-act=openLawFromCase]')
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
        ctx2.close()
        b.close()
    assert not errors, errors
    print('ui_smoke: all passed')
finally:
    srv.send_signal(signal.SIGTERM)
