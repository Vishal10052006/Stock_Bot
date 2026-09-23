"""AB-39 historical backtesting engine tests."""

from __future__ import annotations

import pandas as pd
import pytest

from trading.risk.gate import RiskDecision

from backtesting.engine import (
    BacktestConfig,
    HistoricalBacktestEngine,
)


def _row(
    timestamp: str,
    *,
    symbol: str = "ITC",
    close: float = 100.0,
    regime: str = "TREND_UP",
    regime_probability: float = 0.90,
    vwap_distance_pct: float = 1.0,
    rvol_20: float = 1.5,
    higher_high: bool = True,
    higher_low: bool = True,
    lower_low: bool = False,
    lower_high: bool = False,
) -> dict:
    """Build one valid baseline-strategy decision row."""

    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "close": close,
        "regime": regime,
        "regime_probability": regime_probability,
        "vwap_distance_pct": vwap_distance_pct,
        "rvol_20": rvol_20,
        "higher_high": higher_high,
        "higher_low": higher_low,
        "lower_low": lower_low,
        "lower_high": lower_high,
        "high": close,
        "low": close,
        "atr_14": 2.0,
        "support_20": close - 2.0,
        "resistance_20": close + 2.0,
        "volume": 10_000_000.0,
    }


def test_empty_dataframe_returns_empty_result() -> None:
    """Empty historical data should produce an empty result."""

    result = HistoricalBacktestEngine().run(
        pd.DataFrame()
    )

    assert result.steps == ()
    assert result.outcomes == ()
    assert result.orders == ()
    assert result.completed_trades == 0
    assert result.net_pnl == 0.0


def test_rows_are_processed_chronologically() -> None:
    """Input ordering must not affect chronological processing."""

    rows = pd.DataFrame(
        [
            _row(
                "2026-01-01 09:25:00+05:30",
                close=101.0,
            ),
            _row(
                "2026-01-01 09:15:00+05:30",
                close=100.0,
            ),
        ]
    )

    result = HistoricalBacktestEngine().run(rows)

    timestamps = [
        step.timestamp
        for step in result.steps
    ]

    assert timestamps == sorted(timestamps)


def test_nse_session_is_evaluated_in_ist() -> None:
    rows = pd.DataFrame(
        [
            _row("2026-01-01 09:15:00+05:30"),
            _row("2026-01-01 09:20:00+05:30", close=101.0),
        ]
    )
    result = HistoricalBacktestEngine().run(rows)
    assert result.steps[0].risk.risk_version == "risk_v1.0"
    assert result.steps[0].risk.status.value != "REJECTED" or (
        "SESSION_CLOSED" not in {code.value for code in result.steps[0].risk.reason_codes}
    )


def test_actionable_signal_creates_paper_order() -> None:
    """An approved strategy decision should create a paper fill."""

    rows = pd.DataFrame(
        [
            _row(
                "2026-01-01 09:15:00+05:30",
                close=100.0,
            ),
            _row(
                "2026-01-01 09:20:00+05:30",
                close=101.0,
            ),
        ]
    )

    result = HistoricalBacktestEngine().run(rows)

    assert len(result.orders) == 1
    assert result.orders[0].status.value == "FILLED"


def test_no_trade_does_not_create_order() -> None:
    """A non-actionable strategy decision must remain a no-trade."""

    rows = pd.DataFrame(
        [
            _row(
                "2026-01-01 09:15:00+05:30",
                regime="RANGE",
            ),
        ]
    )

    result = HistoricalBacktestEngine().run(rows)

    assert result.orders == ()
    assert result.completed_trades == 0


def test_trade_is_closed_at_end_of_historical_data() -> None:
    """Open trades must be closed using the configured exit fill."""

    rows = pd.DataFrame(
        [
            _row(
                "2026-01-01 09:15:00+05:30",
                close=100.0,
            ),
            _row(
                "2026-01-01 09:20:00+05:30",
                close=101.0,
            ),
        ]
    )

    result = HistoricalBacktestEngine().run(rows)

    assert result.completed_trades == 1

    outcome = result.outcomes[0]

    assert outcome.entry_price > 0
    assert outcome.exit_price == pytest.approx(100.9495)
    assert outcome.exit_time == pd.Timestamp(
        "2026-01-01 09:20:00+05:30"
    )


def test_max_holding_time_closes_trade() -> None:
    """Configured maximum holding time must be enforced causally."""

    rows = pd.DataFrame(
        [
            _row(
                "2026-01-01 09:15:00+05:30",
                close=100.0,
            ),
            _row(
                "2026-01-01 10:15:00+05:30",
                close=102.0,
            ),
        ]
    )

    engine = HistoricalBacktestEngine(
        config=BacktestConfig(
            max_holding_minutes=60.0,
        )
    )

    result = engine.run(rows)

    assert result.completed_trades == 1

    outcome = result.outcomes[0]

    assert outcome.holding_minutes == 60.0


def test_invalid_price_is_rejected() -> None:
    """Historical prices must be strictly positive."""

    rows = pd.DataFrame(
        [
            _row(
                "2026-01-01 09:15:00+05:30",
                close=0.0,
            ),
        ]
    )

    with pytest.raises(ValueError, match="positive prices"):
        HistoricalBacktestEngine().run(rows)


def test_missing_required_strategy_column_is_rejected() -> None:
    """The baseline strategy contract must be satisfied."""

    rows = pd.DataFrame(
        [
            _row(
                "2026-01-01 09:15:00+05:30",
            ),
        ]
    )

    rows = rows.drop(columns=["rvol_20"])

    with pytest.raises(
        ValueError,
        match="missing required columns",
    ):
        HistoricalBacktestEngine().run(rows)


def test_backtest_uses_full_risk_engine_for_actionable_signal() -> None:
    rows = pd.DataFrame(
        [
            _row("2026-01-01 09:15:00+05:30", close=100.0),
            _row("2026-01-01 09:20:00+05:30", close=101.0),
        ]
    )

    result = HistoricalBacktestEngine().run(rows)

    assert isinstance(result.steps[0].risk, RiskDecision)
    assert result.steps[0].risk.risk_version == "RISK-v1.0"
    assert result.steps[1].risk.risk_version == "RISK-v1.0"
    assert result.orders[0].quantity == 250.0


def test_intraday_trade_is_closed_at_last_bar_before_next_session() -> None:
    """Open positions must not carry overnight into the next NSE session."""

    rows = pd.DataFrame(
        [
            _row("2026-01-01 09:15:00+05:30", close=100.0),
            _row("2026-01-01 15:25:00+05:30", close=101.0),
            _row("2026-01-02 09:15:00+05:30", close=99.0),
        ]
    )

    result = HistoricalBacktestEngine().run(rows)

    assert result.completed_trades == 1
    assert result.outcomes[0].exit_time == pd.Timestamp(
        "2026-01-01 15:25:00+05:30"
    )
    assert result.outcomes[0].exit_time.tz_convert("Asia/Kolkata").date() != pd.Timestamp(
        "2026-01-02 09:15:00+05:30"
    ).tz_convert("Asia/Kolkata").date()


def test_last_session_bar_cannot_open_new_position() -> None:
    """The final available bar of a session is exit-only, never an entry bar."""

    rows = pd.DataFrame(
        [
            _row("2026-01-01 09:15:00+05:30", close=100.0),
            _row("2026-01-01 15:25:00+05:30", close=101.0),
        ]
    )

    result = HistoricalBacktestEngine().run(rows)

    assert len(result.orders) == 1
    assert result.orders[0].timestamp == pd.Timestamp(
        "2026-01-01 09:15:00+05:30"
    )
