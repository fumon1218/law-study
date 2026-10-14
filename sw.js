/* 앱 껍데기만 캐시합니다. 법령·학습 기록은 기기 localStorage에 있고 서버로 나가지 않습니다. */
const CACHE = 'law-study-v4';
const SHELL = ['./', 'index.html', 'style.css', 'core.js', 'app.js', 'manifest.webmanifest', 'icons/icon.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
/* 네트워크 우선(새 배포가 바로 반영), 오프라인이면 캐시 */
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET' || new URL(r.url).origin !== location.origin) return;
  e.respondWith(
    fetch(r).then(res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put(r, copy)); return res; })
      .catch(() => caches.match(r).then(m => m || caches.match('index.html')))
  );
});
