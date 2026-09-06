from datetime import date

import pytest

from market.data.historical.nse_symbol_change_parser import (
    NSESymbolChangeParseError,
    parse_nse_symbol_change_row,
)


def test_parse_real_symbol_transition() -> None:
    record = parse_nse_symbol_change_row(
        [
            "Shalimar Paints Limited",
            "SHALMPAINT",
            "SHALPAINTS",
            "03-MAR-2008",
        ]
    )

    assert record.company == "Shalimar Paints Limited"
    assert record.old_symbol == "SHALMPAINT"
    assert record.new_symbol == "SHALPAINTS"
    assert record.effective_date == date(2008, 3, 3)
    assert record.source == "nse_symbol_change"


def test_parse_same_symbol_nse_record() -> None:
    record = parse_nse_symbol_change_row(
        [
            "Indiabulls Commercial Credit Limited",
            "955SFIL26",
            "955SFIL26",
            "26-DEC-2025",
        ]
    )

    assert record.old_symbol == "955SFIL26"
    assert record.new_symbol == "955SFIL26"
    assert record.effective_date == date(2025, 12, 26)


def test_parse_missing_company_nse_record() -> None:
    record = parse_nse_symbol_change_row(
        [
            "",
            "780LTFL30",
            "799LTFL30",
            "19-FEB-2025",
        ]
    )

    assert record.company is None
    assert record.old_symbol == "780LTFL30"
    assert record.new_symbol == "799LTFL30"
    assert record.effective_date == date(2025, 2, 19)


@pytest.mark.parametrize(
    "row",
    [
        ["Company", "OLD", "NEW"],
        ["Company", "OLD", "NEW", "03-MAR-2008", "EXTRA"],
        ["Company", "", "NEW", "03-MAR-2008"],
        ["Company", "OLD", "", "03-MAR-2008"],
        ["Company", "OLD", "NEW", ""],
        ["Company", "OLD", "NEW", "INVALID-DATE"],
    ],
)
def test_parser_rejects_malformed_rows(row: list[str]) -> None:
    with pytest.raises(NSESymbolChangeParseError):
        parse_nse_symbol_change_row(row)
