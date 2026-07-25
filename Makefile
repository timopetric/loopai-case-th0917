.PHONY: backend frontend dev test lint check build run push

backend:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) -j2 backend frontend

test:
	uv run pytest

lint:
	uv run ruff check .
	cd frontend && npx tsc --noEmit

check: lint test

build:
	docker build -t timopetric/caseth0917:latest .

run:
	docker run --rm -it -p 8000:8000 --env-file .env -e PORT=8000 timopetric/caseth0917:latest

push:
	docker push timopetric/caseth0917:latest
