from __future__ import annotations

import pandas as pd
import pytest

from ml.prediction.failures import PredictionFailure, PredictionFailureStore


def _failure() -> PredictionFailure:
    return PredictionFailure(
        timestamp=pd.Timestamp("2026-09-24 09:15", tz="Asia/Kolkata"),
        symbol="RELIANCE",
        code="MISSING_FEATURE",
        message="required feature RSI_14 is unavailable",
        model_version="model-1",
        feature_version="features-1",
        dataset_version="dataset-1",
    )


def test_prediction_failure_is_explicit_and_persisted(tmp_path) -> None:
    store = PredictionFailureStore(tmp_path / "failures.jsonl")
    store.append(_failure())
    frame = store.read()

    assert len(frame) == 1
    assert frame.iloc[0]["code"] == "MISSING_FEATURE"
    assert frame.iloc[0]["symbol"] == "RELIANCE"


def test_prediction_failure_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PredictionFailure(
            timestamp=pd.Timestamp("2026-09-24 09:15"),
            symbol="RELIANCE",
            code="INVALID_TIMESTAMP",
            message="timestamp is naive",
            model_version="model-1",
            feature_version="features-1",
            dataset_version="dataset-1",
        )
