/* DriveFlow PRO — Service Worker */
const CACHE = 'driveflow-v1';
const ASSETS = [
  '/',
  '/static/css/main.css',
  '/static/js/main.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&family=DM+Sans:wght@400;500&display=swap'
];

// Instalar y cachear assets estáticos
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

// Activar y limpiar caches viejos
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Estrategia: Network first, cache fallback
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Solo cachear GET
  if (e.request.method !== 'GET') return;

  // Assets estáticos: cache first
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        if (cached) return cached;
        return fetch(e.request).then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
          return res;
        });
      })
    );
    return;
  }

  // Páginas: network first, fallback a cache
  e.respondWith(
    fetch(e.request)
      .then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return res;
      })
      .catch(() => caches.match(e.request).then(cached => {
        if (cached) return cached;
        // Página offline simple
        return new Response(
          `<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
          <meta name="viewport" content="width=device-width,initial-scale=1">
          <title>DriveFlow PRO</title>
          <style>body{background:#0a0f1e;color:#f1f5f9;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;gap:12px}
          h1{color:#38bdf8;font-size:2rem;letter-spacing:2px}p{opacity:.6;font-size:.9rem}
          a{color:#38bdf8;text-decoration:none;border:1px solid #38bdf8;padding:8px 20px;border-radius:8px;margin-top:8px;display:inline-block}</style>
          </head><body>
          <h1>DRIVEFLOW PRO</h1>
          <p>Sin conexión a internet</p>
          <p style="font-size:.8rem">Los datos se cargarán cuando vuelva la conexión</p>
          <a href="/">Reintentar</a>
          </body></html>`,
          { headers: { 'Content-Type': 'text/html' } }
        );
      }))
  );
});