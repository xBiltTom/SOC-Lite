"""Generación y descarga de reportes PDF, Word y Excel."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.core.config import settings
from app.core.deps import DbSession, PaginationDep, require_permission
from app.core.errors import AppError, NotFound
from app.core.permissions import P
from app.models.audit import Report
from app.models.enums import ReportFormat, ReportStatus, ReportType
from app.schemas.common import Page
from app.schemas.report import ReportCreate, ReportOut
from app.services import audit, reports

router = APIRouter(prefix="/reports", tags=["Reportes"])

ReadReports = Annotated[Any, Depends(require_permission(P.REPORTS_READ))]
CreateReports = Annotated[Any, Depends(require_permission(P.REPORTS_CREATE))]
ExportReports = Annotated[Any, Depends(require_permission(P.REPORTS_EXPORT))]

MEDIA = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/types", summary="Tipos de reporte disponibles")
async def report_types(_: ReadReports) -> list[dict[str, str]]:
    return [
        {
            "type": "operational",
            "name": "Operacional",
            "description": "Alertas, MTTT, SLA, orígenes e incidentes del periodo.",
            "formats": "pdf,docx,xlsx",
        },
        {
            "type": "management",
            "name": "De gestión",
            "description": "Evolución mensual, automatización, carga operativa y riesgos.",
            "formats": "pdf,docx,xlsx",
        },
        {
            "type": "audit",
            "name": "De auditoría",
            "description": "Bitácora de accesos y acciones, con cadena de integridad.",
            "formats": "pdf,docx,xlsx",
        },
    ]


@router.post("", response_model=ReportOut, status_code=201, summary="Generar reporte")
async def create_report(
    payload: ReportCreate,
    request: Request,
    db: DbSession,
    actor: CreateReports,
) -> ReportOut:
    today = date.today()
    date_to = payload.date_to or today
    date_from = payload.date_from or (date_to - timedelta(days=29))
    days = max(1, (date_to - date_from).days + 1)

    report = Report(
        type=payload.type,
        format=payload.format,
        status=ReportStatus.GENERATING,
        params={
            "days": days,
            "date_from": str(date_from),
            "date_to": str(date_to),
            "title": payload.title,
            "requested_by_name": actor.full_name,
        },
        requested_by=actor.id,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    try:
        path = await reports.generate(db, report)
        report.status = ReportStatus.READY
        report.file_path = str(path)
        report.file_size = path.stat().st_size
        report.completed_at = datetime.now(timezone.utc)
        await audit.record(
            db, module="reports", action="REPORT_GENERATE", user=actor, request=request,
            entity_type="report", entity_id=report.id,
            detail={"type": report.type.value, "format": report.format.value, "days": days},
        )
        await db.commit()
    except Exception as exc:
        report.status = ReportStatus.FAILED
        report.error = str(exc)[:1000]
        await db.commit()
        raise AppError(f"No se pudo generar el reporte: {exc}", 500, "REPORT_FAILED") from exc

    await db.refresh(report)
    return ReportOut.model_validate(report)


@router.get("", response_model=Page[ReportOut], summary="Historial de reportes")
async def list_reports(db: DbSession, _: ReadReports, pagination: PaginationDep) -> Page[ReportOut]:
    total = (await db.execute(select(func.count(Report.id)))).scalar_one()
    rows = (
        await db.execute(
            select(Report).order_by(Report.created_at.desc())
            .offset(pagination.offset).limit(pagination.size)
        )
    ).scalars().all()
    return Page[ReportOut](
        items=[ReportOut.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=max(1, -(-total // pagination.size)),
    )


@router.get("/{report_id}", response_model=ReportOut, summary="Detalle de reporte")
async def get_report(report_id: uuid.UUID, db: DbSession, _: ReadReports) -> ReportOut:
    report = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if report is None:
        raise NotFound("Reporte")
    return ReportOut.model_validate(report)


@router.get("/{report_id}/download", summary="Descargar reporte")
async def download_report(
    report_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: ExportReports,
) -> FileResponse:
    report = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if report is None:
        raise NotFound("Reporte")
    if report.status != ReportStatus.READY or not report.file_path:
        raise AppError("El reporte no está disponible", 409, "REPORT_NOT_READY")

    from pathlib import Path

    path = Path(report.file_path)
    try:
        path.resolve().relative_to(settings.reports_path.resolve())
    except ValueError as exc:
        raise AppError("Ruta de reporte inválida", 500, "REPORT_PATH_INVALID") from exc
    if not path.exists():
        raise NotFound("Archivo de reporte")

    await audit.record(
        db, module="reports", action="REPORT_DOWNLOAD", user=actor, request=request,
        entity_type="report", entity_id=report.id,
        detail={"format": report.format.value, "type": report.type.value},
    )
    await db.commit()

    filename = (
        f"SOC-Lite_{report.type.value}_{report.params.get('date_from', '')}_"
        f"{report.params.get('date_to', '')}.{report.format.value}"
    )
    return FileResponse(
        path,
        media_type=MEDIA.get(report.format.value, "application/octet-stream"),
        filename=filename,
    )
