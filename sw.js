const CACHE_NAME = 'tasaves-v5';
const STATIC_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './tailwind.css',
  './abeja.png'
];
const CDN_CACHE = 'tasaves-cdn-v1';
const CDN_ASSETS = [
  'https://unpkg.com/lucide@latest',
  'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap',
  'https://fonts.gstatic.com/s/inter/v18/UcC73FwrK3iLTeHuS_fFQtVMgLB1v2g0b9DH.woff2'
];
const API_CACHE = 'tasaves-api-v1';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      await cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME && key !== CDN_CACHE && key !== API_CACHE).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

async function cacheCDNAsset(url) {
  const cache = await caches.open(CDN_CACHE);
  try {
    const response = await fetch(url);
    if (response.ok) cache.put(url, response.clone());
    return response;
  } catch {
    return cache.match(url);
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // API calls: network-first with cache fallback
  if (url.pathname === '/rates.json' || url.hostname === 've.dolarapi.com') {
    event.respondWith(
      fetch(request).then(async (response) => {
        if (response.ok) {
          const cache = await caches.open(API_CACHE);
          cache.put(request, response.clone());
        }
        return response;
      }).catch(async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        const fallback = await caches.match('./rates.json');
        return fallback || new Response(JSON.stringify({ error: 'offline' }), { status: 503, headers: { 'Content-Type': 'application/json' } });
      })
    );
    return;
  }

  // CDN assets: cache-first
  if (url.hostname === 'unpkg.com' || url.hostname === 'cdn.jsdelivr.net' || url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
    event.respondWith(
      caches.match(request).then(async (cached) => {
        if (cached) {
          cacheCDNAsset(request.url);
          return cached;
        }
        const response = await fetch(request);
        if (response.ok) {
          const cache = await caches.open(CDN_CACHE);
          cache.put(request, response.clone());
        }
        return response;
      })
    );
    return;
  }

  // Static assets: cache-first
  event.respondWith(
    caches.match(request).then((cached) => {
      const fetchPromise = fetch(request).then(async (response) => {
        if (response && response.ok) {
          const cache = await caches.open(CACHE_NAME);
          cache.put(request, response.clone());
        }
        return response;
      }).catch(() => cached);
      return cached || fetchPromise;
    }).catch(() => {
      return caches.match('./index.html');
    })
  );
});
