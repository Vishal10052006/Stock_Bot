"""End-to-end signed position transition lifecycle tests.

These tests verify the frozen boundary:

    Portfolio -> Risk -> Safety/Execution Authorization -> Paper Fill
                         -> actual signed position -> next Portfolio state

The Portfolio state is rebuilt from the actual paper fill, not from the
requested/projected intent. No broker I/O is involved.
"""

from __future__ import annotations

import pandas as pd
import pytest

from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
    authorize_risk_decision,
)
from execution.engine import OrderStatus
from paper.runtime import PaperTradingConfig, PaperTradingRuntime
from portfolio.contracts import (
    PortfolioAction,
    PortfolioLimits,
    PortfolioPosition,
    PortfolioSnapshot,
    PositionTransition,
    TradeIntent,
)
from portfolio.manager import PortfolioManager
from trading.risk.contracts import RiskPositionContext, RiskPositionTransition
from trading.risk.engine import RiskEngine, RiskInput
from trading.signals.models import CandidateDirection, TradeCandidate
from trading.strategy.models import StrategyDirection


TIMESTAMP = pd.Timestamp("2026-09-24 10:00:00+05:30")
PRICE = 100.0


def _candidate(
    *,
    timestamp: pd.Timestamp,
    side: str,
) -> TradeCandidate:
    direction = (
        CandidateDirection.LONG
        if side == "BUY"
        else CandidateDirection.SHORT
    )
    stop = 96.0 if direction is CandidateDirection.LONG else 104.0
    return TradeCandidate(
        timestamp=timestamp,
        symbol="ITC",
        direction=direction,
        entry_price=PRICE,
        stop_price=stop,
        policy_version="transition_test_v1.0",
    )


def _risk_transition(transition: PositionTransition) -> RiskPositionTransition:
    return RiskPositionTransition[transition.value]


def _portfolio_snapshot(
    runtime: PaperTradingRuntime,
    *,
    timestamp: pd.Timestamp,
) -> PortfolioSnapshot:
    """Project actual paper positions into the Portfolio contract."""
    positions: list[PortfolioPosition] = []
    for position in runtime.positions:
        if position.quantity == 0.0:
            continue
        signed_quantity = (
            position.quantity
            if position.direction is StrategyDirection.LONG
            else -position.quantity
        )
        positions.append(
            PortfolioPosition(
                symbol=position.symbol,
                quantity=signed_quantity,
                mark_price=PRICE,
            )
        )
    return PortfolioSnapshot(
        as_of=timestamp,
        equity=runtime.account_snapshot({"ITC": PRICE})[0],
        positions=tuple(positions),
    )


def _execute_intent(
    *,
    runtime: PaperTradingRuntime,
    portfolio: PortfolioSnapshot,
    intent: TradeIntent,
    timestamp: pd.Timestamp,
) -> tuple[PortfolioSnapshot, PositionTransition]:
    """Run one intent through Portfolio -> Risk -> Authorization -> Paper."""
    portfolio_decision = PortfolioManager(PortfolioLimits()).evaluate(
        portfolio,
        intent,
    )

    assert portfolio_decision.action is PortfolioAction.APPROVE

    transition = portfolio_decision.position_transition
    existing = next(
        (
            position
            for position in portfolio.positions
            if position.symbol == intent.symbol
        ),
        None,
    )
    context = RiskPositionContext(
        transition=_risk_transition(transition),
        existing_quantity=existing.quantity if existing else 0.0,
        projected_quantity=(
            existing.quantity if existing else 0.0
        ) + (intent.quantity if intent.side == "BUY" else -intent.quantity),
    )

    candidate = _candidate(timestamp=timestamp, side=intent.side)
    risk = RiskEngine().evaluate(
        RiskInput(
            timestamp=timestamp,
            symbol="ITC",
            candidate=candidate,
            available_equity=portfolio.equity,
            day_start_equity=portfolio.equity,
            open_positions=len(portfolio.positions),
            symbol_already_open=existing is not None,
            position_context=context,
            gross_exposure=portfolio.gross_exposure,
        )
    )

    assert risk.decision.status.value == "APPROVED"
    assert risk.decision.position_transition is context.transition
    assert risk.decision.approved_projected_quantity is not None

    authorization = authorize_risk_decision(
        risk.decision,
        risk_decision_id=f"{timestamp.isoformat()}:ITC",
    )
    assert authorization.status is ExecutionAuthorizationStatus.AUTHORIZED
    assert authorization.approved_quantity == risk.decision.approved_quantity
    assert authorization.position_transition is context.transition

    order = runtime.submit(
        authorization,
        price=PRICE,
    )
    assert order.status.value == "FILLED"
    assert order.quantity == authorization.approved_quantity

    actual = _portfolio_snapshot(runtime, timestamp=timestamp)
    return actual, transition


@pytest.mark.parametrize(
    ("start", "side", "order_quantity", "expected"),
    [
        (0.0, "BUY", 10.0, 10.0),
        (10.0, "BUY", 5.0, 15.0),
        (15.0, "SELL", 10.0, 5.0),
        (5.0, "SELL", 5.0, 0.0),
        (10.0, "SELL", 15.0, -5.0),
    ],
)
def test_long_side_transition_matrix_matches_actual_paper_position(
    start: float,
    side: str,
    order_quantity: float,
    expected: float,
) -> None:
    """Each transition must produce the expected actual signed position."""
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(slippage_bps=0.0, fee_bps=0.0)
    )

    if start != 0.0:
        bootstrap_side = "BUY" if start > 0 else "SELL"
        bootstrap = TradeIntent(
            "ITC",
            abs(start),
            PRICE,
            bootstrap_side,
            decision_id="bootstrap",
        )
        portfolio, _ = _execute_intent(
            runtime=runtime,
            portfolio=PortfolioSnapshot(
                as_of=TIMESTAMP,
                equity=100_000.0,
                positions=(),
            ),
            intent=bootstrap,
            timestamp=TIMESTAMP,
        )
    else:
        portfolio = PortfolioSnapshot(
            as_of=TIMESTAMP,
            equity=100_000.0,
            positions=(),
        )

    intent = TradeIntent(
        "ITC",
        order_quantity,
        PRICE,
        side,
        decision_id=f"{side}-{order_quantity}",
    )
    actual, transition = _execute_intent(
        runtime=runtime,
        portfolio=portfolio,
        intent=intent,
        timestamp=TIMESTAMP + pd.Timedelta(minutes=1),
    )

    assert transition in {
        PositionTransition.OPEN,
        PositionTransition.INCREASE,
        PositionTransition.REDUCE,
        PositionTransition.FLATTEN,
        PositionTransition.REVERSE,
    }

    position = next(
        (p for p in actual.positions if p.symbol == "ITC"),
        None,
    )
    actual_quantity = position.quantity if position is not None else 0.0
    assert actual_quantity == expected


def test_complete_long_lifecycle_uses_actual_fill_as_next_portfolio_state() -> None:
    """OPEN -> INCREASE -> REDUCE -> FLATTEN ends exactly at flat."""
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(slippage_bps=0.0, fee_bps=0.0)
    )
    portfolio = PortfolioSnapshot(
        as_of=TIMESTAMP,
        equity=100_000.0,
        positions=(),
    )

    steps = [
        ("BUY", 10.0, 10.0, PositionTransition.OPEN),
        ("BUY", 5.0, 15.0, PositionTransition.INCREASE),
        ("SELL", 10.0, 5.0, PositionTransition.REDUCE),
        ("SELL", 5.0, 0.0, PositionTransition.FLATTEN),
    ]

    for index, (side, quantity, expected, transition_expected) in enumerate(steps):
        portfolio, transition = _execute_intent(
            runtime=runtime,
            portfolio=portfolio,
            intent=TradeIntent(
                "ITC",
                quantity,
                PRICE,
                side,
                decision_id=f"lifecycle-{index}",
            ),
            timestamp=TIMESTAMP + pd.Timedelta(minutes=index),
        )
        assert transition is transition_expected
        position = next(
            (p for p in portfolio.positions if p.symbol == "ITC"),
            None,
        )
        assert (position.quantity if position else 0.0) == expected


def test_complete_short_lifecycle_and_reverse_to_long() -> None:
    """OPEN short -> INCREASE -> REDUCE -> FLATTEN -> OPEN long."""
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(slippage_bps=0.0, fee_bps=0.0)
    )
    portfolio = PortfolioSnapshot(
        as_of=TIMESTAMP,
        equity=100_000.0,
        positions=(),
    )

    steps = [
        ("SELL", 10.0, -10.0, PositionTransition.OPEN),
        ("SELL", 5.0, -15.0, PositionTransition.INCREASE),
        ("BUY", 10.0, -5.0, PositionTransition.REDUCE),
        ("BUY", 5.0, 0.0, PositionTransition.FLATTEN),
        ("BUY", 5.0, 5.0, PositionTransition.OPEN),
    ]

    for index, (side, quantity, expected, transition_expected) in enumerate(steps):
        portfolio, transition = _execute_intent(
            runtime=runtime,
            portfolio=portfolio,
            intent=TradeIntent(
                "ITC",
                quantity,
                PRICE,
                side,
                decision_id=f"short-lifecycle-{index}",
            ),
            timestamp=TIMESTAMP + pd.Timedelta(minutes=index),
        )
        assert transition is transition_expected
        position = next(
            (p for p in portfolio.positions if p.symbol == "ITC"),
            None,
        )
        assert (position.quantity if position else 0.0) == expected


def test_reverse_preserves_actual_projected_position_provenance() -> None:
    """A +10 -> -5 reverse submits 15 but actual state becomes -5."""
    runtime = PaperTradingRuntime(
        config=PaperTradingConfig(slippage_bps=0.0, fee_bps=0.0)
    )
    portfolio = PortfolioSnapshot(
        as_of=TIMESTAMP,
        equity=100_000.0,
        positions=(),
    )

    portfolio, _ = _execute_intent(
        runtime=runtime,
        portfolio=portfolio,
        intent=TradeIntent(
            "ITC",
            10.0,
            PRICE,
            "BUY",
            decision_id="bootstrap-long",
        ),
        timestamp=TIMESTAMP,
    )

    intent = TradeIntent(
        "ITC",
        15.0,
        PRICE,
        "SELL",
        decision_id="reverse",
    )
    actual, transition = _execute_intent(
        runtime=runtime,
        portfolio=portfolio,
        intent=intent,
        timestamp=TIMESTAMP + pd.Timedelta(minutes=1),
    )

    assert transition is PositionTransition.REVERSE
    position = next(p for p in actual.positions if p.symbol == "ITC")
    assert position.quantity == -5.0
    assert runtime.journal[-1].quantity == 15.0


def test_partial_fill_builds_portfolio_from_actual_filled_quantity() -> None:
    """Risk-approved 10 does not imply a 10-share Portfolio after a 6-share fill."""
    from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
    from execution.engine import ExecutionEngine

    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.6,
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: PRICE,
    )
    engine = ExecutionEngine(adapter)

    authorization = ExecutionAuthorization(
        timestamp=TIMESTAMP,
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test approval",
        risk_version="RISK-v1.0",
        approved_quantity=10.0,
        approved_notional=10.0 * PRICE,
    )
    request = engine.from_authorization(
        authorization,
        decision_id="partial-fill",
    )

    result = engine.submit(request)

    assert result.snapshot.status.value == "PARTIALLY_FILLED"
    assert result.snapshot.requested_quantity == 10.0
    assert result.snapshot.filled_quantity == 6.0

    broker_positions = adapter.positions()
    assert len(broker_positions) == 1
    assert broker_positions[0].quantity == 6.0

    actual_portfolio = PortfolioSnapshot(
        as_of=TIMESTAMP,
        equity=100_000.0,
        positions=(
            PortfolioPosition(
                symbol=broker_positions[0].symbol,
                quantity=broker_positions[0].quantity,
                mark_price=PRICE,
            ),
        ),
    )

    assert actual_portfolio.positions[0].quantity == 6.0
    assert actual_portfolio.gross_exposure == 6.0 * PRICE
    assert actual_portfolio.gross_exposure < authorization.approved_notional
    assert engine.reconcile_positions(broker_positions)


def test_partial_short_fill_creates_actual_negative_portfolio_exposure() -> None:
    """A partial SELL fill must create the actual signed short, not the request size."""
    from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
    from execution.engine import ExecutionEngine

    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.4,
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: PRICE,
    )
    engine = ExecutionEngine(adapter)

    authorization = ExecutionAuthorization(
        timestamp=TIMESTAMP,
        symbol="ITC",
        direction=StrategyDirection.SHORT,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test approval",
        risk_version="RISK-v1.0",
        approved_quantity=10.0,
        approved_notional=10.0 * PRICE,
    )
    request = engine.from_authorization(
        authorization,
        decision_id="partial-short-fill",
    )

    result = engine.submit(request)

    assert result.snapshot.status.value == "PARTIALLY_FILLED"
    assert result.snapshot.filled_quantity == 4.0

    broker_positions = adapter.positions()
    assert broker_positions[0].quantity == -4.0

    actual_portfolio = PortfolioSnapshot(
        as_of=TIMESTAMP,
        equity=100_000.0,
        positions=(
            PortfolioPosition(
                symbol=broker_positions[0].symbol,
                quantity=broker_positions[0].quantity,
                mark_price=PRICE,
            ),
        ),
    )

    assert actual_portfolio.positions[0].quantity == -4.0
    assert actual_portfolio.gross_exposure == 4.0 * PRICE
    assert engine.reconcile_positions(broker_positions)


def test_partial_fill_continuation_updates_portfolio_only_after_actual_fill() -> None:
    """Portfolio tracks 6 shares first, then 10 only after the remaining 4 fill."""
    from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
    from execution.engine import ExecutionEngine

    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.6,
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: PRICE,
    )
    engine = ExecutionEngine(adapter)

    authorization = ExecutionAuthorization(
        timestamp=TIMESTAMP,
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test approval",
        risk_version="RISK-v1.0",
        approved_quantity=10.0,
        approved_notional=10.0 * PRICE,
    )
    request = engine.from_authorization(
        authorization,
        decision_id="partial-lifecycle",
    )

    first = engine.submit(request)
    assert first.snapshot.filled_quantity == 6.0

    first_positions = adapter.positions()
    assert first_positions[0].quantity == 6.0

    first_portfolio = PortfolioSnapshot(
        as_of=TIMESTAMP,
        equity=100_000.0,
        positions=(
            PortfolioPosition("ITC", 6.0, PRICE),
        ),
    )
    assert first_portfolio.positions[0].quantity == 6.0

    adapter.fill_remaining(request.client_order_id)
    final = engine.refresh(request.client_order_id)

    assert final.status is not None
    assert final.status.value == "FILLED"
    final_positions = adapter.positions()
    assert final_positions[0].quantity == 10.0

    final_portfolio = PortfolioSnapshot(
        as_of=TIMESTAMP + pd.Timedelta(minutes=1),
        equity=100_000.0,
        positions=(
            PortfolioPosition("ITC", 10.0, PRICE),
        ),
    )
    assert final_portfolio.positions[0].quantity == 10.0
    assert engine.reconcile_positions(final_positions)


def test_partial_fill_cancellation_keeps_portfolio_at_actual_filled_quantity() -> None:
    """Portfolio exposure remains at the broker-confirmed partial fill after cancel."""
    from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
    from execution.engine import ExecutionEngine

    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.6,
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: PRICE,
    )
    engine = ExecutionEngine(adapter)

    authorization = ExecutionAuthorization(
        timestamp=TIMESTAMP,
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test approval",
        risk_version="RISK-v1.0",
        approved_quantity=10.0,
        approved_notional=10.0 * PRICE,
    )
    request = engine.from_authorization(
        authorization,
        decision_id="partial-cancel-lifecycle",
    )

    first = engine.submit(request)
    assert first.snapshot.filled_quantity == 6.0

    cancelled = engine.cancel(request.client_order_id)
    assert cancelled.status is OrderStatus.CANCELLED
    assert cancelled.filled_quantity == 6.0

    positions = adapter.positions()
    assert positions[0].quantity == 6.0

    portfolio = PortfolioSnapshot(
        as_of=TIMESTAMP + pd.Timedelta(minutes=1),
        equity=100_000.0,
        positions=(PortfolioPosition("ITC", 6.0, PRICE),),
    )
    assert portfolio.positions[0].quantity == 6.0
    assert portfolio.gross_exposure == 6.0 * PRICE
    assert engine.reconcile_positions(positions)


def test_cancel_fill_race_rebuilds_portfolio_from_final_broker_state() -> None:
    """Final broker FILLED state wins over an earlier local cancellation."""
    from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
    from execution.engine import ExecutionEngine

    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.6,
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: PRICE,
    )
    engine = ExecutionEngine(adapter)
    authorization = ExecutionAuthorization(
        timestamp=TIMESTAMP,
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test approval",
        risk_version="RISK-v1.0",
        approved_quantity=10.0,
        approved_notional=10.0 * PRICE,
    )
    request = engine.from_authorization(
        authorization,
        decision_id="cancel-fill-race",
    )

    engine.submit(request)
    engine.cancel(request.client_order_id)
    adapter.fill_remaining(request.client_order_id, after_cancel=True)

    final_order = engine.refresh(request.client_order_id)
    final_positions = adapter.positions()

    assert final_order.status is OrderStatus.FILLED
    assert final_order.filled_quantity == 10.0
    assert final_positions[0].quantity == 10.0

    portfolio = PortfolioSnapshot(
        as_of=TIMESTAMP + pd.Timedelta(minutes=2),
        equity=100_000.0,
        positions=(PortfolioPosition("ITC", 10.0, PRICE),),
    )
    assert portfolio.gross_exposure == 10.0 * PRICE
    assert engine.reconcile_positions(final_positions)
