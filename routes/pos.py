from flask import Blueprint, render_template, request, jsonify, session
from extensions import db
from models import Repuesto, Venta, HistorialStock
from sqlalchemy import func
from datetime import datetime
import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

pos_bp = Blueprint('pos', __name__)

def _enviar_email_venta(detalle, total, cliente, cajero, hora):
    """Envía notificación de venta al correo del admin."""
    try:
        smtp_user = os.environ.get('MAIL_USER','')
        smtp_pass = os.environ.get('MAIL_PASS','')
        dest      = os.environ.get('MAIL_DEST', 'cristhian_franco1994@hotmail.com')
        if not smtp_user or not smtp_pass:
            return  # Sin config de correo, skip silencioso

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'💰 Nueva venta DriveFlow — ${total:,.2f}'
        msg['From']    = smtp_user
        msg['To']      = dest

        items_html = ''.join(
            f'<tr><td style="padding:6px 12px">{d["cantidad"]}× {d["nombre"]}</td>'
            f'<td style="padding:6px 12px;text-align:right;color:#10b981;font-weight:700">${d["subtotal"]:.2f}</td></tr>'
            for d in detalle
        )
        html = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;background:#0f172a;color:#f1f5f9;border-radius:12px;padding:24px">
          <h2 style="color:#38bdf8;margin:0 0 16px">💰 Nueva Venta — DriveFlow PRO</h2>
          <p style="margin:4px 0;opacity:.7">🕐 {hora} &nbsp;|&nbsp; 👤 Cajero: {cajero}</p>
          <p style="margin:4px 0;opacity:.7">👥 Cliente: {cliente}</p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0">
            <thead><tr style="background:#1e293b">
              <th style="padding:8px 12px;text-align:left">Producto</th>
              <th style="padding:8px 12px;text-align:right">Subtotal</th>
            </tr></thead>
            <tbody>{items_html}</tbody>
          </table>
          <div style="text-align:right;font-size:1.4em;font-weight:700;color:#38bdf8">
            TOTAL: ${total:,.2f}
          </div>
        </div>"""

        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP('smtp-mail.outlook.com', 587) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, dest, msg.as_string())
    except Exception as e:
        print(f'⚠️ Email error: {e}')  # No interrumpe la venta

@pos_bp.route('/')
def index():
    return render_template('pos.html')

@pos_bp.route('/buscar')
def buscar():
    q = request.args.get('q','').upper().strip()
    if not q: return jsonify([])
    productos = Repuesto.query.filter(func.upper(Repuesto.nombre).contains(q)).limit(8).all()
    return jsonify([{
        'id':     p.id, 'nombre': p.nombre,
        'precio': p.p_venta, 'stock': p.stock,
        'estado': p.estado_stock,
        'foto':   f'/static/{p.foto_url}' if p.foto_url else None
    } for p in productos])

@pos_bp.route('/vender', methods=['POST'])
def vender():
    data             = request.get_json(silent=True) or {}
    items            = data.get('items', [])
    cliente_nombre   = data.get('cliente','').strip() or None
    cliente_whatsapp = data.get('whatsapp','').strip() or None
    uid              = session.get('user_id')

    if not items:
        return jsonify({'ok': False, 'msg': 'Carrito vacío.'})

    total = ganancia = 0
    detalle = []; errores = []

    try:
        for item in items:
            p    = db.session.get(Repuesto, item['id'])
            cant = int(item['cantidad'])
            if not p: errores.append(f'Producto #{item["id"]} no encontrado.'); continue
            if p.stock < cant: errores.append(f'Stock insuficiente: {p.nombre} ({p.stock} disp.)'); continue

            g = (p.p_venta - p.p_costo) * cant
            ant = p.stock; p.stock -= cant; p.vendido += cant
            total += p.p_venta * cant; ganancia += g

            db.session.add(Venta(
                repuesto_id=p.id, usuario_id=uid,
                cliente_nombre=cliente_nombre,
                cliente_whatsapp=cliente_whatsapp,
                cantidad=cant, total_venta=p.p_venta*cant,
                ganancia_operacion=g
            ))
            db.session.add(HistorialStock(
                repuesto_id=p.id, usuario_id=uid,
                stock_anterior=ant, stock_nuevo=p.stock, accion='VENDIDO'
            ))
            detalle.append({'nombre':p.nombre,'cantidad':cant,'precio':p.p_venta,'subtotal':p.p_venta*cant})

        if errores and not detalle:
            return jsonify({'ok': False, 'msg': ' | '.join(errores)})

        db.session.commit()
        hora   = datetime.utcnow().strftime('%H:%M:%S')
        cajero = session.get('user_nombre','—')

        # Enviar email en background (no bloquea respuesta)
        _enviar_email_venta(detalle, total, cliente_nombre or 'Cliente general', cajero, hora)

        return jsonify({
            'ok': True, 'total': total, 'ganancia': ganancia,
            'detalle': detalle, 'errores': errores,
            'hora': hora, 'cajero': cajero,
            'cliente':   cliente_nombre or 'Cliente general',
            'whatsapp':  cliente_whatsapp
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'msg': str(e)})

@pos_bp.route('/ventas_hoy')
def ventas_hoy():
    uid  = session.get('user_id')
    hoy  = datetime.utcnow().date()
    ventas = Venta.query.filter(
        Venta.usuario_id == uid,
        func.date(Venta.fecha) == hoy
    ).order_by(Venta.fecha.desc()).limit(20).all()
    total_hoy = sum(v.total_venta for v in ventas)
    return jsonify({
        'total': total_hoy, 'cant': len(ventas),
        'ventas': [{
            'hora':     v.fecha.strftime('%H:%M'),
            'producto': v.repuesto.nombre if v.repuesto else '—',
            'cliente':  v.cliente_nombre or '—',
            'cantidad': v.cantidad, 'total': v.total_venta
        } for v in ventas]
    })