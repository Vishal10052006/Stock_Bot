"""Paper execution certification matrix.

This module is a deterministic certification harness for the broker-neutral paper
adapter. It composes the existing ExecutionEngine, reconciliation, monitoring,
parity, and safety controls; it does not enable or contact a live broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
from execution.engine import (
    ExecutionEngine,
    OrderRequest,
    OrderSnapshot,
    OrderStatus,
    PositionSnapshot,
)
from execution.production import (
    ExecutionAssumptions,
    ExecutionMonitor,
    PaperSoakRunner,
    assert_execution_backtest_parity,
    reconcile_execution_positions,
    validate_kill_switch,
)
from execution.certification import (
    OperationalRunbook,
    validate_replay_idempotency,
)


@dataclass(frozen=True, slots=True)
class PaperCertificationCase:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PaperCertificationReport:
    cases: tuple[PaperCertificationCase, ...]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)

    @property
    def failed(self) -> tuple[PaperCertificationCase, ...]:
        return tuple(case for case in self.cases if not case.passed)


def _case(name: str, check: Callable[[], None]) -> PaperCertificationCase:
    try:
        check()
    except Exception as exc:
        return PaperCertificationCase(name, False, f"{type(exc).__name__}: {exc}")
    return PaperCertificationCase(name, True, "PASS")


def run_paper_certification(
    order_factory: Callable[[], OrderRequest],
) -> PaperCertificationReport:
    """Run the complete deterministic paper certification matrix.

    The matrix intentionally covers control boundaries and failure semantics,
    rather than treating a successful fill as sufficient certification.
    """

    def full_fill() -> None:
        engine = ExecutionEngine(
            PaperBrokerAdapter(
                config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0),
                price_provider=lambda _order: 100.0,
            )
        )
        result = engine.submit(order_factory())
        assert result.snapshot.status is OrderStatus.FILLED
        assert result.snapshot.filled_quantity == result.snapshot.requested_quantity
        assert len(result.snapshot.fills) == 1

    def partial_fill() -> None:
        engine = ExecutionEngine(
            PaperBrokerAdapter(
                config=PaperAdapterConfig(
                    slippage_bps=0.0, fee_bps=0.0, partial_fill_ratio=0.5
                ),
                price_provider=lambda _order: 100.0,
            )
        )
        result = engine.submit(order_factory())
        assert result.snapshot.status is OrderStatus.PARTIALLY_FILLED
        assert 0.0 < result.snapshot.filled_quantity < result.snapshot.requested_quantity

    def broker_rejection() -> None:
        class RejectingAdapter(PaperBrokerAdapter):
            def submit(self, order: OrderRequest) -> OrderSnapshot:
                return OrderSnapshot(
                    broker_order_id="CERT-REJECT-1",
                    client_order_id=order.client_order_id,
                    status=OrderStatus.REJECTED_BROKER,
                    requested_quantity=order.quantity,
                    reason="certification broker rejection",
                )

        result = ExecutionEngine(RejectingAdapter()).submit(order_factory())
        assert result.snapshot.status is OrderStatus.REJECTED_BROKER
        assert not result.accepted

    def unknown_recovery_is_fail_closed() -> None:
        class UnknownAdapter(PaperBrokerAdapter):
            def __init__(self) -> None:
                super().__init__()
                self.submissions = 0

            def submit(self, order: OrderRequest) -> OrderSnapshot:
                self.submissions += 1
                raise TimeoutError("certification timeout")

            def get_order(self, client_order_id: str) -> None:
                return None

        adapter = UnknownAdapter()
        engine = ExecutionEngine(adapter)
        result = engine.submit(order_factory())
        assert result.snapshot.status is OrderStatus.UNKNOWN
        recovered = engine.recover_unknown(result.request.client_order_id)
        assert recovered.status is OrderStatus.UNKNOWN
        assert adapter.submissions == 1

    def duplicate_replay() -> None:
        engine = ExecutionEngine(PaperBrokerAdapter())
        first, second = validate_replay_idempotency(engine, order_factory())
        assert first.snapshot.broker_order_id == second.snapshot.broker_order_id
        assert len(engine.journal) == 1

    def restart_recovery() -> None:
        adapter = PaperBrokerAdapter(
            config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0),
            price_provider=lambda _order: 100.0,
        )
        first = ExecutionEngine(adapter)
        result = first.submit(order_factory())
        assert result.filled

        second = ExecutionEngine(adapter)
        recovered = second.rehydrate((result.request.client_order_id,))
        assert recovered[result.request.client_order_id].status is OrderStatus.FILLED
        assert second.reconcile_order(result.request.client_order_id)

    def signed_position_reconciliation() -> None:
        local = (PositionSnapshot("CERT", -10.0, 100.0),)
        broker = (PositionSnapshot("CERT", -10.0, 100.0),)
        assert reconcile_execution_positions(local, broker).safe

        mismatch = (PositionSnapshot("CERT", -9.0, 100.0),)
        assert not reconcile_execution_positions(local, mismatch).safe

    def monitoring_and_soak() -> None:
        engine = ExecutionEngine(PaperBrokerAdapter())
        monitor = ExecutionMonitor()
        first = engine.submit(order_factory())
        monitor.record(first)
        snapshot = monitor.snapshot(engine)
        assert snapshot.orders == 1
        assert snapshot.filled == 1

        soak = PaperSoakRunner(engine).run([order_factory()])
        assert soak.passed
        assert soak.unknown == 0

    def parity_and_controls() -> None:
        assumptions = ExecutionAssumptions(slippage_bps=5.0, fee_bps=2.0)
        assert_execution_backtest_parity(assumptions, assumptions)
        assert validate_kill_switch()
        assert OperationalRunbook().validate()

    cases = (
        _case("full_fill", full_fill),
        _case("partial_fill", partial_fill),
        _case("broker_rejection", broker_rejection),
        _case("unknown_recovery_fail_closed", unknown_recovery_is_fail_closed),
        _case("duplicate_replay_idempotency", duplicate_replay),
        _case("restart_recovery", restart_recovery),
        _case("signed_position_reconciliation", signed_position_reconciliation),
        _case("monitoring_and_paper_soak", monitoring_and_soak),
        _case("backtest_parity_and_operational_controls", parity_and_controls),
    )
    return PaperCertificationReport(cases)


__all__ = [
    "PaperCertificationCase",
    "PaperCertificationReport",
    "run_paper_certification",
]
