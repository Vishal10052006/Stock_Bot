"""Model-neutral Prediction Bot contracts beyond Phase 9 classification.

These contracts carry probabilistic information only. They deliberately do
not contain trade direction, position sizing, risk authorization, or orders.

The contracts are designed so later return-forecasting, multi-horizon, and
uncertainty models can plug into the same prediction boundary without
changing the Strategy Engine contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from ml.models.logistic import MODEL_CLASSES


@dataclass(frozen=True, slots=True)
class PredictionProvenance:
    """Traceability metadata for one prediction artifact or inference event."""

    model_version: str
    model_family: str
    dataset_version: str
    feature_version: str
    target_version: str
    code_version: str
    calibration_version: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("model_version", self.model_version),
            ("model_family", self.model_family),
            ("dataset_version", self.dataset_version),
            ("feature_version", self.feature_version),
            ("target_version", self.target_version),
            ("code_version", self.code_version),
        ):
            if not str(value).strip():
                raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True, slots=True)
class ClassificationPrediction:
    """Calibrated event probabilities for the canonical Phase 9 outcomes."""

    timestamp: pd.Timestamp
    symbol: str
    probabilities: Mapping[str, float]
    provenance: PredictionProvenance
    uncertainty: float | None = None

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if not str(self.symbol).strip():
            raise ValueError("symbol must not be empty")

        values = {str(key): float(value) for key, value in self.probabilities.items()}
        if tuple(values) != MODEL_CLASSES:
            raise ValueError(
                "probabilities must use the canonical Phase 9 class order"
            )
        if not all(pd.notna(value) and 0.0 <= value <= 1.0 for value in values.values()):
            raise ValueError("probabilities must be finite and lie in [0, 1]")
        if abs(sum(values.values()) - 1.0) > 1e-8:
            raise ValueError("probabilities must sum to 1")

        if self.uncertainty is not None:
            uncertainty = float(self.uncertainty)
            if not pd.notna(uncertainty) or uncertainty < 0.0:
                raise ValueError("uncertainty must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ReturnForecast:
    """Expected-return forecast for one explicitly defined horizon."""

    timestamp: pd.Timestamp
    symbol: str
    horizon_minutes: int
    expected_return: float
    uncertainty: float | None
    provenance: PredictionProvenance
    interval_lower: float | None = None
    interval_upper: float | None = None
    interval_confidence: float | None = None

    def __post_init__(self) -> None:
        if pd.Timestamp(self.timestamp).tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if not str(self.symbol).strip():
            raise ValueError("symbol must not be empty")
        if self.horizon_minutes <= 0:
            raise ValueError("horizon_minutes must be greater than zero")
        if not pd.notna(float(self.expected_return)):
            raise ValueError("expected_return must be finite")

        if self.uncertainty is not None and (
            not pd.notna(float(self.uncertainty)) or float(self.uncertainty) < 0.0
        ):
            raise ValueError("uncertainty must be finite and non-negative")

        if self.interval_lower is not None and not pd.notna(float(self.interval_lower)):
            raise ValueError("interval_lower must be finite")
        if self.interval_upper is not None and not pd.notna(float(self.interval_upper)):
            raise ValueError("interval_upper must be finite")

        if (self.interval_lower is None) != (self.interval_upper is None):
            raise ValueError("interval_lower and interval_upper must be provided together")

        if self.interval_lower is not None and self.interval_upper is not None:
            lower = float(self.interval_lower)
            upper = float(self.interval_upper)
            expected = float(self.expected_return)
            if lower > upper:
                raise ValueError("interval_lower must not exceed interval_upper")
            if not lower <= expected <= upper:
                raise ValueError("expected_return must lie inside the prediction interval")

        if self.interval_confidence is not None:
            confidence = float(self.interval_confidence)
            if not 0.0 < confidence < 1.0:
                raise ValueError("interval_confidence must lie in (0, 1)")
            if self.interval_lower is None:
                raise ValueError("interval_confidence requires a prediction interval")


@dataclass(frozen=True, slots=True)
class MultiHorizonForecast:
    """Collection of return forecasts sharing one decision timestamp."""

    forecasts: tuple[ReturnForecast, ...]

    def __post_init__(self) -> None:
        if not self.forecasts:
            raise ValueError("forecasts must not be empty")
        first = self.forecasts[0]
        horizons = [forecast.horizon_minutes for forecast in self.forecasts]
        if len(set(horizons)) != len(horizons):
            raise ValueError("horizon_minutes must be unique")
        if any(
            forecast.timestamp != first.timestamp or forecast.symbol != first.symbol
            for forecast in self.forecasts
        ):
            raise ValueError("all forecasts must share timestamp and symbol")


@dataclass(frozen=True, slots=True)
class PredictionUncertainty:
    """Explicit uncertainty summary independent of any trading decision."""

    method: str
    value: float
    lower: float | None = None
    upper: float | None = None
    confidence_level: float | None = None

    def __post_init__(self) -> None:
        if not str(self.method).strip():
            raise ValueError("method must not be empty")
        if not pd.notna(float(self.value)) or float(self.value) < 0.0:
            raise ValueError("uncertainty value must be finite and non-negative")
        if self.lower is not None and self.upper is not None:
            if float(self.lower) > float(self.upper):
                raise ValueError("lower uncertainty bound must not exceed upper")
        if self.confidence_level is not None:
            level = float(self.confidence_level)
            if not 0.0 < level < 1.0:
                raise ValueError("confidence_level must lie in (0, 1)")
