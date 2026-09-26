"""Fail-closed failure classification and bounded retry policy.

Retries are permitted only for explicitly retryable, observation/read operations.
Order submission is never retried by this policy because an unknown broker
state must be reconciled before any further action.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FailureClass(str, Enum):
    TRANSIENT = "TRANSIENT"
    UNKNOWN = "UNKNOWN"
    TERMINAL = "TERMINAL"


class FailureAction(str, Enum):
    RETRY = "RETRY"
    RECONCILE = "RECONCILE"
    BLOCK = "BLOCK"


@dataclass(frozen=True, slots=True)
class FailureDecision:
    failure_class: FailureClass
    action: FailureAction
    reason: str
    attempt: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class FailurePolicy:
    """Deterministic fail-closed policy for provider operations."""

    max_read_retries: int = 3

    def __post_init__(self) -> None:
        if self.max_read_retries < 0:
            raise ValueError("max_read_retries must be non-negative")

    def decide(
        self,
        *,
        operation: str,
        failure_class: FailureClass,
        attempt: int,
    ) -> FailureDecision:
        if not operation.strip():
            raise ValueError("operation must not be empty")
        if attempt < 1:
            raise ValueError("attempt must be >= 1")

        operation = operation.strip().lower()

        if operation in {"submit_order", "cancel_order"}:
            return FailureDecision(
                failure_class,
                FailureAction.RECONCILE,
                "order state must be reconciled before another broker action",
                attempt,
                0,
            )

        if failure_class is FailureClass.TRANSIENT and attempt <= self.max_read_retries:
            return FailureDecision(
                failure_class,
                FailureAction.RETRY,
                "bounded retry for explicitly retryable read/observation operation",
                attempt,
                self.max_read_retries,
            )

        if failure_class is FailureClass.UNKNOWN:
            return FailureDecision(
                failure_class,
                FailureAction.RECONCILE,
                "provider state is unknown; obtain authoritative state before proceeding",
                attempt,
                self.max_read_retries,
            )

        return FailureDecision(
            failure_class,
            FailureAction.BLOCK,
            "failure is not safely retryable",
            attempt,
            self.max_read_retries,
        )


__all__ = ["FailureAction", "FailureClass", "FailureDecision", "FailurePolicy"]
