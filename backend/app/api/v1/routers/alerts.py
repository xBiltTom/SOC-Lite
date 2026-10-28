"""API de alertas: ingesta desde SIEM, consulta, triaje, feedback e incidentes."""
from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, Query, Request, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, PaginationDep, require_permission
from app.core.errors import AppError, Conflict, Forbidden, NotFound, Unauthorized
from app.core.permissions import P
from app.models.alert import Alert, AlertFeedback, EnrichmentData, TriageResult
from app.models.enums import (
    AlertStatus,
    AuditResult,
    IncidentPriority,
    IncidentStatus,
    Severity,
    TriageStatus,
    TriageVerdict,
)
from app.models.incident import Incident
from app.schemas.alert import (
    AlertDetail,
    AlertListItem,
    AlertUpdate,
    FeedbackCreate,
    FeedbackOut,
    IncidentCreate,
    IncidentOut,
    IngestResponse,
    TriageOut,
)
from app.schemas.common import Page
from app.services import alert_ingest, audit, triage_client
from app.services.live_events import live_events

router = APIRouter(prefix="/alerts", tags=["Alertas"])

ReadAlerts = Annotated[Any, Depends(require_permission(P.ALERTS_READ))]
RunTriage = Annotated[Any, Depends(require_permission(P.TRIAGE_RUN))]

_SORT = {
    "received_at": "a.received_at ASC",
    "-received_at": "a.received_at DESC",
    "severity": "array_position(ARRAY['info','low','medium','high','critical'], CAST(a.severity AS text)) ASC",
    "-severity": "array_position(ARRAY['info','low','medium','high','critical'], CAST(a.severity AS text)) DESC",
    "rule_level": "a.rule_level ASC NULLS LAST",
    "-rule_level": "a.rule_level DESC NULLS LAST",
}


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Webhook de ingesta (Wazuh / OPNsense / Suricata)",
)
async def ingest(
    request: Request,
    db: DbSession,
    payload: dict[str, Any] = Body(...),
    x_ingest_key: Annotated[str | None, Header(alias="X-Ingest-Key")] = None,
) -> IngestResponse:
    if not x_ingest_key or not secrets.compare_digest(x_ingest_key, settings.ingest_api_key):
        raise Unauthorized("Clave de ingesta inválida")

    normalized = alert_ingest.normalize(payload, source_hint=request.headers.get("x-source"))
    existing = (
        await db.execute(select(Alert).where(Alert.fingerprint == normalized.fingerprint))
    ).scalar_one_or_none()
    if existing is not None:
        existing.dedup_count += 1
        existing.last_seen_at = datetime.now(timezone.utc)
        await audit.record(
            db, module="alerts", action="ALERT_DEDUP", username="webhook", request=request,
            entity_type="alert", entity_id=existing.id,
            detail={"fingerprint": normalized.fingerprint, "dedup_count": existing.dedup_count},
        )
        await db.commit()
        return IngestResponse(
            status="duplicate", alert_id=existing.id, severity=existing.severity,
            deduplicated=True, message="Alerta ya registrada; se incrementó el contador",
        )

    alert = Alert(
        external_id=normalized.external_id,
        source=normalized.source,
        rule_id=normalized.rule_id,
        rule_level=normalized.rule_level,
        description=normalized.description,
        src_ip=normalized.src_ip,
        dst_ip=normalized.dst_ip,
        src_port=normalized.src_port,
        dst_port=normalized.dst_port,
        protocol=normalized.protocol,
        agent_name=normalized.agent_name,
        asset_criticality=normalized.asset_criticality,
        severity=normalized.severity,
        status=AlertStatus.PENDING,
        fingerprint=normalized.fingerprint,
        raw_payload=normalized.raw_payload,
        tags=normalized.tags,
        occurred_at=normalized.occurred_at,
        received_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    await db.flush()
    await audit.record(
        db, module="alerts", action="ALERT_INGEST", username="webhook", request=request,
        entity_type="alert", entity_id=alert.id,
        detail={
            "source": alert.source,
            "severity": alert.severity.value,
            "rule_id": alert.rule_id,
            "src_ip": str(alert.src_ip) if alert.src_ip else None,
        },
    )
    await db.commit()
    await live_events.publish({
        "type": "alert.created", "alert_id": str(alert.id),
        "severity": alert.severity.value, "description": alert.description,
        "simulated": bool(alert.raw_payload.get("demo")),
    })
    return IngestResponse(
        status="accepted", alert_id=alert.id, severity=alert.severity,
        message="Alerta registrada en estado pendiente",
    )


@router.get("", response_model=Page[AlertListItem], summary="Listar alertas")
async def list_alerts(
    db: DbSession,
    _: ReadAlerts,
    pagination: PaginationDep,
    severity: str | None = Query(default=None, description="Lista separada por comas"),
    alert_status: str | None = Query(default=None, alias="status"),
    source: str | None = None,
    q: str | None = Query(default=None, max_length=120),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = Query(default="-received_at", pattern=r"^-?(received_at|severity|rule_level)$"),
) -> Page[AlertListItem]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if severity:
        values = [value for value in severity.split(",") if value]
        conditions.append("CAST(a.severity AS text) = ANY(:severities)")
        params["severities"] = values
    if alert_status:
        values = [value for value in alert_status.split(",") if value]
        conditions.append("CAST(a.status AS text) = ANY(:statuses)")
        params["statuses"] = values
    if source:
        conditions.append("a.source = :source")
        params["source"] = source
    if q:
        conditions.append(
            "(a.description ILIKE :q OR host(a.src_ip) ILIKE :q OR a.agent_name ILIKE :q OR a.rule_id ILIKE :q)"
        )
        params["q"] = f"%{q}%"
    if date_from:
        conditions.append("a.received_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("a.received_at <= :date_to")
        params["date_to"] = date_to

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    total = (
        await db.execute(text(f"SELECT COUNT(*) FROM alerts a {where}"), params)
    ).scalar_one()

    query = text(
        f"""
        WITH latest AS (
            SELECT DISTINCT ON (tr.alert_id) tr.alert_id, tr.verdict, tr.confidence,
                   tr.summary, tr.triaged_at
            FROM triage_results tr ORDER BY tr.alert_id, tr.triaged_at DESC
        )
        SELECT a.id, a.external_id, a.source, a.rule_id, a.rule_level, a.description,
               host(a.src_ip) AS src_ip, host(a.dst_ip) AS dst_ip,
               a.agent_name, a.asset_criticality, a.severity, a.status,
               a.received_at, a.occurred_at, a.dedup_count,
               l.verdict, l.confidence, l.summary, l.triaged_at,
               EXTRACT(EPOCH FROM (l.triaged_at - a.received_at)) / 60.0 AS mttt_minutes,
               i.id AS incident_id, i.ticket_id
        FROM alerts a
        LEFT JOIN latest l ON l.alert_id = a.id
        LEFT JOIN incidents i ON i.alert_id = a.id
        {where}
        ORDER BY {_SORT.get(sort, _SORT['-received_at'])}
        LIMIT :limit OFFSET :offset
        """
    )
    params.update({"limit": pagination.size, "offset": pagination.offset})
    rows = (await db.execute(query, params)).mappings().all()
    return Page[AlertListItem](
        items=[AlertListItem.model_validate(dict(row)) for row in rows],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=max(1, -(-total // pagination.size)),
    )


async def _get_alert(db, alert_id: uuid.UUID) -> Alert:
    alert = (
        await db.execute(
            select(Alert)
            .options(
                selectinload(Alert.triage_results),
                selectinload(Alert.enrichments),
                selectinload(Alert.feedback),
                selectinload(Alert.incident),
            )
            .where(Alert.id == alert_id)
        )
    ).scalar_one_or_none()
    if alert is None:
        raise NotFound("Alerta")
    return alert


@router.get("/{alert_id}", response_model=AlertDetail, summary="Detalle de alerta")
async def get_alert(alert_id: uuid.UUID, db: DbSession, _: ReadAlerts) -> AlertDetail:
    alert = await _get_alert(db, alert_id)
    detail = AlertDetail.model_validate(alert)
    if alert.triage_results:
        delta = alert.triage_results[0].triaged_at - alert.received_at
        detail.mttt_minutes = round(delta.total_seconds() / 60, 1)
    return detail


@router.post("/{alert_id}/triage", response_model=TriageOut, summary="Ejecutar triaje automático")
async def run_triage(
    alert_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: RunTriage,
    force: bool = Query(default=False),
) -> TriageOut:
    # La fila bloqueada evita que dos solicitudes inicien el mismo intento a la vez.
    locked = (await db.execute(select(Alert.id).where(Alert.id == alert_id).with_for_update())).scalar_one_or_none()
    if locked is None:
        raise NotFound("Alerta")
    alert = await _get_alert(db, alert_id)
    if alert.status == AlertStatus.TRIAGING:
        raise Conflict("El triaje de esta alerta ya está en curso")
    latest = alert.triage_results[0] if alert.triage_results else None
    if (alert.status != AlertStatus.TRIAGE_FAILED and latest and not force
            and latest.triaged_at > datetime.now(timezone.utc) - timedelta(seconds=60)):
        return TriageOut.model_validate(latest)

    is_retry = alert.status == AlertStatus.TRIAGE_FAILED
    alert.status = AlertStatus.TRIAGING
    if is_retry:
        await audit.record(
            db, module="triage", action="TRIAGE_RETRY", user=actor,
            username="n8n" if actor is None else None, request=request,
            entity_type="alert", entity_id=alert.id,
        )
    await db.commit()
    await live_events.publish({"type": "alert.triaging", "alert_id": str(alert.id)})

    actor_id = actor.id if actor is not None else None
    actor_username = actor.username if actor is not None else "n8n"
    try:
        return await _complete_triage(alert, request, db, actor)
    except (Exception, asyncio.CancelledError) as exc:
        await db.rollback()
        failed = await _get_alert(db, alert_id)
        failed.status = AlertStatus.TRIAGE_FAILED
        await audit.record(
            db, module="triage", action="TRIAGE_FAILED", user_id=actor_id,
            username=actor_username, request=request,
            entity_type="alert", entity_id=alert_id, result=AuditResult.FAILURE,
            detail={"reason": "No se pudo completar el triaje. Puede reintentarlo."},
        )
        await db.commit()
        await live_events.publish({"type": "alert.triage_failed", "alert_id": str(alert_id)})
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise AppError("No se pudo completar el triaje. Puede reintentarlo.", 503, "TRIAGE_FAILED") from exc


async def _complete_triage(alert: Alert, request: Request, db: DbSession, actor: Any) -> TriageOut:
    enrichment = [
        {
            "provider": item.provider,
            "indicator": item.indicator,
            "indicator_type": item.indicator_type,
            "verdict": item.verdict,
            "score": float(item.score) if item.score is not None else None,
            "country": item.country,
            "asn": item.asn,
        }
        for item in alert.enrichments
    ]
    output = await triage_client.run_triage(alert, enrichment)
    if output.status == TriageStatus.FAILED:
        raise AppError("El servicio de triaje no pudo analizar la alerta", 503, "TRIAGE_UNAVAILABLE")

    result = TriageResult(
        alert_id=alert.id,
        verdict=output.verdict,
        severity=output.severity,
        confidence=output.confidence,
        summary=output.summary,
        reasoning=output.reasoning,
        recommended_actions=output.recommended_actions,
        mitre_techniques=output.mitre_techniques,
        model=output.model,
        prompt_version=output.prompt_version,
        latency_ms=output.latency_ms,
        status=output.status,
        needs_human=output.needs_human,
        fallback_used=output.fallback_used,
        raw_response=output.raw_response,
        triaged_at=datetime.now(timezone.utc),
    )
    db.add(result)

    # Persistimos el enriquecimiento nuevo que devolvió el agente (si lo hubo).
    known = {(item.provider, item.indicator) for item in alert.enrichments}
    for item in output.enrichment:
        if item.get("status") not in ("ok", "not_found"):
            continue
        key = (str(item.get("provider")), str(item.get("indicator")))
        if key in known:
            continue
        db.add(
            EnrichmentData(
                alert_id=alert.id,
                provider=key[0],
                indicator=key[1],
                indicator_type=item.get("indicator_type") or "ip",
                verdict=item.get("verdict"),
                score=item.get("score"),
                country=item.get("country"),
                asn=item.get("asn"),
                raw=item,
            )
        )
        known.add(key)

    # Un falso positivo propuesto requiere validación explícita del analista.
    if output.verdict == TriageVerdict.TRUE_POSITIVE and output.severity.weight >= Severity.HIGH.weight:
        alert.status = AlertStatus.ESCALATED
    else:
        alert.status = AlertStatus.TRIAGED

    # La severidad efectiva nunca baja automáticamente la clasificación de entrada.
    if output.severity.weight > alert.severity.weight:
        alert.severity = output.severity

    await audit.record(
        db, module="triage", action="TRIAGE_RUN", user=actor,
        username="n8n" if actor is None else None, request=request,
        entity_type="alert", entity_id=alert.id,
        detail={
            "verdict": output.verdict.value,
            "severity": output.severity.value,
            "confidence": output.confidence,
            "model": output.model,
            "fallback": output.fallback_used,
            "latency_ms": output.latency_ms,
        },
    )
    await db.commit()
    await db.refresh(result)
    await live_events.publish({"type": "alert.triaged", "alert_id": str(alert.id)})
    return TriageOut.model_validate(result)


@router.post("/{alert_id}/triage/automation", response_model=TriageOut, summary="Triaje desde automatización")
async def automation_triage(
    alert_id: uuid.UUID,
    request: Request,
    db: DbSession,
    x_ingest_key: Annotated[str | None, Header(alias="X-Ingest-Key")] = None,
) -> TriageOut:
    if not x_ingest_key or not secrets.compare_digest(x_ingest_key, settings.ingest_api_key):
        raise Unauthorized("Clave de ingesta inválida")
    return await run_triage(alert_id, request, db, actor=None, force=False)


@router.post("/{alert_id}/feedback", response_model=FeedbackOut, summary="Registrar validación humana")
async def feedback(
    alert_id: uuid.UUID,
    payload: FeedbackCreate,
    request: Request,
    db: DbSession,
    actor: Annotated[Any, Depends(require_permission(P.TRIAGE_FEEDBACK))],
) -> FeedbackOut:
    alert = await _get_alert(db, alert_id)
    if alert.status in (AlertStatus.TRIAGING, AlertStatus.TRIAGE_FAILED):
        raise Conflict("Espere o reintente el triaje antes de validar la alerta")
    existing = (
        await db.execute(
            select(AlertFeedback).where(
                AlertFeedback.alert_id == alert_id, AlertFeedback.user_id == actor.id
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.is_false_positive = payload.is_false_positive
        existing.comment = payload.comment
        entry = existing
    else:
        entry = AlertFeedback(
            alert_id=alert_id,
            user_id=actor.id,
            is_false_positive=payload.is_false_positive,
            comment=payload.comment,
        )
        db.add(entry)

    if payload.is_false_positive:
        alert.status = AlertStatus.FALSE_POSITIVE
    await audit.record(
        db, module="alerts", action="TRIAGE_FEEDBACK", user=actor, request=request,
        entity_type="alert", entity_id=alert.id,
        detail={"is_false_positive": payload.is_false_positive, "comment": payload.comment},
    )
    await db.commit()
    await db.refresh(entry)
    return FeedbackOut.model_validate(entry)


def _default_priority(severity: Severity) -> IncidentPriority:
    return {
        Severity.CRITICAL: IncidentPriority.P1,
        Severity.HIGH: IncidentPriority.P2,
        Severity.MEDIUM: IncidentPriority.P3,
        Severity.LOW: IncidentPriority.P4,
        Severity.INFO: IncidentPriority.P4,
    }[severity]


@router.post("/{alert_id}/incident", response_model=IncidentOut, status_code=201, summary="Crear incidente")
async def create_incident(
    alert_id: uuid.UUID,
    payload: IncidentCreate,
    request: Request,
    db: DbSession,
    actor: Annotated[Any, Depends(require_permission(P.INCIDENTS_CREATE))],
) -> IncidentOut:
    alert = await _get_alert(db, alert_id)
    if alert.status in (AlertStatus.TRIAGING, AlertStatus.TRIAGE_FAILED):
        raise Conflict("Espere o reintente el triaje antes de crear el incidente")
    if alert.incident is not None:
        raise Conflict("La alerta ya tiene un incidente asociado")

    priority = payload.priority or _default_priority(alert.severity)
    sla_hours = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}[priority.value]
    incident = Incident(
        alert_id=alert.id,
        ticket_id=f"OSK-{int(datetime.now(timezone.utc).timestamp()) % 1_000_000:06d}",
        title=payload.title or f"Incidente: {alert.description[:90]}",
        description=payload.description or alert.description,
        status=IncidentStatus.OPEN,
        priority=priority,
        assignee_id=payload.assignee_id or actor.id,
        sla_due_at=datetime.now(timezone.utc) + timedelta(hours=sla_hours),
    )
    db.add(incident)
    alert.status = AlertStatus.ESCALATED
    await db.flush()
    await audit.record(
        db, module="incidents", action="INCIDENT_CREATE", user=actor, request=request,
        entity_type="incident", entity_id=incident.id,
        detail={"alert_id": str(alert.id), "ticket_id": incident.ticket_id, "priority": priority.value},
    )
    await db.commit()
    incident = (
        await db.execute(
            select(Incident)
            .options(selectinload(Incident.alert), selectinload(Incident.assignee))
            .where(Incident.id == incident.id)
        )
    ).scalar_one()
    return IncidentOut.model_validate(incident)


@router.patch("/{alert_id}", response_model=AlertDetail, summary="Actualizar estado de alerta")
async def update_alert(
    alert_id: uuid.UUID,
    payload: AlertUpdate,
    request: Request,
    db: DbSession,
    actor: Annotated[Any, Depends(require_permission(P.ALERTS_UPDATE))],
) -> AlertDetail:
    alert = await _get_alert(db, alert_id)
    changes: dict[str, Any] = {}
    if payload.status is not None:
        if alert.status == AlertStatus.TRIAGING:
            raise Conflict("No se puede cambiar el estado mientras el triaje está en curso")
        if alert.status == AlertStatus.TRIAGE_FAILED:
            raise Conflict("Reintente el triaje antes de cambiar el estado de la alerta")
        if payload.status in (AlertStatus.TRIAGING, AlertStatus.TRIAGE_FAILED):
            raise AppError("Los estados de triaje se gestionan automáticamente", 400, "INVALID_ALERT_STATUS")
        changes["status"] = {"from": alert.status.value, "to": payload.status.value}
        alert.status = payload.status
    if payload.tags is not None:
        changes["tags"] = payload.tags
        alert.tags = payload.tags
    if payload.asset_criticality is not None:
        changes["asset_criticality"] = payload.asset_criticality
        alert.asset_criticality = payload.asset_criticality

    await audit.record(
        db, module="alerts", action="ALERT_UPDATE", user=actor, request=request,
        entity_type="alert", entity_id=alert.id, detail={"changes": changes},
    )
    await db.commit()
    alert = await _get_alert(db, alert_id)
    return AlertDetail.model_validate(alert)
