/**
 * Service worker: caches the app shell so the PWA opens offline.
 *
 * THE ONE RULE: never intercept api.github.com. Data caching belongs in
 * localStorage, where the app layer can do conflict resolution. A service
 * worker serving a cached API response would hand back a stale `sha` and
 * manufacture phantom 409 conflicts.
 *
 * Bump CACHE_VERSION whenever any file below changes -- the old cache is
 * deleted on activate.
 */

const CACHE_VERSION = '2026-09-16.2';
const CACHE_NAME = `atm-shell-${CACHE_VERSION}`;

const SHELL = [
  './',
  './index.html',
  './app.css',
  './manifest.webmanifest',
  './js/main.js',
  './js/ui.js',
  './js/store.js',
  './js/sync.js',
  './js/github.js',
  './js/merge.js',
  './js/i18n.js',
  './js/gestures.js',
  './icons/icon-180.png',
  './icons/icon-192.png',
  './icons/favicon-32.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
      .catch((error) => console.warn('SW install: precache failed', error)));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
  const request = event.request;

  if (request.method !== 'GET') return;                                  // never touch a PUT
  if (new URL(request.url).origin !== self.location.origin) return;      // never touch api.github.com

  if (request.mode === 'navigate') {
    // Network-first so a new deploy is picked up immediately; fall back to the
    // cached shell when offline.
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match('./index.html')));
    return;
  }

  // Cache-first for static assets.
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
      }
      return response;
    })));
});
