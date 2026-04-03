from flask import Blueprint, redirect, url_for, flash, request, session
from extensions import db
from models import Repuesto, Venta, HistorialStock

ventas_bp = Blueprint('ventas', __name__)

@ventas_bp.route('/vender/<int:id>', methods=['POST'])
def vender(id):
    try:
        p    = db.session.get(Repuesto, id)
        cant = int(request.form.get('cantidad_venta', 1))
        if not p: flash('No encontrado.', 'danger'); return redirect(url_for('inventario.inicio'))
        if cant <= 0: flash('Cantidad debe ser mayor a 0.', 'warning'); return redirect(url_for('inventario.inicio'))
        if p.stock < cant: flash(f'⚠️ Stock insuficiente. Disponible: {p.stock}', 'danger'); return redirect(url_for('inventario.inicio'))

        ganancia   = (p.p_venta - p.p_costo) * cant
        ant        = p.stock
        p.stock   -= cant
        p.vendido += cant
        uid        = session.get('user_id')

        db.session.add(Venta(repuesto_id=p.id, usuario_id=uid, cantidad=cant,
                             total_venta=p.p_venta*cant, ganancia_operacion=ganancia))
        db.session.add(HistorialStock(repuesto_id=p.id, usuario_id=uid,
                                      stock_anterior=ant, stock_nuevo=p.stock, accion='VENDIDO'))
        db.session.commit()
        flash(f'✅ Venta: {cant} × {p.nombre} = ${p.p_venta*cant:,.2f}', 'success')
    except ValueError:
        flash('❌ Cantidad inválida.', 'danger')
    except Exception as e:
        db.session.rollback(); flash(f'❌ {e}', 'danger')
    return redirect(url_for('inventario.inicio'))

@ventas_bp.route('/eliminar_venta/<int:id>')
def eliminar_venta(id):
    # Solo admin puede anular
    if session.get('user_rol') not in ('admin',):
        flash('⛔ Solo administradores pueden anular ventas.', 'danger')
        return redirect(url_for('inventario.inicio'))
    try:
        v = db.session.get(Venta, id)
        if not v: flash('Venta no encontrada.', 'danger'); return redirect(url_for('inventario.inicio'))
        if v.repuesto:
            ant = v.repuesto.stock
            v.repuesto.stock   += v.cantidad
            v.repuesto.vendido  = max(0, v.repuesto.vendido - v.cantidad)
            db.session.add(HistorialStock(repuesto_id=v.repuesto.id, usuario_id=session.get('user_id'),
                                          stock_anterior=ant, stock_nuevo=v.repuesto.stock, accion='ANULADO'))
        db.session.delete(v); db.session.commit()
        flash('↩️ Venta anulada y stock restaurado.', 'success')
    except Exception as e:
        db.session.rollback(); flash(f'❌ {e}', 'danger')
    return redirect(url_for('inventario.inicio'))