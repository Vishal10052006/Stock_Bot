"""Final Upstox operational certification gate.

This gate certifies software controls only. It never enables live execution.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UpstoxOperationalCertification:
    adapter_contract: bool
    sandbox_authentication: bool
    sandbox_order_lifecycle: bool
    provider_error_handling: bool
    reconciliation_boundary: bool
    ci_validated: bool
    live_execution_locked: bool = True

    @property
    def software_complete(self) -> bool:
        return all(
            (
                self.adapter_contract,
                self.sandbox_authentication,
                self.sandbox_order_lifecycle,
                self.provider_error_handling,
                self.reconciliation_boundary,
                self.ci_validated,
                self.live_execution_locked,
            )
        )

    def assert_safe(self) -> None:
        if not self.software_complete:
            raise ValueError("Upstox operational certification is incomplete")
        if not self.live_execution_locked:
            raise ValueError("Upstox certification cannot unlock live execution")


__all__ = ["UpstoxOperationalCertification"]
