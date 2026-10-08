"""Tune and evaluate churn models with leakage-safe temporal CV."""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterator

import joblib
import mlflow
import psycopg
from scipy.stats import loguniform, randint
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import BaseCrossValidator, RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

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


class SnapshotTimeSeriesSplit(BaseCrossValidator):
    """Walk forward by complete snapshots, never splitting one snapshot."""

    def __init__(self, n_splits: int = 3) -> None:
        self.n_splits = n_splits

    def split(self, X: Any, y: Any = None, groups: Any = None) -> Iterator[tuple[list[int], list[int]]]:
        if groups is None:
            raise ValueError("SnapshotTimeSeriesSplit requires snapshot groups.")
        unique_groups = sorted(set(groups))
        if len(unique_groups) < self.n_splits + 1:
            raise ValueError("Not enough snapshots for the requested temporal folds.")
        for fold in range(self.n_splits):
            train_groups = set(unique_groups[: fold + 1])
            validation_group = unique_groups[fold + 1]
            train_indices = [index for index, group in enumerate(groups) if group in train_groups]
            validation_indices = [index for index, group in enumerate(groups) if group == validation_group]
            yield train_indices, validation_indices

    def get_n_splits(self, X: Any = None, y: Any = None, groups: Any = None) -> int:
        return self.n_splits


def build_snapshots(database_url: str) -> list[dict[str, Any]]:
    """Build historical customer snapshots from raw orders."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT customer_id, order_timestamp::date,
                    (quantity * unit_price * (1 - discount_pct))::float,
                    product_category, discount_pct::float
                FROM orders WHERE status = 'completed'
                ORDER BY order_timestamp"""
            )
            raw_orders = cursor.fetchall()
            cursor.execute("SELECT customer_id, signup_date FROM customers")
            signup_dates = {customer_id: signup_date for customer_id, signup_date in cursor.fetchall()}

    if not raw_orders:
        raise RuntimeError("Cannot train churn model without completed orders.")
    orders_by_customer: dict[int, list[tuple[date, float, str, float]]] = defaultdict(list)
    for customer_id, order_date, revenue, category, discount_pct in raw_orders:
        orders_by_customer[customer_id].append((order_date, revenue, category, discount_pct))

    first_date = min(order_date for _, order_date, _, _, _ in raw_orders)
    last_date = max(order_date for _, order_date, _, _, _ in raw_orders)
    cutoffs: list[date] = []
    cutoff = first_date + timedelta(days=120)
    while cutoff <= last_date - timedelta(days=60):
        cutoffs.append(cutoff)
        cutoff += timedelta(days=60)

    rows: list[dict[str, Any]] = []
    for cutoff in cutoffs:
        label_end = cutoff + timedelta(days=60)
        for customer_id, customer_orders in orders_by_customer.items():
            historical = [row for row in customer_orders if row[0] <= cutoff]
            if not historical:
                continue
            future = [order_date for order_date, _, _, _ in customer_orders if cutoff < order_date <= label_end]
            recent_30 = [row for row in historical if (cutoff - row[0]).days <= 30]
            recent_90 = [row for row in historical if (cutoff - row[0]).days <= 90]
            recent_90_revenue = [row[1] for row in recent_90]
            last_order_date = historical[-1][0]
            signup_date = signup_dates.get(customer_id, first_date)
            rows.append(
                {
                    "customer_id": customer_id,
                    "snapshot_date": cutoff.isoformat(),
                    "recency_days": (cutoff - last_order_date).days,
                    "orders_last_30d": len(recent_30),
                    "orders_last_90d": len(recent_90),
                    "revenue_last_90d": round(sum(recent_90_revenue), 2),
                    "average_order_value_90d": round(sum(recent_90_revenue) / len(recent_90_revenue), 2) if recent_90_revenue else 0.0,
                    "category_diversity_90d": len({row[2] for row in recent_90}),
                    "discount_rate_90d": round(sum(row[3] for row in recent_90) / len(recent_90), 4) if recent_90 else 0.0,
                    "tenure_days": (cutoff - signup_date).days,
                    "completed_orders_lifetime": len(historical),
                    "churned_next_60_days": int(not future),
                }
            )
    if len({row["snapshot_date"] for row in rows}) < 4:
        raise RuntimeError("Churn training requires at least four historical snapshots for temporal CV and testing.")
    return rows


def _metrics(y_true: list[int], probabilities: Any) -> dict[str, Any]:
    return {
        "roc_auc": float(roc_auc_score(y_true, probabilities)) if len(set(y_true)) > 1 else None,
        "average_precision": float(average_precision_score(y_true, probabilities)) if any(y_true) else None,
    }


def _search_spaces() -> list[tuple[str, Any, dict[str, Any]]]:
    """Small randomized spaces; each family is tuned with the same temporal folds."""
    return [
        (
            "logistic_regression",
            Pipeline([
                ("scale", StandardScaler()),
                ("model", LogisticRegression(class_weight="balanced", max_iter=1_000, random_state=42)),
            ]),
            {"model__C": loguniform(0.01, 100.0)},
        ),
        (
            "random_forest",
            RandomForestClassifier(class_weight="balanced", random_state=42, n_jobs=1),
            {
                "n_estimators": randint(200, 501),
                "max_depth": [3, 5, 8, None],
                "min_samples_leaf": randint(1, 8),
                "max_features": ["sqrt", "log2", 1.0],
            },
        ),
        (
            "extra_trees",
            ExtraTreesClassifier(class_weight="balanced", random_state=42, n_jobs=1),
            {
                "n_estimators": randint(200, 501),
                "max_depth": [3, 5, 8, None],
                "min_samples_leaf": randint(1, 8),
                "max_features": ["sqrt", "log2", 1.0],
            },
        ),
        (
            "hist_gradient_boosting",
            HistGradientBoostingClassifier(random_state=42),
            {
                "learning_rate": loguniform(0.02, 0.2),
                "max_leaf_nodes": randint(5, 31),
                "max_iter": randint(100, 301),
                "l2_regularization": loguniform(0.01, 10.0),
            },
        ),
    ]


def _json_safe_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: (float(value) if hasattr(value, "item") else value) for key, value in params.items()}


def _log_mlflow(metrics_path: Path, metrics: dict[str, Any], model_path: Path) -> str:
    tracking_path = metrics_path.parents[1] / "mlflow.db"
    artifact_path = metrics_path.parents[1] / "mlartifacts"
    artifact_path.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{tracking_path}")
    client = mlflow.MlflowClient()
    experiment = client.get_experiment_by_name("ecommerce-churn")
    if experiment is None:
        experiment_id = mlflow.create_experiment("ecommerce-churn", artifact_location=artifact_path.as_uri())
        mlflow.set_experiment(experiment_id=experiment_id)
    else:
        mlflow.set_experiment(experiment_id=experiment.experiment_id)
    with mlflow.start_run() as run:
        mlflow.log_params({
            "selected_model": metrics["model"],
            "selection_metric": metrics["selection_metric"],
            "cv_folds": metrics["cv_folds"],
            "feature_count": len(metrics["features"]),
        })
        for name in ("roc_auc", "average_precision", "baseline_average_precision"):
            if metrics.get(name) is not None:
                mlflow.log_metric(f"test_{name}", metrics[name])
        mlflow.log_artifact(str(metrics_path), artifact_path="reports")
        mlflow.log_artifact(str(model_path), artifact_path="models")
        return run.info.run_id


def train_churn_model(database_url: str, output_dir: Path) -> dict[str, Any]:
    rows = build_snapshots(database_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = output_dir / "churn_dataset.csv"
    with dataset_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    snapshots = sorted({row["snapshot_date"] for row in rows})
    test_snapshot = snapshots[-1]
    development_rows = [row for row in rows if row["snapshot_date"] < test_snapshot]
    test_rows = [row for row in rows if row["snapshot_date"] == test_snapshot]
    development_snapshots = sorted({row["snapshot_date"] for row in development_rows})
    cv_folds = min(3, len(development_snapshots) - 1)
    if cv_folds < 2:
        raise RuntimeError("Need at least three development snapshots for temporal CV.")
    if len({row["churned_next_60_days"] for row in development_rows}) < 2:
        raise RuntimeError("Development snapshots contain only one churn class.")

    x_development = [[row[feature] for feature in FEATURES] for row in development_rows]
    y_development = [row["churned_next_60_days"] for row in development_rows]
    development_groups = [row["snapshot_date"] for row in development_rows]
    x_test = [[row[feature] for feature in FEATURES] for row in test_rows]
    y_test = [row["churned_next_60_days"] for row in test_rows]
    splitter = SnapshotTimeSeriesSplit(n_splits=cv_folds)

    searches: list[tuple[str, RandomizedSearchCV]] = []
    for family, estimator, parameter_distributions in _search_spaces():
        search = RandomizedSearchCV(
            estimator=estimator,
            param_distributions=parameter_distributions,
            n_iter=6,
            scoring="average_precision",
            cv=splitter,
            refit=True,
            random_state=42,
            n_jobs=1,
            error_score="raise",
        )
        search.fit(x_development, y_development, groups=development_groups)
        searches.append((family, search))

    best_name, best_search = max(searches, key=lambda item: item[1].best_score_)
    final_model = best_search.best_estimator_
    test_probabilities = final_model.predict_proba(x_test)[:, 1]
    test_metrics = _metrics(y_test, test_probabilities)
    permutation = permutation_importance(
        final_model,
        x_test,
        y_test,
        scoring="average_precision",
        n_repeats=10,
        random_state=42,
        n_jobs=1,
    )
    feature_importance = [
        {"feature": feature, "mean_decrease": round(float(decrease), 6)}
        for feature, decrease in sorted(zip(FEATURES, permutation.importances_mean), key=lambda item: item[1], reverse=True)
    ]
    candidate_results = [
        {
            "family": family,
            "cv_average_precision": float(search.best_score_),
            "best_params": _json_safe_params(search.best_params_),
        }
        for family, search in searches
    ]
    metrics = {
        "model": best_name,
        "features": list(FEATURES),
        "selection_metric": "average_precision",
        "cv_strategy": "walk-forward snapshot groups",
        "cv_folds": cv_folds,
        "development_snapshots": development_snapshots,
        "test_snapshot": test_snapshot,
        "development_rows": len(development_rows),
        "test_rows": len(test_rows),
        "candidate_results": candidate_results,
        "test_churn_rate": round(sum(y_test) / len(y_test), 4),
        "baseline_average_precision": round(sum(y_test) / len(y_test), 4),
        **test_metrics,
        "permutation_importance": feature_importance,
        "label_definition": "No completed order in the 60 days after the historical snapshot.",
        "warning": "Demonstration baseline on synthetic data; not a production decision system.",
    }
    metrics_path = output_dir / "churn_metrics.json"
    model_path = output_dir / "churn_model.joblib"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    joblib.dump({"model": final_model, "features": FEATURES, "metrics": metrics}, model_path)
    metrics["mlflow_run_id"] = _log_mlflow(metrics_path, metrics, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    metrics = train_churn_model(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL), root / "data" / "models")
    print(json.dumps(metrics, indent=2))
