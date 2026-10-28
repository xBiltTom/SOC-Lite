"""Tipos de columna reutilizables (ENUM nativos de PostgreSQL ya creados en schema.sql)."""
from __future__ import annotations

from enum import Enum

from sqlalchemy.dialects.postgresql import ENUM


def pg_enum(enum_cls: type[Enum], name: str) -> ENUM:
    return ENUM(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda cls: [member.value for member in cls],
        validate_strings=True,
    )
