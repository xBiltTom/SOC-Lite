# 7. Stack tecnológico detallado

> Criterio: **mínimo coste operativo, máxima trazabilidad y soberanía del dato**. Todo el software
> es open source y desplegable on-premise; no hay dependencia obligatoria de la nube.

---

## 7.1 Resumen

| Capa | Tecnología | Versión fijada | Licencia | Por qué |
|---|---|---|---|---|
| Lenguaje backend | Python | 3.11 | PSF | Ecosistema IA, tipado moderno, soporte LTS de librerías |
| Framework API | FastAPI | 0.115.6 | MIT | Async nativo, Pydantic, OpenAPI automático |
| ORM | SQLAlchemy | 2.0.36 | MIT | ORM maduro con soporte async real y tipado |
| Driver | asyncpg | 0.30.0 | Apache-2.0 | Rendimiento y pool para PostgreSQL |
| Validación | Pydantic | 2.10.4 | MIT | Contratos estrictos y serialización |
| Auth | PyJWT + bcrypt | 2.10.1 / 4.2.1 | MIT / Apache-2.0 | JWT estándar y hashing robusto |
| HTTP cliente | httpx | 0.28.1 | BSD-3 | Cliente async con timeouts |
| PDF | ReportLab | 4.2.5 | BSD | Reportes reproducibles en servidor |
| Word | python-docx | 1.1.2 | MIT | DOCX programático |
| Excel | openpyxl | 3.1.5 | MIT | XLSX con estilos y gráficos nativos |
| Base de datos | PostgreSQL | 16 | PostgreSQL License | JSONB, INET, enums, percentiles, integridad |
| Orquestación | n8n | latest (1.x) | Sustainable Use License* | Integraciones, reintentos y visibilidad |
| IA | LangChain Core + langchain-ollama | ≥1.0, <2 | MIT | Tool calling, prompts, cadenas |
| LLM local | Ollama (llama3.1:8b / mistral) | latest | MIT (Ollama) / licencia del modelo | Soberanía del dato, coste marginal cero |
| Frontend | React + TypeScript | 18.3.1 / 5.6.3 | MIT / Apache-2.0 | Ecosistema, tipado, componentes |
| Build | Vite | 5.4.11 | MIT | Dev rápido, build optimizado |
| UI | Tailwind CSS | 3.4.17 | MIT | Diseño consistente sin CSS muerto |
| Datos remotos | TanStack Query | 5.62.7 | MIT | Caché, reintentos, invalidación |
| Gráficos | Recharts | 2.15.0 | MIT | Charts declarativos para React |
| Ruteo | React Router | 6.28.0 | MIT | Rutas protegidas |
| HTTP frontend | Axios | 1.7.9 | MIT | Interceptores de JWT/refresh |
| Servidor web | Nginx | 1.27-alpine | BSD-2 | SPA, proxy, TLS, CSP |
| Contenedores | Docker + Compose | 29.x / v2 | Apache-2.0 | Reproducibilidad y despliegue |
| Pruebas | pytest + pytest-asyncio | 8.3.4 / 0.25 | MIT / Apache-2.0 | Integración async contra BD real |

\* n8n es "fair-code": uso interno y autoalojado permitido; revisar la licencia si se ofrece como
SaaS a terceros.

---

## 7.2 Backend

### ¿Por qué FastAPI y no Django/Flask?

| Criterio | FastAPI | Django REST | Flask |
|---|---|---|---|
| Async nativo | ✅ | ⚠️ parcial (ASGI desde 4.1) | ⚠️ requiere extensiones |
| Validación + OpenAPI | ✅ Pydantic + Swagger | ✅ DRF + drf-spectacular | ❌ manual |
| Curva de aprendizaje | Baja | Media | Baja |
| Admin incluido | ❌ | ✅ | ❌ |
| Ideal para LLM/streaming | ✅ | ⚠️ | ✅ |
| Ecosistema ORM | SQLAlchemy 2 | Django ORM | SQLAlchemy |

**Decisión:** FastAPI por async, contratos Pydantic y documentación automática. No se necesita el
admin de Django porque la consola React cubre la operación.

### ¿Por qué SQLAlchemy 2 async?

- Mismo modelo para lectura y escritura, con `selectinload` para evitar N+1.
- Compatible con Alembic para migraciones futuras.
- `asyncpg` entrega ~2–3× más throughput que `psycopg2` en cargas de I/O.

### ¿Por qué no un ORM "mágico" o SQL plano?

- SQL plano en servicios críticos (dashboard, reportes) para aprovechar `percentile_cont`,
  `FILTER`, CTEs y `LATERAL`.
- ORM para CRUD y relaciones, evitando SQL injection y manteniendo tipos.

---

## 7.3 Frontend

### ¿Por qué React + TypeScript?

- Tipado estricto contra el contrato de la API (`types/index.ts`), lo que detectó errores en build.
- Ecosistema de tablas/gráficos y familiaridad del equipo.
- Vite reduce el ciclo de feedback (HMR) y produce chunks pequeños.

### ¿Por qué Tailwind y no una librería de componentes?

- Control total del diseño oscuro y de los estados de severidad.
- Sin dependencia de un tema propietario; el CSS final es pequeño (~34 kB).
- Componentes propios reutilizables (`.card`, `.btn`, `.table`).

### ¿Por qué TanStack Query?

- El dashboard tiene 7 consultas independientes que se pueden cachear e invalidar por separado.
- Evita duplicar estado global y maneja reintentos/cancelación.
- `placeholderData` mantiene la tabla estable al paginar.

### ¿Por qué Recharts?

- Declarativo, responsive y suficiente para área/dona/barras/líneas.
- Alternativas: ECharts (más potente, más peso), Chart.js (imperativo), D3 (curva alta).
- El chunk de Recharts (~423 kB) se separa y cachea; sólo se descarga al entrar al dashboard.

---

## 7.4 Datos

### PostgreSQL 16

| Necesidad | Ventaja de PostgreSQL |
|---|---|
| Payload heterogéneo | `JSONB` indexable con GIN |
| IPs | tipo `INET` con operadores de red |
| Métricas | `percentile_cont`, `FILTER`, `generate_series`, CTEs |
| Integridad | FKs, `CHECK`, enums nativos, triggers |
| Concurrencia | MVCC, advisory locks para la cadena de auditoría |
| Extensiones | `pgcrypto` (hash), `pg_trgm` (búsqueda), `citext` |

**¿Por qué no MongoDB?** Las métricas y los joins (alerta → triaje → incidente → usuario) son
relacionales; MongoDB obligaría a duplicar datos y perdería integridad referencial.

**¿Por qué no Elasticsearch?** Excelente para búsqueda de logs a gran escala, pero añade un clúster
y operación. Para 5 000 alertas/día, PostgreSQL con índices GIN/trigram es suficiente. Se puede
añadir Elasticsearch como capa de búsqueda si el volumen crece.

**¿Por qué no MySQL?** `JSONB`, `INET`, enums y funciones de percentiles son más limitados; la
migración no aporta ventaja.

### Volumen y crecimiento

| Escenario | Alertas/día | Almacenamiento anual estimado | Recomendación |
|---|---|---|---|
| PYME | 500–2 000 | 10–40 GB | 1 instancia, 4 vCPU/8 GB |
| Mediana | 5 000–20 000 | 50–200 GB | 8 vCPU/32 GB + réplica de lectura |
| Pública | 20 000–100 000 | 200 GB–1 TB | Particionado + archivado + HA |

---

## 7.5 IA y orquestación

### LangChain vs LangFlow

| Criterio | LangChain (elegido) | LangFlow |
|---|---|---|
| Tool calling y agentes | ✅ control total | ⚠️ visual, limitado |
| Versionado de prompts | ✅ en código | ⚠️ en el grafo |
| Tests unitarios | ✅ | ❌ |
| Memoria de casos | ✅ | ⚠️ |
| Prototipado rápido | ⚠️ | ✅ |
| Perfil del equipo | Desarrolladores | Analistas |

**Decisión:** LangChain en un microservicio FastAPI. LangFlow se puede usar para explorar prompts,
pero no para producción con validación estricta.

### n8n vs alternativas

| Criterio | n8n (elegido) | Airflow | Temporal | Python puro |
|---|---|---|---|---|
| Webhooks event-driven | ✅ | ⚠️ | ✅ | ✅ |
| Integraciones listas | ✅ 400+ | ⚠️ | ❌ | ❌ |
| Reintentos/visibilidad | ✅ | ✅ | ✅ | ❌ |
| Operación por analistas | ✅ | ❌ | ❌ | ❌ |
| Complejidad operativa | Baja | Media | Alta | Baja |

**Decisión:** n8n por velocidad de integración y autonomía del equipo SOC. La lógica crítica se
mantiene en Python testeable.

### Ollama vs OpenAI

| Criterio | Ollama local (default) | OpenAI (opcional) |
|---|---|---|
| Privacidad | ✅ los datos no salen | ❌ payload a terceros |
| Coste | HW + electricidad | Por token |
| Calidad | Buena en 8B; menor en razonamiento complejo | Superior |
| Latencia | 5–25 s en GPU/CPU moderada | 1–5 s |
| Disponibilidad | Depende del host | SLA del proveedor |
| Cumplimiento | Soberanía | Requiere DPA y evaluación |

**Decisión:** Ollama por defecto; el proveedor es una variable de entorno. La arquitectura permite
cambiar sin tocar n8n ni el frontend.

---

## 7.6 Infraestructura

| Componente | Tecnología | Notas |
|---|---|---|
| Contenedores | Docker Engine 24+ / Compose v2 | Red interna, volúmenes nombrados |
| Proxy/TLS | Nginx 1.27 | Terminación TLS, CSP, rate limiting (futuro) |
| Orquestación | Docker Compose | Suficiente para una instancia; Kubernetes si HA |
| Backups | `pg_dump` + WAL | Diario + retención 30 días |
| Observabilidad | Logs JSON + `/health` | Pendiente: Prometheus/Grafana/Loki |
| Secretos | `.env` + gestor externo | Vault/SOPS en producción |

### Puertos

| Servicio | Host | Contenedor |
|---|---|---|
| Frontend | 8090 | 80 |
| API | 8010 | 8000 |
| Triaje | 8011 | 8001 |
| n8n | 5679 | 5678 |
| PostgreSQL | 5439 | 5432 |
| Ollama | 11435 | 11434 |

---

## 7.7 Dimensionamiento y coste

### Perfiles

| Perfil | Endpoints | Alertas/día | HW recomendado | LLM | Coste mensual estimado* |
|---|---|---|---|---|---|
| PYME | 50–200 | 500–2 000 | 4 vCPU, 8 GB, 80 GB | Ollama 8B en CPU o API | USD 40–120 |
| Mediana | 200–1 000 | 5 000–20 000 | 8 vCPU, 32 GB, 500 GB | Ollama 8B + GPU T4 opcional | USD 250–600 |
| Pública | 1 000+ | 20 000+ | 2 nodos, 16 vCPU, 64 GB, 1 TB | Ollama 70B o API privada | USD 800–2 500 |

\* Sólo infraestructura/energía; el software es open source. Los precios de nube varían por región
y proveedor. No incluye horas de operación ni auditoría.

### Comparación con SOAR comercial

| Concepto | SOAR comercial | SOC-Lite |
|---|---|---|
| Licencia anual | USD 30 000–150 000 | 0 |
| Implementación | 3–6 meses | 1–2 semanas |
| Personal dedicado | 1–2 FTE | 0.2–0.5 FTE |
| Coste LLM | Aparte | Local (0) o API (~USD 10–50/mes) |
| Lock-in | Alto | Bajo (todo open source) |

La comparación es orientativa: un SOAR comercial ofrece soporte 24/7, conectores certificados y
cumplimiento contractual que SOC-Lite no incluye.

---

## 7.8 Requisitos no funcionales

| Requisito | Cómo se cumple | Evidencia |
|---|---|---|
| Usabilidad | UI oscura, filtros, atajos visuales, feedback inmediato | Capturas y build |
| Rendimiento | Async, índices, paginación, chunks | 14 tests; dashboard < 300 ms en 728 alertas |
| Confiabilidad | Fallback heurístico, healthchecks, reintentos n8n | Pruebas de triaje degradado |
| Seguridad | JWT, RBAC, bcrypt, CSP, auditoría | Tests de RBAC y cadena |
| Interoperabilidad | API REST + OpenAPI + webhook estándar | `/docs`, contrato |
| Escalabilidad | API sin estado, pool, Docker | N réplicas; particionado futuro |
| Mantenibilidad | Tipado estricto, tests, servicios, docs | `tsc` 0 errores, 14 tests |
| Portabilidad | Docker Compose, variables de entorno | `docker compose up` |

---

## 7.9 Riesgos del stack y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Ollama no soporta tool calling en algún modelo | Triaje degradado | Fallback heurístico + elección de modelo validada |
| n8n cambia su licencia | Coste legal | La lógica crítica está en Python; n8n es reemplazable |
| Recharts pesa 423 kB | Carga inicial del dashboard | Chunk separado y cacheado; lazy load si crece |
| LangChain 1.x introdujo cambios | Ruptura de imports | Versiones pinneadas y tests de contrato |
| PostgreSQL sin HA | Caída del servicio | Backup + réplica; HA en perfil público |
| Dependencia de APIs externas | Enriquecimiento incompleto | `skipped` explícito, caché, proveedores locales |
| Complejidad de credenciales n8n | Fricción de despliegue | Documentado paso a paso; variables de entorno |

---

## 7.10 Política de versiones y actualización

- **Backend:** versiones exactas en `requirements.txt`; actualizar en rama con tests.
- **Frontend:** rangos `^` en `package.json` + `package-lock.json`; CI con `npm ci`.
- **Base de datos:** migraciones Alembic a partir de la v1.1; los cambios de enum se prueban en
  staging.
- **Modelos:** `OLLAMA_MODEL` es configurable; cada cambio se evalúa con el golden set y se registra
  `model`/`prompt_version` en cada triaje.
- **n8n:** exportar el workflow a Git tras cada cambio; importar en staging antes de producción.

---

## 7.11 Conclusión

El stack no busca novedad, sino **adecuación al problema y al equipo**:

- Python/FastAPI/LangChain porque el triaje exige IA, validación y tests.
- PostgreSQL porque las métricas y la auditoría son relacionales e íntegras.
- n8n porque la operación necesita integraciones visibles y reintentos sin desplegar código.
- React/TypeScript porque la consola debe ser rápida, accesible y mantenible.
- Ollama porque la privacidad del incidente no es negociable en PYME y sector público.

El resultado es un sistema de ~10 500 líneas de código (más SQL, workflow y documentación) que se levanta con
`docker compose up`, se opera desde el navegador y deja evidencia verificable de cada acción.
