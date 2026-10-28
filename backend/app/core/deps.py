"""Dependencias de autenticación, autorización y paginación."""
from __future__ import annotations

import ipaddress
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, Query, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import Forbidden, Unauthorized
from app.core.logging import username_ctx
from app.core.security import decode_token
from app.db.session import get_db
from app.models.security import Role, User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/token", auto_error=False
)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    if not token:
        raise Unauthorized("Token de acceso ausente")
    try:
        payload = decode_token(token, "access")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise Unauthorized("Token inválido o expirado") from exc

    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise Unauthorized("Usuario inexistente o desactivado")
    username_ctx.set(user.username)
    request.state.user = user
    request.state.user_id = str(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(*codes: str) -> Callable[..., Any]:
    """Devuelve una dependencia que exige al menos uno de los permisos indicados."""

    async def checker(user: CurrentUser) -> User:
        if not any(user.has_permission(code) for code in codes):
            raise Forbidden(
                f"Se requiere uno de los permisos: {', '.join(codes)}"
            )
        return user

    return checker


@dataclass(slots=True)
class Pagination:
    page: int
    size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def pagination(
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> Pagination:
    return Pagination(page=page, size=size)


PaginationDep = Annotated[Pagination, Depends(pagination)]


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    candidate = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
    if not candidate:
        return None
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return candidate


def ip_object(value: str | None) -> Any:
    """Convierte texto a objeto ipaddress para columnas INET (asyncpg)."""
    if not value:
        return None
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def parse_uuid(value: str, label: str = "identificador") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise Unauthorized(f"{label} inválido") from exc
