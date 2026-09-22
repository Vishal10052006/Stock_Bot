"""Tests for the Phase 12 broker simulator boundary."""

from __future__ import annotations

import pandas as pd
import pytest

from backtesting.broker_simulator import (
    BrokerSimulator,
    BrokerSimulatorConfig,
)
from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
)
from trading.strategy.models import StrategyDirection


def _authorization() -> ExecutionAuthorization:
    return ExecutionAuthorization(
        timestamp=pd.Timestamp("2026-01-01 09:15:00+05:30"),
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        quantity=1.0,
        notional=100.0,
        reason="test",
        risk_version="v1.0",
    )


def test_broker_simulator_reuses_paper_runtime() -> None:
    broker = BrokerSimulator(
        config=BrokerSimulatorConfig(
            slippage_bps=0.0,
            fee_bps=0.0,
        )
    )

    order = broker.submit(
        _authorization(),
        price=100.0,
        quantity=1.0,
    )

    assert order.status.value == "FILLED"
    assert order.fill_price == 100.0
    assert broker.position("ITC") is not None


def test_broker_simulator_rejects_ambiguous_configuration() -> None:
    from paper.runtime import PaperTradingRuntime

    with pytest.raises(ValueError, match="either config or runtime"):
        BrokerSimulator(
            config=BrokerSimulatorConfig(),
            runtime=PaperTradingRuntime(),
        )
