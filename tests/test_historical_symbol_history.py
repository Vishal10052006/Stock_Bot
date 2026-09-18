"""Tests for point-in-time instrument symbol history."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from market.data.historical.symbol_history import (
    InstrumentSymbolInterval,
    InstrumentSymbolTimeline,
)


def make_interval(
    *,
    isin: str = "INE000A01000",
    symbol: str = "OLDNAME",
    exchange: str = "NSE",
    effective_from: date = date(2020, 1, 1),
    effective_to: date | None = None,
) -> InstrumentSymbolInterval:
    return InstrumentSymbolInterval(
        isin=isin,
        symbol=symbol,
        exchange=exchange,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def test_interval_normalizes_identity_fields() -> None:
    interval = make_interval(
        isin=" ine000a01000 ",
        symbol=" oldname ",
        exchange=" nse ",
    )

    assert interval.isin == "INE000A01000"
    assert interval.symbol == "OLDNAME"
    assert interval.exchange == "NSE"


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"isin": ""}, "isin"),
        ({"symbol": ""}, "symbol"),
        ({"exchange": ""}, "exchange"),
        (
            {"effective_from": datetime(2020, 1, 1)},
            "effective_from",
        ),
        (
            {"effective_to": datetime(2020, 1, 2)},
            "effective_to",
        ),
    ],
)
def test_interval_rejects_invalid_values(
    kwargs: dict[str, object],
    error: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=error):
        make_interval(**kwargs)  # type: ignore[arg-type]


def test_interval_rejects_reversed_dates() -> None:
    with pytest.raises(ValueError, match="effective_to"):
        make_interval(
            effective_from=date(2024, 7, 1),
            effective_to=date(2024, 6, 30),
        )


def test_timeline_requires_one_isin() -> None:
    with pytest.raises(ValueError, match="same ISIN"):
        InstrumentSymbolTimeline(
            intervals=(
                make_interval(isin="INE000A01000"),
                make_interval(
                    isin="INE467B01029",
                    symbol="NEWNAME",
                    effective_from=date(2024, 7, 1),
                ),
            )
        )


def test_timeline_requires_one_exchange() -> None:
    with pytest.raises(ValueError, match="same exchange"):
        InstrumentSymbolTimeline(
            intervals=(
                make_interval(exchange="NSE"),
                make_interval(
                    exchange="BSE",
                    symbol="NEWNAME",
                    effective_from=date(2024, 7, 1),
                ),
            )
        )


def test_timeline_rejects_overlapping_intervals() -> None:
    with pytest.raises(ValueError, match="must not overlap"):
        InstrumentSymbolTimeline(
            intervals=(
                make_interval(
                    effective_from=date(2020, 1, 1),
                    effective_to=date(2024, 7, 15),
                ),
                make_interval(
                    symbol="NEWNAME",
                    effective_from=date(2024, 7, 1),
                ),
            )
        )


def test_timeline_rejects_open_interval_before_later_interval() -> None:
    with pytest.raises(ValueError, match="open-ended"):
        InstrumentSymbolTimeline(
            intervals=(
                make_interval(
                    effective_from=date(2020, 1, 1),
                ),
                make_interval(
                    symbol="NEWNAME",
                    effective_from=date(2024, 7, 1),
                ),
            )
        )


def test_timeline_is_automatically_chronological() -> None:
    timeline = InstrumentSymbolTimeline(
        intervals=(
            make_interval(
                symbol="NEWNAME",
                effective_from=date(2024, 7, 1),
            ),
            make_interval(
                symbol="OLDNAME",
                effective_from=date(2020, 1, 1),
                effective_to=date(2024, 6, 30),
            ),
        )
    )

    assert timeline.intervals[0].symbol == "OLDNAME"
    assert timeline.intervals[1].symbol == "NEWNAME"


def test_symbol_lookup_returns_none_before_known_history() -> None:
    timeline = InstrumentSymbolTimeline(
        intervals=(
            make_interval(
                effective_from=date(2020, 1, 1),
                effective_to=date(2024, 6, 30),
            ),
        )
    )

    assert timeline.symbol_on(date(2019, 12, 31)) is None


def test_symbol_lookup_returns_none_for_unknown_gap() -> None:
    timeline = InstrumentSymbolTimeline(
        intervals=(
            make_interval(
                effective_from=date(2020, 1, 1),
                effective_to=date(2022, 12, 31),
            ),
            make_interval(
                symbol="NEWNAME",
                effective_from=date(2024, 1, 1),
            ),
        )
    )

    assert timeline.symbol_on(date(2023, 6, 1)) is None


def test_symbol_lookup_tracks_rename_point_in_time() -> None:
    timeline = InstrumentSymbolTimeline(
        intervals=(
            make_interval(
                symbol="OLDNAME",
                effective_from=date(2020, 1, 1),
                effective_to=date(2024, 6, 30),
            ),
            make_interval(
                symbol="NEWNAME",
                effective_from=date(2024, 7, 1),
            ),
        )
    )

    assert timeline.symbol_on(date(2024, 6, 30)) == "OLDNAME"
    assert timeline.symbol_on(date(2024, 7, 1)) == "NEWNAME"


def test_timeline_is_immutable() -> None:
    timeline = InstrumentSymbolTimeline(
        intervals=(make_interval(),)
    )

    with pytest.raises(FrozenInstanceError):
        timeline.intervals = ()  # type: ignore[misc]


def test_interval_is_immutable() -> None:
    interval = make_interval()

    with pytest.raises(FrozenInstanceError):
        interval.symbol = "OTHER"  # type: ignore[misc]


def test_symbol_timeline_resolves_historical_symbol_changes():
    from datetime import date

    from market.data.historical.symbol_history import (
        InstrumentSymbolInterval,
        InstrumentSymbolTimeline,
    )

    timeline = InstrumentSymbolTimeline(
        (
            InstrumentSymbolInterval(
                isin="INE000A01000",
                symbol="OLDCO",
                exchange="NSE",
                effective_from=date(2020, 1, 1),
                effective_to=date(2022, 12, 31),
            ),
            InstrumentSymbolInterval(
                isin="INE000A01000",
                symbol="NEWCO",
                exchange="NSE",
                effective_from=date(2023, 1, 1),
            ),
        )
    )

    assert timeline.symbol_on(date(2021, 6, 1)) == "OLDCO"
    assert timeline.symbol_on(date(2022, 12, 31)) == "OLDCO"
    assert timeline.symbol_on(date(2023, 1, 1)) == "NEWCO"
    assert timeline.symbol_on(date(2026, 9, 5)) == "NEWCO"
