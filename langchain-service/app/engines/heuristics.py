"""Motor heurístico de respaldo: determinista, sin LLM y sin red.

Se usa cuando el proveedor LLM no está disponible, el modelo no responde o la salida no
valida. La alerta nunca queda sin triaje y el resultado se marca `degraded`.
"""
from __future__ import annotations

from typing import Any

from app.models import AlertIn, RecommendedAction, TriageOut

_ACTIONS = {
    "ransomware": ("Aislar el host de la red y preservar evidencia forense", 1, "SOC"),
    "bruteforce": ("Bloquear la IP de origen y revisar accesos exitosos", 1, "SOC"),
    "web-exploit": ("Aplicar mitigación WAF y parchear el servicio afectado", 1, "Infraestructura"),
    "execution": ("Recolectar árbol de procesos y aislar el endpoint", 1, "SOC"),
    "recon": ("Bloquear el origen en el firewall perimetral", 2, "Infraestructura"),
    "dns": ("Verificar el proceso que originó la consulta DNS", 2, "Analista"),
    "high-impact": ("Abrir incidente y notificar al propietario del activo", 2, "SOC"),
}

_MITRE = {
    "ransomware": "T1486",
    "bruteforce": "T1110",
    "web-exploit": "T1190",
    "execution": "T1059.001",
    "recon": "T1046",
    "dns": "T1071.004",
}


def _malicious_count(enrichment: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in enrichment
        if str(item.get("verdict", "")).lower() in {"malicious", "suspicious"}
    )


def heuristic(
    alert: AlertIn,
    enrichment: list[dict[str, Any]] | None = None,
    memory_hint: dict[str, Any] | None = None,
    reason: str = "LLM no disponible",
) -> TriageOut:
    enrichment = enrichment or []
    level = alert.rule_level or 0
    malicious = _malicious_count(enrichment)
    score = (level / 14) * 50 + (alert.asset_criticality / 5) * 25 + min(malicious * 9, 25)

    if memory_hint and memory_hint.get("false_positives", 0) >= 2:
        score -= 25

    if score >= 65:
        verdict = "true_positive"
    elif score >= 45:
        verdict = "suspicious"
    elif score >= 25:
        verdict = "inconclusive"
    else:
        verdict = "benign"

    severity = alert.severity
    if verdict == "true_positive" and severity in ("low", "medium"):
        severity = "high"
    if verdict == "benign" and severity in ("critical", "high"):
        severity = "medium"

    actions: list[RecommendedAction] = []
    for tag in alert.tags:
        if tag in _ACTIONS:
            text, priority, owner = _ACTIONS[tag]
            actions.append(RecommendedAction(action=text, priority=priority, owner=owner))
    if not actions:
        actions.append(
            RecommendedAction(
                action="Validar el evento con el propietario del activo antes de escalar",
                priority=2,
                owner="Analista",
            )
        )
    actions.append(
        RecommendedAction(
            action="Correlacionar con eventos de las últimas 24 horas en el SIEM",
            priority=3,
            owner="Analista",
        )
    )

    mitre = sorted({_MITRE[tag] for tag in alert.tags if tag in _MITRE})
    confidence = round(min(0.9, 0.45 + score / 220), 3)
    return TriageOut(
        verdict=verdict,
        severity=severity,
        confidence=confidence,
        summary=(
            f"Triaje heurístico ({reason}): regla nivel {level}, activo {alert.asset_criticality}/5, "
            f"{malicious} indicador(es) con reputación negativa. Veredicto {verdict} "
            f"con severidad {severity}."
        ),
        reasoning=(
            "Puntaje = 50% nivel de regla + 25% criticidad del activo + 25% reputación de "
            "indicadores, con penalización por falsos positivos recurrentes en la memoria local. "
            "Resultado degradado: no sustituye la revisión de un analista."
        ),
        recommended_actions=actions[:5],
        mitre_techniques=mitre,
        model="heuristic-engine",
        prompt_version="heuristic-v1",
        latency_ms=0,
        status="degraded",
        needs_human=verdict in ("inconclusive", "suspicious"),
        fallback_used=True,
        enrichment=enrichment,
        raw_response={"score": round(score, 2), "malicious_indicators": malicious, "reason": reason},
    )
