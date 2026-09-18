"""Tests for raw NSE Security Master lifecycle parsing."""

from datetime import date

import pytest

from market.data.historical.nse_security_master_lifecycle_parser import (
    NSESecurityMasterLifecycleParseError,
    parse_nse_security_master_lifecycle,
)


def make_row() -> dict[str, str]:
    return {
        "ListgDt": "888969600",
        "RmvlDt": "0",
        "RadmssnDt": "0",
        "SctyStsNrmlMkt": "6",
        "ElgbltyNrmlMkt": "1",
        "DelFlg": "N",
    }


def test_parser_converts_nse_epoch_dates() -> None:
    lifecycle = parse_nse_security_master_lifecycle(make_row())

    assert lifecycle.listing_date == date(1998, 3, 4)
    assert lifecycle.removal_date is None
    assert lifecycle.readmission_date is None


def test_parser_preserves_nse_status_fields() -> None:
    row = make_row()
    row["SctyStsNrmlMkt"] = "3"
    row["ElgbltyNrmlMkt"] = "0"
    row["DelFlg"] = "Y"

    lifecycle = parse_nse_security_master_lifecycle(row)

    assert lifecycle.normal_market_status == "3"
    assert lifecycle.normal_market_eligibility == "0"
    assert lifecycle.deletion_flag == "Y"


def test_parser_converts_nonzero_removal_and_readmission_dates() -> None:
    row = make_row()
    row["RmvlDt"] = "607910400"
    row["RadmssnDt"] = "822787200"

    lifecycle = parse_nse_security_master_lifecycle(row)

    assert lifecycle.removal_date == date(1989, 4, 7)
    assert lifecycle.readmission_date == date(1996, 1, 28)


@pytest.mark.parametrize(
    "field",
    [
        "ListgDt",
        "RmvlDt",
        "RadmssnDt",
        "SctyStsNrmlMkt",
        "ElgbltyNrmlMkt",
        "DelFlg",
    ],
)
def test_parser_rejects_missing_field(field: str) -> None:
    row = make_row()
    del row[field]

    with pytest.raises(
        NSESecurityMasterLifecycleParseError,
        match=field,
    ):
        parse_nse_security_master_lifecycle(row)


@pytest.mark.parametrize(
    "field",
    [
        "ListgDt",
        "RmvlDt",
        "RadmssnDt",
    ],
)
def test_parser_rejects_invalid_epoch(field: str) -> None:
    row = make_row()
    row[field] = "not-a-timestamp"

    with pytest.raises(
        NSESecurityMasterLifecycleParseError,
        match=field,
    ):
        parse_nse_security_master_lifecycle(row)


def test_parser_rejects_negative_epoch() -> None:
    row = make_row()
    row["ListgDt"] = "-1"

    with pytest.raises(
        NSESecurityMasterLifecycleParseError,
        match="must not be negative",
    ):
        parse_nse_security_master_lifecycle(row)


@pytest.mark.parametrize(
    "field",
    [
        "SctyStsNrmlMkt",
        "ElgbltyNrmlMkt",
        "DelFlg",
    ],
)
def test_parser_rejects_empty_code(field: str) -> None:
    row = make_row()
    row[field] = ""

    with pytest.raises(
        NSESecurityMasterLifecycleParseError,
        match=field,
    ):
        parse_nse_security_master_lifecycle(row)


def test_parser_rejects_non_mapping() -> None:
    with pytest.raises(
        NSESecurityMasterLifecycleParseError,
        match="mapping",
    ):
        parse_nse_security_master_lifecycle(
            object(),  # type: ignore[arg-type]
        )
