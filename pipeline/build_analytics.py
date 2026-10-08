"""Build small warehouse-style summary tables from the clean order tables."""

from __future__ import annotations

import os

import psycopg

DEFAULT_DATABASE_URL = "postgresql://ecommerce_app:change-me-locally@localhost:5433/ecommerce"


def segment_customer(recency_days: int | None, completed_orders: int, total_revenue: float) -> str:
    """Apply transparent business rules; this is not an ML prediction."""
    if completed_orders == 0:
        return "No purchase"
    if recency_days is not None and recency_days > 75 and completed_orders >= 2:
        return "At risk"
    if recency_days is not None and recency_days <= 30 and completed_orders <= 10:
        return "New"
    if total_revenue >= 4_000:
        return "VIP"
    if completed_orders >= 18:
        return "Loyal"
    return "Regular"


def build_analytics(database_url: str) -> tuple[int, int]:
    """Refresh monthly sales and customer feature tables from PostgreSQL."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS monthly_sales (
                    month DATE PRIMARY KEY,
                    revenue NUMERIC(14, 2) NOT NULL,
                    completed_orders INTEGER NOT NULL,
                    active_customers INTEGER NOT NULL,
                    average_order_value NUMERIC(14, 2) NOT NULL
                )"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS customer_features (
                    customer_id INTEGER PRIMARY KEY REFERENCES customers(customer_id),
                    first_order_date DATE,
                    last_order_date DATE,
                    recency_days INTEGER,
                    completed_orders INTEGER NOT NULL,
                    total_revenue NUMERIC(14, 2) NOT NULL,
                    average_order_value NUMERIC(14, 2) NOT NULL,
                    segment TEXT NOT NULL
                )"""
            )
            cursor.execute("TRUNCATE monthly_sales, customer_features")
            cursor.execute(
                """INSERT INTO monthly_sales
                    (month, revenue, completed_orders, active_customers, average_order_value)
                SELECT DATE_TRUNC('month', order_timestamp)::date,
                    ROUND(SUM(quantity * unit_price * (1 - discount_pct)), 2),
                    COUNT(*)::integer,
                    COUNT(DISTINCT customer_id)::integer,
                    ROUND(AVG(quantity * unit_price * (1 - discount_pct)), 2)
                FROM orders
                WHERE status = 'completed'
                GROUP BY 1
                ORDER BY 1"""
            )
            cursor.execute(
                """INSERT INTO customer_features
                    (customer_id, first_order_date, last_order_date, recency_days,
                     completed_orders, total_revenue, average_order_value, segment)
                WITH reference AS (
                    SELECT COALESCE(MAX(order_timestamp::date), DATE '2025-01-01') AS reference_date
                    FROM orders WHERE status = 'completed'
                ), base AS (
                    SELECT c.customer_id,
                        MIN(o.order_timestamp::date) AS first_order_date,
                        MAX(o.order_timestamp::date) AS last_order_date,
                        COUNT(o.order_id)::integer AS completed_orders,
                        COALESCE(SUM(o.quantity * o.unit_price * (1 - o.discount_pct)), 0) AS total_revenue,
                        COALESCE(AVG(o.quantity * o.unit_price * (1 - o.discount_pct)), 0) AS average_order_value,
                        reference.reference_date
                    FROM customers c
                    CROSS JOIN reference
                    LEFT JOIN orders o
                        ON o.customer_id = c.customer_id AND o.status = 'completed'
                    GROUP BY c.customer_id, reference.reference_date
                )
                SELECT customer_id, first_order_date, last_order_date,
                    CASE WHEN last_order_date IS NULL THEN NULL
                         ELSE (reference_date - last_order_date)::integer END,
                    completed_orders,
                    ROUND(total_revenue, 2),
                    ROUND(average_order_value, 2),
                    CASE
                        WHEN completed_orders = 0 THEN 'No purchase'
                        WHEN (reference_date - last_order_date) > 75 AND completed_orders >= 2 THEN 'At risk'
                        WHEN (reference_date - last_order_date) <= 30 AND completed_orders <= 10 THEN 'New'
                        WHEN total_revenue >= 4000 THEN 'VIP'
                        WHEN completed_orders >= 18 THEN 'Loyal'
                        ELSE 'Regular'
                    END
                FROM base"""
            )
            cursor.execute("SELECT COUNT(*) FROM monthly_sales")
            monthly_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM customer_features")
            customer_count = cursor.fetchone()[0]
        connection.commit()
    return monthly_count, customer_count


if __name__ == "__main__":
    monthly_count, customer_count = build_analytics(
        os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    print(f"Built {monthly_count} monthly rows and {customer_count} customer feature rows.")
