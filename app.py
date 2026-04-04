import os
from flask import Flask, session, redirect, url_for, request, send_from_directory
from extensions import db

def create_app():
    app = Flask(__name__)

    default_db = 'sqlite:////data/driveflow.db' if os.path.isdir('/data') else 'sqlite:///driveflow.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', default_db)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = os.environ.get('SECRET_KEY', 'driveflow-secret-2026')

    db.init_app(app)

    from routes.auth import auth_bp
    from routes.inventario import inventario_bp
    from routes.ventas import ventas_bp
    from routes.asistente import asistente_bp
    from routes.usuarios import usuarios_bp
    from routes.historial import historial_bp
    from routes.pos import pos_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(asistente_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(historial_bp)
    app.register_blueprint(pos_bp)

    @app.route('/sw.js')
    def sw():
        return send_from_directory(
            app.static_folder,
            'sw.js',
            mimetype='application/javascript'
        )

    @app.route('/manifest.json')
    def manifest():
        return send_from_directory(
            app.static_folder,
            'manifest.json',
            mimetype='application/manifest+json'
        )

    @app.before_request
    def require_login():
        endpoint = request.endpoint or ''
        libres = {'auth.login', 'auth.logout', 'sw', 'manifest'}

        if endpoint not in libres and not endpoint.startswith('static'):
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))

    with app.app_context():
        db.create_all()

        from models import Usuario

        if not Usuario.query.filter_by(username='admin').first():
            u = Usuario(
                username='admin',
                nombre='Administrador',
                rol='admin'
            )
            u.set_password('admin123')
            db.session.add(u)
            db.session.commit()
            print('✅ Admin creado: admin / admin123')

    return app


# =====================================================
# 🔥 ESTA LÍNEA ES LA QUE TE FALTABA
# =====================================================
app = create_app()


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5050))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True
    )