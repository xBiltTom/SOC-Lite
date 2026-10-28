"""Esquemas de autenticación y sesión."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, examples=["analista1"])
    password: str = Field(min_length=1, max_length=128, examples=["Analista123!"])


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"


class SessionInfo(ORMModel):
    user_id: UUID
    username: str
    role: str
    expires_at: datetime


from app.schemas.user import UserOut  # noqa: E402  (evita ciclo en tiempo de definición)

TokenPair.model_rebuild()
