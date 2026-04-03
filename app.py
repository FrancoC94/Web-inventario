import os
from flask import Flask, session, redirect, url_for, request, send_from_directory
from extensions import db


def create_app():
    app = Flask(__name__)

    # ── Configuración de Base de Datos ────────────────
    # En Render usará la variable DATABASE_URL. En tu PC usará driveflow.db
    default_db = 'sqlite:///driveflow.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', default_db)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Clave secreta para las sesiones (carrito, login, etc.)
    app.secret_key = os.environ.get('SECRET_KEY', 'driveflow-secret-2026')

    db.init_app(app)

    # ── Registro de Blueprints (Tus módulos) ──────────
    from routes.auth import auth_bp
    from routes.inventario import inventario_bp
    from routes.ventas import ventas_bp
    from routes.asistente import asistente_bp
    from routes.usuarios import usuarios_bp
    from routes.historial import historial_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(asistente_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(historial_bp)

    # ── Rutas para PWA (Instalar como App) ────────────
    @app.route('/sw.js')
    def sw():
        return send_from_directory(app.static_folder, 'sw.js',
                                   mimetype='application/javascript')

    @app.route('/manifest.json')
    def manifest():
        return send_from_directory(app.static_folder, 'manifest.json',
                                   mimetype='application/manifest+json')

    # ── Protector de Rutas (Login obligatorio) ────────
    @app.before_request
    def require_login():
        endpoint = request.endpoint or ''
        # Lista de páginas que NO necesitan contraseña
        libres = {'auth.login', 'auth.logout', 'sw', 'manifest', 'static'}

        if endpoint not in libres and not endpoint.startswith('static'):
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))

    # ── Auto-creación de tablas y Usuario Admin ───────
    with app.app_context():
        db.create_all()
        from models import Usuario
        if not Usuario.query.filter_by(username='admin').first():
            u = Usuario(username='admin', nombre='Administrador', rol='admin')
            u.set_password('admin123')
            db.session.add(u)
            db.session.commit()
            print('✅ Servidor Listo. Admin: admin / admin123')

    return app


# ======================================================
# CONFIGURACIÓN PARA EL SERVIDOR (RENDER/GUNICORN)
# ======================================================

# Esta línea crea la aplicación para que Render la vea
app = create_app()

if __name__ == '__main__':
    # Usamos host='0.0.0.0' para que sea visible en red local y en Render
    # El puerto lo elige Render automáticamente o usa el 5050
    port = int(os.environ.get("PORT", 5050))
    app.run(host='0.0.0.0', port=port, debug=True)