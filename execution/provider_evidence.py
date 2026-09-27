from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class ProviderEvidenceState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ProviderEvidenceObservation:
    capability: str
    environment: str
    operation: str
    state: ProviderEvidenceState
    detail: str


@dataclass(frozen=True, slots=True)
class ProviderEvidenceReport:
    provider: str
    observations: tuple[ProviderEvidenceObservation, ...]

    @property
    def blocked(self) -> bool:
        return any(
            item.state in {
                ProviderEvidenceState.UNVERIFIED,
                ProviderEvidenceState.BLOCKED,
                ProviderEvidenceState.FAILED,
            }
            for item in self.observations
        )


def build_provider_evidence_report(
    provider: str,
    observations: Iterable[ProviderEvidenceObservation],
) -> ProviderEvidenceReport:
    normalized_provider = provider.strip()
    if not normalized_provider:
        raise ValueError("provider must not be empty")

    items = tuple(observations)
    if not items:
        raise ValueError("at least one provider evidence observation is required")

    for item in items:
        if not item.capability.strip():
            raise ValueError("capability must not be empty")
        if not item.environment.strip():
            raise ValueError("environment must not be empty")
        if not item.operation.strip():
            raise ValueError("operation must not be empty")
        if not item.detail.strip():
            raise ValueError("detail must not be empty")

    return ProviderEvidenceReport(normalized_provider, items)


def build_upstox_controlled_evidence_plan() -> ProviderEvidenceReport:
    """Describe only evidence still requiring intentional provider observation.

    No network call, order placement, or readiness authorization occurs here.
    """
    pending = (
        ("order_history", "sandbox", "order-state lookup"),
        ("partial_fill", "sandbox", "partial-fill behavior"),
        ("rate_limit", "sandbox", "rate-limit response"),
        ("timeout_recovery", "sandbox", "ambiguous request recovery"),
        ("process_restart", "sandbox", "restart and rehydration"),
        ("position_reconciliation", "production", "read-only positions observation"),
    )
    return build_provider_evidence_report(
        "upstox",
        (
            ProviderEvidenceObservation(
                capability,
                environment,
                operation,
                ProviderEvidenceState.UNVERIFIED,
                "intentional real-provider evidence has not been recorded",
            )
            for capability, environment, operation in pending
        ),
    )


def evidence_payload(observation: Mapping[str, object]) -> ProviderEvidenceObservation:
    """Normalize a captured evidence record without interpreting its outcome."""
    return ProviderEvidenceObservation(
        capability=str(observation.get("capability", "")),
        environment=str(observation.get("environment", "")),
        operation=str(observation.get("operation", "")),
        state=ProviderEvidenceState(str(observation.get("state", ""))),
        detail=str(observation.get("detail", "")),
    )


__all__ = [
    "ProviderEvidenceState",
    "ProviderEvidenceObservation",
    "ProviderEvidenceReport",
    "build_provider_evidence_report",
    "build_upstox_controlled_evidence_plan",
    "evidence_payload",
]
