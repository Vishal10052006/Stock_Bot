"""Phase 9 prediction monitoring contract.

This module stores prediction telemetry only. It does not evaluate P&L,
authorize trades, or alter model state.

References:
    docs/PHASE_9_ML.md
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class PredictionTelemetry:
    """Immutable record of one inference event."""

    timestamp: pd.Timestamp
    symbol: str
    model_version: str
    feature_version: str
    long_probability: float
    short_probability: float
    no_edge_probability: float
    predicted_class: str
    regime: str | None = None

    def __post_init__(self) -> None:
        """Validate the monitoring payload without adding trading authority."""
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")

        probabilities = (
            float(self.long_probability),
            float(self.short_probability),
            float(self.no_edge_probability),
        )
        if not all(pd.notna(value) for value in probabilities):
            raise ValueError("prediction probabilities must be finite")
        if not all(0.0 <= value <= 1.0 for value in probabilities):
            raise ValueError("prediction probabilities must lie in [0, 1]")
        if abs(sum(probabilities) - 1.0) > 1e-8:
            raise ValueError("prediction probabilities must sum to 1")
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if not self.model_version.strip():
            raise ValueError("model_version must not be empty")
        if not self.feature_version.strip():
            raise ValueError("feature_version must not be empty")
        if self.predicted_class not in {
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
        }:
            raise ValueError("predicted_class must be a canonical Phase 9 class")
