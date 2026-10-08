"""Load generated CSV files into the local PostgreSQL database."""

from __future__ import annotations

import csv
import os
from pathlib import Path

import psycopg

DEFAULT_DATABASE_URL = "postgresql://ecommerce_app:change-me-locally@localhost:5433/ecommerce"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_data(data_dir: Path, database_url: str) -> tuple[int, int]:
    customers = read_csv(data_dir / "customers.csv")
    orders = read_csv(data_dir / "orders.csv")
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE customer_features, monthly_sales, orders, customers")
            cursor.executemany(
                """INSERT INTO customers (customer_id, signup_date, country, acquisition_channel)
                VALUES (%(customer_id)s, %(signup_date)s, %(country)s, %(acquisition_channel)s)""",
                customers,
            )
            cursor.executemany(
                """INSERT INTO orders (order_id, customer_id, order_timestamp, product_category,
                quantity, unit_price, discount_pct, status)
                VALUES (%(order_id)s, %(customer_id)s, %(order_timestamp)s, %(product_category)s,
                %(quantity)s, %(unit_price)s, %(discount_pct)s, %(status)s)""",
                orders,
            )
            cursor.execute(
                "SELECT (SELECT COUNT(*) FROM customers), (SELECT COUNT(*) FROM orders)"
            )
            loaded_customers, loaded_orders = cursor.fetchone()
        connection.commit()
    if (loaded_customers, loaded_orders) != (len(customers), len(orders)):
        raise RuntimeError("Database row counts do not match the generated CSV files.")
    return loaded_customers, loaded_orders


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    customer_count, order_count = load_data(root / "data" / "generated", database_url)
    print(f"Loaded {customer_count} customers and {order_count} orders into PostgreSQL.")
