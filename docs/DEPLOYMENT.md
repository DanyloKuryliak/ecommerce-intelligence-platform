# Deployment runbook

## Local release check

From `apps/ecommerce-intelligence`:

```bash
make setup
make db-up
make ml
make test
make run-api
```

Then verify:

- `http://localhost:8001/` — dashboard
- `http://localhost:8001/health` — API health
- `http://localhost:8001/api/v1/dashboard` — analytics and model status
- `http://localhost:8001/api/v1/customers/1/churn-score` — online scoring
- `http://localhost:5000` — local MLflow UI

## Public deployment boundary

Deploy only the lightweight presentation/API layer. The `web/` directory now includes `demo-data.json`; when the live API is unavailable, the dashboard falls back to this static synthetic snapshot. This makes the frontend suitable for a free static host such as GitHub Pages, Cloudflare Pages, or Vercel. Keep PostgreSQL, training, MLflow, and model artifacts on the local machine unless a paid or explicitly approved cloud environment is selected.

Before publishing:

1. Confirm `.env`, `data/`, `.venv/`, and model artifacts are ignored.
2. Run `make ml` and `make test` locally.
3. Check that the dashboard labels all predictions as synthetic demonstrations.
4. Do not expose database credentials or local admin endpoints.
5. Record the deployed commit SHA in the project README.
