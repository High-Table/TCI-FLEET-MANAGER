const CACHE = 'tci-fleet-v2';
const SHELL = ['./index.html', './config.js', './manifest.json', './icon.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  // Purane cache versions delete kar do
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Never cache Firebase API calls - always go to network for fresh data
  if (url.host.includes('firebaseio.com') || url.host.includes('identitytoolkit') || url.host.includes('securetoken')) return;

  // HTML/JS shell files: network-first, so updates apply immediately.
  // Falls back to cache only when offline.
  if (url.pathname.endsWith('index.html') || url.pathname.endsWith('config.js') || url.pathname === '/' || url.pathname.endsWith('/TCI-FLEET-MANAGER/')) {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          const resClone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, resClone));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Everything else (icons, manifest): cache-first is fine
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
