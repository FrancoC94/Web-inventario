from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class Usuario(db.Model):
    __tablename__ = 'usuario'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    nombre        = db.Column(db.String(100), default='')
    rol           = db.Column(db.String(20), default='vendedor')  # admin | supervisor | cajero | vendedor
    activo        = db.Column(db.Boolean, default=True)
    creado_en     = db.Column(db.DateTime, default=datetime.utcnow)
    ventas        = db.relationship('Venta', backref='usuario', lazy=True, foreign_keys='Venta.usuario_id')

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)
    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def ventas_hoy(self):
        hoy = datetime.utcnow().date()
        from sqlalchemy import func
        return Venta.query.filter(
            Venta.usuario_id == self.id,
            func.date(Venta.fecha) == hoy
        ).count()

    @property
    def total_ventas(self):
        from extensions import db as _db
        from sqlalchemy import func
        r = _db.session.query(func.sum(Venta.total_venta)).filter(Venta.usuario_id == self.id).scalar()
        return r or 0

class Repuesto(db.Model):
    __tablename__ = 'repuesto'
    id           = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(100), nullable=False, unique=True)
    p_costo      = db.Column(db.Float, nullable=False)
    p_venta      = db.Column(db.Float, nullable=False)
    stock        = db.Column(db.Integer, nullable=False, default=0)
    vendido      = db.Column(db.Integer, default=0)
    stock_minimo = db.Column(db.Integer, default=5)
    ventas    = db.relationship('Venta', backref='repuesto', cascade='all, delete-orphan', lazy=True)
    historial = db.relationship('HistorialStock', backref='repuesto', cascade='all, delete-orphan', lazy=True)

    @property
    def estado_stock(self):
        if self.stock == 0:                     return 'agotado'
        if self.stock <= self.stock_minimo:     return 'critico'
        if self.stock <= self.stock_minimo * 2: return 'bajo'
        return 'ok'

class Venta(db.Model):
    __tablename__ = 'venta'
    id                 = db.Column(db.Integer, primary_key=True)
    repuesto_id        = db.Column(db.Integer, db.ForeignKey('repuesto.id', ondelete='CASCADE'), nullable=False)
    usuario_id         = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    cantidad           = db.Column(db.Integer, nullable=False)
    total_venta        = db.Column(db.Float, nullable=False)
    ganancia_operacion = db.Column(db.Float, nullable=False)
    fecha              = db.Column(db.DateTime, default=datetime.utcnow)

class HistorialStock(db.Model):
    __tablename__ = 'historial_stock'
    id             = db.Column(db.Integer, primary_key=True)
    repuesto_id    = db.Column(db.Integer, db.ForeignKey('repuesto.id', ondelete='CASCADE'), nullable=False)
    usuario_id     = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    fecha          = db.Column(db.DateTime, default=datetime.utcnow)
    stock_anterior = db.Column(db.Integer, nullable=False)
    stock_nuevo    = db.Column(db.Integer, nullable=False)
    accion         = db.Column(db.String(50), nullable=False)
    usuario        = db.relationship('Usuario', foreign_keys=[usuario_id], lazy=True)