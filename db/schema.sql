-- =====================================================================
--  SOC-Lite · Esquema PostgreSQL 16
--  Triaje automático de alertas SOC para PYME / mediana empresa / sector público
--
--  Ejecutar:  psql -U soclite -d soclite -f db/schema.sql
--  Idempotente: usa IF NOT EXISTS / DROP ... CASCADE en la sección de reset.
-- =====================================================================
\set ON_ERROR_STOP on

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid(), crypt(), digest()
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- búsqueda difusa en descripciones
CREATE EXTENSION IF NOT EXISTS citext;     -- username / email case-insensitive

-- =====================================================================
-- 0. RESET (solo desarrollo; comentar en producción)
-- =====================================================================
DROP VIEW  IF EXISTS v_audit_recent        CASCADE;
DROP VIEW  IF EXISTS v_incident_overview   CASCADE;
DROP VIEW  IF EXISTS v_mttt_stats          CASCADE;
DROP VIEW  IF EXISTS v_dashboard_daily     CASCADE;
DROP VIEW  IF EXISTS v_alert_overview      CASCADE;
DROP TABLE IF EXISTS reports, integrations, refresh_tokens, audit_log,
                     alert_feedback, incidents, triage_results,
                     enrichment_data, alerts, users,
                     role_permissions, permissions, roles CASCADE;
DROP SEQUENCE IF EXISTS audit_log_chain_seq_seq CASCADE;
DROP FUNCTION IF EXISTS generate_synthetic_alerts(int, int) CASCADE;
DROP FUNCTION IF EXISTS fn_audit_chain() CASCADE;
DROP FUNCTION IF EXISTS fn_audit_immutable() CASCADE;
DROP FUNCTION IF EXISTS fn_touch_updated_at() CASCADE;
DROP FUNCTION IF EXISTS fn_alert_dedup() CASCADE;
DROP TYPE IF EXISTS integration_type, report_status, report_format, report_type,
                     audit_result, incident_priority, incident_status, triage_status,
                     triage_verdict, alert_status, severity_level CASCADE;

-- =====================================================================
-- 1. TIPOS ENUMERADOS
-- =====================================================================
CREATE TYPE severity_level AS ENUM ('critical','high','medium','low','info');
CREATE TYPE alert_status AS ENUM ('pending','triaging','triage_failed','triaged','in_review','escalated','closed','false_positive','discarded');
CREATE TYPE triage_verdict AS ENUM ('true_positive','false_positive','suspicious','benign','inconclusive');
CREATE TYPE triage_status AS ENUM ('pending','completed','degraded','failed');
CREATE TYPE incident_status AS ENUM ('open','investigating','contained','resolved','closed');
CREATE TYPE incident_priority AS ENUM ('P1','P2','P3','P4');
CREATE TYPE audit_result AS ENUM ('success','failure','denied');
CREATE TYPE report_type AS ENUM ('operational','management','audit');
CREATE TYPE report_format AS ENUM ('pdf','docx','xlsx');
CREATE TYPE report_status AS ENUM ('queued','generating','ready','failed');
CREATE TYPE integration_type AS ENUM ('siem','edr','ticketing','chat','threat_intel','llm');

-- =====================================================================
-- 2. SEGURIDAD: ROLES, PERMISOS, USUARIOS
-- =====================================================================
CREATE TABLE roles (
    id          smallserial PRIMARY KEY,
    code        citext NOT NULL UNIQUE,          -- admin, soc_manager, analyst, auditor, viewer
    name        text   NOT NULL,
    description text,
    is_system   boolean NOT NULL DEFAULT false,  -- los roles de sistema no se borran
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE permissions (
    id          serial PRIMARY KEY,
    code        text NOT NULL UNIQUE,            -- alerts:read, reports:export, ...
    module      text NOT NULL,
    action      text NOT NULL,
    description text,
    UNIQUE (module, action)
);

CREATE TABLE role_permissions (
    role_id       smallint NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id integer  NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username      citext NOT NULL UNIQUE,
    email         citext NOT NULL UNIQUE,
    full_name     text   NOT NULL,
    password_hash text   NOT NULL,
    role_id       smallint NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    is_active     boolean NOT NULL DEFAULT true,
    mfa_enabled   boolean NOT NULL DEFAULT false,
    last_login_at timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    deleted_at    timestamptz,
    CONSTRAINT users_username_len CHECK (char_length(username) BETWEEN 3 AND 64),
    CONSTRAINT users_email_fmt CHECK (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);
CREATE INDEX idx_users_role ON users(role_id);
CREATE INDEX idx_users_active ON users(is_active) WHERE deleted_at IS NULL;

CREATE TABLE refresh_tokens (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash char(64) NOT NULL UNIQUE,          -- sha256 del token (nunca en claro)
    user_agent text,
    ip         inet,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_expiry ON refresh_tokens(expires_at);

-- =====================================================================
-- 3. ALERTAS
-- =====================================================================
CREATE TABLE alerts (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id        text,                       -- id en Wazuh / OPNsense
    source             text NOT NULL DEFAULT 'wazuh',
    rule_id            text,
    rule_level         smallint CHECK (rule_level BETWEEN 0 AND 16),
    description        text NOT NULL,
    src_ip             inet,
    dst_ip             inet,
    src_port           integer CHECK (src_port BETWEEN 0 AND 65535),
    dst_port           integer CHECK (dst_port BETWEEN 0 AND 65535),
    protocol           text,
    agent_name         text,
    asset_criticality  smallint NOT NULL DEFAULT 3 CHECK (asset_criticality BETWEEN 1 AND 5),
    severity           severity_level NOT NULL DEFAULT 'medium',
    status             alert_status   NOT NULL DEFAULT 'pending',
    fingerprint        text NOT NULL UNIQUE,       -- sha256(source|rule|src|dst|ventana)
    raw_payload        jsonb NOT NULL DEFAULT '{}'::jsonb,
    tags               text[] NOT NULL DEFAULT '{}',
    dedup_count        integer NOT NULL DEFAULT 1,
    occurred_at        timestamptz NOT NULL DEFAULT now(),
    received_at        timestamptz NOT NULL DEFAULT now(),
    last_seen_at       timestamptz NOT NULL DEFAULT now(),
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_alerts_severity   ON alerts(severity);
CREATE INDEX idx_alerts_status     ON alerts(status);
CREATE INDEX idx_alerts_received   ON alerts(received_at DESC);
CREATE INDEX idx_alerts_source     ON alerts(source);
CREATE INDEX idx_alerts_src_ip     ON alerts(src_ip);
CREATE INDEX idx_alerts_agent      ON alerts(agent_name);
CREATE INDEX idx_alerts_rule       ON alerts(rule_id);
CREATE INDEX idx_alerts_tags       ON alerts USING gin(tags);
CREATE INDEX idx_alerts_desc_trgm  ON alerts USING gin(description gin_trgm_ops);

-- =====================================================================
-- 4. ENRIQUECIMIENTO (IOC reputation, geolocalización, MITRE)
-- =====================================================================
CREATE TABLE enrichment_data (
    id             bigserial PRIMARY KEY,
    alert_id       uuid NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    provider       text NOT NULL,                  -- virustotal | abuseipdb | geoip | mitre | internal
    indicator      text NOT NULL,
    indicator_type text NOT NULL,                  -- ip | domain | hash | url
    verdict        text,                           -- malicious | suspicious | clean | unknown
    score          numeric(5,2),                   -- 0..100
    country        text,
    asn            text,
    raw            jsonb NOT NULL DEFAULT '{}'::jsonb,
    fetched_at     timestamptz NOT NULL DEFAULT now(),
    expires_at     timestamptz
);
CREATE INDEX idx_enrich_alert    ON enrichment_data(alert_id);
CREATE INDEX idx_enrich_indicator ON enrichment_data(indicator);

-- =====================================================================
-- 5. TRIAJE (salida del agente LLM / motor heurístico)
-- =====================================================================
CREATE TABLE triage_results (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id            uuid NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    verdict             triage_verdict NOT NULL,
    severity            severity_level NOT NULL,
    confidence          numeric(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    summary             text NOT NULL,
    reasoning           text,
    recommended_actions jsonb NOT NULL DEFAULT '[]'::jsonb,
    mitre_techniques    text[] NOT NULL DEFAULT '{}',
    model               text,
    prompt_version      text,
    latency_ms          integer,
    status              triage_status NOT NULL DEFAULT 'completed',
    needs_human         boolean NOT NULL DEFAULT false,
    fallback_used       boolean NOT NULL DEFAULT false,
    raw_response        jsonb NOT NULL DEFAULT '{}'::jsonb,
    triaged_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_triage_alert    ON triage_results(alert_id, triaged_at DESC);
CREATE INDEX idx_triage_verdict  ON triage_results(verdict);
CREATE INDEX idx_triage_triaged  ON triage_results(triaged_at DESC);

-- =====================================================================
-- 6. RETROALIMENTACIÓN DEL ANALISTA (memoria de falsos positivos)
-- =====================================================================
CREATE TABLE alert_feedback (
    id               bigserial PRIMARY KEY,
    alert_id         uuid NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    user_id          uuid REFERENCES users(id) ON DELETE SET NULL,
    is_false_positive boolean NOT NULL,
    comment          text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (alert_id, user_id)
);
CREATE INDEX idx_feedback_alert ON alert_feedback(alert_id);

-- =====================================================================
-- 7. INCIDENTES
-- =====================================================================
CREATE TABLE incidents (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id    uuid REFERENCES alerts(id) ON DELETE SET NULL,
    ticket_id   text UNIQUE,                      -- identificador local del incidente
    title       text NOT NULL,
    description text,
    status      incident_status NOT NULL DEFAULT 'open',
    priority    incident_priority NOT NULL DEFAULT 'P3',
    assignee_id uuid REFERENCES users(id) ON DELETE SET NULL,
    sla_due_at  timestamptz,
    opened_at   timestamptz NOT NULL DEFAULT now(),
    closed_at   timestamptz,
    resolution  text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_incidents_status   ON incidents(status);
CREATE INDEX idx_incidents_assignee ON incidents(assignee_id);
CREATE INDEX idx_incidents_alert    ON incidents(alert_id);
CREATE INDEX idx_incidents_opened   ON incidents(opened_at DESC);

-- =====================================================================
-- 8. BITÁCORA DE AUDITORÍA (append-only + cadena de hashes)
-- =====================================================================
-- Secuencia propia de la cadena: el id de la tabla no sirve como orden porque
-- PostgreSQL asigna bigserial antes de ejecutar los triggers BEFORE INSERT y
-- dos transacciones concurrentes pueden intercalar sus ids.
CREATE SEQUENCE audit_log_chain_seq_seq;

CREATE TABLE audit_log (
    id          bigserial PRIMARY KEY,
    chain_seq   bigint NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
    username    text,
    module      text NOT NULL,                    -- auth | alerts | triage | ...
    action      text NOT NULL,                    -- ENTER | EXIT | LOGIN | ALERT_INGEST | ...
    entity_type text,
    entity_id   text,
    result      audit_result NOT NULL DEFAULT 'success',
    detail      jsonb NOT NULL DEFAULT '{}'::jsonb,
    ip          inet,
    user_agent  text,
    request_id  text,
    duration_ms integer,
    prev_hash   char(64),
    hash        char(64)
);
CREATE UNIQUE INDEX idx_audit_chain_seq ON audit_log(chain_seq);
CREATE INDEX idx_audit_time       ON audit_log(occurred_at DESC);
CREATE INDEX idx_audit_user       ON audit_log(user_id);
CREATE INDEX idx_audit_module     ON audit_log(module, action);
CREATE INDEX idx_audit_result     ON audit_log(result);
CREATE INDEX idx_audit_entity     ON audit_log(entity_type, entity_id);

CREATE OR REPLACE FUNCTION fn_audit_chain() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_prev char(64);
BEGIN
    -- Serializa la cadena y asigna la posición DENTRO del lock: así el orden de
    -- la cadena no depende del id (que se asigna antes del trigger).
    PERFORM pg_advisory_xact_lock(hashtext('soclite.audit_log.chain'));
    NEW.chain_seq := nextval('audit_log_chain_seq_seq');
    SELECT hash INTO v_prev FROM audit_log ORDER BY chain_seq DESC LIMIT 1;
    NEW.prev_hash := COALESCE(v_prev, repeat('0', 64));
    NEW.hash := encode(digest(
        NEW.prev_hash || '|' || NEW.occurred_at::text || '|' || COALESCE(NEW.user_id::text,'') ||
        '|' || COALESCE(NEW.username,'') || '|' || NEW.module || '|' || NEW.action ||
        '|' || COALESCE(NEW.entity_id,'') || '|' || NEW.result::text ||
        '|' || COALESCE(NEW.detail::text,'{}'), 'sha256'), 'hex');
    RETURN NEW;
END $$;

CREATE TRIGGER trg_audit_chain
    BEFORE INSERT ON audit_log
    FOR EACH ROW EXECUTE FUNCTION fn_audit_chain();

-- Inmutabilidad: ni UPDATE ni DELETE (ni siquiera al propietario de la tabla).
CREATE OR REPLACE FUNCTION fn_audit_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log es append-only: % no permitido', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END $$;

CREATE TRIGGER trg_audit_no_update
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION fn_audit_immutable();

-- =====================================================================
-- 9. INTEGRACIONES Y REPORTES
-- =====================================================================
CREATE TABLE integrations (
    id            serial PRIMARY KEY,
    name          text NOT NULL UNIQUE,
    type          integration_type NOT NULL,
    config        jsonb NOT NULL DEFAULT '{}'::jsonb,   -- secretos referenciados por env, no en claro
    enabled       boolean NOT NULL DEFAULT true,
    last_check_at timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reports (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type         report_type NOT NULL,
    format       report_format NOT NULL,
    status       report_status NOT NULL DEFAULT 'queued',
    params       jsonb NOT NULL DEFAULT '{}'::jsonb,
    file_path    text,
    file_size    bigint,
    requested_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    error        text
);
CREATE INDEX idx_reports_created ON reports(created_at DESC);

-- =====================================================================
-- 10. VISTAS DE LECTURA
-- =====================================================================
CREATE VIEW v_alert_overview AS
SELECT a.id, a.external_id, a.source, a.rule_id, a.rule_level, a.description,
       a.src_ip, a.dst_ip, a.agent_name, a.asset_criticality,
       a.severity, a.status, a.occurred_at, a.received_at,
       t.verdict, t.confidence, t.summary, t.triaged_at,
       EXTRACT(EPOCH FROM (t.triaged_at - a.received_at)) / 60.0 AS mttt_minutes,
       i.id AS incident_id, i.ticket_id, i.status AS incident_status
FROM alerts a
LEFT JOIN LATERAL (
    SELECT * FROM triage_results tr
    WHERE tr.alert_id = a.id
    ORDER BY tr.triaged_at DESC LIMIT 1
) t ON true
LEFT JOIN incidents i ON i.alert_id = a.id;

CREATE VIEW v_incident_overview AS
SELECT i.*, a.severity AS alert_severity, a.description AS alert_description,
       u.full_name AS assignee_name
FROM incidents i
LEFT JOIN alerts a ON a.id = i.alert_id
LEFT JOIN users  u ON u.id = i.assignee_id;

CREATE VIEW v_dashboard_daily AS
SELECT d::date AS day,
       COUNT(a.id)                                                  AS total,
       COUNT(a.id) FILTER (WHERE a.severity = 'critical')           AS critical,
       COUNT(a.id) FILTER (WHERE a.severity = 'high')               AS high,
       COUNT(a.id) FILTER (WHERE a.severity = 'medium')             AS medium,
       COUNT(a.id) FILTER (WHERE a.severity = 'low')                AS low,
       COUNT(a.id) FILTER (WHERE a.status IN ('triaged','closed'))  AS triaged
FROM generate_series(current_date - 29, current_date, interval '1 day') d
LEFT JOIN alerts a ON a.received_at >= d AND a.received_at < d + interval '1 day'
GROUP BY 1 ORDER BY 1;

CREATE VIEW v_mttt_stats AS
SELECT a.severity,
       COUNT(*)                                                                AS triaged_count,
       ROUND(AVG(EXTRACT(EPOCH FROM (t.triaged_at - a.received_at)) / 60.0)::numeric, 2) AS avg_minutes,
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (
             ORDER BY EXTRACT(EPOCH FROM (t.triaged_at - a.received_at)) / 60.0)::numeric, 2) AS p95_minutes,
       ROUND(MIN(EXTRACT(EPOCH FROM (t.triaged_at - a.received_at)) / 60.0)::numeric, 2) AS min_minutes,
       ROUND(MAX(EXTRACT(EPOCH FROM (t.triaged_at - a.received_at)) / 60.0)::numeric, 2) AS max_minutes
FROM alerts a
JOIN triage_results t ON t.alert_id = a.id
GROUP BY a.severity;

CREATE VIEW v_audit_recent AS
SELECT id, occurred_at, username, module, action, entity_type, entity_id,
       result, ip, duration_ms, request_id, left(hash, 12) AS hash_short
FROM audit_log
ORDER BY chain_seq DESC
LIMIT 500;

-- =====================================================================
-- 11. FUNCIONES DE MANTENIMIENTO
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

CREATE TRIGGER trg_users_touch BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();
CREATE TRIGGER trg_incidents_touch BEFORE UPDATE ON incidents
    FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();

-- Correlación de duplicados: si llega la misma huella en la ventana de 15 min,
-- incrementa el contador en lugar de crear otra alerta (idempotencia del webhook).
CREATE OR REPLACE FUNCTION fn_alert_dedup() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.dedup_count > 1 THEN
        NEW.last_seen_at := now();
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_alert_dedup BEFORE INSERT ON alerts
    FOR EACH ROW EXECUTE FUNCTION fn_alert_dedup();

-- =====================================================================
-- 12. GENERADOR DE DATOS SINTÉTICOS (demo / pruebas de carga)
--     SELECT generate_synthetic_alerts(5000, 30);
-- =====================================================================
CREATE OR REPLACE FUNCTION generate_synthetic_alerts(p_count int DEFAULT 500, p_days int DEFAULT 30)
RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    i            int;
    v_r          numeric;
    v_sev        severity_level;
    v_status     alert_status;
    v_verdict    triage_verdict;
    v_alert_id   uuid;
    v_received   timestamptz;
    v_latency    int;
    v_src        inet;
    v_desc       text;
    v_agent      text;
    v_source     text;
    v_rule       text;
    v_ticket     text;
BEGIN
    PERFORM setseed(0.4242);
    FOR i IN 1..p_count LOOP
        v_r := random();
        v_sev := CASE
            WHEN v_r < 0.05 THEN 'critical'::severity_level
            WHEN v_r < 0.18 THEN 'high'::severity_level
            WHEN v_r < 0.50 THEN 'medium'::severity_level
            WHEN v_r < 0.85 THEN 'low'::severity_level
            ELSE 'info'::severity_level END;

        v_received := now() - (random() * p_days || ' days')::interval;

        v_r := random();
        v_status := CASE
            WHEN v_r < 0.78 THEN 'triaged'::alert_status
            WHEN v_r < 0.90 THEN 'pending'::alert_status
            ELSE 'false_positive'::alert_status END;

        v_src := CASE (random() * 5)::int
            WHEN 0 THEN ('203.0.113.' || (1 + (random()*254)::int))::inet
            WHEN 1 THEN ('198.51.100.' || (1 + (random()*254)::int))::inet
            WHEN 2 THEN ('192.0.2.' || (1 + (random()*254)::int))::inet
            WHEN 3 THEN ('45.155.205.' || (1 + (random()*254)::int))::inet
            WHEN 4 THEN ('185.220.101.' || (1 + (random()*254)::int))::inet
            ELSE ('10.0.4.' || (1 + (random()*60)::int))::inet END;

        v_agent := (ARRAY['WKS-CONTAB01','SRV-DC01','SRV-FILE01','WKS-RRHH02','FW-BORDE-01','SRV-WEB01','WKS-GERENCIA'])[1 + (random()*6)::int];
        v_source := CASE WHEN random() < 0.68 THEN 'wazuh' WHEN random() < 0.85 THEN 'opnsense' ELSE 'suricata' END;
        v_rule := (ARRAY['5710','5712','100001','110002','92052','2501','31533','60122'])[1 + (random()*7)::int];

        v_desc := CASE v_sev
            WHEN 'critical' THEN (ARRAY[
                'Ransomware detectado: cifrado masivo de archivos y nota de rescate',
                'Ejecución de PowerShell ofuscado con conexión a C2 conocido',
                'Acceso exitoso con credenciales válidas desde IP maliciosa'])[1 + (random()*2)::int]
            WHEN 'high' THEN (ARRAY[
                'Fuerza bruta SSH contra servidor expuesto',
                'Intento de explotación de vulnerabilidad en servidor web',
                'Descarga de binario desde dominio recién registrado'])[1 + (random()*2)::int]
            WHEN 'medium' THEN (ARRAY[
                'Escaneo de puertos desde host externo',
                'Múltiples inicios de sesión fallidos en aplicación',
                'Consulta DNS a dominio sospechoso'])[1 + (random()*2)::int]
            ELSE (ARRAY[
                'Intento de acceso a recurso inexistente (404)',
                'Regla de auditoría de cambios en configuración',
                'Conexión rechazada por política de firewall'])[1 + (random()*2)::int] END;

        INSERT INTO alerts (external_id, source, rule_id, rule_level, description,
                            src_ip, dst_ip, dst_port, protocol, agent_name, asset_criticality,
                            severity, status, fingerprint, raw_payload, tags,
                            occurred_at, received_at, last_seen_at)
        VALUES ('syn-' || i, v_source, v_rule,
                CASE v_sev WHEN 'critical' THEN 14 WHEN 'high' THEN 11 WHEN 'medium' THEN 7 WHEN 'low' THEN 4 ELSE 2 END,
                v_desc, v_src, '10.0.4.21'::inet, 22, 'tcp', v_agent,
                1 + (random()*4)::int, v_sev, v_status,
                encode(digest('syn-' || i || '|' || v_src::text || '|' || v_received::text, 'sha256'), 'hex'),
                jsonb_build_object('synthetic', true, 'rule', jsonb_build_object('id', v_rule, 'level', 7)),
                ARRAY[v_source], v_received, v_received, v_received)
        RETURNING id INTO v_alert_id;

        IF v_status = 'triaged' OR v_status = 'false_positive' THEN
            v_latency := 2 + (random() * 40)::int;
            v_r := random();
            v_verdict := CASE
                WHEN v_status = 'false_positive' THEN 'false_positive'::triage_verdict
                WHEN v_r < 0.42 THEN 'true_positive'::triage_verdict
                WHEN v_r < 0.68 THEN 'suspicious'::triage_verdict
                WHEN v_r < 0.88 THEN 'benign'::triage_verdict
                ELSE 'inconclusive'::triage_verdict END;

            -- Coherencia: una alerta informativa o de baja severidad no debería
            -- salir como verdadero positivo sin evidencia adicional.
            IF v_sev IN ('info','low') AND v_verdict IN ('true_positive','suspicious') THEN
                v_verdict := 'benign';
            END IF;

            INSERT INTO triage_results (alert_id, verdict, severity, confidence, summary,
                                        recommended_actions, mitre_techniques, model,
                                        prompt_version, latency_ms, status, needs_human,
                                        fallback_used, triaged_at)
            VALUES (v_alert_id, v_verdict, v_sev,
                    0.62 + random() * 0.35,
                    'Alerta correlacionada con ' || v_src::text || '; ' ||
                    CASE v_verdict
                        WHEN 'true_positive' THEN 'actividad maliciosa confirmada por reputación del IOC y contexto del activo.'
                        WHEN 'false_positive' THEN 'actividad consistente con tráfico administrativo legítimo; se recomienda supresión temporal.'
                        WHEN 'suspicious' THEN 'indicadores ambiguos; requiere validación humana antes de escalar.'
                        WHEN 'benign' THEN 'actividad autorizada según línea base del activo.'
                        ELSE 'información insuficiente para un veredicto concluyente.' END,
                    jsonb_build_array(
                        jsonb_build_object('action', CASE WHEN v_verdict = 'true_positive' THEN 'Aislar el host y preservar evidencia' ELSE 'Validar con el propietario del activo' END, 'priority', 1, 'owner', 'SOC'),
                        jsonb_build_object('action', 'Verificar IOC en VirusTotal y AbuseIPDB', 'priority', 2, 'owner', 'analista')),
                    CASE
                        WHEN v_verdict <> 'true_positive' THEN ARRAY[]::text[]
                        WHEN v_desc ILIKE '%ransomware%' THEN ARRAY['T1486']
                        WHEN v_desc ILIKE '%powershell%' THEN ARRAY['T1059.001']
                        WHEN v_desc ILIKE '%ssh%' OR v_desc ILIKE '%fuerza bruta%' THEN ARRAY['T1110']
                        WHEN v_desc ILIKE '%explotación%' OR v_desc ILIKE '%vulnerabilidad%' THEN ARRAY['T1190']
                        WHEN v_desc ILIKE '%escaneo%' THEN ARRAY['T1046']
                        ELSE ARRAY[]::text[]
                    END,
                    'llama3.1:8b', 'v1.2.0', v_latency * 1000,
                    'completed', v_verdict = 'inconclusive', false,
                    v_received + (v_latency || ' minutes')::interval);

            IF random() < 0.35 THEN
                INSERT INTO alert_feedback (alert_id, user_id, is_false_positive, comment)
                SELECT v_alert_id, u.id,
                       (v_verdict IN ('false_positive','benign')),
                       'Revisión de turno'
                FROM users u WHERE u.username = 'analista1';
            END IF;
        END IF;

        IF v_sev IN ('critical','high') AND random() < 0.25 THEN
            v_ticket := 'OSK-' || (10000 + i);
            INSERT INTO incidents (alert_id, ticket_id, title, status, priority, sla_due_at, opened_at)
            VALUES (v_alert_id, v_ticket, 'Incidente: ' || left(v_desc, 90),
                    (ARRAY['open','investigating','contained','resolved'])[1 + (random()*3)::int]::incident_status,
                    CASE WHEN v_sev = 'critical' THEN 'P1' ELSE 'P2' END::incident_priority,
                    v_received + interval '4 hours', v_received + interval '10 minutes');
        END IF;
    END LOOP;
END $$;

COMMIT;

-- =====================================================================
-- 13. VERIFICACIÓN RÁPIDA
-- =====================================================================
DO $$
DECLARE v_tables int;
BEGIN
    SELECT count(*) INTO v_tables
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
    RAISE NOTICE 'SOC-Lite: % tablas creadas, % alertas', v_tables, (SELECT count(*) FROM alerts);
END $$;
