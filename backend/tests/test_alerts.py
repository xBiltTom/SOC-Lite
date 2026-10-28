from __future__ import annotations

import asyncio
import uuid

import pytest

from tests.conftest import unique_alert_payload
from app.models.enums import Severity, TriageStatus, TriageVerdict
from app.models.alert import Alert
from app.services import triage_client
from app.services.triage_recovery import initialize_recovery
from app.core.config import settings
from app.db.session import SessionLocal
from sqlalchemy import text


def test_respaldo_del_backend_no_confirma_por_puntaje():
    alert = Alert(rule_level=14, asset_criticality=5, severity=Severity.CRITICAL, tags=["ransomware"])
    result = triage_client._heuristic(alert)
    assert result.verdict == TriageVerdict.SUSPICIOUS
    assert result.severity == Severity.CRITICAL
    assert result.needs_human and result.fallback_used


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
async def test_triaje_fallido_se_puede_reintentar_sin_duplicar(client, ingest_headers, admin_token, auth, monkeypatch):
    payload = unique_alert_payload()
    created = await client.post("/api/v1/alerts/ingest", json=payload, headers=ingest_headers)
    alert_id = created.json()["alert_id"]
    headers = auth(admin_token)

    async def fail(alert, enrichment):
        raise RuntimeError("fallo interno que no debe exponerse")

    monkeypatch.setattr(triage_client, "run_triage", fail)
    response = await client.post(f"/api/v1/alerts/{alert_id}/triage", headers=headers)
    assert response.status_code == 503
    assert response.json()["code"] == "TRIAGE_FAILED"
    assert "fallo interno" not in response.text
    detail = (await client.get(f"/api/v1/alerts/{alert_id}", headers=headers)).json()
    assert detail["status"] == "triage_failed" and not detail["triage_results"]
    assert (await client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "closed"}, headers=headers)).status_code == 409
    assert (await client.post(f"/api/v1/alerts/{alert_id}/feedback", json={"is_false_positive": True}, headers=headers)).status_code == 409
    assert (await client.post(f"/api/v1/alerts/{alert_id}/incident", json={}, headers=headers)).status_code == 409
    duplicate = await client.post("/api/v1/alerts/ingest", json=payload, headers=ingest_headers)
    assert duplicate.json()["alert_id"] == alert_id and duplicate.json()["status"] == "duplicate"

    async def recover(alert, enrichment):
        return triage_client._heuristic(alert)

    monkeypatch.setattr(triage_client, "run_triage", recover)
    retry = await client.post(f"/api/v1/alerts/{alert_id}/triage", headers=headers)
    assert retry.status_code == 200, retry.text
    detail = (await client.get(f"/api/v1/alerts/{alert_id}", headers=headers)).json()
    assert detail["status"] == "triaged" and len(detail["triage_results"]) == 1
    assert detail["triage_results"][0]["fallback_used"] is True
    async with SessionLocal() as db:
        rows = (await db.execute(text("SELECT action FROM audit_log WHERE entity_id = :id AND action IN ('TRIAGE_FAILED','TRIAGE_RETRY','TRIAGE_RUN')"), {"id": alert_id})).scalars().all()
    assert set(rows) == {"TRIAGE_FAILED", "TRIAGE_RETRY", "TRIAGE_RUN"}


@pytest.mark.asyncio
async def test_solicitudes_simultaneas_no_duplican_el_triaje(client, ingest_headers, admin_token, auth, monkeypatch):
    created = await client.post("/api/v1/alerts/ingest", json=unique_alert_payload(), headers=ingest_headers)
    alert_id = created.json()["alert_id"]
    started, finish = asyncio.Event(), asyncio.Event()

    async def wait_for_release(alert, enrichment):
        started.set()
        await finish.wait()
        return triage_client._heuristic(alert)

    monkeypatch.setattr(triage_client, "run_triage", wait_for_release)
    first = asyncio.create_task(client.post(f"/api/v1/alerts/{alert_id}/triage", headers=auth(admin_token)))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        second = await client.post(f"/api/v1/alerts/{alert_id}/triage", headers=auth(admin_token))
        assert second.status_code == 409
    finally:
        finish.set()
    assert (await first).status_code == 200
    detail = (await client.get(f"/api/v1/alerts/{alert_id}", headers=auth(admin_token))).json()
    assert len(detail["triage_results"]) == 1


@pytest.mark.asyncio
async def test_servicio_caido_con_respaldo_se_procesa_en_modo_degradado(client, ingest_headers, admin_token, auth, monkeypatch):
    monkeypatch.setattr(settings, "triage_service_url", "http://127.0.0.1:1")
    monkeypatch.setattr(settings, "triage_fail_open", True)
    created = await client.post("/api/v1/alerts/ingest", json=unique_alert_payload(), headers=ingest_headers)
    alert_id = created.json()["alert_id"]
    response = await client.post(f"/api/v1/alerts/{alert_id}/triage", headers=auth(admin_token))
    assert response.status_code == 200
    assert response.json()["status"] == "degraded" and response.json()["fallback_used"] is True
    detail = (await client.get(f"/api/v1/alerts/{alert_id}", headers=auth(admin_token))).json()
    assert detail["status"] == "triaged"


@pytest.mark.asyncio
async def test_reinicio_marca_como_fallido_el_triaje_interrumpido(client, ingest_headers, admin_token, auth):
    created = await client.post("/api/v1/alerts/ingest", json=unique_alert_payload(), headers=ingest_headers)
    alert_id = created.json()["alert_id"]
    async with SessionLocal() as db:
        await db.execute(text("UPDATE alerts SET status = 'triaging' WHERE id = CAST(:id AS uuid)"), {"id": alert_id})
        await db.commit()
    await initialize_recovery()
    detail = (await client.get(f"/api/v1/alerts/{alert_id}", headers=auth(admin_token))).json()
    assert detail["status"] == "triage_failed"
    async with SessionLocal() as db:
        action = (await db.execute(text("SELECT action FROM audit_log WHERE entity_id = :id AND action = 'TRIAGE_INTERRUPTED'"), {"id": alert_id})).scalar_one()
    assert action == "TRIAGE_INTERRUPTED"


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
async def test_falso_positivo_del_modelo_requiere_validacion_humana(client, ingest_headers, admin_token, auth, monkeypatch):
    async def fake_triage(alert, enrichment):
        return triage_client.TriageOutput(
            verdict=TriageVerdict.FALSE_POSITIVE, severity=Severity.MEDIUM,
            confidence=0.6, summary="Posible falso positivo; verificar con el analista",
            status=TriageStatus.COMPLETED, needs_human=True,
        )

    monkeypatch.setattr(triage_client, "run_triage", fake_triage)
    created = await client.post("/api/v1/alerts/ingest", json=unique_alert_payload(), headers=ingest_headers)
    alert_id = created.json()["alert_id"]
    response = await client.post(f"/api/v1/alerts/{alert_id}/triage", headers=auth(admin_token))
    assert response.status_code == 200
    assert response.json()["verdict"] == "false_positive"
    detail = await client.get(f"/api/v1/alerts/{alert_id}", headers=auth(admin_token))
    assert detail.json()["status"] == "triaged"
    feedback = await client.post(f"/api/v1/alerts/{alert_id}/feedback", json={"is_false_positive": True}, headers=auth(admin_token))
    assert feedback.status_code == 200
    detail = await client.get(f"/api/v1/alerts/{alert_id}", headers=auth(admin_token))
    assert detail.json()["status"] == "false_positive"


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
