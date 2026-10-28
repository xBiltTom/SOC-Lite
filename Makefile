.PHONY: help up down logs ps seed schema test test-backend lint build smoke clean

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

clean:
	rm -rf frontend/dist backend/storage/reports/*.pdf backend/storage/reports/*.docx backend/storage/reports/*.xlsx
