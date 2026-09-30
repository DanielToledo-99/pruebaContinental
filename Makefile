.PHONY: up down test lint format frontend-check test-postgres

up:
	docker compose up --build -d --wait

down:
	docker compose down

test:
	docker build --target test -t document-ai-backend-test ./backend
	docker run --rm document-ai-backend-test pytest -q

lint:
	docker build --target test -t document-ai-backend-test ./backend
	docker run --rm document-ai-backend-test sh -c 'ruff check . && black --check . && isort --check-only . && mypy'

format:
	cd backend && isort . && black .
	cd frontend && npx prettier --write src e2e '*.ts' '*.js'

frontend-check:
	cd frontend && npm ci && npm run build && npm run lint

test-postgres:
	docker compose up -d --wait db
	docker compose exec -T db sh -c 'psql -U "$$POSTGRES_USER" -tAc "SELECT 1 FROM pg_database WHERE datname = '\''document_ai_test'\''" | grep -q 1 || createdb -U "$$POSTGRES_USER" document_ai_test'
	docker build --target test -t document-ai-backend-test ./backend
	docker run --rm --network document-ai_default --env-file .env -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/document_ai_test document-ai-backend-test alembic upgrade head
	docker run --rm --network document-ai_default -e TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/document_ai_test document-ai-backend-test pytest -q
