"""AB-34 paper runtime tests."""
from __future__ import annotations

import pandas as pd

from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
)
from paper.runtime import (
    PaperOrderStatus,
    PaperTradingRuntime,
    PaperTradingConfig,
)
from trading.strategy.models import StrategyDirection


def _authorization(status: ExecutionAuthorizationStatus) -> ExecutionAuthorization:
    return ExecutionAuthorization(
        timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
        symbol="RELIANCE",
        direction=StrategyDirection.LONG,
        status=status,
        reason="test",
        risk_version="v1.0",
    )


def test_ab34_approved_authorization_creates_fill_and_position() -> None:
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(slippage_bps=5.0, fee_bps=2.0)
    )

    order = runtime.submit(
        _authorization(ExecutionAuthorizationStatus.AUTHORIZED),
        price=100.0,
        quantity=10,
    )

    assert order.status is PaperOrderStatus.FILLED
    assert order.fill_price > 100.0
    assert runtime.position("RELIANCE").quantity == 10
    assert len(runtime.journal) == 1


def test_ab34_blocked_authorization_never_changes_position() -> None:
    runtime = PaperTradingRuntime()

    order = runtime.submit(
        _authorization(ExecutionAuthorizationStatus.BLOCKED),
        price=100.0,
        quantity=10,
    )

    assert order.status is PaperOrderStatus.REJECTED
    assert runtime.position("RELIANCE") is None
    assert len(runtime.journal) == 1


def test_ab34_mark_to_market_is_deterministic() -> None:
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(slippage_bps=0.0, fee_bps=0.0)
    )
    runtime.submit(
        _authorization(ExecutionAuthorizationStatus.AUTHORIZED),
        price=100.0,
        quantity=5,
    )

    assert runtime.mark_to_market("RELIANCE", 105.0) == 25.0
