"""Deterministic prediction ensembles.

The ensemble combines already-generated Prediction Bot outputs. It does not
fit model parameters, tune against external OOS observations, create trade
decisions, size positions, or call execution.

Weights are explicit configuration, not learned from final OOS data. Return
intervals use a conservative component-envelope representation and are not
claimed to preserve the individual conformal coverage guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pandas as pd

from ml.prediction.contracts import (
    ClassificationPrediction,
    MultiHorizonForecast,
    PredictionProvenance,
    ReturnForecast,
)


@dataclass(frozen=True, slots=True)
class EnsembleComponent:
    """One prediction plus an explicit deterministic ensemble weight."""

    prediction: ClassificationPrediction | ReturnForecast
    weight: float

    def __post_init__(self) -> None:
        weight = float(self.weight)
        if not pd.notna(weight) or weight < 0.0:
            raise ValueError("ensemble component weight must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class EnsembleConfig:
    """Frozen, explicit ensemble configuration."""

    method: str = "weighted_average"
    interval_method: str = "component_envelope"

    def __post_init__(self) -> None:
        if self.method != "weighted_average":
            raise ValueError("only weighted_average ensemble method is supported")
        if self.interval_method != "component_envelope":
            raise ValueError("only component_envelope interval method is supported")


class PredictionEnsembler:
    """Combine prediction-only outputs without introducing trading logic."""

    def __init__(self, config: EnsembleConfig | None = None) -> None:
        self.config = config or EnsembleConfig()

    @staticmethod
    def _validate_components(
        components: Sequence[EnsembleComponent],
    ) -> tuple[EnsembleComponent, ...]:
        values = tuple(components)
        if not values:
            raise ValueError("ensemble requires at least one component")
        total = sum(float(component.weight) for component in values)
        if total <= 0.0:
            raise ValueError("ensemble weights must have a positive sum")
        return values

    @staticmethod
    def _normalise_weights(
        components: tuple[EnsembleComponent, ...],
    ) -> tuple[float, ...]:
        total = sum(float(component.weight) for component in components)
        return tuple(float(component.weight) / total for component in components)

    @staticmethod
    def _validate_shared_identity(
        predictions: Sequence[ClassificationPrediction | ReturnForecast],
    ) -> None:
        first = predictions[0]
        timestamp = pd.Timestamp(first.timestamp)
        symbol = str(first.symbol).strip().upper()
        if any(
            pd.Timestamp(prediction.timestamp) != timestamp
            or str(prediction.symbol).strip().upper() != symbol
            for prediction in predictions[1:]
        ):
            raise ValueError("ensemble components must share timestamp and symbol")

    @staticmethod
    def _ensemble_provenance(
        predictions: Sequence[ClassificationPrediction | ReturnForecast],
    ) -> PredictionProvenance:
        first = predictions[0].provenance
        model_versions = ",".join(prediction.provenance.model_version for prediction in predictions)
        return PredictionProvenance(
            model_version=f"ensemble[{model_versions}]",
            model_family="ensemble",
            dataset_version=first.dataset_version,
            feature_version=first.feature_version,
            target_version=first.target_version,
            code_version=first.code_version,
            calibration_version="component-calibrated",
        )

    def combine_classification(
        self,
        components: Sequence[EnsembleComponent],
    ) -> ClassificationPrediction:
        values = self._validate_components(components)
        predictions = tuple(component.prediction for component in values)
        if not all(isinstance(prediction, ClassificationPrediction) for prediction in predictions):
            raise TypeError("classification ensemble requires ClassificationPrediction components")

        self._validate_shared_identity(predictions)
        weights = self._normalise_weights(values)
        probability_keys = ("LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE")
        probabilities = {
            key: sum(
                weight * float(prediction.probabilities[key])
                for weight, prediction in zip(weights, predictions)
            )
            for key in probability_keys
        }
        total = sum(probabilities.values())
        if total <= 0.0:
            raise ValueError("ensemble produced an invalid probability total")
        probabilities = {key: value / total for key, value in probabilities.items()}

        uncertainties = [
            prediction.uncertainty
            for prediction in predictions
            if prediction.uncertainty is not None
        ]
        uncertainty = (
            sum(weight * float(prediction.uncertainty)
                for weight, prediction in zip(weights, predictions)
                if prediction.uncertainty is not None)
            / sum(
                weight for weight, prediction in zip(weights, predictions)
                if prediction.uncertainty is not None
            )
            if uncertainties
            else None
        )

        return ClassificationPrediction(
            timestamp=predictions[0].timestamp,
            symbol=predictions[0].symbol,
            probabilities=probabilities,
            provenance=self._ensemble_provenance(predictions),
            uncertainty=uncertainty,
        )

    def combine_return_forecast(
        self,
        components: Sequence[EnsembleComponent],
    ) -> ReturnForecast:
        values = self._validate_components(components)
        predictions = tuple(component.prediction for component in values)
        if not all(isinstance(prediction, ReturnForecast) for prediction in predictions):
            raise TypeError("return ensemble requires ReturnForecast components")

        self._validate_shared_identity(predictions)
        horizons = {prediction.horizon_minutes for prediction in predictions}
        if len(horizons) != 1:
            raise ValueError("return ensemble components must share horizon_minutes")

        weights = self._normalise_weights(values)
        expected = sum(
            weight * float(prediction.expected_return)
            for weight, prediction in zip(weights, predictions)
        )

        uncertainty_values = [
            (weight, prediction.uncertainty)
            for weight, prediction in zip(weights, predictions)
            if prediction.uncertainty is not None
        ]
        uncertainty = (
            sum(weight * float(value) for weight, value in uncertainty_values)
            / sum(weight for weight, _ in uncertainty_values)
            if uncertainty_values
            else None
        )

        interval_values = [
            (weight, prediction)
            for weight, prediction in zip(weights, predictions)
            if prediction.interval_lower is not None
            and prediction.interval_upper is not None
        ]
        lower = upper = confidence = None
        if interval_values:
            # Envelope is intentionally conservative. It is not a new
            # conformal guarantee and is reported as such by the provenance.
            lower = min(float(prediction.interval_lower) for _, prediction in interval_values)
            upper = max(float(prediction.interval_upper) for _, prediction in interval_values)
            confidence_values = {
                float(prediction.interval_confidence)
                for _, prediction in interval_values
                if prediction.interval_confidence is not None
            }
            if confidence_values:
                if len(confidence_values) != 1:
                    raise ValueError("interval confidence levels must match")
                confidence = next(iter(confidence_values))

        return ReturnForecast(
            timestamp=predictions[0].timestamp,
            symbol=predictions[0].symbol,
            horizon_minutes=next(iter(horizons)),
            expected_return=expected,
            uncertainty=uncertainty,
            provenance=self._ensemble_provenance(predictions),
            interval_lower=lower,
            interval_upper=upper,
            interval_confidence=confidence,
        )

    def combine_multi_horizon(
        self,
        ensembles: Sequence[Sequence[EnsembleComponent]],
    ) -> MultiHorizonForecast:
        values = tuple(ensembles)
        if not values:
            raise ValueError("multi-horizon ensemble requires at least one horizon")
        forecasts = tuple(self.combine_return_forecast(components) for components in values)
        return MultiHorizonForecast(forecasts=forecasts)
