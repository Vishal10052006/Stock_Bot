"""Run deterministic non-network checks for live prediction validation.

This validates the newly added journal/resolver/evaluator components without
opening an Upstox connection or submitting broker orders.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import tempfile

import pandas as pd

from live_validation import (
    LiveOutcomeResolver,
    LivePredictionEvaluator,
    LiveValidationJournal,
    OutcomeStatus,
)
from ml.models.logistic import MODEL_CLASSES


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


def _candles() -> pd.DataFrame:
    start = pd.Timestamp("2026-09-28T09:20:00+05:30")
    closes = [100.0] * 11 + [101.6]
    return pd.DataFrame(
        {
            "timestamp": [
                start + timedelta(minutes=5 * i)
                for i in range(12)
            ],
            "symbol": ["TEST"] * 12,
            "open": closes,
            "high": [100.1] * 11 + [101.7],
            "low": [99.9] * 12,
            "close": closes,
            "volume": [1000.0] * 12,
        }
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="stock-bot-live-validation-") as tmp:
        journal = LiveValidationJournal(
            Path(tmp) / "predictions.jsonl"
        )
        resolver = LiveOutcomeResolver()

        prediction = resolver.create_prediction(
            prediction_id=journal.prediction_id(
                timestamp=_decision_row()["timestamp"],
                symbol="TEST",
                model_version="model-v1",
            ),
            timestamp=_decision_row()["timestamp"],
            symbol="TEST",
            model_version="model-v1",
            feature_version="feature-v1",
            dataset_version="dataset-v1",
            probabilities={
                MODEL_CLASSES[0]: 0.8,
                MODEL_CLASSES[1]: 0.1,
                MODEL_CLASSES[2]: 0.1,
            },
            generated_at=pd.Timestamp(
                "2026-09-28T09:15:01+05:30"
            ),
            decision_row=_decision_row(),
        )

        journal.append_prediction(prediction)

        outcome = resolver.resolve(
            prediction,
            _candles(),
            resolved_at="2026-09-28T10:30:00+05:30",
        )
        if outcome.status is not OutcomeStatus.RESOLVED:
            raise RuntimeError("expected complete test horizon to resolve")

        journal.append_outcome(outcome)

        report = LivePredictionEvaluator(journal).evaluate()

        print("LIVE VALIDATION CONTRACT CHECK")
        print(f"total_predictions={report.total_predictions}")
        print(f"resolved_predictions={report.resolved_predictions}")
        print(f"pending_predictions={report.pending_predictions}")
        print(f"correct_predictions={report.correct_predictions}")
        print(f"incorrect_predictions={report.incorrect_predictions}")
        print(f"accuracy={report.accuracy}")
        print("PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
