import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func
from datetime import datetime
from extensions import db
from models import Repuesto, Venta, HistorialStock

inventario_bp = Blueprint('inventario', __name__)

# Roles que pueden ver costos, editar y eliminar
ROLES_PRIVILEGIADOS = ('admin', 'supervisor')

def puede_ver_costos():
    return session.get('user_rol') in ROLES_PRIVILEGIADOS

def _historial(repuesto_id, ant, nuevo, accion):
    uid = session.get('user_id')
    db.session.add(HistorialStock(
        repuesto_id=repuesto_id, usuario_id=uid,
        stock_anterior=ant, stock_nuevo=nuevo, accion=accion
    ))

def _stats():
    hoy        = datetime.utcnow().date()
    ventas_hoy = Venta.query.filter(func.date(Venta.fecha) == hoy).all()
    total_hoy  = sum(v.total_venta for v in ventas_hoy)
    top = (db.session.query(Venta.repuesto_id, func.sum(Venta.ganancia_operacion).label('g'))
           .group_by(Venta.repuesto_id).order_by(db.text('g DESC')).first())
    estrella  = db.session.get(Repuesto, top[0]).nombre if top else 'Sin datos'
    todos     = Repuesto.query.all()
    faltantes = [p for p in todos if p.stock < 10]
    # Solo mostrar inversión a privilegiados
    inversion = sum(p.p_costo * p.stock for p in todos) if puede_ver_costos() else None
    return dict(
        total_hoy=total_hoy, estrella=estrella,
        inversion=inversion,
        ganancia=db.session.query(func.sum(Venta.ganancia_operacion)).scalar() or 0,
        inversion_sugerida=sum((10 - p.stock) * p.p_costo for p in faltantes) if puede_ver_costos() else None,
        alertas=[p for p in todos if p.stock <= p.stock_minimo],
        puede_costos=puede_ver_costos(),
    )

@inventario_bp.route('/')
def inicio():
    busqueda   = request.args.get('buscar', '').upper().strip()
    inventario = (Repuesto.query.filter(func.upper(Repuesto.nombre).contains(busqueda)).all()
                  if busqueda else Repuesto.query.all())
    ventas = Venta.query.order_by(Venta.fecha.desc()).limit(15).all()
    return render_template('index.html', inventario=inventario, ventas=ventas, **_stats())

@inventario_bp.route('/agregar', methods=['POST'])
def agregar():
    if not puede_ver_costos():
        flash('⛔ Sin permiso para agregar productos.', 'danger')
        return redirect(url_for('inventario.inicio'))
    try:
        nombre  = request.form['nombre'].upper().strip()
        p_costo = float(request.form['p_costo'])
        p_venta = float(request.form['p_venta'])
        stock   = int(request.form['stock'])
        if p_costo <= 0 or p_venta <= 0 or stock < 0:
            flash('Los valores deben ser positivos.', 'warning')
            return redirect(url_for('inventario.inicio'))
        p = Repuesto.query.filter_by(nombre=nombre).first()
        if p:
            ant = p.stock; p.stock += stock; p.p_costo = p_costo; p.p_venta = p_venta
            _historial(p.id, ant, p.stock, 'AGREGADO')
        else:
            p = Repuesto(nombre=nombre, p_costo=p_costo, p_venta=p_venta, stock=stock)
            db.session.add(p); db.session.flush()
            _historial(p.id, 0, stock, 'AGREGADO')
        db.session.commit()
        flash(f'✅ {nombre} registrado.', 'success')
    except ValueError:
        flash('❌ Formato numérico incorrecto.', 'danger')
    except Exception as e:
        db.session.rollback(); flash(f'❌ Error: {e}', 'danger')
    return redirect(url_for('inventario.inicio'))

@inventario_bp.route('/editar/<int:id>', methods=['POST'])
def editar(id):
    if not puede_ver_costos():
        flash('⛔ Sin permiso para editar productos.', 'danger')
        return redirect(url_for('inventario.inicio'))
    try:
        p = db.session.get(Repuesto, id)
        if not p: flash('No encontrado.', 'danger'); return redirect(url_for('inventario.inicio'))
        ant = p.stock
        p.nombre  = request.form['nombre'].upper().strip()
        p.p_costo = float(request.form['p_costo'])
        p.p_venta = float(request.form['p_venta'])
        p.stock   = int(request.form['stock'])
        _historial(p.id, ant, p.stock, 'EDITADO')
        db.session.commit(); flash(f'✅ {p.nombre} actualizado.', 'success')
    except ValueError:
        flash('❌ Formato incorrecto.', 'danger')
    except Exception as e:
        db.session.rollback(); flash(f'❌ {e}', 'danger')
    return redirect(url_for('inventario.inicio'))

@inventario_bp.route('/eliminar_producto/<int:id>')
def eliminar_producto(id):
    if not puede_ver_costos():
        flash('⛔ Sin permiso para eliminar productos.', 'danger')
        return redirect(url_for('inventario.inicio'))
    try:
        p = db.session.get(Repuesto, id)
        if not p: flash('No encontrado.', 'danger'); return redirect(url_for('inventario.inicio'))
        db.session.delete(p); db.session.commit()
        flash(f'🗑️ {p.nombre} eliminado.', 'success')
    except Exception as e:
        db.session.rollback(); flash(f'❌ {e}', 'danger')
    return redirect(url_for('inventario.inicio'))

@inventario_bp.route('/subir_masivo', methods=['POST'])
def subir_masivo():
    if not puede_ver_costos():
        flash('⛔ Sin permiso para cargar Excel.', 'danger')
        return redirect(url_for('inventario.inicio'))
    file = request.files.get('archivo_excel')
    if not file: flash('No se seleccionó archivo.', 'warning'); return redirect(url_for('inventario.inicio'))
    try:
        df = pd.read_excel(file)
        for _, row in df.iterrows():
            nom = str(row['nombre']).upper().strip()
            p   = Repuesto.query.filter_by(nombre=nom).first()
            if p:
                ant = p.stock; p.stock += int(row['stock'])
                p.p_costo = float(row['p_costo']); p.p_venta = float(row['p_venta'])
                _historial(p.id, ant, p.stock, 'AGREGADO')
            else:
                p = Repuesto(nombre=nom, p_costo=float(row['p_costo']),
                             p_venta=float(row['p_venta']), stock=int(row['stock']))
                db.session.add(p); db.session.flush()
                _historial(p.id, 0, int(row['stock']), 'AGREGADO')
        db.session.commit(); flash('📁 Excel cargado correctamente.', 'success')
    except Exception as e:
        db.session.rollback(); flash(f'❌ Error Excel: {e}', 'danger')
    return redirect(url_for('inventario.inicio'))

@inventario_bp.route('/exportar_compras')
def exportar_compras():
    faltantes = Repuesto.query.filter(Repuesto.stock < 10).all()
    if not faltantes: return '✅ Inventario al día.'
    return '\n'.join(['🛒 PEDIDO DRIVEFLOW PRO'] + [f'• {p.nombre}: Pedir {10-p.stock} uds' for p in faltantes])