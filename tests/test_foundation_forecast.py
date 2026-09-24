"""Tests for the optional foundation-model prediction adapter."""

from __future__ import annotations

import sys

import numpy as np
import pytest

from ml.models.foundation_forecast import (
    FoundationForecastConfig,
    FoundationForecastModel,
)


def test_config_rejects_short_context() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        FoundationForecastConfig(context_length=16)


def test_config_rejects_invalid_quantile_order() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        FoundationForecastConfig(
            quantile_lower_index=5,
            quantile_median_index=4,
            quantile_upper_index=9,
        )


def test_forecast_requires_explicit_load() -> None:
    model = FoundationForecastModel()
    with pytest.raises(RuntimeError, match="must be loaded"):
        model.forecast([np.ones(32)], horizon=1)


def test_load_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "timesfm", None)
    model = FoundationForecastModel()
    with pytest.raises(RuntimeError, match="TimesFM is not installed"):
        model.load()


def test_forecast_validates_series_length_after_load() -> None:
    class FakeModel:
        def forecast(self, *, horizon, inputs):
            point = np.zeros((len(inputs), horizon), dtype=float)
            quantiles = np.zeros((len(inputs), horizon, 10), dtype=float)
            return point, quantiles

    model = FoundationForecastModel()
    model._model = FakeModel()
    model._compiled = True

    with pytest.raises(ValueError, match="at least 32"):
        model.forecast([np.ones(31)], horizon=1)


def test_forecast_with_fake_backend_returns_expected_shapes() -> None:
    class FakeModel:
        def forecast(self, *, horizon, inputs):
            point = np.full((len(inputs), horizon), 0.01, dtype=float)
            quantiles = np.empty((len(inputs), horizon, 10), dtype=float)
            for q in range(10):
                quantiles[:, :, q] = (q + 1) * 0.001
            return point, quantiles

    model = FoundationForecastModel()
    model._model = FakeModel()
    model._compiled = True

    result = model.forecast_with_bounds(
        [np.linspace(-0.01, 0.01, 64), np.ones(64)],
        horizon=4,
    )

    assert result["point"].shape == (2, 4)
    assert result["quantiles"].shape == (2, 4, 10)
    assert np.allclose(result["lower"], 0.002)
    assert np.allclose(result["median"], 0.006)
    assert np.allclose(result["upper"], 0.010)


def test_forecast_rejects_non_finite_input() -> None:
    model = FoundationForecastModel()
    model._model = object()
    model._compiled = True

    with pytest.raises(ValueError, match="non-finite"):
        model.forecast([np.array([1.0] * 31 + [np.nan])], horizon=1)

    
def test_forecast_shape_validation_uses_pre_call_batch_size() -> None:
    class FakeModel:
        def forecast(self, *, horizon, inputs):
            # Simulate a backend that pads/mutates the input container while
            # still returning forecasts for the caller-supplied series.
            inputs.extend([np.ones(32) for _ in range(4)])
            point = np.full((2, horizon), 0.01, dtype=float)
            quantiles = np.empty((2, horizon, 10), dtype=float)
            for q in range(10):
                quantiles[:, :, q] = (q + 1) * 0.001
            return point, quantiles

    model = FoundationForecastModel()
    model._model = FakeModel()
    model._compiled = True

    point, quantiles = model.forecast(
        [np.ones(32), np.ones(33)],
        horizon=4,
    )

    assert point.shape == (2, 4)
    assert quantiles.shape == (2, 4, 10)
