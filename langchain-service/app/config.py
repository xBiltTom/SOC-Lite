"""Configuración del microservicio de triaje."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    service_name: str = "SOC-Lite Triage Service"
    version: str = "1.2.0"
    environment: str = "development"

    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_api_key: str = ""
    llm_enabled: bool = True
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 90.0
    llm_max_tool_rounds: int = 4

    virustotal_api_key: str = ""
    abuseipdb_api_key: str = ""
    geoip_enabled: bool = True
    threat_intel_timeout_seconds: float = 6.0

    prompt_version: str = "v1.2.0"
    cors_origins: str = "http://localhost:8090,http://127.0.0.1:8090"
    log_level: str = "INFO"

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
