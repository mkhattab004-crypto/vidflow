.PHONY: help up down build dev-backend dev-frontend migrate seed logs clean

help:
	@echo ""
	@echo "  VidFlow — Developer Commands"
	@echo "  ──────────────────────────────────────────────"
	@echo "  make up            Start all services (Docker Compose)"
	@echo "  make down          Stop all services"
	@echo "  make build         Rebuild images"
	@echo "  make dev-backend   Run backend locally (no Docker)"
	@echo "  make dev-frontend  Run frontend dev server (Vite)"
	@echo "  make migrate       Run Alembic DB migrations"
	@echo "  make seed          Seed default channels"
	@echo "  make logs          Tail all container logs"
	@echo "  make clean         Remove all containers and volumes"
	@echo ""

# ── Docker ───────────────────────────────────────────────────────────────────

up:
	docker-compose up -d
	@echo "✓  VidFlow running"
	@echo "   Frontend  → http://localhost"
	@echo "   API       → http://localhost:8000"
	@echo "   API Docs  → http://localhost:8000/docs"

down:
	docker-compose down

build:
	docker-compose build --no-cache

logs:
	docker-compose logs -f

clean:
	docker-compose down -v --remove-orphans

# ── Local development (no Docker) ───────────────────────────────────────────

dev-backend:
	@echo "Starting backend with hot reload..."
	cd backend && \
	  python -m venv .venv 2>/dev/null || true && \
	  .venv/bin/pip install -q -r requirements.txt && \
	  .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	@echo "Starting Vite dev server..."
	cd frontend && npm install && npm run dev

# ── Database ─────────────────────────────────────────────────────────────────

migrate:
	@echo "Running Alembic migrations..."
	cd backend && \
	  .venv/bin/alembic upgrade head || \
	  docker-compose exec backend alembic upgrade head

seed:
	@echo "Seeding default channels..."
	cd backend && \
	  .venv/bin/python -m app.seed || \
	  docker-compose exec backend python -m app.seed

# ── Build for production ──────────────────────────────────────────────────────

build-frontend:
	cd frontend && npm ci && npm run build

build-backend:
	docker build -t vidflow-backend ./backend

# ── Railway helpers ───────────────────────────────────────────────────────────

railway-deploy:
	railway up

railway-logs:
	railway logs
