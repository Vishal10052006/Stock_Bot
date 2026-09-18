"""Parser for NSE historical symbol-change records."""

from __future__ import annotations

from collections.abc import Sequence

from market.data.historical.nse_symbol_change import (
    NSESymbolChangeRecord,
)


class NSESymbolChangeParseError(ValueError):
    """Raised when an NSE symbol-change row is invalid."""


def parse_nse_symbol_change_row(
    row: Sequence[object],
) -> NSESymbolChangeRecord:
    """Parse one NSE symbol-change CSV row.

    Expected NSE structure:

        Company Name, Old Symbol, New Symbol, Effective Date
    """

    if not isinstance(row, (list, tuple)):
        raise NSESymbolChangeParseError(
            "symbol-change row must be a list or tuple"
        )

    if len(row) != 4:
        raise NSESymbolChangeParseError(
            "symbol-change row must contain exactly 4 fields"
        )

    company, old_symbol, new_symbol, effective_date = row

    if not isinstance(company, str):
        raise NSESymbolChangeParseError(
            "company must be a string"
        )

    for name, value in (
        ("old_symbol", old_symbol),
        ("new_symbol", new_symbol),
        ("effective_date", effective_date),
    ):
        if not isinstance(value, str) or not value.strip():
            raise NSESymbolChangeParseError(
                f"{name} must be a non-empty string"
            )

    try:
        parsed_date = __import__("datetime").datetime.strptime(
            effective_date.strip(),
            "%d-%b-%Y",
        ).date()
    except ValueError as exc:
        raise NSESymbolChangeParseError(
            "effective_date must use DD-MMM-YYYY format"
        ) from exc

    try:
        return NSESymbolChangeRecord(
            company=company,
            old_symbol=old_symbol,
            new_symbol=new_symbol,
            effective_date=parsed_date,
        )
    except (TypeError, ValueError) as exc:
        raise NSESymbolChangeParseError(
            "invalid NSE symbol-change record"
        ) from exc
