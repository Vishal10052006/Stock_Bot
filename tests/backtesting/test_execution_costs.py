from __future__ import annotations

import pandas as pd
import pytest

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

    result = HistoricalBacktestEngine(runtime=runtime).run(
        pd.DataFrame(
            [
                _row("2026-01-01 09:15:00+05:30", close=100.0),
                _row("2026-01-01 09:20:00+05:30", close=101.0),
            ]
        )
    )

    outcome = result.outcomes[0]
    entry = result.orders[0]

    assert entry.quantity == 250.0
    assert entry.fill_price == pytest.approx(100.10)
    assert outcome.entry_price == pytest.approx(100.10)
    assert outcome.exit_price == pytest.approx(100.899)
    # Gross P&L is measured from decision/reference prices. Explicit
    # execution slippage is then deducted exactly once.
    assert outcome.gross_pnl == pytest.approx(250.0)
    assert outcome.slippage_cost == pytest.approx(50.25)
    assert outcome.fees == pytest.approx(25.124875)
    assert outcome.net_pnl == pytest.approx(174.625125)
    assert outcome.net_pnl == pytest.approx(
        outcome.gross_pnl - outcome.fees - outcome.slippage_cost
    )


def test_zero_cost_backtest_matches_market_move() -> None:
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(
            slippage_bps=0.0,
            fee_bps=0.0,
        )
    )

    result = HistoricalBacktestEngine(runtime=runtime).run(
        pd.DataFrame(
            [
                _row("2026-01-01 09:15:00+05:30", close=100.0),
                _row("2026-01-01 09:20:00+05:30", close=101.0),
            ]
        )
    )

    outcome = result.outcomes[0]

    assert outcome.entry_price == 100.0
    assert outcome.exit_price == 101.0
    assert outcome.quantity == 250.0
    assert outcome.gross_pnl == 250.0
    assert outcome.fees == 0.0
    assert outcome.slippage_cost == 0.0
    assert outcome.net_pnl == 250.0


def test_nonzero_exit_slippage_requires_reference_price() -> None:
    from execution.trading_execution import (
        ExecutionAuthorization,
        ExecutionAuthorizationStatus,
    )
    from paper.runtime import PaperOrder, PaperOrderStatus
    from trading.paper.lifecycle import PaperTradeLifecycle
    from trading.strategy.models import StrategyDirection

    timestamp = pd.Timestamp("2026-01-01 09:15:00+05:30")
    authorization = ExecutionAuthorization(
        timestamp=timestamp,
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test",
        risk_version="test",
        approved_quantity=10.0,
        approved_notional=1000.0,
    )
    order = PaperOrder(
        timestamp=timestamp,
        symbol="ITC",
        direction=authorization.direction,
        requested_price=100.0,
        fill_price=100.1,
        quantity=10.0,
        status=PaperOrderStatus.FILLED,
        fees=0.0,
        slippage_cost=1.0,
        reason="test",
    )
    lifecycle = PaperTradeLifecycle()
    lifecycle.open(order)

    with pytest.raises(ValueError, match="reference_price"):
        lifecycle.close(
            "ITC",
            timestamp=timestamp + pd.Timedelta(minutes=5),
            price=99.9,
            exit_slippage_cost=1.0,
        )
