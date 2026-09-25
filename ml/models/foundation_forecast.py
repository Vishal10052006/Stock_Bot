"""Optional foundation-model return forecasting adapter.

This module is deliberately experimental. It keeps the Prediction Bot boundary
prediction-only and does not add a mandatory foundation-model dependency.

The first supported backend is the Google TimesFM 2.5 PyTorch checkpoint. The
adapter is intentionally lazy: importing this module does not import or load
TimesFM weights. A caller must explicitly opt in and install the optional
dependency.

TimesFM 3.0 is not wired into the production-facing path because its default
pretrained weights are currently distributed under a non-commercial,
non-production license. See docs/PREDICTION_BOT_STATUS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class FoundationForecastConfig:
    """Configuration for an explicitly opt-in foundation-model experiment."""

    backend: str = "timesfm_2_5"
    model_id: str = "google/timesfm-2.5-200m-pytorch"
    context_length: int = 512
    max_horizon: int = 64
    batch_size: int = 1
    quantile_lower_index: int = 1
    quantile_median_index: int = 5
    quantile_upper_index: int = 9

    def __post_init__(self) -> None:
        if self.backend != "timesfm_2_5":
            raise ValueError("backend must be 'timesfm_2_5'")
        if not str(self.model_id).strip():
            raise ValueError("model_id must not be empty")
        if self.context_length < 32:
            raise ValueError("context_length must be at least 32")
        if self.max_horizon <= 0:
            raise ValueError("max_horizon must be greater than zero")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        for name, value in (
            ("quantile_lower_index", self.quantile_lower_index),
            ("quantile_median_index", self.quantile_median_index),
            ("quantile_upper_index", self.quantile_upper_index),
        ):
            if not 0 <= value <= 9:
                raise ValueError(f"{name} must lie in [0, 9]")
        if not (
            self.quantile_lower_index
            < self.quantile_median_index
            < self.quantile_upper_index
        ):
            raise ValueError("quantile indices must be strictly increasing")


class FoundationForecastModel:
    """Lazy TimesFM 2.5 adapter for research-only prediction experiments.

    The adapter accepts one or more historical value arrays and returns point
    forecasts plus quantile bounds. It never emits a trade decision.
    """

    def __init__(self, config: FoundationForecastConfig | None = None) -> None:
        self.config = config or FoundationForecastConfig()
        self._model: Any | None = None
        self._compiled = False

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._compiled

    def load(self) -> "FoundationForecastModel":
        """Explicitly load the optional TimesFM checkpoint."""
        try:
            import timesfm  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "TimesFM is not installed. Install the optional experimental "
                "dependency with pip install 'timesfm[torch]'."
            ) from exc

        model_cls = getattr(timesfm, "TimesFM_2p5_200M_torch", None)
        if model_cls is None:
            raise RuntimeError(
                "Installed TimesFM package does not expose "
                "TimesFM_2p5_200M_torch; use a package release supporting "
                "the TimesFM 2.5 PyTorch checkpoint."
            )

        model = model_cls.from_pretrained(self.config.model_id)
        forecast_config = timesfm.ForecastConfig(
            max_context=self.config.context_length,
            max_horizon=self.config.max_horizon,
            normalize_inputs=True,
            per_core_batch_size=self.config.batch_size,
            use_continuous_quantile_head=True,
            infer_is_positive=False,
            fix_quantile_crossing=True,
        )
        model.compile(forecast_config)
        self._model = model
        self._compiled = True
        return self

    def forecast(
        self,
        inputs: Sequence[np.ndarray | Sequence[float]],
        *,
        horizon: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Forecast each supplied series.

        Returns point shape (n_series, horizon) and quantile shape
        (n_series, horizon, 10).

        Financial return series can be negative, so the adapter explicitly
        disables positive-only inference.
        """
        if not self.is_loaded:
            raise RuntimeError("FoundationForecastModel must be loaded before forecast")
        if horizon <= 0 or horizon > self.config.max_horizon:
            raise ValueError(
                f"horizon must be in [1, {self.config.max_horizon}]"
            )
        if not inputs:
            raise ValueError("inputs must not be empty")

        prepared: list[np.ndarray] = []
        for index, values in enumerate(inputs):
            array = np.asarray(values, dtype=np.float32)
            if array.ndim != 1 or len(array) < 32:
                raise ValueError(f"input series {index} must contain at least 32 points")
            if not np.isfinite(array).all():
                raise ValueError(f"input series {index} contains non-finite values")
            prepared.append(array)

        expected_batch_size = len(prepared)

        # TimesFM 2.5 internally pads incomplete batches with synthetic
        # zero-valued placeholder series. Those placeholders can contaminate
        # the compiled batch's forecasts across otherwise independent series.
        # Complete the batch here with valid caller contexts instead, then
        # discard the corresponding padded outputs below. Reusing real
        # contexts is inference-only padding: it adds no observations to any
        # caller series and preserves the original output contract.
        backend_inputs = list(prepared)
        if len(backend_inputs) % self.config.batch_size:
            padding = self.config.batch_size - (
                len(backend_inputs) % self.config.batch_size
            )
            backend_inputs.extend(
                backend_inputs[index % expected_batch_size]
                for index in range(padding)
            )

        point, quantiles = self._model.forecast(
            horizon=horizon,
            inputs=backend_inputs,
        )
        point = np.asarray(point, dtype=float)[:expected_batch_size]
        quantiles = np.asarray(quantiles, dtype=float)[:expected_batch_size]
        point_array = np.asarray(point, dtype=float)
        quantile_array = np.asarray(quantiles, dtype=float)

        expected_point_shape = (expected_batch_size, horizon)
        expected_quantile_shape = (expected_batch_size, horizon, 10)

        # Some TimesFM 2.5 backends expose the same forecast tensor with the
        # first two axes reversed. Normalize only that exact, unambiguous
        # orientation; never reshape or pad a tensor whose dimensions do not
        # prove that it represents the caller's batch and requested horizon.
        if point_array.shape == (horizon, expected_batch_size):
            point_array = point_array.T
        if quantile_array.shape == (horizon, expected_batch_size, 10):
            quantile_array = np.transpose(quantile_array, (1, 0, 2))

        if point_array.shape != expected_point_shape:
            raise RuntimeError(
                f"unexpected TimesFM point shape: {point_array.shape}; "
                f"expected {expected_point_shape}"
            )
        if quantile_array.shape != expected_quantile_shape:
            raise RuntimeError(
                f"unexpected TimesFM quantile shape: {quantile_array.shape}; "
                f"expected {expected_quantile_shape}"
            )
        if not np.isfinite(point_array).all() or not np.isfinite(quantile_array).all():
            raise RuntimeError("TimesFM returned non-finite forecast values")

        return point_array, quantile_array

    def forecast_with_bounds(
        self,
        inputs: Sequence[np.ndarray | Sequence[float]],
        *,
        horizon: int,
    ) -> dict[str, np.ndarray]:
        """Return point forecasts and the configured quantile bounds."""
        point, quantiles = self.forecast(inputs, horizon=horizon)
        lower = quantiles[:, :, self.config.quantile_lower_index]
        median = quantiles[:, :, self.config.quantile_median_index]
        upper = quantiles[:, :, self.config.quantile_upper_index]
        if np.any(lower > upper):
            raise RuntimeError("TimesFM quantile bounds are not monotonic")
        return {
            "point": point,
            "median": median,
            "lower": lower,
            "upper": upper,
            "quantiles": quantiles,
        }
