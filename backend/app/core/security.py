"""Primitivas de seguridad: hashing de contraseñas, JWT y tokens de refresco."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

# ---------------------------------------------------------------------------
# Contraseñas
# ---------------------------------------------------------------------------
_BCRYPT_ROUNDS = 12
_PASSWORD_RULES = (
    (re.compile(r"[A-Z]"), "al menos una letra mayúscula"),
    (re.compile(r"[a-z]"), "al menos una letra minúscula"),
    (re.compile(r"\d"), "al menos un dígito"),
    (re.compile(r"[^A-Za-z0-9]"), "al menos un carácter especial"),
)


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar 72 bytes (límite de bcrypt)")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> None:
    problems = [msg for pattern, msg in _PASSWORD_RULES if not pattern.search(password)]
    if len(password) < settings.password_min_length:
        problems.insert(0, f"al menos {settings.password_min_length} caracteres")
    if problems:
        raise ValueError("La contraseña debe incluir: " + ", ".join(problems))


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def _create_token(subject: str, token_type: str, extra: dict[str, Any], expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "nbf": now,
        "exp": now + expires,
        "jti": secrets.token_urlsafe(16),
        "iss": "soc-lite",
        **extra,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, username: str, role: str, permissions: list[str]) -> str:
    return _create_token(
        user_id,
        "access",
        {"username": username, "role": role, "permissions": permissions},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    token = _create_token(user_id, "refresh", {}, timedelta(days=settings.refresh_token_expire_days))
    return token, expires_at


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer="soc-lite",
        options={"require": ["exp", "iat", "sub", "type"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return payload


def token_fingerprint(token: str) -> str:
    """Hash con el que se persiste el refresh token: nunca se guarda en claro."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
