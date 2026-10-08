"""Evaluate a transparent moving-average demand forecast baseline."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from sklearn.metrics import mean_absolute_error

DEFAULT_DATABASE_URL = "postgresql://ecommerce_app:change-me-locally@localhost:5433/ecommerce"


def next_month(value: date) -> date:
    return date(value.year + (value.month == 12), 1 if value.month == 12 else value.month + 1, 1)


def build_demand_forecast(database_url: str, output_dir: Path) -> dict[str, Any]:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT month, revenue FROM monthly_sales ORDER BY month")
            history = [(month, float(revenue)) for month, revenue in cursor.fetchall()]
    if len(history) < 6:
        raise RuntimeError("Demand forecasting requires at least six monthly summary rows.")

    holdout_size = 3
    window = 3
    train = history[:-holdout_size]
    actual = [value for _, value in history[-holdout_size:]]
    predictions = [sum(value for _, value in train[-window:]) / window] * holdout_size
    mae = float(mean_absolute_error(actual, predictions))
    mape = float(sum(abs(a - p) / a for a, p in zip(actual, predictions)) / len(actual))
    next_value = sum(value for _, value in history[-window:]) / window
    forecast = []
    month = next_month(history[-1][0])
    for _ in range(3):
        forecast.append({"month": month.isoformat(), "forecast_revenue": round(next_value, 2)})
        month = next_month(month)

    report = {
        "model": "three_month_moving_average",
        "history_rows": len(history),
        "holdout_months": holdout_size,
        "mae": round(mae, 2),
        "mape": round(mape, 4),
        "forecast": forecast,
        "warning": "Demonstration baseline on synthetic data; not a financial forecast.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "demand_forecast.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    report = build_demand_forecast(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL), root / "data" / "models")
    print(json.dumps(report, indent=2))
