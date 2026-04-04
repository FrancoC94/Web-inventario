from flask import Blueprint, render_template, request, jsonify, session
from extensions import db
from models import Repuesto, Venta, HistorialStock
from sqlalchemy import func
from datetime import datetime

pos_bp = Blueprint('pos', __name__)

@pos_bp.route('/pos')
def index():
    return render_template('pos.html')

@pos_bp.route('/pos/buscar')
def buscar():
    q = request.args.get('q', '').upper().strip()
    if len(q) < 1:
        return jsonify([])
    productos = Repuesto.query.filter(
        func.upper(Repuesto.nombre).contains(q)
    ).limit(8).all()
    return jsonify([{
        'id':     p.id,
        'nombre': p.nombre,
        'precio': p.p_venta,
        'stock':  p.stock,
        'estado': p.estado_stock
    } for p in productos])

@pos_bp.route('/pos/vender', methods=['POST'])
def vender():
    data  = request.get_json(silent=True) or {}
    items = data.get('items', [])  # [{id, cantidad}, ...]
    uid   = session.get('user_id')

    if not items:
        return jsonify({'ok': False, 'msg': 'Carrito vacío.'})

    total     = 0
    ganancia  = 0
    detalle   = []
    errores   = []

    try:
        for item in items:
            p    = db.session.get(Repuesto, item['id'])
            cant = int(item['cantidad'])
            if not p:
                errores.append(f'Producto #{item["id"]} no encontrado.')
                continue
            if p.stock < cant:
                errores.append(f'Stock insuficiente: {p.nombre} ({p.stock} disponibles).')
                continue

            g         = (p.p_venta - p.p_costo) * cant
            ant       = p.stock
            p.stock  -= cant
            p.vendido += cant
            total    += p.p_venta * cant
            ganancia += g

            db.session.add(Venta(
                repuesto_id=p.id, usuario_id=uid,
                cantidad=cant, total_venta=p.p_venta*cant,
                ganancia_operacion=g
            ))
            db.session.add(HistorialStock(
                repuesto_id=p.id, usuario_id=uid,
                stock_anterior=ant, stock_nuevo=p.stock,
                accion='VENDIDO'
            ))
            detalle.append({
                'nombre':   p.nombre,
                'cantidad': cant,
                'precio':   p.p_venta,
                'subtotal': p.p_venta * cant
            })

        if errores and not detalle:
            return jsonify({'ok': False, 'msg': ' | '.join(errores)})

        db.session.commit()
        return jsonify({
            'ok':       True,
            'total':    total,
            'ganancia': ganancia,
            'detalle':  detalle,
            'errores':  errores,
            'hora':     datetime.utcnow().strftime('%H:%M:%S'),
            'cajero':   session.get('user_nombre', '—')
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'msg': str(e)})

@pos_bp.route('/pos/ventas_hoy')
def ventas_hoy():
    uid = session.get('user_id')
    hoy = datetime.utcnow().date()
    ventas = Venta.query.filter(
        Venta.usuario_id == uid,
        func.date(Venta.fecha) == hoy
    ).order_by(Venta.fecha.desc()).limit(20).all()

    total_hoy = sum(v.total_venta for v in ventas)
    return jsonify({
        'total':  total_hoy,
        'cant':   len(ventas),
        'ventas': [{
            'hora':     v.fecha.strftime('%H:%M'),
            'producto': v.repuesto.nombre if v.repuesto else '—',
            'cantidad': v.cantidad,
            'total':    v.total_venta
        } for v in ventas]
    })