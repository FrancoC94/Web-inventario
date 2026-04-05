from flask import Blueprint, make_response, request, session
from models import Venta, Repuesto
from extensions import db
from sqlalchemy import func
from datetime import datetime, timedelta
import io

reportes_bp = Blueprint('reportes', __name__)

@reportes_bp.route('/reportes/ventas_pdf')
def ventas_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT

        dias = int(request.args.get('dias', 30))
        desde = datetime.utcnow() - timedelta(days=dias)
        ventas = Venta.query.filter(Venta.fecha >= desde).order_by(Venta.fecha.desc()).all()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        styles  = getSampleStyleSheet()
        c_dark  = colors.HexColor('#0f172a')
        c_blue  = colors.HexColor('#38bdf8')
        c_green = colors.HexColor('#10b981')
        c_gray  = colors.HexColor('#64748b')
        c_light = colors.HexColor('#f1f5f9')

        title_style = ParagraphStyle('title', parent=styles['Title'],
                                     fontSize=22, textColor=c_dark, spaceAfter=4)
        sub_style   = ParagraphStyle('sub', parent=styles['Normal'],
                                     fontSize=10, textColor=c_gray, spaceAfter=16)

        story = []

        # Header
        story.append(Paragraph('DRIVEFLOW PRO', title_style))
        story.append(Paragraph(f'Reporte de Ventas — Últimos {dias} días · {datetime.utcnow().strftime("%d/%m/%Y %H:%M")}', sub_style))

        # Stats
        total_ventas   = sum(v.total_venta for v in ventas)
        total_ganancia = sum(v.ganancia_operacion for v in ventas)
        stats_data = [
            ['Total transacciones', 'Total vendido', 'Ganancia total'],
            [str(len(ventas)), f'${total_ventas:,.2f}', f'${total_ganancia:,.2f}']
        ]
        stats_table = Table(stats_data, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), c_dark),
            ('TEXTCOLOR',  (0,0), (-1,0), c_light),
            ('FONTSIZE',   (0,0), (-1,0), 9),
            ('FONTSIZE',   (0,1), (-1,1), 13),
            ('FONTNAME',   (0,1), (-1,1), 'Helvetica-Bold'),
            ('TEXTCOLOR',  (0,1), (0,1), c_dark),
            ('TEXTCOLOR',  (1,1), (1,1), c_blue),
            ('TEXTCOLOR',  (2,1), (2,1), c_green),
            ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
            ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0,1), (-1,1), [c_light]),
            ('GRID',       (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROUNDEDCORNERS', [4]),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 0.5*cm))

        # Tabla detalle
        headers = ['Fecha', 'Producto', 'Cliente', 'Cant.', 'Total', 'Cajero']
        rows    = [headers]
        for v in ventas:
            rows.append([
                v.fecha.strftime('%d/%m/%y %H:%M'),
                v.repuesto.nombre[:28] if v.repuesto else '—',
                (v.cliente_nombre or '—')[:20],
                str(v.cantidad),
                f'${v.total_venta:,.2f}',
                v.usuario.nombre[:16] if v.usuario else '—'
            ])

        col_w = [3.2*cm, 5.5*cm, 3.5*cm, 1.5*cm, 2.5*cm, 2.8*cm]
        det   = Table(rows, colWidths=col_w, repeatRows=1)
        det.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), c_dark),
            ('TEXTCOLOR',     (0,0), (-1,0), c_light),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 8),
            ('ALIGN',         (3,0), (-1,-1), 'CENTER'),
            ('ALIGN',         (4,1), (4,-1), 'RIGHT'),
            ('TEXTCOLOR',     (4,1), (4,-1), c_green),
            ('FONTNAME',      (4,1), (4,-1), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, c_light]),
            ('GRID',          (0,0), (-1,-1), 0.3, colors.HexColor('#e2e8f0')),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ]))
        story.append(det)

        doc.build(story)
        buffer.seek(0)

        resp = make_response(buffer.read())
        resp.headers['Content-Type'] = 'application/pdf'
        resp.headers['Content-Disposition'] = f'attachment; filename=ventas_driveflow_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
        return resp

    except ImportError:
        return '❌ Instala reportlab: pip install reportlab', 500
    except Exception as e:
        return f'❌ Error generando PDF: {e}', 500