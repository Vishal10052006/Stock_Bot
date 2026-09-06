"""Parser for combined dated NSE Security Master evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

from market.data.historical.nse_security_master_evidence import (
    NSESecurityMasterEvidence,
)
from market.data.historical.nse_security_master_lifecycle_parser import (
    NSESecurityMasterLifecycleParseError,
    parse_nse_security_master_lifecycle,
)
from market.data.historical.nse_security_master_parser import (
    NSESecurityMasterParseError,
    parse_nse_security_master_record,
)


class NSESecurityMasterEvidenceParseError(ValueError):
    """Raised when combined NSE Security Master evidence is malformed."""


def parse_nse_security_master_evidence(
    row: Mapping[str, object],
    *,
    snapshot_date: date,
) -> NSESecurityMasterEvidence:
    """Parse one NSE Security Master row into complete dated evidence."""

    if not isinstance(snapshot_date, date):
        raise NSESecurityMasterEvidenceParseError(
            "snapshot_date must be a date"
        )

    if isinstance(snapshot_date, datetime):
        raise NSESecurityMasterEvidenceParseError(
            "snapshot_date must be a date"
        )

    if not isinstance(row, Mapping):
        raise NSESecurityMasterEvidenceParseError(
            "Security Master evidence row must be a mapping"
        )

    try:
        identity = parse_nse_security_master_record(
            row,
            snapshot_date=snapshot_date,
        )

        lifecycle = parse_nse_security_master_lifecycle(row)

        return NSESecurityMasterEvidence(
            identity=identity,
            lifecycle=lifecycle,
        )

    except (
        NSESecurityMasterParseError,
        NSESecurityMasterLifecycleParseError,
        TypeError,
        ValueError,
    ) as exc:
        raise NSESecurityMasterEvidenceParseError(
            "invalid NSE Security Master evidence"
        ) from exc
