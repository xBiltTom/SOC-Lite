"""Registro central de modelos: importar este módulo garantiza que el mapper
conozca todas las entidades y pueda resolver las relaciones."""

from app.models.alert import Alert, AlertFeedback, EnrichmentData, TriageResult
from app.models.audit import AuditLog, Integration, Report
from app.models.incident import Incident
from app.models.security import Permission, RefreshToken, Role, User, role_permissions

__all__ = [
    "Alert",
    "AlertFeedback",
    "AuditLog",
    "EnrichmentData",
    "Incident",
    "Integration",
    "Permission",
    "RefreshToken",
    "Report",
    "Role",
    "TriageResult",
    "User",
    "role_permissions",
]
