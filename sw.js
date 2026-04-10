// BoardMD Service Worker
const CACHE_NAME = 'boardmd-20260409';
const STATIC_ASSETS = ['/manifest.json','/icon-192.png','/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS).catch(()=>{})));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;
  if (event.request.mode === 'navigate' || url.pathname === '/' || url.pathname === '/index.html') {
    event.respondWith(fetch(event.request, { cache: 'no-store' }).catch(() => caches.match('/index.html')));
    return;
  }
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    if (!response || response.status !== 200 || response.type === 'opaque') return response;
    caches.open(CACHE_NAME).then(cache => cache.put(event.request, response.clone()));
    return response;
  })));
});
self.addEventListener('push', event => {
  const data = event.data?.json() || {};
  event.waitUntil(self.registration.showNotification(data.title || 'BoardMD', {
    body: data.body || 'Time to review your cards!',
    icon: '/icon-192.png', badge: '/icon-192.png',
    tag: 'boardmd-reminder', renotify: true,
    data: { url: data.url || '/' },
    actions: [{ action: 'study', title: 'Study Now' }, { action: 'dismiss', title: 'Later' }]
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  if (event.action === 'dismiss') return;
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    for (const c of list) { if (c.url.includes(self.location.origin) && 'focus' in c) return c.focus(); }
    return clients.openWindow(event.notification.data?.url || '/');
  }));
});
