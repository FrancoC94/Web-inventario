from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class Usuario(db.Model):
    __tablename__ = 'usuario'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    nombre        = db.Column(db.String(100), default='')
    rol           = db.Column(db.String(20), default='vendedor')  # admin|supervisor|cajero|vendedor
    activo        = db.Column(db.Boolean, default=True)
    creado_en     = db.Column(db.DateTime, default=datetime.utcnow)
    ventas        = db.relationship('Venta', backref='usuario', lazy=True, foreign_keys='Venta.usuario_id')

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)
    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

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
    foto_url     = db.Column(db.String(255), nullable=True)   # ← foto del producto
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
    cliente_nombre     = db.Column(db.String(100), nullable=True)
    cliente_whatsapp   = db.Column(db.String(20), nullable=True)   # ← WhatsApp opcional
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


class Proveedor(db.Model):
    __tablename__ = 'proveedor'
    id            = db.Column(db.Integer, primary_key=True)
    nombre        = db.Column(db.String(100), nullable=False)
    empresa       = db.Column(db.String(100), default='')
    telefono      = db.Column(db.String(30),  default='')
    whatsapp      = db.Column(db.String(30),  default='')
    email         = db.Column(db.String(100), default='')
    direccion     = db.Column(db.String(200), default='')
    notas         = db.Column(db.Text,        default='')
    activo        = db.Column(db.Boolean,     default=True)
    creado_en     = db.Column(db.DateTime,    default=datetime.utcnow)
    ordenes       = db.relationship('OrdenCompra', backref='proveedor', cascade='all, delete-orphan', lazy=True)

    @property
    def total_comprado(self):
        return sum(o.total for o in self.ordenes if o.estado == 'recibido')

    @property
    def ordenes_pendientes(self):
        return sum(1 for o in self.ordenes if o.estado == 'pendiente')


class OrdenCompra(db.Model):
    __tablename__ = 'orden_compra'
    id            = db.Column(db.Integer, primary_key=True)
    proveedor_id  = db.Column(db.Integer, db.ForeignKey('proveedor.id', ondelete='CASCADE'), nullable=False)
    repuesto_id   = db.Column(db.Integer, db.ForeignKey('repuesto.id', ondelete='SET NULL'), nullable=True)
    usuario_id    = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    producto_nombre = db.Column(db.String(100), nullable=False)
    cantidad      = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(db.Float,   nullable=False, default=0)
    total         = db.Column(db.Float,     nullable=False, default=0)
    estado        = db.Column(db.String(20), default='pendiente')  # pendiente | recibido | cancelado
    notas         = db.Column(db.Text,      default='')
    fecha_pedido  = db.Column(db.DateTime,  default=datetime.utcnow)
    fecha_recibido = db.Column(db.DateTime, nullable=True)
    repuesto      = db.relationship('Repuesto', foreign_keys=[repuesto_id], lazy=True)
    usuario       = db.relationship('Usuario',  foreign_keys=[usuario_id],  lazy=True)


class Caja(db.Model):
    __tablename__ = 'caja'
    id              = db.Column(db.Integer, primary_key=True)
    usuario_id      = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha_apertura  = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_cierre    = db.Column(db.DateTime, nullable=True)
    monto_apertura  = db.Column(db.Float, nullable=False, default=0)
    monto_cierre    = db.Column(db.Float, nullable=True)
    total_ventas    = db.Column(db.Float, default=0)
    total_efectivo  = db.Column(db.Float, nullable=True)
    diferencia      = db.Column(db.Float, nullable=True)
    notas_apertura  = db.Column(db.Text, default='')
    notas_cierre    = db.Column(db.Text, default='')
    estado          = db.Column(db.String(20), default='abierta')  # abierta | cerrada
    usuario         = db.relationship('Usuario', foreign_keys=[usuario_id], lazy=True)

    @property
    def duracion(self):
        fin = self.fecha_cierre or datetime.utcnow()
        diff = fin - self.fecha_apertura
        h = int(diff.total_seconds() // 3600)
        m = int((diff.total_seconds() % 3600) // 60)
        return f'{h}h {m}m'