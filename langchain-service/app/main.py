"""Microservicio de triaje SOC-Lite (FastAPI + LangChain)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.triage_agent import agent, memory
from app.config import settings
from app.models import AlertIn, HealthOut, TriageOut

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("soc-lite.triage")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Triage service iniciado (modelo=%s, llm_enabled=%s)",
                settings.llm_model, settings.llm_enabled)
    yield
    logger.info("Triage service detenido")


app = FastAPI(
    title=settings.service_name,
    version=settings.version,
    description=(
        "Enriquecimiento y clasificación de alertas SOC con LangChain. "
        "Degrada a un motor heurístico local si el proveedor LLM no está disponible."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health", response_model=HealthOut, tags=["Salud"])
async def health() -> HealthOut:
    llm = "disabled" if not settings.llm_enabled else ("configured" if settings.llm_api_key.strip() else "missing_key")
    return HealthOut(
        status="degraded" if llm == "missing_key" else "ok",
        service=settings.service_name,
        version=settings.version,
        llm_enabled=settings.llm_enabled,
        llm=llm,
    )


@app.post("/triage", response_model=TriageOut, tags=["Triaje"], summary="Triar una alerta")
async def triage(alert: AlertIn) -> TriageOut:
    return await agent.triage(alert)


@app.get("/memory", tags=["Triaje"], summary="Memoria de casos recientes")
async def get_memory() -> dict:
    memory._load()  # noqa: SLF001
    return {
        "entries": len(memory._data),  # noqa: SLF001
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "keys": list(memory._data.keys())[:50],  # noqa: SLF001
    }


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": settings.service_name, "docs": "/docs", "triage": "/triage"}
