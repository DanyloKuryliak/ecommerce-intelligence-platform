# Architecture and boundaries

The local system of record is PostgreSQL (`customers`, `products`, `orders`). A quality gate checks generated CSVs before load. `monthly_sales` and `customer_features` are derived PostgreSQL tables. ClickHouse holds an analytical copy of **completed** order lines, including product IDs/names; the sync fails on row-count or revenue mismatch. The API combines PostgreSQL business metrics with ClickHouse product results.

The Airflow DAG runs generate → validate → load, then analytics, ClickHouse sync and churn training; demand forecasting follows analytics, and monitoring follows churn. MLflow records the selected churn model's metrics and artifacts. BentoML loads the saved model and handles typed prediction requests; FastAPI assembles the customer's current features, calls BentoML, and adds transparent reason flags. The Next.js site requests FastAPI only on localhost and otherwise uses the checked-in synthetic aggregate snapshot.

Churn is defined as no completed order in the 60 days after a snapshot. Training features use only history available at that snapshot. Model selection uses older walk-forward snapshots; the newest snapshot is an untouched test. Average precision is the selection metric because churn is imbalanced; ROC AUC, prevalence baseline, parameters, and permutation importance are also reported. LightGBM is a candidate alongside tree ensembles and logistic regression, but is not forced to win. The simple demand model is a three-month moving average evaluated on historical holdout months.

Monitoring reports prediction/high-risk rates, baseline comparison and large feature shifts. It is batch evaluation on synthetic snapshots, not a live production alert system. The what-if slider applies a percentage to baseline forecast values; it does not retrain the model.

Local services bind to loopback where feasible. The static deployment contains no database, Airflow, MLflow, BentoML, raw customer rows, or model weights. No real customer data or production retention decisions are supported.
