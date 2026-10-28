.PHONY: help up down logs ps seed schema test test-backend lint build smoke clean n8n-import demo-ssh simulator-start simulator-stop

help:
	@echo "SOC-Lite · comandos"
	@echo "  make up        Levanta el stack (db, api, triaje, web, n8n)"
	@echo "  make down      Detiene el stack"
	@echo "  make logs      Sigue logs de los servicios"
	@echo "  make schema    Aplica schema.sql a la base local (5439)"
	@echo "  make seed      Carga datos semilla"
	@echo "  make test      Ejecuta pruebas del backend"
	@echo "  make build     Compila el frontend"
	@echo "  make smoke     Prueba de humo HTTP contra la API local"
	@echo "  make n8n-import Importa el workflow en n8n (crear antes la cuenta)"
	@echo "  make demo-ssh  Envía una alerta SSH simulada por n8n"
	@echo "  make simulator-start / simulator-stop  Inicia / detiene el simulador"
	@echo "  make clean     Elimina artefactos locales (no volúmenes)"

up:
	docker compose up -d --build
	@echo "Frontend: http://localhost:8090 · API: http://localhost:8010/docs · n8n: http://localhost:5679"

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

schema:
	psql -h 127.0.0.1 -p 5439 -U soclite -d soclite -v ON_ERROR_STOP=1 -f db/schema.sql

seed:
	psql -h 127.0.0.1 -p 5439 -U soclite -d soclite -v ON_ERROR_STOP=1 -f db/seed.sql

test:
	cd backend && .venv/bin/python -m pytest -q

build:
	cd frontend && npm run build

smoke:
	bash scripts/smoke_test.sh

n8n-import:
	docker compose exec -T -u node n8n n8n import:workflow --input=/workflows/soc_lite_triage_workflow.json
	@echo "Workflow importado. Actualiza la página de n8n para verlo."

demo-ssh:
	python3 scripts/simulate_bruteforce.py

simulator-start:
	docker compose --profile simulation up -d --build simulator

simulator-stop:
	docker compose --profile simulation stop simulator

clean:
	rm -rf frontend/dist backend/storage/reports/*.pdf backend/storage/reports/*.docx backend/storage/reports/*.xlsx
