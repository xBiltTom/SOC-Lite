"""Herramientas de enriquecimiento (threat intelligence) con caché y timeouts.

Cada herramienta degrada de forma explícita: si no hay API key o el proveedor
falla, devuelve `status=skipped|error` en lugar de inventar un veredicto.
Nunca se envían datos internos del activo: sólo el indicador (IP/dominio).
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings

_CACHE_TTL = 3600


@dataclass
class _CacheEntry:
    value: dict[str, Any]
    expires_at: float


@dataclass
class ThreatIntel:
    _cache: dict[str, _CacheEntry] = field(default_factory=dict)

    def _get(self, key: str) -> dict[str, Any] | None:
        entry = self._cache.get(key)
        if entry and entry.expires_at > time.monotonic():
            return entry.value
        return None

    def _put(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        self._cache[key] = _CacheEntry(value=value, expires_at=time.monotonic() + _CACHE_TTL)
        return value

    async def virustotal(self, ip: str) -> dict[str, Any]:
        if not settings.virustotal_api_key:
            return {"provider": "virustotal", "indicator": ip, "status": "skipped",
                    "reason": "sin API key configurada"}
        key = f"vt:{ip}"
        if cached := self._get(key):
            return cached
        url = f"https://www.virustotal.com/api/v3/ip_addresses/{ip}"
        try:
            async with httpx.AsyncClient(timeout=settings.threat_intel_timeout_seconds) as client:
                response = await client.get(url, headers={"x-apikey": settings.virustotal_api_key})
            if response.status_code == 404:
                return self._put(key, {"provider": "virustotal", "indicator": ip,
                                       "status": "not_found", "verdict": "unknown", "score": 0})
            response.raise_for_status()
            stats = (
                response.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            )
            malicious = int(stats.get("malicious", 0))
            suspicious = int(stats.get("suspicious", 0))
            total = malicious + suspicious + int(stats.get("harmless", 0)) + int(stats.get("undetected", 0))
            score = round(((malicious * 2 + suspicious) / max(total, 1)) * 100, 1)
            verdict = "malicious" if malicious >= 3 else "suspicious" if malicious + suspicious >= 2 else "clean"
            return self._put(key, {
                "provider": "virustotal", "indicator": ip, "status": "ok",
                "verdict": verdict, "score": min(score, 100.0), "raw": stats,
            })
        except (httpx.HTTPError, ValueError) as exc:
            return {"provider": "virustotal", "indicator": ip, "status": "error", "reason": str(exc)[:200]}

    async def abuseipdb(self, ip: str) -> dict[str, Any]:
        if not settings.abuseipdb_api_key:
            return {"provider": "abuseipdb", "indicator": ip, "status": "skipped",
                    "reason": "sin API key configurada"}
        key = f"abuse:{ip}"
        if cached := self._get(key):
            return cached
        url = "https://api.abuseipdb.com/api/v2/check"
        try:
            async with httpx.AsyncClient(timeout=settings.threat_intel_timeout_seconds) as client:
                response = await client.get(
                    url,
                    params={"ipAddress": ip, "maxAgeInDays": 90},
                    headers={"Key": settings.abuseipdb_api_key, "Accept": "application/json"},
                )
            response.raise_for_status()
            data = response.json().get("data", {})
            score = float(data.get("abuseConfidenceScore", 0) or 0)
            verdict = "malicious" if score >= 75 else "suspicious" if score >= 25 else "clean"
            return self._put(key, {
                "provider": "abuseipdb", "indicator": ip, "status": "ok",
                "verdict": verdict, "score": score,
                "country": data.get("countryCode"),
                "raw": {"totalReports": data.get("totalReports"), "usageType": data.get("usageType")},
            })
        except (httpx.HTTPError, ValueError) as exc:
            return {"provider": "abuseipdb", "indicator": ip, "status": "error", "reason": str(exc)[:200]}

    async def geoip(self, ip: str) -> dict[str, Any]:
        if not settings.geoip_enabled:
            return {"provider": "geoip", "indicator": ip, "status": "skipped"}
        key = f"geo:{ip}"
        if cached := self._get(key):
            return cached
        try:
            async with httpx.AsyncClient(timeout=settings.threat_intel_timeout_seconds) as client:
                response = await client.get(f"https://ipwho.is/{ip}")
            response.raise_for_status()
            data = response.json()
            if not data.get("success", True):
                return {"provider": "geoip", "indicator": ip, "status": "not_found"}
            return self._put(key, {
                "provider": "geoip", "indicator": ip, "status": "ok",
                "country": data.get("country_code"), "city": data.get("city"),
                "asn": f"AS{data.get('connection', {}).get('asn')}" if data.get("connection") else None,
            })
        except (httpx.HTTPError, ValueError) as exc:
            return {"provider": "geoip", "indicator": ip, "status": "error", "reason": str(exc)[:200]}

    async def enrich(self, alert) -> list[dict[str, Any]]:  # noqa: ANN001
        results: list[dict[str, Any]] = []
        if alert.src_ip:
            results.extend(
                await asyncio.gather(
                    self.virustotal(alert.src_ip),
                    self.abuseipdb(alert.src_ip),
                    self.geoip(alert.src_ip),
                )
            )
        results.extend(mitre_lookup(alert.description, alert.tags))
        return results


# ---------------------------------------------------------------------------
# MITRE ATT&CK: mapeo determinista por firma textual (sin LLM)
# ---------------------------------------------------------------------------
_MITRE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("brute", "fuerza bruta", "failed password", "login"), "T1110"),
    (("ransom", "cifrado", "locked", "rescate"), "T1486"),
    (("powershell", "encodedcommand", "-enc"), "T1059.001"),
    (("scan", "escaneo", "portscan"), "T1046"),
    (("sql", "xss", "traversal", "cve-", "exploit"), "T1190"),
    (("dns", "domain", "dominio"), "T1071.004"),
    (("c2", "command and control", "beacon"), "T1071.001"),
    (("credential", "mimikatz", "lsass"), "T1003"),
    (("persistence", "run key", "schtasks"), "T1053.005"),
)


def mitre_lookup(description: str, tags: list[str] | None = None) -> list[dict[str, Any]]:
    text = f"{description} {' '.join(tags or [])}".lower()
    techniques = sorted({technique for keywords, technique in _MITRE_RULES if any(k in text for k in keywords)})
    return [
        {
            "provider": "mitre",
            "indicator": technique,
            "indicator_type": "technique",
            "status": "ok",
            "verdict": "informational",
            "score": None,
        }
        for technique in techniques
    ]


threat_intel = ThreatIntel()
