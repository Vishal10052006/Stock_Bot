"""Execution certification utilities for deterministic production hardening.

These helpers exercise failure semantics without enabling live trading. External
broker certification remains an opt-in integration concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from execution.engine import ExecutionEngine, ExecutionResult, OrderRequest, OrderStatus


class FailureScenario(str, Enum):
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    DUPLICATE_REPLAY = "DUPLICATE_REPLAY"
    BROKER_REJECTION = "BROKER_REJECTION"


@dataclass(frozen=True, slots=True)
class FailureMatrixReport:
    scenarios: tuple[FailureScenario, ...]
    passed: tuple[FailureScenario, ...]
    failures: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return len(self.passed) == len(self.scenarios) and not self.failures


def validate_failure_matrix(
    engine_factory: Callable[[], ExecutionEngine],
    order_factory: Callable[[], OrderRequest],
) -> FailureMatrixReport:
    """Validate fail-closed submission behavior supplied by the test adapter.

    TIMEOUT and NETWORK_ERROR must become UNKNOWN. UNKNOWN must never be
    followed by an automatic submission. Broker rejection must remain a
    terminal rejection.
    """
    scenarios = (
        FailureScenario.TIMEOUT,
        FailureScenario.NETWORK_ERROR,
        FailureScenario.BROKER_REJECTION,
    )
    passed: list[FailureScenario] = []
    failures: list[str] = []

    for scenario in scenarios:
        engine = engine_factory()
        order = order_factory()
        result = engine.submit(order)
        if scenario in {FailureScenario.TIMEOUT, FailureScenario.NETWORK_ERROR}:
            if result.snapshot.status is not OrderStatus.UNKNOWN:
                failures.append(
                    f"{scenario.value}: expected UNKNOWN, got {result.snapshot.status.value}"
                )
                continue
            before = len(getattr(engine.adapter, "submitted_client_ids", ()))
            recovered = engine.recover_unknown(order.client_order_id)
            after = len(getattr(engine.adapter, "submitted_client_ids", ()))
            if recovered.status is not OrderStatus.UNKNOWN:
                failures.append(
                    f"{scenario.value}: missing broker state must remain UNKNOWN"
                )
                continue
            if after != before:
                failures.append(
                    f"{scenario.value}: recovery attempted a duplicate submission"
                )
                continue
        elif result.snapshot.status is not OrderStatus.REJECTED_BROKER:
            failures.append(
                f"{scenario.value}: expected REJECTED_BROKER, "
                f"got {result.snapshot.status.value}"
            )
            continue
        passed.append(scenario)

    return FailureMatrixReport(tuple(scenarios), tuple(passed), tuple(failures))


@dataclass(frozen=True, slots=True)
class RetryBackoffPolicy:
    """Bounded exponential backoff policy for future broker retry orchestration."""

    initial_seconds: float = 0.5
    multiplier: float = 2.0
    max_seconds: float = 8.0
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if self.initial_seconds <= 0:
            raise ValueError("initial_seconds must be positive")
        if self.multiplier < 1:
            raise ValueError("multiplier must be at least 1")
        if self.max_seconds < self.initial_seconds:
            raise ValueError("max_seconds must be >= initial_seconds")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")

    def delay_for(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        if attempt > self.max_attempts:
            raise ValueError("attempt exceeds max_attempts")
        return min(
            self.initial_seconds * (self.multiplier ** (attempt - 1)),
            self.max_seconds,
        )


def validate_replay_idempotency(
    engine: ExecutionEngine, order: OrderRequest
) -> tuple[ExecutionResult, ExecutionResult]:
    """Submit the same immutable order twice and require one broker identity."""
    first = engine.submit(order)
    second = engine.submit(order)
    if first.snapshot.broker_order_id != second.snapshot.broker_order_id:
        raise AssertionError("duplicate replay created a second broker order")
    if second.snapshot != first.snapshot:
        raise AssertionError("duplicate replay changed the authoritative snapshot")
    return first, second


@dataclass(frozen=True, slots=True)
class OperationalRunbook:
    """Machine-readable operational checklist for the execution gate."""

    preflight: tuple[str, ...] = (
        "risk authorization is ACTIVE",
        "independent safety gate allows execution",
        "broker credentials are valid for the intended environment",
        "execution monitoring is running",
        "kill switch is tested and reachable",
    )
    incident: tuple[str, ...] = (
        "activate kill switch",
        "stop new submissions",
        "preserve execution journal and broker identifiers",
        "reconcile broker orders and signed positions",
        "resolve UNKNOWN orders from broker truth",
        "resume only after readiness gates pass",
    )
    shutdown: tuple[str, ...] = (
        "stop new submissions",
        "reconcile open orders",
        "reconcile signed positions",
        "persist execution evidence",
        "verify live execution remains locked unless explicitly certified",
    )

    def validate(self) -> bool:
        return all(self.preflight) and all(self.incident) and all(self.shutdown)
