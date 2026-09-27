"""PAPER-03 restart and reconciliation certification.

This harness certifies restart recovery against authoritative paper-broker
state. It never resubmits an order during reconciliation and never enables live
broker execution.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
from execution.engine import ExecutionEngine, OrderRequest, OrderSnapshot, OrderStatus, PositionSnapshot
from execution.production import reconcile_execution_positions

@dataclass(frozen=True, slots=True)
class RestartReconciliationCase:
    name: str
    passed: bool
    detail: str

@dataclass(frozen=True, slots=True)
class RestartReconciliationReport:
    cases: tuple[RestartReconciliationCase, ...]
    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)
    @property
    def failed(self) -> tuple[RestartReconciliationCase, ...]:
        return tuple(case for case in self.cases if not case.passed)

def _case(name: str, check: Callable[[], None]) -> RestartReconciliationCase:
    try:
        check()
    except Exception as exc:
        return RestartReconciliationCase(name, False, f"{type(exc).__name__}: {exc}")
    return RestartReconciliationCase(name, True, "PASS")

def run_restart_reconciliation_certification(
    order_factory: Callable[[], OrderRequest],
) -> RestartReconciliationReport:
    """Run the deterministic PAPER-03 restart/reconciliation matrix."""

    def restart_filled_order() -> None:
        adapter = PaperBrokerAdapter(
            config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0),
            price_provider=lambda _order: 100.0,
        )
        original = ExecutionEngine(adapter)
        result = original.submit(order_factory())
        assert result.snapshot.status is OrderStatus.FILLED
        restarted = ExecutionEngine(adapter)
        recovered = restarted.rehydrate((result.request.client_order_id,))
        snapshot = recovered[result.request.client_order_id]
        assert snapshot.status is OrderStatus.FILLED
        assert snapshot.filled_quantity == result.snapshot.filled_quantity
        assert snapshot.average_fill_price == result.snapshot.average_fill_price
        assert restarted.reconcile_order(result.request.client_order_id)

    def restart_partial_order() -> None:
        adapter = PaperBrokerAdapter(
            config=PaperAdapterConfig(
                slippage_bps=0.0, fee_bps=0.0, partial_fill_ratio=0.5
            ),
            price_provider=lambda _order: 100.0,
        )
        original = ExecutionEngine(adapter)
        result = original.submit(order_factory())
        assert result.snapshot.status is OrderStatus.PARTIALLY_FILLED
        restarted = ExecutionEngine(adapter)
        recovered = restarted.rehydrate((result.request.client_order_id,))
        snapshot = recovered[result.request.client_order_id]
        assert snapshot.status is OrderStatus.PARTIALLY_FILLED
        assert snapshot.filled_quantity == result.snapshot.filled_quantity
        assert restarted.reconcile_order(result.request.client_order_id)

    def unknown_resolves_to_filled_without_resubmit() -> None:
        class LateAckAdapter(PaperBrokerAdapter):
            def __init__(self) -> None:
                super().__init__(
                    config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0),
                    price_provider=lambda _order: 100.0,
                )
                self.submissions = 0
            def submit(self, order: OrderRequest) -> OrderSnapshot:
                self.submissions += 1
                snapshot = super().submit(order)
                raise ConnectionError("ack lost after paper broker accepted order")
        adapter = LateAckAdapter()
        engine = ExecutionEngine(adapter)
        result = engine.submit(order_factory())
        assert result.snapshot.status is OrderStatus.UNKNOWN
        assert adapter.submissions == 1
        recovered = engine.recover_unknown(result.request.client_order_id)
        assert recovered.status is OrderStatus.FILLED
        assert adapter.submissions == 1
        assert engine.reconcile_order(result.request.client_order_id)

    def unknown_missing_state_stays_fail_closed() -> None:
        class MissingStateAdapter(PaperBrokerAdapter):
            def __init__(self) -> None:
                super().__init__()
                self.submissions = 0
            def submit(self, order: OrderRequest) -> OrderSnapshot:
                self.submissions += 1
                raise TimeoutError("paper broker state unavailable")
            def get_order(self, client_order_id: str) -> None:
                return None
        adapter = MissingStateAdapter()
        engine = ExecutionEngine(adapter)
        result = engine.submit(order_factory())
        assert result.snapshot.status is OrderStatus.UNKNOWN
        recovered = engine.recover_unknown(result.request.client_order_id)
        assert recovered.status is OrderStatus.UNKNOWN
        assert adapter.submissions == 1

    def malformed_reconciliation_is_rejected() -> None:
        class MalformedAdapter(PaperBrokerAdapter):
            def get_order(self, client_order_id: str) -> OrderSnapshot:
                return OrderSnapshot(
                    broker_order_id="PAPER-MALFORMED",
                    client_order_id=client_order_id,
                    status=OrderStatus.FILLED,
                    requested_quantity=100.0,
                    filled_quantity=50.0,
                    average_fill_price=100.0,
                )
        adapter = MalformedAdapter(
            config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0),
            price_provider=lambda _order: 100.0,
        )
        engine = ExecutionEngine(adapter)
        result = engine.submit(order_factory())
        assert result.snapshot.status is OrderStatus.FILLED
        restarted = ExecutionEngine(adapter)
        try:
            restarted.rehydrate((result.request.client_order_id,))
        except ValueError as exc:
            assert "FILLED quantity mismatch" in str(exc)
        else:
            raise AssertionError("malformed broker quantity was accepted")

    def signed_position_match_and_mismatch() -> None:
        local = (
            PositionSnapshot("CERT-LONG", 10.0, 100.0),
            PositionSnapshot("CERT-SHORT", -5.0, 120.0),
        )
        broker = (
            PositionSnapshot("CERT-LONG", 10.0, 100.0),
            PositionSnapshot("CERT-SHORT", -5.0, 120.0),
        )
        assert reconcile_execution_positions(local, broker).safe
        mismatch = (
            PositionSnapshot("CERT-LONG", 9.0, 100.0),
            PositionSnapshot("CERT-SHORT", -5.0, 120.0),
        )
        assert not reconcile_execution_positions(local, mismatch).safe

    def unknown_rehydration_from_broker_truth() -> None:
        adapter = PaperBrokerAdapter()
        first = ExecutionEngine(adapter)
        result = first.submit(order_factory())
        assert result.filled
        restarted = ExecutionEngine(adapter)
        recovered = restarted.rehydrate((result.request.client_order_id,))
        assert recovered[result.request.client_order_id].status is OrderStatus.FILLED
        assert restarted.reconcile_order(result.request.client_order_id)

    cases = (
        _case("restart_filled_order", restart_filled_order),
        _case("restart_partial_order", restart_partial_order),
        _case("unknown_resolves_to_filled_without_resubmit", unknown_resolves_to_filled_without_resubmit),
        _case("unknown_missing_state_stays_fail_closed", unknown_missing_state_stays_fail_closed),
        _case("malformed_reconciliation_is_rejected", malformed_reconciliation_is_rejected),
        _case("signed_position_match_and_mismatch", signed_position_match_and_mismatch),
        _case("unknown_rehydration_from_broker_truth", unknown_rehydration_from_broker_truth),
    )
    return RestartReconciliationReport(cases)

__all__ = [
    "RestartReconciliationCase",
    "RestartReconciliationReport",
    "run_restart_reconciliation_certification",
]
