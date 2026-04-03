from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import Usuario, Venta
from sqlalchemy import func
from datetime import datetime

usuarios_bp = Blueprint('usuarios', __name__)

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrap(*a, **kw):
        if session.get('user_rol') != 'admin':
            flash('⛔ Solo administradores pueden acceder.', 'danger')
            return redirect(url_for('inventario.inicio'))
        return f(*a, **kw)
    return wrap

# ── Panel de usuarios ──────────────────────────────
@usuarios_bp.route('/usuarios')
@admin_required
def lista():
    usuarios = Usuario.query.order_by(Usuario.creado_en.desc()).all()
    # Stats por usuario
    hoy = datetime.utcnow().date()
    stats = {}
    for u in usuarios:
        ventas_hoy   = Venta.query.filter(Venta.usuario_id == u.id, func.date(Venta.fecha) == hoy).all()
        total_hoy    = sum(v.total_venta for v in ventas_hoy)
        total_global = db.session.query(func.sum(Venta.total_venta)).filter(Venta.usuario_id == u.id).scalar() or 0
        total_ventas = Venta.query.filter(Venta.usuario_id == u.id).count()
        stats[u.id] = {'hoy': total_hoy, 'global': total_global, 'cant': total_ventas}
    return render_template('usuarios.html', usuarios=usuarios, stats=stats)

# ── Crear usuario ──────────────────────────────────
@usuarios_bp.route('/usuarios/crear', methods=['POST'])
@admin_required
def crear():
    try:
        username = request.form['username'].strip().lower()
        nombre   = request.form['nombre'].strip()
        rol      = request.form['rol']
        password = request.form['password']

        if not username or not password:
            flash('Usuario y contraseña son obligatorios.', 'warning')
            return redirect(url_for('usuarios.lista'))

        if Usuario.query.filter_by(username=username).first():
            flash(f'❌ El usuario "{username}" ya existe.', 'danger')
            return redirect(url_for('usuarios.lista'))

        if len(password) < 4:
            flash('❌ La contraseña debe tener al menos 4 caracteres.', 'warning')
            return redirect(url_for('usuarios.lista'))

        u = Usuario(username=username, nombre=nombre, rol=rol)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash(f'✅ Usuario "{username}" creado con rol {rol}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {e}', 'danger')
    return redirect(url_for('usuarios.lista'))

# ── Editar usuario ─────────────────────────────────
@usuarios_bp.route('/usuarios/editar/<int:id>', methods=['POST'])
@admin_required
def editar(id):
    try:
        u = db.session.get(Usuario, id)
        if not u:
            flash('Usuario no encontrado.', 'danger')
            return redirect(url_for('usuarios.lista'))

        # No permitir editar al propio admin logueado si cambia su rol
        if u.id == session['user_id'] and request.form['rol'] != 'admin':
            flash('⚠️ No puedes quitarte el rol de admin a ti mismo.', 'warning')
            return redirect(url_for('usuarios.lista'))

        u.nombre = request.form['nombre'].strip()
        u.rol    = request.form['rol']
        u.activo = request.form.get('activo') == '1'

        nueva_pw = request.form.get('password', '').strip()
        if nueva_pw:
            if len(nueva_pw) < 4:
                flash('❌ La contraseña debe tener al menos 4 caracteres.', 'warning')
                return redirect(url_for('usuarios.lista'))
            u.set_password(nueva_pw)

        db.session.commit()
        flash(f'✅ Usuario "{u.username}" actualizado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {e}', 'danger')
    return redirect(url_for('usuarios.lista'))

# ── Eliminar usuario ───────────────────────────────
@usuarios_bp.route('/usuarios/eliminar/<int:id>')
@admin_required
def eliminar(id):
    try:
        u = db.session.get(Usuario, id)
        if not u:
            flash('Usuario no encontrado.', 'danger')
            return redirect(url_for('usuarios.lista'))
        if u.id == session['user_id']:
            flash('⚠️ No puedes eliminar tu propia cuenta.', 'warning')
            return redirect(url_for('usuarios.lista'))
        if u.username == 'admin':
            flash('⚠️ No se puede eliminar el admin principal.', 'warning')
            return redirect(url_for('usuarios.lista'))
        db.session.delete(u)
        db.session.commit()
        flash(f'🗑️ Usuario "{u.username}" eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {e}', 'danger')
    return redirect(url_for('usuarios.lista'))

# ── Toggle activo/inactivo ─────────────────────────
@usuarios_bp.route('/usuarios/toggle/<int:id>')
@admin_required
def toggle(id):
    u = db.session.get(Usuario, id)
    if u and u.id != session['user_id']:
        u.activo = not u.activo
        db.session.commit()
        estado = 'activado' if u.activo else 'desactivado'
        flash(f'✅ Usuario "{u.username}" {estado}.', 'success')
    return redirect(url_for('usuarios.lista'))

# ── Mi perfil ──────────────────────────────────────
@usuarios_bp.route('/perfil', methods=['GET', 'POST'])
def perfil():
    u = db.session.get(Usuario, session['user_id'])
    if request.method == 'POST':
        try:
            nombre  = request.form['nombre'].strip()
            pw_act  = request.form.get('pw_actual', '')
            pw_new  = request.form.get('pw_nueva', '')

            if nombre:
                u.nombre = nombre
                session['user_nombre'] = nombre

            if pw_new:
                if not u.check_password(pw_act):
                    flash('❌ Contraseña actual incorrecta.', 'danger')
                    return redirect(url_for('usuarios.perfil'))
                if len(pw_new) < 4:
                    flash('❌ La nueva contraseña debe tener al menos 4 caracteres.', 'warning')
                    return redirect(url_for('usuarios.perfil'))
                u.set_password(pw_new)

            db.session.commit()
            flash('✅ Perfil actualizado.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error: {e}', 'danger')
        return redirect(url_for('usuarios.perfil'))

    # Stats del usuario
    hoy        = datetime.utcnow().date()
    ventas_hoy = Venta.query.filter(Venta.usuario_id == u.id, func.date(Venta.fecha) == hoy).all()
    total_hoy  = sum(v.total_venta for v in ventas_hoy)
    total_global = db.session.query(func.sum(Venta.total_venta)).filter(Venta.usuario_id == u.id).scalar() or 0
    ultimas = Venta.query.filter(Venta.usuario_id == u.id).order_by(Venta.fecha.desc()).limit(10).all()
    return render_template('perfil.html', u=u, total_hoy=total_hoy, total_global=total_global, ultimas=ultimas)