from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from execution.engine import PositionSnapshot
from execution.certification import PositionEvidenceReport, build_position_evidence
from execution.provider_evidence import ProviderEvidenceReport


class UpstoxEvidenceState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class UpstoxCapabilityEvidence:
    capability: str
    state: UpstoxEvidenceState
    environment: str
    detail: str


@dataclass(frozen=True, slots=True)
class UpstoxReadinessAttestation:
    capabilities: tuple[UpstoxCapabilityEvidence, ...]
    evidence_fingerprint: str

    @property
    def blocked(self) -> bool:
        return any(
            evidence.state in {
                UpstoxEvidenceState.UNVERIFIED,
                UpstoxEvidenceState.BLOCKED,
                UpstoxEvidenceState.FAILED,
            }
            for evidence in self.capabilities
        )

    @property
    def verified(self) -> bool:
        return bool(self.capabilities) and not self.blocked


def build_upstox_readiness_attestation(
    capabilities: Iterable[UpstoxCapabilityEvidence],
) -> UpstoxReadinessAttestation:
    items = tuple(capabilities)
    if not items:
        raise ValueError("at least one provider capability is required")
    import hashlib
    import json

    payload = [
        {
            "capability": item.capability,
            "state": item.state.value,
            "environment": item.environment,
            "detail": item.detail,
        }
        for item in items
    ]
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return UpstoxReadinessAttestation(items, fingerprint)


def build_upstox_readiness_from_provider_report(
    report: ProviderEvidenceReport,
) -> UpstoxReadinessAttestation:
    if report.provider.strip().lower() != "upstox":
        raise ValueError("provider report must be for upstox")

    return build_upstox_readiness_attestation(
        UpstoxCapabilityEvidence(
            capability=observation.capability,
            state=UpstoxEvidenceState(observation.state.value),
            environment=observation.environment,
            detail=observation.detail,
        )
        for observation in report.observations
    )


def build_position_reconciliation_evidence(
    local: Iterable[PositionSnapshot] | None,
    broker: Iterable[PositionSnapshot] | None,
) -> PositionEvidenceReport:
    return build_position_evidence("upstox-production", local, broker)


__all__ = [
    "UpstoxEvidenceState",
    "UpstoxCapabilityEvidence",
    "UpstoxReadinessAttestation",
    "build_upstox_readiness_attestation",
    "build_upstox_readiness_from_provider_report",
    "build_position_reconciliation_evidence",
]
