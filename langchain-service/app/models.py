"""Contrato de entrada/salida del microservicio de triaje."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Severity = Literal["critical", "high", "medium", "low", "info"]
Verdict = Literal["true_positive", "false_positive", "suspicious", "benign", "inconclusive"]


class EnrichmentIn(BaseModel):
    provider: str
    indicator: str
    indicator_type: str | None = None
    verdict: str | None = None
    score: float | None = None
    country: str | None = None
    asn: str | None = None


class AlertIn(BaseModel):
    alert_id: str | None = None
    source: str = "wazuh"
    rule_id: str | None = None
    rule_level: int | None = None
    description: str = Field(min_length=1, max_length=4000)
    src_ip: str | None = None
    dst_ip: str | None = None
    agent_name: str | None = None
    asset_criticality: int = Field(default=3, ge=1, le=5)
    severity: Severity = "medium"
    tags: list[str] = []
    raw_payload: dict[str, Any] = {}
    enrichment: list[EnrichmentIn] = []

    @field_validator("rule_level")
    @classmethod
    def level_range(cls, value: int | None) -> int | None:
        if value is not None and not 0 <= value <= 16:
            raise ValueError("rule_level fuera de rango")
        return value


class RecommendedAction(BaseModel):
    action: str = Field(max_length=300)
    priority: int = Field(default=2, ge=1, le=4)
    owner: str = Field(default="SOC", max_length=60)


class TriageOut(BaseModel):
    verdict: Verdict
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=10, max_length=1200)
    reasoning: str | None = Field(default=None, max_length=4000)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list, max_length=8)
    mitre_techniques: list[str] = Field(default_factory=list, max_length=10)
    model: str
    prompt_version: str
    latency_ms: int
    status: Literal["completed", "degraded", "failed"] = "completed"
    needs_human: bool = False
    fallback_used: bool = False
    enrichment: list[dict[str, Any]] = []
    raw_response: dict[str, Any] = {}


class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    llm_enabled: bool
    llm: str
