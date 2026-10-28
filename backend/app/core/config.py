"""Configuración central de SOC-Lite (12-factor, variables de entorno)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Aplicación
    app_name: str = "SOC-Lite API"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Seguridad
    secret_key: str = "dev-secret-key-change-in-production-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 10
    ingest_api_key: str = "dev-ingest-key-change-me"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:8090", "http://127.0.0.1:8090"]
    )

    # Base de datos
    database_url: str = "postgresql+asyncpg://soclite:soclite@127.0.0.1:5439/soclite"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # Servicio de triaje (LangChain)
    triage_service_url: str = "http://127.0.0.1:8011"
    triage_timeout_seconds: float = 25.0
    triage_fail_open: bool = True

    # Reportes
    storage_dir: Path = Path("storage")
    reports_dir: Path = Path("storage/reports")

    # Operación
    sla_critical_minutes: int = 15
    sla_high_minutes: int = 30
    sla_medium_minutes: int = 240
    sla_low_minutes: int = 1440
    dedup_window_minutes: int = 15

    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            if value.lstrip().startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def reports_path(self) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        return self.reports_dir

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
