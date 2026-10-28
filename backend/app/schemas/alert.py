"""Esquemas de alertas, enriquecimiento, triaje e incidentes."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    AlertStatus,
    IncidentPriority,
    IncidentStatus,
    Severity,
    TriageStatus,
    TriageVerdict,
)
from app.schemas.common import IPAddressStr, ORMModel


class TriageOut(ORMModel):
    id: UUID
    verdict: TriageVerdict
    severity: Severity
    confidence: float
    summary: str
    reasoning: str | None = None
    recommended_actions: list[dict[str, Any]] = []
    mitre_techniques: list[str] = []
    model: str | None = None
    prompt_version: str | None = None
    latency_ms: int | None = None
    status: TriageStatus
    needs_human: bool = False
    fallback_used: bool = False
    triaged_at: datetime


class EnrichmentOut(ORMModel):
    id: int
    provider: str
    indicator: str
    indicator_type: str
    verdict: str | None = None
    score: float | None = None
    country: str | None = None
    asn: str | None = None
    raw: dict[str, Any] = {}
    fetched_at: datetime


class FeedbackOut(ORMModel):
    id: int
    user_id: UUID | None = None
    is_false_positive: bool
    comment: str | None = None
    created_at: datetime


class IncidentBrief(ORMModel):
    id: UUID
    ticket_id: str | None = None
    title: str
    status: IncidentStatus
    priority: IncidentPriority
    assignee_id: UUID | None = None
    sla_due_at: datetime | None = None
    opened_at: datetime


class AlertListItem(ORMModel):
    id: UUID
    external_id: str | None = None
    source: str
    rule_id: str | None = None
    rule_level: int | None = None
    description: str
    src_ip: IPAddressStr = None
    dst_ip: IPAddressStr = None
    agent_name: str | None = None
    asset_criticality: int
    severity: Severity
    status: AlertStatus
    received_at: datetime
    occurred_at: datetime
    dedup_count: int = 1
    verdict: TriageVerdict | None = None
    confidence: float | None = None
    summary: str | None = None
    triaged_at: datetime | None = None
    mttt_minutes: float | None = None
    incident_id: UUID | None = None
    ticket_id: str | None = None


class AlertDetail(ORMModel):
    id: UUID
    external_id: str | None = None
    source: str
    rule_id: str | None = None
    rule_level: int | None = None
    description: str
    src_ip: IPAddressStr = None
    dst_ip: IPAddressStr = None
    src_port: int | None = None
    dst_port: int | None = None
    protocol: str | None = None
    agent_name: str | None = None
    asset_criticality: int
    severity: Severity
    status: AlertStatus
    fingerprint: str
    raw_payload: dict[str, Any] = {}
    tags: list[str] = []
    dedup_count: int
    occurred_at: datetime
    received_at: datetime
    last_seen_at: datetime
    created_at: datetime
    triage_results: list[TriageOut] = []
    enrichments: list[EnrichmentOut] = []
    feedback: list[FeedbackOut] = []
    incident: IncidentBrief | None = None
    mttt_minutes: float | None = None


class AlertUpdate(BaseModel):
    status: AlertStatus | None = None
    tags: list[str] | None = None
    asset_criticality: int | None = Field(default=None, ge=1, le=5)


class FeedbackCreate(BaseModel):
    is_false_positive: bool
    comment: str | None = Field(default=None, max_length=1000)


class IncidentCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    priority: IncidentPriority | None = None
    assignee_id: UUID | None = None
    description: str | None = Field(default=None, max_length=4000)


class IncidentOut(ORMModel):
    id: UUID
    alert_id: UUID | None = None
    ticket_id: str | None = None
    title: str
    description: str | None = None
    status: IncidentStatus
    priority: IncidentPriority
    assignee_id: UUID | None = None
    assignee_name: str | None = None
    alert_severity: Severity | None = None
    alert_description: str | None = None
    sla_due_at: datetime | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    resolution: str | None = None
    created_at: datetime


class IncidentUpdate(BaseModel):
    status: IncidentStatus | None = None
    priority: IncidentPriority | None = None
    assignee_id: UUID | None = None
    resolution: str | None = Field(default=None, max_length=4000)


class IngestResponse(BaseModel):
    status: str
    alert_id: UUID | None = None
    severity: Severity | None = None
    deduplicated: bool = False
    message: str | None = None


class TriageRequest(BaseModel):
    force: bool = False


class RawAlertPayload(BaseModel):
    """Contrato laxo para Wazuh/OPNsense: se valida en el normalizador, no aquí."""

    model_config = {"extra": "allow"}
    id: str | None = None
    rule: dict[str, Any] | None = None
    agent: dict[str, Any] | None = None
    data: dict[str, Any] | None = None
    severity: str | None = None
    source: str | None = None

    @field_validator("severity")
    @classmethod
    def valid_severity(cls, value: str | None) -> str | None:
        if value and value not in {s.value for s in Severity}:
            raise ValueError(f"severidad inválida: {value}")
        return value
