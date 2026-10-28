from __future__ import annotations

import uuid

import pytest

from tests.conftest import unique_alert_payload


@pytest.mark.asyncio
async def test_ingesta_sin_clave_es_rechazada(client):
    response = await client.post("/api/v1/alerts/ingest", json=unique_alert_payload())
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ingesta_y_deduplicacion(client, ingest_headers, admin_token, auth):
    payload = unique_alert_payload()
    first = await client.post("/api/v1/alerts/ingest", json=payload, headers=ingest_headers)
    assert first.status_code == 202, first.text
    body = first.json()
    assert body["status"] == "accepted"
    assert body["severity"] == "critical"

    alert_id = body["alert_id"]
    detail = await client.get(f"/api/v1/alerts/{alert_id}", headers=auth(admin_token))
    assert detail.status_code == 200
    assert detail.json()["src_ip"] == "203.0.113.77"

    second = await client.post("/api/v1/alerts/ingest", json=payload, headers=ingest_headers)
    assert second.status_code == 202
    assert second.json()["status"] == "duplicate"
    assert second.json()["deduplicated"] is True


@pytest.mark.asyncio
async def test_automatizacion_requiere_clave_y_guarda_triaje(client, ingest_headers, admin_token, auth):
    created = await client.post("/api/v1/alerts/ingest", json=unique_alert_payload(), headers=ingest_headers)
    alert_id = created.json()["alert_id"]
    path = f"/api/v1/alerts/{alert_id}/triage/automation"
    assert (await client.post(path)).status_code == 401
    assert (await client.post(path, headers={"X-Ingest-Key": "incorrecta"})).status_code == 401
    result = await client.post(path, headers=ingest_headers)
    assert result.status_code == 200, result.text
    detail = await client.get(f"/api/v1/alerts/{alert_id}", headers=auth(admin_token))
    assert len(detail.json()["triage_results"]) == 1
    repeated = await client.post(path, headers=ingest_headers)
    assert repeated.status_code == 200
    assert repeated.json()["id"] == result.json()["id"]


@pytest.mark.asyncio
async def test_triaje_con_fallback_heuristica(client, ingest_headers, admin_token, auth):
    payload = unique_alert_payload()
    payload["rule"]["description"] = f"Ransomware de prueba {uuid.uuid4().hex[:6]}"
    created = await client.post("/api/v1/alerts/ingest", json=payload, headers=ingest_headers)
    alert_id = created.json()["alert_id"]

    response = await client.post(
        f"/api/v1/alerts/{alert_id}/triage", headers=auth(admin_token)
    )
    assert response.status_code == 200, response.text
    triage = response.json()
    assert triage["verdict"] in {
        "true_positive",
        "false_positive",
        "suspicious",
        "benign",
        "inconclusive",
    }
    assert 0 <= triage["confidence"] <= 1
    assert triage["summary"]
    assert triage["recommended_actions"]


@pytest.mark.asyncio
async def test_feedback_e_incidente(client, ingest_headers, admin_token, auth):
    payload = unique_alert_payload()
    created = await client.post("/api/v1/alerts/ingest", json=payload, headers=ingest_headers)
    alert_id = created.json()["alert_id"]
    headers = auth(admin_token)

    feedback = await client.post(
        f"/api/v1/alerts/{alert_id}/feedback",
        json={"is_false_positive": False, "comment": "Validado por prueba automatizada"},
        headers=headers,
    )
    assert feedback.status_code == 200
    assert feedback.json()["is_false_positive"] is False

    incident = await client.post(
        f"/api/v1/alerts/{alert_id}/incident", json={"priority": "P2"}, headers=headers
    )
    assert incident.status_code == 201, incident.text
    assert incident.json()["ticket_id"].startswith("OSK-")


@pytest.mark.asyncio
async def test_listado_filtra_por_severidad(client, admin_token, auth):
    headers = auth(admin_token)
    response = await client.get("/api/v1/alerts?severity=critical&size=5", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert all(item["severity"] == "critical" for item in data["items"])
