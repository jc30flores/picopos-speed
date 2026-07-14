const STATIC_CACHE = "gastroposv-static-v1";
const PWA_CACHE = "gastroposv-pwa-v1";
const APP_SHELL = ["/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(APP_SHELL))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => ![STATIC_CACHE, PWA_CACHE].includes(key)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

const isPwaPublicAsset = (url) =>
  url.pathname === "/api/public/manifest.webmanifest" ||
  url.pathname === "/api/public/pwa/metadata/" ||
  url.pathname.startsWith("/api/public/pwa/");

const isViteDevAsset = (url) =>
  url.pathname.startsWith("/src/") ||
  url.pathname.startsWith("/@") ||
  url.pathname.includes("__vite") ||
  url.searchParams.has("t");

const networkFirst = async (request, cacheName) => {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      cache.put(request, response.clone()).catch(() => undefined);
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
};

const cacheFirst = async (request, cacheName) => {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) {
    cache.put(request, response.clone()).catch(() => undefined);
  }
  return response;
};

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (isPwaPublicAsset(url)) {
    event.respondWith(networkFirst(request, PWA_CACHE));
    return;
  }

  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/media/")) {
    event.respondWith(fetch(request));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request, STATIC_CACHE));
    return;
  }

  if (isViteDevAsset(url)) {
    event.respondWith(fetch(request));
    return;
  }

  if (url.pathname.startsWith("/assets/") || ["script", "style", "font", "image"].includes(request.destination)) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
  }
});
