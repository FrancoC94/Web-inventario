from flask import Blueprint, request, jsonify, session
from models import Repuesto, Venta, Gasto, Proveedor
from extensions import db
from sqlalchemy import func
from datetime import datetime, timedelta

asistente_bp = Blueprint('asistente', __name__)

# ── Recopilar datos reales del negocio ─────────────────────
def _datos():
    hoy      = datetime.utcnow().date()
    ayer     = hoy - timedelta(days=1)
    semana   = datetime.utcnow() - timedelta(days=7)
    mes      = datetime.utcnow().replace(day=1)

    todos    = Repuesto.query.all()
    agotados = [p for p in todos if p.stock == 0]
    criticos = [p for p in todos if 0 < p.stock <= p.stock_minimo]
    bajos    = [p for p in todos if p.stock_minimo < p.stock <= p.stock_minimo * 2]

    ventas_hoy   = Venta.query.filter(func.date(Venta.fecha) == hoy).all()
    ventas_ayer  = Venta.query.filter(func.date(Venta.fecha) == ayer).all()
    ventas_sem   = Venta.query.filter(Venta.fecha >= semana).all()
    ventas_mes   = Venta.query.filter(Venta.fecha >= mes).all()
    ventas_todas = Venta.query.all()

    total_hoy    = sum(v.total_venta for v in ventas_hoy)
    total_ayer   = sum(v.total_venta for v in ventas_ayer)
    total_sem    = sum(v.total_venta for v in ventas_sem)
    total_mes    = sum(v.total_venta for v in ventas_mes)
    gan_hoy      = sum(v.ganancia_operacion for v in ventas_hoy)
    gan_sem      = sum(v.ganancia_operacion for v in ventas_sem)
    gan_mes      = sum(v.ganancia_operacion for v in ventas_mes)
    gan_total    = sum(v.ganancia_operacion for v in ventas_todas)

    # Gastos del mes
    gastos_mes = 0
    try:
        gastos_mes = db.session.query(func.sum(Gasto.monto)).filter(Gasto.fecha >= mes).scalar() or 0
    except: pass

    # Top productos por ganancia
    top_gan = (db.session.query(Venta.repuesto_id, func.sum(Venta.ganancia_operacion).label('g'),
                                func.sum(Venta.cantidad).label('c'))
               .group_by(Venta.repuesto_id)
               .order_by(db.text('g DESC')).limit(5).all())

    top_productos = []
    for row in top_gan:
        p = db.session.get(Repuesto, row[0])
        if p: top_productos.append({'nombre': p.nombre, 'ganancia': row[1], 'vendido': row[2], 'stock': p.stock})

    # Producto más vendido hoy
    hoy_counts = {}
    for v in ventas_hoy:
        hoy_counts[v.repuesto_id] = hoy_counts.get(v.repuesto_id, 0) + v.cantidad
    estrella_hoy = None
    if hoy_counts:
        pid = max(hoy_counts, key=hoy_counts.get)
        p   = db.session.get(Repuesto, pid)
        if p: estrella_hoy = p.nombre

    # Margen promedio
    margen_prom = 0
    with_cost = [p for p in todos if p.p_costo > 0]
    if with_cost:
        margen_prom = sum((p.p_venta - p.p_costo) / p.p_costo * 100 for p in with_cost) / len(with_cost)

    # Valor del inventario
    valor_inv = sum(p.p_costo * p.stock for p in todos)

    # Variación vs ayer
    variacion = ((total_hoy - total_ayer) / total_ayer * 100) if total_ayer > 0 else None

    # Proveedor count
    prov_count = 0
    try: prov_count = Proveedor.query.filter_by(activo=True).count()
    except: pass

    return {
        'todos': todos, 'agotados': agotados, 'criticos': criticos, 'bajos': bajos,
        'total_hoy': total_hoy, 'total_ayer': total_ayer, 'total_sem': total_sem, 'total_mes': total_mes,
        'gan_hoy': gan_hoy, 'gan_sem': gan_sem, 'gan_mes': gan_mes, 'gan_total': gan_total,
        'gastos_mes': gastos_mes, 'ganancia_neta': gan_mes - gastos_mes,
        'top_productos': top_productos, 'estrella_hoy': estrella_hoy,
        'margen_prom': margen_prom, 'valor_inv': valor_inv,
        'variacion': variacion, 'prov_count': prov_count,
        'num_ventas_hoy': len(ventas_hoy), 'num_ventas_sem': len(ventas_sem),
    }

# ── Motor de respuestas ────────────────────────────────────
def _responder(msg, nombre_usuario=''):
    m = msg.lower().strip()
    d = _datos()
    saludo = f' {nombre_usuario}' if nombre_usuario else ''

    # ── SALUDO / AYUDA ─────────────────────────────────────
    if any(w in m for w in ['hola','buenos','buenas','hey','hi','qué tal','que tal','inicio','ayuda','puedes','funciones']):
        hora = datetime.utcnow().hour
        if hora < 12:   tiempo = 'Buenos días'
        elif hora < 18: tiempo = 'Buenas tardes'
        else:           tiempo = 'Buenas noches'

        alertas = len(d['agotados']) + len(d['criticos'])
        alerta_txt = f'\n⚠️ Tienes **{alertas}** producto(s) que necesitan atención urgente.' if alertas else '\n✅ Inventario en buen estado.'

        return (f'{tiempo}{saludo}! 👋 Soy tu asistente DriveFlow PRO.\n\n'
                f'📊 **Estado actual del negocio:**{alerta_txt}\n'
                f'💰 Ventas hoy: **${d["total_hoy"]:,.2f}** ({d["num_ventas_hoy"]} transacciones)\n'
                f'📦 Productos en inventario: **{len(d["todos"])}**\n\n'
                f'Puedo ayudarte con:\n'
                f'• ventas / ganancias / resumen\n'
                f'• stock / alertas / pedidos\n'
                f'• márgenes / rentabilidad\n'
                f'• consejos / análisis\n'
                f'• buscar un producto específico\n\n'
                f'¿Qué necesitas saber?')

    # ── RESUMEN GENERAL ─────────────────────────────────────
    if any(w in m for w in ['resumen','reporte','informe','general','todo','cómo vamos','como vamos','estado']):
        var_txt = ''
        if d['variacion'] is not None:
            icono = '📈' if d['variacion'] >= 0 else '📉'
            var_txt = f'\n{icono} Variación vs ayer: **{d["variacion"]:+.1f}%**'

        return (f'📋 **RESUMEN DRIVEFLOW PRO**\n\n'
                f'**HOY:**\n'
                f'💰 Ventas: **${d["total_hoy"]:,.2f}** ({d["num_ventas_hoy"]} transacciones)\n'
                f'📈 Ganancia bruta: **${d["gan_hoy"]:,.2f}**{var_txt}\n\n'
                f'**ESTA SEMANA:**\n'
                f'💰 Ventas: **${d["total_sem"]:,.2f}** ({d["num_ventas_sem"]} transacciones)\n'
                f'📈 Ganancia: **${d["gan_sem"]:,.2f}**\n\n'
                f'**ESTE MES:**\n'
                f'💰 Ventas: **${d["total_mes"]:,.2f}**\n'
                f'📈 Ganancia bruta: **${d["gan_mes"]:,.2f}**\n'
                f'💸 Gastos: **${d["gastos_mes"]:,.2f}**\n'
                f'✨ Ganancia neta: **${d["ganancia_neta"]:,.2f}**\n\n'
                f'**INVENTARIO:**\n'
                f'📦 Productos: **{len(d["todos"])}** | Agotados: **{len(d["agotados"])}** | Críticos: **{len(d["criticos"])}**\n'
                f'💎 Valor inventario: **${d["valor_inv"]:,.2f}**')

    # ── VENTAS ─────────────────────────────────────────────
    if any(w in m for w in ['venta','vendido','hoy','facturé','facture','cobré','cobre','ingreso']):
        if 'semana' in m or '7 días' in m or '7 dias' in m:
            return (f'📊 **Ventas de la semana:**\n'
                    f'💰 Total: **${d["total_sem"]:,.2f}**\n'
                    f'📈 Ganancia bruta: **${d["gan_sem"]:,.2f}**\n'
                    f'🛒 Transacciones: **{d["num_ventas_sem"]}**\n'
                    f'📊 Promedio diario: **${d["total_sem"]/7:,.2f}**')
        if 'mes' in m:
            return (f'📊 **Ventas del mes:**\n'
                    f'💰 Total: **${d["total_mes"]:,.2f}**\n'
                    f'📈 Ganancia bruta: **${d["gan_mes"]:,.2f}**\n'
                    f'💸 Gastos del mes: **${d["gastos_mes"]:,.2f}**\n'
                    f'✨ Ganancia neta: **${d["ganancia_neta"]:,.2f}**')

        var_txt = ''
        if d['variacion'] is not None:
            icono = '📈' if d['variacion'] >= 0 else '📉'
            var_txt = f'\n{icono} Variación vs ayer (${d["total_ayer"]:,.2f}): **{d["variacion"]:+.1f}%**'

        estrella_txt = f'\n🏆 Producto más vendido hoy: **{d["estrella_hoy"]}**' if d['estrella_hoy'] else ''
        return (f'💰 **Ventas de hoy:**\n'
                f'Total: **${d["total_hoy"]:,.2f}**\n'
                f'Ganancia bruta: **${d["gan_hoy"]:,.2f}**\n'
                f'Transacciones: **{d["num_ventas_hoy"]}**{var_txt}{estrella_txt}')

    # ── GANANCIAS / RENTABILIDAD ────────────────────────────
    if any(w in m for w in ['ganancia','rentab','utilidad','beneficio','profit','neta']):
        consejo = ''
        if d['ganancia_neta'] < 0:
            consejo = f'\n\n⚠️ **Atención:** Tu ganancia neta es negativa. Los gastos (${d["gastos_mes"]:,.2f}) superan la ganancia bruta. Revisa tus gastos o aumenta ventas.'
        elif d['margen_prom'] < 20:
            consejo = f'\n\n💡 **Consejo:** Tu margen promedio es bajo ({d["margen_prom"]:.1f}%). Considera revisar los precios de tus productos.'
        elif d['ganancia_neta'] > 0:
            consejo = f'\n\n✅ **Buen trabajo!** Tu negocio está generando ganancias netas positivas este mes.'

        return (f'📈 **Análisis de ganancias:**\n\n'
                f'**Este mes:**\n'
                f'Ganancia bruta: **${d["gan_mes"]:,.2f}**\n'
                f'Gastos: **-${d["gastos_mes"]:,.2f}**\n'
                f'Ganancia neta: **${d["ganancia_neta"]:,.2f}**\n\n'
                f'**Histórico total:** **${d["gan_total"]:,.2f}**\n'
                f'**Margen promedio inventario:** **{d["margen_prom"]:.1f}%**{consejo}')

    # ── STOCK / INVENTARIO ──────────────────────────────────
    if any(w in m for w in ['stock','inventario','cuántos','cuantos','productos','almacén','almacen']):
        txt = f'📦 **Inventario actual:**\n\nTotal productos: **{len(d["todos"])}**\nValor total: **${d["valor_inv"]:,.2f}**\n\n'
        if d['agotados']:
            txt += f'**💀 AGOTADOS ({len(d["agotados"])}):**\n'
            txt += '\n'.join(f'  • {p.nombre}' for p in d['agotados'][:5])
            if len(d['agotados']) > 5: txt += f'\n  ...y {len(d["agotados"])-5} más'
            txt += '\n\n'
        if d['criticos']:
            txt += f'**🔴 CRÍTICOS ({len(d["criticos"])}):**\n'
            txt += '\n'.join(f'  • {p.nombre}: {p.stock} uds (mín: {p.stock_minimo})' for p in d['criticos'][:5])
            txt += '\n\n'
        if d['bajos']:
            txt += f'**🟡 STOCK BAJO ({len(d["bajos"])}):**\n'
            txt += '\n'.join(f'  • {p.nombre}: {p.stock} uds' for p in d['bajos'][:3])
        if not d['agotados'] and not d['criticos'] and not d['bajos']:
            txt += '✅ Todo el inventario está bien abastecido.'
        return txt

    # ── ALERTAS / CRÍTICOS ──────────────────────────────────
    if any(w in m for w in ['alerta','crítico','critico','agotado','urgente','reposición','reposicion','falta']):
        total_alertas = len(d['agotados']) + len(d['criticos'])
        if total_alertas == 0:
            return '✅ ¡Excelente! No tienes productos críticos ni agotados. Tu inventario está bien abastecido.'

        txt = f'🚨 **{total_alertas} producto(s) necesitan atención:**\n\n'
        if d['agotados']:
            txt += '**💀 AGOTADOS — Sin stock:**\n'
            txt += '\n'.join(f'  • {p.nombre}' for p in d['agotados'])
            txt += '\n\n'
        if d['criticos']:
            txt += '**🔴 CRÍTICOS — Reponer pronto:**\n'
            txt += '\n'.join(f'  • {p.nombre}: {p.stock}/{p.stock_minimo} uds mínimo' for p in d['criticos'])
        txt += '\n\n💡 Escribe **"pedido"** para ver cuánto necesitas comprar.'
        return txt

    # ── PEDIDO / REPOSICIÓN ─────────────────────────────────
    if any(w in m for w in ['pedido','comprar','reponer','abastecer','pedir','orden','proveedor']):
        urgentes = d['agotados'] + d['criticos']
        if not urgentes:
            return '✅ No necesitas hacer pedidos urgentes. Tu inventario está bien abastecido.'
        inversion = sum(max(0, p.stock_minimo * 3 - p.stock) * p.p_costo for p in urgentes)
        txt = f'🛒 **Pedido sugerido ({len(urgentes)} productos):**\n\n'
        for p in urgentes[:10]:
            cant_pedir = max(0, p.stock_minimo * 3 - p.stock)
            costo_total = cant_pedir * p.p_costo
            txt += f'  • {p.nombre}: pedir **{cant_pedir} uds** (${costo_total:,.2f})\n'
        txt += f'\n💵 **Inversión total estimada: ${inversion:,.2f}**'
        if d['prov_count'] > 0:
            txt += f'\n📞 Tienes **{d["prov_count"]}** proveedores activos. Ve a Proveedores para crear la orden.'
        return txt

    # ── TOP PRODUCTOS / ESTRELLAS ───────────────────────────
    if any(w in m for w in ['top','mejor','estrella','más vendido','mas vendido','popular','rentable']):
        if not d['top_productos']:
            return '📊 Aún no hay suficientes ventas para mostrar el top de productos.'
        txt = '🏆 **Top productos por ganancia:**\n\n'
        for i, p in enumerate(d['top_productos'], 1):
            estado = '⚠️ Stock bajo' if p['stock'] <= 5 else '✅'
            txt += f'  {i}. **{p["nombre"]}**\n'
            txt += f'     Ganancia: ${p["ganancia"]:,.2f} | Vendido: {p["vendido"]} uds {estado}\n'
        txt += f'\n💡 **Consejo:** Asegúrate de mantener bien abastecidos estos productos — son los que más dinero generan.'
        return txt

    # ── MÁRGENES / PRECIOS ──────────────────────────────────
    if any(w in m for w in ['margen','precio','markup','rentab','costo']):
        todos = d['todos']
        con_margen = [(p, (p.p_venta-p.p_costo)/p.p_costo*100) for p in todos if p.p_costo > 0]
        if not con_margen:
            return '📊 No hay productos con costo registrado para calcular márgenes.'
        top_margen = sorted(con_margen, key=lambda x: x[1], reverse=True)[:5]
        low_margen = [x for x in con_margen if x[1] < 15]
        txt = f'📊 **Análisis de márgenes:**\n\nMargen promedio: **{d["margen_prom"]:.1f}%**\n\n'
        txt += '**Top 5 mejor margen:**\n'
        for p, m in top_margen:
            txt += f'  • {p.nombre}: **{m:.0f}%**\n'
        if low_margen:
            txt += f'\n⚠️ **{len(low_margen)} producto(s) con margen menor al 15%** — considera revisar sus precios:\n'
            txt += '\n'.join(f'  • {p.nombre}: {m:.0f}%' for p,m in low_margen[:4])
        return txt

    # ── CONSEJOS / ANÁLISIS ─────────────────────────────────
    if any(w in m for w in ['consejo','tip','sugerencia','mejorar','optimizar','ayudarme','qué hago','que hago','análisis','analisis']):
        consejos = []
        if d['agotados']:
            consejos.append(f'🚨 Tienes **{len(d["agotados"])}** producto(s) agotados — cada día sin stock es dinero perdido.')
        if d['ganancia_neta'] < 0:
            consejos.append(f'💸 Tus gastos superan la ganancia este mes. Analiza qué gastos puedes reducir.')
        if d['margen_prom'] < 20:
            consejos.append(f'📊 Tu margen promedio ({d["margen_prom"]:.1f}%) está bajo. La calculadora de precios puede ayudarte a ajustar.')
        if d['total_hoy'] == 0:
            consejos.append(f'🛒 Sin ventas hoy. ¿Consideraste alguna promoción o descuento temporal?')
        if d['total_hoy'] > d['total_ayer'] * 1.2:
            consejos.append(f'🎉 ¡Hoy vendes un {((d["total_hoy"]/d["total_ayer"]-1)*100):.0f}% más que ayer! Buen ritmo.')
        if not d['top_productos']:
            consejos.append(f'📦 Registra ventas en el POS para ver análisis de productos estrellas.')
        if not consejos:
            consejos.append(f'✅ Tu negocio está funcionando bien. Mantén el inventario abastecido y sigue monitoreando las ganancias netas.')
            consejos.append(f'💡 Revisa los productos con mejor margen y asegúrate de tenerlos siempre en stock.')

        return '💡 **Consejos para tu negocio:**\n\n' + '\n\n'.join(consejos)

    # ── COMPARAR HOY VS AYER ────────────────────────────────
    if any(w in m for w in ['ayer','comparar','vs','diferencia','cambio']):
        if d['variacion'] is None:
            return '📊 No hay ventas de ayer para comparar.'
        icono  = '📈' if d['variacion'] >= 0 else '📉'
        estado = 'mejor' if d['variacion'] >= 0 else 'menor'
        return (f'{icono} **Comparación hoy vs ayer:**\n\n'
                f'Hoy: **${d["total_hoy"]:,.2f}**\n'
                f'Ayer: **${d["total_ayer"]:,.2f}**\n'
                f'Diferencia: **{d["variacion"]:+.1f}%** ({estado} que ayer)\n\n'
                f'{"🎉 ¡Buen día!" if d["variacion"] >= 0 else "💪 Vamos, aún puedes mejorar el día!"}')

    # ── BÚSQUEDA DIRECTA DE PRODUCTO ───────────────────────
    palabras = [w for w in m.split() if len(w) > 2]
    for p in d['todos']:
        if any(w in p.nombre.lower() for w in palabras) or p.nombre.lower() in m:
            margen = (p.p_venta - p.p_costo) / p.p_costo * 100 if p.p_costo > 0 else 0
            estado_icon = {'ok':'🟢','bajo':'🟡','critico':'🔴','agotado':'💀'}.get(p.estado_stock,'⚪')
            ganancia_ud = p.p_venta - p.p_costo
            alerta = ''
            if p.estado_stock in ('agotado','critico'):
                cant_pedir = max(0, p.stock_minimo * 3 - p.stock)
                alerta = f'\n⚠️ Necesitas reponer. Pedir aprox. **{cant_pedir} uds** (${cant_pedir*p.p_costo:,.2f})'
            return (f'{estado_icon} **{p.nombre}**\n\n'
                    f'📦 Stock: **{p.stock} uds** (mín: {p.stock_minimo})\n'
                    f'💰 Precio venta: **${p.p_venta:,.2f}**\n'
                    f'🏷️ Costo: **${p.p_costo:,.2f}**\n'
                    f'📈 Ganancia por unidad: **${ganancia_ud:,.2f}**\n'
                    f'📊 Margen: **{margen:.1f}%**\n'
                    f'🛒 Vendido total: **{p.vendido} uds**\n'
                    f'💎 Estado: **{p.estado_stock.upper()}**{alerta}')

    # ── RESPUESTA POR DEFECTO ───────────────────────────────
    return ('🤖 No entendí exactamente, pero puedo ayudarte con:\n\n'
            '• **"resumen"** → estado general del negocio\n'
            '• **"ventas hoy/semana/mes"** → análisis de ventas\n'
            '• **"ganancias"** → rentabilidad y ganancia neta\n'
            '• **"alertas"** → productos críticos o agotados\n'
            '• **"pedido"** → qué necesitas comprar\n'
            '• **"top productos"** → los más rentables\n'
            '• **"márgenes"** → análisis de precios\n'
            '• **"consejos"** → sugerencias personalizadas\n'
            '• **"ayer vs hoy"** → comparar días\n'
            '• Nombre de un producto para buscarlo\n\n'
            '¿Qué quieres saber?')

@asistente_bp.route('/asistente', methods=['POST'])
def asistente():
    data   = request.get_json(silent=True) or {}
    msg    = data.get('msg','').strip()
    nombre = session.get('user_nombre','')
    if not msg:
        return jsonify({'res': '❓ Escribe tu pregunta.'})
    return jsonify({'res': _responder(msg, nombre)})

@asistente_bp.route('/alertas_stock')
def alertas_stock():
    todos   = Repuesto.query.all()
    alertas = [{'id':p.id,'nombre':p.nombre,'stock':p.stock,'minimo':p.stock_minimo,
                'estado':p.estado_stock,'precio':p.p_costo}
               for p in todos if p.estado_stock != 'ok']
    alertas.sort(key=lambda x: x['stock'])
    return jsonify({'alertas':alertas,'total':len(alertas)})