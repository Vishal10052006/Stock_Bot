"""Phase 12 deterministic stop, target and partial-exit tests."""

from __future__ import annotations

import pandas as pd

from backtesting.engine import HistoricalBacktestEngine


def _row(
    timestamp: str,
    *,
    close: float,
    high: float,
    low: float,
) -> dict:
    return {
        "timestamp": timestamp,
        "symbol": "ITC",
        "close": close,
        "high": high,
        "low": low,
        "volume": 10_000_000.0,
        "regime": "TREND_UP",
        "regime_probability": 0.90,
        "vwap_distance_pct": 1.0,
        "rvol_20": 1.5,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
        "atr_14": 2.0,
        "support_20": close - 2.0,
        "resistance_20": close + 2.0,
    }


def test_target_partially_exits_and_remaining_position_is_closed() -> None:
    result = HistoricalBacktestEngine().run(
        pd.DataFrame(
            [
                _row(
                    "2026-01-01 09:15:00+05:30",
                    close=100.0,
                    high=100.0,
                    low=100.0,
                ),
                _row(
                    "2026-01-01 09:20:00+05:30",
                    close=103.0,
                    high=104.0,
                    low=103.0,
                ),
                _row(
                    "2026-01-01 09:25:00+05:30",
                    close=103.0,
                    high=103.0,
                    low=102.5,
                ),
            ]
        )
    )

    assert result.completed_trades == 2
    assert result.outcomes[0].quantity == 125.0
    assert result.outcomes[0].exit_price < 103.0
    assert result.outcomes[1].quantity == 125.0


def test_stop_takes_precedence_when_stop_and_target_share_a_bar() -> None:
    result = HistoricalBacktestEngine().run(
        pd.DataFrame(
            [
                _row(
                    "2026-01-01 09:15:00+05:30",
                    close=100.0,
                    high=100.0,
                    low=100.0,
                ),
                _row(
                    "2026-01-01 09:20:00+05:30",
                    close=99.0,
                    high=104.0,
                    low=97.0,
                ),
            ]
        )
    )

    assert result.completed_trades == 1
    assert result.outcomes[0].quantity == 250.0
    assert result.outcomes[0].exit_price < 100.0
