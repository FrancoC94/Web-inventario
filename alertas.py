from flask import Blueprint, jsonify
from models import Repuesto

alertas_bp = Blueprint('alertas', __name__)

# ── Función para obtener alertas con severidad
def _obtener_alertas():
    productos = Repuesto.query.all()
    alertas = []
    for p in productos:
        if p.estado_stock == 'agotado':
            icono = '💀'
        elif p.estado_stock == 'critico':
            icono = '🔴'
        elif p.estado_stock == 'bajo':
            icono = '🟡'
        else:
            continue  # Stock ok, no alertar

        alertas.append({
            'id': p.id,
            'nombre': p.nombre,
            'stock': p.stock,
            'estado': p.estado_stock,
            'icono': icono
        })
    return alertas

# ── Ruta que devuelve alertas en JSON
@alertas_bp.route('/alertas', methods=['GET'])
def alertas():
    alertas = _obtener_alertas()
    return jsonify({
        'count': len(alertas),
        'alertas': alertas
    })