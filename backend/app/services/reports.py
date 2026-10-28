"""Generación de reportes operacionales, de gestión y de auditoría.

Formatos: PDF (ReportLab), Word (python-docx) y Excel (openpyxl con gráficos
nativos). El archivo se guarda en `storage/reports/{id}.{ext}` y la fila en
`reports` conserva parámetros, tamaño y autor para trazabilidad.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit import Report
from app.models.enums import ReportFormat, ReportType
from app.services import dashboard

SEVERITY_ES = {
    "critical": "Crítica",
    "high": "Alta",
    "medium": "Media",
    "low": "Baja",
    "info": "Informativa",
    "true_positive": "Verdadero positivo",
    "false_positive": "Falso positivo",
    "suspicious": "Sospechoso",
    "benign": "Benigno",
    "inconclusive": "Inconcluso",
}

STATUS_ES = {
    "pending": "Pendiente",
    "triaging": "En triaje",
    "triage_failed": "Error de triaje",
    "triaged": "Triada",
    "in_review": "En revisión",
    "escalated": "Escalada",
    "closed": "Cerrada",
    "false_positive": "Falso positivo",
    "discarded": "Descartada",
    "open": "Abierto",
    "investigating": "En investigación",
    "contained": "Contenido",
    "resolved": "Resuelto",
}

REPORT_TITLES = {
    "operational": "Reporte operacional SOC",
    "management": "Reporte de gestión SOC",
    "audit": "Reporte de auditoría y trazabilidad",
}


# ---------------------------------------------------------------------------
# Recolección de datos
# ---------------------------------------------------------------------------
async def _gather(db: AsyncSession, report: Report) -> dict[str, Any]:
    params = report.params or {}
    days = int(params.get("days", 30))
    summary = await dashboard.summary(db, days)
    data: dict[str, Any] = {
        "meta": {
            "id": str(report.id),
            "type": report.type.value,
            "format": report.format.value,
            "title": REPORT_TITLES[report.type.value],
            "subtitle": params.get("title") or "",
            "days": days,
            "date_from": summary["period"]["date_from"],
            "date_to": summary["period"]["date_to"],
            "generated_at": datetime.now(timezone.utc),
            "generated_by": params.get("requested_by_name", "Sistema"),
        },
        "summary": summary,
        "trend": await dashboard.trend(db, min(days, 30)),
        "severity": (await dashboard.severity_distribution(db, days))["items"],
        "mttt": await dashboard.mttt_by_severity(db, days),
        "sla": await dashboard.sla_rows(db, days),
        "sources": await dashboard.top_sources(db, days, 10, "ip"),
        "incidents": [],
        "critical_alerts": [],
        "monthly": [],
        "audit": {"rows": [], "by_module": [], "chain": None},
    }

    incidents = (
        await db.execute(
            text(
                """
                SELECT i.ticket_id, i.title, i.status, i.priority, i.opened_at,
                       COALESCE(u.full_name, 'sin asignar') AS assignee
                FROM incidents i LEFT JOIN users u ON u.id = i.assignee_id
                WHERE i.opened_at >= now() - make_interval(days => :days)
                ORDER BY i.opened_at DESC LIMIT 20
                """
            ),
            {"days": days},
        )
    ).mappings().all()
    data["incidents"] = [dict(row) for row in incidents]

    alerts = (
        await db.execute(
            text(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (alert_id) alert_id, verdict, triaged_at
                    FROM triage_results ORDER BY alert_id, triaged_at DESC
                )
                SELECT a.id, a.description, a.severity, a.status, host(a.src_ip) AS src_ip,
                       a.agent_name, a.received_at, l.verdict, l.triaged_at
                FROM alerts a LEFT JOIN latest l ON l.alert_id = a.id
                WHERE a.received_at >= now() - make_interval(days => :days)
                  AND a.severity IN ('critical','high')
                ORDER BY a.received_at DESC LIMIT 15
                """
            ),
            {"days": days},
        )
    ).mappings().all()
    data["critical_alerts"] = [dict(row) for row in alerts]

    monthly = (
        await db.execute(
            text(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (alert_id) alert_id, triaged_at
                    FROM triage_results ORDER BY alert_id, triaged_at DESC
                )
                SELECT to_char(date_trunc('month', a.received_at), 'YYYY-MM') AS month,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE a.severity = 'critical') AS critical,
                       COUNT(l.triaged_at) AS triaged,
                       ROUND(AVG(EXTRACT(EPOCH FROM (l.triaged_at - a.received_at)) / 60.0)::numeric, 1) AS avg_minutes
                FROM alerts a LEFT JOIN latest l ON l.alert_id = a.id
                WHERE a.received_at >= now() - interval '12 months'
                GROUP BY 1 ORDER BY 1
                """
            )
        )
    ).mappings().all()
    data["monthly"] = [dict(row) for row in monthly]

    if report.type == ReportType.AUDIT:
        start = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            await db.execute(
                text(
                    """
                    SELECT occurred_at, username, module, action, result, entity_type,
                           entity_id, CAST(ip AS text) AS ip, duration_ms, request_id
                    FROM audit_log WHERE occurred_at >= :start
                    ORDER BY id DESC LIMIT 500
                    """
                ),
                {"start": start},
            )
        ).mappings().all()
        data["audit"]["rows"] = [dict(row) for row in rows]
        by_module = (
            await db.execute(
                text(
                    """
                    SELECT module, COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE result = 'success') AS success,
                           COUNT(*) FILTER (WHERE result = 'failure') AS failure,
                           COUNT(*) FILTER (WHERE result = 'denied') AS denied
                    FROM audit_log WHERE occurred_at >= :start
                    GROUP BY module ORDER BY total DESC
                    """
                ),
                {"start": start},
            )
        ).mappings().all()
        data["audit"]["by_module"] = [dict(row) for row in by_module]

    return data


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "SocTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20,
            leading=24, textColor=colors.HexColor("#0F172A"), alignment=TA_LEFT, spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "SocSub", parent=base["Normal"], fontName="Helvetica", fontSize=10,
            textColor=colors.HexColor("#475569"), spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "SocH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13,
            textColor=colors.HexColor("#1D4ED8"), spaceBefore=12, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "SocBody", parent=base["Normal"], fontName="Helvetica", fontSize=9,
            leading=12, textColor=colors.HexColor("#1E293B"),
        ),
        "small": ParagraphStyle(
            "SocSmall", parent=base["Normal"], fontName="Helvetica", fontSize=7.5,
            textColor=colors.HexColor("#64748B"),
        ),
    }


def _pdf_table(rows: list[list[str]], widths: list[float], header_color: str = "#1E3A8A") -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _footer(canvas, doc) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(18 * mm, 10 * mm, "SOC-Lite · Documento generado automáticamente")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    canvas.restoreState()


def _render_pdf(data: dict[str, Any], path: Path) -> None:
    styles = _pdf_styles()
    doc = SimpleDocTemplate(
        str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=18 * mm,
        title=data["meta"]["title"], author="SOC-Lite",
    )
    meta, summary = data["meta"], data["summary"]
    totals, rates, mttt = summary["totals"], summary["rates"], summary["mttt"]
    story: list[Any] = []

    story.append(Paragraph(meta["title"], styles["title"]))
    story.append(
        Paragraph(
            f"Periodo {meta['date_from']} a {meta['date_to']} · {meta['days']} días · "
            f"Generado {meta['generated_at']:%Y-%m-%d %H:%M UTC} por {meta['generated_by']}",
            styles["subtitle"],
        )
    )
    if meta.get("subtitle"):
        story.append(Paragraph(meta["subtitle"], styles["body"]))

    story.append(Paragraph("Indicadores clave", styles["h2"]))
    kpi_rows = [
        ["Indicador", "Valor", "Indicador", "Valor"],
        ["Alertas recibidas", f"{totals['alerts']:,}", "MTTT promedio", f"{mttt['avg_minutes']} min"],
        ["Alertas críticas", f"{totals['critical']:,}", "MTTT P95", f"{mttt['p95_minutes']} min"],
        ["Alertas altas", f"{totals['high']:,}", "Cumplimiento SLA", f"{rates['sla_compliance']}%"],
        ["Triajes automáticos", f"{totals['triaged']:,}", "Automatización", f"{rates['automation']}%"],
        ["Falsos positivos", f"{totals['false_positive']:,}", "Tasa de FP", f"{rates['false_positive']}%"],
        ["Incidentes abiertos", f"{totals['incidents_open']:,}", "Revisión humana", f"{rates['human_review']}%"],
    ]
    story.append(_pdf_table(kpi_rows, [50 * mm, 30 * mm, 50 * mm, 30 * mm]))

    story.append(Paragraph("Distribución por severidad", styles["h2"]))
    sev_rows = [["Severidad", "Alertas", "Porcentaje"]]
    for item in data["severity"]:
        total = sum(i["count"] for i in data["severity"]) or 1
        sev_rows.append(
            [SEVERITY_ES.get(item["severity"], item["severity"]), str(item["count"]),
             f"{item['count'] / total * 100:.1f}%"]
        )
    severity_table = _pdf_table(sev_rows, [60 * mm, 30 * mm, 30 * mm])

    drawing = Drawing(160, 90)
    chart = VerticalBarChart()
    chart.x = 10
    chart.y = 10
    chart.height = 65
    chart.width = 140
    chart.data = [[item["count"] for item in data["severity"]]]
    chart.categoryAxis.categoryNames = [
        SEVERITY_ES.get(item["severity"], item["severity"]) for item in data["severity"]
    ]
    chart.bars[0].fillColor = colors.HexColor("#2563EB")
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 7
    chart.categoryAxis.labels.fontSize = 7
    drawing.add(chart)
    story.append(KeepTogether([severity_table, Spacer(1, 6), drawing]))

    if data["mttt"]:
        story.append(Paragraph("Tiempo medio de triaje (MTTT) por severidad", styles["h2"]))
        rows = [["Severidad", "Triajes", "Promedio (min)", "P95 (min)", "SLA (min)", "Cumplimiento"]]
        rows += [
            [SEVERITY_ES.get(r["severity"], r["severity"]), str(r["count"]), f"{r['avg_minutes']}",
             f"{r['p95_minutes']}", str(r["target_minutes"]), f"{r['compliance']}%"]
            for r in data["mttt"]
        ]
        story.append(_pdf_table(rows, [30 * mm, 22 * mm, 30 * mm, 25 * mm, 25 * mm, 28 * mm]))

    story.append(Paragraph("Top orígenes de alertas", styles["h2"]))
    rows = [["Origen (IP)", "Alertas", "Críticas/altas"]]
    rows += [[s["label"], str(s["count"]), str(s["critical"])] for s in data["sources"][:10]]
    story.append(_pdf_table(rows, [95 * mm, 25 * mm, 30 * mm]))

    if data["critical_alerts"]:
        story.append(Paragraph("Alertas críticas y altas recientes", styles["h2"]))
        rows = [["Fecha", "Severidad", "Descripción", "Activo", "Veredicto"]]
        for alert in data["critical_alerts"][:10]:
            rows.append(
                [
                    alert["received_at"].strftime("%Y-%m-%d %H:%M"),
                    SEVERITY_ES.get(str(alert["severity"]), str(alert["severity"])),
                    Paragraph(str(alert["description"])[:160], styles["small"]),
                    alert.get("agent_name") or "-",
                    SEVERITY_ES.get(str(alert.get("verdict") or "-"), str(alert.get("verdict") or "-")),
                ]
            )
        story.append(_pdf_table(rows, [28 * mm, 20 * mm, 85 * mm, 25 * mm, 22 * mm]))

    if data["incidents"]:
        story.append(Paragraph("Incidentes del periodo", styles["h2"]))
        rows = [["Ticket", "Título", "Estado", "Prioridad", "Responsable"]]
        rows += [
            [i.get("ticket_id") or "-", Paragraph(str(i["title"])[:90], styles["small"]),
             STATUS_ES.get(str(i["status"]), str(i["status"])), str(i["priority"]), i["assignee"]]
            for i in data["incidents"][:15]
        ]
        story.append(_pdf_table(rows, [25 * mm, 80 * mm, 25 * mm, 18 * mm, 32 * mm]))

    if data["monthly"]:
        story.append(PageBreak())
        story.append(Paragraph("Evolución mensual", styles["h2"]))
        rows = [["Mes", "Alertas", "Críticas", "Triajes", "MTTT promedio (min)"]]
        rows += [
            [m["month"], str(m["total"]), str(m["critical"]), str(m["triaged"]),
             str(m["avg_minutes"] or "-")]
            for m in data["monthly"]
        ]
        story.append(_pdf_table(rows, [30 * mm, 30 * mm, 30 * mm, 30 * mm, 45 * mm]))

    if data["audit"]["rows"]:
        story.append(Paragraph("Bitácora de auditoría (últimos 500 eventos)", styles["h2"]))
        rows = [["Fecha/hora", "Usuario", "Módulo", "Acción", "Resultado", "IP"]]
        rows += [
            [
                row["occurred_at"].strftime("%Y-%m-%d %H:%M:%S"),
                row.get("username") or "-",
                row["module"],
                row["action"],
                str(row["result"]),
                row.get("ip") or "-",
            ]
            for row in data["audit"]["rows"][:200]
        ]
        story.append(_pdf_table(rows, [34 * mm, 25 * mm, 22 * mm, 40 * mm, 20 * mm, 28 * mm]))

    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Reporte generado a partir de la base de datos operativa de SOC-Lite. "
            "Las métricas de MTTT y SLA se calculan con la última ejecución de triaje de cada alerta. "
            "Documento de uso interno; no sustituye la evidencia forense ni el registro legal.",
            styles["small"],
        )
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------
def _render_docx(data: dict[str, Any], path: Path) -> None:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    meta, summary = data["meta"], data["summary"]
    totals, rates, mttt = summary["totals"], summary["rates"], summary["mttt"]
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)

    title = doc.add_heading(meta["title"], level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    subtitle = doc.add_paragraph(
        f"Periodo {meta['date_from']} a {meta['date_to']} · {meta['days']} días · "
        f"Generado {meta['generated_at']:%Y-%m-%d %H:%M UTC} por {meta['generated_by']}"
    )
    subtitle.runs[0].font.color.rgb = RGBColor(0x47, 0x55, 0x69)
    if meta.get("subtitle"):
        doc.add_paragraph(meta["subtitle"])

    doc.add_heading("Indicadores clave", level=1)
    kpis = [
        ("Alertas recibidas", totals["alerts"]),
        ("Alertas críticas", totals["critical"]),
        ("Alertas altas", totals["high"]),
        ("Triajes automáticos", totals["triaged"]),
        ("Falsos positivos", totals["false_positive"]),
        ("Incidentes abiertos", totals["incidents_open"]),
        ("MTTT promedio (min)", mttt["avg_minutes"]),
        ("MTTT P95 (min)", mttt["p95_minutes"]),
        ("Automatización (%)", rates["automation"]),
        ("Tasa de falsos positivos (%)", rates["false_positive"]),
        ("Cumplimiento SLA (%)", rates["sla_compliance"]),
        ("Revisión humana (%)", rates["human_review"]),
    ]
    table = doc.add_table(rows=0, cols=2)
    table.style = "Light List Accent 1"
    for label, value in kpis:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = str(value)

    doc.add_heading("Distribución por severidad", level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    for cell, text in zip(table.rows[0].cells, ("Severidad", "Alertas", "Porcentaje")):
        cell.text = text
    total = sum(item["count"] for item in data["severity"]) or 1
    for item in data["severity"]:
        cells = table.add_row().cells
        cells[0].text = SEVERITY_ES.get(item["severity"], item["severity"])
        cells[1].text = str(item["count"])
        cells[2].text = f"{item['count'] / total * 100:.1f}%"

    doc.add_heading("MTTT y cumplimiento de SLA", level=1)
    table = doc.add_table(rows=1, cols=6)
    table.style = "Light Grid Accent 1"
    for cell, text in zip(
        table.rows[0].cells,
        ("Severidad", "Triajes", "Promedio", "P95", "Objetivo", "Cumplimiento"),
    ):
        cell.text = text
    for row in data["mttt"]:
        cells = table.add_row().cells
        cells[0].text = SEVERITY_ES.get(row["severity"], row["severity"])
        cells[1].text = str(row["count"])
        cells[2].text = f"{row['avg_minutes']} min"
        cells[3].text = f"{row['p95_minutes']} min"
        cells[4].text = f"{row['target_minutes']} min"
        cells[5].text = f"{row['compliance']}%"

    doc.add_heading("Top orígenes", level=1)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    for cell, text in zip(table.rows[0].cells, ("Origen", "Alertas", "Críticas/altas")):
        cell.text = text
    for source in data["sources"][:10]:
        cells = table.add_row().cells
        cells[0].text = source["label"]
        cells[1].text = str(source["count"])
        cells[2].text = str(source["critical"])

    if data["incidents"]:
        doc.add_heading("Incidentes del periodo", level=1)
        table = doc.add_table(rows=1, cols=5)
        table.style = "Light Grid Accent 1"
        for cell, text in zip(table.rows[0].cells, ("Ticket", "Título", "Estado", "Prioridad", "Responsable")):
            cell.text = text
        for incident in data["incidents"][:20]:
            cells = table.add_row().cells
            cells[0].text = incident.get("ticket_id") or "-"
            cells[1].text = str(incident["title"])[:120]
            cells[2].text = STATUS_ES.get(str(incident["status"]), str(incident["status"]))
            cells[3].text = str(incident["priority"])
            cells[4].text = incident["assignee"]

    if data["monthly"]:
        doc.add_heading("Evolución mensual", level=1)
        table = doc.add_table(rows=1, cols=5)
        table.style = "Light Grid Accent 1"
        for cell, text in zip(table.rows[0].cells, ("Mes", "Alertas", "Críticas", "Triajes", "MTTT (min)")):
            cell.text = text
        for month in data["monthly"]:
            cells = table.add_row().cells
            cells[0].text = month["month"]
            cells[1].text = str(month["total"])
            cells[2].text = str(month["critical"])
            cells[3].text = str(month["triaged"])
            cells[4].text = str(month["avg_minutes"] or "-")

    if data["audit"]["rows"]:
        doc.add_heading("Bitácora de auditoría", level=1)
        table = doc.add_table(rows=1, cols=6)
        table.style = "Light Grid Accent 1"
        for cell, text in zip(
            table.rows[0].cells, ("Fecha/hora", "Usuario", "Módulo", "Acción", "Resultado", "IP")
        ):
            cell.text = text
        for row in data["audit"]["rows"][:100]:
            cells = table.add_row().cells
            cells[0].text = row["occurred_at"].strftime("%Y-%m-%d %H:%M:%S")
            cells[1].text = row.get("username") or "-"
            cells[2].text = row["module"]
            cells[3].text = row["action"]
            cells[4].text = str(row["result"])
            cells[5].text = row.get("ip") or "-"

    doc.add_paragraph(
        "Reporte generado automáticamente por SOC-Lite. Uso interno; no sustituye evidencia forense."
    )
    doc.save(str(path))


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------
_HEADER_FILL = PatternFill("solid", fgColor="1E3A8A")
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
_TITLE_FONT = Font(bold=True, size=14, color="0F172A")
_THIN = Side(style="thin", color="CBD5E1")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _write_sheet(ws, title: str, headers: list[str], rows: list[list[Any]], widths: list[int] | None = None) -> None:
    ws.append([title])
    ws["A1"].font = _TITLE_FONT
    ws.append([])
    ws.append(headers)
    header_row = ws.max_row
    for cell in ws[header_row]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _BORDER
    for row in rows:
        ws.append(row)
    for row in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row):
        for cell in row:
            cell.border = _BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for index, width in enumerate(widths or [22] * len(headers), start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(headers))}{ws.max_row}"


def _render_xlsx(data: dict[str, Any], path: Path) -> None:
    meta, summary = data["meta"], data["summary"]
    totals, rates, mttt = summary["totals"], summary["rates"], summary["mttt"]
    wb = Workbook()

    ws = wb.active
    ws.title = "Resumen"
    ws["A1"] = meta["title"]
    ws["A1"].font = Font(bold=True, size=16, color="0F172A")
    ws["A2"] = f"Periodo {meta['date_from']} a {meta['date_to']} ({meta['days']} días)"
    ws["A3"] = f"Generado {meta['generated_at']:%Y-%m-%d %H:%M UTC} por {meta['generated_by']}"
    ws.append([])
    ws.append(["Indicador", "Valor"])
    for cell in ws[5]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    kpis = [
        ("Alertas recibidas", totals["alerts"]),
        ("Alertas críticas", totals["critical"]),
        ("Alertas altas", totals["high"]),
        ("Alertas medias", totals["medium"]),
        ("Alertas bajas", totals["low"]),
        ("Triajes automáticos", totals["triaged"]),
        ("Pendientes", totals["pending"]),
        ("Falsos positivos", totals["false_positive"]),
        ("Incidentes abiertos", totals["incidents_open"]),
        ("MTTT promedio (min)", mttt["avg_minutes"]),
        ("MTTT P95 (min)", mttt["p95_minutes"]),
        ("Automatización (%)", rates["automation"]),
        ("Tasa de falsos positivos (%)", rates["false_positive"]),
        ("Cumplimiento SLA (%)", rates["sla_compliance"]),
        ("Revisión humana (%)", rates["human_review"]),
    ]
    for label, value in kpis:
        ws.append([label, value])
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 18

    ws2 = wb.create_sheet("Tendencias")
    _write_sheet(
        ws2, "Evolución diaria",
        ["Fecha", "Total", "Críticas", "Altas", "Medias", "Bajas", "Falsos positivos"],
        [
            [row["date"], row["total"], row["critical"], row["high"], row["medium"], row["low"],
             row["false_positive"]]
            for row in data["trend"]
        ],
        [12, 10, 10, 10, 10, 10, 16],
    )
    chart = LineChart()
    chart.title = "Alertas por día"
    chart.y_axis.title = "Alertas"
    chart.x_axis.title = "Fecha"
    chart_data = Reference(ws2, min_col=2, max_col=3, min_row=4, max_row=ws2.max_row)
    categories = Reference(ws2, min_col=1, min_row=5, max_row=ws2.max_row)
    chart.add_data(chart_data, titles_from_data=True)
    chart.set_categories(categories)
    chart.height = 8
    chart.width = 20
    ws2.add_chart(chart, "I4")

    ws3 = wb.create_sheet("Severidad")
    _write_sheet(
        ws3, "Distribución por severidad", ["Severidad", "Alertas"],
        [[SEVERITY_ES.get(item["severity"], item["severity"]), item["count"]] for item in data["severity"]],
        [18, 12],
    )
    bar = BarChart()
    bar.title = "Alertas por severidad"
    bar.add_data(Reference(ws3, min_col=2, min_row=4, max_row=9), titles_from_data=True)
    bar.set_categories(Reference(ws3, min_col=1, min_row=5, max_row=9))
    bar.height = 8
    bar.width = 16
    ws3.add_chart(bar, "D4")

    ws4 = wb.create_sheet("MTTT")
    _write_sheet(
        ws4, "MTTT y SLA",
        ["Severidad", "Triajes", "Promedio (min)", "P95 (min)", "Objetivo (min)", "Cumplimiento (%)"],
        [[SEVERITY_ES.get(r["severity"], r["severity"]), r["count"], r["avg_minutes"],
          r["p95_minutes"], r["target_minutes"], r["compliance"]] for r in data["mttt"]],
        [18, 10, 16, 12, 15, 18],
    )

    ws5 = wb.create_sheet("Origenes")
    _write_sheet(
        ws5, "Top orígenes", ["Origen", "Alertas", "Críticas/altas"],
        [[s["label"], s["count"], s["critical"]] for s in data["sources"]],
        [28, 12, 16],
    )

    ws6 = wb.create_sheet("Incidentes")
    _write_sheet(
        ws6, "Incidentes del periodo",
        ["Ticket", "Título", "Estado", "Prioridad", "Responsable", "Apertura"],
        [[i.get("ticket_id") or "-", i["title"], STATUS_ES.get(str(i["status"]), str(i["status"])),
          i["priority"], i["assignee"], i["opened_at"].strftime("%Y-%m-%d %H:%M")]
         for i in data["incidents"]],
        [14, 55, 16, 10, 24, 18],
    )

    ws7 = wb.create_sheet("Mensual")
    _write_sheet(
        ws7, "Evolución mensual", ["Mes", "Alertas", "Críticas", "Triajes", "MTTT (min)"],
        [[m["month"], m["total"], m["critical"], m["triaged"], m["avg_minutes"]]
         for m in data["monthly"]],
        [12, 12, 12, 12, 14],
    )

    if data["audit"]["rows"]:
        ws8 = wb.create_sheet("Auditoria")
        _write_sheet(
            ws8, "Bitácora de auditoría",
            ["Fecha/hora", "Usuario", "Módulo", "Acción", "Resultado", "Entidad", "IP", "Duración (ms)"],
            [[r["occurred_at"].strftime("%Y-%m-%d %H:%M:%S"), r.get("username") or "-", r["module"],
              r["action"], str(r["result"]), r.get("entity_id") or "-", r.get("ip") or "-",
              r.get("duration_ms") or ""] for r in data["audit"]["rows"]],
            [20, 16, 14, 20, 12, 20, 16, 14],
        )
        ws9 = wb.create_sheet("Auditoria_Modulos")
        _write_sheet(
            ws9, "Eventos por módulo", ["Módulo", "Total", "Éxito", "Fallo", "Denegado"],
            [[m["module"], m["total"], m["success"], m["failure"], m["denied"]]
             for m in data["audit"]["by_module"]],
            [18, 10, 10, 10, 12],
        )

    ws_meta = wb.create_sheet("Metadatos")
    _write_sheet(
        ws_meta, "Metadatos del reporte", ["Campo", "Valor"],
        [["ID", meta["id"]], ["Tipo", meta["type"]], ["Formato", meta["format"]],
         ["Periodo (días)", meta["days"]], ["Desde", str(meta["date_from"])], ["Hasta", str(meta["date_to"])],
         ["Generado por", meta["generated_by"]], ["Generado el", meta["generated_at"].isoformat()],
         ["Clasificación", "Uso interno"]],
        [24, 44],
    )
    wb.save(str(path))


# ---------------------------------------------------------------------------
# API del servicio
# ---------------------------------------------------------------------------
async def generate(db: AsyncSession, report: Report) -> Path:
    """Genera el archivo físico y devuelve su ruta."""
    data = await _gather(db, report)
    extension = report.format.value
    path = settings.reports_path / f"{report.id}.{extension}"
    renderers = {
        ReportFormat.PDF: _render_pdf,
        ReportFormat.DOCX: _render_docx,
        ReportFormat.XLSX: _render_xlsx,
    }
    renderer = renderers[report.format]
    await asyncio.to_thread(renderer, data, path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("El renderizador no produjo un archivo válido")
    return path
