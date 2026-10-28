#!/usr/bin/env bash
# Prueba de humo de SOC-Lite: login, dashboard, ingesta, triaje, reporte y auditoría.
# Uso:  API=http://127.0.0.1:8010 bash scripts/smoke_test.sh
set -euo pipefail

API="${API:-http://127.0.0.1:8010}"
SOC_USER="${SOC_USER:-admin}"
SOC_PASS="${SOC_PASS:-Admin123!}"
SOC_INGEST_KEY="${SOC_INGEST_KEY:-dev-ingest-key-change-me}"

json() { python3 -c "import sys,json;d=json.load(sys.stdin);print($1)"; }

echo "1) Health"
curl -fsS "$API/health" | json "d['status']"

echo "2) Login"
TOKEN=$(curl -fsS -X POST "$API/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$SOC_USER\",\"password\":\"$SOC_PASS\"}" | json "d['access_token']")
echo "   token: ${#TOKEN} caracteres"

AUTH=(-H "Authorization: Bearer $TOKEN")

echo "3) Dashboard"
curl -fsS "$API/api/v1/dashboard/summary?days=30" "${AUTH[@]}" \
  | json "f\"alertas={d['totals']['alerts']} mttt={d['mttt']['avg_minutes']} min fp={d['rates']['false_positive']}%\""

echo "4) Ingesta"
MARKER="smoke-$(date +%s)"
ALERT_ID=$(curl -fsS -X POST "$API/api/v1/alerts/ingest" \
  -H "X-Ingest-Key: $SOC_INGEST_KEY" -H 'Content-Type: application/json' \
  -d "{\"id\":\"$MARKER\",\"rule\":{\"id\":\"5710\",\"level\":12,\"description\":\"Fuerza bruta SSH ($MARKER)\"},\"agent\":{\"name\":\"SRV-SMOKE\"},\"data\":{\"srcip\":\"203.0.113.99\",\"dstip\":\"10.0.4.21\",\"dstport\":22}}" \
  | json "d['alert_id']")
echo "   alert_id=$ALERT_ID"

echo "5) Triaje"
curl -fsS -X POST "$API/api/v1/alerts/$ALERT_ID/triage" "${AUTH[@]}" \
  | json "f\"verdict={d['verdict']} severity={d['severity']} fallback={d['fallback_used']}\""

echo "6) Reporte XLSX"
REPORT_ID=$(curl -fsS -X POST "$API/api/v1/reports" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"type":"operational","format":"xlsx"}' | json "d['id']")
echo "   report_id=$REPORT_ID"
curl -fsS "$API/api/v1/reports/$REPORT_ID/download" "${AUTH[@]}" -o /tmp/soc-lite-smoke.xlsx
echo "   descargado: $(stat -c%s /tmp/soc-lite-smoke.xlsx) bytes"

echo "7) Integridad de la bitácora"
curl -fsS "$API/api/v1/audit/verify-chain" "${AUTH[@]}" \
  | json "f\"valid={d['valid']} checked={d['checked']}\""

echo "OK · prueba de humo completada"
