from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import Usuario

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('inventario.inicio'))
    if request.method == 'POST':
        u = request.form.get('username','').strip()
        p = request.form.get('password','')
        user = Usuario.query.filter_by(username=u, activo=True).first()
        if user and user.check_password(p):
            session['user_id']     = user.id
            session['user_nombre'] = user.nombre or user.username
            session['user_rol']    = user.rol
            flash(f'Bienvenido, {user.nombre or user.username}!', 'success')
            return redirect(url_for('inventario.inicio'))
        flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))