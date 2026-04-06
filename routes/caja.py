from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import db
from models import Caja, Venta, Usuario
from sqlalchemy import func
from datetime import datetime

caja_bp = Blueprint('caja', __name__)

def _caja_abierta():
    """Retorna la caja abierta del usuario actual, o None."""
    uid = session.get('user_id')
    return Caja.query.filter_by(usuario_id=uid, estado='abierta').first()

def _ventas_caja(caja):
    """Ventas del usuario durante el turno de la caja."""
    q = Venta.query.filter(
        Venta.usuario_id == caja.usuario_id,
        Venta.fecha >= caja.fecha_apertura
    )
    if caja.fecha_cierre:
        q = q.filter(Venta.fecha <= caja.fecha_cierre)
    return q.all()

# ── Panel de caja ──────────────────────────────────────────
@caja_bp.route('/caja')
def panel():
    uid    = session.get('user_id')
    abierta = _caja_abierta()
    historial = Caja.query.filter_by(usuario_id=uid)\
                          .order_by(Caja.fecha_apertura.desc()).limit(10).all()

    ventas_turno = []
    total_turno  = 0
    if abierta:
        ventas_turno = _ventas_caja(abierta)
        total_turno  = sum(v.total_venta for v in ventas_turno)

    return render_template('caja.html',
                           caja=abierta,
                           historial=historial,
                           ventas_turno=ventas_turno,
                           total_turno=total_turno)

# ── Abrir caja ─────────────────────────────────────────────
@caja_bp.route('/caja/abrir', methods=['POST'])
def abrir():
    uid = session.get('user_id')
    if _caja_abierta():
        flash('⚠️ Ya tienes una caja abierta.', 'warning')
        return redirect(url_for('caja.panel'))
    try:
        monto = float(request.form.get('monto_apertura', 0))
        notas = request.form.get('notas', '').strip()
        c = Caja(
            usuario_id     = uid,
            monto_apertura = monto,
            notas_apertura = notas,
            estado         = 'abierta'
        )
        db.session.add(c)
        db.session.commit()
        flash(f'✅ Caja abierta con ${monto:,.2f} de efectivo inicial.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {e}', 'danger')
    return redirect(url_for('caja.panel'))

# ── Cerrar caja ─────────────────────────────────────────────
@caja_bp.route('/caja/cerrar', methods=['POST'])
def cerrar():
    c = _caja_abierta()
    if not c:
        flash('No hay caja abierta.', 'warning')
        return redirect(url_for('caja.panel'))
    try:
        monto_cierre   = float(request.form.get('monto_cierre', 0))
        notas          = request.form.get('notas', '').strip()
        ventas_turno   = _ventas_caja(c)
        total_ventas   = sum(v.total_venta for v in ventas_turno)
        esperado       = c.monto_apertura + total_ventas
        diferencia     = monto_cierre - esperado

        c.fecha_cierre  = datetime.utcnow()
        c.monto_cierre  = monto_cierre
        c.total_ventas  = total_ventas
        c.total_efectivo = monto_cierre
        c.diferencia    = diferencia
        c.notas_cierre  = notas
        c.estado        = 'cerrada'
        db.session.commit()

        if abs(diferencia) < 0.01:
            flash(f'✅ Caja cerrada. Todo cuadra perfectamente.', 'success')
        elif diferencia > 0:
            flash(f'✅ Caja cerrada. Sobrante: ${diferencia:,.2f}', 'success')
        else:
            flash(f'⚠️ Caja cerrada. Faltante: ${abs(diferencia):,.2f}', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {e}', 'danger')
    return redirect(url_for('caja.panel'))

# ── Resumen caja (API) ─────────────────────────────────────
@caja_bp.route('/caja/resumen')
def resumen():
    c = _caja_abierta()
    if not c:
        return jsonify({'abierta': False})
    ventas = _ventas_caja(c)
    total  = sum(v.total_venta for v in ventas)
    return jsonify({
        'abierta':        True,
        'monto_apertura': c.monto_apertura,
        'total_ventas':   total,
        'num_ventas':     len(ventas),
        'esperado':       c.monto_apertura + total,
        'duracion':       c.duracion,
        'desde':          c.fecha_apertura.strftime('%H:%M')
    })

# ── Detalle caja histórica ─────────────────────────────────
@caja_bp.route('/caja/<int:id>')
def detalle(id):
    c = db.session.get(Caja, id)
    if not c or c.usuario_id != session.get('user_id'):
        flash('No encontrado.', 'danger')
        return redirect(url_for('caja.panel'))
    ventas = _ventas_caja(c)
    return render_template('caja_detalle.html', c=c, ventas=ventas)