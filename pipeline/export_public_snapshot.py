"""Export only synthetic dashboard aggregates for the static public demo."""

from __future__ import annotations

import json
import os
from pathlib import Path

from api.app.main import DEFAULT_DATABASE_URL, get_dashboard


def export_snapshot(database_url: str, output_path: Path) -> dict:
    dashboard = get_dashboard(database_url)
    snapshot = {
        "kpis": dashboard["kpis"],
        "monthly_revenue": dashboard["monthly_revenue"],
        "category_revenue": dashboard["category_revenue"],
        "product_performance": dashboard["product_performance"],
        "analytics": {"segments": dashboard["analytics"]["segments"]},
        "ml_status": dashboard["ml_status"],
        "data_note": dashboard["data_note"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return snapshot


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "web" / "demo-data.json"
    result = export_snapshot(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL), target)
    print(f"Exported {len(result['product_performance'])} products to {target}.")
