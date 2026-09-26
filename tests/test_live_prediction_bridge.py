from __future__ import annotations

import pandas as pd

from live_validation import (
    LivePredictionValidationBridge,
    LiveValidationJournal,
)
from ml.models.logistic import MODEL_CLASSES
from ml.prediction.contracts import (
    ClassificationPrediction,
    PredictionProvenance,
)


def _prediction() -> ClassificationPrediction:
    return ClassificationPrediction(
        timestamp=pd.Timestamp("2026-09-28T09:15:00+05:30"),
        symbol="TEST",
        probabilities={
            MODEL_CLASSES[0]: 0.8,
            MODEL_CLASSES[1]: 0.1,
            MODEL_CLASSES[2]: 0.1,
        },
        provenance=PredictionProvenance(
            model_version="model-v1",
            model_family="logistic",
            dataset_version="dataset-v1",
            feature_version="feature-v1",
            target_version="phase7-v1",
            code_version="test",
        ),
    )


def _decision_row() -> pd.Series:
    return pd.Series(
        {
            "timestamp": pd.Timestamp("2026-09-28T09:15:00+05:30"),
            "symbol": "TEST",
            "close": 100.0,
            "atr_14": 1.0,
            "swing_low": 98.0,
            "support_20": 98.0,
            "swing_high": 102.0,
            "resistance_20": 102.0,
        }
    )


def test_bridge_records_prediction_and_keeps_prediction_layer_separate(tmp_path):
    journal = LiveValidationJournal(tmp_path / "live.jsonl")
    bridge = LivePredictionValidationBridge(journal)

    recorded = bridge.record_prediction(_prediction(), _decision_row())

    assert recorded.prediction_id
    events = journal.read_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "PREDICTION"
    assert events[0]["predicted_class"] == "LONG_SUCCESS"
