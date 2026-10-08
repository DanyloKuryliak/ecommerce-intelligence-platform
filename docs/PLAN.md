# E-Commerce Intelligence: build plan

## Goal

Create a recruiter-friendly business-intelligence demo that explains how raw order records become useful metrics and ML predictions. All records are deterministic synthetic data generated with seed `42`; lifecycle profiles are used only inside the simulator and are never exposed as model features.

## Milestone 1 — the vertical slice we implement now

| Step | What it does | Done when |
| --- | --- | --- |
| 1. Data generator | Creates fake customers and orders with a repeatable random seed. | The same seed produces the same row counts and IDs. |
| 2. Database schema | Defines `customers` and `orders` tables and their relationship. | PostgreSQL starts with the tables present. |
| 3. Loader | Inserts the generated CSV files into PostgreSQL. | The database row counts match the generated CSV row counts. |
| 4. Analytics API | Calculates completed-order KPIs and chart series in SQL. | `/api/v1/dashboard` returns valid JSON. |
| 5. Dashboard | Calls the API and renders the KPIs/charts. | A browser displays the values from the API. |

## Checkpoint 2 — input data quality gate

Before the loader touches PostgreSQL, `pipeline/quality_checks.py` checks required fields, duplicate IDs, valid dates, numeric ranges, known customers, and allowed order statuses. A failed report makes `make load` stop. The dashboard also shows the latest quality status.

## Checkpoint 3 — analytics warehouse and customer segments

`make analytics` refreshes two derived tables after loading: `monthly_sales` for trend reporting and `customer_features` for customer-level behavior. Transparent rules label customers `No purchase`, `New` (recent, low-order-count), `At risk` (no recent order), `VIP` (high revenue), `Loyal` (high order count), or `Regular`. These are descriptive segments, not churn predictions.

## Checkpoint 4 — first ML baselines

`make ml` compares tuned logistic regression, random forest, extra trees, and histogram gradient boosting on a validation snapshot, selects by average precision, refits the winner before one untouched chronological test snapshot, and also evaluates a three-month moving-average revenue forecast. Both reports and artifacts are local, ignored model outputs; both include explicit warnings that synthetic-demo metrics are not production claims.

## Checkpoint 5 — behavior-rich synthetic data

The original generator made nearly every customer order at a similar rate, which left little signal for any model. The revised generator simulates stable customers, low-frequency customers, and customers whose activity decays after a hidden lifecycle point. The hidden profile is not stored; it only makes future order behavior meaningfully related to observable historical features.

## Checkpoint 6 — leakage-safe model selection and explanations

The churn pipeline now holds out the newest historical snapshot as a final test set. On older development snapshots it runs a small randomized hyperparameter search across logistic regression, random forest, extra trees, and histogram gradient boosting. Each candidate uses walk-forward snapshot folds: training only uses earlier snapshots than validation, so future behavior cannot leak backward into model selection. The winner is selected by average precision, evaluated once on the untouched test snapshot, and compared with the positive-rate baseline.

The saved report contains permutation importance, candidate parameters, the selected model, snapshot dates, and a local MLflow run ID. The API exposes those global explanations and simple per-customer reason flags alongside each score. This remains a portfolio demonstration on synthetic data, not a production retention decision system.

`make mlflow-ui` opens the local experiment browser at `http://localhost:5000`, backed by `data/mlflow.db` and artifacts under `data/mlartifacts/`.

## Checkpoint 7 — product insights and what-if analysis

The dashboard now includes product-category performance (orders, units, revenue, and average discount) and a small what-if sales scenario. The scenario applies a user-selected growth percentage to the baseline demand forecast through `/api/v1/forecast/what-if`; it is intentionally transparent and labelled as synthetic demonstration output.

## Checkpoint 8 — model monitoring and portfolio readiness

`make ml` now finishes by generating `model_monitoring.json`. It compares the newest customer snapshot with development history, reports prediction/high-risk rates, checks model performance against the baseline, and flags large feature shifts for review. The dashboard exposes model-family comparisons and these monitoring checks so a visitor can see both model quality and operational caveats.

## Data contract

### `customers`

One row is one synthetic customer. It has an ID, country, signup date, and acquisition channel. It contains no real person or contact data.

### `orders`

One row is one synthetic order line. `status = completed` contributes to revenue; cancelled orders remain in the data so the later quality layer can explain why they are excluded. Revenue is calculated as:

```text
quantity × unit price × (1 − discount percentage)
```

## What is deliberately out of scope

- Real customer data, payments, user accounts, and authentication.
- Churn or demand predictions before a time-aware training/evaluation design exists.
- Airflow, ClickHouse, and LightGBM before the simple pipeline has earned their complexity.
- A public deployment before the local system, provenance notes, and basic tests work.

## Acceptance checks

- `pytest` verifies deterministic generator behavior and the API's static health/dashboard shell.
- Docker Compose validates and PostgreSQL becomes healthy.
- The loader reports the inserted customer and order totals.
- `/api/v1/dashboard` returns values from PostgreSQL.
- The browser dashboard renders those values without manual copying.
- The quality command passes for generated data and fails for a deliberately broken order reference.
- `monthly_sales` contains one row per month and `customer_features` contains one row per customer.
- The API and dashboard show customer segment counts and top customers.
- Churn training uses features available before each snapshot, randomized search with walk-forward CV, and reports ROC-AUC/average precision on a later untouched snapshot.
- The churn artifact includes reproducible search results, permutation importance, and a local MLflow experiment record.
- The churn API returns reason flags and global feature importance with each customer score.
- The MLflow UI loads the recorded churn run and its model/report artifacts locally.
- The dashboard returns product performance rows and calculates a what-if forecast without mutating the baseline report.
- `make ml` produces a model monitoring report and the dashboard displays its health checks.
- Demand forecasting reports holdout error and produces three future monthly baseline values.
- The API exposes model status and a customer churn-score endpoint after local training.

## How to read the code without coding

Follow the arrows in this order: `pipeline/generate_demo_data.py` → `pipeline/load_demo_data.py` → `db/init.sql` → `api/app/main.py` → `web/index.html`. At each arrow, the output of the prior step becomes the input of the next.
