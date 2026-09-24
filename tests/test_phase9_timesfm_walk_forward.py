from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.run_phase9_timesfm_walk_forward import (
    FROZEN_CONTEXT_LENGTH,
    FROZEN_CONFIDENCE,
    FROZEN_HORIZON_BARS,
    _load_merged,
    _session_history,
    _forecast_rows,
)


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    timestamps = pd.date_range(
        "2026-01-05 09:15:00",
        periods=80,
        freq="5min",
        tz="Asia/Kolkata",
    )
    dataset = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * len(timestamps),
            "close": np.linspace(100.0, 108.0, len(timestamps)),
            "price_ema_9_distance_pct": 0.0,
            "price_ema_20_distance_pct": 0.0,
            "price_ema_50_distance_pct": 0.0,
            "ema_9_20_distance_pct": 0.0,
            "ema_20_50_distance_pct": 0.0,
        }
    )
    targets = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * len(timestamps),
            "future_timestamp": timestamps + pd.Timedelta(minutes=60),
            "future_return": [0.01] * len(timestamps),
            "horizon_bars": [FROZEN_HORIZON_BARS] * len(timestamps),
        }
    )
    dataset_path = tmp_path / "dataset.parquet"
    target_path = tmp_path / "targets.parquet"
    dataset.to_parquet(dataset_path)
    targets.to_parquet(target_path)
    return dataset_path, target_path


class FakeFoundationModel:
    def forecast(self, inputs, *, horizon):
        point = np.array(
            [[float(series[-1]) * (1.01 + 0.0001 * i) for i in range(horizon)]
             for series in inputs],
            dtype=float,
        )
        quantiles = np.zeros((len(inputs), horizon, 10), dtype=float)
        for i in range(10):
            quantiles[:, :, i] = point * (0.995 + 0.001 * i)
        return point, quantiles


def test_protocol_constants_are_frozen() -> None:
    assert FROZEN_CONTEXT_LENGTH == 64
    assert FROZEN_HORIZON_BARS == 12
    assert FROZEN_CONFIDENCE == 0.80


def test_loader_requires_positive_close_and_future_target(tmp_path: Path) -> None:
    dataset_path, target_path = _write_inputs(tmp_path)
    merged, features, horizon = _load_merged(dataset_path, target_path)

    assert len(merged) == 80
    assert features
    assert horizon == 12
    assert (merged["future_timestamp"] > merged["timestamp"]).all()


def test_session_history_never_uses_current_or_future_rows(tmp_path: Path) -> None:
    dataset_path, target_path = _write_inputs(tmp_path)
    merged, _, _ = _load_merged(dataset_path, target_path)

    timestamp = merged.iloc[64]["timestamp"]
    history = _session_history(
        merged,
        symbol="ITC",
        timestamp=timestamp,
        context_length=FROZEN_CONTEXT_LENGTH,
    )

    assert history is not None
    assert len(history) == FROZEN_CONTEXT_LENGTH
    assert np.isclose(history[-1], merged.iloc[63]["close"])


def test_session_history_resets_across_trading_days(tmp_path: Path) -> None:
    dataset_path, target_path = _write_inputs(tmp_path)
    merged, _, _ = _load_merged(dataset_path, target_path)
    next_day = merged.copy()
    next_day["timestamp"] = next_day["timestamp"] + pd.Timedelta(days=1)
    combined = pd.concat([merged, next_day], ignore_index=True)

    timestamp = combined.iloc[80 + 64]["timestamp"]
    history = _session_history(
        combined,
        symbol="ITC",
        timestamp=timestamp,
        context_length=FROZEN_CONTEXT_LENGTH,
    )

    assert history is not None
    assert np.isclose(history[-1], combined.iloc[80 + 63]["close"])


def test_forecast_conversion_produces_return_and_interval(tmp_path: Path) -> None:
    dataset_path, target_path = _write_inputs(tmp_path)
    merged, _, _ = _load_merged(dataset_path, target_path)

    test = merged.iloc[64:66].copy()
    predictions, skipped = _forecast_rows(
        FakeFoundationModel(),
        history=merged.iloc[:64].copy(),
        test=test,
        context_length=FROZEN_CONTEXT_LENGTH,
        horizon=FROZEN_HORIZON_BARS,
    )

    assert skipped == 0
    assert len(predictions) == 2
    assert np.isfinite(predictions["predicted_return"]).all()
    assert (predictions["lower_return"] <= predictions["upper_return"]).all()


def test_insufficient_context_is_explicitly_skipped(tmp_path: Path) -> None:
    dataset_path, target_path = _write_inputs(tmp_path)
    merged, _, _ = _load_merged(dataset_path, target_path)

    predictions, skipped = _forecast_rows(
        FakeFoundationModel(),
        history=merged.iloc[:20].copy(),
        test=merged.iloc[20:22].copy(),
        context_length=FROZEN_CONTEXT_LENGTH,
        horizon=FROZEN_HORIZON_BARS,
    )

    assert predictions.empty
    assert skipped == 2
