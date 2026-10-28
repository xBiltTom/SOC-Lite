"""Contrato del canal en vivo con la base de datos del laboratorio."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.core.config import settings
from tests.conftest import ADMIN, unique_alert_payload


def test_live_requires_token_and_emits_after_ingest():
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/live") as ws:
            ws.send_json({"token": "invalid"})
            with pytest.raises(WebSocketDisconnect) as error:
                ws.receive_json()
            assert error.value.code == 4401

        login = client.post("/api/v1/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]})
        assert login.status_code == 200
        with client.websocket_connect("/api/v1/live") as ws:
            ws.send_json({"token": login.json()["access_token"]})
            assert ws.receive_json()["type"] == "connected"
            payload = unique_alert_payload()
            payload["demo"] = True
            result = client.post("/api/v1/alerts/ingest", json=payload, headers={"X-Ingest-Key": settings.ingest_api_key})
            assert result.status_code == 202
            event = ws.receive_json()
            assert event["type"] == "alert.created"
            assert event["alert_id"] == result.json()["alert_id"]
            assert event["simulated"] is True
            triage = client.post(f"/api/v1/alerts/{event['alert_id']}/triage/automation", headers={"X-Ingest-Key": settings.ingest_api_key})
            assert triage.status_code == 200
            assert ws.receive_json() == {"type": "alert.triaged", "alert_id": event["alert_id"]}
