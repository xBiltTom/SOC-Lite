"""Cliente del microservicio de triaje (LangChain) con degradación controlada.

Principio de diseño: el agente propone, el backend valida y persiste. Si el
microservicio LLM no responde, entra un motor heurístico local marcado como
`degraded`; la alerta nunca se queda sin triaje (operación 24/7).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.errors import AppError
from app.models.alert import Alert
from app.models.enums import Severity, TriageStatus, TriageVerdict

logger = logging.getLogger("soc-lite.triage")


class RemoteTriage(BaseModel):
    verdict: TriageVerdict
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    summary: str
    reasoning: str | None = None
    recommended_actions: list[dict[str, Any]] = []
    mitre_techniques: list[str] = []
    model: str | None = None
    prompt_version: str | None = None
    latency_ms: int | None = None
    status: TriageStatus = TriageStatus.COMPLETED
    needs_human: bool = False
    fallback_used: bool = False
    enrichment: list[dict[str, Any]] = []


@dataclass(slots=True)
class TriageOutput:
    verdict: TriageVerdict
    severity: Severity
    confidence: float
    summary: str
    reasoning: str | None = None
    recommended_actions: list[dict[str, Any]] = field(default_factory=list)
    mitre_techniques: list[str] = field(default_factory=list)
    model: str = "heuristica-local"
    prompt_version: str = "v1.2.0"
    latency_ms: int = 0
    status: TriageStatus = TriageStatus.COMPLETED
    needs_human: bool = False
    fallback_used: bool = False
    raw_response: dict[str, Any] = field(default_factory=dict)
    enrichment: list[dict[str, Any]] = field(default_factory=list)


_ACTION_BY_TAG = {
    "ransomware": "Aislar el host de la red y preservar evidencia forense",
    "bruteforce": "Bloquear la IP de origen y revisar accesos exitosos",
    "web-exploit": "Aplicar mitigación WAF y parchear el servicio afectado",
    "execution": "Recolectar árbol de procesos y aislar el endpoint",
    "recon": "Bloquear el origen en el firewall perimetral",
    "dns": "Verificar el proceso que originó la consulta DNS",
}

_MITRE_BY_TAG = {
    "ransomware": ["T1486"],
    "bruteforce": ["T1110"],
    "web-exploit": ["T1190"],
    "execution": ["T1059.001"],
    "recon": ["T1046"],
    "dns": ["T1071.004"],
}


def _heuristic(alert: Alert, enrichments: list[dict[str, Any]] | None = None) -> TriageOutput:
    """Motor de respaldo determinista, sin red ni LLM."""
    level = alert.rule_level or 0
    criticality = alert.asset_criticality or 3
    malicious = sum(
        1
        for item in enrichments or []
        if item.get("status") in (None, "ok")
        and str(item.get("verdict", "")).lower() in {"malicious", "suspicious"}
    )
    score = (level / 14) * 55 + (criticality / 5) * 25 + min(malicious * 8, 20)

    if score >= 50:
        verdict = TriageVerdict.SUSPICIOUS
    else:
        verdict = TriageVerdict.INCONCLUSIVE

    severity = alert.severity
    confidence = 0.5  # Indicador orientativo, no probabilidad calibrada.
    tags = alert.tags or []
    actions: list[dict[str, Any]] = []
    for tag, action in _ACTION_BY_TAG.items():
        if tag in tags:
            actions.append({"action": action, "priority": 1, "owner": "SOC"})
    if not actions:
        actions.append(
            {
                "action": "Validar el evento con el propietario del activo antes de escalar",
                "priority": 2,
                "owner": "Analista",
            }
        )
    actions.append(
        {
            "action": "Correlacionar con eventos de las últimas 24 horas en el SIEM",
            "priority": 3,
            "owner": "Analista",
        }
    )

    mitre: list[str] = []
    for tag in tags:
        mitre.extend(_MITRE_BY_TAG.get(tag, []))
    mitre = sorted(set(mitre))

    summary = (
        f"Triaje heurístico local (LLM no disponible): nivel de regla {level}, "
        f"criticidad del activo {criticality}/5 y {malicious} indicador(es) maliciosos. "
        f"Veredicto {verdict.value} con severidad {severity.value}."
    )
    return TriageOutput(
        verdict=verdict,
        severity=severity,
        confidence=confidence,
        summary=summary,
        reasoning=(
            "Puntaje compuesto = 55% nivel de regla + 25% criticidad del activo + "
            "20% reputación de indicadores. El puntaje prioriza la revisión y no confirma "
            "un ataque; la confianza es orientativa y no está calibrada."
        ),
        recommended_actions=actions,
        mitre_techniques=mitre,
        model="heuristic-engine",
        prompt_version="heuristic-v2",
        status=TriageStatus.DEGRADED,
        needs_human=True,
        fallback_used=True,
        raw_response={"score": round(score, 2), "malicious_indicators": malicious},
    )


def _payload(alert: Alert, enrichments: list[dict[str, Any]] | None) -> dict[str, Any]:
    return {
        "alert_id": str(alert.id),
        "source": alert.source,
        "rule_id": alert.rule_id,
        "rule_level": alert.rule_level,
        "description": alert.description,
        "src_ip": str(alert.src_ip) if alert.src_ip else None,
        "dst_ip": str(alert.dst_ip) if alert.dst_ip else None,
        "agent_name": alert.agent_name,
        "asset_criticality": alert.asset_criticality,
        "severity": alert.severity.value,
        "tags": alert.tags,
        "raw_payload": alert.raw_payload,
        "enrichment": enrichments or [],
    }


async def run_triage(
    alert: Alert, enrichments: list[dict[str, Any]] | None = None
) -> TriageOutput:
    url = f"{settings.triage_service_url.rstrip('/')}/triage"
    try:
        async with httpx.AsyncClient(timeout=settings.triage_timeout_seconds) as client:
            response = await client.post(url, json=_payload(alert, enrichments))
            response.raise_for_status()
            parsed = RemoteTriage.model_validate(response.json())
            return TriageOutput(
                **parsed.model_dump(),
                raw_response=response.json(),
            )
    except (httpx.HTTPError, ValidationError, ValueError) as exc:
        logger.warning("triaje remoto no disponible (%s); se usa heurística local", exc)
        if not settings.triage_fail_open:
            raise AppError("Servicio de triaje no disponible", 503, "TRIAGE_UNAVAILABLE") from exc
        return _heuristic(alert, enrichments)
