"""Agente de triaje con LangChain + Ollama y degradación a heurística local.

Flujo:
  1. Enriquecimiento con herramientas (VirusTotal, AbuseIPDB, GeoIP, MITRE).
  2. Memoria local de casos (falsos positivos recurrentes por indicador).
  3. LLM con *tool calling* y prompt endurecido contra inyección de instrucciones.
  4. Validación Pydantic de la salida; si falla, reintento de reparación y, en
     último término, motor heurístico marcado como `degraded`.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field, field_validator, model_validator

from app.chains import prompts
from app.config import settings
from app.engines.heuristics import heuristic
from app.models import AlertIn, RecommendedAction, TriageOut
from app.tools.threat_intel import mitre_lookup, threat_intel

logger = logging.getLogger("soc-lite.triage")

_JSON_BLOCK = re.compile(r"\{.*\}", re.S)
_MITRE = re.compile(r"^T\d{4}(\.\d{3})?$")


class LLMDecision(BaseModel):
    verdict: str
    severity: str
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=10, max_length=1200)
    reasoning: str | None = Field(default=None, max_length=4000)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list, max_length=8)
    mitre_techniques: list[str] = Field(default_factory=list)
    needs_human: bool = False

    @field_validator("verdict")
    @classmethod
    def valid_verdict(cls, value: str) -> str:
        value = value.strip().lower()
        allowed = {"true_positive", "false_positive", "suspicious", "benign", "inconclusive"}
        return value if value in allowed else "inconclusive"

    @field_validator("severity")
    @classmethod
    def valid_severity(cls, value: str) -> str:
        value = value.strip().lower()
        return value if value in {"critical", "high", "medium", "low", "info"} else "medium"

    @field_validator("mitre_techniques")
    @classmethod
    def valid_mitre(cls, values: list[str]) -> list[str]:
        return [value for value in values if _MITRE.match(value)][:10]

    @model_validator(mode="after")
    def ensure_actions(self) -> "LLMDecision":
        if not self.recommended_actions:
            self.recommended_actions = [
                RecommendedAction(
                    action="Validar el evento con el propietario del activo",
                    priority=2,
                    owner="Analista",
                )
            ]
        return self


@dataclass
class TriageMemory:
    """Memoria persistente y acotada de casos recientes (no guarda payloads crudos)."""

    path: Path = Path("data/triage_memory.json")
    max_entries: int = 500
    _data: dict[str, Any] = field(default_factory=dict)
    _loaded: bool = False

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if self.path.exists():
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._data = {}
        self._loaded = True

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if len(self._data) > self.max_entries:
                ordered = sorted(
                    self._data.items(), key=lambda item: item[1].get("last_seen", ""), reverse=True
                )
                self._data = dict(ordered[: self.max_entries])
            self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            logger.warning("no se pudo persistir la memoria de triaje")

    @staticmethod
    def key(alert: AlertIn) -> str:
        return f"{alert.src_ip or 'sin-ip'}|{alert.rule_id or 'sin-regla'}"

    def hint(self, alert: AlertIn) -> dict[str, Any] | None:
        self._load()
        entry = self._data.get(self.key(alert))
        if not entry:
            return None
        return {
            "verdict": entry.get("verdict"),
            "false_positives": entry.get("false_positives", 0),
            "total": entry.get("total", 0),
            "last_seen": entry.get("last_seen"),
        }

    def record(self, alert: AlertIn, output: TriageOut) -> None:
        self._load()
        key = self.key(alert)
        entry = self._data.get(
            key, {"verdict": None, "false_positives": 0, "total": 0, "last_seen": None}
        )
        entry["verdict"] = output.verdict
        entry["total"] = int(entry.get("total", 0)) + 1
        if output.verdict == "false_positive":
            entry["false_positives"] = int(entry.get("false_positives", 0)) + 1
        entry["last_seen"] = datetime.now(timezone.utc).isoformat()
        self._data[key] = entry
        self._save()


memory = TriageMemory()


def _build_tools() -> list[BaseTool]:
    @tool
    async def lookup_virustotal(ip: str) -> str:
        """Consulta la reputación de una IP en VirusTotal."""
        return json.dumps(await threat_intel.virustotal(ip), ensure_ascii=False)

    @tool
    async def lookup_abuseipdb(ip: str) -> str:
        """Consulta los reportes de abuso de una IP en AbuseIPDB."""
        return json.dumps(await threat_intel.abuseipdb(ip), ensure_ascii=False)

    @tool
    async def lookup_geoip(ip: str) -> str:
        """Obtiene país, ciudad y ASN de una IP."""
        return json.dumps(await threat_intel.geoip(ip), ensure_ascii=False)

    @tool
    async def map_mitre(descripcion: str) -> str:
        """Mapea una descripción de alerta a técnicas MITRE ATT&CK."""
        return json.dumps(mitre_lookup(descripcion), ensure_ascii=False)

    return [lookup_virustotal, lookup_abuseipdb, lookup_geoip, map_mitre]


def _enrichment_text(items: list[dict[str, Any]]) -> str:
    if not items:
        return "sin enriquecimiento disponible"
    lines = []
    for item in items:
        provider = item.get("provider", "?")
        indicator = item.get("indicator", "?")
        if item.get("status") in ("skipped", "error"):
            lines.append(f"- {provider} ({indicator}): {item.get('status')} {item.get('reason', '')}")
        else:
            lines.append(
                f"- {provider} ({indicator}): verdict={item.get('verdict')} "
                f"score={item.get('score')} country={item.get('country')} asn={item.get('asn')}"
            )
    return "\n".join(lines)


def _extract_json(content: Any) -> dict[str, Any]:
    if isinstance(content, list):
        content = " ".join(str(part) for part in content)
    text = str(content).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    match = _JSON_BLOCK.search(text)
    if not match:
        raise ValueError("la respuesta no contiene un objeto JSON")
    return json.loads(match.group(0))


@dataclass
class TriageAgent:
    _llm_checked_at: float = 0.0
    _llm_available: bool = False

    async def _available(self) -> bool:
        if not settings.llm_enabled:
            return False
        if time.monotonic() - self._llm_checked_at < 30:
            return self._llm_available
        self._llm_checked_at = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            self._llm_available = response.status_code == 200
        except httpx.HTTPError:
            self._llm_available = False
        return self._llm_available

    async def _llm_triage(
        self, alert: AlertIn, enrichment: list[dict[str, Any]], hint: dict[str, Any] | None
    ) -> TriageOut:
        started = time.perf_counter()
        llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
            client_kwargs={"timeout": settings.llm_timeout_seconds},
        )
        tools = _build_tools()
        tool_map = {item.name: item for item in tools}
        bound = llm.bind_tools(tools)

        human = prompts.HUMAN_TEMPLATE.format(
            source=alert.source,
            rule_id=alert.rule_id,
            rule_level=alert.rule_level,
            description=alert.description[:2000],
            src_ip=alert.src_ip,
            dst_ip=alert.dst_ip,
            agent_name=alert.agent_name,
            asset_criticality=alert.asset_criticality,
            severity=alert.severity,
            tags=", ".join(alert.tags) or "ninguna",
            payload=json.dumps(alert.raw_payload, ensure_ascii=False)[:1500],
            enrichment=_enrichment_text(enrichment),
            memory=json.dumps(hint, ensure_ascii=False) if hint else "sin casos previos",
        )
        messages: list[Any] = [SystemMessage(content=prompts.SYSTEM_PROMPT), HumanMessage(content=human)]

        response: Any = None
        for _ in range(settings.llm_max_tool_rounds):
            response = await bound.ainvoke(messages)
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                break
            messages.append(response)
            for call in tool_calls:
                selected = tool_map.get(call.get("name"))
                if selected is None:
                    messages.append(
                        ToolMessage(content="herramienta no permitida", tool_call_id=call.get("id", ""))
                    )
                    continue
                try:
                    result = await selected.ainvoke(call.get("args", {}))
                except Exception as exc:  # una herramienta caída no rompe el triaje
                    result = json.dumps({"status": "error", "reason": str(exc)[:200]})
                messages.append(ToolMessage(content=str(result), tool_call_id=call.get("id", "")))

        decision = LLMDecision.model_validate(_extract_json(response.content))
        latency_ms = int((time.perf_counter() - started) * 1000)
        mitre = sorted(
            set(decision.mitre_techniques)
            | {item["indicator"] for item in enrichment if item.get("provider") == "mitre"}
        )
        return TriageOut(
            verdict=decision.verdict,
            severity=decision.severity,
            confidence=round(decision.confidence, 3),
            summary=decision.summary,
            reasoning=decision.reasoning,
            recommended_actions=decision.recommended_actions[:5],
            mitre_techniques=mitre[:10],
            model=settings.ollama_model,
            prompt_version=prompts.PROMPT_VERSION,
            latency_ms=latency_ms,
            status="completed",
            needs_human=decision.needs_human or decision.verdict == "inconclusive",
            fallback_used=False,
            enrichment=enrichment,
            raw_response={"content": str(response.content)[:4000]},
        )

    async def triage(self, alert: AlertIn) -> TriageOut:
        enrichment = await threat_intel.enrich(alert)
        for provided in alert.enrichment:
            enrichment.append(provided.model_dump())
        hint = memory.hint(alert)

        if await self._available():
            try:
                output = await self._llm_triage(alert, enrichment, hint)
                memory.record(alert, output)
                return output
            except Exception as exc:  # validación, timeout, modelo sin tool-calling...
                logger.warning("fallo del LLM (%s); se activa heurística", exc)
                output = heuristic(alert, enrichment, hint, reason="fallo o timeout del LLM")
                memory.record(alert, output)
                return output

        output = heuristic(alert, enrichment, hint, reason="Ollama no disponible")
        memory.record(alert, output)
        return output


agent = TriageAgent()
