from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import db
from models import Gasto, Venta
from sqlalchemy import func
from datetime import datetime, timedelta

gastos_bp = Blueprint('gastos', __name__)

CATEGORIAS = ['arriendo','luz','agua','internet','salario','transporte','compras','otros']

def _stats_mes(año, mes):
    desde = datetime(año, mes, 1)
    hasta = (desde + timedelta(days=32)).replace(day=1)
    gastos = Gasto.query.filter(Gasto.fecha >= desde, Gasto.fecha < hasta).all()
    ventas = Venta.query.filter(Venta.fecha >= desde, Venta.fecha < hasta).all()
    total_gastos  = sum(g.monto for g in gastos)
    total_ventas  = sum(v.total_venta for v in ventas)
    total_ganancia = sum(v.ganancia_operacion for v in ventas)
    ganancia_neta  = total_ganancia - total_gastos
    return dict(
        gastos=gastos, total_gastos=total_gastos,
        total_ventas=total_ventas, total_ganancia=total_ganancia,
        ganancia_neta=ganancia_neta,
        por_categoria={c: sum(g.monto for g in gastos if g.categoria==c) for c in CATEGORIAS}
    )

@gastos_bp.route('/gastos')
def lista():
    año  = int(request.args.get('año',  datetime.utcnow().year))
    mes  = int(request.args.get('mes',  datetime.utcnow().month))
    cat  = request.args.get('cat', '')
    desde = datetime(año, mes, 1)
    hasta = (desde + timedelta(days=32)).replace(day=1)

    q = Gasto.query.filter(Gasto.fecha >= desde, Gasto.fecha < hasta)
    if cat: q = q.filter(Gasto.categoria == cat)
    gastos = q.order_by(Gasto.fecha.desc()).all()

    stats  = _stats_mes(año, mes)
    meses  = [(i, ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][i-1]) for i in range(1,13)]

    return render_template('gastos.html',
        gastos=gastos, stats=stats, categorias=CATEGORIAS,
        año=año, mes=mes, cat=cat, meses=meses,
        now=datetime.utcnow().strftime('%Y-%m-%d'))

@gastos_bp.route('/gastos/crear', methods=['POST'])
def crear():
    try:
        monto = float(request.form['monto'])
        if monto <= 0:
            flash('El monto debe ser mayor a 0.', 'warning')
            return redirect(url_for('gastos.lista'))
        g = Gasto(
            usuario_id  = session.get('user_id'),
            categoria   = request.form['categoria'],
            descripcion = request.form['descripcion'].strip(),
            monto       = monto,
            notas       = request.form.get('notas','').strip(),
            fecha       = datetime.strptime(request.form.get('fecha', datetime.utcnow().strftime('%Y-%m-%d')), '%Y-%m-%d')
        )
        db.session.add(g)
        db.session.commit()
        flash(f'✅ Gasto registrado: ${monto:,.2f}', 'success')
    except ValueError:
        flash('❌ Monto inválido.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {e}', 'danger')
    return redirect(url_for('gastos.lista'))

@gastos_bp.route('/gastos/eliminar/<int:id>')
def eliminar(id):
    try:
        g = db.session.get(Gasto, id)
        if not g: flash('No encontrado.', 'danger'); return redirect(url_for('gastos.lista'))
        db.session.delete(g); db.session.commit()
        flash('🗑️ Gasto eliminado.', 'success')
    except Exception as e:
        db.session.rollback(); flash(f'❌ {e}', 'danger')
    return redirect(url_for('gastos.lista'))

@gastos_bp.route('/gastos/api/chart')
def chart_data():
    año = int(request.args.get('año', datetime.utcnow().year))
    datos = []
    for mes in range(1, 13):
        s = _stats_mes(año, mes)
        datos.append({
            'mes':      ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][mes-1],
            'gastos':   round(s['total_gastos'], 2),
            'ganancia': round(s['total_ganancia'], 2),
            'neta':     round(s['ganancia_neta'], 2)
        })
    return jsonify(datos)