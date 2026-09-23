from __future__ import annotations

import pandas as pd
import pytest

from ml.prediction.contracts import PredictionProvenance
from ml.prediction.inference import PredictionInferenceRequest, PredictionInferenceService
from ml.prediction.storage import PredictionStore


class _FakePredictor:
    def predict(self, features: pd.DataFrame, *, identifiers: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({
            "timestamp": identifiers["timestamp"],
            "symbol": identifiers["symbol"],
            "long_probability": [0.6] * len(features),
            "short_probability": [0.2] * len(features),
            "no_edge_probability": [0.2] * len(features),
            "model_version": ["model-1"] * len(features),
        })


def _request() -> PredictionInferenceRequest:
    timestamp = pd.Timestamp("2026-09-23 09:15", tz="Asia/Kolkata")
    return PredictionInferenceRequest(
        features=pd.DataFrame({"feature": [1.0]}),
        identifiers=pd.DataFrame({"timestamp": [timestamp], "symbol": ["RELIANCE"]}),
        provenance=PredictionProvenance(
            model_version="model-1", model_family="logistic",
            dataset_version="dataset-1", feature_version="features-1",
            target_version="target-1", code_version="code-1",
        ),
    )


def test_inference_returns_prediction_contract_and_persists(tmp_path) -> None:
    store = PredictionStore(tmp_path / "predictions.jsonl")
    predictions = PredictionInferenceService(_FakePredictor(), store=store).predict(_request())
    assert len(predictions) == 1
    assert predictions[0].symbol == "RELIANCE"
    assert predictions[0].probabilities["LONG_SUCCESS"] == 0.6
    assert len(store.read()) == 1


def test_inference_request_rejects_row_mismatch() -> None:
    with pytest.raises(ValueError, match="equal row counts"):
        PredictionInferenceRequest(
            features=pd.DataFrame({"feature": [1.0, 2.0]}),
            identifiers=pd.DataFrame({
                "timestamp": [pd.Timestamp("2026-09-23 09:15", tz="Asia/Kolkata")],
                "symbol": ["RELIANCE"],
            }),
            provenance=_request().provenance,
        )


def test_inference_binds_deterministic_input_lineage() -> None:
    request = _request()
    prediction = PredictionInferenceService(_FakePredictor()).predict(request)[0]

    assert prediction.lineage is not None
    assert prediction.lineage.source_type == "prediction_inference_request"
    assert prediction.lineage.feature_names == ("feature",)
    assert len(prediction.lineage.feature_hash) == 64
    assert prediction.lineage.input_timestamp == request.identifiers.iloc[0]["timestamp"]


def test_inference_rejects_predictor_identifier_mismatch() -> None:
    class _BadPredictor(_FakePredictor):
        def predict(self, features: pd.DataFrame, *, identifiers: pd.DataFrame) -> pd.DataFrame:
            result = super().predict(features, identifiers=identifiers)
            result.loc[0, "symbol"] = "TCS"
            return result

    with pytest.raises(ValueError, match="identifiers do not match"):
        PredictionInferenceService(_BadPredictor()).predict(_request())
