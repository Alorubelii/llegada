/* Llegada · service worker: abre al instante y sin cobertura muestra lo último que tenía.
   Los datos en directo (servidor y espejo) nunca se guardan: siempre van a la red. */
const VERSION = "llegada-v2";
const BASE = ["./", "./index.html", "./manifest.webmanifest", "./icon.svg", "./icon-192.png", "./data/estaciones.json"];
self.addEventListener("install", e => { e.waitUntil(caches.open(VERSION).then(c => c.addAll(BASE)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return; // datos en directo: red
  // la página y los horarios: primero red, si falla la copia guardada
  e.respondWith(fetch(e.request).then(r => { const copia = r.clone(); if (r.ok) caches.open(VERSION).then(c => c.put(e.request, copia)); return r; })
    .catch(() => caches.match(e.request).then(r => r || caches.match("./index.html"))));
});
self.addEventListener("notificationclick", e => { e.notification.close(); e.waitUntil(self.clients.matchAll({ type: "window" }).then(cs => cs.length ? cs[0].focus() : self.clients.openWindow("./#seguir"))); });
