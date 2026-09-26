"""Tests for live prediction outcome validation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from live_validation import (
    LiveOutcomeResolver,
    LivePredictionEvaluator,
    LiveValidationJournal,
    OutcomeStatus,
)
from ml.models.logistic import MODEL_CLASSES


def _decision_row(timestamp: str = "2026-09-28T09:15:00+05:30") -> pd.Series:
    return pd.Series(
        {
            "timestamp": pd.Timestamp(timestamp),
            "symbol": "TEST",
            "close": 100.0,
            "atr_14": 1.0,
            "swing_low": 98.0,
            "support_20": 98.0,
            "swing_high": 102.0,
            "resistance_20": 102.0,
        }
    )


def _candles(
    closes: list[float],
    *,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
) -> pd.DataFrame:
    start = pd.Timestamp("2026-09-28T09:20:00+05:30")
    highs = highs or [value + 0.1 for value in closes]
    lows = lows or [value - 0.1 for value in closes]
    return pd.DataFrame(
        {
            "timestamp": [start + timedelta(minutes=5 * i) for i in range(len(closes))],
            "symbol": ["TEST"] * len(closes),
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1000.0] * len(closes),
        }
    )


def _prediction(resolver: LiveOutcomeResolver):
    return resolver.create_prediction(
        prediction_id="prediction-1",
        timestamp=pd.Timestamp("2026-09-28T09:15:00+05:30"),
        symbol="TEST",
        model_version="model-v1",
        feature_version="features-v1",
        dataset_version="dataset-v1",
        probabilities={
            MODEL_CLASSES[0]: 0.80,
            MODEL_CLASSES[1]: 0.10,
            MODEL_CLASSES[2]: 0.10,
        },
        generated_at=pd.Timestamp("2026-09-28T09:15:01+05:30"),
        decision_row=_decision_row(),
    )


def test_pending_until_complete_horizon() -> None:
    resolver = LiveOutcomeResolver()
    prediction = _prediction(resolver)

    candles = _candles([100.0] * 5)
    outcome = resolver.resolve(
        prediction,
        candles,
        resolved_at="2026-09-28T10:00:00+05:30",
    )

    assert outcome.status is OutcomeStatus.PENDING
    assert outcome.actual_class is None


def test_resolves_long_success_using_phase7_rules() -> None:
    resolver = LiveOutcomeResolver()
    prediction = _prediction(resolver)

    # Long target = 101.5. No barrier is touched before the sixth bar.
    closes = [100.0, 100.1, 100.2, 100.3, 100.4, 100.5,
              100.6, 100.7, 100.8, 100.9, 101.0, 101.6]
    highs = [value + 0.05 for value in closes]
    lows = [value - 0.05 for value in closes]
    candles = _candles(closes, highs=highs, lows=lows)

    outcome = resolver.resolve(
        prediction,
        candles,
        resolved_at="2026-09-28T10:30:00+05:30",
    )

    assert outcome.status is OutcomeStatus.RESOLVED
    assert outcome.actual_class == "LONG_SUCCESS"
    assert outcome.outcome_reason == "LONG_SUCCESS"
    assert outcome.outcome_bars == 12


def test_same_bar_ambiguity_is_conservative_no_edge() -> None:
    resolver = LiveOutcomeResolver()
    prediction = _prediction(resolver)

    closes = [100.0] * 12
    highs = [100.2] * 12
    lows = [99.8] * 12
    highs[0] = 101.6
    lows[0] = 98.4
    candles = _candles(closes, highs=highs, lows=lows)

    outcome = resolver.resolve(
        prediction,
        candles,
        resolved_at="2026-09-28T10:30:00+05:30",
    )

    assert outcome.status is OutcomeStatus.RESOLVED
    assert outcome.actual_class == "NO_EDGE"
    assert "AMBIGUOUS" in (outcome.outcome_reason or "")


def test_outcome_never_uses_prediction_timestamp_bar() -> None:
    resolver = LiveOutcomeResolver()
    prediction = _prediction(resolver)

    # The prediction bar itself breaches both barriers, but it is not eligible
    # because Phase 7 evaluates only timestamps strictly after the decision.
    prediction_bar = pd.DataFrame(
        {
            "timestamp": [prediction.timestamp],
            "symbol": ["TEST"],
            "open": [100.0],
            "high": [101.6],
            "low": [98.4],
            "close": [100.0],
            "volume": [1000.0],
        }
    )
    future = _candles([100.0] * 12)
    candles = pd.concat([prediction_bar, future], ignore_index=True)

    outcome = resolver.resolve(
        prediction,
        candles,
        resolved_at="2026-09-28T10:30:00+05:30",
    )

    assert outcome.actual_class == "NO_EDGE"
    assert outcome.outcome_bars == 12


def test_journal_and_evaluator_count_correct_and_incorrect(tmp_path) -> None:
    journal = LiveValidationJournal(tmp_path / "live-validation.jsonl")
    resolver = LiveOutcomeResolver()
    prediction = _prediction(resolver)
    journal.append_prediction(prediction)

    candles = _candles(
        [100.0] * 11 + [101.6],
        highs=[100.1] * 11 + [101.7],
        lows=[99.9] * 12,
    )
    resolved = resolver.resolve(
        prediction,
        candles,
        resolved_at="2026-09-28T10:30:00+05:30",
    )
    journal.append_outcome(resolved)

    second = resolver.create_prediction(
        prediction_id="prediction-2",
        timestamp=pd.Timestamp("2026-09-28T09:20:00+05:30"),
        symbol="TEST",
        model_version="model-v1",
        feature_version="features-v1",
        dataset_version="dataset-v1",
        probabilities={
            MODEL_CLASSES[0]: 0.10,
            MODEL_CLASSES[1]: 0.80,
            MODEL_CLASSES[2]: 0.10,
        },
        generated_at=pd.Timestamp("2026-09-28T09:20:01+05:30"),
        decision_row=_decision_row("2026-09-28T09:20:00+05:30"),
    )
    journal.append_prediction(second)
    wrong = resolved.__class__(
        prediction_id="prediction-2",
        status=OutcomeStatus.RESOLVED,
        actual_class="LONG_SUCCESS",
        outcome_timestamp=pd.Timestamp("2026-09-28T10:20:00+05:30"),
        outcome_bars=12,
        outcome_reason="LONG_SUCCESS",
        resolved_at=pd.Timestamp("2026-09-28T10:20:01+05:30"),
    )
    journal.append_outcome(wrong)

    report = LivePredictionEvaluator(journal).evaluate()

    assert report.total_predictions == 2
    assert report.resolved_predictions == 2
    assert report.pending_predictions == 0
    assert report.correct_predictions == 1
    assert report.incorrect_predictions == 1
    assert report.accuracy == 0.5
    assert int(np.asarray(report.confusion_matrix).sum()) == 2


def test_journal_rejects_duplicate_prediction(tmp_path) -> None:
    journal = LiveValidationJournal(tmp_path / "live-validation.jsonl")
    prediction = _prediction(LiveOutcomeResolver())
    journal.append_prediction(prediction)

    with pytest.raises(ValueError, match="already exists"):
        journal.append_prediction(prediction)
