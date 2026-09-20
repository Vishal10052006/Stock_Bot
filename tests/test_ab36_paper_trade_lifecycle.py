"""AB-36 paper trade lifecycle coverage."""
from __future__ import annotations

import pandas as pd
import pytest

from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
)
from paper.runtime import PaperTradingConfig, PaperTradingRuntime
from trading.paper.lifecycle import PaperTradeLifecycle
from trading.strategy.models import StrategyDirection


def _order(direction: StrategyDirection = StrategyDirection.LONG):
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(slippage_bps=0.0, fee_bps=0.0)
    )
    auth = ExecutionAuthorization(
        timestamp=pd.Timestamp("2026-09-20 10:00:00+05:30"),
        symbol="RELIANCE",
        direction=direction,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test",
        risk_version="v1.0",
    )
    return runtime.submit(auth, price=100.0, quantity=10.0)


def test_ab36_captures_long_trade_outcome_and_excursion() -> None:
    lifecycle = PaperTradeLifecycle()
    order = _order()

    lifecycle.open(order)
    lifecycle.mark(
        "RELIANCE",
        timestamp=pd.Timestamp("2026-09-20 10:05:00+05:30"),
        price=98.0,
    )
    lifecycle.mark(
        "RELIANCE",
        timestamp=pd.Timestamp("2026-09-20 10:10:00+05:30"),
        price=105.0,
    )
    outcome = lifecycle.close(
        "RELIANCE",
        timestamp=pd.Timestamp("2026-09-20 10:20:00+05:30"),
        price=103.0,
    )

    assert outcome.net_pnl == 30.0
    assert outcome.mae == -20.0
    assert outcome.mfe == 50.0
    assert outcome.holding_minutes == 20.0
    assert lifecycle.outcomes == (outcome,)


def test_ab36_supports_short_trade_direction() -> None:
    lifecycle = PaperTradeLifecycle()
    order = _order(StrategyDirection.SHORT)

    lifecycle.open(order)
    outcome = lifecycle.close(
        "RELIANCE",
        timestamp=pd.Timestamp("2026-09-20 10:30:00+05:30"),
        price=95.0,
    )

    assert outcome.direction is StrategyDirection.SHORT
    assert outcome.gross_pnl == 50.0


def test_ab36_rejects_non_filled_orders_and_duplicate_open() -> None:
    lifecycle = PaperTradeLifecycle()
    order = _order()
    lifecycle.open(order)

    with pytest.raises(ValueError, match="already open"):
        lifecycle.open(order)
