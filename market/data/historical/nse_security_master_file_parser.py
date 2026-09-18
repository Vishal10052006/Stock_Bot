"""Parser for dated NSE Security Master CSV files."""

from __future__ import annotations

import csv
import gzip
import io
from collections.abc import Iterable, Iterator, Mapping
from datetime import date, datetime

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)
from market.data.historical.nse_security_master_parser import (
    NSESecurityMasterParseError,
    parse_nse_security_master_record,
)
from market.data.historical.nse_security_master_snapshot import (
    NSESecurityMasterSnapshot,
)


class NSESecurityMasterFileParseError(ValueError):
    """Raised when an NSE Security Master file is malformed."""


def parse_nse_security_master_csv(
    payload: bytes,
    *,
    snapshot_date: date,
) -> NSESecurityMasterSnapshot:
    """Parse an uncompressed NSE Security Master CSV payload."""

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")

    _validate_snapshot_date(snapshot_date)

    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NSESecurityMasterFileParseError(
            "Security Master file must be valid UTF-8 CSV"
        ) from exc

    rows = csv.DictReader(io.StringIO(text))

    if rows.fieldnames is None:
        raise NSESecurityMasterFileParseError(
            "Security Master CSV is missing its header"
        )

    required = {
        "FinInstrmId",
        "TckrSymb",
        "SctySrs",
        "ISIN",
    }

    missing = sorted(required - set(rows.fieldnames))

    if missing:
        raise NSESecurityMasterFileParseError(
            "Security Master CSV missing required columns: "
            + ", ".join(missing)
        )

    records: list[NSESecurityMasterRecord] = []

    for row_number, row in enumerate(rows, start=2):
        try:
            record = parse_nse_security_master_record(
                row,
                snapshot_date=snapshot_date,
            )
        except NSESecurityMasterParseError as exc:
            raise NSESecurityMasterFileParseError(
                f"invalid Security Master row {row_number}"
            ) from exc

        records.append(record)

    if not records:
        raise NSESecurityMasterFileParseError(
            "Security Master CSV contains no records"
        )

    try:
        return NSESecurityMasterSnapshot(
            snapshot_date=snapshot_date,
            records=tuple(records),
        )
    except (TypeError, ValueError) as exc:
        raise NSESecurityMasterFileParseError(
            "invalid NSE Security Master snapshot"
        ) from exc


def parse_nse_security_master_gzip(
    payload: bytes,
    *,
    snapshot_date: date,
) -> NSESecurityMasterSnapshot:
    """Decompress and parse an NSE Security Master CSV.GZ payload."""

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")

    _validate_snapshot_date(snapshot_date)

    try:
        csv_payload = gzip.decompress(payload)
    except (OSError, EOFError) as exc:
        raise NSESecurityMasterFileParseError(
            "invalid NSE Security Master gzip payload"
        ) from exc

    return parse_nse_security_master_csv(
        csv_payload,
        snapshot_date=snapshot_date,
    )


def _validate_snapshot_date(snapshot_date: date) -> None:
    if not isinstance(snapshot_date, date):
        raise TypeError("snapshot_date must be a date")

    if isinstance(snapshot_date, datetime):
        raise TypeError("snapshot_date must be a date")
