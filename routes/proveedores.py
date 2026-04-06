from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import db
from models import Proveedor, OrdenCompra, Repuesto, HistorialStock
from datetime import datetime
from sqlalchemy import func

proveedores_bp = Blueprint('proveedores', __name__)

ROLES_PRIVILEGIADOS = ('admin', 'supervisor')

def puede_gestionar():
    return session.get('user_rol') in ROLES_PRIVILEGIADOS

# ── Lista de proveedores ───────────────────────────────────
@proveedores_bp.route('/proveedores')
def lista():
    busqueda   = request.args.get('q', '').strip()
    query      = Proveedor.query
    if busqueda:
        query = query.filter(
            db.or_(
                Proveedor.nombre.ilike(f'%{busqueda}%'),
                Proveedor.empresa.ilike(f'%{busqueda}%')
            )
        )
    proveedores = query.order_by(Proveedor.nombre).all()
    return render_template('proveedores.html',
                           proveedores=proveedores,
                           busqueda=busqueda,
                           puede_gestionar=puede_gestionar())

# ── Crear proveedor ────────────────────────────────────────
@proveedores_bp.route('/proveedores/crear', methods=['POST'])
def crear():
    if not puede_gestionar():
        flash('⛔ Sin permiso.', 'danger')
        return redirect(url_for('proveedores.lista'))
    try:
        p = Proveedor(
            nombre    = request.form['nombre'].strip(),
            empresa   = request.form.get('empresa','').strip(),
            telefono  = request.form.get('telefono','').strip(),
            whatsapp  = request.form.get('whatsapp','').strip(),
            email     = request.form.get('email','').strip(),
            direccion = request.form.get('direccion','').strip(),
            notas     = request.form.get('notas','').strip(),
        )
        db.session.add(p)
        db.session.commit()
        flash(f'✅ Proveedor "{p.nombre}" creado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {e}', 'danger')
    return redirect(url_for('proveedores.lista'))

# ── Editar proveedor ───────────────────────────────────────
@proveedores_bp.route('/proveedores/editar/<int:id>', methods=['POST'])
def editar(id):
    if not puede_gestionar():
        flash('⛔ Sin permiso.', 'danger')
        return redirect(url_for('proveedores.lista'))
    try:
        p = db.session.get(Proveedor, id)
        if not p: flash('No encontrado.', 'danger'); return redirect(url_for('proveedores.lista'))
        p.nombre    = request.form['nombre'].strip()
        p.empresa   = request.form.get('empresa','').strip()
        p.telefono  = request.form.get('telefono','').strip()
        p.whatsapp  = request.form.get('whatsapp','').strip()
        p.email     = request.form.get('email','').strip()
        p.direccion = request.form.get('direccion','').strip()
        p.notas     = request.form.get('notas','').strip()
        p.activo    = request.form.get('activo') == '1'
        db.session.commit()
        flash(f'✅ {p.nombre} actualizado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ {e}', 'danger')
    return redirect(url_for('proveedores.lista'))

# ── Eliminar proveedor ─────────────────────────────────────
@proveedores_bp.route('/proveedores/eliminar/<int:id>')
def eliminar(id):
    if not puede_gestionar():
        flash('⛔ Sin permiso.', 'danger')
        return redirect(url_for('proveedores.lista'))
    try:
        p = db.session.get(Proveedor, id)
        if not p: flash('No encontrado.', 'danger'); return redirect(url_for('proveedores.lista'))
        db.session.delete(p)
        db.session.commit()
        flash(f'🗑️ {p.nombre} eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ {e}', 'danger')
    return redirect(url_for('proveedores.lista'))

# ── Detalle proveedor + sus órdenes ───────────────────────
@proveedores_bp.route('/proveedores/<int:id>')
def detalle(id):
    p      = db.session.get(Proveedor, id)
    if not p: flash('No encontrado.', 'danger'); return redirect(url_for('proveedores.lista'))
    ordenes = OrdenCompra.query.filter_by(proveedor_id=id)\
                               .order_by(OrdenCompra.fecha_pedido.desc()).all()
    repuestos = Repuesto.query.order_by(Repuesto.nombre).all()
    return render_template('proveedor_detalle.html',
                           p=p, ordenes=ordenes, repuestos=repuestos,
                           puede_gestionar=puede_gestionar())

# ── Crear orden de compra ─────────────────────────────────
@proveedores_bp.route('/proveedores/<int:id>/orden', methods=['POST'])
def crear_orden(id):
    if not puede_gestionar():
        flash('⛔ Sin permiso.', 'danger')
        return redirect(url_for('proveedores.detalle', id=id))
    try:
        cant  = int(request.form['cantidad'])
        precio = float(request.form['precio_unitario'])
        rep_id = request.form.get('repuesto_id') or None
        if rep_id: rep_id = int(rep_id)

        # Nombre del producto
        nombre = request.form.get('producto_nombre','').strip()
        if not nombre and rep_id:
            r = db.session.get(Repuesto, rep_id)
            nombre = r.nombre if r else 'Sin nombre'

        o = OrdenCompra(
            proveedor_id    = id,
            repuesto_id     = rep_id,
            usuario_id      = session.get('user_id'),
            producto_nombre = nombre,
            cantidad        = cant,
            precio_unitario = precio,
            total           = cant * precio,
            notas           = request.form.get('notas','').strip(),
        )
        db.session.add(o)
        db.session.commit()
        flash(f'✅ Orden creada: {cant} × {nombre}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ {e}', 'danger')
    return redirect(url_for('proveedores.detalle', id=id))

# ── Marcar orden como recibida ────────────────────────────
@proveedores_bp.route('/proveedores/orden/<int:id>/recibir', methods=['POST'])
def recibir_orden(id):
    if not puede_gestionar():
        flash('⛔ Sin permiso.', 'danger')
        return redirect(url_for('proveedores.lista'))
    try:
        o = db.session.get(OrdenCompra, id)
        if not o: flash('Orden no encontrada.', 'danger'); return redirect(url_for('proveedores.lista'))

        o.estado         = 'recibido'
        o.fecha_recibido = datetime.utcnow()

        # Actualizar stock del repuesto si está vinculado
        if o.repuesto_id:
            r = db.session.get(Repuesto, o.repuesto_id)
            if r:
                ant      = r.stock
                r.stock += o.cantidad
                r.p_costo = o.precio_unitario  # actualizar costo
                db.session.add(HistorialStock(
                    repuesto_id=r.id, usuario_id=session.get('user_id'),
                    stock_anterior=ant, stock_nuevo=r.stock,
                    accion='COMPRA'
                ))

        db.session.commit()
        flash(f'✅ Orden recibida. Stock actualizado automáticamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ {e}', 'danger')
    return redirect(url_for('proveedores.detalle', id=o.proveedor_id))

# ── Cancelar orden ─────────────────────────────────────────
@proveedores_bp.route('/proveedores/orden/<int:id>/cancelar')
def cancelar_orden(id):
    if not puede_gestionar():
        return redirect(url_for('proveedores.lista'))
    o = db.session.get(OrdenCompra, id)
    if o:
        o.estado = 'cancelado'
        db.session.commit()
        flash('↩️ Orden cancelada.', 'success')
    return redirect(url_for('proveedores.detalle', id=o.proveedor_id))

# ── API: buscar repuestos para autocomplete ────────────────
@proveedores_bp.route('/proveedores/api/repuestos')
def api_repuestos():
    q = request.args.get('q','').upper()
    r = Repuesto.query.filter(func.upper(Repuesto.nombre).contains(q)).limit(8).all()
    return jsonify([{'id': p.id, 'nombre': p.nombre, 'costo': p.p_costo, 'stock': p.stock} for p in r])