"""Gestión de incidentes derivados del triaje."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, PaginationDep, require_permission
from app.core.errors import AppError, Forbidden, NotFound
from app.core.permissions import P
from app.models.alert import Alert
from app.models.enums import IncidentStatus
from app.models.incident import Incident
from app.models.security import Permission, Role, User
from app.schemas.alert import IncidentAssignee, IncidentOut, IncidentUpdate
from app.schemas.common import Page
from app.services import audit

router = APIRouter(prefix="/incidents", tags=["Incidentes"])

ReadIncidents = Annotated[Any, Depends(require_permission(P.INCIDENTS_READ))]


@router.get("/assignees", response_model=list[IncidentAssignee], summary="Responsables disponibles")
async def list_assignees(
    db: DbSession,
    _: Annotated[Any, Depends(require_permission(P.INCIDENTS_CREATE, P.INCIDENTS_UPDATE))],
) -> list[IncidentAssignee]:
    users = (await db.execute(
        select(User).where(
            User.is_active.is_(True), User.deleted_at.is_(None),
            User.role.has(Role.permissions.any(Permission.code == P.INCIDENTS_UPDATE)),
        ).order_by(User.full_name)
    )).scalars().all()
    return [IncidentAssignee.model_validate(user) for user in users]


@router.get("", response_model=Page[IncidentOut], summary="Listar incidentes")
async def list_incidents(
    db: DbSession,
    _: ReadIncidents,
    pagination: PaginationDep,
    incident_status: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    assignee_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, max_length=120),
) -> Page[IncidentOut]:
    conditions = []
    if incident_status:
        conditions.append(Incident.status == incident_status)
    if priority:
        conditions.append(Incident.priority == priority)
    if assignee_id:
        conditions.append(Incident.assignee_id == assignee_id)
    if q:
        pattern = f"%{q}%"
        conditions.append(or_(Incident.title.ilike(pattern), Incident.ticket_id.ilike(pattern)))

    total = (await db.execute(select(func.count(Incident.id)).where(*conditions))).scalar_one()
    rows = (
        await db.execute(
            select(Incident)
            .options(selectinload(Incident.assignee), selectinload(Incident.alert))
            .where(*conditions)
            .order_by(Incident.opened_at.desc())
            .offset(pagination.offset)
            .limit(pagination.size)
        )
    ).scalars().all()
    return Page[IncidentOut](
        items=[IncidentOut.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=max(1, -(-total // pagination.size)),
    )


@router.get("/{incident_id}", response_model=IncidentOut, summary="Detalle de incidente")
async def get_incident(incident_id: uuid.UUID, db: DbSession, _: ReadIncidents) -> IncidentOut:
    incident = (
        await db.execute(
            select(Incident)
            .options(selectinload(Incident.assignee), selectinload(Incident.alert))
            .where(Incident.id == incident_id)
        )
    ).scalar_one_or_none()
    if incident is None:
        raise NotFound("Incidente")
    return IncidentOut.model_validate(incident)


@router.patch("/{incident_id}", response_model=IncidentOut, summary="Actualizar incidente")
async def update_incident(
    incident_id: uuid.UUID,
    payload: IncidentUpdate,
    request: Request,
    db: DbSession,
    actor: Annotated[Any, Depends(require_permission(P.INCIDENTS_UPDATE, P.INCIDENTS_CLOSE))],
) -> IncidentOut:
    incident = (
        await db.execute(
            select(Incident)
            .options(selectinload(Incident.assignee), selectinload(Incident.alert))
            .where(Incident.id == incident_id)
        )
    ).scalar_one_or_none()
    if incident is None:
        raise NotFound("Incidente")

    if not actor.has_permission(P.INCIDENTS_UPDATE):
        if (payload.priority is not None or payload.assignee_id is not None
                or payload.status not in (IncidentStatus.CLOSED, IncidentStatus.RESOLVED)):
            raise Forbidden("Se requiere incidents:update para editar el incidente")

    final_status = payload.status or incident.status
    final_resolution = payload.resolution if payload.resolution is not None else incident.resolution
    if final_status in (IncidentStatus.CLOSED, IncidentStatus.RESOLVED) and not (final_resolution or "").strip():
        raise AppError("La resolución es obligatoria para resolver o cerrar el incidente", 422, "RESOLUTION_REQUIRED")

    changes: dict[str, Any] = {}
    if payload.status is not None and payload.status != incident.status:
        if payload.status in (IncidentStatus.CLOSED, IncidentStatus.RESOLVED) and not actor.has_permission(
            P.INCIDENTS_CLOSE
        ):
            raise Forbidden("Se requiere incidents:close para cerrar o resolver")
        changes["status"] = {"from": incident.status.value, "to": payload.status.value}
        incident.status = payload.status
        if payload.status in (IncidentStatus.CLOSED, IncidentStatus.RESOLVED):
            incident.closed_at = datetime.now(timezone.utc)
        else:
            incident.closed_at = None
    if payload.priority is not None:
        changes["priority"] = {"from": incident.priority.value, "to": payload.priority.value}
        incident.priority = payload.priority
    if payload.assignee_id is not None:
        assignee = (await db.execute(select(User).where(
            User.id == payload.assignee_id, User.is_active.is_(True), User.deleted_at.is_(None)
        ))).scalar_one_or_none()
        if assignee is None or not assignee.has_permission(P.INCIDENTS_UPDATE):
            raise AppError("El responsable debe ser un usuario activo con permiso para gestionar incidentes", 422, "INVALID_ASSIGNEE")
        changes["assignee_id"] = {"from": str(incident.assignee_id) if incident.assignee_id else None, "to": str(payload.assignee_id)}
        incident.assignee_id = payload.assignee_id
        incident.assignee = assignee
    if payload.resolution is not None:
        changes["resolution"] = payload.resolution
        incident.resolution = payload.resolution

    await audit.record(
        db, module="incidents", action="INCIDENT_UPDATE", user=actor, request=request,
        entity_type="incident", entity_id=incident.id, detail={"changes": changes},
    )
    await db.commit()
    incident = (
        await db.execute(
            select(Incident)
            .options(selectinload(Incident.assignee), selectinload(Incident.alert))
            .where(Incident.id == incident_id)
        )
    ).scalar_one()
    return IncidentOut.model_validate(incident)
