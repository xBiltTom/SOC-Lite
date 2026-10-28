-- Aplicar una vez a instalaciones existentes; no modifica otros roles.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE r.code = 'analyst' AND p.code = 'incidents:close'
ON CONFLICT DO NOTHING;
