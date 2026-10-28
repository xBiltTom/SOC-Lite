"""Agregador de la API v1."""
from fastapi import APIRouter

from app.api.v1.routers import alerts, audit, auth, dashboard, incidents, reports, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(alerts.router)
api_router.include_router(incidents.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(audit.router)
