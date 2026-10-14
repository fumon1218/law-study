/* 법 공부 앱 — 순수 로직 (파서·빈칸 생성·간격 반복). DOM 비의존이라 node에서 테스트 가능 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.LawCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const BOX_DAYS = [0, 1, 3, 7, 14, 30, 60];

  /* ---------- 날짜 ---------- */
  function fmt(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function today() { return fmt(new Date()); }
  function addDays(ds, n) {
    const p = ds.split('-').map(Number);
    return fmt(new Date(p[0], p[1] - 1, p[2] + n));
  }

  /* ---------- 해시·난수 (조문마다 같은 빈칸이 나오도록) ---------- */
  function hash(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  /* ---------- 국가법령정보센터 원문 링크 ---------- */
  function lawUrl(name, label) {
    const base = 'https://www.law.go.kr/' + encodeURIComponent('법령') + '/' + encodeURIComponent(name.replace(/\s+/g, ''));
    return label ? base + '/' + encodeURIComponent(label) : base;
  }

  /* ---------- 원문 붙여넣기 → 조문 분해 ---------- */
  const ART_RE = /^제\s?(\d+)\s?조(?:\s?의\s?(\d+))?\s*(?:\(([^)]*)\))?\s*(.*)$/;
  const CHAP_RE = /^제\s?\d+\s?[장절편관](?:의\s?\d+)?\s+\S.*$/;
  const CONT_RE = /^(제|에|의|를|을|와|과|및|또는|부터|까지|에서|에 따라)/;

  function parseLaw(raw) {
    const lines = String(raw).replace(/\r/g, '').split('\n')
      .map(function (s) { return s.replace(/[ 　]/g, ' ').replace(/\s+/g, ' ').trim(); })
      .filter(Boolean);
    const arts = [], warnings = [];
    let chapter = '', cur = null, last = [0, 0];

    for (const line of lines) {
      if (arts.length && /^부\s?칙(\s|$|<|\()/.test(line)) break;
      if (CHAP_RE.test(line) && !/^제\s?\d+\s?조/.test(line)) { chapter = line; cur = null; continue; }

      const m = line.match(ART_RE);
      if (m) {
        const no = +m[1], sub = m[2] ? +m[2] : 0;
        const title = (m[3] || '').trim(), rest = (m[4] || '').trim();
        const looksRef = m[3] === undefined && CONT_RE.test(rest);
        const increasing = !arts.length || no > last[0] || (no === last[0] && sub > last[1]);
        if (!looksRef && increasing) {
          cur = {
            no: no, sub: sub,
            label: '제' + no + '조' + (sub ? '의' + sub : ''),
            title: title, lines: rest ? [rest] : [], chapter: chapter
          };
          arts.push(cur); last = [no, sub];
          continue;
        }
        if (!looksRef && !increasing) warnings.push('순서가 맞지 않는 줄을 앞 조문에 붙였습니다: ' + line.slice(0, 24));
      }
      if (cur) cur.lines.push(line);
    }

    /* 누락 의심 (삭제 조문도 원문에는 "삭제"로 남으므로 번호가 비면 복사 누락 가능성) */
    if (arts.length) {
      const seen = new Set(arts.filter(function (a) { return !a.sub; }).map(function (a) { return a.no; }));
      const missing = [];
      for (let n = arts[0].no; n <= arts[arts.length - 1].no; n++) if (!seen.has(n)) missing.push('제' + n + '조');
      if (missing.length) warnings.push('번호가 비어 있습니다(복사 누락 가능): ' + missing.slice(0, 12).join(', ') + (missing.length > 12 ? ' 외 ' + (missing.length - 12) + '건' : ''));
    }
    return { articles: arts, warnings: warnings };
  }

  function isDeleted(a) {
    return a.lines.length > 0 && a.lines.every(function (l) { return /^삭제/.test(l) || /^[<\[].*[>\]]$/.test(l); });
  }

  /* ---------- 빈칸 만들기 ---------- */
  const PART = /(으로서|으로써|에서는|에서|에게|으로|부터|까지|에는|에도|이라|라고|이며|하며|과의|와의|에의|에|의|은|는|을|를|과|와|도)$/;
  const VERB = /(한다|된다|있다|없다|이다|아니한다|하여야|하여서|하며|하고|하는|되는|받은|받는|있는|없는|같다|다만|그러하지|아니하다)$/;
  const STOP = new Set(['다음', '경우', '때에는', '이법', '및', '또는', '각', '해당', '관한', '대한', '따라', '위하여', '있어서', '따른', '관하여', '대하여', '다른', '같은', '사항', '내용', '이내', '이상', '이하', '이후', '이전', '날부터', '날까지', '때까지', '때부터', '이를', '그밖의', '그']);
  const NOUN_HAN = /(기한|제한|권한|상한|하한|시한|연한|한도)$/;

  function lineClass(l) {
    if (/^[①-⑳㉑-㉟]/.test(l)) return 'h';
    if (/^\d+(?:의\d+)?\./.test(l)) return 'ho';
    if (/^[가-힣]\./.test(l)) return 'mok';
    if (/^[<\[]/.test(l) && /[>\]]$/.test(l)) return 'note';
    return 'p';
  }

  function classify(tk) {
    const m = tk.t.match(/^([^\p{L}\p{N}]*)([\p{L}\p{N}][\p{L}\p{N}·ㆍ\-]*)([\s\S]*)$/u);
    tk.cand = false;
    if (!m) return;
    const lead = m[1], word = m[2], tail = m[3];
    if (!lead && /^\d+(?:의\d+)?$/.test(word) && /^\./.test(tail)) return; // "1." 같은 항목 번호
    let core = word, part = '';
    const pm = word.match(PART);
    if (pm && word.length - pm[0].length >= 2) { core = word.slice(0, word.length - pm[0].length); part = pm[0]; }
    tk.lead = lead; tk.core = core; tk.part = part; tk.tail = tail;
    const hasDigit = /[0-9]/.test(core);
    if (hasDigit) { tk.cand = core.length >= 2; tk.digit = tk.cand; return; }
    if (core.length < 2 || !/\p{Script=Hangul}/u.test(core)) return;
    if (STOP.has(core) || VERB.test(word)) return;
    if (/[한할된]$/.test(core) && !NOUN_HAN.test(core)) return;
    tk.cand = true;
  }

  function tokenize(line) {
    const out = [];
    let inNote = false;
    for (const p of line.split(/(\s+)/)) {
      if (p === '') continue;
      if (/^\s+$/.test(p)) { out.push({ t: p, sp: true }); continue; }
      if (!inNote && /^[<\[]/.test(p)) inNote = true;
      const tk = { t: p, sp: false, note: inNote };
      if (inNote && /[>\]][.,)]*$/.test(p)) inNote = false;
      if (!tk.note) classify(tk);
      out.push(tk);
    }
    return out;
  }

  /* level 0=빈칸 없음, 1=하, 2=중(숫자·기한 우선 가림), 3=상 */
  function makeBlanks(a, level, salt) {
    const rows = a.lines.map(function (l) { return { cls: lineClass(l), toks: tokenize(l) }; });
    const cands = [];
    rows.forEach(function (r, ri) {
      if (r.cls === 'note') return;
      r.toks.forEach(function (t, ti) { if (!t.sp && !t.note && t.cand) cands.push([ri, ti, !!t.digit]); });
    });
    const chosen = new Set();
    if (level > 0 && cands.length) {
      const ratio = [0, 0.2, 0.35, 0.55][level] || 0.35;
      const want = Math.max(1, Math.round(cands.length * ratio));
      if (level >= 2) cands.filter(function (c) { return c[2]; }).forEach(function (c) { chosen.add(c[0] + ',' + c[1]); });
      const rnd = mulberry32(hash(a.label + '|' + a.lines.length + '|' + level + '|' + (salt || 0)));
      const pool = cands.filter(function (c) { return !chosen.has(c[0] + ',' + c[1]); });
      for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(rnd() * (i + 1)); const tmp = pool[i]; pool[i] = pool[j]; pool[j] = tmp;
      }
      for (const c of pool) { if (chosen.size >= want) break; chosen.add(c[0] + ',' + c[1]); }
    }
    rows.forEach(function (r, ri) { r.toks.forEach(function (t, ti) { t.blank = chosen.has(ri + ',' + ti); }); });
    return rows;
  }

  /* ---------- 간격 반복 (라이트너 상자) g: 0 몰랐다 / 1 애매 / 2 알았다 ---------- */
  function nextState(s, g, t) {
    const st = Object.assign({ box: 0, lapses: 0, reps: 0, due: t }, s || {});
    let clearWrong = false;
    if (g === 0) { st.box = 1; st.lapses++; st.due = t; }
    else if (g === 1) { st.box = Math.max(1, st.box); st.due = addDays(t, Math.max(1, Math.floor(BOX_DAYS[st.box] / 2))); }
    else { st.box = Math.min(BOX_DAYS.length - 1, st.box + 1); st.due = addDays(t, BOX_DAYS[st.box]); clearWrong = st.box >= 3; }
    st.reps++;
    return { state: st, clearWrong: clearWrong };
  }

  return { BOX_DAYS: BOX_DAYS, today: today, addDays: addDays, hash: hash, lawUrl: lawUrl, parseLaw: parseLaw, isDeleted: isDeleted, makeBlanks: makeBlanks, tokenize: tokenize, nextState: nextState };
});
