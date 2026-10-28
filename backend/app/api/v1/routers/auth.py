"""Autenticación: login, refresh con rotación, logout y cambio de contraseña."""
from __future__ import annotations

import ipaddress
import uuid
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.errors import AppError, Unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_fingerprint,
    validate_password_strength,
    verify_password,
)
from app.models.enums import AuditResult
from app.models.security import RefreshToken, Role, User
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, TokenPair
from app.schemas.common import Message
from app.schemas.user import PasswordChange, UserOut
from app.services import audit

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _ip(request: Request):
    host = request.client.host if request.client else None
    try:
        return ipaddress.ip_address(host) if host else None
    except ValueError:
        return None


def _tokens_for(user: User, request: Request) -> tuple[str, str, datetime]:
    access = create_access_token(
        str(user.id), user.username, user.role.code, user.permissions
    )
    refresh, expires_at = create_refresh_token(str(user.id))
    return access, refresh, expires_at


async def _issue(db, user: User, request: Request, *, rotate_from: RefreshToken | None = None) -> TokenPair:
    access, refresh, expires_at = _tokens_for(user, request)
    if rotate_from is not None:
        rotate_from.revoked_at = datetime.now(timezone.utc)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_fingerprint(refresh),
            user_agent=request.headers.get("user-agent"),
            ip=_ip(request),
            expires_at=expires_at,
        )
    )
    user.last_login_at = datetime.now(timezone.utc)
    await audit.record(
        db,
        module="auth",
        action="LOGIN" if rotate_from is None else "TOKEN_REFRESH",
        user=user,
        request=request,
        entity_type="user",
        entity_id=user.id,
        detail={"username": user.username, "role": user.role.code},
    )
    await db.commit()
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


async def _authenticate(db, username: str, password: str, request: Request) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.username == username.strip().lower())
    )
    user = result.scalar_one_or_none()
    if user is None or user.deleted_at is not None or not user.is_active:
        await audit.record(
            db,
            module="auth",
            action="LOGIN_FAILED",
            username=username[:64],
            request=request,
            result=AuditResult.FAILURE,
            detail={"reason": "usuario_inexistente_o_inactivo"},
        )
        await db.commit()
        raise Unauthorized("Usuario o contraseña incorrectos")

    if not verify_password(password, user.password_hash):
        await audit.record(
            db,
            module="auth",
            action="LOGIN_FAILED",
            user=user,
            request=request,
            result=AuditResult.FAILURE,
            detail={"reason": "password_incorrecto"},
        )
        await db.commit()
        raise Unauthorized("Usuario o contraseña incorrectos")
    return user


@router.post("/login", response_model=TokenPair, summary="Iniciar sesión (JSON)")
async def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenPair:
    user = await _authenticate(db, payload.username, payload.password, request)
    return await _issue(db, user, request)


@router.post("/token", response_model=TokenPair, summary="Iniciar sesión (OAuth2 password flow)")
async def token(
    request: Request,
    db: DbSession,
    form: OAuth2PasswordRequestForm = Depends(),
) -> TokenPair:
    user = await _authenticate(db, form.username, form.password, request)
    return await _issue(db, user, request)


@router.post("/refresh", response_model=TokenPair, summary="Renovar tokens (rotación)")
async def refresh(payload: RefreshRequest, request: Request, db: DbSession) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token, "refresh")
        user_id = uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise Unauthorized("Refresh token inválido o expirado") from exc

    stored = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_fingerprint(payload.refresh_token))
        )
    ).scalar_one_or_none()

    if stored is None:
        raise Unauthorized("Refresh token desconocido")
    if stored.revoked_at is not None:
        # Reutilización de un token ya rotado: se revocan todas las sesiones.
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == stored.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await audit.record(
            db,
            module="auth",
            action="TOKEN_REUSE_DETECTED",
            username=str(user_id),
            result=AuditResult.DENIED,
            request=request,
            entity_type="refresh_token",
            entity_id=stored.id,
        )
        await db.commit()
        raise Unauthorized("Sesión revocada por reutilización de token")
    if stored.expires_at <= datetime.now(timezone.utc):
        raise Unauthorized("Refresh token expirado")

    user = (
        await db.execute(
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if user is None:
        raise Unauthorized("Usuario no disponible")
    return await _issue(db, user, request, rotate_from=stored)


@router.post("/logout", response_model=Message, summary="Cerrar sesión y revocar refresh tokens")
async def logout(
    payload: LogoutRequest, request: Request, user: CurrentUser, db: DbSession
) -> Message:
    query = update(RefreshToken).where(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    )
    if payload.refresh_token:
        query = query.where(RefreshToken.token_hash == token_fingerprint(payload.refresh_token))
    await db.execute(query.values(revoked_at=datetime.now(timezone.utc)))
    await audit.record(
        db, module="auth", action="LOGOUT", user=user, request=request,
        entity_type="user", entity_id=user.id,
    )
    await db.commit()
    return Message(detail="Sesión cerrada")


@router.get("/me", response_model=UserOut, summary="Perfil y permisos del usuario autenticado")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/change-password", response_model=Message, summary="Cambiar contraseña propia")
async def change_password(
    payload: PasswordChange, request: Request, user: CurrentUser, db: DbSession
) -> Message:
    if not verify_password(payload.current_password, user.password_hash):
        await audit.record(
            db, module="auth", action="PASSWORD_CHANGE", user=user, request=request,
            result=AuditResult.DENIED, detail={"reason": "password_actual_incorrecto"},
        )
        await db.commit()
        raise Unauthorized("La contraseña actual no es correcta")
    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise AppError(str(exc), 400, "WEAK_PASSWORD") from exc

    user.password_hash = hash_password(payload.new_password)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await audit.record(
        db, module="auth", action="PASSWORD_CHANGE", user=user, request=request,
        entity_type="user", entity_id=user.id,
    )
    await db.commit()
    return Message(detail="Contraseña actualizada; vuelva a iniciar sesión")
