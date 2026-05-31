# ============================================
# Makefile - Common Development Commands
# ============================================
# WHY A MAKEFILE?
# Instead of remembering long commands, you type:
#   make setup    → sets up everything
#   make dev      → starts both servers
#   make test     → runs all tests
#   make migrate  → runs database migrations
#
# Run any command: make <command-name>
# ============================================

.PHONY: setup setup-backend setup-frontend dev dev-backend dev-frontend \
        migrate test lint clean help

# ============================================
# Setup Commands
# ============================================

setup: setup-backend setup-frontend
	@echo "✅ Full setup complete! Run 'make dev' to start."

setup-backend:
	@echo "🐍 Setting up Python backend..."
	cd backend && python -m venv venv
	cd backend && ./venv/bin/pip install --upgrade pip
	cd backend && ./venv/bin/pip install -r requirements.txt
	cd backend && cp -n .env.example .env || true
	@echo "✅ Backend ready. Edit backend/.env with your API keys."

setup-frontend:
	@echo "⚛️  Setting up React frontend..."
	cd frontend && npm install
	cd frontend && cp -n .env.example .env || true
	@echo "✅ Frontend ready."

# ============================================
# Database Commands
# ============================================

db-create:
	@echo "🗄️  Creating PostgreSQL database..."
	createdb ai_job_hunter
	@echo "✅ Database 'ai_job_hunter' created."

migrate:
	@echo "🔄 Running database migrations..."
	cd backend && ./venv/bin/alembic upgrade head
	@echo "✅ Migrations complete."

migrate-create:
	@echo "📝 Creating new migration..."
	cd backend && ./venv/bin/alembic revision --autogenerate -m "$(name)"

migrate-rollback:
	@echo "⏪ Rolling back last migration..."
	cd backend && ./venv/bin/alembic downgrade -1

# ============================================
# Development Servers
# ============================================

dev-backend:
	@echo "🚀 Starting FastAPI backend on http://localhost:8000"
	cd backend && ./venv/bin/uvicorn main:app --reload --port 8000

dev-frontend:
	@echo "⚛️  Starting React frontend on http://localhost:3000"
	cd frontend && npm run dev

# Run both servers simultaneously
dev:
	@echo "🚀 Starting all services..."
	make -j2 dev-backend dev-frontend

# ============================================
# Testing
# ============================================

test:
	@echo "🧪 Running all tests..."
	cd backend && ./venv/bin/pytest tests/ -v

test-watch:
	cd backend && ./venv/bin/pytest tests/ -v --watch

# ============================================
# Code Quality
# ============================================

lint:
	cd backend && ./venv/bin/ruff check .
	cd frontend && npm run lint

format:
	cd backend && ./venv/bin/black .
	cd backend && ./venv/bin/ruff check --fix .

# ============================================
# Utilities
# ============================================

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

help:
	@echo ""
	@echo "🎯 AI Job Hunter - Available Commands"
	@echo "======================================"
	@echo "make setup          - Install all dependencies"
	@echo "make db-create      - Create PostgreSQL database"
	@echo "make migrate        - Run database migrations"
	@echo "make dev            - Start backend + frontend"
	@echo "make dev-backend    - Start FastAPI only"
	@echo "make dev-frontend   - Start React only"
	@echo "make test           - Run all tests"
	@echo "make lint           - Check code quality"
	@echo "make clean          - Remove cache files"
	@echo ""
