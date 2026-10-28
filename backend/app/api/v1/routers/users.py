"""Administración de usuarios, roles y matriz de permisos (RBAC)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession, PaginationDep, require_permission
from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.core.permissions import P
from app.core.security import hash_password, validate_password_strength
from app.models.enums import AuditResult
from app.models.security import Permission, RefreshToken, Role, User, role_permissions
from app.schemas.common import Message, Page
from app.schemas.user import (
    PasswordReset,
    PermissionOut,
    RoleOut,
    RolePermissionsUpdate,
    UserCreate,
    UserDetail,
    UserOut,
    UserUpdate,
)
from app.services import audit

router = APIRouter(tags=["Usuarios y roles"])

ReadUsers = Annotated[User, Depends(require_permission(P.USERS_READ))]
ManageUsers = Annotated[User, Depends(require_permission(P.USERS_CREATE, P.USERS_UPDATE))]
ReadRoles = Annotated[User, Depends(require_permission(P.ROLES_READ))]


@router.get("/users", response_model=Page[UserOut], summary="Listar usuarios")
async def list_users(
    db: DbSession,
    _: ReadUsers,
    pagination: PaginationDep,
    q: str | None = Query(default=None, max_length=80),
    role: str | None = Query(default=None, max_length=40),
    is_active: bool | None = None,
) -> Page[UserOut]:
    conditions = [User.deleted_at.is_(None)]
    if q:
        pattern = f"%{q}%"
        conditions.append(
            or_(
                User.username.ilike(pattern),
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
            )
        )
    if role:
        conditions.append(User.role.has(Role.code == role))
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))

    total = (await db.execute(select(func.count(User.id)).where(*conditions))).scalar_one()
    rows = (
        await db.execute(
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(*conditions)
            .order_by(User.full_name)
            .offset(pagination.offset)
            .limit(pagination.size)
        )
    ).scalars().all()
    return Page[UserOut](
        items=[UserOut.model_validate(user) for user in rows],
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=max(1, -(-total // pagination.size)),
    )


@router.post("/users", response_model=UserOut, status_code=201, summary="Crear usuario")
async def create_user(payload: UserCreate, db: DbSession, actor: ManageUsers) -> UserOut:
    if not actor.has_permission(P.USERS_CREATE):
        raise Forbidden("Se requiere users:create")
    try:
        validate_password_strength(payload.password)
    except ValueError as exc:
        raise AppError(str(exc), 400, "WEAK_PASSWORD") from exc

    role = (await db.execute(select(Role).where(Role.id == payload.role_id))).scalar_one_or_none()
    if role is None:
        raise NotFound("Rol")
    exists = (
        await db.execute(
            select(User.id).where(
                or_(User.username == payload.username, User.email == str(payload.email))
            )
        )
    ).first()
    if exists:
        raise Conflict("Ya existe un usuario con ese nombre de usuario o correo")

    user = User(
        username=payload.username,
        email=str(payload.email),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role_id=payload.role_id,
        is_active=payload.is_active,
    )
    db.add(user)
    await db.flush()
    await audit.record(
        db,
        module="users",
        action="USER_CREATE",
        user=actor,
        entity_type="user",
        entity_id=user.id,
        detail={"username": user.username, "role": role.code},
    )
    await db.commit()
    await db.refresh(user, ["role"])
    return UserOut.model_validate(user)


@router.get("/users/{user_id}", response_model=UserDetail, summary="Detalle de usuario")
async def get_user(user_id: uuid.UUID, db: DbSession, _: ReadUsers) -> UserDetail:
    user = (
        await db.execute(
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if user is None:
        raise NotFound("Usuario")
    return UserDetail.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut, summary="Actualizar usuario")
async def update_user(
    user_id: uuid.UUID, payload: UserUpdate, db: DbSession, actor: ManageUsers
) -> UserOut:
    if not actor.has_permission(P.USERS_UPDATE):
        raise Forbidden("Se requiere users:update")
    user = (
        await db.execute(
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if user is None:
        raise NotFound("Usuario")
    if user.id == actor.id and payload.is_active is False:
        raise Conflict("No puede desactivar su propia cuenta")

    changes: dict[str, object] = {}
    if payload.email is not None and str(payload.email) != user.email:
        duplicate = (
            await db.execute(select(User.id).where(User.email == str(payload.email), User.id != user.id))
        ).first()
        if duplicate:
            raise Conflict("El correo ya está en uso")
        changes["email"] = str(payload.email)
        user.email = str(payload.email)
    if payload.full_name is not None:
        changes["full_name"] = payload.full_name
        user.full_name = payload.full_name
    if payload.role_id is not None and payload.role_id != user.role_id:
        role = (await db.execute(select(Role).where(Role.id == payload.role_id))).scalar_one_or_none()
        if role is None:
            raise NotFound("Rol")
        changes["role"] = role.code
        user.role_id = payload.role_id
    if payload.is_active is not None:
        changes["is_active"] = payload.is_active
        user.is_active = payload.is_active
    if payload.mfa_enabled is not None:
        changes["mfa_enabled"] = payload.mfa_enabled
        user.mfa_enabled = payload.mfa_enabled

    if payload.is_active is False:
        await db.execute(
            RefreshToken.__table__.update()
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    await audit.record(
        db, module="users", action="USER_UPDATE", user=actor, entity_type="user",
        entity_id=user.id, detail={"changes": changes},
    )
    await db.commit()
    await db.refresh(user, ["role"])
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}", response_model=Message, summary="Desactivar usuario (baja lógica)")
async def delete_user(
    user_id: uuid.UUID,
    db: DbSession,
    actor: Annotated[User, Depends(require_permission(P.USERS_DELETE))],
) -> Message:
    if user_id == actor.id:
        raise Conflict("No puede eliminar su propia cuenta")
    user = (
        await db.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if user is None:
        raise NotFound("Usuario")
    if user.role.code == "admin":
        admins = (
            await db.execute(
                select(func.count(User.id))
                .join(Role, Role.id == User.role_id)
                .where(Role.code == "admin", User.is_active.is_(True), User.deleted_at.is_(None))
            )
        ).scalar_one()
        if admins <= 1:
            raise Conflict("No se puede eliminar al último administrador activo")

    user.is_active = False
    user.deleted_at = datetime.now(timezone.utc)
    await audit.record(
        db, module="users", action="USER_DELETE", user=actor, entity_type="user",
        entity_id=user.id, detail={"username": user.username},
    )
    await db.commit()
    return Message(detail="Usuario desactivado")


@router.post("/users/{user_id}/reset-password", response_model=Message, summary="Restablecer contraseña")
async def reset_password(
    user_id: uuid.UUID,
    payload: PasswordReset,
    db: DbSession,
    actor: Annotated[User, Depends(require_permission(P.USERS_UPDATE))],
) -> Message:
    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise AppError(str(exc), 400, "WEAK_PASSWORD") from exc
    user = (
        await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if user is None:
        raise NotFound("Usuario")

    user.password_hash = hash_password(payload.new_password)
    await db.execute(
        RefreshToken.__table__.update()
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await audit.record(
        db, module="users", action="PASSWORD_RESET", user=actor, entity_type="user",
        entity_id=user.id, detail={"username": user.username},
    )
    await db.commit()
    return Message(detail="Contraseña restablecida")


# ---------------------------------------------------------------------------
# Roles y permisos
# ---------------------------------------------------------------------------
@router.get("/roles", response_model=list[RoleOut], summary="Listar roles y permisos")
async def list_roles(db: DbSession, _: ReadRoles) -> list[RoleOut]:
    roles = (
        await db.execute(select(Role).options(selectinload(Role.permissions)).order_by(Role.id))
    ).scalars().all()
    counts = dict(
        (
            await db.execute(
                select(User.role_id, func.count(User.id))
                .where(User.deleted_at.is_(None))
                .group_by(User.role_id)
            )
        ).all()
    )
    result = []
    for role in roles:
        item = RoleOut.model_validate(role)
        item.user_count = int(counts.get(role.id, 0))
        result.append(item)
    return result


@router.get("/permissions", response_model=list[PermissionOut], summary="Catálogo de permisos")
async def list_permissions(db: DbSession, _: ReadRoles) -> list[PermissionOut]:
    rows = (
        await db.execute(select(Permission).order_by(Permission.module, Permission.action))
    ).scalars().all()
    return [PermissionOut.model_validate(row) for row in rows]


@router.put("/roles/{role_id}/permissions", response_model=RoleOut, summary="Actualizar matriz de permisos")
async def update_role_permissions(
    role_id: int,
    payload: RolePermissionsUpdate,
    db: DbSession,
    actor: Annotated[User, Depends(require_permission(P.ROLES_UPDATE))],
) -> RoleOut:
    role = (
        await db.execute(
            select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
        )
    ).scalar_one_or_none()
    if role is None:
        raise NotFound("Rol")
    if role.code == "admin":
        raise Conflict("El rol Administrador es inmutable para evitar el bloqueo del sistema")
    if role.id == actor.role_id and P.ROLES_UPDATE not in payload.permission_codes:
        raise Conflict("No puede retirar el permiso roles:update de su propio rol")

    permissions = (
        await db.execute(select(Permission).where(Permission.code.in_(payload.permission_codes)))
    ).scalars().all()
    found = {permission.code for permission in permissions}
    missing = sorted(set(payload.permission_codes) - found)
    if missing:
        raise AppError(f"Permisos inexistentes: {', '.join(missing)}", 400, "UNKNOWN_PERMISSION")

    await db.execute(delete(role_permissions).where(role_permissions.c.role_id == role.id))
    await db.execute(
        role_permissions.insert(),
        [{"role_id": role.id, "permission_id": permission.id} for permission in permissions],
    )
    await audit.record(
        db, module="roles", action="ROLE_PERMISSIONS_UPDATE", user=actor,
        entity_type="role", entity_id=role.id,
        detail={"role": role.code, "permissions": sorted(found)},
    )
    await db.commit()

    role = (
        await db.execute(select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id))
    ).scalar_one()
    count = (
        await db.execute(
            select(func.count(User.id)).where(User.role_id == role.id, User.deleted_at.is_(None))
        )
    ).scalar_one()
    result = RoleOut.model_validate(role)
    result.user_count = int(count)
    return result
