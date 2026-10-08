"""Local scheduled data, warehouse and model refresh."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from airflow.sdk import dag, task

ROOT = Path("/opt/project")


@dag(
    dag_id="ecommerce_intelligence_refresh",
    schedule="@weekly",
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    is_paused_upon_creation=True,
    tags=["portfolio", "ecommerce"],
)
def ecommerce_pipeline():
    @task
    def generate():
        from pipeline.generate_demo_data import generate_data

        generate_data(ROOT / "data" / "generated", seed=42)

    @task
    def validate():
        from pipeline.quality_checks import run_quality_checks, write_quality_report

        report = run_quality_checks(ROOT / "data" / "generated")
        write_quality_report(ROOT / "data" / "generated", report)
        if report["status"] != "passed":
            raise RuntimeError("Synthetic input quality checks failed.")

    @task
    def load():
        from pipeline.load_demo_data import load_data

        load_data(ROOT / "data" / "generated", os.environ["DATABASE_URL"])

    @task
    def analytics():
        from pipeline.build_analytics import build_analytics

        build_analytics(os.environ["DATABASE_URL"])

    @task
    def warehouse():
        from pipeline.sync_clickhouse import sync_orders

        sync_orders(os.environ["DATABASE_URL"])

    @task
    def churn():
        from ml.churn_model import train_churn_model

        train_churn_model(os.environ["DATABASE_URL"], ROOT / "data" / "models")

    @task
    def demand():
        from ml.demand_forecast import build_demand_forecast

        build_demand_forecast(os.environ["DATABASE_URL"], ROOT / "data" / "models")

    @task
    def monitor():
        import json

        from ml.model_monitoring import build_monitoring_report

        report = build_monitoring_report(ROOT / "data" / "models")
        (ROOT / "data" / "models" / "model_monitoring.json").write_text(json.dumps(report, indent=2) + "\n")

    generated = generate()
    validated = validate()
    loaded = load()
    analytics_task = analytics()
    warehouse_task = warehouse()
    churn_task = churn()
    demand_task = demand()
    monitored = monitor()

    generated >> validated >> loaded
    loaded >> [analytics_task, warehouse_task, churn_task]
    analytics_task >> demand_task
    churn_task >> monitored


ecommerce_pipeline()
