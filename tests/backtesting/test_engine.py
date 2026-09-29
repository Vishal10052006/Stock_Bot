"""Phase 12 historical backtesting engine tests."""

from __future__ import annotations

import pandas as pd
import pytest

from backtesting.engine import BacktestConfig, HistoricalBacktestEngine


def _row(
    timestamp: str,
    *,
    symbol: str = "ITC",
    close: float = 100.0,
    regime: str = "TREND_UP",
) -> dict:
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "close": close,
        "regime": regime,
        "regime_probability": 0.90,
        "vwap_distance_pct": 1.0,
        "rvol_20": 1.5,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
        "high": close,
        "low": close,
        "atr_14": 2.0,
        "support_20": close - 2.0,
        "resistance_20": close + 2.0,
        "volume": 10_000_000.0,
    }


def test_empty_dataframe_returns_empty_result() -> None:
    result = HistoricalBacktestEngine().run(pd.DataFrame())
    assert result.steps == ()
    assert result.outcomes == ()


def test_rows_are_processed_chronologically_without_mutating_input() -> None:
    rows = pd.DataFrame([
        _row("2026-01-01 09:25:00+05:30", close=101.0),
        _row("2026-01-01 09:15:00+05:30", close=100.0),
    ])
    original = rows.copy(deep=True)

    result = HistoricalBacktestEngine().run(rows)

    assert [step.timestamp for step in result.steps] == sorted(
        step.timestamp for step in result.steps
    )
    pd.testing.assert_frame_equal(rows, original)


def test_actionable_signal_creates_paper_order() -> None:
    result = HistoricalBacktestEngine().run(pd.DataFrame([
        _row("2026-01-01 09:15:00+05:30", close=100.0),
        _row("2026-01-01 09:20:00+05:30", close=101.0),
    ]))
    assert len(result.orders) == 1
    assert result.orders[0].status.value == "FILLED"


def test_no_trade_does_not_create_order() -> None:
    result = HistoricalBacktestEngine().run(pd.DataFrame([
        _row("2026-01-01 09:15:00+05:30", regime="RANGE"),
    ]))
    assert result.orders == ()


def test_final_historical_observation_cannot_open_new_trade() -> None:
    result = HistoricalBacktestEngine().run(pd.DataFrame([
        _row("2026-01-01 09:15:00+05:30", close=100.0),
        _row("2026-01-01 09:20:00+05:30", close=101.0),
    ]))
    assert all(
        order.timestamp != pd.Timestamp("2026-01-01 09:20:00+05:30")
        for order in result.orders
    )


def test_trade_is_closed_at_end_of_historical_data() -> None:
    result = HistoricalBacktestEngine().run(pd.DataFrame([
        _row("2026-01-01 09:15:00+05:30", close=100.0),
        _row("2026-01-01 09:20:00+05:30", close=101.0),
    ]))
    assert result.completed_trades == 1
    assert result.outcomes[0].exit_time == pd.Timestamp(
        "2026-01-01 09:20:00+05:30"
    )


def test_max_holding_time_closes_trade() -> None:
    result = HistoricalBacktestEngine(
        config=BacktestConfig(max_holding_minutes=60.0),
    ).run(pd.DataFrame([
        _row("2026-01-01 09:15:00+05:30", close=100.0),
        _row("2026-01-01 10:15:00+05:30", close=102.0),
    ]))
    assert result.completed_trades == 1
    assert result.outcomes[0].holding_minutes == 60.0


def test_invalid_price_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive.*prices"):
        HistoricalBacktestEngine().run(pd.DataFrame([
            _row("2026-01-01 09:15:00+05:30", close=0.0),
        ]))


def test_missing_required_strategy_column_is_rejected() -> None:
    rows = pd.DataFrame([_row("2026-01-01 09:15:00+05:30")]).drop(
        columns=["rvol_20"]
    )
    with pytest.raises(ValueError, match="missing required columns"):
        HistoricalBacktestEngine().run(rows)


def test_intraday_trade_does_not_carry_to_next_session() -> None:
    result = HistoricalBacktestEngine().run(pd.DataFrame([
        _row("2026-01-01 09:15:00+05:30", close=100.0),
        _row("2026-01-01 15:25:00+05:30", close=101.0),
        _row("2026-01-02 09:15:00+05:30", close=99.0),
    ]))
    assert result.completed_trades == 1
    assert result.outcomes[0].exit_time == pd.Timestamp(
        "2026-01-01 15:25:00+05:30"
    )


def test_last_available_session_bar_is_not_an_entry_bar() -> None:
    result = HistoricalBacktestEngine().run(pd.DataFrame([
        _row("2026-01-01 09:15:00+05:30", close=100.0),
        _row("2026-01-01 15:25:00+05:30", close=101.0),
    ]))
    assert len(result.orders) == 1
    assert result.orders[0].timestamp == pd.Timestamp(
        "2026-01-01 09:15:00+05:30"
    )


def test_duplicate_symbol_timestamp_rows_are_rejected() -> None:
    row = _row("2026-01-01 09:15:00+05:30")
    with pytest.raises(ValueError, match="duplicate"):
        HistoricalBacktestEngine().run(pd.DataFrame([row, row]))
