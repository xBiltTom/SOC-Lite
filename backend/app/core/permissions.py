"""Catálogo de permisos y utilidades de autorización."""
from __future__ import annotations

from enum import StrEnum


class P(StrEnum):
    DASHBOARD_READ = "dashboard:read"
    DASHBOARD_EXPORT = "dashboard:export"
    ALERTS_READ = "alerts:read"
    ALERTS_CREATE = "alerts:create"
    ALERTS_UPDATE = "alerts:update"
    ALERTS_DELETE = "alerts:delete"
    ALERTS_EXPORT = "alerts:export"
    TRIAGE_READ = "triage:read"
    TRIAGE_RUN = "triage:run"
    TRIAGE_FEEDBACK = "triage:feedback"
    INCIDENTS_READ = "incidents:read"
    INCIDENTS_CREATE = "incidents:create"
    INCIDENTS_UPDATE = "incidents:update"
    INCIDENTS_CLOSE = "incidents:close"
    INCIDENTS_EXPORT = "incidents:export"
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    ROLES_READ = "roles:read"
    ROLES_UPDATE = "roles:update"
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    REPORTS_READ = "reports:read"
    REPORTS_CREATE = "reports:create"
    REPORTS_EXPORT = "reports:export"


# Módulos que expone la navegación del frontend (orden canónico)
MODULE_ORDER = (
    "dashboard",
    "alerts",
    "triage",
    "incidents",
    "users",
    "roles",
    "audit",
    "reports",
)
