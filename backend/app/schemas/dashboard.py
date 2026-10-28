"""Esquemas de métricas del dashboard."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import Severity


class Period(BaseModel):
    days: int
    date_from: date
    date_to: date


class Totals(BaseModel):
    alerts: int
    critical: int
    high: int
    medium: int
    low: int
    info: int
    triaged: int
    pending: int
    incidents_open: int
    false_positive: int


class Rates(BaseModel):
    automation: float          # % de alertas con triaje automático
    false_positive: float      # % de falsos positivos sobre alertas triadas
    sla_compliance: float      # % de triajes dentro del SLA
    human_review: float        # % de triajes que requieren humano


class MTTT(BaseModel):
    avg_minutes: float
    p95_minutes: float
    target_minutes: float


class Deltas(BaseModel):
    alerts_pct: float
    mttt_pct: float


class DashboardSummary(BaseModel):
    period: Period
    totals: Totals
    rates: Rates
    mttt: MTTT
    deltas: Deltas
    generated_at: datetime


class TrendPoint(BaseModel):
    date: date
    total: int
    critical: int
    high: int
    medium: int
    low: int
    false_positive: int


class SeveritySlice(BaseModel):
    severity: Severity
    count: int


class TopSource(BaseModel):
    key: str
    label: str
    count: int
    critical: int


class MtttRow(BaseModel):
    severity: Severity
    count: int
    avg_minutes: float
    p95_minutes: float
    target_minutes: int
    compliance: float


class FpPoint(BaseModel):
    date: date
    triaged: int
    false_positive: int
    rate: float


class SlaRow(BaseModel):
    severity: Severity
    target_minutes: int
    total: int
    within_sla: int
    compliance: float
    breaches: int


class AnalystRow(BaseModel):
    username: str
    full_name: str
    actions: int
    triages: int


class SeverityDistribution(BaseModel):
    items: list[SeveritySlice]
    total: int
