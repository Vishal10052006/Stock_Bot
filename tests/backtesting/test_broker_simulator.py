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
        reason="test",
        risk_version="v1.0",
        approved_quantity=1.0,
        approved_notional=100.0,
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


@pytest.mark.parametrize("field", ["slippage_bps", "fee_bps"])
def test_broker_simulator_rejects_non_finite_costs(field: str) -> None:
    value = float("nan")
    kwargs = {"slippage_bps": 5.0, "fee_bps": 2.0}
    kwargs[field] = value
    with pytest.raises(ValueError, match="finite"):
        BrokerSimulatorConfig(**kwargs)
