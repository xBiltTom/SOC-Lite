"""Endpoints de métricas e indicadores del dashboard."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.deps import DbSession, require_permission
from app.core.permissions import P
from app.schemas.dashboard import (
    AnalystRow,
    DashboardSummary,
    FpPoint,
    MtttRow,
    SeverityDistribution,
    SlaRow,
    TopSource,
    TrendPoint,
)
from app.services import dashboard

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

ReadDashboard = Annotated[Any, Depends(require_permission(P.DASHBOARD_READ))]
Days = Annotated[int, Query(ge=1, le=365, description="Ventana en días")]


@router.get("/summary", response_model=DashboardSummary, summary="KPIs principales")
async def summary(db: DbSession, _: ReadDashboard, days: Days = 30) -> dict:
    return await dashboard.summary(db, days)


@router.get("/trend", response_model=list[TrendPoint], summary="Serie diaria de alertas")
async def trend(db: DbSession, _: ReadDashboard, days: Days = 30) -> list[dict]:
    return await dashboard.trend(db, days)


@router.get("/severity", response_model=SeverityDistribution, summary="Distribución por severidad")
async def severity(db: DbSession, _: ReadDashboard, days: Days = 30) -> dict:
    return await dashboard.severity_distribution(db, days)


@router.get("/top-sources", response_model=list[TopSource], summary="Top orígenes")
async def top_sources(
    db: DbSession,
    _: ReadDashboard,
    days: Days = 30,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    by: Annotated[str, Query(pattern="^(ip|agent|rule)$")] = "ip",
) -> list[dict]:
    return await dashboard.top_sources(db, days, limit, by)


@router.get("/mttt", response_model=list[MtttRow], summary="MTTT por severidad")
async def mttt(db: DbSession, _: ReadDashboard, days: Days = 30) -> list[dict]:
    return await dashboard.mttt_by_severity(db, days)


@router.get("/fp-rate", response_model=list[FpPoint], summary="Tasa de falsos positivos")
async def fp_rate(db: DbSession, _: ReadDashboard, days: Days = 30) -> list[dict]:
    return await dashboard.fp_series(db, days)


@router.get("/sla", response_model=list[SlaRow], summary="Cumplimiento de SLA")
async def sla(db: DbSession, _: ReadDashboard, days: Days = 30) -> list[dict]:
    return await dashboard.sla_rows(db, days)


@router.get("/analysts", response_model=list[AnalystRow], summary="Actividad por analista")
async def analysts(db: DbSession, _: ReadDashboard, days: Days = 30) -> list[dict]:
    return await dashboard.analyst_activity(db, days)
