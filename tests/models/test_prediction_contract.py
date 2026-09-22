"""Tests for Phase 9 prediction and monitoring contracts."""

from __future__ import annotations

import pandas as pd
import pytest

from ml.prediction.models import SignalPrediction
from ml.prediction.monitoring import PredictionTelemetry


def test_signal_prediction_accepts_valid_probabilities() -> None:
    """A valid calibrated probability vector is accepted."""
    prediction = SignalPrediction(
        timestamp=pd.Timestamp("2026-09-22 10:25:00+05:30"),
        symbol="RELIANCE",
        long_probability=0.70,
        short_probability=0.10,
        no_edge_probability=0.20,
    )

    assert prediction.model_version == "phase9-signal-v1.0"


@pytest.mark.parametrize(
    "probabilities",
    [
        (0.70, 0.10, 0.10),
        (1.10, -0.10, 0.00),
    ],
)
def test_signal_prediction_rejects_invalid_probability_vectors(probabilities) -> None:
    """Probability mass must be a finite simplex."""
    with pytest.raises(ValueError):
        SignalPrediction(
            timestamp=pd.Timestamp("2026-09-22 10:25:00+05:30"),
            symbol="RELIANCE",
            long_probability=probabilities[0],
            short_probability=probabilities[1],
            no_edge_probability=probabilities[2],
        )


def test_signal_prediction_requires_timezone_aware_timestamp() -> None:
    """Decision timestamps must remain explicitly timezone-aware."""
    with pytest.raises(ValueError, match="timezone-aware"):
        SignalPrediction(
            timestamp=pd.Timestamp("2026-09-22 10:25:00"),
            symbol="RELIANCE",
            long_probability=0.70,
            short_probability=0.10,
            no_edge_probability=0.20,
        )


def test_prediction_telemetry_is_prediction_only() -> None:
    """Monitoring contains probabilities and metadata, not trade authority."""
    telemetry = PredictionTelemetry(
        timestamp=pd.Timestamp("2026-09-22 10:25:00+05:30"),
        symbol="RELIANCE",
        model_version="phase9-signal-v1.0",
        feature_version="v1.0",
        long_probability=0.70,
        short_probability=0.10,
        no_edge_probability=0.20,
        predicted_class="LONG_SUCCESS",
        regime="TREND_UP",
    )

    assert telemetry.predicted_class == "LONG_SUCCESS"


def test_prediction_telemetry_rejects_invalid_probability_mass() -> None:
    """Monitoring must fail closed on malformed model output."""
    with pytest.raises(ValueError, match="sum to 1"):
        PredictionTelemetry(
            timestamp=pd.Timestamp("2026-09-22 10:25:00+05:30"),
            symbol="RELIANCE",
            model_version="phase9-signal-v1.0",
            feature_version="v1.0",
            long_probability=0.80,
            short_probability=0.10,
            no_edge_probability=0.20,
            predicted_class="LONG_SUCCESS",
        )
