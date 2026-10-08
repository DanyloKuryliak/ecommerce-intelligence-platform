"""BentoML service for the locally trained churn classifier."""

from __future__ import annotations

import os
from pathlib import Path

import bentoml
import joblib
from pydantic import BaseModel, Field

from ml.churn_model import FEATURES

MODEL_PATH = Path(os.getenv("CHURN_MODEL_PATH", Path(__file__).resolve().parents[1] / "data" / "models" / "churn_model.joblib"))


class CustomerFeatures(BaseModel):
    recency_days: float = Field(ge=0)
    orders_last_30d: float = Field(ge=0)
    orders_last_90d: float = Field(ge=0)
    revenue_last_90d: float = Field(ge=0)
    average_order_value_90d: float = Field(ge=0)
    category_diversity_90d: float = Field(ge=0)
    discount_rate_90d: float = Field(ge=0, le=1)
    tenure_days: float = Field(ge=0)
    completed_orders_lifetime: float = Field(ge=0)


class ChurnPrediction(BaseModel):
    churn_probability: float
    risk_band: str
    model: str
    model_run_id: str | None


@bentoml.service(resources={"cpu": "1"}, traffic={"timeout": 10})
class ChurnService:
    def __init__(self) -> None:
        if not MODEL_PATH.exists():
            raise RuntimeError("Train the churn model before starting BentoML.")
        artifact = joblib.load(MODEL_PATH)
        if tuple(artifact["features"]) != FEATURES:
            raise RuntimeError("Saved churn feature schema does not match the serving schema.")
        self.model = artifact["model"]
        self.metrics = artifact["metrics"]

    @bentoml.api
    def predict(self, customer: CustomerFeatures) -> ChurnPrediction:
        values = [getattr(customer, feature) for feature in FEATURES]
        probability = float(self.model.predict_proba([values])[0][1])
        return ChurnPrediction(
            churn_probability=round(probability, 4),
            risk_band="high" if probability >= 0.5 else "lower",
            model=self.metrics["model"],
            model_run_id=self.metrics.get("mlflow_run_id"),
        )
