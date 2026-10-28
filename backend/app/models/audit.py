"""Bitácora de auditoría y almacenamiento de reportes."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import (
    AuditResult,
    IntegrationType,
    ReportFormat,
    ReportStatus,
    ReportType,
)
from app.models.types import pg_enum


class AuditLog(Base):
    """Append-only. La cadena de hashes y la inmutabilidad viven en PostgreSQL."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chain_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    username: Mapped[str | None] = mapped_column(Text)
    module: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[str | None] = mapped_column(Text)
    result: Mapped[AuditResult] = mapped_column(
        pg_enum(AuditResult, "audit_result"), nullable=False, default=AuditResult.SUCCESS
    )
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    ip: Mapped[Any | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    prev_hash: Mapped[str | None] = mapped_column(Text)
    hash: Mapped[str | None] = mapped_column(Text)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[ReportType] = mapped_column(pg_enum(ReportType, "report_type"), nullable=False)
    format: Mapped[ReportFormat] = mapped_column(
        pg_enum(ReportFormat, "report_format"), nullable=False
    )
    status: Mapped[ReportStatus] = mapped_column(
        pg_enum(ReportStatus, "report_status"), nullable=False, default=ReportStatus.QUEUED
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    type: Mapped[IntegrationType] = mapped_column(
        pg_enum(IntegrationType, "integration_type"), nullable=False
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
