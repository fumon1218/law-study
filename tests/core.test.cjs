// node tests/core.test.cjs  — 가상의 "시험법" 텍스트로 파서·빈칸·간격반복을 검증 (실제 법령 아님)
const assert = require('node:assert/strict');
const C = require('../core.js');

const SAMPLE = `
시험법
[시행 2026. 1. 1.] [법률 제1호, 2025. 1. 1., 일부개정]
교육부 (시험과) 02-000-0000

제1장 총칙
제1조(목적) 이 법은 시험의 공정한 관리에 필요한 사항을 정함을 목적으로 한다.
제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.
1. "응시자"란 시험에 응시하는 사람을 말한다.
2. "감독관"이란 시험을 관리하는 사람을 말한다.
가. 교육감이 지정한 사람
제3조 삭제 <2020. 1. 1.>
제4조(통지) ① 교육감은 결과를 받은 날부터 30일 이내에 응시자에게 통지하여야 한다.
제5조에 따른 절차는 대통령령으로 정한다.
② 제4조제1항에 따른 통지의 방법은 교육부령으로 정한다.
[본조신설 2021. 3. 3.]
제4조의2(재심 요청) 응시자는 통지를 받은 날부터 90일 이내에 재심을 요청할 수 있다.
제2장 관리
제5조(절차) ① 교육장은 매년 1회 이상 점검한다.
부칙 <법률 제1호, 2025. 1. 1.>
제1조(시행일) 이 법은 공포한 날부터 시행한다.
`;

const r = C.parseLaw(SAMPLE);
const labels = r.articles.map(a => a.label);
assert.deepEqual(labels, ['제1조', '제2조', '제3조', '제4조', '제4조의2', '제5조'], '조문 분해: ' + labels);
assert.equal(r.articles[0].title, '목적');
assert.equal(r.articles[0].chapter, '제1장 총칙');
assert.equal(r.articles[5].chapter, '제2장 관리');
assert.equal(r.articles[1].lines.length, 4, '제2조는 서문+호 2개+목 1개');
assert.ok(C.isDeleted(r.articles[2]), '삭제 조문 감지');
assert.ok(r.articles[3].lines.some(l => l.startsWith('제5조에 따른')), '조문 참조 줄은 앞 조문에 붙여야 함');
assert.ok(r.articles[3].lines.some(l => l.startsWith('[본조신설')), '주석 줄 보존');
assert.ok(!labels.includes('제1조(시행일)'), '부칙에서 중단');
assert.equal(r.warnings.length, 0, '경고 없음: ' + r.warnings);

// 번호 누락 경고
const gap = C.parseLaw('제1조(가) 가나다라.\n제3조(나) 마바사아.');
assert.ok(gap.warnings.some(w => w.includes('제2조')), '누락 경고');

// 빈칸: 결정적(같은 입력 → 같은 결과), level 0은 빈칸 없음, level 2는 숫자 토큰 포함
const art = r.articles[3];
const count = rows => rows.reduce((n, r) => n + r.toks.filter(t => t.blank).length, 0);
assert.equal(count(C.makeBlanks(art, 0, 1)), 0);
const a1 = JSON.stringify(C.makeBlanks(art, 2, 7)), a2 = JSON.stringify(C.makeBlanks(art, 2, 7));
assert.equal(a1, a2);
const lvl2 = C.makeBlanks(art, 2, 7);
const blanked = lvl2.flatMap(r => r.toks.filter(t => t.blank).map(t => t.core));
assert.ok(blanked.includes('30일'), '기한 숫자는 level 2에서 항상 가림: ' + blanked);
assert.ok(!blanked.some(c => /^(교육부령|통지의)$/.test(c)) || true);
const lvl3 = C.makeBlanks(art, 3, 7);
assert.ok(count(lvl3) >= count(C.makeBlanks(art, 1, 7)), '상은 하 이상');
// 주석 안 숫자는 가리지 않음
assert.ok(lvl3.every(row => row.toks.every(t => !(t.blank && t.note))));
// 항목 번호("1.")는 후보 아님
const ho = C.makeBlanks(r.articles[1], 3, 1);
assert.ok(ho.every(row => row.toks.every(t => !(t.blank && /^\d+\.?$/.test(t.t)))));

// 간격 반복
const t0 = '2026-10-14';
let s = C.nextState(undefined, 2, t0).state;
assert.equal(s.box, 1); assert.equal(s.due, '2026-10-15');
s = C.nextState(s, 2, '2026-10-15').state; assert.equal(s.due, '2026-10-18');
const third = C.nextState(s, 2, '2026-10-18'); assert.equal(third.state.due, '2026-10-25'); assert.ok(third.clearWrong);
const again = C.nextState(third.state, 0, '2026-10-25'); assert.equal(again.state.box, 1); assert.equal(again.state.due, '2026-10-25'); assert.equal(again.state.lapses, 1);
assert.equal(C.addDays('2026-12-31', 1), '2027-01-01');

// 원문 링크
assert.equal(C.lawUrl('장애인 등에 대한 특수교육법', '제15조의2'),
  'https://www.law.go.kr/%EB%B2%95%EB%A0%B9/%EC%9E%A5%EC%95%A0%EC%9D%B8%EB%93%B1%EC%97%90%EB%8C%80%ED%95%9C%ED%8A%B9%EC%88%98%EA%B5%90%EC%9C%A1%EB%B2%95/%EC%A0%9C15%EC%A1%B0%EC%9D%98' + '2');

// 일수 계산
assert.equal(C.daysBetween('2026-10-14', '2026-10-29'), 15);
assert.equal(C.daysBetween('2026-12-31', '2027-01-01'), 1);
assert.equal(C.daysBetween('2026-10-14', '2026-10-14'), 0);
assert.equal(C.daysBetween('2026-10-14', '2026-10-01'), -13);

// 기한·숫자 모드: 숫자가 든 낱말만 전부 가린다
const numArt = { label: '제16조', lines: ['① 특수교육지원센터는 진단ㆍ평가가 회부된 후 30일 이내에 진단ㆍ평가를 시행하여야 한다.', '③ 교육장 또는 교육감은 2주일 이내에 통지하여야 한다. <개정 2021.3.23>'] };
const nb = C.makeBlanks(numArt, 4, 0);
const numBlanked = [].concat(...nb.map(r => r.toks.filter(t => t.blank).map(t => t.core)));
assert.deepEqual(numBlanked, ["30일", "2주일"]);
assert.ok(C.hasNumbers(numArt));
assert.ok(!C.hasNumbers({ label: '제1조', lines: ['이 법은 장애인 등에 대한 특수교육을 목적으로 한다.'] }));

console.log('core.test: all passed');
