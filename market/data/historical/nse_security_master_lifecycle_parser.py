"""Parser for raw NSE Security Master lifecycle fields."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime

from market.data.historical.nse_security_master_lifecycle import (
    NSESecurityMasterLifecycle,
)


class NSESecurityMasterLifecycleParseError(ValueError):
    """Raised when NSE lifecycle fields are malformed."""


_REQUIRED_FIELDS = (
    "ListgDt",
    "RmvlDt",
    "RadmssnDt",
    "SctyStsNrmlMkt",
    "ElgbltyNrmlMkt",
    "DelFlg",
)


def parse_nse_security_master_lifecycle(
    row: Mapping[str, object],
) -> NSESecurityMasterLifecycle:
    """Parse raw NSE lifecycle fields into a typed lifecycle contract."""

    if not isinstance(row, Mapping):
        raise NSESecurityMasterLifecycleParseError(
            "Security Master lifecycle row must be a mapping"
        )

    missing = [
        field
        for field in _REQUIRED_FIELDS
        if field not in row
    ]

    if missing:
        raise NSESecurityMasterLifecycleParseError(
            "Security Master lifecycle row missing required fields: "
            + ", ".join(missing)
        )

    try:
        listing_date = _parse_nse_epoch_date(
            row["ListgDt"],
            field="ListgDt",
        )
        removal_date = _parse_nse_epoch_date(
            row["RmvlDt"],
            field="RmvlDt",
        )
        readmission_date = _parse_nse_epoch_date(
            row["RadmssnDt"],
            field="RadmssnDt",
        )

        normal_market_status = _parse_required_string(
            row["SctyStsNrmlMkt"],
            field="SctyStsNrmlMkt",
        )
        normal_market_eligibility = _parse_required_string(
            row["ElgbltyNrmlMkt"],
            field="ElgbltyNrmlMkt",
        )
        deletion_flag = _parse_required_string(
            row["DelFlg"],
            field="DelFlg",
        )

        return NSESecurityMasterLifecycle(
            listing_date=listing_date,
            removal_date=removal_date,
            readmission_date=readmission_date,
            normal_market_status=normal_market_status,
            normal_market_eligibility=normal_market_eligibility,
            deletion_flag=deletion_flag,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(
            exc,
            NSESecurityMasterLifecycleParseError,
        ):
            raise

        raise NSESecurityMasterLifecycleParseError(
            "invalid NSE Security Master lifecycle fields"
        ) from exc


def _parse_nse_epoch_date(
    value: object,
    *,
    field: str,
) -> date | None:
    if not isinstance(value, str):
        raise NSESecurityMasterLifecycleParseError(
            f"{field} must be a string"
        )

    value = value.strip()

    if not value:
        raise NSESecurityMasterLifecycleParseError(
            f"{field} must not be empty"
        )

    try:
        epoch_seconds = int(value)
    except ValueError as exc:
        raise NSESecurityMasterLifecycleParseError(
            f"{field} must contain Unix epoch seconds"
        ) from exc

    if epoch_seconds == 0:
        return None

    if epoch_seconds < 0:
        raise NSESecurityMasterLifecycleParseError(
            f"{field} must not be negative"
        )

    try:
        return datetime.fromtimestamp(
            epoch_seconds,
            tz=UTC,
        ).date()
    except (OverflowError, OSError, ValueError) as exc:
        raise NSESecurityMasterLifecycleParseError(
            f"{field} contains an invalid Unix timestamp"
        ) from exc


def _parse_required_string(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NSESecurityMasterLifecycleParseError(
            f"{field} must be a non-empty string"
        )

    return value.strip()
