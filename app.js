/* 법 공부 앱 — 화면과 저장. 로직은 core.js (LawCore) */
(function () {
  'use strict';
  const C = window.LawCore;
  const LS_KEY = 'lawstudy:v1';
  const $ = (s, r) => (r || document).querySelector(s);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* ---------- 저장 ---------- */
  function defaults() {
    return { v: 1, laws: [], srs: {}, wrong: {}, notes: {}, procs: [], daily: { date: '', n: 0 }, settings: { level: 2, newPerDay: 10 } };
  }
  function load() {
    try {
      const s = JSON.parse(localStorage.getItem(LS_KEY));
      if (s && s.v === 1) { const d = defaults(); return Object.assign(d, s, { settings: Object.assign(d.settings, s.settings || {}) }); }
    } catch (e) { /* 손상 시 새로 시작 */ }
    return defaults();
  }
  let S = load();
  function save() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(S)); }
    catch (e) { toast('저장 공간이 부족합니다. 관리 탭에서 백업을 내보내 주세요.'); }
  }
  let toastTimer;
  function toast(msg) {
    const t = $('#toast'); t.textContent = msg; t.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 2600);
  }

  /* ---------- 상태 ---------- */
  const U = { view: 'home', lawId: null, label: null, q: '', sess: null, draft: null, quiz: null, loading: true };
  const getLaw = id => S.laws.find(l => l.id === id);
  const curLaw = () => getLaw(U.lawId) || S.laws[0] || null;
  const keyOf = (law, a) => law.id + '|' + a.label;
  function findByKey(k) {
    const i = k.indexOf('|'); const law = getLaw(k.slice(0, i));
    if (!law) return null;
    const a = law.articles.find(x => x.label === k.slice(i + 1));
    return a ? { law, a } : null;
  }
  function counts(law) {
    const t = C.today(); let total = 0, studied = 0, due = 0, fresh = 0, wrong = 0;
    for (const a of law.articles) {
      if (C.isDeleted(a)) continue;
      total++; const k = keyOf(law, a), s = S.srs[k];
      if (s) { studied++; if (s.due <= t) due++; } else fresh++;
      if (S.wrong[k]) wrong++;
    }
    const allow = Math.max(0, S.settings.newPerDay - (S.daily.date === t ? S.daily.n : 0));
    return { total, studied, due, fresh, wrong, newToday: Math.min(fresh, allow) };
  }

  /* ---------- 공통 렌더 ---------- */
  const NAV = [['home', '🏠', '홈'], ['browse', '📖', '조문'], ['study', '🧠', '암기'], ['procs', '🔁', '절차'], ['manage', '⚙️', '관리']];
  function renderNav() {
    $('#nav').innerHTML = NAV.map(n => `<button data-act="nav" data-v="${n[0]}" class="${U.view === n[0] ? 'on' : ''}"><span class="ic">${n[1]}</span>${n[2]}</button>`).join('');
  }
  const main = html => { $('#main').innerHTML = html; };
  const FOOT = '<p class="foot">※ 법령 본문은 국가법령정보센터 원문을 정리한 공개 데이터(또는 직접 붙여넣은 원문)입니다. 데이터 반영 시차가 있을 수 있으므로 업무 적용 전에는 각 조문의 「원문 보기」 링크로 현행 여부를 확인하세요. 앱이 만든 빈칸·퀴즈 등 가공 내용은 참고용입니다.</p>';
  function lawSelect(id) {
    if (S.laws.length < 2) return '';
    return `<select data-change="law" id="${id}" style="max-width:360px">${S.laws.map(l => `<option value="${l.id}" ${l.id === (curLaw() || {}).id ? 'selected' : ''}>${esc(l.name)}</option>`).join('')}</select>`;
  }
  function rowsHtml(rows) {
    return rows.map(r => '<p class="ln ' + r.cls + '">' + r.toks.map(t => {
      if (t.sp) return esc(t.t);
      if (t.blank) return esc(t.lead) + '<span class="blank" data-act="blank" tabindex="0" role="button">' + esc(t.core) + '</span>' + esc(t.part) + esc(t.tail);
      return esc(t.t);
    }).join('') + '</p>').join('');
  }
  const artBody = a => rowsHtml(C.makeBlanks(a, 0, 0));

  /* ---------- 홈 ---------- */
  function vHome() {
    if (!S.laws.length && U.loading) { main('<h1>특수교육법 학습</h1><section class="card empty"><h2>법령을 불러오는 중…</h2></section>'); return; }
    if (!S.laws.length) {
      main(`<h1>특수교육법 학습</h1>
      <section class="card empty"><h2>먼저 법령 원문을 가져오세요</h2>
      <p>국가법령정보센터에서 법령 본문을 복사해 붙여넣으면 조문별로 나뉘어 암기 카드가 됩니다.</p>
      <button class="btn pri" data-act="nav" data-v="manage">법령 가져오기</button></section>${FOOT}`);
      return;
    }
    const laws = S.laws.map(l => ({ l, c: counts(l) }));
    const sum = k => laws.reduce((n, x) => n + x.c[k], 0);
    main(`<h1>오늘의 학습</h1>
    <div class="grid g3">
      <div class="stat"><b>${sum('due')}</b><span>오늘 복습할 조문</span></div>
      <div class="stat"><b>${sum('newToday')}</b><span>오늘 새로 볼 조문</span></div>
      <div class="stat"><b>${sum('wrong')}</b><span>오답 노트</span></div>
      <div class="stat"><b>${sum('studied')}/${sum('total')}</b><span>학습한 조문</span></div>
    </div>
    <div class="row" style="margin:16px 0"><button class="btn pri" data-act="goStudy">🧠 암기 시작</button></div>
    ${laws.map(x => `<section class="card"><h2>${esc(x.l.name)}</h2>
      <div class="sub">기준일 ${esc(x.l.baseDate || '미입력')} · 조문 ${x.c.total}개 · 복습 ${x.c.due} · 오답 ${x.c.wrong}${x.l.pending && x.l.pending.length ? ' · 📅 시행 예정 개정 ' + x.l.pending.length + '건' : ''}</div>
      <div class="row" style="margin-top:10px"><button class="btn sm" data-act="openLaw" data-id="${x.l.id}">조문 보기</button>
      <a class="btn sm" href="${C.lawUrl(x.l.name)}" target="_blank" rel="noopener">원문 법령 ↗</a></div></section>`).join('')}${FOOT}`);
  }

  /* ---------- 조문 탐색 ---------- */
  function vBrowse() {
    const law = curLaw();
    if (!law) { vHome(); return; }
    U.lawId = law.id;
    main(`<div class="row" style="justify-content:space-between"><h1>${esc(law.name)}</h1>${lawSelect('lawSel')}</div>
    ${lawInfo(law)}
    <div class="split"><aside class="toc"><input id="q" placeholder="조문·키워드 검색" value="${esc(U.q)}"><div id="tocList"></div></aside>
    <section id="artView"></section></div>${FOOT}`);
    updateToc(); updateArt();
  }
  function lawInfo(law) {
    const m = law.meta;
    if (!m) return law.baseDate ? `<p class="sub">기준일 ${esc(law.baseDate)} (직접 붙여넣은 원문)</p>` : '';
    return `<p class="sub">현행(시행 중) · 시행 ${esc(m['시행일자'])} · ${esc(kindLabel(m))} · 공포 ${esc(m['공포일자'])}</p>`
      + (law.pending && law.pending.length ? `<div class="warnbox pend">📅 이미 공포되어 <b>시행을 앞둔 개정이 ${law.pending.length}개 조문</b>에 있습니다. 조문 목록 맨 아래 「시행 예정 개정」에서 확인하세요.</div>` : '')
      + (law.notes || []).map(n => `<div class="warnbox">ℹ ${esc(n)}</div>`).join('');
  }
  function pendHtml(p, law) {
    const am = p.amendments.map(x => `<div class="sub">공포 ${esc(x['공포일자'])} · ${esc(kindLabel({ '법령구분': (law.meta || {})['법령구분'], '공포번호': x['공포번호'] }))} · ${x['시행일자'] ? '시행 ' + esc(x['시행일자']) : esc(x['시행메모'] || '시행일은 부칙 참고')}</div>
      <details><summary class="sub">부칙 보기</summary>${x['부칙'].map(l => `<p class="ln note2">${esc(l)}</p>`).join('')}</details>`).join('');
    const body = p.removed ? '<p>이 조문은 삭제될 예정입니다.</p>' : rowsHtml(C.makeBlanks({ label: p.label, lines: p.lines }, 0, 0));
    return `<div class="pendbox"><b>📅 시행 예정 개정</b> <span class="sub">(아직 시행 전 · 현재는 위의 현행 조문이 적용됩니다)</span>${am}<h3>개정 후 본문</h3>${body}</div>`;
  }
  function updateToc() {
    const law = curLaw(); if (!law) return;
    const q = U.q.trim(); let chap = null, h = '';
    for (const a of law.articles) {
      if (q && !(a.label + a.title + a.lines.join(' ')).includes(q)) continue;
      if (a.chapter !== chap) { chap = a.chapter; if (chap) h += `<div class="chap">${esc(chap)}</div>`; }
      const k = keyOf(law, a), s = S.srs[k], t = C.today();
      h += `<button data-act="openArt" data-l="${esc(a.label)}" class="${U.label === a.label ? 'on' : ''} ${C.isDeleted(a) ? 'del' : ''}">${esc(a.label)}${a.title ? ' ' + esc(a.title) : ''}${a.changed ? '<span class="badge">개정</span>' : ''}${(law.pending || []).some(p => p.label === a.label) ? '<span class="badge pend">예정</span>' : ''}${S.wrong[k] ? '<span class="badge wr">오답</span>' : (s && s.due <= t ? '<span class="badge due">복습</span>' : '')}</button>`;
    }
    const pend = (law.pending || []).filter(p => !q || (p.label + p.title + p.lines.join(' ')).includes(q));
    if (pend.length) h += '<div class="chap">📅 시행 예정 개정</div>' + pend.map(p => `<button data-act="openArt" data-l="${esc(p.label)}" class="${U.label === p.label ? 'on' : ''}">${esc(p.label)}${p.title ? ' ' + esc(p.title) : ''}<span class="badge pend">${p.isNew ? '신설' : p.removed ? '삭제' : '개정'}</span></button>`).join('');
    $('#tocList').innerHTML = h || '<div class="empty sub">검색 결과가 없습니다</div>';
  }
  function updateArt() {
    const law = curLaw(), box = $('#artView'); if (!box || !law) return;
    const a0 = law.articles.find(x => x.label === U.label);
    const p = (law.pending || []).find(x => x.label === U.label);
    if (!a0 && !p) { box.innerHTML = '<div class="card empty">조문 목록에서 조문을 선택하세요.</div>'; return; }
    const a = a0 || { label: p.label, title: p.title, chapter: p.chapter, lines: [] };
    const k = keyOf(law, a);
    box.innerHTML = `<article class="card art"><h2>${esc(a.label)}${a.title ? '(' + esc(a.title) + ')' : ''}${a.changed ? `<span class="badge">개정 ${esc(a.changed)}</span>` : ''}</h2>
      <div class="sub">${esc(a.chapter || '')}</div>${a0 ? artBody(a) : '<p class="sub">현재 시행 중인 조문이 아닙니다. 아래 시행 예정 개정으로 신설됩니다.</p>'}${p ? pendHtml(p, law) : ''}
      <div class="row" style="margin-top:14px">
        <a class="btn sm" href="${C.lawUrl(law.name, a0 ? a.label : '')}" target="_blank" rel="noopener">원문 보기 ↗</a>
        ${(!a0 || C.isDeleted(a)) ? '' : `<button class="btn sm pri" data-act="studyOne" data-l="${esc(a.label)}">이 조문 암기</button>`}</div>
      <label for="memo">내 메모 (업무 시 주의점, 연상법 등)</label>
      <textarea id="memo" data-memo="${esc(k)}" style="min-height:100px">${esc(S.notes[k] || '')}</textarea></article>`;
  }

  /* ---------- 암기 ---------- */
  function buildQueue(law, mode) {
    const t = C.today(), due = [], fresh = [], wrong = [];
    for (const a of law.articles) {
      if (C.isDeleted(a)) continue;
      const k = keyOf(law, a), s = S.srs[k];
      if (S.wrong[k]) wrong.push(k);
      if (s) { if (s.due <= t) due.push(k); } else fresh.push(k);
    }
    due.sort((x, y) => S.srs[x].due.localeCompare(S.srs[y].due));
    const allow = Math.max(0, S.settings.newPerDay - (S.daily.date === t ? S.daily.n : 0));
    if (mode === 'wrong') return wrong;
    if (mode === 'fresh') return fresh.slice(0, 10);
    return due.concat(fresh.slice(0, allow));
  }
  function startSession(law, mode, keys) {
    const q = keys || buildQueue(law, mode);
    if (!q.length) { toast(mode === 'wrong' ? '오답 노트가 비어 있습니다' : '지금 학습할 조문이 없습니다'); return; }
    U.sess = { lawId: law.id, keys: q.slice(), i: 0, shown: false, re: {}, salt: Date.now() % 997, done: false, total: q.length };
    U.view = 'study'; render();
  }
  function vStudy() {
    const s = U.sess;
    if (s && s.done) {
      main(`<h1>수고하셨습니다</h1><section class="card empty"><h2>${s.total}개 조문 학습을 마쳤습니다</h2>
      <div class="row" style="justify-content:center"><button class="btn pri" data-act="endSess">학습 화면으로</button></div></section>`);
      return;
    }
    if (s) { vCard(); return; }
    const law = curLaw();
    if (!law) { vHome(); return; }
    U.lawId = law.id;
    const c = counts(law);
    main(`<div class="row" style="justify-content:space-between"><h1>암기</h1>${lawSelect('lawSel')}</div>
    <section class="card"><h2>${esc(law.name)}</h2>
      <div class="grid g3"><div class="stat"><b>${c.due}</b><span>복습 대상</span></div><div class="stat"><b>${c.newToday}</b><span>오늘 새 조문</span></div><div class="stat"><b>${c.wrong}</b><span>오답</span></div></div>
      <div class="row" style="margin-top:16px">
        <button class="btn pri" data-act="start" data-m="due">오늘 학습 시작</button>
        <button class="btn" data-act="start" data-m="fresh">새 조문 10개 더</button>
        <button class="btn" data-act="start" data-m="wrong">오답만 복습</button></div>
      <label>빈칸 난이도</label>
      <div class="row">${[1, 2, 3].map(n => `<button class="btn sm ${S.settings.level === n ? 'pri' : ''}" data-act="level" data-n="${n}">${['', '하', '중 (기한·숫자 우선)', '상'][n]}</button>`).join('')}</div>
      <p class="sub">틀린 조문은 같은 날 다시 나오고, 맞히면 1일 → 3일 → 7일 → 14일 간격으로 복습합니다.</p></section>${FOOT}`);
  }
  function vCard() {
    const s = U.sess, k = s.keys[s.i], f = findByKey(k);
    if (!f) { s.i++; if (s.i >= s.keys.length) s.done = true; render(); return; }
    const reps = S.srs[k] ? S.srs[k].reps : 0;
    const rows = C.makeBlanks(f.a, S.settings.level, s.salt + reps);
    const pct = Math.round(s.i / s.keys.length * 100);
    main(`<div class="progress"><i style="width:${pct}%"></i></div>
    <div class="row" style="justify-content:space-between"><span class="sub">${s.i + 1} / ${s.keys.length} · ${esc(f.law.name)}</span><button class="btn sm" data-act="endSess">그만하기</button></div>
    <article class="card card-study"><h2>${esc(f.a.label)}${f.a.title ? '(' + esc(f.a.title) + ')' : ''}${f.a.changed ? '<span class="badge">개정됨</span>' : ''}</h2>
      ${rowsHtml(rows)}
      <div class="row" style="margin-top:14px"><button class="btn sm" data-act="revealAll">정답 모두 보기</button>
      <a class="btn sm" href="${C.lawUrl(f.law.name, f.a.label)}" target="_blank" rel="noopener">원문 ↗</a></div></article>
    <div id="grades" class="row" ${s.shown ? '' : 'hidden'}>
      <button class="btn bad" data-act="grade" data-g="0">몰랐다</button>
      <button class="btn warn" data-act="grade" data-g="1">애매</button>
      <button class="btn ok" data-act="grade" data-g="2">알았다</button></div>
    <p class="sub" id="hint" ${s.shown ? 'hidden' : ''}>빈칸을 눌러 하나씩 확인하거나, 「정답 모두 보기」 후 자기 평가를 해 주세요.</p>`);
  }
  function grade(g) {
    const s = U.sess, k = s.keys[s.i], isNew = !S.srs[k], t = C.today();
    const r = C.nextState(S.srs[k], g, t);
    S.srs[k] = r.state;
    if (g === 0) {
      S.wrong[k] = (S.wrong[k] || 0) + 1;
      if ((s.re[k] || 0) < 2) { s.re[k] = (s.re[k] || 0) + 1; s.keys.push(k); }
    } else if (r.clearWrong) delete S.wrong[k];
    if (isNew) { if (S.daily.date !== t) S.daily = { date: t, n: 0 }; S.daily.n++; }
    save(); s.i++; s.shown = false;
    if (s.i >= s.keys.length) s.done = true;
    render();
  }

  /* ---------- 절차 순서 퀴즈 ---------- */
  function shuffle(a) { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
  function vProcs() {
    const q = U.quiz;
    if (q) { vQuiz(); return; }
    main(`<h1>절차·순서 암기</h1>
    <p class="sub">선정·배치 절차처럼 순서와 기한이 중요한 흐름을 직접 입력해 두고 순서 맞히기로 외웁니다. 단계는 조문 원문을 보며 직접 적어 주세요.</p>
    ${S.procs.length ? S.procs.map((p, i) => `<section class="card"><h2>${esc(p.name)}</h2>
      <div class="sub">${p.steps.length}단계${p.ref ? ' · 근거: ' + esc(p.ref) : ''} · 정답 ${p.ok || 0}/${p.tries || 0}회</div>
      <div class="row" style="margin-top:10px"><button class="btn sm pri" data-act="quiz" data-i="${i}">순서 맞히기</button>
      <button class="btn sm" data-act="procDel" data-i="${i}">삭제</button></div></section>`).join('') : '<div class="card empty">등록된 절차가 없습니다.</div>'}
    <section class="card"><h2>새 절차 등록</h2>
      <label for="pn">절차 이름</label><input id="pn" placeholder="예: 특수교육대상자 선정·배치 절차">
      <label for="pr">근거 조문 (선택)</label><input id="pr" placeholder="예: 제15조~제17조">
      <label for="ps">단계 (한 줄에 한 단계, 순서대로)</label><textarea id="ps" placeholder="1단계 내용&#10;2단계 내용&#10;3단계 내용" style="min-height:130px"></textarea>
      <div class="row" style="margin-top:12px"><button class="btn pri" data-act="procAdd">저장</button></div></section>${FOOT}`);
  }
  function startQuiz(i) {
    const p = S.procs[i]; if (!p) return;
    let order = shuffle(p.steps.map((_, n) => n));
    if (order.length > 1 && order.every((v, n) => v === n)) order = order.reverse();
    U.quiz = { i, pool: order, ans: [], checked: false };
    render();
  }
  function vQuiz() {
    const q = U.quiz, p = S.procs[q.i];
    const left = q.pool.filter(n => !q.ans.includes(n));
    let body;
    if (q.checked) {
      body = `<ol class="ordered">${p.steps.map((st, n) => `<li><button class="chip ${q.ans[n] === n ? 'right' : 'wrong'}" disabled>${esc(st)}</button></li>`).join('')}</ol>
      <p>${q.ans.every((v, n) => v === n) ? '✅ 모두 맞았습니다.' : '❌ 위가 올바른 순서입니다. 다시 도전해 보세요.'}</p>
      <div class="row"><button class="btn pri" data-act="quiz" data-i="${q.i}">다시 풀기</button><button class="btn" data-act="quizEnd">목록으로</button></div>`;
    } else {
      body = `<h3>내가 고른 순서</h3><ol class="ordered">${q.ans.map(n => `<li><button class="chip picked" data-act="unpick" data-n="${n}">${esc(p.steps[n])}</button></li>`).join('')}</ol>
      <h3>남은 단계 (순서대로 눌러 주세요)</h3><div class="chips">${left.map(n => `<button class="chip" data-act="pick" data-n="${n}">${esc(p.steps[n])}</button>`).join('')}</div>
      <div class="row"><button class="btn pri" data-act="quizCheck" ${left.length ? 'disabled' : ''}>정답 확인</button><button class="btn" data-act="quizEnd">그만두기</button></div>`;
    }
    main(`<h1>${esc(p.name)}</h1><section class="card">${body}</section>`);
  }

  /* ---------- 관리 (가져오기·백업·설정) ---------- */
  function vManage() {
    const d = U.draft;
    main(`<h1>관리</h1>
    <section class="card"><h2>법령 가져오기</h2>
      <ol class="sub" style="padding-left:1.2em;margin-top:0"><li>국가법령정보센터(law.go.kr)에서 법령 페이지를 열고 본문 전체를 복사합니다.</li><li>아래에 붙여넣고 「분석」을 누르면 조문별로 나뉩니다. 부칙 앞까지만 읽습니다.</li><li>같은 이름으로 다시 붙여넣으면 개정된 조문만 표시되고 학습 기록은 유지됩니다.</li></ol>
      <label for="ln">법령 이름</label><input id="ln" placeholder="예: 장애인 등에 대한 특수교육법" value="${esc(d ? d.name : '')}">
      <label for="lb">기준일 (시행일)</label><input id="lb" placeholder="예: 2025-06-21" value="${esc(d ? d.baseDate : '')}">
      <label for="lt">본문</label><textarea id="lt" placeholder="제1조(목적) ...">${esc(d ? d.raw : '')}</textarea>
      <div class="row" style="margin-top:12px"><button class="btn pri" data-act="analyze">분석</button></div>
      ${d && d.parsed ? previewHtml(d) : ''}</section>
    <section class="card"><h2>저장된 법령</h2>${S.laws.length ? S.laws.map(l => `<div class="row" style="justify-content:space-between;margin:8px 0"><span>${esc(l.name)} <span class="sub">조문 ${l.articles.length} · 기준일 ${esc(l.baseDate || '-')}</span></span>${l.builtin ? '<span class="sub">기본 제공</span>' : `<button class="btn sm" data-act="lawDel" data-id="${l.id}">삭제</button>`}</div>`).join('') : '<p class="sub">아직 없습니다.</p>'}
      <div class="row" style="margin-top:10px"><button class="btn sm" data-act="resync">내장 법령 다시 불러오기</button></div>
      <p class="sub">기본 제공 법령은 국가법령정보센터 원문을 정리한 공개 데이터(legalize-kr)입니다. 앱을 열 때 새 버전이 있으면 자동으로 반영되고, 바뀐 조문은 「개정」 표시와 함께 복습 대상으로 돌아옵니다.</p></section>
    <section class="card"><h2>학습 설정</h2>
      <label for="np">하루 새 조문 수</label><select id="np" data-change="newPer">${[5, 10, 15, 20, 30].map(n => `<option ${S.settings.newPerDay === n ? 'selected' : ''}>${n}</option>`).join('')}</select></section>
    <section class="card"><h2>백업</h2><p class="sub">학습 기록은 이 기기의 브라우저에만 저장됩니다. 기기를 바꾸거나 브라우저 데이터를 지우기 전에 내보내기 해 두세요.</p>
      <div class="row"><button class="btn" data-act="export">내보내기 (JSON)</button><label class="btn" style="margin:0">가져오기<input type="file" accept=".json,application/json" data-change="import" hidden></label></div></section>${FOOT}`);
  }
  function previewHtml(d) {
    const p = d.parsed, n = p.articles.length;
    if (!n) return '<div class="warnbox">조문을 찾지 못했습니다. 「제1조(목적)」처럼 조 번호로 시작하는 줄이 있는지 확인해 주세요.</div>';
    const del = p.articles.filter(C.isDeleted).length;
    return `<div class="card" style="margin-top:14px"><b>조문 ${n}개를 찾았습니다</b> <span class="sub">(삭제 조문 ${del}개는 암기에서 제외)</span>
      <div class="sub">처음: ${esc(p.articles[0].label)} ${esc(p.articles[0].title)} · 마지막: ${esc(p.articles[n - 1].label)} ${esc(p.articles[n - 1].title)}</div>
      ${p.warnings.map(w => `<div class="warnbox">⚠ ${esc(w)}</div>`).join('')}
      ${d.diff ? `<div class="warnbox">기존 저장본과 비교: 변경·신설 ${d.diff.changed.length}개${d.diff.changed.length ? ' (' + esc(d.diff.changed.slice(0, 8).join(', ')) + (d.diff.changed.length > 8 ? ' 외' : '') + ')' : ''}, 삭제됨 ${d.diff.removed}개</div>` : ''}
      <div class="row" style="margin-top:10px"><button class="btn ok" data-act="saveLaw">${d.diff ? '덮어쓰기 저장' : '저장'}</button></div></div>`;
  }
  function analyze() {
    const name = $('#ln').value.trim(), baseDate = $('#lb').value.trim(), raw = $('#lt').value;
    if (!name) { toast('법령 이름을 입력해 주세요'); return; }
    if (!raw.trim()) { toast('본문을 붙여넣어 주세요'); return; }
    const parsed = C.parseLaw(raw);
    const old = S.laws.find(l => l.id === lawId(name));
    let diff = null;
    if (old) {
      const m = new Map(old.articles.map(a => [a.label, a.lines.join('\n')]));
      const changed = [];
      for (const a of parsed.articles) { const o = m.get(a.label); if (o === undefined) changed.push(a.label + '(신설)'); else if (o !== a.lines.join('\n')) changed.push(a.label); }
      diff = { changed, removed: old.articles.filter(a => !parsed.articles.some(b => b.label === a.label)).length };
    }
    U.draft = { name, baseDate, raw, parsed, diff }; render();
  }
  const lawId = name => 'l' + C.hash(name.replace(/\s+/g, '')).toString(36);
  /* 법령 저장·갱신 공통: 같은 이름이면 학습 기록을 유지하고, 바뀐 조문만 '개정' 표시 + 복습 대상으로 되돌림 */
  function upsertLaw(base) {
    const id = lawId(base.name), old = getLaw(id), t = C.today();
    const oldMap = old ? new Map(old.articles.map(a => [a.label, a])) : null;
    let changed = 0;
    const arts = base.articles.map(a => {
      const x = Object.assign({}, a);
      if (oldMap) {
        const o = oldMap.get(a.label), k = id + '|' + a.label;
        if (!o) { x.changed = t; changed++; }
        else if (o.lines.join('\n') !== a.lines.join('\n')) { x.changed = t; changed++; if (S.srs[k]) S.srs[k].due = t; }
        else if (o.changed) x.changed = o.changed;
      }
      return x;
    });
    const law = Object.assign({}, base, { id, importedAt: t, articles: arts });
    if (old) S.laws[S.laws.indexOf(old)] = law; else S.laws.push(law);
    return { law, changed, isNew: !old };
  }
  function saveLaw() {
    const d = U.draft; if (!d || !d.parsed.articles.length) return;
    const r = upsertLaw({ name: d.name, baseDate: d.baseDate, articles: d.parsed.articles, custom: true });
    save(); U.draft = null; U.lawId = r.law.id; U.view = 'browse'; U.label = null; toast('저장했습니다'); render();
  }

  /* ---------- 내장 법령 (data/ 폴더) 자동 불러오기 ---------- */
  const kindLabel = m => (m['법령구분'] || '') + ' 제' + m['공포번호'] + '호';
  async function syncBuiltin(force) {
    let msg = '', touched = false;
    try {
      const r = await fetch('data/index.json', { cache: 'no-cache' });
      if (!r.ok) throw new Error('index');
      const idx = await r.json(), done = [];
      for (const e of idx.laws) {
        const old = getLaw(lawId(e.name));
        if (old && old.custom) continue;               // 직접 붙여넣은 법령은 덮어쓰지 않음
        if (old && old.rev === e.rev) continue;          // 같은 버전이면 건너뜀 (수동 확인 시에도 동일)
        const r2 = await fetch('data/' + e.file, { cache: 'no-cache' });
        if (!r2.ok) continue;
        const d = await r2.json();
        const res = upsertLaw({ name: d.name, baseDate: d.meta['시행일자'], articles: d.articles, meta: d.meta, pending: d.pending || [], notes: d.notes || [], builtin: true, rev: e.rev });
        done.push({ name: d.name, changed: res.changed, isNew: res.isNew });
      }
      if (done.length) {
        save(); touched = true;
        const upd = done.filter(x => !x.isNew && x.changed);
        msg = upd.length ? '법령 개정을 반영했습니다: ' + upd.map(x => x.name + ' ' + x.changed + '개 조문').join(', ') : '내장 법령 ' + done.length + '개를 불러왔습니다';
      } else if (force) msg = '이미 최신 상태입니다';
    } catch (err) { if (force) msg = '불러오지 못했습니다. 인터넷 연결을 확인하세요'; }
    const wasLoading = U.loading; U.loading = false;
    if (touched || wasLoading || force) render();
    if (msg) toast(msg);
  }

  /* ---------- 라우팅·이벤트 ---------- */
  function render() {
    renderNav();
    ({ home: vHome, browse: vBrowse, study: vStudy, procs: vProcs, manage: vManage }[U.view] || vHome)();
    window.scrollTo(0, 0);
  }
  const A = {
    nav: t => { U.view = t.dataset.v; if (U.view !== 'study') { /* 진행 중 세션은 유지 */ } render(); },
    goStudy: () => { U.view = 'study'; render(); },
    openLaw: t => { U.lawId = t.dataset.id; U.view = 'browse'; U.label = null; render(); },
    openArt: t => { U.label = t.dataset.l; updateToc(); updateArt(); if (window.innerWidth < 820) $('#artView').scrollIntoView({ behavior: 'smooth' }); },
    studyOne: t => { const law = curLaw(); startSession(law, 'one', [keyOf(law, law.articles.find(a => a.label === t.dataset.l))]); },
    start: t => startSession(curLaw(), t.dataset.m),
    level: t => { S.settings.level = +t.dataset.n; save(); render(); },
    blank: t => t.classList.toggle('open'),
    revealAll: () => { document.querySelectorAll('.blank').forEach(b => b.classList.add('open')); U.sess.shown = true; $('#grades').hidden = false; $('#hint').hidden = true; },
    grade: t => grade(+t.dataset.g),
    endSess: () => { U.sess = null; render(); },
    procAdd: () => {
      const name = $('#pn').value.trim(), steps = $('#ps').value.split('\n').map(s => s.trim()).filter(Boolean);
      if (!name || steps.length < 2) { toast('이름과 2단계 이상을 입력해 주세요'); return; }
      S.procs.push({ name, ref: $('#pr').value.trim(), steps, ok: 0, tries: 0 }); save(); render();
    },
    procDel: t => { if (confirm('이 절차를 삭제할까요?')) { S.procs.splice(+t.dataset.i, 1); save(); render(); } },
    quiz: t => startQuiz(+t.dataset.i),
    pick: t => { U.quiz.ans.push(+t.dataset.n); render(); },
    unpick: t => { U.quiz.ans = U.quiz.ans.filter(n => n !== +t.dataset.n); render(); },
    quizCheck: () => { const q = U.quiz, p = S.procs[q.i]; q.checked = true; p.tries = (p.tries || 0) + 1; if (q.ans.every((v, n) => v === n)) p.ok = (p.ok || 0) + 1; save(); render(); },
    quizEnd: () => { U.quiz = null; render(); },
    analyze, saveLaw,
    resync: () => syncBuiltin(true),
    lawDel: t => {
      const law = getLaw(t.dataset.id);
      if (!law || !confirm('「' + law.name + '」과 이 법령의 학습 기록을 삭제할까요?')) return;
      S.laws = S.laws.filter(l => l.id !== law.id);
      Object.keys(S.srs).concat(Object.keys(S.wrong), Object.keys(S.notes)).forEach(k => { if (k.startsWith(law.id + '|')) { delete S.srs[k]; delete S.wrong[k]; delete S.notes[k]; } });
      if (U.lawId === law.id) U.lawId = null; save(); render();
    },
    export: () => {
      const blob = new Blob([JSON.stringify(S)], { type: 'application/json' }), a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = 'law-study-backup-' + C.today() + '.json'; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    }
  };
  document.addEventListener('click', e => { const t = e.target.closest('[data-act]'); if (t && A[t.dataset.act]) A[t.dataset.act](t, e); });
  document.addEventListener('keydown', e => { if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('blank')) { e.preventDefault(); e.target.classList.toggle('open'); } });
  let memoTimer;
  document.addEventListener('input', e => {
    if (e.target.id === 'q') { U.q = e.target.value; updateToc(); }
    if (e.target.dataset && e.target.dataset.memo) {
      const k = e.target.dataset.memo, v = e.target.value; clearTimeout(memoTimer);
      memoTimer = setTimeout(() => { if (v.trim()) S.notes[k] = v; else delete S.notes[k]; save(); }, 400);
    }
  });
  document.addEventListener('change', e => {
    const t = e.target, c = t.dataset && t.dataset.change; if (!c) return;
    if (c === 'law') { U.lawId = t.value; U.label = null; render(); }
    if (c === 'newPer') { S.settings.newPerDay = +t.value; save(); toast('저장했습니다'); }
    if (c === 'import' && t.files[0]) {
      const fr = new FileReader();
      fr.onload = () => {
        try {
          const d = JSON.parse(fr.result);
          if (!d || d.v !== 1 || !Array.isArray(d.laws)) throw new Error('형식');
          if (!confirm('현재 기기의 학습 기록을 이 백업으로 바꿉니다. 계속할까요?')) return;
          S = Object.assign(defaults(), d); save(); render(); toast('백업을 불러왔습니다');
        } catch (err) { toast('올바른 백업 파일이 아닙니다'); }
      };
      fr.readAsText(t.files[0]);
    }
  });

  if ('serviceWorker' in navigator && location.protocol.startsWith('http')) navigator.serviceWorker.register('sw.js').catch(() => {});
  render();
  syncBuiltin(false);
  window.__LS = { get S() { return S; }, U: U, render: render }; // 디버그용
})();
