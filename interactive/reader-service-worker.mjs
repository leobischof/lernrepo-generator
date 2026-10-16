import {rangeBounds} from "./reader-offline.mjs";
const base = new URL("./",self.location.href);
const FAMILY = `lernrepo-reader-${encodeURIComponent(base.pathname)}-`;
const CACHE = FAMILY + "__LEARNREPO_CACHE_VERSION__";
const localURL = path => {
  const url = new URL(path,base);
  if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) throw new Error("Ungültiger Paketpfad");
  return url.href;
};
self.addEventListener("install",event => event.waitUntil((async () => {
  const response = await fetch(localURL("reader-offline-index.json"),{cache:"no-store"});
  if (!response.ok) throw new Error("Offline-Dateiliste fehlt");
  const index = await response.json(), cache = await caches.open(CACHE);
  await cache.addAll(index.shell.map(localURL));
  await self.skipWaiting();
})()));
self.addEventListener("activate",event => event.waitUntil((async () => {
  for (const name of await caches.keys()) if (name.startsWith(FAMILY) && name !== CACHE) await caches.delete(name);
  await self.clients.claim();
})()));
self.addEventListener("message",event => {
  if (event.data?.type !== "CACHE_CHAPTER") return;
  const port = event.ports[0];
  event.waitUntil((async () => {
    try {
      const cache = await caches.open(CACHE);
      const manifest = await (await cache.match(localURL("reader-manifest.json"))).json();
      const chapter = manifest.chapters.find(c => c.number === event.data.number);
      if (!chapter) throw new Error("Kapitel nicht gefunden");
      const files = [chapter.pdf,chapter.timeline,chapter.audio].filter(Boolean);
      for (let i = 0; i < files.length; i++) {
        port?.postMessage({message:`Kapitel ${chapter.number}: Datei ${i+1}/${files.length} speichern …`});
        const url = localURL(files[i]);
        if (!await cache.match(url)) await cache.add(new Request(url,{credentials:"same-origin"}));
      }
      port?.postMessage({done:true,message:`Kapitel ${chapter.number} ist auf diesem Gerät offline gespeichert.`});
    } catch (error) { port?.postMessage({error:true,message:`Offline-Speichern fehlgeschlagen: ${error.message}`}); }
  })());
});
self.addEventListener("fetch",event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const key = url.pathname.endsWith("/reader.html") ? localURL("reader.html") : request.url;
    const cached = await cache.match(key);
    if (!cached) return fetch(request);
    const range = request.headers.get("Range");
    if (!range) return cached;
    const blob = await cached.blob(), bounds = rangeBounds(range,blob.size);
    if (!bounds) return new Response(null,{status:416,headers:{"Content-Range":`bytes */${blob.size}`}});
    const [start,end] = bounds;
    return new Response(blob.slice(start,end+1),{status:206,headers:{"Content-Type":cached.headers.get("Content-Type") || "application/octet-stream","Content-Length":String(end-start+1),"Content-Range":`bytes ${start}-${end}/${blob.size}`,"Accept-Ranges":"bytes"}});
  })());
});
