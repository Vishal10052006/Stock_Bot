"""Combined dated NSE Security Master identity and lifecycle evidence."""

from __future__ import annotations

from dataclasses import dataclass

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)
from market.data.historical.nse_security_master_lifecycle import (
    NSESecurityMasterLifecycle,
)


@dataclass(frozen=True, slots=True)
class NSESecurityMasterEvidence:
    """Identity and lifecycle evidence for one NSE instrument record."""

    identity: NSESecurityMasterRecord
    lifecycle: NSESecurityMasterLifecycle

    def __post_init__(self) -> None:
        if not isinstance(
            self.identity,
            NSESecurityMasterRecord,
        ):
            raise TypeError(
                "identity must be an NSESecurityMasterRecord"
            )

        if not isinstance(
            self.lifecycle,
            NSESecurityMasterLifecycle,
        ):
            raise TypeError(
                "lifecycle must be an NSESecurityMasterLifecycle"
            )
