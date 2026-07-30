.PHONY: up seed test test-backend test-frontend build frontend-install backend-install

VENV=.venv/bin
export PYTHONPATH := $(CURDIR)

up: build
	$(VENV)/uvicorn backend.app.main:app --host 127.0.0.1 --port 8100

build: frontend-install
	cd frontend && npm run build

frontend-install:
	cd frontend && npm install

backend-install:
	python3 -m venv .venv
	$(VENV)/pip install -U pip
	$(VENV)/pip install -r backend/requirements.txt

seed:
	$(VENV)/python -m backend.app.seed_cli

test-backend:
	$(VENV)/pytest -q backend/tests

test-frontend: frontend-install
	cd frontend && npm test

test: test-backend test-frontend
