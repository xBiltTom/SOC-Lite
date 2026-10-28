"""Middlewares: request-id, cabeceras de seguridad y bitácora de acceso.

La bitácora registra ENTRADA y SALIDA por módulo (usuario, fecha, hora, acción),
además de los eventos de negocio que cada router anota explícitamente.
"""
from __future__ import annotations

import ipaddress
import logging
import time
import uuid
from datetime import datetime, timezone

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import request_id_ctx
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.enums import AuditResult

logger = logging.getLogger("soc-lite.audit")

SKIP_PATHS = ("/health", "/docs", "/redoc", "/openapi.json", "/metrics", "/favicon.ico")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=()")
        response.headers.setdefault("Cache-Control", "no-store")
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def _module_from_path(path: str) -> str:
    tail = path.removeprefix(settings.api_v1_prefix).strip("/")
    return tail.split("/")[0] if tail else "root"


def _identity(request: Request) -> tuple[uuid.UUID | None, str | None]:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        if request.headers.get("x-ingest-key"):
            return None, "webhook"
        return None, None
    try:
        payload = decode_token(header.split(" ", 1)[1].strip(), "access")
        return uuid.UUID(payload["sub"]), payload.get("username")
    except (jwt.PyJWTError, ValueError, KeyError):
        return None, None


class AuditAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if (
            not path.startswith(settings.api_v1_prefix)
            or path.startswith(SKIP_PATHS)
            or request.method == "OPTIONS"
        ):
            return await call_next(request)

        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        user_id, username = _identity(request)
        module = _module_from_path(path)
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            if status_code < 400:
                result = AuditResult.SUCCESS
            elif status_code in (401, 403):
                result = AuditResult.DENIED
            else:
                result = AuditResult.FAILURE
            raw_ip = request.client.host if request.client else None
            try:
                ip_value = ipaddress.ip_address(raw_ip) if raw_ip else None
            except ValueError:
                ip_value = None
            shared = {
                "user_id": user_id,
                "username": username,
                "module": module,
                "entity_type": "request",
                "ip": ip_value,
                "user_agent": request.headers.get("user-agent"),
                "request_id": request_id_ctx.get(),
            }
            try:
                async with SessionLocal() as session:
                    session.add_all(
                        [
                            AuditLog(
                                **shared,
                                action="ENTER",
                                result=result,
                                occurred_at=started_at,
                                detail={
                                    "method": request.method,
                                    "path": path,
                                    "query": str(request.url.query)[:500],
                                },
                            ),
                            AuditLog(
                                **shared,
                                action="EXIT",
                                result=result,
                                duration_ms=duration_ms,
                                detail={
                                    "method": request.method,
                                    "path": path,
                                    "status_code": status_code,
                                },
                            ),
                        ]
                    )
                    await session.commit()
            except Exception:  # nunca romper la respuesta por fallar la auditoría
                logger.exception("no se pudo escribir la bitácora de acceso")
                if settings.is_production:
                    raise
