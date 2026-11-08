/* Divar Filing Workspace PWA — security-first service worker
 * Scope: /workspace/ only (served from /workspace/sw.js)
 *
 * Policy:
 * - Never cache authenticated workspace HTML or API/CRM responses
 * - Never cache POST/PUT/PATCH/DELETE
 * - Never touch /payment/, /accounts/, /api/, /products/, /admin/
 * - Offline: show generic offline page (no personal data)
 * - Static assets stay on browser/HTTP cache (/static/ is outside SW scope by design)
 */
/* eslint-disable no-restricted-globals */
'use strict';

var CACHE_VERSION = '__WS_PWA_CACHE_VERSION__';
var OFFLINE_CACHE = CACHE_VERSION + '-offline';
var OFFLINE_URL = '__WS_PWA_OFFLINE_URL__';

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(OFFLINE_CACHE).then(function (cache) {
      return cache.add(OFFLINE_URL);
    })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.map(function (key) {
          if (key.indexOf('ws-pwa-') === 0 && key.indexOf(CACHE_VERSION) !== 0) {
            return caches.delete(key);
          }
          return undefined;
        })
      );
    }).then(function () {
      return self.clients.claim();
    })
  );
});

self.addEventListener('message', function (event) {
  var data = event.data || {};
  if (data && data.type === 'WS_PWA_SKIP_WAITING') {
    self.skipWaiting();
  }
});

function isMutatingMethod(method) {
  var m = (method || 'GET').toUpperCase();
  return m !== 'GET' && m !== 'HEAD';
}

function isWorkspaceNavigation(request, url) {
  if (request.mode !== 'navigate') return false;
  return url.pathname === '/workspace' || url.pathname.indexOf('/workspace/') === 0;
}

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (!request) return;

  var url;
  try {
    url = new URL(request.url);
  } catch (e) {
    return;
  }

  if (url.origin !== self.location.origin) return;

  // Mutating methods: never intercept (browser handles; nothing enters Cache Storage).
  if (isMutatingMethod(request.method)) return;

  // Only special-case navigations inside /workspace/ for offline messaging.
  // All other same-scope GETs (including /workspace/api/*) stay network-only
  // by not calling respondWith — no Cache Storage involvement.
  if (!isWorkspaceNavigation(request, url)) return;

  event.respondWith(
    fetch(request).catch(function () {
      return caches.open(OFFLINE_CACHE).then(function (cache) {
        return cache.match(OFFLINE_URL).then(function (cached) {
          if (cached) return cached;
          return new Response(
            '<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">' +
              '<meta name="viewport" content="width=device-width,initial-scale=1">' +
              '<title>قطع اتصال</title></head><body style="font-family:Tahoma,sans-serif;padding:2rem;text-align:center">' +
              '<h1>اتصال اینترنت برقرار نیست</h1>' +
              '<p>میزکار برای نمایش داده‌های به‌روز به اینترنت نیاز دارد.</p>' +
              '<button onclick="location.reload()">تلاش مجدد</button></body></html>',
            {
              status: 503,
              statusText: 'Offline',
              headers: { 'Content-Type': 'text/html; charset=utf-8' },
            }
          );
        });
      });
    })
  );
});
