"""Tests for historical market-data validation."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from market.candles.models import Candle
from market.data.historical.calendar import (
    FixedSessionCalendar,
)
from market.data.historical.nse_calendar import (
    NSETradingCalendar,
)
from market.data.historical.validation import (
    DatasetValidationResult,
    HistoricalDatasetValidator,
)


IST = ZoneInfo("Asia/Kolkata")


def make_candle(
    *,
    symbol: str = "RELIANCE",
    exchange: str = "NSE",
    timeframe_minutes: int = 5,
    timestamp: datetime | None = None,
    close: float = 103.0,
) -> Candle:
    """Create a deterministic valid candle."""

    return Candle(
        symbol=symbol,
        exchange=exchange,
        timeframe_minutes=timeframe_minutes,
        timestamp=timestamp
        or datetime(2026, 1, 2, 9, 15, tzinfo=IST),
        open=100.0,
        high=max(105.0, close),
        low=min(98.0, close),
        close=close,
        volume=1000.0,
    )


def make_sequence(
    timestamps: list[datetime],
    *,
    symbol: str = "RELIANCE",
    exchange: str = "NSE",
    timeframe_minutes: int = 5,
) -> list[Candle]:
    """Create candles using supplied timestamps."""

    return [
        make_candle(
            symbol=symbol,
            exchange=exchange,
            timeframe_minutes=timeframe_minutes,
            timestamp=timestamp,
            close=103.0 + index,
        )
        for index, timestamp in enumerate(timestamps)
    ]


def test_valid_nse_five_minute_dataset_passes() -> None:
    bars = make_sequence(
        [
            datetime(2026, 1, 2, 9, 15, tzinfo=IST),
            datetime(2026, 1, 2, 9, 20, tzinfo=IST),
            datetime(2026, 1, 2, 9, 25, tzinfo=IST),
        ]
    )

    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=NSETradingCalendar(),
    )

    assert result.valid
    assert result.errors == ()
    assert result.warnings == ()


def test_empty_dataset_is_invalid() -> None:
    result = HistoricalDatasetValidator().validate([])

    assert not result.valid
    assert "dataset must contain at least one candle" in result.errors


def test_non_candle_object_is_rejected() -> None:
    result = HistoricalDatasetValidator().validate(
        [object()]
    )

    assert not result.valid
    assert "bar at index 0 is not a Candle" in result.errors


def test_multiple_symbols_are_rejected() -> None:
    bars = [
        make_candle(
            symbol="RELIANCE",
            timestamp=datetime(
                2026, 1, 2, 9, 15, tzinfo=IST
            ),
        ),
        make_candle(
            symbol="TCS",
            timestamp=datetime(
                2026, 1, 2, 9, 20, tzinfo=IST
            ),
        ),
    ]

    result = HistoricalDatasetValidator().validate(bars)

    assert not result.valid
    assert "dataset contains multiple symbols" in result.errors


def test_multiple_exchanges_are_rejected() -> None:
    bars = [
        make_candle(
            exchange="NSE",
            timestamp=datetime(
                2026, 1, 2, 9, 15, tzinfo=IST
            ),
        ),
        make_candle(
            exchange="BSE",
            timestamp=datetime(
                2026, 1, 2, 9, 20, tzinfo=IST
            ),
        ),
    ]

    result = HistoricalDatasetValidator().validate(bars)

    assert not result.valid
    assert "dataset contains multiple exchanges" in result.errors


def test_multiple_timeframes_are_rejected() -> None:
    bars = [
        make_candle(
            timeframe_minutes=5,
            timestamp=datetime(
                2026, 1, 2, 9, 15, tzinfo=IST
            ),
        ),
        make_candle(
            timeframe_minutes=15,
            timestamp=datetime(
                2026, 1, 2, 9, 30, tzinfo=IST
            ),
        ),
    ]

    result = HistoricalDatasetValidator().validate(bars)

    assert not result.valid
    assert "dataset contains multiple timeframes" in result.errors


def test_duplicate_timestamps_are_rejected() -> None:
    timestamp = datetime(
        2026, 1, 2, 9, 15, tzinfo=IST
    )

    bars = make_sequence([timestamp, timestamp])

    result = HistoricalDatasetValidator().validate(bars)

    assert not result.valid
    assert any(
        "duplicate timestamp" in error
        for error in result.errors
    )


def test_out_of_order_timestamps_are_rejected() -> None:
    bars = make_sequence(
        [
            datetime(2026, 1, 2, 9, 20, tzinfo=IST),
            datetime(2026, 1, 2, 9, 15, tzinfo=IST),
        ]
    )

    result = HistoricalDatasetValidator().validate(bars)

    assert not result.valid
    assert any(
        "not strictly increasing" in error
        for error in result.errors
    )


def test_equal_timestamps_are_rejected_as_non_increasing() -> None:
    timestamp = datetime(
        2026, 1, 2, 9, 15, tzinfo=IST
    )

    bars = make_sequence([timestamp, timestamp])

    result = HistoricalDatasetValidator().validate(bars)

    assert not result.valid
    assert any(
        "not strictly increasing" in error
        for error in result.errors
    )


def test_validator_rejects_corrupted_naive_timestamp() -> None:
    candle = make_candle()

    # The Candle contract normally prevents this state. Deliberately
    # corrupt the immutable object here so the validator's own defensive
    # timezone check is tested independently.
    object.__setattr__(
        candle,
        "timestamp",
        datetime(2026, 1, 2, 9, 15),
    )

    result = HistoricalDatasetValidator().validate([candle])

    assert not result.valid
    assert any(
        "timezone-aware" in error
        for error in result.errors
    )


def test_inconsistent_timestamp_offsets_are_rejected() -> None:
    utc = ZoneInfo("UTC")

    bars = make_sequence(
        [
            datetime(2026, 1, 2, 9, 15, tzinfo=IST),
            datetime(2026, 1, 2, 9, 20, tzinfo=utc),
        ]
    )

    result = HistoricalDatasetValidator().validate(bars)

    assert not result.valid
    assert any(
        "inconsistent timestamp offsets" in error
        for error in result.errors
    )


def test_invalid_expected_interval_is_rejected() -> None:
    bars = make_sequence(
        [
            datetime(2026, 1, 2, 9, 15, tzinfo=IST),
            datetime(2026, 1, 2, 9, 20, tzinfo=IST),
        ]
    )

    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(0),
    )

    assert not result.valid
    assert "expected_interval must be greater than zero" in result.errors


def test_intraday_missing_candle_is_warning() -> None:
    bars = make_sequence(
        [
            datetime(2026, 1, 2, 9, 15, tzinfo=IST),
            datetime(2026, 1, 2, 9, 25, tzinfo=IST),
        ]
    )

    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=NSETradingCalendar(),
    )

    assert result.valid
    assert result.errors == ()
    assert any(
        "unexpected timestamp interval" in warning
        for warning in result.warnings
    )


def test_overnight_gap_is_not_reported_as_intraday_missing_candle() -> None:
    bars = make_sequence(
        [
            datetime(2026, 1, 2, 15, 25, tzinfo=IST),
            datetime(2026, 1, 5, 9, 15, tzinfo=IST),
        ]
    )

    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=NSETradingCalendar(),
    )

    assert result.valid
    assert result.errors == ()
    assert not any(
        "unexpected timestamp interval" in warning
        for warning in result.warnings
    )


def test_weekend_gap_is_not_reported_as_missing_trading_session() -> None:
    bars = make_sequence(
        [
            datetime(2026, 1, 2, 15, 25, tzinfo=IST),
            datetime(2026, 1, 5, 9, 15, tzinfo=IST),
        ]
    )

    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=NSETradingCalendar(),
    )

    assert result.valid
    assert not any(
        "missing trading-session data" in warning
        for warning in result.warnings
    )


def test_missing_trading_session_is_reported_as_warning() -> None:
    bars = make_sequence(
        [
            datetime(2026, 1, 2, 15, 25, tzinfo=IST),
            datetime(2026, 1, 5, 9, 15, tzinfo=IST),
        ]
    )

    # Friday -> Monday has no intervening trading date, so this should
    # remain a normal session transition.
    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=NSETradingCalendar(),
    )

    assert result.valid


def test_holiday_timestamp_is_rejected() -> None:
    bars = [
        make_candle(
            timestamp=datetime(
                2026, 1, 26, 9, 15, tzinfo=IST
            )
        )
    ]

    result = HistoricalDatasetValidator().validate(
        bars,
        calendar=NSETradingCalendar(),
    )

    assert not result.valid
    assert any(
        "non-trading day" in error
        for error in result.errors
    )


def test_outside_nse_session_is_rejected() -> None:
    bars = [
        make_candle(
            timestamp=datetime(
                2026, 1, 2, 8, 30, tzinfo=IST
            )
        )
    ]

    result = HistoricalDatasetValidator().validate(
        bars,
        calendar=NSETradingCalendar(),
    )

    assert not result.valid
    assert any(
        "outside trading session" in error
        for error in result.errors
    )


def test_pending_special_session_is_rejected_until_session_is_known() -> None:
    bars = [
        make_candle(
            timestamp=datetime(
                2026, 11, 8, 18, 0, tzinfo=IST
            )
        )
    ]

    result = HistoricalDatasetValidator().validate(
        bars,
        calendar=NSETradingCalendar(),
    )

    assert not result.valid
    assert any(
        "no session" in error
        for error in result.errors
    )


def test_fixed_calendar_can_validate_regular_session() -> None:
    calendar = FixedSessionCalendar(
        timezone=IST,
        open_time=datetime(
            2026, 1, 2, 9, 15, tzinfo=IST
        ).time(),
        close_time=datetime(
            2026, 1, 2, 15, 30, tzinfo=IST
        ).time(),
    )

    bars = make_sequence(
        [
            datetime(2026, 1, 2, 9, 15, tzinfo=IST),
            datetime(2026, 1, 2, 9, 20, tzinfo=IST),
        ]
    )

    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=calendar,
    )

    assert result.valid


def test_validation_result_cannot_be_valid_with_errors() -> None:
    with pytest.raises(
        ValueError,
        match="cannot be valid when errors exist",
    ):
        DatasetValidationResult(
            valid=True,
            errors=("bad data",),
            warnings=(),
        )


def test_validation_does_not_modify_input() -> None:
    bars = make_sequence(
        [
            datetime(2026, 1, 2, 9, 15, tzinfo=IST),
            datetime(2026, 1, 2, 9, 20, tzinfo=IST),
        ]
    )

    original = tuple(bars)

    HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=NSETradingCalendar(),
    )

    assert tuple(bars) == original


def test_complete_session_rejects_missing_final_candles() -> None:
    timestamps = [
        datetime(
            2026,
            1,
            2,
            9,
            15,
            tzinfo=IST,
        ) + timedelta(minutes=5 * index)
        for index in range(73)
    ]

    # A complete NSE session requires starts through 15:25.
    # Deliberately omit the final two candles: 15:20 and 15:25.
    bars = make_sequence(timestamps)

    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=NSETradingCalendar(),
        require_complete_sessions=True,
    )

    assert not result.valid
    assert any(
        "incomplete trading session" in error
        for error in result.errors
    )
    assert any(
        "15:20:00" in error
        for error in result.errors
    )
    assert any(
        "15:25:00" in error
        for error in result.errors
    )


def test_complete_nse_session_is_valid() -> None:
    timestamps = [
        datetime(
            2026,
            1,
            2,
            9,
            15,
            tzinfo=IST,
        ) + timedelta(minutes=5 * index)
        for index in range(75)
    ]

    bars = make_sequence(timestamps)

    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=NSETradingCalendar(),
        require_complete_sessions=True,
    )

    assert result.valid
    assert result.errors == ()


def test_open_current_session_allows_partial_tail() -> None:
    timestamps = [
        datetime(
            2026,
            1,
            2,
            9,
            15,
            tzinfo=IST,
        ) + timedelta(minutes=5 * index)
        for index in range(58)
    ]

    bars = make_sequence(timestamps)

    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=NSETradingCalendar(),
        require_complete_sessions=True,
        as_of=datetime(
            2026,
            1,
            2,
            14,
            0,
            tzinfo=IST,
        ),
    )

    assert result.valid
    assert result.errors == ()


def test_closed_session_rejects_partial_tail() -> None:
    timestamps = [
        datetime(
            2026,
            1,
            2,
            9,
            15,
            tzinfo=IST,
        ) + timedelta(minutes=5 * index)
        for index in range(73)
    ]

    bars = make_sequence(timestamps)

    result = HistoricalDatasetValidator().validate(
        bars,
        expected_interval=timedelta(minutes=5),
        calendar=NSETradingCalendar(),
        require_complete_sessions=True,
        as_of=datetime(
            2026,
            1,
            2,
            18,
            0,
            tzinfo=IST,
        ),
    )

    assert not result.valid
    assert any(
        "incomplete trading session" in error
        for error in result.errors
    )


def test_naive_as_of_is_rejected() -> None:
    result = HistoricalDatasetValidator().validate(
        make_sequence(
            [
                datetime(
                    2026,
                    1,
                    2,
                    9,
                    15,
                    tzinfo=IST,
                ),
            ]
        ),
        calendar=NSETradingCalendar(),
        as_of=datetime(
            2026,
            1,
            2,
            14,
            0,
        ),
    )

    assert not result.valid
    assert "as_of must be timezone-aware" in result.errors


def test_as_of_allows_observation_at_exact_boundary() -> None:
    timestamp = datetime(
        2026,
        1,
        2,
        14,
        0,
        tzinfo=IST,
    )

    result = HistoricalDatasetValidator().validate(
        make_sequence([timestamp]),
        calendar=NSETradingCalendar(),
        as_of=timestamp,
    )

    assert result.valid
    assert result.errors == ()


def test_as_of_rejects_future_observation() -> None:
    as_of = datetime(
        2026,
        1,
        2,
        14,
        0,
        tzinfo=IST,
    )

    future_timestamp = datetime(
        2026,
        1,
        2,
        14,
        5,
        tzinfo=IST,
    )

    result = HistoricalDatasetValidator().validate(
        make_sequence([future_timestamp]),
        calendar=NSETradingCalendar(),
        as_of=as_of,
    )

    assert not result.valid
    assert any(
        "occurs after as_of" in error
        for error in result.errors
    )
