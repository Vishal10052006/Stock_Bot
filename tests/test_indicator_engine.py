"""Integration tests for the unified IndicatorEngine."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from market.indicators.engine import (
    IndicatorEngine,
    calculate_indicators,
)


IST = ZoneInfo("Asia/Kolkata")


def make_ohlcv(rows: int = 80) -> pd.DataFrame:
    """Create deterministic intraday OHLCV candles."""
    timestamps = [
        datetime(
            2026,
            9,
            1,
            9,
            15,
            tzinfo=IST,
        ) + timedelta(minutes=5 * index)
        for index in range(rows)
    ]

    close = pd.Series(
        [
            100.0
            + (index * 0.4)
            + ((index % 5) * 0.2)
            for index in range(rows)
        ],
        dtype=float,
    )

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": [
                1000.0 + (index * 20.0)
                for index in range(rows)
            ],
        }
    )


def test_engine_adds_all_phase4_indicators() -> None:
    """Engine should expose every required Phase 4 output."""
    data = make_ohlcv()

    result = IndicatorEngine().calculate(data)

    expected = {
        # Trend
        "ema_9",
        "ema_20",
        "ema_50",
        "sma",
        "vwap",

        # Momentum
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_histogram",
        "roc_14",

        # Volatility
        "atr_14",
        "bb_middle",
        "bb_upper",
        "bb_lower",
        "bb_width",
        "realized_volatility_20",

        # Volume
        "rvol_20",
        "volume_change_1",

        # Structure
        "support_20",
        "resistance_20",
        "distance_to_support_pct",
        "distance_to_resistance_pct",
        "higher_high",
        "lower_low",
        "higher_low",
        "lower_high",
    }

    assert expected.issubset(result.columns)


def test_engine_preserves_original_ohlcv_columns() -> None:
    """Original candle fields must remain available."""
    data = make_ohlcv()

    result = IndicatorEngine().calculate(data)

    for column in [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:
        assert column in result.columns


def test_engine_does_not_modify_input() -> None:
    """Indicator calculation must not mutate candle data."""
    data = make_ohlcv()
    original = data.copy(deep=True)

    IndicatorEngine().calculate(data)

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_engine_preserves_row_count() -> None:
    """Indicator calculation must never create or remove candles."""
    data = make_ohlcv(80)

    result = IndicatorEngine().calculate(data)

    assert len(result) == len(data)


def test_engine_preserves_index() -> None:
    """Indicator calculation must preserve the candle index."""
    data = make_ohlcv(80)

    result = IndicatorEngine().calculate(data)

    pd.testing.assert_index_equal(
        result.index,
        data.index,
    )


def test_engine_is_deterministic() -> None:
    """Identical input must produce identical indicators."""
    data = make_ohlcv()

    first = IndicatorEngine().calculate(data)
    second = IndicatorEngine().calculate(data)

    pd.testing.assert_frame_equal(
        first,
        second,
    )


def test_engine_supports_custom_parameters() -> None:
    """Configured indicator periods must propagate correctly."""
    data = make_ohlcv(80)

    engine = IndicatorEngine(
        trend_sma_period=10,
        rsi_period=7,
        roc_period=5,
        atr_period=7,
        bollinger_period=10,
        realized_volatility_period=10,
        rvol_period=10,
        structure_period=10,
    )

    result = engine.calculate(data)

    assert "sma" in result.columns
    assert "rsi_7" in result.columns
    assert "roc_5" in result.columns
    assert "atr_7" in result.columns
    assert "realized_volatility_10" in result.columns
    assert "rvol_10" in result.columns
    assert "support_10" in result.columns
    assert "resistance_10" in result.columns


def test_engine_rejects_missing_column() -> None:
    """Missing candle fields must be rejected."""
    data = make_ohlcv().drop(
        columns=["close"]
    )

    with pytest.raises(
        ValueError,
        match="missing required OHLCV",
    ):
        IndicatorEngine().calculate(data)


def test_engine_rejects_non_dataframe() -> None:
    """The engine requires a pandas DataFrame."""
    with pytest.raises(
        TypeError,
        match="pandas DataFrame",
    ):
        IndicatorEngine().calculate(
            {"close": [100.0]}  # type: ignore[arg-type]
        )


def test_engine_rejects_empty_dataframe() -> None:
    """An empty candle set is invalid."""
    data = make_ohlcv(1).iloc[0:0]

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        IndicatorEngine().calculate(data)


def test_convenience_function_matches_engine() -> None:
    """One-shot helper must match direct engine usage."""
    data = make_ohlcv()

    direct = IndicatorEngine().calculate(data)
    helper = calculate_indicators(data)

    pd.testing.assert_frame_equal(
        direct,
        helper,
    )


def test_engine_contains_no_trading_decision_column() -> None:
    """IndicatorEngine must remain separate from decision logic."""
    data = make_ohlcv()

    result = IndicatorEngine().calculate(data)

    forbidden = {
        "buy",
        "sell",
        "hold",
        "signal",
        "action",
        "decision",
    }

    assert forbidden.isdisjoint(
        {
            str(column).lower()
            for column in result.columns
        }
    )
