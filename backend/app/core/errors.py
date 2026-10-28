"""Errores de aplicación con respuesta uniforme (RFC 7807 simplificado)."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.logging import request_id_ctx

logger = logging.getLogger("soc-lite.errors")


class AppError(Exception):
    def __init__(self, detail: str, status_code: int = 400, code: str | None = None):
        self.detail = detail
        self.status_code = status_code
        self.code = code or f"HTTP_{status_code}"
        super().__init__(detail)


class NotFound(AppError):
    def __init__(self, resource: str = "Recurso"):
        super().__init__(f"{resource} no encontrado", 404, "NOT_FOUND")


class Forbidden(AppError):
    def __init__(self, detail: str = "Permisos insuficientes"):
        super().__init__(detail, 403, "FORBIDDEN")


class Unauthorized(AppError):
    def __init__(self, detail: str = "Credenciales inválidas o sesión expirada"):
        super().__init__(detail, 401, "UNAUTHORIZED")


class Conflict(AppError):
    def __init__(self, detail: str):
        super().__init__(detail, 409, "CONFLICT")


def _payload(request: Request, detail: str, code: str) -> dict:
    return {
        "detail": detail,
        "code": code,
        "request_id": request_id_ctx.get(),
        "path": request.url.path,
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(request, exc.detail, exc.code),
            headers={"X-Request-ID": request_id_ctx.get()},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                **_payload(request, "Datos de entrada inválidos", "VALIDATION_ERROR"),
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("conflicto de integridad en %s: %s", request.url.path, exc.orig)
        return JSONResponse(
            status_code=409,
            content=_payload(request, "El registro entra en conflicto con datos existentes", "CONFLICT"),
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("error de base de datos en %s", request.url.path)
        return JSONResponse(
            status_code=503,
            content=_payload(request, "Servicio de datos no disponible", "DB_UNAVAILABLE"),
        )
