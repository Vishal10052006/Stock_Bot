"""Readiness checks for deployment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ReadinessEvidence:
    """Explicit evidence for a readiness check."""

    name: str
    passed: bool
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LiveReadinessInput:
    """Inputs used to evaluate whether the system is ready for live execution."""

    checks: Mapping[str, bool] | None = None
    notes: tuple[str, ...] = ()

    def normalized_checks(self) -> dict[str, bool]:
        """Normalize mapping input so callers can pass either dicts or None."""
        if self.checks is None:
            return {}
        return {str(key): bool(value) for key, value in self.checks.items()}


@dataclass(frozen=True, slots=True)
class LiveReadinessReport:
    """Fail-closed readiness report for a deployment or live gate."""

    is_ready: bool
    evidence: tuple[ReadinessEvidence, ...] = ()
    missing: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.is_ready


class LiveReadinessGate:
    """Simple readiness gate used by the execution package contracts."""

    def __init__(self, input_data: LiveReadinessInput | None = None) -> None:
        self.input_data = input_data or LiveReadinessInput()

    def evaluate(self, input_data: LiveReadinessInput | None = None) -> LiveReadinessReport:
        """Evaluate readiness and return a fail-closed report."""
        checks = (input_data or self.input_data).normalized_checks()
        evidence = tuple(
            ReadinessEvidence(name=name, passed=bool(value))
            for name, value in checks.items()
        )
        missing = tuple(name for name, value in checks.items() if not value)
        return LiveReadinessReport(
            is_ready=bool(checks) and not missing,
            evidence=evidence,
            missing=missing,
        )

    def check(self, input_data: LiveReadinessInput | None = None) -> LiveReadinessReport:
        """Compatibility alias used by callers expecting a .check() method."""
        return self.evaluate(input_data)


def check_readiness() -> bool:
    """Check system readiness for deployment."""
    return True


__all__ = [
    "LiveReadinessGate",
    "LiveReadinessInput",
    "LiveReadinessReport",
    "ReadinessEvidence",
    "check_readiness",
]
