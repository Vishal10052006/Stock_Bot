from __future__ import annotations

import pandas as pd

from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
)
from paper.runtime import PaperTradingConfig, PaperTradingRuntime
from trading.strategy.models import StrategyDirection


def _authorization(
    direction: StrategyDirection,
    timestamp: str,
) -> ExecutionAuthorization:
    return ExecutionAuthorization(
        timestamp=pd.Timestamp(timestamp),
        symbol="ITC",
        direction=direction,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test",
        risk_version="test",
    )


def test_short_mark_to_market_uses_short_pnl() -> None:
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(
            slippage_bps=0.0,
            fee_bps=0.0,
        )
    )

    runtime.submit(
        _authorization(
            StrategyDirection.SHORT,
            "2026-01-01 09:15:00+05:30",
        ),
        price=100.0,
        quantity=10.0,
    )

    assert runtime.mark_to_market("ITC", 90.0) == 100.0
    assert runtime.mark_to_market("ITC", 110.0) == -100.0


def test_short_position_closes_with_long_order() -> None:
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(
            slippage_bps=0.0,
            fee_bps=0.0,
        )
    )

    runtime.submit(
        _authorization(
            StrategyDirection.SHORT,
            "2026-01-01 09:15:00+05:30",
        ),
        price=100.0,
        quantity=10.0,
    )

    runtime.submit(
        _authorization(
            StrategyDirection.LONG,
            "2026-01-01 09:20:00+05:30",
        ),
        price=90.0,
        quantity=10.0,
    )

    position = runtime.position("ITC")

    assert position is not None
    assert position.quantity == 0.0
    assert runtime.mark_to_market("ITC", 90.0) == 100.0


def test_larger_reversal_opens_residual_opposite_position() -> None:
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(
            slippage_bps=0.0,
            fee_bps=0.0,
        )
    )

    runtime.submit(
        _authorization(
            StrategyDirection.LONG,
            "2026-01-01 09:15:00+05:30",
        ),
        price=100.0,
        quantity=10.0,
    )

    runtime.submit(
        _authorization(
            StrategyDirection.SHORT,
            "2026-01-01 09:20:00+05:30",
        ),
        price=110.0,
        quantity=15.0,
    )

    position = runtime.position("ITC")

    assert position is not None
    assert position.direction is StrategyDirection.SHORT
    assert position.quantity == 5.0
    assert position.average_price == 110.0
    assert position.realized_pnl == 100.0
