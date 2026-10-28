"""Normalización de alertas provenientes de Wazuh, OPNsense y Suricata.

El webhook acepta el JSON crudo del SIEM: aquí se extraen los campos comunes,
se calcula la huella de correlación y se mapea el nivel de regla a severidad.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.models.enums import Severity

_SEVERITY_ALIASES = {
    "crit": "critical",
    "critical": "critical",
    "alta": "high",
    "high": "high",
    "media": "medium",
    "medium": "medium",
    "baja": "low",
    "low": "low",
    "info": "info",
    "informational": "info",
}

_TAG_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"brute|fuerza bruta|failed password", re.I), "bruteforce"),
    (re.compile(r"ransom|cifrado|locked", re.I), "ransomware"),
    (re.compile(r"scan|escaneo", re.I), "recon"),
    (re.compile(r"powershell|cmd\.exe|wmic", re.I), "execution"),
    (re.compile(r"sql|xss|traversal|cve-", re.I), "web-exploit"),
    (re.compile(r"dns|domain", re.I), "dns"),
    (re.compile(r"firewall|block|deny", re.I), "firewall"),
)


@dataclass(slots=True)
class NormalizedAlert:
    source: str
    description: str
    severity: Severity
    fingerprint: str
    external_id: str | None = None
    rule_id: str | None = None
    rule_level: int | None = None
    src_ip: Any | None = None
    dst_ip: Any | None = None
    src_port: int | None = None
    dst_port: int | None = None
    protocol: str | None = None
    agent_name: str | None = None
    asset_criticality: int = 3
    raw_payload: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            return value
    return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_ip(value: Any) -> Any | None:
    if value in (None, "", "-"):
        return None
    try:
        return ipaddress.ip_address(str(value).strip())
    except ValueError:
        return None


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(value, str) and value:
        text = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _fingerprint(source: str, rule_id: str | None, src: Any, dst: Any, external_id: str | None,
                 occurred_at: datetime) -> str:
    """Huella estable en una ventana de 15 minutos: agrupa repeticiones del mismo evento."""
    window = int(occurred_at.timestamp() // (settings.dedup_window_minutes * 60))
    material = "|".join(
        [
            source,
            rule_id or "",
            str(src or ""),
            str(dst or ""),
            external_id or "",
            str(window),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def normalize(payload: dict[str, Any], source_hint: str | None = None) -> NormalizedAlert:
    """Acepta el payload de Wazuh (`rule`, `agent`, `data`) y variantes planas."""
    rule = payload.get("rule") if isinstance(payload.get("rule"), dict) else {}
    agent = payload.get("agent") if isinstance(payload.get("agent"), dict) else {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}

    source = str(
        _first(payload, "source", "integration")
        or source_hint
        or ("opnsense" if "opnsense" in str(payload).lower() else "wazuh")
    )[:40]

    rule_id = _first(rule, "id", "rule_id") or _first(payload, "rule_id", "signature_id")
    rule_level = _as_int(_first(rule, "level") or _first(payload, "rule_level", "level"))
    description = str(
        _first(rule, "description")
        or _first(payload, "description", "message", "full_log", "event")
        or "Alerta sin descripción"
    )[:2000]

    severity_raw = _first(payload, "severity")
    severity = (
        Severity(_SEVERITY_ALIASES.get(str(severity_raw).lower(), str(severity_raw).lower()))
        if severity_raw and str(severity_raw).lower() in _SEVERITY_ALIASES
        else Severity.from_rule_level(rule_level)
    )

    src = _as_ip(
        _first(data, "srcip", "src_ip", "src", "source_ip")
        or _first(payload, "src_ip", "srcip", "source_ip")
    )
    dst = _as_ip(
        _first(data, "dstip", "dst_ip", "dst", "dest_ip")
        or _first(payload, "dst_ip", "dstip", "dest_ip")
    )
    src_port = _as_int(_first(data, "srcport", "src_port") or _first(payload, "src_port"))
    dst_port = _as_int(
        _first(data, "dstport", "dst_port", "dest_port") or _first(payload, "dst_port", "dest_port")
    )
    protocol = _first(data, "protocol") or _first(payload, "protocol")
    agent_name = _first(agent, "name", "id") or _first(payload, "agent_name", "host")
    external_id = _first(payload, "id", "alert_id", "event_id")
    occurred_at = _as_datetime(
        _first(payload, "timestamp", "occurred_at", "time") or _first(data, "timestamp")
    )

    criticality = _as_int(
        _first(payload, "asset_criticality", "criticality") or _first(agent, "criticality")
    )
    criticality = min(max(criticality or 3, 1), 5)

    text = f"{description} {payload.get('full_log', '')}"
    tags = sorted({label for pattern, label in _TAG_RULES if pattern.search(text)})
    if source and source not in tags:
        tags.append(source)
    if severity in (Severity.CRITICAL, Severity.HIGH):
        tags.append("high-impact")

    return NormalizedAlert(
        source=source,
        description=description,
        severity=severity,
        fingerprint=_fingerprint(source, str(rule_id) if rule_id else None, src, dst,
                                 str(external_id) if external_id else None, occurred_at),
        external_id=str(external_id) if external_id else None,
        rule_id=str(rule_id) if rule_id else None,
        rule_level=rule_level,
        src_ip=src,
        dst_ip=dst,
        src_port=src_port,
        dst_port=dst_port,
        protocol=str(protocol) if protocol else None,
        agent_name=str(agent_name) if agent_name else None,
        asset_criticality=criticality,
        raw_payload=payload,
        tags=tags[:12],
        occurred_at=occurred_at,
    )
