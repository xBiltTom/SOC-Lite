"""Esquemas comunes: paginación, errores y tipos reutilizables."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

T = TypeVar("T")


def _ip_to_str(value: object) -> object:
    if value is None:
        return None
    # asyncpg devuelve IPv4Interface/IPv6Interface para columnas INET; se expone
    # sólo la dirección, sin la máscara /32.
    return str(getattr(value, "ip", value))


IPAddressStr = Annotated[str | None, BeforeValidator(_ip_to_str)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    pages: int


class Message(BaseModel):
    detail: str


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
    request_id: str | None = None


class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    database: str
    timestamp: datetime
