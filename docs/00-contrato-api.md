# Contrato de API v1

> Base: `http://localhost:8010/api/v1` · OpenAPI interactivo: `/docs` · Redoc: `/redoc`
> Autenticación: `Authorization: Bearer <access_token>` salvo login/refresh e ingesta.

---

## Convenciones

| Tema | Convención |
|---|---|
| Formato | JSON UTF-8 |
| Fechas | ISO 8601 con zona (`2026-10-20T10:15:51.792Z`) |
| Paginación | `page` (1..N), `size` (1..200); respuesta `{items,total,page,size,pages}` |
| Errores | `{detail, code, request_id, path}`; validación añade `errors[]` |
| IDs | UUID v4 |
| Orden | `sort=received_at|-received_at|severity|-severity|rule_level|-rule_level` |
| Idempotencia | Ingesta por `fingerprint`; triaje por ventana de 60 s o `force=true` |

---

## Autenticación

### `POST /auth/login`

```json
{"username": "analista1", "password": "Analista123!"}
```

```json
{
  "access_token": "…",
  "refresh_token": "…",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "…", "username": "analista1", "email": "analista1@soclite.example.com",
    "full_name": "Carlos Mendoza",
    "role": {"id": 3, "code": "analyst", "name": "Analista SOC"},
    "is_active": true, "mfa_enabled": false,
    "last_login_at": "2026-10-20T10:15:00Z", "created_at": "2026-09-01T08:00:00Z",
    "permissions": ["alerts:read", "alerts:create", "triage:run", "…"]
  }
}
```

| Código | Significado |
|---|---|
| 200 | Sesión iniciada |
| 401 | Credenciales inválidas o cuenta inactiva |
| 422 | Payload inválido |

### `POST /auth/token`

`application/x-www-form-urlencoded` (`username`, `password`) para el flujo OAuth2 password. Misma
respuesta que `/login`.

### `POST /auth/refresh`

```json
{"refresh_token": "…"}
```

Rota el par. Si el token ya fue rotado, revoca todas las sesiones y devuelve `401`.

### `POST /auth/logout`

Requiere access token. Revoca refresh tokens (todos o el indicado). `200 {"detail":"Sesión cerrada"}`.

### `GET /auth/me`

Devuelve el perfil y los permisos efectivos (recalculados desde la base).

### `POST /auth/change-password`

```json
{"current_password": "Analista123!", "new_password": "NuevaClave2026!"}
```

Valida política, revoca sesiones y audita `PASSWORD_CHANGE`.

---

## Alertas

### `POST /alerts/ingest` (máquina)

Cabecera obligatoria: `X-Ingest-Key: <INGEST_API_KEY>`. No usa JWT.

```json
{
  "id": "wazuh-9001",
  "timestamp": "2026-10-20T10:00:00Z",
  "rule": {"id": "5710", "level": 10, "description": "Fuerza bruta SSH"},
  "agent": {"name": "SRV-WEB01", "criticality": 5},
  "data": {"srcip": "203.0.113.44", "dstip": "10.0.4.21", "dstport": 22, "protocol": "tcp"}
}
```

```json
{"status": "accepted", "alert_id": "…", "severity": "critical",
 "deduplicated": false, "message": "Alerta registrada en estado pendiente"}
```

| Código | Caso |
|---|---|
| 202 | Aceptada o duplicada |
| 401 | Clave inválida |
| 422 | Payload inválido |

### `GET /alerts`

Parámetros: `page`, `size`, `severity` (lista separada por comas), `status`, `source`, `q`,
`date_from`, `date_to`, `sort`.

```json
{
  "items": [{
    "id": "…", "source": "wazuh", "rule_id": "5710", "rule_level": 10,
    "description": "Fuerza bruta SSH…", "src_ip": "203.0.113.44",
    "agent_name": "SRV-WEB01", "asset_criticality": 5,
    "severity": "critical", "status": "triaged",
    "verdict": "true_positive", "confidence": 0.96,
    "summary": "…", "mttt_minutes": 6.0,
    "received_at": "2026-10-20T10:00:00Z", "incident_id": "…", "ticket_id": "OSK-10001"
  }],
  "total": 379, "page": 1, "size": 15, "pages": 26
}
```

### `GET /alerts/{id}`

Devuelve la alerta completa con `triage_results[]`, `enrichments[]`, `feedback[]`, `incident`,
`raw_payload`, `tags`, `fingerprint` y `mttt_minutes`.

### `POST /alerts/{id}/triage?force=false`

Ejecuta el triaje. Respuesta:

```json
{
  "id": "…", "verdict": "true_positive", "severity": "critical", "confidence": 0.96,
  "summary": "…", "reasoning": "…",
  "recommended_actions": [{"action": "Bloquear IP", "priority": 1, "owner": "SOC"}],
  "mitre_techniques": ["T1110"], "model": "llama3.1:8b", "prompt_version": "v1.2.0",
  "latency_ms": 18400, "status": "completed", "needs_human": false,
  "fallback_used": false, "triaged_at": "2026-10-20T10:01:00Z"
}
```

### `POST /alerts/{id}/feedback`

```json
{"is_false_positive": true, "comment": "Escaneo bloqueado por firewall"}
```

### `POST /alerts/{id}/incident`

```json
{"priority": "P2", "title": "Investigar SSH", "assignee_id": null}
```

Devuelve `IncidentOut` con `ticket_id`, `status`, `priority`, `sla_due_at`.

### `PATCH /alerts/{id}`

```json
{"status": "in_review", "tags": ["ssh", "revisar"], "asset_criticality": 4}
```

---

## Incidentes

| Método | Ruta | Permiso | Descripción |
|---|---|---|---|
| GET | `/incidents` | `incidents:read` | Filtros `status`, `priority`, `assignee_id`, `q` |
| GET | `/incidents/{id}` | `incidents:read` | Detalle |
| PATCH | `/incidents/{id}` | `incidents:update` / `incidents:close` | Estado, prioridad, responsable, resolución |

Cerrar o resolver exige `incidents:close`; se asigna `closed_at`.

---

## Dashboard

| Método | Ruta | Permiso | Respuesta |
|---|---|---|---|
| GET | `/dashboard/summary?days=30` | `dashboard:read` | `{period,totals,rates,mttt,deltas,generated_at}` |
| GET | `/dashboard/trend?days=30` | `dashboard:read` | `[{date,total,critical,high,medium,low,false_positive}]` |
| GET | `/dashboard/severity?days=30` | `dashboard:read` | `{items:[{severity,count}],total}` |
| GET | `/dashboard/top-sources?days=30&by=ip` | `dashboard:read` | `[{key,label,count,critical}]` |
| GET | `/dashboard/mttt?days=30` | `dashboard:read` | `[{severity,count,avg_minutes,p95_minutes,target_minutes,compliance}]` |
| GET | `/dashboard/fp-rate?days=30` | `dashboard:read` | `[{date,triaged,false_positive,rate}]` |
| GET | `/dashboard/sla?days=30` | `dashboard:read` | `[{severity,target_minutes,total,within_sla,compliance,breaches}]` |
| GET | `/dashboard/analysts?days=30` | `dashboard:read` | `[{username,full_name,actions,triages}]` |

`days` ∈ [1, 365]. `by` ∈ `ip|agent|rule`.

---

## Reportes

### `GET /reports/types`

```json
[{"type":"operational","name":"Operacional","description":"…","formats":"pdf,docx,xlsx"}]
```

### `POST /reports`

```json
{"type": "management", "format": "pdf", "date_from": "2026-09-21", "date_to": "2026-10-20"}
```

```json
{"id":"…","type":"management","format":"pdf","status":"ready",
 "params":{"days":30,"date_from":"2026-09-21","date_to":"2026-10-20"},
 "file_size":284311,"created_at":"…","completed_at":"…","error":null}
```

### `GET /reports`

Historial paginado.

### `GET /reports/{id}/download`

`200` con `Content-Disposition: attachment` y MIME:
`application/pdf`, `…wordprocessingml.document`, `…spreadsheetml.sheet`.
Requiere `reports:export`. Audita `REPORT_DOWNLOAD`.

---

## Auditoría

### `GET /audit`

Filtros: `module`, `action`, `username`, `result` (`success|failure|denied`), `q`,
`date_from`, `date_to`, `page`, `size`.

```json
{
  "items": [{
    "id": 142, "occurred_at": "2026-10-20T10:15:51Z", "username": "analista1",
    "module": "triage", "action": "TRIAGE_RUN", "entity_type": "alert",
    "entity_id": "…", "result": "success",
    "detail": {"verdict": "true_positive"}, "ip": "10.10.1.30",
    "request_id": "…", "duration_ms": 14380, "hash": "…"
  }],
  "total": 1250, "page": 1, "size": 20, "pages": 63
}
```

### `GET /audit/modules`

`[{"module":"alerts","total":812}, …]`

### `GET /audit/stats?days=30`

`{total, success, failure, denied, modules[]}`

### `GET /audit/verify-chain`

```json
{"valid": true, "checked": 1250, "broken_at": null, "message": "Cadena íntegra"}
```

### `GET /audit/export?format=csv|xlsx`

Descarga CSV/XLSX (máx. 50 000 filas). Requiere `audit:export`. Audita `AUDIT_EXPORT`.

### `POST /audit/events` (máquina)

Cabecera `X-Ingest-Key`. Para n8n:

```json
{"module":"triage","action":"TRIAGE_COMPLETED","entity_type":"alert","entity_id":"…",
 "result":"success","username":"n8n","detail":{"verdict":"true_positive"}}
```

```json
{"id": 150, "hash": "…64 hex…"}
```

---

## Usuarios y roles

| Método | Ruta | Permiso | Descripción |
|---|---|---|---|
| GET | `/users` | `users:read` | Filtros `q`, `role`, `is_active` |
| POST | `/users` | `users:create` | `{username,email,full_name,password,role_id,is_active}` |
| GET | `/users/{id}` | `users:read` | Detalle |
| PATCH | `/users/{id}` | `users:update` | Email, nombre, rol, estado, MFA |
| DELETE | `/users/{id}` | `users:delete` | Baja lógica; no permite el último admin |
| POST | `/users/{id}/reset-password` | `users:update` | `{new_password}`; revoca sesiones |
| GET | `/roles` | `roles:read` | Roles con permisos y `user_count` |
| GET | `/permissions` | `roles:read` | Catálogo |
| PUT | `/roles/{id}/permissions` | `roles:update` | `{permission_codes:[…]}` |

---

## Salud

| Método | Ruta | Auth | Respuesta |
|---|---|---|---|
| GET | `/health` | — | `{status,service,version,environment,database,timestamp}` |
| GET | `/health/ready` | — | `{status,database,triage_service}` |

---

## Matriz de permisos por endpoint (resumen)

| Grupo | Lectura | Escritura | Exportación |
|---|---|---|---|
| Alertas | `alerts:read` | `alerts:create/update/delete`, `triage:run/feedback` | `alerts:export` |
| Incidentes | `incidents:read` | `incidents:create/update/close` | `incidents:export` |
| Dashboard | `dashboard:read` | — | `dashboard:export` |
| Usuarios | `users:read` | `users:create/update/delete` | — |
| Roles | `roles:read` | `roles:update` | — |
| Auditoría | `audit:read` | — | `audit:export` |
| Reportes | `reports:read` | `reports:create` | `reports:export` |

La matriz efectiva se administra en `roles × permissions` y se puede editar desde la UI
(`PUT /roles/{id}/permissions`), salvo el rol `admin`, que es inmutable.
