from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.provider_evidence import (
    ProviderEvidenceObservation,
    ProviderEvidenceState,
)


@dataclass(frozen=True, slots=True)
class SandboxOrderStateEvidence:
    observation: ProviderEvidenceObservation
    broker_order_id: str


def _status_text(value: Any) -> str:
    return str(value).strip().lower()


def capture_sandbox_order_state_evidence(
    *,
    request: dict[str, Any],
    placed_response: dict[str, Any],
    lookup_response: dict[str, Any] | None,
    cancelled_response: dict[str, Any] | None,
) -> SandboxOrderStateEvidence:
    """Convert already-observed sandbox responses into non-authorizing evidence.

    This function performs no network I/O. Callers must supply the actual
    provider responses captured by a separately controlled integration run.
    """
    placed_data = placed_response.get("data")
    if not isinstance(placed_data, dict):
        raise ValueError("placed_response data must be an object")

    broker_order_id = str(
        placed_data.get("order_id")
        or placed_data.get("order_ids", [None])[0]
        or ""
    ).strip()
    if not broker_order_id:
        raise ValueError("placed response must contain broker order identity")

    if lookup_response is None:
        observation = ProviderEvidenceObservation(
            "order_history",
            "sandbox",
            "broker order-state lookup",
            ProviderEvidenceState.UNVERIFIED,
            "sandbox lookup evidence was not captured",
        )
        return SandboxOrderStateEvidence(observation, broker_order_id)

    lookup_data = lookup_response.get("data")
    if not isinstance(lookup_data, dict):
        raise ValueError("lookup_response data must be an object")

    lookup_id = str(lookup_data.get("order_id") or "").strip()
    lookup_tag = str(lookup_data.get("tag") or "").strip()
    requested_tag = str(request.get("tag") or "").strip()

    if lookup_id != broker_order_id:
        state = ProviderEvidenceState.FAILED
        detail = "broker lookup order identity did not match placement identity"
    elif requested_tag and lookup_tag and lookup_tag != requested_tag:
        state = ProviderEvidenceState.FAILED
        detail = "broker lookup tag did not match submitted deterministic tag"
    elif cancelled_response is not None and _status_text(cancelled_response.get("status")) not in {
        "success",
        "ok",
    }:
        state = ProviderEvidenceState.FAILED
        detail = "sandbox cancel response did not acknowledge success"
    else:
        state = ProviderEvidenceState.VERIFIED
        detail = "sandbox broker order identity and lookup evidence matched"

    operation = "place → lookup"
    if cancelled_response is not None:
        operation = "place → lookup → cancel"

    observation = ProviderEvidenceObservation(
        "order_history",
        "sandbox",
        operation,
        state,
        detail,
    )
    return SandboxOrderStateEvidence(observation, broker_order_id)


__all__ = [
    "SandboxOrderStateEvidence",
    "capture_sandbox_order_state_evidence",
]
