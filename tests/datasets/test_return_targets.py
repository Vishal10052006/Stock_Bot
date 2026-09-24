from __future__ import annotations

import pandas as pd
import pytest

from ml.datasets.return_targets import build_fixed_horizon_return_targets


def _candles() -> pd.DataFrame:
    ts = pd.date_range(
        "2026-09-01 09:15",
        periods=5,
        freq="5min",
        tz="Asia/Kolkata",
    )
    return pd.DataFrame(
        {
            "timestamp": ts,
            "symbol": ["AAA"] * len(ts),
            "close": [100.0, 101.0, 102.0, 104.0, 105.0],
        }
    )


def test_target_uses_exactly_n_strictly_future_bars() -> None:
    candles = _candles()
    decisions = candles.iloc[[0]][["timestamp", "symbol", "close"]]

    result = build_fixed_horizon_return_targets(
        candles,
        decisions,
        horizon_bars=2,
    )

    assert len(result) == 1
    assert result.iloc[0]["future_timestamp"] == candles.iloc[2]["timestamp"]
    assert result.iloc[0]["future_close"] == 102.0
    assert result.iloc[0]["future_return"] == pytest.approx(0.02)
    assert result.iloc[0]["horizon_bars"] == 2


def test_incomplete_future_horizon_is_excluded() -> None:
    candles = _candles()
    decisions = candles.iloc[[3]][["timestamp", "symbol", "close"]]

    result = build_fixed_horizon_return_targets(
        candles,
        decisions,
        horizon_bars=2,
    )

    assert result.empty


def test_target_is_symbol_specific() -> None:
    candles = _candles()
    other = candles.copy()
    other["symbol"] = "BBB"
    other["close"] = [200.0, 201.0, 202.0, 204.0, 205.0]
    candles = pd.concat([candles, other], ignore_index=True)

    decisions = candles.iloc[[0, 5]][["timestamp", "symbol", "close"]]

    result = build_fixed_horizon_return_targets(
        candles,
        decisions,
        horizon_bars=1,
    )

    assert result["symbol"].tolist() == ["AAA", "BBB"]
    assert result["future_close"].tolist() == [101.0, 201.0]


def test_same_timestamp_future_bar_is_not_allowed() -> None:
    candles = _candles()
    decisions = pd.DataFrame(
        {
            "timestamp": [candles.iloc[0]["timestamp"]],
            "symbol": ["AAA"],
            "close": [100.0],
        }
    )

    result = build_fixed_horizon_return_targets(
        candles,
        decisions,
        horizon_bars=1,
    )

    assert result.iloc[0]["future_timestamp"] > result.iloc[0]["timestamp"]


def test_rejects_duplicate_candle_keys() -> None:
    candles = _candles()
    candles = pd.concat([candles, candles.iloc[[0]]], ignore_index=True)
    decisions = _candles().iloc[[0]][["timestamp", "symbol", "close"]]

    with pytest.raises(ValueError, match="duplicate"):
        build_fixed_horizon_return_targets(
            candles,
            decisions,
            horizon_bars=1,
        )


def test_rejects_naive_timestamps() -> None:
    candles = _candles()
    decisions = candles.iloc[[0]][["timestamp", "symbol", "close"]].copy()
    decisions["timestamp"] = decisions["timestamp"].dt.tz_localize(None)

    with pytest.raises(ValueError, match="timezone-aware"):
        build_fixed_horizon_return_targets(
            candles,
            decisions,
            horizon_bars=1,
        )
