from __future__ import annotations

from typing import Iterable

from execution.provider_evidence import (
    ProviderEvidenceObservation,
    ProviderEvidenceReport,
    build_provider_evidence_report,
)
from execution.upstox_readiness import (
    UpstoxReadinessAttestation,
    build_upstox_readiness_from_provider_report,
)


def build_upstox_provider_evidence_bundle(
    observations: Iterable[ProviderEvidenceObservation],
) -> tuple[ProviderEvidenceReport, UpstoxReadinessAttestation]:
    """Build the canonical provider report and its readiness projection.

    This is an observational composition boundary only. It performs no network
    I/O, order submission, retry, reconciliation, or execution authorization.
    Provider observations are preserved exactly and remain fail-closed when
    any required capability is not verified.
    """
    report = build_provider_evidence_report("upstox", observations)
    readiness = build_upstox_readiness_from_provider_report(report)
    return report, readiness


__all__ = ["build_upstox_provider_evidence_bundle"]
