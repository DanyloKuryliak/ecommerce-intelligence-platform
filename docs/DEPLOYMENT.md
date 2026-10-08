# Local verification and static release

1. From the project folder, run `make setup`, `make data`, `make db-up`, `make ml`, `make airflow-up`, and trigger `ecommerce_intelligence_refresh` in the local Airflow UI. Check the run and each task succeeded.
2. Run `make demo-snapshot`, `make test`, then in `frontend/` run `npm ci`, `npm run typecheck`, `npm run build`, and `npm run test:e2e`.
3. Verify locally: Next.js `http://127.0.0.1:3000`; API `/health`, `/api/v1/dashboard`, `/api/v1/product-performance`, and `/api/v1/customers/1/churn-score` on port 8001; BentoML `/readyz` on port 3001; MLflow on port 5000. Compare PostgreSQL/ClickHouse row and revenue totals from `make warehouse`.
4. Review `web/demo-data.json` and `frontend/out/` for synthetic aggregates only. Confirm `.env`, `data/`, `.venv/`, `node_modules/`, `.next/`, `out/`, and model weights remain ignored.
5. Publish `frontend/out/` to a static host only after reviewing the host and costs. Do not expose local database, Airflow, MLflow, or BentoML ports publicly. Record the deployed URL and commit after publication; this repository does not imply that a public site has already been deployed.

The public build can show KPIs, product analysis, model comparisons, monitoring, and the what-if slider from the saved snapshot. Live customer scoring is intentionally local-only. Changing the source dataset requires a fresh full pipeline, snapshot export, build, and release.
