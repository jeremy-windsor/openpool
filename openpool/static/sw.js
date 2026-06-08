const CACHE_NAME = "openpool-shell-v4";
const SHELL = ["/static/tokens.css", "/static/app.css", "/static/app.js"];

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
      fetch(event.request).catch(() =>
        new Response(
          "<!doctype html><title>openpool offline</title><main><h1>Offline</h1><p>Dashboard chemistry is not shown from a stale cache. Reconnect and refresh before dosing.</p></main>",
          { status: 503, headers: { "Content-Type": "text/html" } },
        ),
      ),
    );
    return;
  }
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
