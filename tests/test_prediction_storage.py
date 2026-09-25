from __future__ import annotations

import pandas as pd
import pytest

from ml.prediction.storage import PredictionRecord, PredictionStore


def _record() -> PredictionRecord:
    return PredictionRecord(
        timestamp=pd.Timestamp("2026-09-23 09:15", tz="Asia/Kolkata"),
        symbol="RELIANCE",
        model_version="model-1",
        dataset_version="dataset-1",
        feature_version="features-1",
        generated_at=pd.Timestamp("2026-09-23 09:16", tz="Asia/Kolkata"),
        prediction_type="classification",
        payload={"p_long": 0.4, "p_short": 0.2, "p_no_edge": 0.4},
    )


def test_prediction_store_round_trip(tmp_path) -> None:
    store = PredictionStore(tmp_path / "predictions.jsonl")
    store.append(_record())

    frame = store.read()

    assert len(frame) == 1
    assert frame.iloc[0]["symbol"] == "RELIANCE"
    assert frame.iloc[0]["model_version"] == "model-1"
    assert frame.iloc[0]["payload"]["p_long"] == 0.4


def test_prediction_record_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PredictionRecord(
            timestamp=pd.Timestamp("2026-09-23 09:15"),
            symbol="RELIANCE",
            model_version="model-1",
            dataset_version="dataset-1",
            feature_version="features-1",
            generated_at=pd.Timestamp("2026-09-23 09:16", tz="Asia/Kolkata"),
            prediction_type="classification",
            payload={},
        )


def test_store_starts_empty(tmp_path) -> None:
    frame = PredictionStore(tmp_path / "missing.jsonl").read()
    assert frame.empty
