from flask import Blueprint, request, jsonify
from models import Repuesto, Venta
from extensions import db
from sqlalchemy import func
from datetime import datetime

asistente_bp = Blueprint('asistente', __name__)

def _resumen():
    todos      = Repuesto.query.all()
    criticos   = [p for p in todos if p.estado_stock in ('critico','agotado')]
    hoy        = datetime.utcnow().date()
    ventas_hoy = Venta.query.filter(func.date(Venta.fecha) == hoy).all()
    total_hoy  = sum(v.total_venta for v in ventas_hoy)
    ganancia   = db.session.query(func.sum(Venta.ganancia_operacion)).scalar() or 0
    top = (db.session.query(Venta.repuesto_id, func.sum(Venta.ganancia_operacion).label('g'))
           .group_by(Venta.repuesto_id).order_by(db.text('g DESC')).first())
    estrella = db.session.get(Repuesto, top[0]).nombre if top else 'Sin datos'
    return todos, criticos, total_hoy, ganancia, estrella

def _responder(msg):
    msg_l = msg.lower()
    todos, criticos, total_hoy, ganancia, estrella = _resumen()

    if any(w in msg_l for w in ['hola','ayuda','puedes','funciones','inicio']):
        return ('👋 Hola! Soy el asistente de DRIVEFLOW PRO.\n\n'
                'Puedo ayudarte con:\n'
                '📦 Stock e inventario\n'
                '💰 Ventas y ganancias\n'
                '🚨 Alertas de productos críticos\n'
                '🛒 Recomendaciones de pedidos\n'
                '📊 Márgenes y análisis\n\n'
                '¿Qué necesitas saber?')

    if any(w in msg_l for w in ['stock','inventario','cuantos','cuántos','productos']):
        if criticos:
            lista = '\n'.join(f'  🔴 {p.nombre}: {p.stock} uds' for p in criticos[:6])
            return f'📦 Tienes **{len(todos)}** productos en total.\n\n⚠️ **{len(criticos)}** necesitan atención:\n{lista}'
        return f'📦 Tienes **{len(todos)}** productos. ✅ Todo el inventario está bien abastecido.'

    if any(w in msg_l for w in ['venta','vendido','hoy','dia','día']):
        return (f'💰 Ventas de hoy: **${total_hoy:,.2f}**\n'
                f'📈 Ganancia acumulada total: **${ganancia:,.2f}**\n'
                f'🏆 Producto estrella: **{estrella}**')

    if any(w in msg_l for w in ['critico','crítico','agotado','urgente','alerta']):
        if not criticos:
            return '✅ ¡Excelente! No tienes productos críticos o agotados en este momento.'
        lista = '\n'.join(f'  {"💀" if p.estado_stock=="agotado" else "🔴"} {p.nombre}: {p.stock} uds (mín: {p.stock_minimo})' for p in criticos)
        return f'🚨 Productos que necesitan reposición urgente:\n{lista}'

    if any(w in msg_l for w in ['margen','ganancia','rentable','mejor','precio']):
        ganancias = sorted([(p, (p.p_venta-p.p_costo)/p.p_costo*100) for p in todos if p.p_costo>0], key=lambda x: x[1], reverse=True)
        top3 = '\n'.join(f'  {i+1}. {p.nombre}: **{m:.0f}%** margen' for i,(p,m) in enumerate(ganancias[:5]))
        return f'📊 Productos con mejor margen de ganancia:\n{top3}'

    if any(w in msg_l for w in ['pedir','pedido','comprar','reponer','abastecer']):
        if not criticos:
            return '✅ No necesitas hacer pedidos urgentes ahora mismo.'
        inversion = sum(max(0,(p.stock_minimo*2 - p.stock)) * p.p_costo for p in criticos)
        lista = '\n'.join(f'  • {p.nombre}: pedir {max(0,p.stock_minimo*2-p.stock)} uds' for p in criticos[:8])
        return f'🛒 Pedido sugerido para reponer stock:\n{lista}\n\n💵 Inversión estimada: **${inversion:,.2f}**'

    if any(w in msg_l for w in ['estrella','top','mas vendido','más vendido','popular']):
        return f'🏆 El producto estrella por ganancia es: **{estrella}**'

    if any(w in msg_l for w in ['resumen','reporte','informe','general']):
        return (f'📋 **RESUMEN DRIVEFLOW PRO**\n\n'
                f'📦 Total productos: **{len(todos)}**\n'
                f'🚨 Productos críticos: **{len(criticos)}**\n'
                f'💰 Ventas hoy: **${total_hoy:,.2f}**\n'
                f'📈 Ganancia acumulada: **${ganancia:,.2f}**\n'
                f'🏆 Producto estrella: **{estrella}**')

    # Búsqueda directa de producto
    for p in todos:
        if p.nombre.lower() in msg_l or any(w in p.nombre.lower() for w in msg_l.split() if len(w)>3):
            estado_icon = {'ok':'🟢','bajo':'🟡','critico':'🔴','agotado':'💀'}.get(p.estado_stock,'⚪')
            return (f'{estado_icon} **{p.nombre}**\n'
                    f'Stock: {p.stock} uds\n'
                    f'Precio venta: ${p.p_venta:,.2f}\n'
                    f'Costo: ${p.p_costo:,.2f}\n'
                    f'Margen: {((p.p_venta-p.p_costo)/p.p_costo*100):.1f}%\n'
                    f'Estado: {p.estado_stock.upper()}')

    return ('🤖 Entendido. Puedo ayudarte con:\n'
            '• stock / inventario\n• ventas / ganancias\n• alertas / críticos\n'
            '• pedidos / reposición\n• márgenes / precios\n• resumen general\n\n'
            'O escribe el nombre de un producto para buscarlo.')

@asistente_bp.route('/asistente', methods=['POST'])
def asistente():
    data = request.get_json(silent=True) or {}
    msg  = data.get('msg','').strip()
    if not msg:
        return jsonify({'res':'❓ Escribe tu pregunta.'})
    return jsonify({'res': _responder(msg)})

@asistente_bp.route('/alertas_stock')
def alertas_stock():
    todos   = Repuesto.query.all()
    alertas = [{'id':p.id,'nombre':p.nombre,'stock':p.stock,'minimo':p.stock_minimo,
                'estado':p.estado_stock,'precio':p.p_costo}
               for p in todos if p.estado_stock != 'ok']
    alertas.sort(key=lambda x: x['stock'])
    return jsonify({'alertas':alertas,'total':len(alertas)})