"""Esquemas de reportes y bitácora."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AuditResult, ReportFormat, ReportStatus, ReportType
from app.schemas.common import IPAddressStr, ORMModel


class ReportCreate(BaseModel):
    type: ReportType
    format: ReportFormat
    date_from: date | None = None
    date_to: date | None = None
    title: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def _check_range(self) -> "ReportCreate":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from no puede ser posterior a date_to")
        return self


class ReportOut(ORMModel):
    id: UUID
    type: ReportType
    format: ReportFormat
    status: ReportStatus
    params: dict[str, Any] = {}
    file_size: int | None = None
    requested_by: UUID | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class AuditOut(ORMModel):
    id: int
    occurred_at: datetime
    user_id: UUID | None = None
    username: str | None = None
    module: str
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    result: AuditResult
    detail: dict[str, Any] = {}
    ip: IPAddressStr = None
    user_agent: str | None = None
    request_id: str | None = None
    duration_ms: int | None = None
    hash: str | None = None


class ChainVerify(BaseModel):
    valid: bool
    checked: int
    broken_at: int | None = None
    message: str


class AuditEventIn(BaseModel):
    module: str = Field(min_length=2, max_length=40)
    action: str = Field(min_length=2, max_length=60)
    entity_type: str | None = Field(default=None, max_length=40)
    entity_id: str | None = Field(default=None, max_length=120)
    result: AuditResult = AuditResult.SUCCESS
    username: str | None = Field(default=None, max_length=60)
    detail: dict[str, Any] = {}


class AuditStats(BaseModel):
    total: int
    success: int
    failure: int
    denied: int
    modules: list[dict[str, Any]]
