# scraper/reporter.py

import os
from xml.sax.saxutils import escape
from datetime import datetime, date, timedelta
from collections import defaultdict
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)

from .config import PDF_PATH, LOG_TXT_PATH, DIAS_BUSQUEDA

# Nombres de los días de la semana en español
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

def format_datetime(dt: datetime) -> str:
    """Devuelve 'DíaSemana, YYYY-MM-DD HH:MM:SS AM/PM'."""
    dia = DIAS_SEMANA[dt.weekday()]
    return f"{dia}, {dt.strftime('%Y-%m-%d %I:%M:%S %p')}"

def format_duration(start_ts: float, end_ts: float) -> str:
    """Formatea la duración de forma dinámica."""
    total = int(end_ts - start_ts)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h}h {m}min {s}s"
    if m > 0:
        return f"{m}min {s}s"
    return f"{s}s"

def generar_pdf(total_procesos, actes, errors, start_ts, end_ts):
    """
    total_procesos: int
    actes:   list of (numero, fecha, actuacion, anotacion, url)
    errors:  list of (numero, mensaje)
    start_ts, end_ts: floats
    """
    os.makedirs(os.path.dirname(PDF_PATH), exist_ok=True)
    doc = SimpleDocTemplate(PDF_PATH, pagesize=A4, title="Reporte de Actuaciones")
    styles = getSampleStyleSheet()

    # Estilo que envuelve texto y permite celdas altas
    styleWrap = ParagraphStyle(
        'wrap',
        parent=styles['Normal'],
        wordWrap='LTR',      # envuelve en espacios
        leading=12           # espacio entre líneas
    )

    elements = []

    # --- Encabezado con día de la semana, formato AM/PM y duración dinámica
    start_dt = datetime.fromtimestamp(start_ts)
    end_dt   = datetime.fromtimestamp(end_ts)

    # Rango de búsqueda
    cutoff_date = date.today() - timedelta(days=DIAS_BUSQUEDA)
    rango_text = (
        f"<b>RANGO DE BÚSQUEDA:</b> ÚLTIMOS {DIAS_BUSQUEDA} DÍAS "
        f"({cutoff_date.isoformat()} al {date.today().isoformat()})"
    )

    elements.append(Paragraph("REPORTE DIARIO DE ACTUACIONES", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(rango_text, styles['Normal']))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        f"<b>INICIO:</b> {format_datetime(start_dt)}<br/>"
        f"<b>FIN:</b>   {format_datetime(end_dt)}<br/>"
        f"<b>TIEMPO TRANSCURRIDO:</b> {format_duration(start_ts, end_ts)}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 12))

    # --- Conteos generales en negrita
    errores  = len(errors)
    escaneos = total_procesos - errores

    # Agrupo actuaciones por proceso
    por_proceso = defaultdict(list)
    for num, fecha, actu, anota, url in actes:
        por_proceso[num].append((fecha, actu, anota))

    con_actos = len(por_proceso)
    sin_actos = escaneos - con_actos

    elements.append(Paragraph(
        f"<b>Total procesos:</b>       {total_procesos}<br/>"
        f"<b>----------------------------------------------------------------------------------------------------------------------------</b><br/>"
        f"<b>Escaneados:</b>           {escaneos}<br/>"
        f"<b>Con errores:</b>          {errores}<br/>"
        f"<b>Con actuaciones:</b>     {con_actos}<br/>"
        f"<b>Sin actuaciones:</b>     {sin_actos}<br/>",
        styles['Normal']
    ))
    elements.append(Spacer(1, 12))

    # --- Detalle de actuaciones
    for num in sorted(por_proceso):
        elements.append(Paragraph(f"Num. Radicación {num}", styles['Heading3']))
        data = [["Fecha", "Actuación", "Anotación"]]
        for fecha, actu, anota in por_proceso[num]:
            data.append([
                Paragraph(fecha, styles['Normal']),
                Paragraph(actu, styles['Normal']),
                Paragraph(escape(anota), styleWrap)
            ])
        col_widths = [60, 150, doc.width - 210]
        tbl = Table(data, colWidths=col_widths)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
            ('LINEBELOW',  (0,0), (-1,0), 1, colors.grey),
            ('LINEBELOW',  (0,1), (-1,-1), 0.5, colors.grey),
            ('VALIGN',     (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 8))

    # --- Procesos con error
    if errors:
        elements.append(Paragraph("Procesos con ERROR", styles['Heading2']))
        data_e = [["Número", "Mensaje"]]
        for num, msg in errors:
            p = Paragraph(msg.replace("\n", "<br/>"), styleWrap)
            data_e.append([str(num), p])
        col_widths = [150, doc.width - 150]
        tbl_e = Table(data_e, colWidths=col_widths)
        tbl_e.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.pink),
            ('LINEBELOW',  (0,0), (-1,0), 1, colors.grey),
            ('LINEBELOW',  (0,1), (-1,-1), 0.5, colors.grey),
            ('VALIGN',     (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(tbl_e)
    else:
        elements.append(Paragraph("No hubo errores en ningún proceso.", styles['Normal']))

    # --- Generar y volcar log de texto
    doc.build(elements)
    print(f"PDF generado: {PDF_PATH}")

    with open(LOG_TXT_PATH, "w", encoding="utf-8") as f:
        f.write(f"Reporte generado: {datetime.now()}\n")
        f.write(
            f"Total: {total_procesos}, Escaneados: {escaneos}, "
            f"Con actuaciones: {con_actos}, Sin actuaciones: {sin_actos}, Errores: {errores}\n\n"
        )
        if errors:
            for num, msg in errors:
                f.write(f"{num} → {msg}\n")
        else:
            f.write("Cero errores.\n")
