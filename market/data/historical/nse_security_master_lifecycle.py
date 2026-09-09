"""Raw NSE Security Master lifecycle evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class NSESecurityMasterLifecycle:
    """Raw lifecycle fields published by NSE for one instrument record.

    NSE-native status and eligibility codes are deliberately preserved as
    strings. Their exchange semantics must not be silently converted into
    application-level lifecycle states at this boundary.
    """

    listing_date: date | None
    removal_date: date | None
    readmission_date: date | None
    normal_market_status: str
    normal_market_eligibility: str
    deletion_flag: str

    def __post_init__(self) -> None:
        for name in (
            "listing_date",
            "removal_date",
            "readmission_date",
        ):
            value = getattr(self, name)

            if value is not None:
                if not isinstance(value, date):
                    raise TypeError(f"{name} must be a date or None")

                if isinstance(value, datetime):
                    raise TypeError(f"{name} must be a date or None")

        for name in (
            "normal_market_status",
            "normal_market_eligibility",
            "deletion_flag",
        ):
            value = getattr(self, name)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{name} must be a non-empty string"
                )

        object.__setattr__(
            self,
            "normal_market_status",
            self.normal_market_status.strip(),
        )
        object.__setattr__(
            self,
            "normal_market_eligibility",
            self.normal_market_eligibility.strip(),
        )
        object.__setattr__(
            self,
            "deletion_flag",
            self.deletion_flag.strip().upper(),
        )
