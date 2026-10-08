import csv
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from api.app.main import app, apply_forecast_scenario
from pipeline.generate_demo_data import CUSTOMER_COUNT, generate_data
from pipeline.quality_checks import run_quality_checks
from pipeline.build_analytics import segment_customer
from ml.churn_model import SnapshotTimeSeriesSplit
from ml.model_monitoring import _relative_change


def test_generator_is_repeatable_and_writes_expected_rows(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_counts = generate_data(first, seed=42)
    second_counts = generate_data(second, seed=42)
    assert first_counts == second_counts
    assert first_counts[0] == CUSTOMER_COUNT
    assert first_counts[1] > 5_000
    assert (first / "orders.csv").read_text() == (second / "orders.csv").read_text()


def test_quality_report_passes_for_generated_data(tmp_path: Path) -> None:
    generate_data(tmp_path, seed=42)

    report = run_quality_checks(tmp_path)

    assert report["status"] == "passed"
    assert all(check["status"] == "passed" for check in report["checks"])


def test_quality_report_fails_for_unknown_customer(tmp_path: Path) -> None:
    generate_data(tmp_path, seed=42)
    orders_path = tmp_path / "orders.csv"
    with orders_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    rows[0]["customer_id"] = "999999"
    with orders_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)

    report = run_quality_checks(tmp_path)

    assert report["status"] == "failed"
    reference_check = next(check for check in report["checks"] if check["name"] == "orders_reference_known_customers")
    assert reference_check["status"] == "failed"


def test_quality_report_rejects_product_category_mismatch(tmp_path: Path) -> None:
    generate_data(tmp_path, seed=42)
    orders_path = tmp_path / "orders.csv"
    with orders_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    rows[0]["product_category"] = "Unknown"
    with orders_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)

    report = run_quality_checks(tmp_path)

    assert report["status"] == "failed"
    assert next(check for check in report["checks"] if check["name"] == "orders_reference_catalog")["status"] == "failed"


def test_customer_segmentation_rules_are_transparent() -> None:
    assert segment_customer(None, 0, 0) == "No purchase"
    assert segment_customer(30, 10, 100) == "New"
    assert segment_customer(80, 3, 500) == "At risk"
    assert segment_customer(60, 18, 500) == "Loyal"
    assert segment_customer(60, 2, 4_000) == "VIP"


def test_forecast_scenario_applies_growth_without_mutating_baseline() -> None:
    baseline = [{"month": "2026-01-01", "forecast_revenue": 100.0}]

    result = apply_forecast_scenario(baseline, 10)

    assert result == [{"month": "2026-01-01", "forecast_revenue": 110.0}]
    assert baseline == [{"month": "2026-01-01", "forecast_revenue": 100.0}]


def test_relative_change_handles_zero_reference() -> None:
    assert _relative_change(0, 0) == 0
    assert _relative_change(0, 4) == 1
    assert _relative_change(10, 15) == 0.5


def test_static_demo_snapshot_has_dashboard_contract() -> None:
    snapshot = json.loads(Path(__file__).resolve().parents[2].joinpath("web", "demo-data.json").read_text())

    assert snapshot["kpis"]["active_customers"] > 0
    assert snapshot["product_performance"]
    assert len({product["product_id"] for product in snapshot["product_performance"]}) == 12
    assert all(product["product_name"] and product["product_category"] for product in snapshot["product_performance"])
    assert "customer_id" not in json.dumps(snapshot)
    assert snapshot["ml_status"]["churn_metrics"]["candidate_results"]
    assert snapshot["ml_status"]["demand_forecast"]["forecast"]


def test_snapshot_split_is_forward_only_and_keeps_snapshots_intact() -> None:
    groups = ["2025-01-01", "2025-01-01", "2025-03-01", "2025-03-01", "2025-05-01", "2025-05-01"]
    folds = list(SnapshotTimeSeriesSplit(n_splits=2).split(groups, groups=groups))

    assert len(folds) == 2
    for train_indices, validation_indices in folds:
        train_groups = {groups[index] for index in train_indices}
        validation_groups = {groups[index] for index in validation_indices}
        assert train_groups.isdisjoint(validation_groups)
        assert max(train_groups) < min(validation_groups)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health_describes_synthetic_data() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data": "synthetic"}


@pytest.mark.anyio
async def test_dashboard_explains_missing_local_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://missing:missing@127.0.0.1:1/missing")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard")

    assert response.status_code == 503
    assert "PostgreSQL is unavailable" in response.json()["detail"]
