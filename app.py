import os
from flask import Flask, session, redirect, url_for, request, send_from_directory
from extensions import db
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

def create_app():
    app = Flask(__name__)

    # ── Configuración de Base de Datos ────────────────
    # En local usa tu MariaDB del .env, en Render usa la Variable de Entorno
    default_db = 'sqlite:///driveflow.db'
    db_url = os.environ.get('DATABASE_URL', default_db)

    # Corrección automática de protocolos para SQLAlchemy
    if db_url.startswith('mysql://'):
        # Cambia mysql:// a mysql+mysqlconnector:// para MariaDB/MySQL
        db_url = db_url.replace('mysql://', 'mysql+mysqlconnector://', 1)
    elif db_url.startswith('postgres://'):
        # Render a veces entrega postgres:// pero SQLAlchemy pide postgresql://
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    app.config['SQLALCHEMY_DATABASE_URI']        = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS']      = {'pool_recycle': 280, 'pool_pre_ping': True}
    app.config['MAX_CONTENT_LENGTH']             = 5 * 1024 * 1024
    app.secret_key = os.environ.get('SECRET_KEY', 'driveflow-secret-2026')

    # Inicializar la base de datos con la app
    db.init_app(app)

    # ── Registro de Blueprints ────────────────────────
    from routes.auth        import auth_bp
    from routes.inventario  import inventario_bp
    from routes.ventas      import ventas_bp
    from routes.asistente   import asistente_bp
    from routes.usuarios    import usuarios_bp
    from routes.historial   import historial_bp
    from routes.pos         import pos_bp
    from routes.reportes    import reportes_bp
    from routes.proveedores import proveedores_bp
    from routes.caja        import caja_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(asistente_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(historial_bp)
    app.register_blueprint(pos_bp, url_prefix='/pos')
    app.register_blueprint(reportes_bp)
    app.register_blueprint(proveedores_bp)
    app.register_blueprint(caja_bp)

    # ── Rutas para PWA ────────────────────────────────
    @app.route('/sw.js')
    def sw():
        return send_from_directory(app.static_folder, 'sw.js', mimetype='application/javascript')

    @app.route('/manifest.json')
    def manifest():
        return send_from_directory(app.static_folder, 'manifest.json', mimetype='application/manifest+json')

    # ── Middleware: Protección de rutas ───────────────
    @app.before_request
    def require_login():
        endpoint = request.endpoint or ''
        libres = {'auth.login', 'auth.logout', 'sw', 'manifest', 'static'}
        if endpoint not in libres and not endpoint.startswith('static'):
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))

    # ── Configuración Inicial (Tablas y Admin) ────────
    with app.app_context():
        from models import Usuario
        db.create_all()
        # Crear admin por defecto si no existe
        if not Usuario.query.filter_by(username='admin').first():
            u = Usuario(username='admin', nombre='Administrador', rol='admin')
            u.set_password('admin123')
            db.session.add(u)
            db.session.commit()
            print('✅ Base de datos sincronizada y usuario admin verificado.')

    return app

# ── INSTANCIA GLOBAL (Obligatorio para Render/Gunicorn) ──
app = create_app()

# ── Punto de entrada para ejecución local ───────────
if __name__ == '__main__':
    # Render asigna un puerto automáticamente en la variable PORT
    port = int(os.environ.get('PORT', 5050))
    # debug=True solo se activa si corres el archivo directamente en tu PC
    app.run(host='0.0.0.0', port=port, debug=True)