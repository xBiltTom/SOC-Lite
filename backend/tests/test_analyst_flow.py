"""Recorrido del analista desde la alerta hasta el cierre del caso."""
import pytest

from tests.conftest import VIEWER, login, unique_alert_payload


@pytest.mark.asyncio
async def test_analyst_corrects_feedback_assigns_and_closes(client, ingest_headers, analyst_token, auth):
    headers = auth(analyst_token)
    created = await client.post('/api/v1/alerts/ingest', json=unique_alert_payload(), headers=ingest_headers)
    alert_id = created.json()['alert_id']

    first = await client.post(f'/api/v1/alerts/{alert_id}/feedback', json={'is_false_positive': True, 'comment': 'Revisión inicial'}, headers=headers)
    assert first.status_code == 200
    corrected = await client.post(f'/api/v1/alerts/{alert_id}/feedback', json={'is_false_positive': False, 'comment': 'Evidencia adicional confirma la actividad'}, headers=headers)
    assert corrected.status_code == 200
    detail = await client.get(f'/api/v1/alerts/{alert_id}', headers=headers)
    assert detail.json()['status'] == 'in_review'
    assert detail.json()['feedback'][0]['is_false_positive'] is False

    candidates = await client.get('/api/v1/incidents/assignees', headers=headers)
    assert candidates.status_code == 200, candidates.text
    assignee = next(user for user in candidates.json() if user['username'] == 'analista2')
    assert set(assignee) == {'id', 'username', 'full_name'}
    incident = await client.post(f'/api/v1/alerts/{alert_id}/incident', json={'title': 'Revisar acceso SSH', 'priority': 'P2'}, headers=headers)
    assert incident.status_code == 201, incident.text
    assert incident.json()['ticket_id'].startswith('INC-')
    incident_id = incident.json()['id']
    duplicate = await client.post(f'/api/v1/alerts/{alert_id}/incident', json={}, headers=headers)
    assert duplicate.status_code == 409

    assigned = await client.patch(f'/api/v1/incidents/{incident_id}', json={'assignee_id': assignee['id'], 'status': 'investigating'}, headers=headers)
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()['assignee_id'] == assignee['id']
    assert assigned.json()['assignee_name'] == assignee['full_name']
    linked = await client.get(f'/api/v1/alerts/{alert_id}', headers=headers)
    assert linked.json()['incident']['id'] == incident_id
    assert linked.json()['incident']['assignee_name'] == assignee['full_name']

    no_resolution = await client.patch(f'/api/v1/incidents/{incident_id}', json={'status': 'closed', 'resolution': '   '}, headers=headers)
    assert no_resolution.status_code == 422
    closed = await client.patch(f'/api/v1/incidents/{incident_id}', json={'status': 'closed', 'resolution': 'Investigación completada; se revisaron los registros.'}, headers=headers)
    assert closed.status_code == 200, closed.text
    assert closed.json()['status'] == 'closed' and closed.json()['closed_at']
    assert closed.json()['resolution'].startswith('Investigación completada')

    viewer_token = await login(client, VIEWER)
    denied = await client.patch(f'/api/v1/incidents/{incident_id}', json={'priority': 'P1'}, headers=auth(viewer_token))
    assert denied.status_code == 403
    assert (await client.get('/api/v1/incidents/assignees', headers=auth(viewer_token))).status_code == 403


@pytest.mark.asyncio
async def test_invalid_incident_assignee_is_rejected(client, ingest_headers, analyst_token, auth):
    headers = auth(analyst_token)
    created = await client.post('/api/v1/alerts/ingest', json=unique_alert_payload(), headers=ingest_headers)
    alert_id = created.json()['alert_id']
    response = await client.post(f'/api/v1/alerts/{alert_id}/incident', json={'assignee_id': '00000000-0000-0000-0000-000000000000'}, headers=headers)
    assert response.status_code == 422
    assert response.json()['code'] == 'INVALID_ASSIGNEE'
