"""Create a small, reproducible health report for the churn artifact."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import joblib

DEFAULT_DATABASE_URL = "postgresql://ecommerce_app:change-me-locally@localhost:5433/ecommerce"
FEATURES = (
    "recency_days",
    "orders_last_30d",
    "orders_last_90d",
    "revenue_last_90d",
    "average_order_value_90d",
    "category_diversity_90d",
    "discount_rate_90d",
    "tenure_days",
    "completed_orders_lifetime",
)


def _mean(rows: list[dict[str, str]], field: str) -> float:
    values = [float(row[field]) for row in rows]
    return sum(values) / len(values) if values else 0.0


def _relative_change(reference: float, current: float) -> float:
    """Return a bounded relative change, treating two zeroes as unchanged."""
    if reference == 0:
        return 0.0 if current == 0 else 1.0
    return (current - reference) / abs(reference)


def build_monitoring_report(model_dir: Path) -> dict[str, Any]:
    """Compare the latest snapshot with development data and score its health."""
    metrics_path = model_dir / "churn_metrics.json"
    dataset_path = model_dir / "churn_dataset.csv"
    model_path = model_dir / "churn_model.joblib"
    if not all(path.exists() for path in (metrics_path, dataset_path, model_path)):
        raise RuntimeError("Train the churn model before running monitoring.")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    with dataset_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    snapshots = sorted({row["snapshot_date"] for row in rows})
    latest_snapshot = snapshots[-1]
    development_rows = [row for row in rows if row["snapshot_date"] < latest_snapshot]
    latest_rows = [row for row in rows if row["snapshot_date"] == latest_snapshot]
    feature_drift = []
    for feature in FEATURES:
        reference_mean = _mean(development_rows, feature)
        latest_mean = _mean(latest_rows, feature)
        change = _relative_change(reference_mean, latest_mean)
        feature_drift.append(
            {
                "feature": feature,
                "development_mean": round(reference_mean, 4),
                "latest_mean": round(latest_mean, 4),
                "relative_change": round(change, 4),
                "status": "review" if abs(change) >= 0.5 else "stable",
            }
        )

    artifact = joblib.load(model_path)
    probabilities = artifact["model"].predict_proba([[float(row[feature]) for feature in FEATURES] for row in latest_rows])[:, 1]
    high_risk_rate = sum(probability >= 0.5 for probability in probabilities) / len(probabilities)
    review_features = [item["feature"] for item in feature_drift if item["status"] == "review"]
    status = "review" if review_features else "healthy"
    return {
        "status": status,
        "model": metrics["model"],
        "latest_snapshot": latest_snapshot,
        "development_rows": len(development_rows),
        "latest_rows": len(latest_rows),
        "test_metrics": {
            "roc_auc": metrics.get("roc_auc"),
            "average_precision": metrics.get("average_precision"),
            "baseline_average_precision": metrics.get("baseline_average_precision"),
        },
        "prediction_summary": {
            "mean_churn_probability": round(float(probabilities.mean()), 4),
            "high_risk_rate": round(high_risk_rate, 4),
        },
        "feature_drift": feature_drift,
        "checks": [
            {
                "name": "performance_above_baseline",
                "status": "passed" if (metrics.get("average_precision") or 0) > (metrics.get("baseline_average_precision") or 0) else "review",
            },
            {
                "name": "feature_drift",
                "status": "passed" if not review_features else "review",
                "details": review_features or "No feature changed by 50% or more.",
            },
        ],
        "warning": "Monitoring is a synthetic-demo health report; thresholds are not production SLAs.",
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "data" / "models"
    report = build_monitoring_report(output_dir)
    (output_dir / "model_monitoring.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
