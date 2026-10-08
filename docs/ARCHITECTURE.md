# Architecture

## Local development

```text
generate_demo_data.py
        ↓ CSV
quality_checks.py
        ↓ validated CSV
load_demo_data.py → PostgreSQL
        ↓
build_analytics.py → monthly_sales + customer_features
        ↓
FastAPI → web/index.html
        ↓
churn_model.py + demand_forecast.py
        ↓
model_monitoring.py + MLflow
```

PostgreSQL is the system of record for the local demo. The ML jobs build point-in-time customer snapshots from completed orders, keep the newest snapshot untouched for evaluation, and save versioned reports/artifacts under ignored local `data/` paths.

## Prediction contract

- Churn entity: one customer at one historical snapshot.
- Churn label: no completed order in the following 60 days.
- Churn features: only orders available on or before the snapshot date.
- Evaluation: walk-forward snapshot cross-validation plus one newest-snapshot holdout.
- Demand output: three future monthly revenue values from a baseline model.
- API fallback: endpoints return `503` when the required local model/report is absent.

## Public-demo boundary

The public layer should stay lightweight: serve a precomputed synthetic snapshot or a small API deployment. PostgreSQL, MLflow, retraining, and generated model artifacts remain local infrastructure. No secrets, customer records, or model weights belong in source control.
