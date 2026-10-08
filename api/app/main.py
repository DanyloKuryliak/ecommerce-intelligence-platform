"""Serve the first E-Commerce Intelligence dashboard from PostgreSQL."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import joblib
import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from pipeline.quality_checks import run_quality_checks

DEFAULT_DATABASE_URL = "postgresql://ecommerce_app:change-me-locally@localhost:5433/ecommerce"
WEB_INDEX = Path(__file__).resolve().parents[2] / "web" / "index.html"
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "generated"
MODEL_DIR = Path(__file__).resolve().parents[2] / "data" / "models"

app = FastAPI(title="E-Commerce Intelligence API", version="0.1.0")


def get_quality_report() -> dict[str, Any]:
    """Read the latest input-quality result, or explain that it has not run."""
    report_path = DATA_DIR / "quality_report.json"
    if not report_path.exists():
        return {"status": "not_run", "data_note": "Run the quality checkpoint before loading data."}
    return run_quality_checks(DATA_DIR)


def get_ml_status() -> dict[str, Any]:
    """Return saved evaluation reports without hiding missing-model state."""
    status: dict[str, Any] = {}
    for name in ("churn_metrics", "demand_forecast", "model_monitoring"):
        path = MODEL_DIR / f"{name}.json"
        status[name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "not_trained"}
    return status


def get_dashboard(database_url: str) -> dict[str, Any]:
    """Calculate only completed-order metrics directly from PostgreSQL."""
    try:
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT
                        COALESCE(SUM(quantity * unit_price * (1 - discount_pct)), 0),
                        COUNT(*),
                        COUNT(DISTINCT customer_id),
                        COALESCE(AVG(quantity * unit_price * (1 - discount_pct)), 0)
                    FROM orders WHERE status = 'completed'"""
                )
                revenue, orders, active_customers, average_order_value = cursor.fetchone()
                cursor.execute(
                    """SELECT TO_CHAR(DATE_TRUNC('month', order_timestamp), 'YYYY-MM'),
                        ROUND(SUM(quantity * unit_price * (1 - discount_pct)), 2)
                    FROM orders WHERE status = 'completed'
                    GROUP BY 1 ORDER BY 1"""
                )
                monthly_revenue = [{"month": month, "revenue": float(value)} for month, value in cursor.fetchall()]
                cursor.execute(
                    """SELECT product_category,
                        ROUND(SUM(quantity * unit_price * (1 - discount_pct)), 2)
                    FROM orders WHERE status = 'completed'
                    GROUP BY 1 ORDER BY 2 DESC"""
                )
                category_revenue = [{"category": category, "revenue": float(value)} for category, value in cursor.fetchall()]
                cursor.execute(
                    """SELECT product_category,
                        COUNT(*)::integer,
                        COALESCE(SUM(quantity), 0)::integer,
                        ROUND(SUM(quantity * unit_price * (1 - discount_pct)), 2),
                        ROUND(AVG(discount_pct), 4)
                    FROM orders WHERE status = 'completed'
                    GROUP BY product_category ORDER BY 4 DESC"""
                )
                product_performance = [
                    {
                        "product_category": category,
                        "orders": orders,
                        "units": units,
                        "revenue": float(revenue),
                        "average_discount": float(discount),
                    }
                    for category, orders, units, revenue, discount in cursor.fetchall()
                ]
    except psycopg.Error as error:
        raise RuntimeError("PostgreSQL is unavailable or demo data has not been loaded.") from error

    return {
        "kpis": {
            "revenue": float(revenue),
            "completed_orders": orders,
            "active_customers": active_customers,
            "average_order_value": float(average_order_value),
        },
        "monthly_revenue": monthly_revenue,
        "category_revenue": category_revenue,
        "product_performance": product_performance,
        "data_quality": get_quality_report(),
        "analytics": get_analytics(database_url),
        "ml_status": get_ml_status(),
        "data_note": "Synthetic deterministic demo data; completed orders only.",
    }


def get_analytics(database_url: str) -> dict[str, Any]:
    """Read the refreshed warehouse-style summaries."""
    try:
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT TO_CHAR(month, 'YYYY-MM'), revenue, completed_orders,
                        active_customers, average_order_value
                    FROM monthly_sales ORDER BY month"""
                )
                monthly = [
                    {
                        "month": month,
                        "revenue": float(revenue),
                        "completed_orders": completed_orders,
                        "active_customers": active_customers,
                        "average_order_value": float(average_order_value),
                    }
                    for month, revenue, completed_orders, active_customers, average_order_value in cursor.fetchall()
                ]
                cursor.execute(
                    """SELECT segment, COUNT(*)::integer
                    FROM customer_features GROUP BY segment ORDER BY COUNT(*) DESC, segment"""
                )
                segments = [{"segment": segment, "customers": customers} for segment, customers in cursor.fetchall()]
                cursor.execute(
                    """SELECT customer_id, completed_orders, total_revenue, segment
                    FROM customer_features WHERE completed_orders > 0
                    ORDER BY total_revenue DESC, customer_id LIMIT 10"""
                )
                top_customers = [
                    {
                        "customer_id": customer_id,
                        "completed_orders": completed_orders,
                        "total_revenue": float(total_revenue),
                        "segment": segment,
                    }
                    for customer_id, completed_orders, total_revenue, segment in cursor.fetchall()
                ]
    except psycopg.Error as error:
        raise RuntimeError("Analytics tables are not built; run make analytics.") from error
    return {"monthly": monthly, "segments": segments, "top_customers": top_customers}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data": "synthetic"}


@app.get("/api/v1/dashboard")
def dashboard() -> dict[str, Any]:
    try:
        return get_dashboard(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/v1/analytics")
def analytics() -> dict[str, Any]:
    try:
        return get_analytics(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/v1/ml-status")
def ml_status() -> dict[str, Any]:
    return get_ml_status()


def apply_forecast_scenario(forecast: list[dict[str, Any]], growth_pct: float) -> list[dict[str, Any]]:
    """Apply a transparent what-if growth assumption to the baseline forecast."""
    multiplier = 1 + (growth_pct / 100)
    return [
        {**row, "forecast_revenue": round(float(row["forecast_revenue"]) * multiplier, 2)}
        for row in forecast
    ]


@app.get("/api/v1/forecast/what-if")
def forecast_what_if(growth_pct: float = Query(default=0.0, ge=-100.0, le=200.0)) -> dict[str, Any]:
    """Return the baseline demand forecast under a user-selected growth assumption."""
    path = MODEL_DIR / "demand_forecast.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Demand forecast is not trained; run make ml.")
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        "growth_pct": growth_pct,
        "forecast": apply_forecast_scenario(report["forecast"], growth_pct),
        "warning": "Demonstration scenario on synthetic data; not a financial forecast.",
    }


@app.get("/api/v1/customers/{customer_id}/churn-score")
def churn_score(customer_id: int) -> dict[str, Any]:
    model_path = MODEL_DIR / "churn_model.joblib"
    if not model_path.exists():
        raise HTTPException(status_code=503, detail="Churn model is not trained; run make ml.")
    try:
        with psycopg.connect(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """WITH reference AS (
                        SELECT COALESCE(MAX(order_timestamp::date), DATE '2025-01-01') AS reference_date
                        FROM orders WHERE status = 'completed'
                    )
                    SELECT
                        COALESCE((reference.reference_date - MAX(o.order_timestamp::date))::float, 9999),
                        COUNT(o.order_id) FILTER (WHERE o.order_timestamp::date > reference.reference_date - 30),
                        COUNT(o.order_id) FILTER (WHERE o.order_timestamp::date > reference.reference_date - 90),
                        COALESCE(SUM(o.quantity * o.unit_price * (1 - o.discount_pct))
                            FILTER (WHERE o.order_timestamp::date > reference.reference_date - 90), 0),
                        COALESCE(AVG(o.quantity * o.unit_price * (1 - o.discount_pct))
                            FILTER (WHERE o.order_timestamp::date > reference.reference_date - 90), 0),
                        COUNT(DISTINCT o.product_category)
                            FILTER (WHERE o.order_timestamp::date > reference.reference_date - 90),
                        COALESCE(AVG(o.discount_pct)
                            FILTER (WHERE o.order_timestamp::date > reference.reference_date - 90), 0),
                        (reference.reference_date - c.signup_date)::float,
                        COUNT(o.order_id)
                    FROM customers c
                    CROSS JOIN reference
                    LEFT JOIN orders o ON o.customer_id = c.customer_id AND o.status = 'completed'
                    WHERE c.customer_id = %s
                    GROUP BY c.customer_id, c.signup_date, reference.reference_date""",
                    (customer_id,),
                )
                row = cursor.fetchone()
    except psycopg.Error as error:
        raise HTTPException(status_code=503, detail="PostgreSQL is unavailable.") from error
    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    artifact = joblib.load(model_path)
    features = [0 if value is None else float(value) for value in row]
    probability = float(artifact["model"].predict_proba([features])[0][1])
    feature_map = dict(zip(artifact["features"], features))
    reasons: list[str] = []
    if feature_map["recency_days"] > 60:
        reasons.append("No recent order")
    if feature_map["orders_last_30d"] == 0:
        reasons.append("No order in the last 30 days")
    if feature_map["orders_last_90d"] == 0:
        reasons.append("No order in the last 90 days")
    if feature_map["category_diversity_90d"] <= 1:
        reasons.append("Limited category activity")
    return {
        "customer_id": customer_id,
        "churn_probability": round(probability, 4),
        "risk_band": "high" if probability >= 0.5 else "lower",
        "features": feature_map,
        "reasons": reasons,
        "global_feature_importance": artifact["metrics"].get("permutation_importance", []),
        "warning": "Demonstration baseline on synthetic data; not a production decision system.",
    }


@app.get("/")
def web_dashboard() -> FileResponse:
    return FileResponse(WEB_INDEX)
