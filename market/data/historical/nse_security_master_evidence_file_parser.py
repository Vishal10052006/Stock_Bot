"""Parser for complete dated NSE Security Master evidence files."""

from __future__ import annotations

import csv
import gzip
import io
from datetime import date, datetime

from market.data.historical.nse_security_master_evidence_parser import (
    NSESecurityMasterEvidenceParseError,
    parse_nse_security_master_evidence,
)
from market.data.historical.nse_security_master_evidence_snapshot import (
    NSESecurityMasterEvidenceSnapshot,
)


class NSESecurityMasterEvidenceFileParseError(ValueError):
    """Raised when a complete NSE Security Master evidence file is malformed."""


_REQUIRED_FIELDS = {
    "FinInstrmId",
    "TckrSymb",
    "SctySrs",
    "ISIN",
    "ListgDt",
    "RmvlDt",
    "RadmssnDt",
    "SctyStsNrmlMkt",
    "ElgbltyNrmlMkt",
    "DelFlg",
}


def parse_nse_security_master_evidence_csv(
    payload: bytes,
    *,
    snapshot_date: date,
) -> NSESecurityMasterEvidenceSnapshot:
    """Parse an uncompressed NSE Security Master CSV into complete evidence."""

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")

    _validate_snapshot_date(snapshot_date)

    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NSESecurityMasterEvidenceFileParseError(
            "Security Master evidence file must be valid UTF-8 CSV"
        ) from exc

    rows = csv.DictReader(io.StringIO(text))

    if rows.fieldnames is None:
        raise NSESecurityMasterEvidenceFileParseError(
            "Security Master evidence CSV is missing its header"
        )

    missing = sorted(_REQUIRED_FIELDS - set(rows.fieldnames))

    if missing:
        raise NSESecurityMasterEvidenceFileParseError(
            "Security Master evidence CSV missing required columns: "
            + ", ".join(missing)
        )

    evidence = []

    for row_number, row in enumerate(rows, start=2):
        try:
            item = parse_nse_security_master_evidence(
                row,
                snapshot_date=snapshot_date,
            )
        except NSESecurityMasterEvidenceParseError as exc:
            raise NSESecurityMasterEvidenceFileParseError(
                f"invalid Security Master evidence row {row_number}"
            ) from exc

        evidence.append(item)

    if not evidence:
        raise NSESecurityMasterEvidenceFileParseError(
            "Security Master evidence CSV contains no records"
        )

    try:
        return NSESecurityMasterEvidenceSnapshot(
            snapshot_date=snapshot_date,
            evidence=tuple(evidence),
        )
    except (TypeError, ValueError) as exc:
        raise NSESecurityMasterEvidenceFileParseError(
            "invalid NSE Security Master evidence snapshot"
        ) from exc


def parse_nse_security_master_evidence_gzip(
    payload: bytes,
    *,
    snapshot_date: date,
) -> NSESecurityMasterEvidenceSnapshot:
    """Decompress and parse an NSE Security Master evidence CSV.GZ payload."""

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")

    _validate_snapshot_date(snapshot_date)

    try:
        csv_payload = gzip.decompress(payload)
    except (OSError, EOFError) as exc:
        raise NSESecurityMasterEvidenceFileParseError(
            "invalid NSE Security Master evidence gzip payload"
        ) from exc

    return parse_nse_security_master_evidence_csv(
        csv_payload,
        snapshot_date=snapshot_date,
    )


def _validate_snapshot_date(snapshot_date: date) -> None:
    if not isinstance(snapshot_date, date):
        raise TypeError("snapshot_date must be a date")

    if isinstance(snapshot_date, datetime):
        raise TypeError("snapshot_date must be a date")
