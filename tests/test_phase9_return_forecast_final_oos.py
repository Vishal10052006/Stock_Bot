import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.run_phase9_return_forecast_final_oos import (
    FROZEN_CALIBRATION_RATIO,
    FROZEN_CONFIDENCE,
    FROZEN_PURGE_MINUTES,
    FROZEN_TRAIN_RATIO,
    FROZEN_VALIDATION_RATIO,
    _load_merged,
)


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    timestamps = pd.date_range(
        "2026-01-01 09:15:00",
        periods=12,
        freq="5min",
        tz="Asia/Kolkata",
    )
    dataset = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * 12,
            "future_return": [0.0] * 12,
        }
    )
    # _load_merged only needs canonical feature columns to exist; future_return
    # is supplied by the target artifact.
    dataset["open"] = 100.0
    dataset["high"] = 101.0
    dataset["low"] = 99.0
    dataset["close"] = 100.0
    dataset["volume"] = 1000.0

    targets = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * 12,
            "future_timestamp": timestamps + pd.Timedelta(minutes=60),
            "future_return": [0.001] * 12,
            "horizon_bars": [12] * 12,
        }
    )
    dataset_path = tmp_path / "dataset.parquet"
    target_path = tmp_path / "targets.parquet"
    dataset.to_parquet(dataset_path)
    targets.to_parquet(target_path)
    return dataset_path, target_path


def test_final_oos_protocol_constants_are_frozen() -> None:
    assert FROZEN_TRAIN_RATIO == 0.70
    assert FROZEN_VALIDATION_RATIO == 0.15
    assert FROZEN_PURGE_MINUTES == 60
    assert FROZEN_CALIBRATION_RATIO == 0.10
    assert FROZEN_CONFIDENCE == 0.90


def test_final_oos_loader_requires_strictly_future_targets(tmp_path: Path) -> None:
    dataset_path, target_path = _write_inputs(tmp_path)
    merged, _, horizon = _load_merged(dataset_path, target_path)

    assert len(merged) == 12
    assert horizon == 12
    assert (merged["future_timestamp"] > merged["timestamp"]).all()


def test_final_oos_loader_rejects_non_future_target(tmp_path: Path) -> None:
    dataset_path, target_path = _write_inputs(tmp_path)
    targets = pd.read_parquet(target_path)
    targets.loc[0, "future_timestamp"] = targets.loc[0, "timestamp"]
    targets.to_parquet(target_path)

    with pytest.raises(ValueError, match="non-future"):
        _load_merged(dataset_path, target_path)
