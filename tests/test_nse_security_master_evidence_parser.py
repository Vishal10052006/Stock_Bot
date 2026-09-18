"""Tests for combined NSE Security Master evidence parsing."""

from datetime import date

import pytest

from market.data.historical.nse_security_master_evidence_parser import (
    NSESecurityMasterEvidenceParseError,
    parse_nse_security_master_evidence,
)


SNAPSHOT_DATE = date(2026, 9, 4)


def make_row() -> dict[str, str]:
    return {
        "FinInstrmId": "15342",
        "TckrSymb": "SHALPAINTS",
        "SctySrs": "EQ",
        "ISIN": "INE849C01026",
        "ListgDt": "888969600",
        "RmvlDt": "0",
        "RadmssnDt": "0",
        "SctyStsNrmlMkt": "1",
        "ElgbltyNrmlMkt": "0",
        "DelFlg": "N",
    }


def test_parser_builds_complete_evidence() -> None:
    evidence = parse_nse_security_master_evidence(
        make_row(),
        snapshot_date=SNAPSHOT_DATE,
    )

    assert evidence.identity.snapshot_date == SNAPSHOT_DATE
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


def test_parser_preserves_lifecycle_codes() -> None:
    row = make_row()
    row["SctyStsNrmlMkt"] = "3"
    row["ElgbltyNrmlMkt"] = "1"
    row["DelFlg"] = "Y"

    evidence = parse_nse_security_master_evidence(
        row,
        snapshot_date=SNAPSHOT_DATE,
    )

    assert evidence.lifecycle.normal_market_status == "3"
    assert evidence.lifecycle.normal_market_eligibility == "1"
    assert evidence.lifecycle.deletion_flag == "Y"


def test_parser_rejects_missing_identity_fields() -> None:
    row = make_row()
    del row["FinInstrmId"]

    with pytest.raises(
        NSESecurityMasterEvidenceParseError,
        match="invalid",
    ):
        parse_nse_security_master_evidence(
            row,
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_missing_lifecycle_fields() -> None:
    row = make_row()
    del row["DelFlg"]

    with pytest.raises(
        NSESecurityMasterEvidenceParseError,
        match="invalid",
    ):
        parse_nse_security_master_evidence(
            row,
            snapshot_date=SNAPSHOT_DATE,
        )


def test_parser_rejects_non_mapping() -> None:
    with pytest.raises(
        NSESecurityMasterEvidenceParseError,
        match="mapping",
    ):
        parse_nse_security_master_evidence(
            [],
            snapshot_date=SNAPSHOT_DATE,
        )  # type: ignore[arg-type]


def test_parser_rejects_invalid_snapshot_date() -> None:
    with pytest.raises(
        NSESecurityMasterEvidenceParseError,
        match="snapshot_date",
    ):
        parse_nse_security_master_evidence(
            make_row(),
            snapshot_date="2026-09-04",  # type: ignore[arg-type]
        )
