from pathlib import Path

import pandas as pd
import pytest

from scripts.run_phase9_return_forecast_ensemble_walk_forward import (
    _load_merged,
)


def test_ensemble_walk_forward_loader_requires_future_target(tmp_path: Path) -> None:
    timestamps = pd.date_range(
        "2026-01-01 09:15:00",
        periods=3,
        freq="5min",
        tz="Asia/Kolkata",
    )
    dataset = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * 3,
            "price_ema_9_distance_pct": [0.0, 0.1, 0.2],
        }
    )
    targets = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * 3,
            "future_timestamp": timestamps + pd.Timedelta(minutes=60),
            "future_return": [0.01, -0.01, 0.02],
            "horizon_bars": [12] * 3,
        }
    )
    dataset_path = tmp_path / "dataset.parquet"
    target_path = tmp_path / "targets.parquet"
    dataset.to_parquet(dataset_path)
    targets.to_parquet(target_path)

    merged, features, horizon = _load_merged(dataset_path, target_path)

    assert len(merged) == 3
    assert features == ["price_ema_9_distance_pct"]
    assert horizon == 12


def test_ensemble_walk_forward_loader_rejects_non_future_target(tmp_path: Path) -> None:
    timestamps = pd.date_range(
        "2026-01-01 09:15:00",
        periods=3,
        freq="5min",
        tz="Asia/Kolkata",
    )
    dataset = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * 3,
            "price_ema_9_distance_pct": [0.0, 0.1, 0.2],
        }
    )
    targets = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * 3,
            "future_timestamp": timestamps + pd.Timedelta(minutes=60),
            "future_return": [0.01, -0.01, 0.02],
            "horizon_bars": [12] * 3,
        }
    )
    targets.loc[0, "future_timestamp"] = timestamps[0]
    dataset_path = tmp_path / "dataset.parquet"
    target_path = tmp_path / "targets.parquet"
    dataset.to_parquet(dataset_path)
    targets.to_parquet(target_path)

    with pytest.raises(ValueError, match="non-future"):
        _load_merged(dataset_path, target_path)
