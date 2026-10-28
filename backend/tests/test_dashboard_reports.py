from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_summary_y_series(client, admin_token, auth):
    headers = auth(admin_token)
    summary = await client.get("/api/v1/dashboard/summary?days=30", headers=headers)
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert data["totals"]["alerts"] > 0
    assert 0 <= data["rates"]["automation"] <= 100
    assert data["mttt"]["avg_minutes"] >= 0

    for endpoint in ("trend", "severity", "mttt", "sla", "fp-rate", "top-sources"):
        response = await client.get(f"/api/v1/dashboard/{endpoint}?days=30", headers=headers)
        assert response.status_code == 200, f"{endpoint}: {response.text}"


@pytest.mark.asyncio
async def test_reporte_excel_se_genera_y_descarga(client, admin_token, auth):
    headers = auth(admin_token)
    created = await client.post(
        "/api/v1/reports",
        json={"type": "operational", "format": "xlsx"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["status"] == "ready"
    assert report["file_size"] > 1000

    download = await client.get(f"/api/v1/reports/{report['id']}/download", headers=headers)
    assert download.status_code == 200
    assert download.content[:2] == b"PK"  # firma ZIP de un .xlsx


@pytest.mark.asyncio
async def test_bitacora_verifica_cadena(client, admin_token, auth):
    headers = auth(admin_token)
    response = await client.get("/api/v1/audit/verify-chain", headers=headers)
    assert response.status_code == 200
    assert response.json()["valid"] is True

    events = await client.get("/api/v1/audit?size=5", headers=headers)
    assert events.status_code == 200
    assert events.json()["total"] > 0


@pytest.mark.asyncio
async def test_evento_de_auditoria_desde_automatizacion(client, ingest_headers):
    response = await client.post(
        "/api/v1/audit/events",
        json={
            "module": "n8n",
            "action": "WORKFLOW_TEST",
            "entity_type": "workflow",
            "entity_id": "soc_lite_triage",
            "result": "success",
            "detail": {"source": "pytest"},
        },
        headers=ingest_headers,
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["hash"]) == 64
