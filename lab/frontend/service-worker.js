const CACHE = "the-lab-v11";
const ASSETS = [
  "/styles.css",
  "/app.js",
  "/login.js",
  "/manifest.webmanifest",
  "/icons/icon-192.svg",
  "/icons/icon-512.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.mode === "navigate") return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/repo/")) return;
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
