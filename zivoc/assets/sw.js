self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  e.respondWith(fetch(e.request).catch(function () {
    if (e.request.mode === 'navigate') {
      return new Response('You are offline. Reconnect to use Zivoc.', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }
    return Response.error();
  }));
});
