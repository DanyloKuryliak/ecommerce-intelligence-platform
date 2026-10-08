"""Refresh a ClickHouse analytical copy of completed PostgreSQL orders."""

from __future__ import annotations

import os
from decimal import Decimal

import clickhouse_connect
import psycopg

from pipeline.load_demo_data import DEFAULT_DATABASE_URL

CREATE_ORDERS = """CREATE TABLE IF NOT EXISTS ecommerce.completed_orders (
    order_id UInt32,
    customer_id UInt32,
    order_date Date,
    product_id LowCardinality(String),
    product_name LowCardinality(String),
    product_category LowCardinality(String),
    units UInt16,
    revenue Decimal(18, 5)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(order_date)
ORDER BY (order_date, product_category, order_id)"""


def sync_orders(database_url: str) -> dict[str, int]:
    """Replace the local analytical copy and verify row and revenue parity."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT o.order_id, o.customer_id, o.order_timestamp::date,
                    o.product_id, p.product_name, o.product_category,
                    o.quantity, o.quantity * o.unit_price * (1 - o.discount_pct)
                FROM orders o JOIN products p ON p.product_id = o.product_id
                WHERE o.status = 'completed' ORDER BY o.order_id"""
            )
            rows = cursor.fetchall()
    if not rows:
        raise RuntimeError("No completed PostgreSQL orders to synchronize.")

    client = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "change-me-locally"),
    )
    client.command("CREATE DATABASE IF NOT EXISTS ecommerce")
    client.command(CREATE_ORDERS)
    client.command("ALTER TABLE ecommerce.completed_orders MODIFY COLUMN revenue Decimal(18, 5)")
    client.command("ALTER TABLE ecommerce.completed_orders ADD COLUMN IF NOT EXISTS product_id LowCardinality(String)")
    client.command("ALTER TABLE ecommerce.completed_orders ADD COLUMN IF NOT EXISTS product_name LowCardinality(String)")
    client.command("TRUNCATE TABLE ecommerce.completed_orders")
    client.insert(
        "ecommerce.completed_orders",
        rows,
        column_names=["order_id", "customer_id", "order_date", "product_id", "product_name", "product_category", "units", "revenue"],
    )
    count, revenue = client.query("SELECT count(), sum(revenue) FROM ecommerce.completed_orders").first_row
    expected_revenue = sum((row[7] for row in rows), Decimal("0"))
    if count != len(rows) or abs(Decimal(str(revenue)) - expected_revenue) > Decimal("0.01"):
        raise RuntimeError("ClickHouse copy differs from PostgreSQL in row count or revenue.")
    return {"completed_orders": count, "revenue": str(expected_revenue)}


if __name__ == "__main__":
    print(sync_orders(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)))
