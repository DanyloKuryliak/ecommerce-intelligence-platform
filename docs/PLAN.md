# E-Commerce Intelligence — project checklist

Goal: a recruiter-friendly, fully rehearsable **local** data/ML system plus a lightweight static public demo. All data is deterministic and synthetic; hidden lifecycle profiles in the simulator are never used as model features.

## Local build

- [x] Generate customer, product, and order CSVs; reject missing, duplicate, invalid, and mismatched records before database load.
- [x] Load PostgreSQL tables and refresh monthly sales and customer segments.
- [x] Copy completed order lines to ClickHouse and verify row/revenue parity; show named-product performance.
- [x] Train churn candidates, including LightGBM, using randomized configurations, forward-only snapshot cross-validation, and a later untouched test snapshot.
- [x] Track the chosen model's metrics/artifacts in MLflow; serve scores through BentoML and FastAPI.
- [x] Build a demand baseline, transparent what-if scenario, and batch model-monitoring report.
- [x] Orchestrate the whole refresh with a locally tested Airflow DAG.
- [x] Build a responsive Next.js/Recharts frontend and an aggregate-only static snapshot.
- [x] Run Python tests, frontend type/build checks, browser checks, and API/service smoke tests.

## Publication boundary

- [ ] Publish the static `frontend/out/` site after explicit host/account review; record its URL and deployed commit.

The local project can be complete without claiming a public URL that has not been created. The static demo never exposes live model scoring; that feature is local-only.

## Data and model contract

`customers` contains synthetic IDs, signup dates, country, and acquisition channel. `products` maps product ID to name/category. `orders` is one synthetic order line; only `status = completed` contributes to revenue. Revenue = `quantity × unit_price × (1 − discount_pct)`.

The churn entity is a customer at a historical snapshot; the label is no completed order in the following 60 days. Features are derived only from data available at that snapshot. Candidate selection uses average precision on walk-forward folds; final test metrics are calculated once on a later held-out snapshot. Demand uses a simple moving-average baseline. Scores on this fabricated dataset are not evidence of real-world performance.

## How to read it

Follow `pipeline/` → `db/` → `ml/` → `serving/` → `api/` → `frontend/`. The [architecture guide](ARCHITECTURE.md) explains the handoffs; the [runbook](DEPLOYMENT.md) gives exact checks.
