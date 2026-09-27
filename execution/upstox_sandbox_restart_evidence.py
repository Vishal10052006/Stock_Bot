"""Deterministic Upstox process-restart evidence capture."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from execution.provider_evidence import ProviderEvidenceObservation, ProviderEvidenceState
from execution.engine import OrderStatus


@dataclass(frozen=True, slots=True)
class SandboxRestartEvidence:
    observation: ProviderEvidenceObservation
    broker_order_id: str
    recovered_status: str


def capture_sandbox_restart_evidence(
    *,
    client_order_id: str,
    pre_restart: Mapping[str, Any],
    post_restart: Mapping[str, Any] | None,
    broker_order_id: str,
    submission_count_before: int,
    submission_count_after: int,
) -> SandboxRestartEvidence:
    """Classify an already-observed restart rehydration result."""
    if not client_order_id.strip():
        raise ValueError("client_order_id must not be empty")
    if not broker_order_id.strip():
        raise ValueError("broker_order_id must not be empty")
    if submission_count_before < 0 or submission_count_after < 0:
        raise ValueError("submission counts must be non-negative")

    pre_id = str(pre_restart.get("client_order_id") or "").strip()
    if pre_id != client_order_id:
        raise ValueError("pre-restart client order identity mismatch")

    if post_restart is None:
        return SandboxRestartEvidence(
            ProviderEvidenceObservation(
                "process_restart", "sandbox", "restart and rehydration",
                ProviderEvidenceState.UNVERIFIED,
                "post-restart broker state was not captured",
            ),
            broker_order_id,
            OrderStatus.UNKNOWN.value,
        )

    post_id = str(post_restart.get("client_order_id") or "").strip()
    if post_id != client_order_id:
        return SandboxRestartEvidence(
            ProviderEvidenceObservation(
                "process_restart", "sandbox", "restart and rehydration",
                ProviderEvidenceState.FAILED,
                "post-restart client order identity did not match",
            ),
            broker_order_id,
            OrderStatus.UNKNOWN.value,
        )

    status = str(post_restart.get("status") or "").strip().upper()
    if status not in {item.value for item in OrderStatus}:
        raise ValueError("post-restart status is not a valid OrderStatus")

    if submission_count_after != submission_count_before:
        return SandboxRestartEvidence(
            ProviderEvidenceObservation(
                "process_restart", "sandbox", "restart and rehydration",
                ProviderEvidenceState.FAILED,
                "restart recovery caused an additional submission",
            ),
            broker_order_id,
            status,
        )

    if status == OrderStatus.UNKNOWN.value:
        state = ProviderEvidenceState.UNVERIFIED
        detail = "restart state remains UNKNOWN; broker truth was not resolved"
    else:
        state = ProviderEvidenceState.VERIFIED
        detail = "post-restart state was rehydrated without duplicate submission"

    return SandboxRestartEvidence(
        ProviderEvidenceObservation(
            "process_restart", "sandbox", "restart and rehydration",
            state, detail,
        ),
        broker_order_id,
        status,
    )


__all__ = ["SandboxRestartEvidence", "capture_sandbox_restart_evidence"]
