"""Deterministic Upstox timeout/network recovery evidence capture.

The capture boundary consumes an already-observed failure. It never retries,
submits an order, or performs reconciliation itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from execution.provider_evidence import (
    ProviderEvidenceObservation,
    ProviderEvidenceState,
)
from execution.upstox_certification import (
    UpstoxFailureClass,
    classify_upstox_error,
)


@dataclass(frozen=True, slots=True)
class SandboxRecoveryEvidence:
    observation: ProviderEvidenceObservation
    failure_class: UpstoxFailureClass
    requires_reconciliation: bool


def capture_sandbox_timeout_recovery_evidence(
    *,
    failure: Mapping[str, Any],
) -> SandboxRecoveryEvidence:
    """Classify an already-observed timeout/network failure.

    The returned evidence is VERIFIED only for the software observation that
    the ambiguous failure requires reconciliation. It is not real-provider
    evidence and does not authorize a retry.
    """
    message = str(failure.get("message") or failure.get("detail") or "").strip()
    error_type = str(failure.get("error_type") or "").strip()
    if not message and not error_type:
        raise ValueError("observed failure must contain a message or error_type")

    status_raw = failure.get("status_code", failure.get("http_status"))
    if status_raw is None:
        http_status = None
    else:
        try:
            http_status = int(status_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("provider HTTP status must be numeric") from exc

    code = str(failure.get("code") or failure.get("error_code") or "").strip()
    classified = classify_upstox_error(
        http_status=http_status,
        code=code,
        message=f"{error_type} {message}".strip(),
    )

    if classified.failure_class not in {
        UpstoxFailureClass.NETWORK,
        UpstoxFailureClass.PROVIDER_UNAVAILABLE,
        UpstoxFailureClass.UNKNOWN,
    }:
        return SandboxRecoveryEvidence(
            ProviderEvidenceObservation(
                "timeout_recovery",
                "sandbox",
                "ambiguous request recovery",
                ProviderEvidenceState.UNVERIFIED,
                (
                    f"observed failure classified as "
                    f"{classified.failure_class.value}; timeout/network recovery "
                    "was not established"
                ),
            ),
            classified.failure_class,
            classified.requires_reconciliation,
        )

    if not classified.requires_reconciliation:
        raise ValueError(
            "ambiguous timeout/network outcome must require reconciliation"
        )

    return SandboxRecoveryEvidence(
        ProviderEvidenceObservation(
            "timeout_recovery",
            "sandbox",
            "ambiguous request recovery",
            ProviderEvidenceState.VERIFIED,
            (
                f"observed {classified.failure_class.value} outcome requires "
                "broker-state reconciliation before retry"
            ),
        ),
        classified.failure_class,
        True,
    )


__all__ = [
    "SandboxRecoveryEvidence",
    "capture_sandbox_timeout_recovery_evidence",
]
