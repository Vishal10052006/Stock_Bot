"""Versioned, prediction-only inference boundary.

The service validates decision-time feature rows, invokes a supplied model
adapter, attaches provenance, and optionally persists telemetry. It never
constructs labels, reads future outcomes, chooses trades, sizes positions,
or calls a broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from ml.prediction.contracts import ClassificationPrediction, PredictionProvenance
from ml.prediction.storage import PredictionRecord, PredictionStore


class ClassificationPredictor(Protocol):
    def predict(self, features: pd.DataFrame, *, identifiers: pd.DataFrame) -> pd.DataFrame:
        ...


@dataclass(frozen=True, slots=True)
class PredictionInferenceRequest:
    features: pd.DataFrame
    identifiers: pd.DataFrame
    provenance: PredictionProvenance

    def __post_init__(self) -> None:
        if not isinstance(self.features, pd.DataFrame):
            raise TypeError("features must be a pandas DataFrame")
        if not isinstance(self.identifiers, pd.DataFrame):
            raise TypeError("identifiers must be a pandas DataFrame")
        if len(self.features) != len(self.identifiers):
            raise ValueError("features and identifiers must have equal row counts")
        required = {"timestamp", "symbol"}
        if not required.issubset(self.identifiers.columns):
            raise ValueError("identifiers must contain timestamp and symbol")


class PredictionInferenceService:
    """Execute one deterministic classification inference request."""

    api_version = "prediction-inference-v1"

    def __init__(self, predictor: ClassificationPredictor, *, store: PredictionStore | None = None) -> None:
        self.predictor = predictor
        self.store = store

    def predict(self, request: PredictionInferenceRequest) -> tuple[ClassificationPrediction, ...]:
        result = self.predictor.predict(request.features, identifiers=request.identifiers)
        expected = {
            "timestamp", "symbol", "long_probability", "short_probability",
            "no_edge_probability", "model_version",
        }
        if not expected.issubset(result.columns):
            raise ValueError("predictor returned an invalid classification schema")
        if len(result) != len(request.features):
            raise ValueError("predictor returned an unexpected row count")

        predictions: list[ClassificationPrediction] = []
        for _, row in result.iterrows():
            prediction = ClassificationPrediction(
                timestamp=pd.Timestamp(row["timestamp"]),
                symbol=str(row["symbol"]),
                probabilities={
                    "LONG_SUCCESS": float(row["long_probability"]),
                    "SHORT_SUCCESS": float(row["short_probability"]),
                    "NO_EDGE": float(row["no_edge_probability"]),
                },
                provenance=request.provenance,
            )
            predictions.append(prediction)
            if self.store is not None:
                self.store.append(
                    PredictionRecord(
                        timestamp=prediction.timestamp,
                        symbol=prediction.symbol,
                        model_version=request.provenance.model_version,
                        dataset_version=request.provenance.dataset_version,
                        feature_version=request.provenance.feature_version,
                        generated_at=pd.Timestamp.now(tz="UTC"),
                        prediction_type="classification",
                        payload={
                            "p_long": prediction.probabilities["LONG_SUCCESS"],
                            "p_short": prediction.probabilities["SHORT_SUCCESS"],
                            "p_no_edge": prediction.probabilities["NO_EDGE"],
                            "api_version": self.api_version,
                        },
                    )
                )
        return tuple(predictions)
