"""Contracts for corroborated security-lineage transitions."""

from __future__ import annotations

from dataclasses import dataclass

from market.data.historical.nse_security_master_observation import (
    NSESecurityMasterObservation,
)
from market.data.historical.security_lineage_transition import (
    SecurityLineageTransition,
)


@dataclass(frozen=True, slots=True)
class SecurityLineageResolution:
    """Corroborated identity transition without inventing lineage dates.

    ``before`` is the dated Security Master observation representing the old
    symbol before the transition.

    ``after`` is the dated Security Master observation representing the new
    symbol on or after the transition.

    This result does not itself construct SecurityLineage intervals because
    the available evidence may not establish when either instrument first
    became effective.
    """

    transition: SecurityLineageTransition
    before: NSESecurityMasterObservation
    after: NSESecurityMasterObservation

    def __post_init__(self) -> None:
        if not isinstance(
            self.transition,
            SecurityLineageTransition,
        ):
            raise TypeError(
                "transition must be a SecurityLineageTransition"
            )

        if not isinstance(
            self.before,
            NSESecurityMasterObservation,
        ):
            raise TypeError(
                "before must be an NSESecurityMasterObservation"
            )

        if not isinstance(
            self.after,
            NSESecurityMasterObservation,
        ):
            raise TypeError(
                "after must be an NSESecurityMasterObservation"
            )

        if self.before.observed_on >= self.transition.effective_date:
            raise ValueError(
                "before observation must be before transition effective date"
            )

        if self.after.observed_on < self.transition.effective_date:
            raise ValueError(
                "after observation must be on or after transition effective date"
            )

        if self.before.symbol != self.transition.old_symbol:
            raise ValueError(
                "before observation symbol does not match old_symbol"
            )

        if self.after.symbol != self.transition.new_symbol:
            raise ValueError(
                "after observation symbol does not match new_symbol"
            )
