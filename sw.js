const CACHE = 'tci-fleet-v1';
const SHELL = ['./index.html', './config.js', './manifest.json', './icon.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // Never cache Firebase API calls - always go to network for fresh data
  if (url.host.includes('firebaseio.com') || url.host.includes('identitytoolkit')) return;

  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
