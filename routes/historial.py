from flask import Blueprint, render_template, request, session, redirect, url_for
from models import HistorialStock, Repuesto, Usuario
from extensions import db
from sqlalchemy import func
from datetime import datetime, timedelta

historial_bp = Blueprint('historial', __name__)

@historial_bp.route('/historial')
def index():
    # Filtros
    accion   = request.args.get('accion', '')
    producto = request.args.get('producto', '').upper().strip()
    dias     = int(request.args.get('dias', 30))
    page     = int(request.args.get('page', 1))
    per_page = 25

    desde = datetime.utcnow() - timedelta(days=dias)
    query = HistorialStock.query.filter(HistorialStock.fecha >= desde)

    if accion:
        query = query.filter(HistorialStock.accion == accion)

    if producto:
        ids = [p.id for p in Repuesto.query.filter(
            func.upper(Repuesto.nombre).contains(producto)).all()]
        if ids:
            query = query.filter(HistorialStock.repuesto_id.in_(ids))
        else:
            query = query.filter(db.false())

    total     = query.count()
    registros = query.order_by(HistorialStock.fecha.desc())\
                     .offset((page-1)*per_page).limit(per_page).all()
    total_pags = max(1, (total + per_page - 1) // per_page)

    # Stats rápidas
    stats = {
        'total':    HistorialStock.query.filter(HistorialStock.fecha >= desde).count(),
        'vendidos': HistorialStock.query.filter(HistorialStock.fecha >= desde,
                    HistorialStock.accion == 'VENDIDO').count(),
        'agregados':HistorialStock.query.filter(HistorialStock.fecha >= desde,
                    HistorialStock.accion == 'AGREGADO').count(),
        'anulados': HistorialStock.query.filter(HistorialStock.fecha >= desde,
                    HistorialStock.accion == 'ANULADO').count(),
        'editados': HistorialStock.query.filter(HistorialStock.fecha >= desde,
                    HistorialStock.accion == 'EDITADO').count(),
    }

    return render_template('historial.html',
        registros=registros, stats=stats,
        accion=accion, producto=producto, dias=dias,
        page=page, total_pags=total_pags, total=total)