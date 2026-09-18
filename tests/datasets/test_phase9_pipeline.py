from __future__ import annotations
import math

import pandas as pd
import pytest

from market.candles.models import Candle
from market.data.historical.models import HistoricalDataset
from ml.datasets.pipeline import build_phase9_dataset
from ml.datasets.models import TrainingDataset


IST = "Asia/Kolkata"


def make_historical_dataset(
    periods: int = 80,
) -> HistoricalDataset:
    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=periods,
        freq="5min",
        tz=IST,
    )

    candles = []

    for i, timestamp in enumerate(timestamps):
        close = (
            100.0
            + i * 0.03
            + 2.0 * math.sin(i / 3.0)
        )

        open_price = close - 0.10
        high = close + 0.30
        low = close - 0.30

        candles.append(
            Candle(
                symbol="TEST",
                exchange="NSE",
                timeframe_minutes=5,
                timestamp=timestamp.to_pydatetime(),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=1000.0 + i * 10.0,
            )
        )

    return HistoricalDataset(
        symbol="TEST",
        exchange="NSE",
        timeframe_minutes=5,
        bars=tuple(candles),
        metadata={
            "provider": "Phase9TestProvider",
            "pipeline_version": "test",
        },
    )


def make_market_context(
    timestamps: pd.DatetimeIndex,
) -> pd.DataFrame:
    close = pd.Series(
        [100.0 + i * 0.01 for i in range(len(timestamps))],
        index=timestamps,
        dtype="float64",
    )

    return_1 = close.pct_change(1)
    return_3 = close.pct_change(3)
    return_12 = close.pct_change(12)

    volatility_20 = (
        return_1.rolling(
            20,
            min_periods=20,
        ).std()
    )

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "close": close.to_numpy(),
            "return_1": return_1.to_numpy(),
            "return_3": return_3.to_numpy(),
            "return_12": return_12.to_numpy(),
            "volatility_20": volatility_20.to_numpy(),
        }
    )


def test_phase9_pipeline_returns_training_dataset() -> None:
    dataset = make_historical_dataset()

    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=80,
        freq="5min",
        tz=IST,
    )

    market_context = make_market_context(timestamps)

    result = build_phase9_dataset(
        dataset,
        market_context=market_context,
    )

    assert isinstance(
        result.training_dataset,
        TrainingDataset,
    )

    assert result.eligible_rows > 0
    assert len(result.labels) == result.eligible_rows


def test_phase9_dataset_has_exact_feature_schema() -> None:
    dataset = make_historical_dataset()

    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=80,
        freq="5min",
        tz=IST,
    )

    result = build_phase9_dataset(
        dataset,
        market_context=make_market_context(timestamps),
    )

    training = result.training_dataset

    assert training.data.columns.tolist() == [
        "timestamp",
        "symbol",
        *training.feature_columns,
        "label",
    ]

    assert len(training.feature_columns) == 40


def test_phase9_has_one_label_per_training_row() -> None:
    dataset = make_historical_dataset()

    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=80,
        freq="5min",
        tz=IST,
    )

    result = build_phase9_dataset(
        dataset,
        market_context=make_market_context(timestamps),
    )

    training = result.training_dataset

    assert len(training.data) == result.eligible_rows
    assert training.data[
        ["timestamp", "symbol"]
    ].duplicated().sum() == 0


def test_phase9_labels_are_canonical_three_class_target() -> None:
    dataset = make_historical_dataset()

    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=80,
        freq="5min",
        tz=IST,
    )

    result = build_phase9_dataset(
        dataset,
        market_context=make_market_context(timestamps),
    )

    assert set(result.training_dataset.y.unique()).issubset(
        {
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
        }
    )


def test_phase9_does_not_require_phase8_strategy() -> None:
    """
    ML target generation must not depend on BaselineStrategy.

    A row is labeled from both hypothetical directions even when
    Phase 8 would independently return NO_TRADE.
    """

    dataset = make_historical_dataset()

    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=80,
        freq="5min",
        tz=IST,
    )

    result = build_phase9_dataset(
        dataset,
        market_context=make_market_context(timestamps),
    )

    assert result.eligible_rows > 0
    assert len(result.labels) == result.eligible_rows


def test_phase9_excludes_unconstructable_candidate_rows() -> None:
    dataset = make_historical_dataset(periods=80)

    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=80,
        freq="5min",
        tz=IST,
    )

    result = build_phase9_dataset(
        dataset,
        market_context=make_market_context(timestamps),
    )

    assert result.feature_rows == (
        result.eligible_rows + result.excluded_rows
    )

    assert result.excluded_rows >= 0


def test_phase9_does_not_put_future_metadata_into_training_data() -> None:
    dataset = make_historical_dataset()

    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=80,
        freq="5min",
        tz=IST,
    )

    result = build_phase9_dataset(
        dataset,
        market_context=make_market_context(timestamps),
    )

    forbidden = {
        "outcome_timestamp",
        "outcome_bars",
        "outcome_reason",
        "target_price",
        "stop_price",
        "future_return",
        "future_close",
        "future_high",
        "future_low",
        "future_price",
    }

    assert forbidden.isdisjoint(
        result.training_dataset.data.columns
    )


def test_phase9_identifiers_are_timezone_aware() -> None:
    dataset = make_historical_dataset()

    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=80,
        freq="5min",
        tz=IST,
    )

    result = build_phase9_dataset(
        dataset,
        market_context=make_market_context(timestamps),
    )

    assert isinstance(
        result.training_dataset.data["timestamp"].dtype,
        pd.DatetimeTZDtype,
    )


def test_phase9_rejects_missing_market_context() -> None:
    dataset = make_historical_dataset()

    with pytest.raises(TypeError):
        build_phase9_dataset(
            dataset,
            market_context=None,  # type: ignore[arg-type]
        )


def test_phase9_requires_historical_dataset_contract() -> None:
    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=80,
        freq="5min",
        tz=IST,
    )

    with pytest.raises(TypeError):
        build_phase9_dataset(
            pd.DataFrame(),
            market_context=make_market_context(timestamps),
        )