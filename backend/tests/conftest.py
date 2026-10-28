"""Fixtures de pruebas de integración contra PostgreSQL real (sin mocks de BD)."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db.session import engine
from app.main import app

ADMIN = ("admin", "Admin123!")
ANALYST = ("analista1", "Analista123!")
VIEWER = ("visor", "Visor123!")


@pytest_asyncio.fixture(autouse=True)
async def _fresh_pool():
    """Cada prueba corre en su propio event loop: el pool asyncpg no debe
    reutilizar conexiones creadas en un loop ya cerrado."""
    await engine.dispose()
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


async def login(client: AsyncClient, credentials: tuple[str, str]) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": credentials[0], "password": credentials[1]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    return await login(client, ADMIN)


@pytest_asyncio.fixture
async def analyst_token(client: AsyncClient) -> str:
    return await login(client, ANALYST)


@pytest.fixture
def auth():
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture
def ingest_headers() -> dict[str, str]:
    return {"X-Ingest-Key": settings.ingest_api_key}


def unique_alert_payload() -> dict:
    marker = uuid.uuid4().hex[:10]
    return {
        "id": f"test-{marker}",
        "timestamp": "2026-10-20T10:00:00Z",
        "rule": {"id": "5710", "level": 12, "description": f"Fuerza bruta SSH de prueba {marker}"},
        "agent": {"name": "SRV-TEST01", "criticality": 5},
        "data": {"srcip": "203.0.113.77", "dstip": "10.0.4.21", "dstport": 22, "protocol": "tcp"},
        "source": "wazuh",
    }
