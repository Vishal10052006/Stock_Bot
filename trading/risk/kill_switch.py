"""Independent hard kill-switch state for the Risk Engine.

The switch is intentionally separate from model output. Execution should
also re-check the independent safety state before any future live order.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    """Immutable snapshot of hard safety triggers."""

    manual: bool = False
    data_failure: bool = False
    broker_failure: bool = False
    abnormal_latency: bool = False
    position_mismatch: bool = False
    invalid_price: bool = False
    duplicate_order: bool = False
    connectivity_failure: bool = False
    model_degradation: bool = False

    @property
    def active(self) -> bool:
        """Return whether any hard safety trigger is active."""
        return any(
            (
                self.manual,
                self.data_failure,
                self.broker_failure,
                self.abnormal_latency,
                self.position_mismatch,
                self.invalid_price,
                self.duplicate_order,
                self.connectivity_failure,
                self.model_degradation,
            )
        )
