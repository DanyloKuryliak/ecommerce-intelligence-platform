"""Run cheap, explicit quality checks before demo data enters PostgreSQL."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

CUSTOMER_FIELDS = ("customer_id", "signup_date", "country", "acquisition_channel")
ORDER_FIELDS = (
    "order_id",
    "customer_id",
    "order_timestamp",
    "product_category",
    "quantity",
    "unit_price",
    "discount_pct",
    "status",
)
ALLOWED_STATUSES = {"completed", "cancelled"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _check(name: str, passed: bool, details: str) -> dict[str, Any]:
    return {"name": name, "status": "passed" if passed else "failed", "details": details}


def run_quality_checks(data_dir: Path) -> dict[str, Any]:
    """Return a JSON-serializable report without changing the input files."""
    customers = _read_csv(data_dir / "customers.csv")
    orders = _read_csv(data_dir / "orders.csv")
    checks: list[dict[str, Any]] = []

    customer_ids = [row.get("customer_id", "") for row in customers]
    order_ids = [row.get("order_id", "") for row in orders]
    checks.append(_check("customers_not_empty", bool(customers), f"{len(customers)} customer rows found"))
    checks.append(_check("orders_not_empty", bool(orders), f"{len(orders)} order rows found"))
    checks.append(_check("customer_ids_unique", len(customer_ids) == len(set(customer_ids)), "Customer IDs have no duplicates"))
    checks.append(_check("order_ids_unique", len(order_ids) == len(set(order_ids)), "Order IDs have no duplicates"))

    missing_customer_fields = sum(
        1 for row in customers for field in CUSTOMER_FIELDS if not row.get(field, "").strip()
    )
    missing_order_fields = sum(
        1 for row in orders for field in ORDER_FIELDS if not row.get(field, "").strip()
    )
    checks.append(_check("customer_required_fields", missing_customer_fields == 0, f"{missing_customer_fields} missing customer fields"))
    checks.append(_check("order_required_fields", missing_order_fields == 0, f"{missing_order_fields} missing order fields"))

    valid_customer_ids: set[int] = set()
    invalid_customer_ids = 0
    invalid_signup_dates = 0
    for row in customers:
        try:
            valid_customer_ids.add(int(row["customer_id"]))
        except (KeyError, TypeError, ValueError):
            invalid_customer_ids += 1
        try:
            date.fromisoformat(row["signup_date"])
        except (KeyError, TypeError, ValueError):
            invalid_signup_dates += 1
    checks.append(_check("customer_ids_are_integers", invalid_customer_ids == 0, f"{invalid_customer_ids} invalid customer IDs"))
    checks.append(_check("signup_dates_are_valid", invalid_signup_dates == 0, f"{invalid_signup_dates} invalid signup dates"))

    unknown_customers = 0
    invalid_timestamps = 0
    invalid_numbers = 0
    invalid_statuses = 0
    for row in orders:
        try:
            if int(row["customer_id"]) not in valid_customer_ids:
                unknown_customers += 1
        except (KeyError, TypeError, ValueError):
            unknown_customers += 1
        try:
            datetime.fromisoformat(row["order_timestamp"])
        except (KeyError, TypeError, ValueError):
            invalid_timestamps += 1
        try:
            if int(row["quantity"]) <= 0 or float(row["unit_price"]) <= 0 or not 0 <= float(row["discount_pct"]) < 1:
                invalid_numbers += 1
        except (KeyError, TypeError, ValueError):
            invalid_numbers += 1
        if row.get("status") not in ALLOWED_STATUSES:
            invalid_statuses += 1
    checks.append(_check("orders_reference_known_customers", unknown_customers == 0, f"{unknown_customers} orders reference unknown customers"))
    checks.append(_check("order_timestamps_are_valid", invalid_timestamps == 0, f"{invalid_timestamps} invalid order timestamps"))
    checks.append(_check("order_numbers_are_valid", invalid_numbers == 0, f"{invalid_numbers} orders have invalid numeric values"))
    checks.append(_check("order_statuses_are_known", invalid_statuses == 0, f"{invalid_statuses} orders have unknown statuses"))

    passed = all(check["status"] == "passed" for check in checks)
    return {
        "status": "passed" if passed else "failed",
        "rows": {"customers": len(customers), "orders": len(orders)},
        "checks": checks,
        "data_note": "Synthetic deterministic demo data; this report checks CSV inputs before database loading.",
    }


def write_quality_report(data_dir: Path, report: dict[str, Any]) -> Path:
    report_path = data_dir / "quality_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report_path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data" / "generated"
    report = run_quality_checks(data_dir)
    report_path = write_quality_report(data_dir, report)
    print(f"Quality status: {report['status'].upper()}")
    for check in report["checks"]:
        print(f"- {check['status'].upper()}: {check['name']} — {check['details']}")
    print(f"Report written to {report_path}")
    if report["status"] != "passed":
        raise SystemExit(1)
