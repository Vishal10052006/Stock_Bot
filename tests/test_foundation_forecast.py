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


def test_forecast_pads_incomplete_batches_with_valid_contexts() -> None:
    class FakeModel:
        def __init__(self):
            self.seen_inputs = None

        def forecast(self, *, horizon, inputs):
            self.seen_inputs = list(inputs)
            point = np.asarray(
                [[float(values[-1])] * horizon for values in inputs],
                dtype=float,
            )
            quantiles = np.zeros((len(inputs), horizon, 10), dtype=float)
            return point, quantiles

    fake = FakeModel()
    model = FoundationForecastModel(
        FoundationForecastConfig(batch_size=4)
    )
    model._model = fake
    model._compiled = True

    inputs = [
        np.full(64, 11.0),
        np.full(64, 22.0),
        np.full(64, 33.0),
    ]

    point, quantiles = model.forecast(inputs, horizon=2)

    assert fake.seen_inputs is not None
    assert len(fake.seen_inputs) == 4
    assert [float(values[-1]) for values in fake.seen_inputs] == [
        11.0,
        22.0,
        33.0,
        11.0,
    ]
    assert point.shape == (3, 2)
    assert np.array_equal(
        point,
        np.asarray(
            [
                [11.0, 11.0],
                [22.0, 22.0],
                [33.0, 33.0],
            ]
        ),
    )
    assert quantiles.shape == (3, 2, 10)


def test_forecast_normalizes_timesfm_transposed_batch_orientation() -> None:
    class FakeModel:
        def forecast(self, *, horizon, inputs):
            batch = len(inputs)
            point = np.arange(horizon * batch, dtype=float).reshape(
                horizon, batch
            )
            quantiles = np.empty((horizon, batch, 10), dtype=float)
            for q in range(10):
                quantiles[:, :, q] = point + q
            return point, quantiles

    model = FoundationForecastModel()
    model._model = FakeModel()
    model._compiled = True

    point, quantiles = model.forecast(
        [np.ones(64), np.ones(64), np.ones(64)],
        horizon=4,
    )

    expected = np.arange(12, dtype=float).reshape(4, 3).T
    assert point.shape == (3, 4)
    assert np.array_equal(point, expected)
    assert quantiles.shape == (3, 4, 10)
    assert np.array_equal(quantiles[:, :, 0], expected)
    assert np.array_equal(quantiles[:, :, 9], expected + 9)


def test_forecast_does_not_reshape_unverified_point_shape() -> None:
    class FakeModel:
        def forecast(self, *, horizon, inputs):
            point = np.zeros((horizon - 1, len(inputs)), dtype=float)
            quantiles = np.zeros((len(inputs), horizon, 10), dtype=float)
            return point, quantiles

    model = FoundationForecastModel()
    model._model = FakeModel()
    model._compiled = True

    with pytest.raises(RuntimeError, match="unexpected TimesFM point shape"):
        model.forecast([np.ones(64), np.ones(64), np.ones(64)], horizon=4)


def test_forecast_does_not_reshape_unverified_quantile_shape() -> None:
    class FakeModel:
        def forecast(self, *, horizon, inputs):
            point = np.zeros((len(inputs), horizon), dtype=float)
            quantiles = np.zeros((horizon - 1, len(inputs), 10), dtype=float)
            return point, quantiles

    model = FoundationForecastModel()
    model._model = FakeModel()
    model._compiled = True

    with pytest.raises(RuntimeError, match="unexpected TimesFM quantile shape"):
        model.forecast([np.ones(64), np.ones(64), np.ones(64)], horizon=4)
