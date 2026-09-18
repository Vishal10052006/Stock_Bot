"""Tests for raw NSE Security Master lifecycle evidence."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from market.data.historical.nse_security_master_lifecycle import (
    NSESecurityMasterLifecycle,
)


def make_lifecycle() -> NSESecurityMasterLifecycle:
    return NSESecurityMasterLifecycle(
        listing_date=date(1998, 2, 10),
        removal_date=None,
        readmission_date=None,
        normal_market_status="6",
        normal_market_eligibility="1",
        deletion_flag="N",
    )


def test_lifecycle_preserves_raw_nse_fields() -> None:
    lifecycle = make_lifecycle()

    assert lifecycle.listing_date == date(1998, 2, 10)
    assert lifecycle.removal_date is None
    assert lifecycle.readmission_date is None
    assert lifecycle.normal_market_status == "6"
    assert lifecycle.normal_market_eligibility == "1"
    assert lifecycle.deletion_flag == "N"


def test_lifecycle_normalizes_string_fields() -> None:
    lifecycle = NSESecurityMasterLifecycle(
        listing_date=None,
        removal_date=None,
        readmission_date=None,
        normal_market_status=" 6 ",
        normal_market_eligibility=" 1 ",
        deletion_flag=" y ",
    )

    assert lifecycle.normal_market_status == "6"
    assert lifecycle.normal_market_eligibility == "1"
    assert lifecycle.deletion_flag == "Y"


@pytest.mark.parametrize(
    "field",
    [
        "normal_market_status",
        "normal_market_eligibility",
        "deletion_flag",
    ],
)
def test_lifecycle_rejects_empty_raw_fields(field: str) -> None:
    values = {
        "listing_date": None,
        "removal_date": None,
        "readmission_date": None,
        "normal_market_status": "6",
        "normal_market_eligibility": "1",
        "deletion_flag": "N",
    }
    values[field] = ""

    with pytest.raises(ValueError, match=field):
        NSESecurityMasterLifecycle(**values)


@pytest.mark.parametrize(
    "field",
    [
        "listing_date",
        "removal_date",
        "readmission_date",
    ],
)
def test_lifecycle_rejects_datetime(field: str) -> None:
    values = {
        "listing_date": None,
        "removal_date": None,
        "readmission_date": None,
        "normal_market_status": "6",
        "normal_market_eligibility": "1",
        "deletion_flag": "N",
    }
    values[field] = datetime(2026, 9, 4)

    with pytest.raises(TypeError, match=field):
        NSESecurityMasterLifecycle(**values)


def test_lifecycle_rejects_invalid_date_type() -> None:
    with pytest.raises(TypeError, match="listing_date"):
        NSESecurityMasterLifecycle(
            listing_date="2026-09-04",  # type: ignore[arg-type]
            removal_date=None,
            readmission_date=None,
            normal_market_status="6",
            normal_market_eligibility="1",
            deletion_flag="N",
        )


def test_lifecycle_is_immutable() -> None:
    lifecycle = make_lifecycle()

    with pytest.raises(FrozenInstanceError):
        lifecycle.deletion_flag = "Y"  # type: ignore[misc]


def test_lifecycle_allows_zero_date_conversion_as_none() -> None:
    lifecycle = NSESecurityMasterLifecycle(
        listing_date=None,
        removal_date=None,
        readmission_date=None,
        normal_market_status="3",
        normal_market_eligibility="0",
        deletion_flag="Y",
    )

    assert lifecycle.listing_date is None
    assert lifecycle.removal_date is None
    assert lifecycle.readmission_date is None
