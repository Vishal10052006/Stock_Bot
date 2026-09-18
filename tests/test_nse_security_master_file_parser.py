"""Tests for the NSE Security Master CSV/GZIP parser."""

from datetime import date
import gzip

import pytest

from market.data.historical.nse_security_master_file_parser import (
    NSESecurityMasterFileParseError,
    parse_nse_security_master_csv,
    parse_nse_security_master_gzip,
)


SNAPSHOT_DATE = date(2026, 9, 4)

HEADER = (
    "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN\n"
)

ROW_RELIANCE = (
    "2885,RELIANCE,EQ,RELIANCE INDUSTRIES LIMITED,"
    "INE002A01018\n"
)

ROW_TCS = (
    "11536,TCS,EQ,TATA CONSULTANCY SERVICES LIMITED,"
    "INE467B01029\n"
)


def test_parse_csv_builds_snapshot() -> None:
    payload = (
        HEADER
        + ROW_TCS
        + ROW_RELIANCE
    ).encode()

    snapshot = parse_nse_security_master_csv(
        payload,
        snapshot_date=SNAPSHOT_DATE,
    )

    assert snapshot.snapshot_date == SNAPSHOT_DATE
    assert len(snapshot.records) == 2

    assert snapshot.record_for("RELIANCE") is not None
    assert snapshot.record_for("TCS") is not None


def test_parse_csv_preserves_duplicate_isin() -> None:
    payload = (
        HEADER
        + "1357,HIMADCHEM,EQ,HIMADRI,"
        + "INE019C01026\n"
        + "14334,HSCL,EQ,HSCL,"
        + "INE019C01026\n"
    ).encode()

    snapshot = parse_nse_security_master_csv(
        payload,
        snapshot_date=SNAPSHOT_DATE,
    )

    assert len(snapshot.records) == 2
    assert snapshot.records[0].isin == snapshot.records[1].isin


def test_parse_gzip_builds_snapshot() -> None:
    csv_payload = (
        HEADER
        + ROW_RELIANCE
    ).encode()

    gzip_payload = gzip.compress(csv_payload)

    snapshot = parse_nse_security_master_gzip(
        gzip_payload,
        snapshot_date=SNAPSHOT_DATE,
    )

    assert len(snapshot.records) == 1
    assert snapshot.records[0].symbol == "RELIANCE"


def test_parser_rejects_missing_header() -> None:
    with pytest.raises(
        NSESecurityMasterFileParseError,
        match="missing its header",
    ):
        parse_nse_security_master_csv(
            b"",
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_missing_required_column() -> None:
    payload = (
        "FinInstrmId,TckrSymb,SctySrs\n"
        "2885,RELIANCE,EQ\n"
    ).encode()

    with pytest.raises(
        NSESecurityMasterFileParseError,
        match="missing required columns",
    ):
        parse_nse_security_master_csv(
            payload,
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_empty_file() -> None:
    payload = HEADER.encode()

    with pytest.raises(
        NSESecurityMasterFileParseError,
        match="contains no records",
    ):
        parse_nse_security_master_csv(
            payload,
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_malformed_row() -> None:
    payload = (
        HEADER
        + "2885,RELIANCE,EQ,,\n"
    ).encode()

    with pytest.raises(
        NSESecurityMasterFileParseError,
        match="row 2",
    ):
        parse_nse_security_master_csv(
            payload,
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_duplicate_fin_instrm_id() -> None:
    payload = (
        HEADER
        + "2885,RELIANCE,EQ,RELIANCE,INE002A01018\n"
        + "2885,TCS,EQ,TCS,INE467B01029\n"
    ).encode()

    with pytest.raises(
        NSESecurityMasterFileParseError,
        match="invalid NSE Security Master snapshot",
    ):
        parse_nse_security_master_csv(
            payload,
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_invalid_gzip() -> None:
    with pytest.raises(
        NSESecurityMasterFileParseError,
        match="invalid NSE Security Master gzip",
    ):
        parse_nse_security_master_gzip(
            b"not-gzip",
            snapshot_date=SNAPSHOT_DATE,
        )
