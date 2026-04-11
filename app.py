import os
from flask import Flask, session, redirect, url_for, request, send_from_directory
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from extensions import db

load_dotenv()


def create_app():
    app = Flask(__name__)

    default_db = (
        "sqlite:////data/driveflow.db"
        if os.path.isdir("/data")
        else "sqlite:///driveflow.db"
    )

    db_url = os.environ.get("DATABASE_URL", default_db)

    if db_url.startswith("mysql://"):
        db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    app.secret_key = os.environ.get("SECRET_KEY", "driveflow-secret-2026")

    db.init_app(app)

    try:
        with app.app_context():
            db.session.execute(text("SELECT 1"))
    except OperationalError:
        print("⚠️ No se pudo conectar a DATABASE_URL, usando SQLite temporal")
        app.config["SQLALCHEMY_DATABASE_URI"] = default_db

    from routes.auth import auth_bp
    from routes.inventario import inventario_bp
    from routes.ventas import ventas_bp
    from routes.asistente import asistente_bp
    from routes.usuarios import usuarios_bp
    from routes.historial import historial_bp
    from routes.pos import pos_bp
    from routes.reportes import reportes_bp
    from routes.proveedores import proveedores_bp
    from routes.caja import caja_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(asistente_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(historial_bp)
    app.register_blueprint(pos_bp, url_prefix="/pos")
    app.register_blueprint(reportes_bp)
    app.register_blueprint(proveedores_bp)
    app.register_blueprint(caja_bp)

    @app.route("/sw.js")
    def sw():
        return send_from_directory(
            app.static_folder,
            "sw.js",
            mimetype="application/javascript",
        )

    @app.route("/manifest.json")
    def manifest():
        return send_from_directory(
            app.static_folder,
            "manifest.json",
            mimetype="application/manifest+json",
        )

    @app.before_request
    def require_login():
        endpoint = request.endpoint or ""
        libres = {"auth.login", "auth.logout", "sw", "manifest", "static"}

        if endpoint and endpoint not in libres and not endpoint.startswith("static"):
            if "user_id" not in session:
                return redirect(url_for("auth.login"))

    with app.app_context():
        from models import Usuario

        db.create_all()

        if not Usuario.query.filter_by(username="admin").first():
            admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
            u = Usuario(
                username="admin",
                nombre="Administrador",
                rol="admin",
            )
            u.set_password(admin_pass)
            db.session.add(u)
            db.session.commit()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)