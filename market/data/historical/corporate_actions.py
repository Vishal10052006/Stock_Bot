"""Provider-neutral corporate-action contracts for historical market data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class CorporateActionType(str, Enum):
    """Supported corporate-action categories."""

    DIVIDEND = "dividend"
    BONUS = "bonus"
    SPLIT = "split"
    RIGHTS = "rights"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class CorporateAction:
    """Immutable corporate-action event associated with an instrument."""

    isin: str
    action_type: CorporateActionType
    ex_date: date
    source: str
    announcement_date: date | None = None
    record_date: date | None = None
    ratio_numerator: int | None = None
    ratio_denominator: int | None = None
    amount: Decimal | None = None
    currency: str | None = None

    def __post_init__(self) -> None:
        """Validate the corporate-action contract."""

        if not isinstance(self.isin, str) or not self.isin.strip():
            raise ValueError("isin must be a non-empty string")

        if not isinstance(self.action_type, CorporateActionType):
            raise TypeError(
                "action_type must be a CorporateActionType"
            )

        for name, value in (
            ("ex_date", self.ex_date),
            ("announcement_date", self.announcement_date),
            ("record_date", self.record_date),
        ):
            if value is not None and (
                not isinstance(value, date)
                or isinstance(value, datetime)
            ):
                raise TypeError(
                    f"{name} must be a date or None"
                )

        if (
            self.announcement_date is not None
            and self.announcement_date > self.ex_date
        ):
            raise ValueError(
                "announcement_date must be on or before ex_date"
            )

        if (
            self.record_date is not None
            and self.record_date < self.ex_date
        ):
            raise ValueError(
                "record_date must be on or after ex_date"
            )

        if (
            self.ratio_numerator is not None
            and (
                not isinstance(self.ratio_numerator, int)
                or isinstance(self.ratio_numerator, bool)
                or self.ratio_numerator <= 0
            )
        ):
            raise ValueError(
                "ratio_numerator must be a positive integer or None"
            )

        if (
            self.ratio_denominator is not None
            and (
                not isinstance(self.ratio_denominator, int)
                or isinstance(self.ratio_denominator, bool)
                or self.ratio_denominator <= 0
            )
        ):
            raise ValueError(
                "ratio_denominator must be a positive integer or None"
            )

        if (
            (self.ratio_numerator is None)
            != (self.ratio_denominator is None)
        ):
            raise ValueError(
                "ratio_numerator and ratio_denominator must be "
                "provided together"
            )

        if self.amount is not None:
            if not isinstance(self.amount, Decimal):
                raise TypeError("amount must be a Decimal or None")
            if self.amount < 0:
                raise ValueError("amount must be non-negative")

        if self.currency is not None:
            if (
                not isinstance(self.currency, str)
                or not self.currency.strip()
            ):
                raise ValueError(
                    "currency must be a non-empty string or None"
                )

        if (
            not isinstance(self.source, str)
            or not self.source.strip()
        ):
            raise ValueError("source must be a non-empty string")
