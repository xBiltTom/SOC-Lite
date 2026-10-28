"""Enumeraciones compartidas entre ORM, esquemas y lógica de negocio."""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - utilidad
        return self.value


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def weight(self) -> int:
        return {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}[self.value]

    @classmethod
    def from_rule_level(cls, level: int | None) -> "Severity":
        level = level or 0
        if level >= 12:
            return cls.CRITICAL
        if level >= 10:
            return cls.HIGH
        if level >= 7:
            return cls.MEDIUM
        if level >= 4:
            return cls.LOW
        return cls.INFO


class AlertStatus(StrEnum):
    PENDING = "pending"
    TRIAGING = "triaging"
    TRIAGED = "triaged"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    CLOSED = "closed"
    FALSE_POSITIVE = "false_positive"
    DISCARDED = "discarded"


class TriageVerdict(StrEnum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    SUSPICIOUS = "suspicious"
    BENIGN = "benign"
    INCONCLUSIVE = "inconclusive"


class TriageStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    FAILED = "failed"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentPriority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class AuditResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class ReportType(StrEnum):
    OPERATIONAL = "operational"
    MANAGEMENT = "management"
    AUDIT = "audit"


class ReportFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"


class ReportStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class IntegrationType(StrEnum):
    SIEM = "siem"
    EDR = "edr"
    TICKETING = "ticketing"
    CHAT = "chat"
    THREAT_INTEL = "threat_intel"
    LLM = "llm"
