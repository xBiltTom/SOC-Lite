"""Punto de entrada de SOC-Lite API."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.v1.routers import health
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import engine
from app.services.triage_recovery import initialize_recovery
from app.middleware.audit_middleware import (
    AuditAccessMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)

configure_logging()
logger = logging.getLogger("soc-lite")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_production and settings.secret_key.startswith("dev-"):
        raise RuntimeError("SECRET_KEY de desarrollo detectada en producción")
    await initialize_recovery()
    logger.info("SOC-Lite API iniciada", extra={"environment": settings.environment})
    yield
    await engine.dispose()
    logger.info("SOC-Lite API detenida")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Triaje automático de alertas SOC con orquestación n8n, enriquecimiento "
        "LangChain y dashboard operativo. RBAC, bitácora append-only y reportes "
        "PDF/Word/Excel."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={"name": "Equipo SOC-Lite"},
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Ingest-Key", "X-Request-ID", "X-Source"],
    expose_headers=["X-Request-ID", "X-Response-Time-ms", "Content-Disposition"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditAccessMiddleware)
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api": settings.api_v1_prefix,
    }
