"""Tests for explicit security-lineage transition evidence."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from market.data.historical.security_lineage_transition import (
    SecurityLineageTransition,
)


def make_transition() -> SecurityLineageTransition:
    return SecurityLineageTransition(
        old_symbol="SHALMPAINT",
        new_symbol="SHALPAINTS",
        effective_date=date(2008, 3, 3),
        source="nse_symbol_change",
    )


def test_transition_preserves_explicit_evidence() -> None:
    transition = make_transition()

    assert transition.old_symbol == "SHALMPAINT"
    assert transition.new_symbol == "SHALPAINTS"
    assert transition.effective_date == date(2008, 3, 3)
    assert transition.source == "nse_symbol_change"


def test_transition_normalizes_values() -> None:
    transition = SecurityLineageTransition(
        old_symbol=" shalmpaint ",
        new_symbol=" shalpaints ",
        effective_date=date(2008, 3, 3),
        source=" nse_symbol_change ",
    )

    assert transition.old_symbol == "SHALMPAINT"
    assert transition.new_symbol == "SHALPAINTS"
    assert transition.source == "nse_symbol_change"


@pytest.mark.parametrize(
    "field",
    [
        "old_symbol",
        "new_symbol",
        "source",
    ],
)
def test_transition_rejects_empty_fields(field: str) -> None:
    values = {
        "old_symbol": "SHALMPAINT",
        "new_symbol": "SHALPAINTS",
        "effective_date": date(2008, 3, 3),
        "source": "nse_symbol_change",
    }
    values[field] = ""

    with pytest.raises(ValueError, match=field):
        SecurityLineageTransition(**values)


def test_transition_rejects_invalid_date() -> None:
    with pytest.raises(TypeError, match="effective_date"):
        SecurityLineageTransition(
            old_symbol="OLD",
            new_symbol="NEW",
            effective_date=datetime(2008, 3, 3),
            source="test",
        )


def test_transition_is_immutable() -> None:
    transition = make_transition()

    with pytest.raises(FrozenInstanceError):
        transition.new_symbol = "OTHER"  # type: ignore[misc]


def test_transition_rejects_same_symbol() -> None:
    with pytest.raises(
        ValueError,
        match="old_symbol and new_symbol must differ",
    ):
        SecurityLineageTransition(
            old_symbol="955SFIL26",
            new_symbol="955SFIL26",
            effective_date=date(2025, 12, 26),
            source="nse_symbol_change",
        )


def test_transition_from_nse_symbol_change() -> None:
    from market.data.historical.nse_symbol_change import (
        NSESymbolChangeRecord,
    )

    record = NSESymbolChangeRecord(
        company="Shalimar Paints Limited",
        old_symbol="SHALMPAINT",
        new_symbol="SHALPAINTS",
        effective_date=date(2008, 3, 3),
    )

    transition = SecurityLineageTransition.from_nse_symbol_change(record)

    assert transition.old_symbol == "SHALMPAINT"
    assert transition.new_symbol == "SHALPAINTS"
    assert transition.effective_date == date(2008, 3, 3)
    assert transition.source == "nse_symbol_change"


def test_transition_from_nse_symbol_change_rejects_wrong_type() -> None:
    with pytest.raises(TypeError, match="NSESymbolChangeRecord"):
        SecurityLineageTransition.from_nse_symbol_change(  # type: ignore[arg-type]
            object()
        )
