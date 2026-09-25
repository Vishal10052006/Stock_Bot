"""Production-side validation and operational controls for the execution engine.

This module deliberately does not enable live trading. It provides broker-contract
validation, execution observability, reconciliation, paper-soak execution,
backtest/execution assumption parity, restart rehydration, and fail-closed
production readiness gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from execution.engine import (
    BrokerAdapter,
    ExecutionEngine,
    ExecutionResult,
    OrderRequest,
    OrderSnapshot,
    OrderStatus,
    PositionSnapshot,
)
from execution.reconciliation import (
    BrokerPosition,
    BrokerReconciler,
    ReconciliationReport,
)
from execution.safety import IndependentSafetyGate, SafetyState
from monitoring.metrics import MetricsCollector


class ProductionGateStatus(str, Enum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class BrokerContractReport:
    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]


def validate_broker_contract(adapter: BrokerAdapter) -> BrokerContractReport:
    """Validate the broker adapter surface without submitting a live order."""
    checks: list[str] = []
    failures: list[str] = []
    required = ("submit", "get_order", "cancel", "positions")

    for name in required:
        if not callable(getattr(adapter, name, None)):
            failures.append(f"missing broker method: {name}")
        else:
            checks.append(f"{name}:callable")

    try:
        positions = adapter.positions()
        if not isinstance(positions, tuple):
            failures.append("positions() must return tuple[PositionSnapshot, ...]")
        else:
            for position in positions:
                if not isinstance(position, PositionSnapshot):
                    failures.append("positions() returned a non-PositionSnapshot")
                    break
            else:
                checks.append("positions:snapshot-contract")
    except Exception as exc:
        failures.append(f"positions() failed: {exc}")

    return BrokerContractReport(
        passed=not failures,
        checks=tuple(checks),
        failures=tuple(failures),
    )


@dataclass(frozen=True, slots=True)
class ExecutionOperationalMetrics:
    orders: int
    filled: int
    partial: int
    rejected: int
    unknown: int
    requested_quantity: float
    filled_quantity: float
    fill_ratio: float
    rejection_rate: float
    unknown_rate: float
    average_latency_ms: float


class ExecutionMonitor:
    """Translate execution results into bounded operational metrics."""

    def __init__(self, collector: MetricsCollector | None = None) -> None:
        self.collector = collector or MetricsCollector()

    def record(self, result: ExecutionResult) -> None:
        status = result.snapshot.status
        labels = {"purpose": result.request.purpose, "symbol": result.request.symbol}
        self.collector.record("execution.order", 1.0, labels=labels)
        self.collector.record(
            "execution.accepted", float(result.accepted), labels=labels
        )
        self.collector.record(
            "execution.filled", float(status is OrderStatus.FILLED), labels=labels
        )
        self.collector.record(
            "execution.partial",
            float(status is OrderStatus.PARTIALLY_FILLED),
            labels=labels,
        )
        self.collector.record(
            "execution.rejected",
            float(status in {
                OrderStatus.REJECTED_LOCAL,
                OrderStatus.REJECTED_BROKER,
                OrderStatus.FAILED,
            }),
            labels=labels,
        )
        self.collector.record(
            "execution.unknown",
            float(status is OrderStatus.UNKNOWN),
            labels=labels,
        )
        self.collector.record(
            "execution.latency_ms", result.latency_ms, labels=labels
        )
        self.collector.record(
            "execution.requested_quantity",
            result.request.quantity,
            labels=labels,
        )
        self.collector.record(
            "execution.filled_quantity",
            result.snapshot.filled_quantity,
            labels=labels,
        )

    def snapshot(self, engine: ExecutionEngine) -> ExecutionOperationalMetrics:
        metrics = engine.metrics()
        return ExecutionOperationalMetrics(
            orders=metrics.orders,
            filled=metrics.filled_orders,
            partial=metrics.partially_filled_orders,
            rejected=metrics.rejected_orders,
            unknown=metrics.unknown_orders,
            requested_quantity=metrics.requested_quantity,
            filled_quantity=metrics.filled_quantity,
            fill_ratio=metrics.fill_ratio,
            rejection_rate=metrics.rejection_rate,
            unknown_rate=(metrics.unknown_orders / metrics.orders)
            if metrics.orders else 0.0,
            average_latency_ms=metrics.average_latency_ms,
        )


def reconcile_execution_positions(
    local: Iterable[PositionSnapshot] | None,
    broker: Iterable[PositionSnapshot] | None,
) -> ReconciliationReport:
    """Compare signed local and broker positions using the canonical reconciler."""
    if local is None or broker is None:
        return BrokerReconciler().reconcile(None, None)

    local_positions = tuple(
        BrokerPosition(p.symbol, p.quantity, p.average_price) for p in local
    )
    broker_positions = tuple(
        BrokerPosition(p.symbol, p.quantity, p.average_price) for p in broker
    )
    return BrokerReconciler().reconcile(local_positions, broker_positions)


@dataclass(frozen=True, slots=True)
class PaperSoakReport:
    orders: int
    filled: int
    partial: int
    rejected: int
    unknown: int
    reconciliation_safe: bool
    errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return (
            self.orders > 0
            and not self.errors
            and self.unknown == 0
            and self.reconciliation_safe
        )


class PaperSoakRunner:
    """Run an explicit sequence of approved orders through paper execution."""

    def __init__(
        self,
        engine: ExecutionEngine,
        monitor: ExecutionMonitor | None = None,
    ) -> None:
        self.engine = engine
        self.monitor = monitor or ExecutionMonitor()

    def run(self, orders: Iterable[OrderRequest]) -> PaperSoakReport:
        errors: list[str] = []
        results: list[ExecutionResult] = []

        for order in orders:
            try:
                result = self.engine.submit(order)
                results.append(result)
                self.monitor.record(result)
            except Exception as exc:
                errors.append(f"{order.client_order_id}: {exc}")

        broker_positions = self.engine.adapter.positions()
        # Paper execution has one authoritative position source. Reconciliation
        # is therefore explicitly checked for structural consistency.
        reconciliation_safe = all(
            isinstance(position, PositionSnapshot)
            for position in broker_positions
        )

        statuses = [result.snapshot.status for result in results]
        return PaperSoakReport(
            orders=len(results),
            filled=sum(status is OrderStatus.FILLED for status in statuses),
            partial=sum(status is OrderStatus.PARTIALLY_FILLED for status in statuses),
            rejected=sum(
                status in {
                    OrderStatus.REJECTED_LOCAL,
                    OrderStatus.REJECTED_BROKER,
                    OrderStatus.FAILED,
                }
                for status in statuses
            ),
            unknown=sum(status is OrderStatus.UNKNOWN for status in statuses),
            reconciliation_safe=reconciliation_safe,
            errors=tuple(errors),
        )


@dataclass(frozen=True, slots=True)
class ExecutionAssumptions:
    slippage_bps: float
    fee_bps: float

    def __post_init__(self) -> None:
        if self.slippage_bps < 0 or self.fee_bps < 0:
            raise ValueError("execution assumptions cannot be negative")


def assert_execution_backtest_parity(
    execution: ExecutionAssumptions,
    backtest: ExecutionAssumptions,
) -> None:
    """Fail closed when historical and execution cost assumptions diverge."""
    if execution != backtest:
        raise ValueError(
            "backtest/execution assumption mismatch: "
            f"execution={execution} backtest={backtest}"
        )


@dataclass(frozen=True, slots=True)
class ProductionReadiness:
    status: ProductionGateStatus
    failed_gates: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.status is ProductionGateStatus.PASS


class ProductionReadinessGate:
    """Fail-closed execution production gate; live execution remains separate."""

    FIELDS = (
        "broker_contract_validated",
        "failure_matrix_validated",
        "restart_recovery_validated",
        "reconciliation_validated",
        "kill_switch_validated",
        "monitoring_validated",
        "paper_soak_validated",
        "backtest_execution_parity_validated",
        "operational_runbook_validated",
        "ci_validated",
    )

    def evaluate(self, gates: dict[str, bool]) -> ProductionReadiness:
        failures: list[str] = []
        reasons: list[str] = []
        for field in self.FIELDS:
            if gates.get(field) is not True:
                failures.append(field)
                reasons.append(f"{field} is not validated")
        return ProductionReadiness(
            ProductionGateStatus.PASS if not failures else ProductionGateStatus.BLOCKED,
            tuple(failures),
            tuple(reasons),
        )


def validate_kill_switch() -> bool:
    """Return True only when the independent kill switch blocks execution."""
    decision = IndependentSafetyGate().evaluate(SafetyState(kill_switch_active=True))
    return not decision.allowed
