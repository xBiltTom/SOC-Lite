"""Healthchecks para orquestadores (Docker/Kubernetes)."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.common import HealthOut

router = APIRouter(prefix="/health", tags=["Salud"])


async def _database_ok() -> bool:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("", response_model=HealthOut, summary="Estado del servicio")
async def health() -> HealthOut:
    db_ok = await _database_ok()
    return HealthOut(
        status="ok" if db_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database="ok" if db_ok else "unavailable",
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/ready", summary="Readiness probe")
async def ready() -> dict[str, str]:
    db_ok = await _database_ok()
    triage_ok = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.triage_service_url.rstrip('/')}/health")
            triage_ok = response.status_code == 200
    except httpx.HTTPError:
        triage_ok = False
    return {
        "status": "ready" if db_ok else "not_ready",
        "database": "ok" if db_ok else "unavailable",
        "triage_service": "ok" if triage_ok else "degraded",
    }
