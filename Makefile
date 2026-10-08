.DEFAULT_GOAL := help

PYTHON ?= python3
VENV := .venv
PY := $(VENV)/bin/python
COMPOSE := docker compose --env-file .env -f infra/compose.local.yaml

.PHONY: help setup data quality db-up db-down load analytics ml monitor mlflow-ui test run-api

help:
	@echo "setup → data → db-up → load → analytics → ml → test → run-api"

setup:
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r api/requirements.txt

data:
	$(PY) pipeline/generate_demo_data.py

quality:
	$(PY) pipeline/quality_checks.py

analytics: load
	set -a; . ./.env; set +a; $(PY) pipeline/build_analytics.py

ml: analytics
	set -a; . ./.env; set +a; $(PY) ml/churn_model.py
	set -a; . ./.env; set +a; $(PY) ml/demand_forecast.py
	$(MAKE) monitor

monitor:
	$(PY) ml/model_monitoring.py

mlflow-ui:
	$(VENV)/bin/mlflow ui --backend-store-uri sqlite:///data/mlflow.db --host 127.0.0.1 --port 5000

db-up:
	$(COMPOSE) up -d --wait

db-down:
	$(COMPOSE) down

load: quality
	set -a; . ./.env; set +a; $(PY) pipeline/load_demo_data.py

test:
	$(PY) -m pytest api/tests -q

run-api:
	set -a; . ./.env; set +a; $(PY) -m uvicorn api.app.main:app --reload --port 8001
