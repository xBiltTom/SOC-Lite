"""Incidentes derivados del triaje."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import IncidentPriority, IncidentStatus
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.security import User


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL")
    )
    ticket_id: Mapped[str | None] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[IncidentStatus] = mapped_column(
        pg_enum(IncidentStatus, "incident_status"), nullable=False, default=IncidentStatus.OPEN
    )
    priority: Mapped[IncidentPriority] = mapped_column(
        pg_enum(IncidentPriority, "incident_priority"), nullable=False, default=IncidentPriority.P3
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alert: Mapped[Optional["Alert"]] = relationship(back_populates="incident", lazy="selectin")
    assignee: Mapped[Optional["User"]] = relationship(lazy="selectin")

    @property
    def assignee_name(self) -> str | None:
        return self.assignee.full_name if self.assignee else None

    @property
    def alert_severity(self):
        return self.alert.severity if self.alert else None

    @property
    def alert_description(self) -> str | None:
        return self.alert.description if self.alert else None
