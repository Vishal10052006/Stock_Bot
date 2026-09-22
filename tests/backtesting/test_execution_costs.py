from __future__ import annotations

import pandas as pd

from backtesting.engine import HistoricalBacktestEngine
from paper.runtime import PaperTradingConfig, PaperTradingRuntime

def _row(timestamp: str, *, close: float) -> dict:
    return {
        "timestamp": timestamp,
        "symbol": "ITC",
        "close": close,
        "regime": "TREND_UP",
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


def test_backtest_applies_entry_and_exit_costs() -> None:
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(
            slippage_bps=10.0,
            fee_bps=5.0,
        )
    )

    result = HistoricalBacktestEngine(
        runtime=runtime,
        config=__import__('backtesting.engine', fromlist=['BacktestConfig']).BacktestConfig(target_reward_risk=100.0),
    ).run(
        pd.DataFrame(
            [
                _row(
                    "2026-01-01 09:15:00+05:30",
                    close=100.0,
                ),
                _row(
                    "2026-01-01 09:20:00+05:30",
                    close=110.0,
                ),
            ]
        )
    )

    outcome = result.outcomes[0]
    entry = result.orders[0]

    assert outcome.gross_pnl < 10.0
    assert outcome.slippage_cost > entry.slippage_cost
    assert outcome.fees > entry.fees
    assert outcome.net_pnl < outcome.gross_pnl


def test_zero_cost_backtest_matches_market_move() -> None:
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(
            slippage_bps=0.0,
            fee_bps=0.0,
        )
    )

    result = HistoricalBacktestEngine(
        runtime=runtime,
    ).run(
        pd.DataFrame(
            [
                _row(
                    "2026-01-01 09:15:00+05:30",
                    close=100.0,
                ),
                _row(
                    "2026-01-01 09:20:00+05:30",
                    close=110.0,
                ),
            ]
        )
    )

    outcome = result.outcomes[0]

    assert outcome.entry_price == 100.0
    assert outcome.exit_price == 110.0
    assert outcome.gross_pnl == 10.0
    assert outcome.fees == 0.0
    assert outcome.slippage_cost == 0.0
    assert outcome.net_pnl == 10.0
