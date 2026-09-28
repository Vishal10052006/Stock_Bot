"""PAPER-06 / E15 execution-monitoring certification.

This certification composes the existing execution observability primitives. It
does not create trading authority, submit live broker orders, alter Risk/Strategy,
or replace the central Monitoring Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
from execution.engine import (
    ExecutionEngine,
    ExecutionResult,
    OrderRequest,
    OrderSnapshot,
    OrderStatus,
    PositionSnapshot,
)
from execution.production import ExecutionMonitor, reconcile_execution_positions
from monitoring.execution import (
    ExecutionMonitoringSnapshot,
    evaluate_execution_monitoring,
)


@dataclass(frozen=True, slots=True)
class MonitoringCertificationCase:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class MonitoringCertificationReport:
    cases: tuple[MonitoringCertificationCase, ...]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)

    @property
    def failed(self) -> tuple[MonitoringCertificationCase, ...]:
        return tuple(case for case in self.cases if not case.passed)


def _case(name: str, check: Callable[[], None]) -> MonitoringCertificationCase:
    try:
        check()
    except Exception as exc:
        return MonitoringCertificationCase(
            name, False, f"{type(exc).__name__}: {exc}"
        )
    return MonitoringCertificationCase(name, True, "PASS")


def run_monitoring_certification(
    order_factory: Callable[[], OrderRequest],
) -> MonitoringCertificationReport:
    """Run deterministic E15 execution-monitoring certification."""

    def full_fill_metrics() -> None:
        engine = ExecutionEngine(
            PaperBrokerAdapter(
                config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=0.0),
                price_provider=lambda _order: 100.0,
            )
        )
        monitor = ExecutionMonitor()
        result = engine.submit(order_factory())
        monitor.record(result)
        snapshot = monitor.snapshot(engine)

        assert snapshot.orders == 1
        assert snapshot.filled == 1
        assert snapshot.partial == 0
        assert snapshot.rejected == 0
        assert snapshot.unknown == 0
        assert snapshot.requested_quantity == result.request.quantity
        assert snapshot.filled_quantity == result.snapshot.filled_quantity
        assert snapshot.fill_ratio == 1.0
        assert snapshot.rejection_rate == 0.0
        assert monitor.collector.values("execution.latency_ms")

    def partial_fill_metrics() -> None:
        engine = ExecutionEngine(
            PaperBrokerAdapter(
                config=PaperAdapterConfig(
                    slippage_bps=0.0,
                    fee_bps=0.0,
                    partial_fill_ratio=0.5,
                ),
                price_provider=lambda _order: 100.0,
            )
        )
        monitor = ExecutionMonitor()
        result = engine.submit(order_factory())
        monitor.record(result)
        snapshot = monitor.snapshot(engine)

        assert result.snapshot.status is OrderStatus.PARTIALLY_FILLED
        assert snapshot.orders == 1
        assert snapshot.partial == 1
        assert snapshot.filled == 0
        assert snapshot.fill_ratio == 0.5

    def rejection_metrics() -> None:
        class RejectingAdapter(PaperBrokerAdapter):
            def submit(self, order: OrderRequest) -> OrderSnapshot:
                return OrderSnapshot(
                    broker_order_id="PAPER06-REJECT",
                    client_order_id=order.client_order_id,
                    status=OrderStatus.REJECTED_BROKER,
                    requested_quantity=order.quantity,
                    reason="PAPER-06 rejection",
                )

        engine = ExecutionEngine(RejectingAdapter())
        monitor = ExecutionMonitor()
        result = engine.submit(order_factory())
        monitor.record(result)
        snapshot = monitor.snapshot(engine)

        assert snapshot.orders == 1
        assert snapshot.rejected == 1
        assert snapshot.rejection_rate == 1.0
        assert snapshot.filled == 0

    def unknown_is_observable_without_retry() -> None:
        class UnknownAdapter(PaperBrokerAdapter):
            def __init__(self) -> None:
                super().__init__()
                self.submissions = 0

            def submit(self, order: OrderRequest) -> OrderSnapshot:
                self.submissions += 1
                raise TimeoutError("PAPER-06 timeout")

            def get_order(self, client_order_id: str) -> None:
                return None

        adapter = UnknownAdapter()
        engine = ExecutionEngine(adapter)
        monitor = ExecutionMonitor()
        result = engine.submit(order_factory())
        monitor.record(result)
        snapshot = monitor.snapshot(engine)

        assert result.snapshot.status is OrderStatus.UNKNOWN
        assert snapshot.unknown == 1
        assert snapshot.unknown_rate == 1.0

        recovered = engine.recover_unknown(result.request.client_order_id)
        monitor.record(
            ExecutionResult(
                request=result.request,
                snapshot=recovered,
                accepted=False,
                latency_ms=0.0,
                error=recovered.reason or None,
            )
        )
        assert adapter.submissions == 1

    def fees_are_observable() -> None:
        engine = ExecutionEngine(
            PaperBrokerAdapter(
                config=PaperAdapterConfig(slippage_bps=0.0, fee_bps=10.0),
                price_provider=lambda _order: 100.0,
            )
        )
        monitor = ExecutionMonitor()
        result = engine.submit(order_factory())
        monitor.record(result)
        metrics = engine.metrics()

        assert result.filled
        assert metrics.total_fees > 0.0
        assert monitor.snapshot(engine).filled_quantity == result.snapshot.filled_quantity

    def reconciliation_failure_is_observable() -> None:
        local = (PositionSnapshot("ITC", 100.0, 100.0),)
        broker = (PositionSnapshot("ITC", 90.0, 100.0),)
        report = reconcile_execution_positions(local, broker)
        assert not report.safe
        assert report.mismatches

    def monitoring_policy_is_descriptive_only() -> None:
        metrics, alerts = evaluate_execution_monitoring(
            ExecutionMonitoringSnapshot(
                order_count=10,
                filled_count=7,
                rejected_count=2,
                partial_fill_count=1,
                total_latency_seconds=2.0,
                total_slippage=3.0,
            ),
            max_rejection_rate=0.10,
        )
        assert metrics["fill_rate"] == 0.7
        assert metrics["rejection_rate"] == 0.2
        assert metrics["partial_fill_rate"] == 0.1
        assert metrics["average_latency_seconds"] == 0.2
        assert metrics["average_slippage"] == 0.3
        assert alerts == ("EXECUTION_REJECTION_RATE_HIGH",)

    def monitor_is_observation_only() -> None:
        engine = ExecutionEngine(PaperBrokerAdapter())
        monitor = ExecutionMonitor()
        assert len(engine.journal) == 0
        monitor.snapshot(engine)
        result = engine.submit(order_factory())
        monitor.record(result)
        assert len(engine.journal) == 1

    cases = (
        _case("full_fill_metrics", full_fill_metrics),
        _case("partial_fill_metrics", partial_fill_metrics),
        _case("rejection_metrics", rejection_metrics),
        _case("unknown_observed_without_retry", unknown_is_observable_without_retry),
        _case("fees_are_observable", fees_are_observable),
        _case("reconciliation_failure_is_observable", reconciliation_failure_is_observable),
        _case("monitoring_policy_is_descriptive_only", monitoring_policy_is_descriptive_only),
        _case("monitor_is_observation_only", monitor_is_observation_only),
    )
    return MonitoringCertificationReport(cases)


__all__ = [
    "MonitoringCertificationCase",
    "MonitoringCertificationReport",
    "run_monitoring_certification",
]
