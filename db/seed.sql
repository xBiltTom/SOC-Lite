-- =====================================================================
--  SOC-Lite · Datos semilla
--  Ejecutar después de schema.sql:
--    psql -U soclite -d soclite -f db/seed.sql
--  Contraseñas de demostración (cambiar en producción):
--    admin / Admin123!        gerente / Gerente123!
--    analista1 / Analista123! analista2 / Analista123!
--    auditor / Auditor123!    visor / Visor123!
-- =====================================================================
\set ON_ERROR_STOP on
BEGIN;

-- ---------------------------------------------------------------------
-- 1. ROLES
-- ---------------------------------------------------------------------
INSERT INTO roles (code, name, description, is_system) VALUES
 ('admin',       'Administrador',      'Control total del sistema, usuarios, roles y configuración.', true),
 ('soc_manager', 'Jefe de SOC',        'Supervisa operación, SLA, reportes y gestión del equipo.',    true),
 ('analyst',     'Analista SOC',       'Triaje, investigación y respuesta sobre alertas e incidentes.', true),
 ('auditor',     'Auditor',            'Lectura global y acceso completo a la bitácora de auditoría.', true),
 ('viewer',      'Consulta',           'Solo lectura de dashboard, alertas e incidentes.',             true);

-- ---------------------------------------------------------------------
-- 2. PERMISOS (módulo:acción)
-- ---------------------------------------------------------------------
INSERT INTO permissions (code, module, action, description) VALUES
 ('dashboard:read',    'dashboard', 'read',    'Ver dashboard y métricas'),
 ('dashboard:export',  'dashboard', 'export',  'Exportar tablero de métricas'),
 ('alerts:read',       'alerts',    'read',    'Ver alertas y su detalle'),
 ('alerts:create',     'alerts',    'create',  'Registrar o ingerir alertas'),
 ('alerts:update',     'alerts',    'update',  'Cambiar estado y asignación de alertas'),
 ('alerts:delete',     'alerts',    'delete',  'Descartar alertas'),
 ('alerts:export',     'alerts',    'export',  'Exportar listado de alertas'),
 ('triage:read',       'triage',    'read',    'Ver resultados de triaje'),
 ('triage:run',        'triage',    'run',     'Ejecutar triaje automático o manual'),
 ('triage:feedback',   'triage',    'feedback','Registrar falso positivo / validación'),
 ('incidents:read',    'incidents', 'read',    'Ver incidentes'),
 ('incidents:create',  'incidents', 'create',  'Crear incidentes y tickets'),
 ('incidents:update',  'incidents', 'update',  'Actualizar investigación y estado'),
 ('incidents:close',   'incidents', 'close',   'Cerrar incidentes'),
 ('incidents:export',  'incidents', 'export',  'Exportar incidentes'),
 ('users:read',        'users',     'read',    'Ver usuarios'),
 ('users:create',      'users',     'create',  'Crear usuarios'),
 ('users:update',      'users',     'update',  'Editar usuarios y asignar rol'),
 ('users:delete',      'users',     'delete',  'Desactivar usuarios'),
 ('roles:read',        'roles',     'read',    'Ver roles y permisos'),
 ('roles:update',      'roles',     'update',  'Modificar la matriz de permisos'),
 ('audit:read',        'audit',     'read',    'Consultar bitácora de auditoría'),
 ('audit:export',      'audit',     'export',  'Exportar bitácora'),
 ('reports:read',      'reports',   'read',    'Ver reportes generados'),
 ('reports:create',    'reports',   'create',  'Generar reportes'),
 ('reports:export',    'reports',   'export',  'Descargar reportes en PDF/Word/Excel');

-- ---------------------------------------------------------------------
-- 3. MATRIZ ROL-PERMISO
-- ---------------------------------------------------------------------
-- admin: todos
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p WHERE r.code = 'admin';

-- soc_manager: operación completa salvo administración de usuarios/roles
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p
  ON p.module IN ('dashboard','alerts','triage','incidents','reports','audit')
WHERE r.code = 'soc_manager';
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code IN ('users:read','roles:read')
WHERE r.code = 'soc_manager';

-- analyst
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY (ARRAY[
 'dashboard:read','alerts:read','alerts:create','alerts:update','alerts:export',
 'triage:read','triage:run','triage:feedback',
 'incidents:read','incidents:create','incidents:update','incidents:close',
 'reports:read','reports:create'])
WHERE r.code = 'analyst';

-- auditor
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY (ARRAY[
 'dashboard:read','alerts:read','alerts:export','triage:read','incidents:read',
 'audit:read','audit:export','reports:read','reports:create','reports:export'])
WHERE r.code = 'auditor';

-- viewer
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY (ARRAY[
 'dashboard:read','alerts:read','incidents:read','reports:read'])
WHERE r.code = 'viewer';

-- ---------------------------------------------------------------------
-- 4. USUARIOS
-- ---------------------------------------------------------------------
INSERT INTO users (username, email, full_name, password_hash, role_id, is_active) VALUES
 ('admin',     'admin@soclite.example.com',     'Administrador del Sistema', crypt('Admin123!',     gen_salt('bf', 12)), (SELECT id FROM roles WHERE code='admin'),       true),
 ('gerente',   'gerente@soclite.example.com',   'María Fernanda Rojas',      crypt('Gerente123!',   gen_salt('bf', 12)), (SELECT id FROM roles WHERE code='soc_manager'), true),
 ('analista1', 'analista1@soclite.example.com', 'Carlos Mendoza',            crypt('Analista123!',  gen_salt('bf', 12)), (SELECT id FROM roles WHERE code='analyst'),     true),
 ('analista2', 'analista2@soclite.example.com', 'Lucía Paredes',             crypt('Analista123!',  gen_salt('bf', 12)), (SELECT id FROM roles WHERE code='analyst'),     true),
 ('auditor',   'auditor@soclite.example.com',   'Jorge Salazar',             crypt('Auditor123!',   gen_salt('bf', 12)), (SELECT id FROM roles WHERE code='auditor'),     true),
 ('visor',     'visor@soclite.example.com',     'Dirección General',         crypt('Visor123!',     gen_salt('bf', 12)), (SELECT id FROM roles WHERE code='viewer'),      true);

-- ---------------------------------------------------------------------
-- 5. INTEGRACIONES
-- ---------------------------------------------------------------------
INSERT INTO integrations (name, type, config, enabled, last_check_at) VALUES
 ('Wazuh Manager',   'siem',        '{"endpoint":"https://wazuh.local:55000","webhook":"/api/v1/alerts/ingest"}', true,  now() - interval '3 minutes'),
 ('OPNsense',        'siem',        '{"endpoint":"https://fw.local/api","syslog_port":514}'::jsonb, true, now() - interval '8 minutes'),
 ('VirusTotal',      'threat_intel','{"api_key_env":"VIRUSTOTAL_API_KEY","quota":"free"}', true,  now() - interval '1 hour'),
 ('AbuseIPDB',       'threat_intel','{"api_key_env":"ABUSEIPDB_API_KEY","quota":"free"}',  true,  now() - interval '1 hour'),
 ('osTicket',        'ticketing',   '{"endpoint":"https://osticket.local/api","queue":"SOC"}', true, now() - interval '12 minutes'),
 ('Slack',           'chat',        '{"channel":"#soc-alertas","webhook_env":"SLACK_WEBHOOK_URL"}', true, now() - interval '1 minute'),
 ('LLM compatible con OpenAI', 'llm', '{"config":"LLM_BASE_URL y LLM_MODEL"}', false, NULL);

-- ---------------------------------------------------------------------
-- 6. ALERTAS CURADAS (historias de demostración)
-- ---------------------------------------------------------------------
INSERT INTO alerts (id, external_id, source, rule_id, rule_level, description, src_ip, dst_ip,
                    src_port, dst_port, protocol, agent_name, asset_criticality, severity, status,
                    fingerprint, raw_payload, tags, occurred_at, received_at, last_seen_at)
VALUES
 ('11111111-1111-1111-1111-111111111101','wazuh-9001','wazuh','5710',10,
  'Fuerza bruta SSH: 87 intentos fallidos contra usuario root',
  '203.0.113.44','10.0.4.21',52344,22,'tcp','SRV-WEB01',5,'critical','triaged',
  encode(digest('curated-1','sha256'),'hex'),
  '{"rule":{"id":"5710","level":10,"description":"sshd brute force"},"agent":{"name":"SRV-WEB01"},"data":{"srcip":"203.0.113.44","dstip":"10.0.4.21","dstport":22}}',
  ARRAY['ssh','bruteforce','exposed-service'], now() - interval '2 hours', now() - interval '2 hours', now() - interval '2 hours'),

 ('11111111-1111-1111-1111-111111111102','wazuh-9002','wazuh','100001',14,
  'Ransomware: cifrado masivo de archivos y nota de rescate en servidor de archivos',
  '10.0.4.55','10.0.4.30',49812,445,'tcp','SRV-FILE01',5,'critical','escalated',
  encode(digest('curated-2','sha256'),'hex'),
  '{"rule":{"id":"100001","level":14},"agent":{"name":"SRV-FILE01"},"data":{"file":"*.locked","user":"jperez"}}',
  ARRAY['ransomware','malware','critical-asset'], now() - interval '5 hours', now() - interval '5 hours', now() - interval '5 hours'),

 ('11111111-1111-1111-1111-111111111103','opn-9003','opnsense','92052',6,
  'Escaneo de puertos horizontal desde host externo (1.024 destinos)',
  '198.51.100.23','10.0.0.1',41022,0,'tcp','FW-BORDE-01',4,'low','false_positive',
  encode(digest('curated-3','sha256'),'hex'),
  '{"rule":{"id":"92052","level":6},"interface":"wan","packets":1024}',
  ARRAY['scan','recon'], now() - interval '7 hours', now() - interval '7 hours', now() - interval '7 hours'),

 ('11111111-1111-1111-1111-111111111104','wazuh-9004','wazuh','110002',12,
  'PowerShell ofuscado con conexión a infraestructura C2 conocida',
  '10.0.4.77','185.220.101.9',50888,443,'tcp','WKS-GERENCIA',4,'high','triaged',
  encode(digest('curated-4','sha256'),'hex'),
  '{"rule":{"id":"110002","level":12},"agent":{"name":"WKS-GERENCIA"},"data":{"command":"powershell -enc SQBFAFgA"}}',
  ARRAY['powershell','c2','mitre-T1059'], now() - interval '9 hours', now() - interval '9 hours', now() - interval '9 hours'),

 ('11111111-1111-1111-1111-111111111105','wazuh-9005','wazuh','5710',5,
  'Inicio de sesión fallido para usuario inexistente (1 intento)',
  '10.0.4.12','10.0.4.21',0,22,'tcp','WKS-CONTAB01',2,'medium','false_positive',
  encode(digest('curated-5','sha256'),'hex'),
  '{"rule":{"id":"5710","level":5},"agent":{"name":"WKS-CONTAB01"}}',
  ARRAY['auth','low-signal'], now() - interval '12 hours', now() - interval '12 hours', now() - interval '12 hours'),

 ('11111111-1111-1111-1111-111111111106','wazuh-9006','wazuh','31533',11,
  'Intento de explotación de vulnerabilidad en servidor web (CVE-2024-4577)',
  '45.155.205.12','10.0.4.21',38122,443,'tcp','SRV-WEB01',5,'high','triaged',
  encode(digest('curated-6','sha256'),'hex'),
  '{"rule":{"id":"31533","level":11},"http":{"url":"/cgi-bin/php-cgi.exe?%ADd+allow_url_include"}}',
  ARRAY['web','exploit','cve'], now() - interval '1 day 3 hours', now() - interval '1 day 3 hours', now() - interval '1 day 3 hours'),

 ('11111111-1111-1111-1111-111111111107','wazuh-9007','wazuh','60122',7,
  'Consulta DNS a dominio recién registrado con reputación sospechosa',
  '10.0.4.33','10.0.4.2',53544,53,'udp','WKS-RRHH02',3,'medium','triaged',
  encode(digest('curated-7','sha256'),'hex'),
  '{"rule":{"id":"60122","level":7},"dns":{"query":"update-service-cdn.xyz"}}',
  ARRAY['dns','c2-suspect'], now() - interval '1 day 8 hours', now() - interval '1 day 8 hours', now() - interval '1 day 8 hours'),

 ('11111111-1111-1111-1111-111111111108','opn-9008','opnsense','2501',3,
  'Conexión rechazada por política de firewall (salida no permitida)',
  '10.0.4.90','192.0.2.55',52110,8080,'tcp','FW-BORDE-01',2,'info','closed',
  encode(digest('curated-8','sha256'),'hex'),
  '{"rule":{"id":"2501","level":3},"action":"block"}',
  ARRAY['firewall','policy'], now() - interval '2 days', now() - interval '2 days', now() - interval '2 days');

-- Enriquecimiento de las alertas curadas
INSERT INTO enrichment_data (alert_id, provider, indicator, indicator_type, verdict, score, country, asn, raw) VALUES
 ('11111111-1111-1111-1111-111111111101','virustotal','203.0.113.44','ip','malicious', 92, 'RU','AS49505', '{"malicious":14,"suspicious":2,"harmless":3}'),
 ('11111111-1111-1111-1111-111111111101','abuseipdb','203.0.113.44','ip','malicious', 100,'RU','AS49505', '{"abuseConfidenceScore":100,"totalReports":418}'),
 ('11111111-1111-1111-1111-111111111101','geoip','203.0.113.44','ip','unknown', null,'RU','AS49505', '{"city":"Moscow"}'),
 ('11111111-1111-1111-1111-111111111102','internal','SRV-FILE01','host','malicious', 98,'PE',null, '{"criticality":5,"owner":"Finanzas"}'),
 ('11111111-1111-1111-1111-111111111103','abuseipdb','198.51.100.23','ip','suspicious', 35,'BR','AS28573', '{"abuseConfidenceScore":35,"totalReports":21}'),
 ('11111111-1111-1111-1111-111111111104','virustotal','185.220.101.9','ip','malicious', 88, 'DE','AS205100','{"malicious":9,"suspicious":1}'),
 ('11111111-1111-1111-1111-111111111104','geoip','185.220.101.9','ip','unknown', null,'DE','AS205100','{"city":"Frankfurt"}'),
 ('11111111-1111-1111-1111-111111111106','virustotal','45.155.205.12','ip','malicious', 79, 'NL','AS200000','{"malicious":6}'),
 ('11111111-1111-1111-1111-111111111107','internal','update-service-cdn.xyz','domain','suspicious', 55,null,null,'{"age_days":4,"category":"newly-registered"}');

-- Triajes curados
INSERT INTO triage_results (alert_id, verdict, severity, confidence, summary, reasoning,
                            recommended_actions, mitre_techniques, model, prompt_version,
                            latency_ms, status, needs_human, fallback_used, triaged_at)
VALUES
 ('11111111-1111-1111-1111-111111111101','true_positive','critical',0.96,
  'Fuerza bruta SSH confirmada contra SRV-WEB01 desde 203.0.113.44 (IP con 100% de confianza de abuso y 418 reportes). El servicio SSH está expuesto a Internet y el activo es crítico (5/5).',
  'Se observaron 87 intentos en 6 minutos, patrón T1110. La IP de origen aparece como maliciosa en VirusTotal y AbuseIPDB. No hay evidencia de éxito, pero el volumen y la criticidad justifican contención inmediata.',
  '[{"action":"Bloquear 203.0.113.44 en el firewall perimetral","priority":1,"owner":"SOC"},
    {"action":"Verificar en SRV-WEB01 si hubo login exitoso y revisar ~/.ssh/authorized_keys","priority":1,"owner":"Analista"},
    {"action":"Deshabilitar autenticación por contraseña en SSH y aplicar fail2ban","priority":2,"owner":"Infraestructura"},
    {"action":"Abrir incidente P1 y notificar al responsable del activo","priority":2,"owner":"SOC"}]',
  ARRAY['T1110','T1078'], 'llama3.1:8b', 'v1.2.0', 18400, 'completed', false, false, now() - interval '1 hour 54 minutes'),

 ('11111111-1111-1111-1111-111111111102','true_positive','critical',0.99,
  'Ransomware activo en SRV-FILE01: cifrado masivo con extensión .locked y nota de rescate. Riesgo de propagación a unidades de red compartidas.',
  'La regla 100001 tiene nivel 14 y se correlacionan eventos de creación masiva de archivos y modificación de extensiones. El activo es crítico y pertenece a Finanzas.',
  '[{"action":"Aislar SRV-FILE01 de la red inmediatamente","priority":1,"owner":"SOC"},
    {"action":"Preservar imagen forense y memoria antes de restaurar","priority":1,"owner":"DFIR"},
    {"action":"Verificar integridad de respaldos y ventana de restauración","priority":1,"owner":"Infraestructura"},
    {"action":"Notificar a dirección y evaluar obligación de reporte regulatorio","priority":2,"owner":"CISO"}]',
  ARRAY['T1486','T1490','T1021.002'], 'llama3.1:8b', 'v1.2.0', 22100, 'completed', false, false, now() - interval '4 hours 48 minutes'),

 ('11111111-1111-1111-1111-111111111103','false_positive','low',0.87,
  'Escaneo de puertos desde 198.51.100.23 con reputación moderada. El firewall bloqueó el 100% del tráfico y no se alcanzó ningún servicio.',
  'El origen tiene 35% de confianza de abuso y el análisis de geoip lo ubica en un rango de hosting. Todos los paquetes fueron descartados por la política WAN-IN.',
  '[{"action":"Cerrar como falso positivo y agregar a lista de observación 30 días","priority":3,"owner":"Analista"}]',
  ARRAY['T1046'], 'llama3.1:8b', 'v1.2.0', 9300, 'completed', false, false, now() - interval '6 hours 55 minutes'),

 ('11111111-1111-1111-1111-111111111104','suspicious','high',0.78,
  'PowerShell codificado en WKS-GERENCIA con conexión a 185.220.101.9 (nodo de salida Tor, reputación maliciosa). Posible ejecución de segunda etapa.',
  'El comando usa -enc y el destino figura en listas de C2. No se observó descarga de payload ni persistencia; se requiere validación en el endpoint.',
  '[{"action":"Aislar WKS-GERENCIA y recolectar árbol de procesos","priority":1,"owner":"SOC"},
    {"action":"Analizar el blob PowerShell decodificado","priority":2,"owner":"Analista"},
    {"action":"Bloquear 185.220.101.9 y revisar otros hosts con la misma conexión","priority":2,"owner":"Infraestructura"}]',
  ARRAY['T1059.001','T1071.001'], 'llama3.1:8b', 'v1.2.0', 16700, 'completed', true, false, now() - interval '8 hours 40 minutes'),

 ('11111111-1111-1111-1111-111111111105','false_positive','medium',0.82,
  'Un único intento fallido de autenticación con usuario inexistente desde la red interna. Patrón habitual de un script de monitoreo mal configurado.',
  'No hay repetición ni acceso exitoso; la IP interna pertenece a WKS-CONTAB01 y el evento coincide con la ventana de tareas programadas.',
  '[{"action":"Corregir la credencial del script de monitoreo","priority":3,"owner":"Infraestructura"}]',
  ARRAY[]::text[], 'llama3.1:8b', 'v1.2.0', 7200, 'completed', false, true, now() - interval '11 hours 45 minutes'),

 ('11111111-1111-1111-1111-111111111106','true_positive','high',0.91,
  'Intento de explotación de CVE-2024-4577 contra SRV-WEB01. El payload contiene parámetros de inyección de argumentos PHP y proviene de 45.155.205.12.',
  'La firma coincide con exploits públicos de la CVE. El servidor no tiene el parche aplicado según el inventario, por lo que un intento exitoso es plausible.',
  '[{"action":"Aplicar parche de PHP o mitigación WAF en SRV-WEB01","priority":1,"owner":"Infraestructura"},
    {"action":"Revisar logs de PHP y archivos creados en las últimas 24 h","priority":1,"owner":"Analista"},
    {"action":"Bloquear el IOC y buscar retroactivamente en el SIEM","priority":2,"owner":"SOC"}]',
  ARRAY['T1190'], 'llama3.1:8b', 'v1.2.0', 14300, 'completed', false, false, now() - interval '1 day 2 hours'),

 ('11111111-1111-1111-1111-111111111107','benign','medium',0.74,
  'Consulta DNS a dominio recién registrado sin resolución posterior ni tráfico asociado. Compatible con telemetría de actualización.',
  'El dominio tiene 4 días de antigüedad y no figura como malicioso. El proceso solicitante es el agente de actualizaciones corporativo.',
  '[{"action":"Verificar el certificado del agente de actualizaciones","priority":3,"owner":"Infraestructura"}]',
  ARRAY[]::text[], 'llama3.1:8b', 'v1.2.0', 8100, 'completed', false, false, now() - interval '1 day 7 hours'),

 ('11111111-1111-1111-1111-111111111108','benign','info',0.93,
  'Conexión saliente bloqueada por política. Sin impacto: el destino no está permitido y el usuario fue notificado.',
  'La regla 2501 aplica denegación por defecto. No hay indicadores de compromiso.',
  '[{"action":"Sin acción; cerrar","priority":4,"owner":"Analista"}]',
  ARRAY[]::text[], 'llama3.1:8b', 'v1.2.0', 5100, 'completed', false, false, now() - interval '1 day 20 hours');

-- Incidentes curados
INSERT INTO incidents (alert_id, ticket_id, title, status, priority, assignee_id, sla_due_at, opened_at)
VALUES
 ('11111111-1111-1111-1111-111111111101','OSK-10001','Fuerza bruta SSH sobre SRV-WEB01','investigating','P1',
  (SELECT id FROM users WHERE username='analista1'), now() + interval '2 hours', now() - interval '1 hour 50 minutes'),
 ('11111111-1111-1111-1111-111111111102','OSK-10002','Ransomware en SRV-FILE01 (Finanzas)','contained','P1',
  (SELECT id FROM users WHERE username='analista2'), now() + interval '1 hour', now() - interval '4 hours 45 minutes'),
 ('11111111-1111-1111-1111-111111111104','OSK-10003','Posible C2 en WKS-GERENCIA','open','P2',
  (SELECT id FROM users WHERE username='analista1'), now() + interval '6 hours', now() - interval '8 hours 30 minutes'),
 ('11111111-1111-1111-1111-111111111106','OSK-10004','Explotación CVE-2024-4577 en SRV-WEB01','resolved','P2',
  (SELECT id FROM users WHERE username='analista2'), now() - interval '1 day', now() - interval '1 day 2 hours');

UPDATE incidents SET closed_at = now() - interval '20 hours', resolution = 'Parche aplicado y WAF en modo bloqueo.'
WHERE ticket_id = 'OSK-10004';

-- Feedback
INSERT INTO alert_feedback (alert_id, user_id, is_false_positive, comment) VALUES
 ('11111111-1111-1111-1111-111111111103', (SELECT id FROM users WHERE username='analista1'), true,  'Escaneo bloqueado por firewall; sin impacto.'),
 ('11111111-1111-1111-1111-111111111105', (SELECT id FROM users WHERE username='analista2'), true,  'Script de monitoreo con credencial vencida.'),
 ('11111111-1111-1111-1111-111111111101', (SELECT id FROM users WHERE username='analista1'), false, 'Confirmado: intentos reales, sin éxito.'),
 ('11111111-1111-1111-1111-111111111107', (SELECT id FROM users WHERE username='analista2'), false, 'Tráfico del agente de actualizaciones.');

-- ---------------------------------------------------------------------
-- 7. VOLUMEN SINTÉTICO PARA EL DASHBOARD (480 alertas / 30 días)
-- ---------------------------------------------------------------------
SELECT generate_synthetic_alerts(720, 60);

-- ---------------------------------------------------------------------
-- 8. BITÁCORA INICIAL
-- ---------------------------------------------------------------------
INSERT INTO audit_log (occurred_at, user_id, username, module, action, entity_type, result, detail, ip, request_id)
SELECT now() - interval '6 days', u.id, u.username, 'system', 'SEED_LOAD', 'database', 'success',
       jsonb_build_object('alerts', (SELECT count(*) FROM alerts), 'users', (SELECT count(*) FROM users)),
       '127.0.0.1'::inet, 'seed-0001'
FROM users u WHERE u.username = 'admin';

INSERT INTO audit_log (occurred_at, user_id, username, module, action, entity_type, result, detail, ip, request_id)
SELECT now() - interval '5 days', u.id, u.username, 'auth', 'LOGIN', 'user', 'success',
       jsonb_build_object('method', 'password'), '10.10.1.25'::inet, 'seed-0002'
FROM users u WHERE u.username = 'gerente';

INSERT INTO audit_log (occurred_at, user_id, username, module, action, entity_type, result, detail, ip, request_id)
SELECT now() - interval '4 days', u.id, u.username, 'alerts', 'ALERT_INGEST', 'alert', 'success',
       jsonb_build_object('source', 'wazuh', 'severity', 'critical'), '10.10.1.30'::inet, 'seed-0003'
FROM users u WHERE u.username = 'analista1';

COMMIT;

-- Resumen
SELECT 'roles' AS tabla, count(*) FROM roles
UNION ALL SELECT 'permissions', count(*) FROM permissions
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'alerts', count(*) FROM alerts
UNION ALL SELECT 'triage_results', count(*) FROM triage_results
UNION ALL SELECT 'incidents', count(*) FROM incidents
UNION ALL SELECT 'audit_log', count(*) FROM audit_log;
