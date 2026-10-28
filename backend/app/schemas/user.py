"""Esquemas de usuarios, roles y permisos."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel


class PermissionOut(ORMModel):
    id: int
    code: str
    module: str
    action: str
    description: str | None = None


class RoleBrief(ORMModel):
    id: int
    code: str
    name: str


class RoleOut(RoleBrief):
    description: str | None = None
    is_system: bool = False
    permissions: list[PermissionOut] = []
    user_count: int = 0


class RolePermissionsUpdate(BaseModel):
    permission_codes: list[str] = Field(min_length=1, max_length=200)


class UserOut(ORMModel):
    id: UUID
    username: str
    email: EmailStr
    full_name: str
    role: RoleBrief
    is_active: bool
    mfa_enabled: bool
    last_login_at: datetime | None = None
    created_at: datetime
    permissions: list[str] = []


class UserDetail(UserOut):
    updated_at: datetime | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    role_id: int
    is_active: bool = True

    @field_validator("username")
    @classmethod
    def lower(cls, value: str) -> str:
        return value.strip().lower()


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=3, max_length=120)
    role_id: int | None = None
    is_active: bool | None = None
    mfa_enabled: bool | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)
