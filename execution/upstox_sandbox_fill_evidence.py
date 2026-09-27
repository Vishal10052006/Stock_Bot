from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.provider_evidence import (
    ProviderEvidenceObservation,
    ProviderEvidenceState,
)


@dataclass(frozen=True, slots=True)
class SandboxFillEvidence:
    observation: ProviderEvidenceObservation
    broker_order_id: str
    filled_quantity: float


def capture_sandbox_fill_evidence(
    *,
    placed_response: dict[str, Any],
    state_response: dict[str, Any] | None,
) -> SandboxFillEvidence:
    """Classify already-observed provider fill state without network I/O."""
    placed_data = placed_response.get("data")
    if not isinstance(placed_data, dict):
        raise ValueError("placed_response data must be an object")

    broker_order_id = str(
        placed_data.get("order_id")
        or (placed_data.get("order_ids") or [None])[0]
        or ""
    ).strip()
    if not broker_order_id:
        raise ValueError("placed response must contain broker order identity")

    if state_response is None:
        return SandboxFillEvidence(
            ProviderEvidenceObservation(
                "partial_fill",
                "sandbox",
                "broker fill-state lookup",
                ProviderEvidenceState.UNVERIFIED,
                "fill-state evidence was not captured",
            ),
            broker_order_id,
            0.0,
        )

    data = state_response.get("data")
    if not isinstance(data, dict):
        raise ValueError("state_response data must be an object")

    state_id = str(data.get("order_id") or "").strip()
    if state_id != broker_order_id:
        return SandboxFillEvidence(
            ProviderEvidenceObservation(
                "partial_fill",
                "sandbox",
                "broker fill-state lookup",
                ProviderEvidenceState.FAILED,
                "fill-state order identity did not match placement identity",
            ),
            broker_order_id,
            0.0,
        )

    try:
        requested = float(data.get("quantity", data.get("requested_quantity", 0)))
        filled = float(data.get("filled_quantity", data.get("filled_qty", 0)))
    except (TypeError, ValueError) as exc:
        raise ValueError("provider fill quantities must be numeric") from exc

    if requested <= 0 or filled < 0 or filled > requested:
        raise ValueError("provider fill quantities are invalid")

    status = str(data.get("status") or "").strip().lower().replace("_", " ")

    if status in {"partially filled", "partial"}:
        if not 0 < filled < requested:
            return SandboxFillEvidence(
                ProviderEvidenceObservation(
                    "partial_fill",
                    "sandbox",
                    "broker partial-fill state",
                    ProviderEvidenceState.FAILED,
                    "provider reported partial fill with invalid quantity",
                ),
                broker_order_id,
                filled,
            )
        state = ProviderEvidenceState.VERIFIED
        detail = "provider reported a valid partial-fill state"
    else:
        state = ProviderEvidenceState.UNVERIFIED
        detail = f"provider state {status!r} was observed; partial-fill behavior not established"

    return SandboxFillEvidence(
        ProviderEvidenceObservation(
            "partial_fill",
            "sandbox",
            "broker partial-fill state",
            state,
            detail,
        ),
        broker_order_id,
        filled,
    )


__all__ = ["SandboxFillEvidence", "capture_sandbox_fill_evidence"]
