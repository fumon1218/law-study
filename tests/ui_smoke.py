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
        pg.on('console', lambda m: errors.append('console.error: %s' % m.text) if m.type == 'error' else None)
        pg.goto('http://localhost:8765/index.html')

        assert '법령 원문을 가져오세요' in pg.inner_text('#main'), '빈 상태 안내'
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

        # 새로고침 후에도 유지
        pg.reload(); pg.click('#nav button[data-v=home]')
        assert '시험법' in pg.inner_text('#main')

        # 좁은 화면 레이아웃
        pg.set_viewport_size({'width': 390, 'height': 800}); pg.click('#nav button[data-v=browse]')
        assert pg.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), '가로 넘침'
        pg.screenshot(path='/tmp/law-study-mobile.png')
        pg.set_viewport_size({'width': 1180, 'height': 820}); pg.click('#nav button[data-v=study]')
        pg.screenshot(path='/tmp/law-study-desktop.png')
        b.close()
    assert not errors, errors
    print('ui_smoke: all passed')
finally:
    srv.send_signal(signal.SIGTERM)
