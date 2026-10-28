# SOC-Lite

**Triaje automático de alertas SOC para PYME, mediana empresa y organismo público.**
Caso de uso 1 (crítico): reducir la fatiga de alertas combinando orquestación low-code
(n8n), enriquecimiento de threat intelligence y razonamiento LLM local (LangChain + Ollama),
con una consola web operativa, RBAC y bitácora inmutable.

![Panel de control](docs/screenshots/02-dashboard.png)

---

## El problema en una frase

Los SOAR comerciales cuestan decenas de miles de dólares; las PYMEs sólo tienen SIEMs open
source (Wazuh) que **generan** alertas pero no las **priorizan ni enriquecen**. El 70–90 % son
falsos positivos o de baja relevancia, así que las alertas críticas se pierden en la cola y el
MTTT se mide en horas.

## La solución

```
Wazuh / OPNsense ──webhook──▶ n8n ──▶ LangChain + Ollama ──▶ PostgreSQL ──▶ Dashboard React
                                  │            │                              │
                                  │            └─ VirusTotal · AbuseIPDB       │
                                  │               GeoIP · MITRE · memoria FP   │
                                  └──▶ Slack · osTicket · bitácora ◀──────────┘
```

- **n8n** ingesta, normaliza, deduplica, enruta por severidad y notifica.
- **LangChain** enriquece y clasifica con un agente de herramientas; si Ollama cae, un motor
  heurístico determinista sigue triando (modo `degraded`) — la alerta nunca se pierde.
- **FastAPI** expone la API del dashboard, aplica RBAC, persiste el triaje y genera reportes.
- **React** ofrece dashboard, cola de alertas, detalle con resumen LLM, usuarios/roles,
  auditoría y reportes.

## Los seis requisitos obligatorios

| Requisito | Implementación verificada |
|---|---|
| Stack justificado | FastAPI + SQLAlchemy 2 async + PostgreSQL 16 + React 18/TS/Vite + n8n + LangChain/Ollama. Ver [07-stack](docs/07-stack-tecnologico.md) |
| PostgreSQL principal | 13 tablas, 5 vistas, 11 enums, `JSONB`, `INET`, `ARRAY`, `percentile_cont` para el P95 del MTTT |
| Dashboard de métricas | 8 endpoints de agregación; KPIs de volumen, MTTT, SLA, FP, automatización, severidad, top orígenes y tendencia |
| Reportes PDF/Word/Excel | ReportLab, python-docx y openpyxl; 3 tipos de reporte × 3 formatos, con historial y descarga auditada |
| RBAC | 5 roles, 26 permisos `módulo:acción`, matriz editable en la UI y validación en cada endpoint |
| Bitácora de auditoría | ENTER/EXIT por módulo + eventos de negocio, con usuario, fecha, hora, IP, resultado y cadena de hashes SHA-256 append-only |

## Arranque rápido

### Opción A — Docker Compose (recomendado)

```bash
cp .env.example .env          # cambiar SECRET_KEY, contraseñas y claves
docker compose up -d --build
docker compose exec ollama ollama pull llama3.1:8b   # perfil "llm"

# Frontend   → http://localhost:8090
# API docs   → http://localhost:8010/docs
# n8n        → http://localhost:5679
# PostgreSQL → localhost:5439
```

> Ollama es opcional. Sin él, el microservicio responde con el motor heurístico y lo marca
> como `degraded` (comportamiento esperado, no un fallo).

### Puertos de esta instalación

| Servicio | URL / puerto host | Notas |
|---|---|---|
| Frontend | **http://localhost:8090** | Vite en desarrollo y Nginx en Docker |
| API | http://localhost:8010/api/v1 | |
| Swagger / OpenAPI | **http://localhost:8010/docs** | Redoc en `/redoc` |
| Microservicio de triaje | http://localhost:8011/health | Sin interfaz web |
| n8n | http://localhost:5679 | Contenedor interno 5678 |
| PostgreSQL | localhost:**5439** | Contenedor interno 5432 |

> Se eligieron 8090/8010/8011/5439 para no chocar con aplicaciones que ya ocupan 3000, 8000,
> 8080 o 5432 en el equipo. Si necesita otros, cámbielos en `docker-compose.yml`,
> `frontend/vite.config.ts` y `backend/app/core/config.py`.

### Opción B — Desarrollo local

```bash
# 1. Base de datos (PostgreSQL 16 en 5439)
createdb -h 127.0.0.1 -p 5439 -U soclite soclite
psql -h 127.0.0.1 -p 5439 -U soclite -d soclite -f db/schema.sql
psql -h 127.0.0.1 -p 5439 -U soclite -d soclite -f db/seed.sql

# 2. API
cd backend
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010

# 3. Microservicio de triaje
cd ../langchain-service
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8011

# 4. Frontend
cd ../frontend
npm install
npm run dev            # http://127.0.0.1:8090 (proxy /api → :8010)
```

## Credenciales de demostración

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `Admin123!` | Administrador |
| `gerente` | `Gerente123!` | Jefe de SOC |
| `analista1` | `Analista123!` | Analista |
| `analista2` | `Analista123!` | Analista |
| `auditor` | `Auditor123!` | Auditor |
| `visor` | `Visor123!` | Solo lectura |

> Cambiar todas las contraseñas y `SECRET_KEY` antes de cualquier uso real. Las cuentas son
> sólo para el laboratorio.

## Estructura del repositorio

```text
soc-lite/
├── docker-compose.yml          # db, backend, triage, frontend, n8n, ollama (perfil)
├── .env.example                # 60+ variables documentadas
├── Makefile                    # up, down, schema, seed, test, build, smoke
├── db/
│   ├── schema.sql              # 13 tablas, 5 vistas, enums, triggers, generador sintético
│   └── seed.sql                # roles, permisos, usuarios, 8 alertas curadas + 720 sintéticas
├── backend/                    # FastAPI + SQLAlchemy 2 async
│   ├── app/core/               # config, JWT, RBAC, errores, logging
│   ├── app/models/             # ORM tipado
│   ├── app/schemas/            # contratos Pydantic v2
│   ├── app/api/v1/routers/     # auth, users, alerts, incidents, dashboard, reports, audit
│   ├── app/services/           # ingesta, triaje, métricas, reportes, auditoría
│   ├── app/middleware/         # request-id, cabeceras, bitácora ENTER/EXIT
│   └── tests/                  # 14 pruebas de integración contra PostgreSQL real
├── langchain-service/          # FastAPI + LangChain + Ollama
│   ├── app/agents/             # agente con tool calling y memoria de casos
│   ├── app/tools/              # VirusTotal, AbuseIPDB, GeoIP, MITRE
│   ├── app/chains/             # prompts versionados y defensas anti-inyección
│   └── app/engines/            # fallback heurístico determinista
├── frontend/                   # React 18 + TypeScript + Vite + Tailwind
│   ├── src/api/                # cliente axios, refresh automático, endpoints tipados
│   ├── src/components/         # layout, badges, KPIs, tablas, modales
│   ├── src/pages/              # login, dashboard, alertas, detalle, incidentes, usuarios,
│   │                           # roles, auditoría, reportes
│   └── deploy/nginx.conf       # SPA + proxy /api + cabeceras + CSP
├── n8n/
│   └── soc_lite_triage_workflow.json   # 21 nodos (10 operativos + soporte), importable
├── docs/                       # arquitectura, modelo de datos, backend, frontend, workflow,
│                               # datasets, stack, contrato de API y capturas
└── backend/storage/reports/    # PDF/Word/Excel generados en local
                                # (en Docker: volumen "reports")
```

## Documentación

| # | Sección | Documento |
|---|---|---|
| 1 | Arquitectura del sistema | [01-arquitectura.md](docs/01-arquitectura.md) |
| 2 | Modelo de datos PostgreSQL y semillas | [02-modelo-datos.md](docs/02-modelo-datos.md) · [schema.sql](db/schema.sql) · [seed.sql](db/seed.sql) |
| 3 | Backend completo | [03-backend.md](docs/03-backend.md) |
| 4 | Frontend completo | [04-frontend.md](docs/04-frontend.md) |
| 5 | Flujo de nodos n8n | [05-workflow-n8n.md](docs/05-workflow-n8n.md) · [workflow JSON](n8n/soc_lite_triage_workflow.json) |
| 6 | Datasets públicos | [06-datasets-publicos.md](docs/06-datasets-publicos.md) |
| 7 | Stack tecnológico | [07-stack-tecnologico.md](docs/07-stack-tecnologico.md) |
| — | Contrato de API v1 | [00-contrato-api.md](docs/00-contrato-api.md) |

## Prueba de humo

```bash
# 1. Autenticarse
TOKEN=$(curl -s -X POST http://localhost:8010/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"analista1","password":"Analista123!"}' | jq -r .access_token)

# 2. Ingerir una alerta de Wazuh
curl -s -X POST http://localhost:8010/api/v1/alerts/ingest \
  -H "X-Ingest-Key: $INGEST_API_KEY" -H 'Content-Type: application/json' \
  -d '{"id":"demo-1","rule":{"id":"5710","level":12,"description":"Fuerza bruta SSH"},
       "agent":{"name":"SRV-WEB01"},"data":{"srcip":"203.0.113.44","dstip":"10.0.4.21"}}'

# 3. Triar (usa LangChain o el fallback heurístico)
curl -s -X POST http://localhost:8010/api/v1/alerts/<ALERT_ID>/triage \
  -H "Authorization: Bearer $TOKEN"

# 4. Dashboard, bitácora y reporte
curl -s "http://localhost:8010/api/v1/dashboard/summary?days=30" -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8010/api/v1/audit/verify-chain" -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8010/api/v1/reports \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"operational","format":"pdf"}'
```

## Importar el workflow en n8n

1. Abrir `http://localhost:5679` y crear la cuenta de propietario.
2. **Workflows → Import from File** → `n8n/soc_lite_triage_workflow.json`.
3. Crear la credencial **PostgreSQL** apuntando a `db:5432` (usuario `soclite`, base `soclite`)
   y asignarla a los tres nodos PostgreSQL.
4. Configurar variables de entorno del contenedor: `LANGCHAIN_URL`, `SLACK_WEBHOOK_URL`,
   `OSTICKET_URL`, `OSTICKET_TOKEN`, `SOCLITE_API_URL`, `SOCLITE_INGEST_KEY`.
5. Activar el workflow; el webhook queda en `POST http://localhost:5679/webhook/soc-lite-ingest`.

La tabla de los 10 nodos operativos, sus entradas/salidas y las consultas SQL están en
[05-workflow-n8n.md](docs/05-workflow-n8n.md).

## Verificación ejecutada en este entregable

| Componente | Verificación | Resultado |
|---|---|---|
| PostgreSQL | `schema.sql` + `seed.sql` sobre PostgreSQL 16 | 13 tablas, 728 alertas, 647 triajes, 33 incidentes |
| Backend | `pytest` (integración contra PostgreSQL real) | **14 passed** |
| API | login, RBAC, ingesta, dedup, triaje, feedback, incidente, dashboard, reportes, auditoría | OK |
| Reportes | PDF (ReportLab), DOCX (python-docx), XLSX (openpyxl) | archivos válidos y descargables |
| Auditoría | `GET /audit/verify-chain` | cadena íntegra |
| Frontend | `tsc --noEmit` + `vite build` | 0 errores TS; ~830 KB (gzip ~240 KB) |
| UI | capturas con Chrome headless | 9 pantallas en `docs/screenshots/` |
| n8n | importación en `n8n:latest` + SQL validado contra PostgreSQL | workflow importado (21 nodos) |

### Limitaciones conocidas

- **Ollama no estaba disponible** en el entorno de verificación: el servicio de triaje respondió
  con el motor heurístico (`status=degraded`). El camino LLM está implementado y se activa al
  detectar Ollama en `OLLAMA_BASE_URL`; requiere `ollama pull llama3.1:8b`.
- **No se ejecutó el workflow n8n de punta a punta** porque requiere crear la credencial
  PostgreSQL y las variables de Slack/osTicket en la instancia. Sí se importó en n8n y se
  validaron las dos consultas SQL contra la base real.
- Las APIs externas (VirusTotal, AbuseIPDB, GeoIP) requieren claves; sin ellas se marcan como
  `skipped` y el veredicto baja su confianza.
- El entorno local no incluye TLS; en producción se termina en Nginx/ingress con certificados.

## Seguridad

- JWT de acceso corto (30 min) + refresh rotativo con detección de reutilización.
- Contraseñas con bcrypt (coste 12) y política mínima de 10 caracteres.
- RBAC evaluado en el backend; la UI sólo oculta lo que el usuario no puede hacer.
- Bitácora append-only con triggers que bloquean `UPDATE`/`DELETE` y cadena SHA-256.
- Webhook de ingesta con clave compartida (`X-Ingest-Key`) y comparación en tiempo constante.
- Defensa contra inyección de prompts: la alerta se delimita como dato no confiable y la salida
  se valida con Pydantic antes de persistirse.
- Cabeceras de seguridad y CSP en Nginx; CORS restringido por configuración.
- El agente **propone** acciones, no ejecuta contenciones: la respuesta humana queda en el centro.

## Licencia

MIT para el código. Los datasets externos conservan sus propias licencias (ver
[06-datasets-publicos.md](docs/06-datasets-publicos.md)).
