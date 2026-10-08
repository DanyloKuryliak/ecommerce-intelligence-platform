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
    products = read_csv(data_dir / "products.csv")
    orders = read_csv(data_dir / "orders.csv")
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY, product_name TEXT NOT NULL, product_category TEXT NOT NULL)""")
            cursor.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS product_id TEXT REFERENCES products(product_id)")
            cursor.execute("TRUNCATE customer_features, monthly_sales, orders, customers, products")
            cursor.executemany(
                """INSERT INTO products (product_id, product_name, product_category)
                VALUES (%(product_id)s, %(product_name)s, %(product_category)s)""",
                products,
            )
            cursor.executemany(
                """INSERT INTO customers (customer_id, signup_date, country, acquisition_channel)
                VALUES (%(customer_id)s, %(signup_date)s, %(country)s, %(acquisition_channel)s)""",
                customers,
            )
            cursor.executemany(
                """INSERT INTO orders (order_id, customer_id, order_timestamp, product_category, product_id,
                quantity, unit_price, discount_pct, status)
                VALUES (%(order_id)s, %(customer_id)s, %(order_timestamp)s, %(product_category)s, %(product_id)s,
                %(quantity)s, %(unit_price)s, %(discount_pct)s, %(status)s)""",
                orders,
            )
            cursor.execute("ALTER TABLE orders ALTER COLUMN product_id SET NOT NULL")
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
