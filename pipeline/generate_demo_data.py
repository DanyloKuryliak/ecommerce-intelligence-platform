"""Create deterministic synthetic store data with realistic customer lifecycles.

The generator uses hidden simulation profiles (stable, low-frequency, and
decaying activity) to create learnable behavior. Those profiles are not written
to the database, so models must learn from observable order history.
"""

from __future__ import annotations

import csv
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SEED = 42
CUSTOMER_COUNT = 600
COUNTRIES = ("Ukraine", "Poland", "Germany", "United Kingdom")
CHANNELS = ("organic", "paid_search", "email", "referral")
CATEGORIES = {
    "Accessories": (8.0, 45.0),
    "Electronics": (80.0, 450.0),
    "Home": (20.0, 180.0),
    "Sports": (15.0, 140.0),
}
PRODUCTS = {
    "Accessories": ("Canvas Tote", "Travel Pouch", "Desk Organizer"),
    "Electronics": ("Wireless Headphones", "Smart Speaker", "Portable Charger"),
    "Home": ("Table Lamp", "Throw Blanket", "Coffee Maker"),
    "Sports": ("Yoga Mat", "Running Bottle", "Training Bag"),
}


def generate_data(output_dir: Path, seed: int = SEED) -> tuple[int, int]:
    """Write customers.csv and orders.csv; return their actual row counts."""
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    start = date(2025, 1, 1)
    customers = []
    profiles: dict[int, tuple[float, int | None]] = {}

    for customer_id in range(1, CUSTOMER_COUNT + 1):
        signup = date(2024, 1, 1) + timedelta(days=rng.randrange(365))
        customers.append(
            {
                "customer_id": customer_id,
                "signup_date": signup.isoformat(),
                "country": rng.choice(COUNTRIES),
                "acquisition_channel": rng.choice(CHANNELS),
            }
        )
        profile_roll = rng.random()
        if profile_roll < 0.60:
            base_weekly_probability, churn_week = 0.62, None
        elif profile_roll < 0.80:
            base_weekly_probability, churn_week = 0.32, rng.randint(30, 46)
        else:
            base_weekly_probability, churn_week = 0.18, rng.randint(18, 42)
        profiles[customer_id] = (base_weekly_probability, churn_week)

    orders = []
    products = [
        {"product_id": f"{category[:3].upper()}-{index:02d}", "product_name": name, "product_category": category}
        for category, names in PRODUCTS.items()
        for index, name in enumerate(names, start=1)
    ]
    product_ids = {category: [row["product_id"] for row in products if row["product_category"] == category] for category in PRODUCTS}
    order_id = 1
    for customer_id in range(1, CUSTOMER_COUNT + 1):
        base_probability, churn_week = profiles[customer_id]
        for week in range(52):
            probability = 0.02 if churn_week is not None and week >= churn_week else base_probability
            if rng.random() >= probability:
                continue
            transaction_count = 1 + int(base_probability > 0.5 and rng.random() < 0.25)
            for _ in range(transaction_count):
                category = rng.choice(tuple(CATEGORIES))
                product_id = rng.choice(product_ids[category])
                low, high = CATEGORIES[category]
                order_date = start + timedelta(days=week * 7 + rng.randrange(7))
                order_time = datetime(
                    order_date.year,
                    order_date.month,
                    order_date.day,
                    tzinfo=timezone.utc,
                ) + timedelta(minutes=rng.randrange(1_440))
                orders.append(
                    {
                        "order_id": order_id,
                        "customer_id": customer_id,
                        "order_timestamp": order_time.isoformat(),
                        "product_category": category,
                        "product_id": product_id,
                        "quantity": rng.randint(1, 4),
                        "unit_price": f"{rng.uniform(low, high):.2f}",
                        "discount_pct": f"{rng.choice((0, 0, 0.05, 0.10, 0.15)):.2f}",
                        "status": "cancelled" if rng.random() < 0.06 else "completed",
                    }
                )
                order_id += 1

    orders.sort(key=lambda row: row["order_timestamp"])
    _write_csv(output_dir / "customers.csv", customers)
    _write_csv(output_dir / "products.csv", products)
    _write_csv(output_dir / "orders.csv", orders)
    return len(customers), len(orders)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    customer_count, order_count = generate_data(root / "data" / "generated")
    print(f"Generated {customer_count} customers and {order_count} orders in data/generated/.")
