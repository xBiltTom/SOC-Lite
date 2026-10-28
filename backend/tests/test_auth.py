from __future__ import annotations

import pytest

from tests.conftest import ADMIN, ANALYST, VIEWER, login


@pytest.mark.asyncio
async def test_login_ok_y_perfil(client):
    response = await client.post(
        "/api/v1/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] and data["refresh_token"]
    assert data["user"]["role"]["code"] == "admin"
    assert "alerts:read" in data["user"]["permissions"]

    profile = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert profile.status_code == 200
    assert profile.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_login_fallido(client):
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "incorrecta"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_rbac_deniega_usuarios_a_visor(client):
    token = await login(client, VIEWER)
    response = await client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"].startswith("Se requiere")


@pytest.mark.asyncio
async def test_analista_puede_ver_alertas_pero_no_usuarios(client):
    token = await login(client, ANALYST)
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/api/v1/alerts?size=1", headers=headers)).status_code == 200
    assert (await client.get("/api/v1/users", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_refresh_rota_token(client):
    login_response = await client.post(
        "/api/v1/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]}
    )
    refresh = login_response.json()["refresh_token"]
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert response.status_code == 200
    assert response.json()["access_token"]
    # El token anterior ya no puede reutilizarse
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert replay.status_code == 401
