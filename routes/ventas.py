from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import Venta, Repuesto, HistorialStock
from sqlalchemy import func
from datetime import datetime, timedelta

ventas_bp = Blueprint('ventas', __name__)

# ── Página de ventas separada ──────────────────────────────
@ventas_bp.route('/ventas')
def lista():
    page     = int(request.args.get('page', 1))
    per_page = 30
    desde    = request.args.get('desde', '')
    hasta    = request.args.get('hasta', '')
    cliente  = request.args.get('cliente', '').strip()

    query = Venta.query

    if desde:
        try: query = query.filter(Venta.fecha >= datetime.strptime(desde, '%Y-%m-%d'))
        except: pass
    if hasta:
        try: query = query.filter(Venta.fecha <= datetime.strptime(hasta + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
        except: pass
    if cliente:
        query = query.filter(Venta.cliente_nombre.ilike(f'%{cliente}%'))

    total_registros = query.count()
    total_pags      = max(1, (total_registros + per_page - 1) // per_page)
    ventas          = query.order_by(Venta.fecha.desc())\
                           .offset((page-1)*per_page).limit(per_page).all()

    # Stats del período
    todas         = query.all()
    total_ventas  = sum(v.total_venta for v in todas)
    total_gan     = sum(v.ganancia_operacion for v in todas)

    # Stats de hoy siempre
    hoy          = datetime.utcnow().date()
    ventas_hoy   = Venta.query.filter(func.date(Venta.fecha) == hoy).all()
    total_hoy    = sum(v.total_venta for v in ventas_hoy)
    gan_hoy      = sum(v.ganancia_operacion for v in ventas_hoy)

    return render_template('ventas.html',
        ventas=ventas, page=page, total_pags=total_pags,
        total_registros=total_registros,
        total_ventas=total_ventas, total_gan=total_gan,
        total_hoy=total_hoy, gan_hoy=gan_hoy,
        desde=desde, hasta=hasta, cliente=cliente)

# ── Vender desde inventario ────────────────────────────────
@ventas_bp.route('/vender/<int:id>', methods=['POST'])
def vender(id):
    try:
        p    = db.session.get(Repuesto, id)
        cant = int(request.form.get('cantidad_venta', 1))
        if not p or p.stock < cant:
            flash('❌ Stock insuficiente.', 'danger')
            return redirect(url_for('inventario.inicio'))
        g = (p.p_venta - p.p_costo) * cant
        ant = p.stock; p.stock -= cant; p.vendido += cant
        db.session.add(Venta(
            repuesto_id=p.id, usuario_id=session.get('user_id'),
            cantidad=cant, total_venta=p.p_venta*cant, ganancia_operacion=g
        ))
        db.session.add(HistorialStock(
            repuesto_id=p.id, usuario_id=session.get('user_id'),
            stock_anterior=ant, stock_nuevo=p.stock, accion='VENDIDO'
        ))
        db.session.commit()
        flash(f'✅ Vendido: {cant} × {p.nombre} = ${p.p_venta*cant:,.2f}', 'success')
    except Exception as e:
        db.session.rollback(); flash(f'❌ {e}', 'danger')
    return redirect(url_for('inventario.inicio'))

# ── Anular venta ───────────────────────────────────────────
@ventas_bp.route('/eliminar_venta/<int:id>')
def eliminar_venta(id):
    if session.get('user_rol') not in ('admin', 'supervisor'):
        flash('⛔ Sin permiso para anular ventas.', 'danger')
        return redirect(url_for('ventas.lista'))
    try:
        v = db.session.get(Venta, id)
        if not v: flash('No encontrada.', 'danger'); return redirect(url_for('ventas.lista'))
        # Restaurar stock
        p = db.session.get(Repuesto, v.repuesto_id)
        if p:
            ant = p.stock; p.stock += v.cantidad; p.vendido -= v.cantidad
            db.session.add(HistorialStock(
                repuesto_id=p.id, usuario_id=session.get('user_id'),
                stock_anterior=ant, stock_nuevo=p.stock, accion='ANULADO'
            ))
        db.session.delete(v)
        db.session.commit()
        flash('↩️ Venta anulada y stock restaurado.', 'success')
    except Exception as e:
        db.session.rollback(); flash(f'❌ {e}', 'danger')
    return redirect(url_for('ventas.lista'))