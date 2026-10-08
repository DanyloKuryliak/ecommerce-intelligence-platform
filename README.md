# E-Commerce Intelligence

A locally runnable analytics and ML portfolio project for a **synthetic** online store. The public-demo build is a static Next.js site with precomputed results; all databases, orchestration, training, and model serving run on your computer.

```text
Synthetic CSV → quality gate → PostgreSQL ──→ customer segments + monthly sales
                                  │
                                  ├──→ ClickHouse → product performance
                                  └──→ LightGBM and other churn candidates → MLflow
                                                 │
                                                 └──→ BentoML → FastAPI → Next.js + Recharts
Airflow orchestrates the local refresh; demand forecasts and monitoring feed the same dashboard.
```

## What you can explore

- Completed-order revenue, orders, active customers, monthly trend, and customer segments.
- Twelve named products with revenue and month-over-month change from ClickHouse.
- Churn-model comparison, time-aware cross-validation, held-out test metrics, monitoring checks, and a live customer score routed through BentoML.
- A three-month revenue forecast and transparent growth what-if slider. The forecast is a baseline, **not** an optimized production model.

All values and people are simulated. Model scores demonstrate an engineering workflow, not business advice or a guarantee on real customers.

Latest verified local run (2026-10-08): 600 customers, 16,452 generated order lines, 15,464 completed orders, and $4.27M completed-order revenue matched across PostgreSQL and ClickHouse. Five churn model families were compared; Extra Trees won on cross-validation and scored 0.845 test average precision versus a 0.338 positive-rate baseline (test ROC AUC 0.946). The demand baseline had 14.0% holdout MAPE; monitoring reported `review`, which is shown rather than hidden. These numbers describe only this deterministic synthetic dataset.

## Run locally

Prerequisites: Docker Desktop, `uv`, Node.js/npm. The commands are documented so the system can be reproduced; the coding agent can run them for you.

```bash
cd apps/ecommerce-intelligence
cp .env.example .env
make setup
make data
make db-up
make ml
make airflow-up
make demo-snapshot
make test
```

`make ml` loads the data, builds analytics and the ClickHouse copy, trains/evaluates churn and demand, logs an MLflow run, and writes monitoring results. `make airflow-up` starts the local orchestration and MLflow UI; trigger the `ecommerce_intelligence_refresh` DAG at `http://127.0.0.1:8080` to rehearse the complete workflow. The DAG has a weekly schedule but starts paused, so Docker cannot silently overwrite a local run. Unpause it in Airflow only when you want automatic weekly refreshes.

For the live site, start these in separate terminals:

```bash
make run-bento
make run-api
cd frontend && npm ci && npm run dev
```

Open `http://127.0.0.1:3000`. Local endpoints: FastAPI `:8001`, BentoML `:3001`, MLflow `:5000`, Airflow `:8080`, PostgreSQL `:5433`, ClickHouse HTTP `:8123`. The frontend falls back to checked-in aggregate demo data if the local API is absent; live customer scoring requires all local services. To stop containers, `make db-down` (include `--profile orchestration` in Compose if you also started Airflow/MLflow).

## Code tour

| Folder | Role |
| --- | --- |
| `pipeline/`, `db/` | Generate, validate and load CSV; refresh PostgreSQL and ClickHouse. |
| `ml/` | Point-in-time training, forecasting and model monitoring. |
| `orchestration/` | Airflow DAG connecting the local stages. |
| `serving/`, `api/` | BentoML prediction service and FastAPI business endpoints. |
| `frontend/` | Next.js/Recharts dashboard and browser tests. |
| `web/demo-data.json` | Exported, aggregate-only public-demo snapshot. |
| `infra/`, `docs/` | Docker services and architecture/release details. |

Start reading at [the architecture guide](docs/ARCHITECTURE.md), then follow `pipeline/generate_demo_data.py` → `pipeline/load_demo_data.py` → `pipeline/sync_clickhouse.py` → `ml/churn_model.py` → `serving/service.py` → `api/app/main.py` → `frontend/app/dashboard.tsx`.

## Verification and publication

```bash
make test
cd frontend && npm run typecheck && npm run build && npm run test:e2e
```

The frontend's `out/` directory is the deployable static site. See [the release runbook](docs/DEPLOYMENT.md). No external deployment is performed automatically, and no raw synthetic customer/order rows, secrets, or model weights are committed. The original static `web/index.html` is retained as a legacy API-root view; Next.js is the primary UI.
