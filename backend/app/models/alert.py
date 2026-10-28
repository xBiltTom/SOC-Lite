"""Alertas, enriquecimiento, triaje y retroalimentación."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    AlertStatus,
    Severity,
    TriageStatus,
    TriageVerdict,
)
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.incident import Incident


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="wazuh")
    rule_id: Mapped[str | None] = mapped_column(Text)
    rule_level: Mapped[int | None] = mapped_column(SmallInteger)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    src_ip: Mapped[Any | None] = mapped_column(INET)
    dst_ip: Mapped[Any | None] = mapped_column(INET)
    src_port: Mapped[int | None] = mapped_column(Integer)
    dst_port: Mapped[int | None] = mapped_column(Integer)
    protocol: Mapped[str | None] = mapped_column(Text)
    agent_name: Mapped[str | None] = mapped_column(Text)
    asset_criticality: Mapped[int] = mapped_column(SmallInteger, default=3, nullable=False)
    severity: Mapped[Severity] = mapped_column(
        pg_enum(Severity, "severity_level"), nullable=False, default=Severity.MEDIUM
    )
    status: Mapped[AlertStatus] = mapped_column(
        pg_enum(AlertStatus, "alert_status"), nullable=False, default=AlertStatus.PENDING
    )
    fingerprint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    dedup_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    triage_results: Mapped[list["TriageResult"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan", order_by="TriageResult.triaged_at.desc()"
    )
    enrichments: Mapped[list["EnrichmentData"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )
    feedback: Mapped[list["AlertFeedback"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )
    incident: Mapped[Optional["Incident"]] = relationship(back_populates="alert", uselist=False)

    __table_args__ = (
        Index("idx_alerts_severity", "severity"),
        Index("idx_alerts_status", "status"),
        Index("idx_alerts_received", "received_at"),
    )

    @property
    def latest_triage(self) -> "TriageResult | None":
        return self.triage_results[0] if self.triage_results else None


class EnrichmentData(Base):
    __tablename__ = "enrichment_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    indicator: Mapped[str] = mapped_column(Text, nullable=False)
    indicator_type: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    country: Mapped[str | None] = mapped_column(Text)
    asn: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    alert: Mapped[Alert] = relationship(back_populates="enrichments")


class TriageResult(Base):
    __tablename__ = "triage_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    verdict: Mapped[TriageVerdict] = mapped_column(
        pg_enum(TriageVerdict, "triage_verdict"), nullable=False
    )
    severity: Mapped[Severity] = mapped_column(pg_enum(Severity, "severity_level"), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    recommended_actions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    mitre_techniques: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[TriageStatus] = mapped_column(
        pg_enum(TriageStatus, "triage_status"), nullable=False, default=TriageStatus.COMPLETED
    )
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    triaged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alert: Mapped[Alert] = relationship(back_populates="triage_results")


class AlertFeedback(Base):
    __tablename__ = "alert_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    is_false_positive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alert: Mapped[Alert] = relationship(back_populates="feedback")
