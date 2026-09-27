"""PAPER-02 failure and recovery certification.

PAPER-02 exercises the existing failure-matrix utility against deterministic
paper adapters. It validates that ambiguous broker outcomes fail closed and
that recovery never becomes an implicit duplicate submission path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from execution.adapters.paper import PaperBrokerAdapter
from execution.certification import FailureScenario, validate_failure_matrix
from execution.engine import ExecutionEngine, OrderRequest, OrderSnapshot, OrderStatus


@dataclass(frozen=True, slots=True)
class FailureRecoveryCertification:
    complete: bool
    scenarios: tuple[FailureScenario, ...]
    passed: tuple[FailureScenario, ...]
    failures: tuple[str, ...]


def run_failure_recovery_certification(
    order_factory: Callable[[], OrderRequest],
) -> FailureRecoveryCertification:
    """Run PAPER-02 using deterministic failure-injection adapters."""

    scenario = {"index": -1}
    scenarios = (
        FailureScenario.TIMEOUT,
        FailureScenario.NETWORK_ERROR,
        FailureScenario.BROKER_REJECTION,
    )

    class InjectedFailureAdapter(PaperBrokerAdapter):
        def __init__(self) -> None:
            super().__init__()
            scenario["index"] += 1
            self.failure = scenarios[scenario["index"]]
            self.submitted_client_ids: list[str] = []

        def submit(self, order: OrderRequest) -> OrderSnapshot:
            self.submitted_client_ids.append(order.client_order_id)
            if self.failure is FailureScenario.TIMEOUT:
                raise TimeoutError("certification timeout")
            if self.failure is FailureScenario.NETWORK_ERROR:
                raise ConnectionError("certification network error")
            return OrderSnapshot(
                broker_order_id="CERT-REJECT",
                client_order_id=order.client_order_id,
                status=OrderStatus.REJECTED_BROKER,
                requested_quantity=order.quantity,
                reason="certification rejection",
            )

        def get_order(self, client_order_id: str) -> None:
            return None

    report = validate_failure_matrix(
        engine_factory=lambda: ExecutionEngine(InjectedFailureAdapter()),
        order_factory=order_factory,
    )
    return FailureRecoveryCertification(
        complete=report.complete,
        scenarios=report.scenarios,
        passed=report.passed,
        failures=report.failures,
    )


__all__ = ["FailureRecoveryCertification", "run_failure_recovery_certification"]
