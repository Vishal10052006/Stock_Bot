"""Tests for complete NSE Security Master evidence file parsing."""

from datetime import date
import gzip

import pytest

from market.data.historical.nse_security_master_evidence_file_parser import (
    NSESecurityMasterEvidenceFileParseError,
    parse_nse_security_master_evidence_csv,
    parse_nse_security_master_evidence_gzip,
)


SNAPSHOT_DATE = date(2026, 9, 4)

HEADER = (
    "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,"
    "ListgDt,RmvlDt,RadmssnDt,SctyStsNrmlMkt,"
    "ElgbltyNrmlMkt,DelFlg\n"
)

ROW = (
    "15342,SHALPAINTS,EQ,SHALIMAR PAINTS LIMITED,"
    "INE849C01026,888969600,0,0,1,0,N\n"
)


def test_parse_csv_builds_complete_evidence_snapshot() -> None:
    snapshot = parse_nse_security_master_evidence_csv(
        (HEADER + ROW).encode(),
        snapshot_date=SNAPSHOT_DATE,
    )

    assert snapshot.snapshot_date == SNAPSHOT_DATE
    assert len(snapshot.evidence) == 1

    evidence = snapshot.evidence[0]

    assert evidence.identity.fin_instrm_id == "15342"
    assert evidence.identity.symbol == "SHALPAINTS"
    assert evidence.identity.series == "EQ"
    assert evidence.identity.isin == "INE849C01026"

    assert evidence.lifecycle.listing_date == date(1998, 3, 4)
    assert evidence.lifecycle.removal_date is None
    assert evidence.lifecycle.readmission_date is None
    assert evidence.lifecycle.normal_market_status == "1"
    assert evidence.lifecycle.normal_market_eligibility == "0"
    assert evidence.lifecycle.deletion_flag == "N"


def test_parse_gzip_builds_complete_evidence_snapshot() -> None:
    payload = gzip.compress((HEADER + ROW).encode())

    snapshot = parse_nse_security_master_evidence_gzip(
        payload,
        snapshot_date=SNAPSHOT_DATE,
    )

    assert len(snapshot.evidence) == 1
    assert snapshot.evidence[0].identity.symbol == "SHALPAINTS"


def test_parser_preserves_duplicate_isin() -> None:
    payload = (
        HEADER
        + "1357,HIMADCHEM,EQ,HIMADRI,INE019C01026,"
        "0,0,0,3,0,Y\n"
        + "14334,HSCL,EQ,HSCL,INE019C01026,"
        "0,0,0,1,1,N\n"
    ).encode()

    snapshot = parse_nse_security_master_evidence_csv(
        payload,
        snapshot_date=SNAPSHOT_DATE,
    )

    assert len(snapshot.evidence) == 2
    assert (
        snapshot.evidence[0].identity.isin
        == snapshot.evidence[1].identity.isin
    )


def test_parser_rejects_missing_lifecycle_column() -> None:
    payload = (
        "FinInstrmId,TckrSymb,SctySrs,ISIN,"
        "ListgDt,RmvlDt,RadmssnDt,SctyStsNrmlMkt,"
        "ElgbltyNrmlMkt\n"
        "15342,SHALPAINTS,EQ,INE849C01026,"
        "888969600,0,0,1,0\n"
    ).encode()

    with pytest.raises(
        NSESecurityMasterEvidenceFileParseError,
        match="missing required columns",
    ):
        parse_nse_security_master_evidence_csv(
            payload,
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_missing_header() -> None:
    with pytest.raises(
        NSESecurityMasterEvidenceFileParseError,
        match="missing its header",
    ):
        parse_nse_security_master_evidence_csv(
            b"",
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_empty_file() -> None:
    with pytest.raises(
        NSESecurityMasterEvidenceFileParseError,
        match="contains no records",
    ):
        parse_nse_security_master_evidence_csv(
            HEADER.encode(),
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_malformed_row() -> None:
    payload = (
        HEADER
        + "15342,SHALPAINTS,EQ,SHALIMAR,"
        "INE849C01026,not-an-epoch,0,0,1,0,N\n"
    ).encode()

    with pytest.raises(
        NSESecurityMasterEvidenceFileParseError,
        match="row 2",
    ):
        parse_nse_security_master_evidence_csv(
            payload,
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_duplicate_fin_instrm_id() -> None:
    payload = (
        HEADER
        + ROW
        + "15342,TCS,EQ,TCS,INE467B01029,"
        "0,0,0,1,1,N\n"
    ).encode()

    with pytest.raises(
        NSESecurityMasterEvidenceFileParseError,
        match="invalid NSE Security Master evidence snapshot",
    ):
        parse_nse_security_master_evidence_csv(
            payload,
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_invalid_gzip() -> None:
    with pytest.raises(
        NSESecurityMasterEvidenceFileParseError,
        match="invalid NSE Security Master evidence gzip",
    ):
        parse_nse_security_master_evidence_gzip(
            b"not-gzip",
            snapshot_date=SNAPSHOT_DATE,
        )
