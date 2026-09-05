const CACHE_NAME = "openpool-shell-v6";
const SHELL = [
  "/static/tokens.css",
  "/static/app.css",
  "/static/app.js",
  "/static/offline.html",
];
const SHELL_PATHS = new Set(SHELL);

self.addEventListener("install", (event) => {
  // Activate the new worker immediately instead of waiting for every tab to
  // close, so shell/CSS fixes reach the user on the next load.
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(async () =>
        (await caches.match("/static/offline.html")) ||
        new Response(
          "<!doctype html><title>Offline - openpool</title><h1>openpool is offline</h1><p>No dosing guidance is available offline.</p>",
          { status: 503, headers: { "Content-Type": "text/html" } },
        ),
      ),
    );
    return;
  }
  const url = new URL(event.request.url);
  if (url.origin === self.location.origin && SHELL_PATHS.has(url.pathname)) {
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
  }
});
