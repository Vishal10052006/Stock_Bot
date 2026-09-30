"""Fail-closed guards for the automation control plane."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from execution.safety import IndependentSafetyGate, SafetyState


class AutomationGateError(RuntimeError):
    """Raised when an automation invariant is violated."""


def require_causal_timestamp(
    decision_timestamp: datetime,
    observed_timestamp: datetime,
) -> None:
    """Reject information observed after the decision timestamp."""
    if decision_timestamp.tzinfo is None or observed_timestamp.tzinfo is None:
        raise AutomationGateError("timestamps must be timezone-aware")
    if observed_timestamp > decision_timestamp:
        raise AutomationGateError("future observation rejected")


def require_fresh_context(
    context: Any,
    decision_timestamp: datetime,
    *,
    max_age_seconds: int | None = None,
) -> None:
    """Validate optional context timestamp and freshness."""
    timestamp = getattr(context, "timestamp", None)
    if timestamp is None:
        return
    if hasattr(timestamp, "to_pydatetime"):
        timestamp = timestamp.to_pydatetime()
    require_causal_timestamp(decision_timestamp, timestamp)
    if max_age_seconds is not None:
        age = (decision_timestamp - timestamp).total_seconds()
        if age > max_age_seconds:
            raise AutomationGateError("stale context rejected")


def live_safety_blocked() -> bool:
    """Return whether the independent live lock remains active."""
    result = IndependentSafetyGate().evaluate(
        SafetyState(live_execution_enabled=False)
    )
    return not result.allowed
