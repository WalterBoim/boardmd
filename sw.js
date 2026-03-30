// BoardMD Service Worker v1.0
const CACHE_NAME = 'boardmd-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
];

// Install — cache static assets
self.addEventListener('install', event => {
  console.log('[SW] Installing BoardMD Service Worker');
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS).catch(err => {
        console.log('[SW] Cache addAll partial fail (ok):', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener('activate', event => {
  console.log('[SW] Activating BoardMD Service Worker');
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Fetch — network first, fall back to cache
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Skip non-GET and external requests (Supabase, Puter, Google Fonts etc)
  if (event.request.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;

  // For navigation requests (HTML pages) — network first, cache fallback
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // Cache the fresh page
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match('/index.html'))
    );
    return;
  }

  // For static assets — cache first
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        if (!response || response.status !== 200 || response.type === 'opaque') {
          return response;
        }
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return response;
      });
    })
  );
});

// Push notifications
self.addEventListener('push', event => {
  const data = event.data?.json() || {};
  const title = data.title || 'BoardMD';
  const options = {
    body: data.body || 'Time to review your cards!',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    tag: 'boardmd-reminder',
    renotify: true,
    data: { url: data.url || '/' },
    actions: [
      { action: 'study', title: '▶ Study Now' },
      { action: 'dismiss', title: 'Later' }
    ]
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Notification click
self.addEventListener('notificationclick', event => {
  event.notification.close();
  if (event.action === 'dismiss') return;
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const client of list) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow(event.notification.data?.url || '/');
    })
  );
});
