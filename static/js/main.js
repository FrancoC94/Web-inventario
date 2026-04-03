/* DRIVEFLOW PRO — main.js */

// ── Tema ───────────────────────────────────────────────────
const body = document.body;
body.setAttribute('data-theme', localStorage.getItem('df-theme') || 'dark');
function toggleTheme() {
    const next = body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    body.setAttribute('data-theme', next);
    localStorage.setItem('df-theme', next);
}

// ── Toast ──────────────────────────────────────────────────
function toast(msg, type = 'success', ms = 3500) {
    const c  = document.getElementById('toasts');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = msg;
    c.appendChild(el);
    setTimeout(() => {
        el.style.animation = 'tout .3s ease forwards';
        setTimeout(() => el.remove(), 300);
    }, ms);
}

// Flash auto-hide
document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => { el.style.transition='opacity .5s'; el.style.opacity='0'; setTimeout(()=>el.remove(),500); }, 4000);
});

// ── Animación entrada filas ────────────────────────────────
document.querySelectorAll('#tbodyInventario .fila').forEach((fila, i) => {
    fila.style.opacity = '0';
    fila.style.animation = `rowIn .35s ease ${i * 45}ms forwards`;
});

// ── Modal editar ───────────────────────────────────────────
function abrirEditar(id, nombre, costo, venta, stock) {
    document.getElementById('formEditar').action = `/editar/${id}`;
    document.getElementById('eNombre').value = nombre;
    document.getElementById('eCosto').value  = costo;
    document.getElementById('eVenta').value  = venta;
    document.getElementById('eStock').value  = stock;
    document.getElementById('modalEditar').classList.add('open');
    setTimeout(() => document.getElementById('eNombre').focus(), 80);
}
function cerrarModal() {
    document.getElementById('modalEditar').classList.remove('open');
}
document.getElementById('modalEditar').addEventListener('click', e => {
    if (e.target === document.getElementById('modalEditar')) cerrarModal();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') { cerrarModal(); } });

// ── Venta con animación ────────────────────────────────────
function onVender(e, form) {
    if (!confirm('¿Confirmar venta?')) return false;
    const fila = form.closest('tr');
    if (fila) {
        fila.style.animation = 'rowSale 1.2s ease';
        document.querySelectorAll('.kpi').forEach(k => {
            k.style.transition = 'transform .15s ease';
            k.style.transform  = 'scale(1.04)';
            setTimeout(() => { k.style.transform = ''; }, 280);
        });
    }
    return true;
}

// ── Eliminar con animación ─────────────────────────────────
function onEliminar(e, a, nombre) {
    e.preventDefault();
    if (!confirm(`¿Eliminar "${nombre}"? No se puede deshacer.`)) return false;
    const fila = a.closest('tr');
    if (fila) {
        fila.style.transition = 'opacity .3s ease, transform .3s ease';
        fila.style.opacity    = '0';
        fila.style.transform  = 'translateX(16px)';
        setTimeout(() => { window.location.href = a.href; }, 300);
    } else {
        window.location.href = a.href;
    }
    return false;
}

// ── Copiar pedido ──────────────────────────────────────────
async function copiarPedido() {
    try {
        const res  = await fetch('/exportar_compras');
        const text = await res.text();
        await navigator.clipboard.writeText(text);
        toast('📋 Pedido copiado. ¡Pégalo en WhatsApp!', 'success');
    } catch {
        toast('❌ No se pudo copiar.', 'danger');
    }
}

// ── Panel de Alertas ───────────────────────────────────────
let alertasOpen = false;

function toggleAlertas() {
    alertasOpen = !alertasOpen;
    document.getElementById('alertasPanel').classList.toggle('open', alertasOpen);
    document.getElementById('alertasOverlay').classList.toggle('open', alertasOpen);
    if (alertasOpen) cargarAlertas();
}

async function cargarAlertas() {
    try {
        const res  = await fetch('/alertas_stock');
        const data = await res.json();

        // Badge
        const badge = document.getElementById('badgeCount');
        if (data.total > 0) {
            badge.textContent = data.total;
            badge.style.display = 'inline';
        } else {
            badge.style.display = 'none';
        }

        // Lista
        const body = document.getElementById('alertasBody');
        if (!data.alertas.length) {
            body.innerHTML = '<p class="alertas-empty">✅ Todo el inventario está bien abastecido.</p>';
            return;
        }
        const iconos = { agotado: '💀', critico: '🔴', bajo: '🟡' };
        body.innerHTML = data.alertas.map(a => `
            <div class="alerta-item ${a.estado}">
                <div class="alerta-icono">${iconos[a.estado] || '⚠️'}</div>
                <div class="alerta-info">
                    <div class="alerta-nombre">${a.nombre}</div>
                    <div class="alerta-det">Mínimo: ${a.minimo} uds · Costo: $${a.precio.toFixed(2)}</div>
                </div>
                <div class="alerta-num ${a.estado}">${a.stock}</div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error alertas:', err);
    }
}

// Carga inicial y polling cada 30s
cargarAlertas();
setInterval(cargarAlertas, 30000);

// ── Asistente IA ───────────────────────────────────────────
let iaOpen = false;

function toggleIA() {
    iaOpen = !iaOpen;
    document.getElementById('iaPanel').classList.toggle('open', iaOpen);
    if (iaOpen) setTimeout(() => document.getElementById('iaInput').focus(), 100);
}

function pregunta(texto) {
    document.getElementById('iaInput').value = texto;
    enviarIA();
}

async function enviarIA() {
    const input = document.getElementById('iaInput');
    const log   = document.getElementById('iaLog');
    const msg   = input.value.trim();
    if (!msg) return;

    // Burbuja usuario
    const uDiv = document.createElement('div');
    uDiv.className = 'ia-msg user';
    uDiv.innerHTML = `<span class="ia-av">👤</span><div class="ia-burbuja">${msg}</div>`;
    log.appendChild(uDiv);
    input.value = '';
    input.disabled = true;

    // Typing
    const tDiv = document.createElement('div');
    tDiv.className = 'ia-msg bot';
    tDiv.innerHTML = '<span class="ia-av">🤖</span><div class="typing"><span></span><span></span><span></span></div>';
    log.appendChild(tDiv);
    log.scrollTop = log.scrollHeight;

    try {
        const res  = await fetch('/asistente', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ msg })
        });
        const data = await res.json();
        tDiv.remove();

        const bDiv = document.createElement('div');
        bDiv.className = 'ia-msg bot';
        // Formato básico markdown
        const html = data.res
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
        bDiv.innerHTML = `<span class="ia-av">🤖</span><div class="ia-burbuja">${html}</div>`;
        log.appendChild(bDiv);
    } catch {
        tDiv.remove();
        const eDiv = document.createElement('div');
        eDiv.className = 'ia-msg bot';
        eDiv.innerHTML = '<span class="ia-av">🤖</span><div class="ia-burbuja">❌ Error. Intenta de nuevo.</div>';
        log.appendChild(eDiv);
    } finally {
        input.disabled = false;
        input.focus();
        log.scrollTop = log.scrollHeight;
    }
}