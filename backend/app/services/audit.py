"""Servicio de bitácora: escritura de eventos de negocio y verificación de cadena."""
from __future__ import annotations

import ipaddress
import uuid
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import client_ip
from app.core.logging import request_id_ctx
from app.models.audit import AuditLog
from app.models.enums import AuditResult
from app.models.security import User


def _ip(value: str | None) -> Any:
    if not value:
        return None
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


async def record(
    db: AsyncSession,
    *,
    module: str,
    action: str,
    user: User | None = None,
    request: Request | None = None,
    username: str | None = None,
    entity_type: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    result: AuditResult = AuditResult.SUCCESS,
    detail: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    occurred_at: datetime | None = None,
    user_id: uuid.UUID | None = None,
) -> AuditLog:
    """Añade un evento a la sesión actual. El llamador decide el commit.

    El hash y el prev_hash los calcula un trigger de PostgreSQL, de modo que la
    cadena es íntegra incluso si se escribe desde otro proceso (n8n, psql).
    """
    entry = AuditLog(
        module=module,
        action=action,
        user_id=user.id if user else user_id,
        username=username or (user.username if user else None),
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        result=result,
        detail=detail or {},
        ip=_ip(client_ip(request)) if request else None,
        user_agent=(request.headers.get("user-agent") if request else None),
        request_id=request_id_ctx.get() if request_id_ctx.get() != "-" else None,
        duration_ms=duration_ms,
        occurred_at=occurred_at or datetime.now().astimezone(),
    )
    db.add(entry)
    await db.flush()
    # El hash y la cadena los calcula un trigger de PostgreSQL; se releen para
    # que la API pueda devolverlos en la misma transacción.
    await db.refresh(entry, attribute_names=["id", "occurred_at", "prev_hash", "hash"])
    return entry


async def verify_chain(db: AsyncSession, limit: int = 5000) -> tuple[bool, int, int | None]:
    """Verifica la cadena recalculando cada hash en PostgreSQL (misma expresión
    que el trigger) y comprobando además el eslabón prev_hash."""
    from sqlalchemy import text

    rows = (
        await db.execute(
            text(
                """
                SELECT chain_seq, prev_hash, hash,
                       encode(digest(
                           COALESCE(prev_hash,'') || '|' || CAST(occurred_at AS text) || '|' ||
                           COALESCE(CAST(user_id AS text),'') || '|' || COALESCE(username,'') || '|' ||
                           module || '|' || action || '|' || COALESCE(entity_id,'') || '|' ||
                           CAST(result AS text) || '|' || COALESCE(CAST(detail AS text),'{}'), 'sha256'), 'hex') AS expected
                FROM audit_log
                ORDER BY chain_seq ASC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()

    previous = "0" * 64
    for index, row in enumerate(rows, start=1):
        if row["prev_hash"] != previous or row["hash"] != row["expected"]:
            return False, index, int(row["chain_seq"])
        previous = row["hash"]
    return True, len(rows), None
