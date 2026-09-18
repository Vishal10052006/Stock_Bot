"""Tests for historical corporate-action contracts."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from market.data.historical.corporate_actions import (
    CorporateAction,
    CorporateActionType,
)


def make_action(**overrides: object) -> CorporateAction:
    values: dict[str, object] = {
        "isin": "INE002A01018",
        "action_type": CorporateActionType.DIVIDEND,
        "ex_date": date(2026, 8, 27),
        "announcement_date": date(2026, 8, 20),
        "record_date": date(2026, 8, 28),
        "amount": Decimal("10.50"),
        "currency": "INR",
        "source": "upstox",
    }
    values.update(overrides)
    return CorporateAction(**values)


def test_corporate_action_accepts_valid_event() -> None:
    action = make_action()

    assert action.isin == "INE002A01018"
    assert action.action_type is CorporateActionType.DIVIDEND
    assert action.ex_date == date(2026, 8, 27)
    assert action.amount == Decimal("10.50")
    assert action.currency == "INR"


def test_corporate_action_is_immutable() -> None:
    action = make_action()

    with pytest.raises(AttributeError):
        action.isin = "INE467B01029"


def test_corporate_action_requires_isin() -> None:
    with pytest.raises(ValueError, match="isin"):
        make_action(isin="")


def test_corporate_action_rejects_invalid_action_type() -> None:
    with pytest.raises(TypeError, match="CorporateActionType"):
        make_action(action_type="dividend")


def test_corporate_action_rejects_datetime_for_date_fields() -> None:
    with pytest.raises(TypeError, match="ex_date must be a date or None"):
        make_action(
            ex_date=datetime(2026, 8, 27, 9, 15),
        )


def test_announcement_date_cannot_follow_ex_date() -> None:
    with pytest.raises(
        ValueError,
        match="announcement_date must be on or before ex_date",
    ):
        make_action(
            announcement_date=date(2026, 8, 28),
        )


def test_record_date_cannot_precede_ex_date() -> None:
    with pytest.raises(
        ValueError,
        match="record_date must be on or after ex_date",
    ):
        make_action(
            record_date=date(2026, 8, 26),
        )


def test_ratio_requires_both_components() -> None:
    with pytest.raises(
        ValueError,
        match="provided together",
    ):
        make_action(ratio_numerator=1)


def test_ratio_components_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="ratio_numerator",
    ):
        make_action(
            ratio_numerator=0,
            ratio_denominator=1,
        )


def test_amount_must_be_decimal() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        make_action(amount=10.50)


def test_amount_cannot_be_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        make_action(amount=Decimal("-1"))


def test_currency_must_not_be_blank() -> None:
    with pytest.raises(
        ValueError,
        match="currency must be a non-empty string",
    ):
        make_action(currency=" ")


def test_source_is_required() -> None:
    with pytest.raises(
        ValueError,
        match="source must be a non-empty string",
    ):
        make_action(source="")
