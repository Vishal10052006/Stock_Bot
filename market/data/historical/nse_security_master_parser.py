"""Parser for NSE dated Security Master records."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)


class NSESecurityMasterParseError(ValueError):
    """Raised when an NSE Security Master record is malformed."""


_REQUIRED_FIELDS = (
    "FinInstrmId",
    "TckrSymb",
    "SctySrs",
    "ISIN",
)


def parse_nse_security_master_record(
    row: Mapping[str, object],
    *,
    snapshot_date: date,
) -> NSESecurityMasterRecord:
    """Parse one NSE Security File row into a typed identity record."""

    if not isinstance(snapshot_date, date):
        raise NSESecurityMasterParseError(
            "snapshot_date must be a date"
        )

    if isinstance(snapshot_date, datetime):
        raise NSESecurityMasterParseError(
            "snapshot_date must be a date"
        )

    if not isinstance(row, Mapping):
        raise NSESecurityMasterParseError(
            "Security Master record must be a mapping"
        )

    missing = [
        field
        for field in _REQUIRED_FIELDS
        if field not in row
        or not isinstance(row[field], str)
        or not row[field].strip()
    ]

    if missing:
        raise NSESecurityMasterParseError(
            "Security Master record missing required fields: "
            + ", ".join(missing)
        )

    try:
        return NSESecurityMasterRecord(
            snapshot_date=snapshot_date,
            fin_instrm_id=row["FinInstrmId"].strip(),
            symbol=row["TckrSymb"].strip(),
            series=row["SctySrs"].strip(),
            isin=row["ISIN"].strip(),
        )
    except (TypeError, ValueError) as exc:
        raise NSESecurityMasterParseError(
            "invalid NSE Security Master identity record"
        ) from exc
