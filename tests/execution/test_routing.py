"""Execution routing policy tests."""

from __future__ import annotations

import pytest

from execution.engine import ExecutionEngine
from execution.adapters.paper import PaperBrokerAdapter
from execution.routing import RouteQuote, RoutingPolicy, SmartOrderRouter
from execution.trading_execution import ExecutionAuthorization, ExecutionAuthorizationStatus
from trading.strategy.models import StrategyDirection
import pandas as pd


def _order():
    auth = ExecutionAuthorization(
        timestamp=pd.Timestamp("2026-09-24T10:00:00+05:30"),
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test",
        risk_version="RISK-v1.0",
        approved_quantity=100.0,
        approved_notional=10_000.0,
        risk_decision_id="risk-router-test",
    )
    return ExecutionEngine.from_authorization(auth, decision_id="router-test")


def test_router_selects_lowest_cost_eligible_route() -> None:
    router = SmartOrderRouter()
    decision = router.select(
        _order(),
        (
            RouteQuote("A", 100.0, 8.0, 2.0),
            RouteQuote("B", 100.0, 3.0, 1.0),
        ),
    )
    assert decision.broker == "B"
    assert decision.considered == ("A", "B")


def test_router_rejects_unhealthy_and_insufficient_routes() -> None:
    router = SmartOrderRouter()
    with pytest.raises(ValueError, match="no broker route"):
        router.select(
            _order(),
            (
                RouteQuote("A", 100.0, 1.0, 1.0, healthy=False),
                RouteQuote("B", 50.0, 1.0, 1.0),
            ),
        )


def test_router_can_prefer_latency_when_configured() -> None:
    router = SmartOrderRouter(
        RoutingPolicy(
            slippage_weight=0.0,
            fee_weight=0.0,
            latency_weight=1.0,
        )
    )
    decision = router.select(
        _order(),
        (
            RouteQuote("A", 100.0, 20.0, 20.0, latency_ms=50.0),
            RouteQuote("B", 100.0, 1.0, 1.0, latency_ms=10.0),
        ),
    )
    assert decision.broker == "B"


def test_router_rejects_duplicate_routes() -> None:
    with pytest.raises(ValueError, match="duplicate broker"):
        SmartOrderRouter().select(
            _order(),
            (
                RouteQuote("A", 100.0, 1.0, 1.0),
                RouteQuote("A", 100.0, 1.0, 1.0),
            ),
        )


def test_router_returns_configured_adapter_without_submitting() -> None:
    adapters = {
        "A": PaperBrokerAdapter(),
        "B": PaperBrokerAdapter(),
    }
    adapter, decision = SmartOrderRouter().select_adapter(
        _order(),
        adapters,
        (
            RouteQuote("A", 100.0, 4.0, 2.0),
            RouteQuote("B", 100.0, 2.0, 1.0),
        ),
    )
    assert adapter is adapters["B"]
    assert decision.broker == "B"
    assert not adapter.positions()
