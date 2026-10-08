# E-Commerce Intelligence Platform

Status: **portfolio MVP complete — local system and public-demo package ready**.

This project will grow from a small, honest analytics application into an MLOps portfolio project. We start with synthetic data so no customer information, orders, or credentials are involved. The generator now simulates different customer lifecycles—stable, low-frequency, and decaying activity—so the ML task has meaningful behavior to learn.

## What works in this milestone

```text
Deterministic fake store data
        ↓
PostgreSQL (local Docker container)
        ↓
FastAPI analytics API
        ↓
Simple browser dashboard
```

The dashboard shows completed-order revenue, order count, active customers, average order value, monthly revenue, and category revenue. The local API also exposes clearly labelled demonstration churn and demand reports after `make ml`.

## Code tour — what each folder means

| Folder | Plain-language role |
| --- | --- |
| `pipeline/` | Creates fake but realistic-looking customers and orders, then loads them into the database. |
| `db/` | Defines the two database tables. Think of it as the database blueprint. |
| `infra/` | Starts PostgreSQL in Docker, isolated from the rest of your computer. |
| `api/` | Reads completed orders, calculates KPIs, and provides them to the browser. |
| `web/` | The small dashboard page people will see. |
| `docs/` | The plan, data contract, and later model/evaluation records. |

## Run it locally

You do not need to type these during our collaboration—I run them. They are here so you can understand the sequence:

```bash
cd apps/ecommerce-intelligence
cp .env.example .env
make setup
make data
make db-up
make load
make analytics
make ml
make test
make run-api
```

Then open `http://localhost:8001`. The first run downloads the Python libraries and the database image; later runs are much faster. To stop PostgreSQL: `make db-down`.

## ML checkpoint

`make ml` now trains churn with randomized hyperparameter search, walk-forward snapshot cross-validation, an untouched chronological test snapshot, permutation importance, and a local MLflow run in `data/mlflow.db` with artifacts under `data/mlartifacts/`. The API returns a score plus human-readable demonstration reasons and the global importance report.

To inspect the recorded experiment in a browser, run `make mlflow-ui` and open `http://localhost:5000`. The UI reads the local SQLite tracking database and shows the selected model, candidate metrics, parameters, and saved artifacts. It is a development tool; it is not part of the public demo deployment.

The dashboard also shows product-category performance and supports a transparent forecast what-if scenario, for example applying +10% growth to the baseline forecast.

`make ml` also generates a monitoring report comparing the newest snapshot with development history. It reports prediction rates, baseline comparison, and feature shifts requiring review; these checks are visible in the dashboard alongside model-family comparisons.

## Next milestones

1. Optional: publish the lightweight precomputed demo using [the deployment runbook](docs/DEPLOYMENT.md).
2. Optional: replace local PostgreSQL/MLflow with managed services for cloud-learning purposes.

The local portfolio scope is complete: the project has a reproducible data pipeline, analytics API, interactive dashboard, supervised churn model, demand forecast baseline, what-if analysis, model monitoring, MLflow tracking, tests, CI, and deployment documentation.

For a static public demo, publish the `web/` directory. It uses the live API when available and falls back to the checked-in synthetic `web/demo-data.json` snapshot when it is hosted without a backend.
