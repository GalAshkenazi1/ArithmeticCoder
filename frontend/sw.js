// Service worker: lets the showcase be installed ("Add to Home Screen") and open without a network.
// Pages, scripts and styles come from the network first (always fresh), and from the cache only
// when offline. The API (/api/*) is never cached: encoding needs the server.

const CACHE = "arith-v1";
const CORE = ["./", "encode.html", "compare.html", "encoders.html", "css/app.css", "manifest.webmanifest",
  "icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  event.respondWith(fetch(event.request)
    .then((response) => {
      if (response.ok) {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(event.request, copy));
      }
      return response;
    })
    .catch(() => caches.match(event.request).then((hit) => hit ?? caches.match("./"))));
});
