"""Migración aditiva y recuperación de intentos interrumpidos al iniciar la API."""
import logging

from sqlalchemy import select, text

from app.db.session import SessionLocal, engine
from app.models.alert import Alert
from app.models.enums import AlertStatus, AuditResult
from app.services import audit

logger = logging.getLogger(__name__)


async def initialize_recovery() -> None:
    # PostgreSQL requiere confirmar el nuevo valor del enum antes de usarlo.
    async with engine.begin() as connection:
        exists = await connection.scalar(text(
            "SELECT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            "WHERE t.typname = 'alert_status' AND e.enumlabel = 'triage_failed')"
        ))
        if not exists:
            await connection.execute(text("ALTER TYPE alert_status ADD VALUE IF NOT EXISTS 'triage_failed'"))

    # El backend usa un único proceso: al arrancar no puede quedar un intento anterior activo.
    async with SessionLocal() as db:
        alerts = (await db.execute(select(Alert).where(Alert.status == AlertStatus.TRIAGING))).scalars().all()
        for alert in alerts:
            alert.status = AlertStatus.TRIAGE_FAILED
            await audit.record(
                db, module="triage", action="TRIAGE_INTERRUPTED", username="system",
                entity_type="alert", entity_id=alert.id, result=AuditResult.FAILURE,
                detail={"reason": "El servicio se reinició durante el triaje"},
            )
        await db.commit()
        if alerts:
            logger.warning("Se recuperaron %s triajes interrumpidos", len(alerts))
