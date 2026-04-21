/* DriveFlow PRO — Service Worker con modo offline POS */
const CACHE   = 'driveflow-v2';
const OFFLINE_DB = 'driveflow-offline';

const ASSETS = [
  '/pos',
  '/static/css/main.css',
  '/static/js/main.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&family=DM+Sans:wght@400;500&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js'
];

// ── Instalar ───────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── Activar ────────────────────────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// ── Fetch: cachear estáticos, POST ventas offline ──────────
self.addEventListener('fetch', e => {
  const url = e.request.url;

  // Interceptar POST a /pos/vender cuando offline
  if (e.request.method === 'POST' && url.includes('/pos/vender')) {
    e.respondWith(
      fetch(e.request.clone()).catch(async () => {
        // Sin internet — guardar en IndexedDB para sincronizar luego
        const body = await e.request.clone().json().catch(() => null);
        if (body) {
          await guardarOffline(body);
          return new Response(JSON.stringify({
            ok:      true,
            offline: true,
            total:   body.items ? body.items.reduce((s, i) => s + (i.precio || 0) * i.cantidad, 0) : 0,
            detalle: body.items || [],
            cajero:  'Offline',
            cliente: body.cliente || 'Cliente general',
            hora:    new Date().toLocaleTimeString('es'),
            errores: [],
            msg:     '⚠️ Venta guardada offline. Se sincronizará al recuperar conexión.'
          }), { headers: { 'Content-Type': 'application/json' } });
        }
        return new Response(JSON.stringify({ ok: false, msg: 'Sin conexión y sin datos.' }),
          { headers: { 'Content-Type': 'application/json' } });
      })
    );
    return;
  }

  // GET estáticos: cache first
  if (e.request.method === 'GET' && (url.includes('/static/') || url.includes('googleapis') || url.includes('cloudflare'))) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        if (cached) return cached;
        return fetch(e.request).then(res => {
          caches.open(CACHE).then(c => c.put(e.request, res.clone()));
          return res;
        });
      })
    );
    return;
  }

  // GET páginas: network first, cache fallback
  if (e.request.method === 'GET') {
    e.respondWith(
      fetch(e.request).then(res => {
        caches.open(CACHE).then(c => c.put(e.request, res.clone()));
        return res;
      }).catch(() => caches.match(e.request).then(cached => cached || offlinePage()))
    );
  }
});

// ── Guardar venta offline en IndexedDB ─────────────────────
async function guardarOffline(data) {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(OFFLINE_DB, 1);
    req.onupgradeneeded = e => {
      e.target.result.createObjectStore('ventas', { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = e => {
      const db  = e.target.result;
      const tx  = db.transaction('ventas', 'readwrite');
      tx.objectStore('ventas').add({ ...data, timestamp: Date.now() });
      tx.oncomplete = resolve;
      tx.onerror    = reject;
    };
    req.onerror = reject;
  });
}

// ── Sincronizar ventas offline ─────────────────────────────
self.addEventListener('sync', e => {
  if (e.tag === 'sync-ventas') {
    e.waitUntil(sincronizarVentas());
  }
});

async function sincronizarVentas() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(OFFLINE_DB, 1);
    req.onsuccess = async e => {
      const db     = e.target.result;
      const tx     = db.transaction('ventas', 'readonly');
      const ventas = await new Promise(r => {
        const all = []; const cursor = tx.objectStore('ventas').openCursor();
        cursor.onsuccess = ev => {
          if (ev.target.result) { all.push(ev.target.result.value); ev.target.result.continue(); }
          else r(all);
        };
      });

      for (const venta of ventas) {
        try {
          const res = await fetch('/pos/vender', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(venta)
          });
          if (res.ok) {
            // Borrar de IndexedDB si se sincronizó
            const tx2 = db.transaction('ventas', 'readwrite');
            tx2.objectStore('ventas').delete(venta.id);
          }
        } catch {}
      }

      // Notificar a los clientes
      const clients = await self.clients.matchAll();
      clients.forEach(c => c.postMessage({ type: 'SYNC_DONE', count: ventas.length }));
      resolve();
    };
    req.onerror = reject;
  });
}

// ── Página offline ─────────────────────────────────────────
function offlinePage() {
  return new Response(`<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DriveFlow PRO — Offline</title>
<style>
  body{background:#0a0f1e;color:#f1f5f9;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;gap:12px;text-align:center;padding:20px}
  h1{color:#38bdf8;font-size:2rem;letter-spacing:2px;margin:0}
  .sub{opacity:.5;font-size:.88rem}
  .badge{background:rgba(245,158,11,.15);color:#f59e0b;border:1px solid rgba(245,158,11,.3);padding:8px 20px;border-radius:20px;font-size:.82rem;font-weight:700}
  a{color:#38bdf8;text-decoration:none;border:1px solid #38bdf8;padding:10px 24px;border-radius:10px;margin-top:8px;display:inline-block;font-weight:700}
  a:hover{background:#38bdf8;color:#0a0f1e}
</style></head>
<body>
  <h1>DRIVEFLOW PRO</h1>
  <p class="sub">Panel de Control · Inventario Inteligente</p>
  <span class="badge">📡 Sin conexión a internet</span>
  <p class="sub" style="max-width:300px">El POS sigue funcionando. Las ventas se guardarán y sincronizarán cuando vuelva la conexión.</p>
  <a href="/pos">🛒 Ir al POS</a>
  <a href="/">← Inventario</a>
</body></html>`,
    { headers: { 'Content-Type': 'text/html' } });
}