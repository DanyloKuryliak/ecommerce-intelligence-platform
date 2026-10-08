.DEFAULT_GOAL := help

PYTHON ?= python3
VENV := .venv
PY := $(VENV)/bin/python
COMPOSE := docker compose --env-file .env -f infra/compose.local.yaml

.PHONY: help setup data quality db-up db-down load analytics warehouse ml monitor mlflow-ui airflow-up demo-snapshot test run-api run-bento

help:
	@echo "setup → data → db-up → analytics → warehouse → ml → test → run-api"

setup:
	uv venv $(VENV)
	uv pip install --python $(PY) -r api/requirements.txt

data:
	$(PY) pipeline/generate_demo_data.py

quality:
	$(PY) pipeline/quality_checks.py

analytics: load
	set -a; . ./.env; set +a; $(PY) pipeline/build_analytics.py

warehouse:
	set -a; . ./.env; set +a; $(PY) -m pipeline.sync_clickhouse

ml: analytics warehouse
	set -a; . ./.env; set +a; $(PY) ml/churn_model.py
	set -a; . ./.env; set +a; $(PY) ml/demand_forecast.py
	$(MAKE) monitor

monitor:
	$(PY) ml/model_monitoring.py

mlflow-ui:
	@echo "MLflow is available at http://127.0.0.1:5000 after make airflow-up"

demo-snapshot:
	set -a; . ./.env; set +a; $(PY) -m pipeline.export_public_snapshot

db-up:
	$(COMPOSE) up -d --wait postgres clickhouse

airflow-up:
	$(COMPOSE) --profile orchestration up -d --build airflow

db-down:
	$(COMPOSE) down

load: quality
	set -a; . ./.env; set +a; $(PY) pipeline/load_demo_data.py

test:
	$(PY) -m pytest api/tests -q

run-api:
	set -a; . ./.env; set +a; $(PY) -m uvicorn api.app.main:app --reload --port 8001

run-bento:
	$(VENV)/bin/bentoml serve serving/service.py:ChurnService --port 3001
