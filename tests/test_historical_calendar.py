"""Tests for historical trading-session calendars."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from market.data.historical.calendar import (
    FixedSessionCalendar,
    TradingSession,
)
from market.data.historical.nse_calendar import (
    NSE_REGULAR_CLOSE,
    NSE_REGULAR_OPEN,
    NSETradingCalendar,
)


IST = ZoneInfo("Asia/Kolkata")


def test_trading_session_accepts_valid_boundaries() -> None:
    session = TradingSession(
        session_date=date(2026, 1, 2),
        open_time=time(9, 15),
        close_time=time(15, 30),
    )

    assert session.contains(
        datetime(2026, 1, 2, 9, 15, tzinfo=IST)
    )

    assert not session.contains(
        datetime(2026, 1, 2, 15, 30, tzinfo=IST)
    )


def test_trading_session_rejects_invalid_boundaries() -> None:
    with pytest.raises(
        ValueError,
        match="close_time must be after open_time",
    ):
        TradingSession(
            session_date=date(2026, 1, 2),
            open_time=time(15, 30),
            close_time=time(9, 15),
        )


def test_trading_session_rejects_naive_timestamp() -> None:
    session = TradingSession(
        session_date=date(2026, 1, 2),
        open_time=time(9, 15),
        close_time=time(15, 30),
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        session.contains(
            datetime(2026, 1, 2, 10, 0)
        )


def test_nse_calendar_uses_india_timezone() -> None:
    calendar = NSETradingCalendar()

    assert calendar.timezone == IST


def test_nse_regular_session_is_0915_to_1530() -> None:
    calendar = NSETradingCalendar()

    session = calendar.get_session(date(2026, 1, 2))

    assert session is not None
    assert session.open_time == NSE_REGULAR_OPEN
    assert session.close_time == NSE_REGULAR_CLOSE


def test_nse_weekend_is_not_trading_day() -> None:
    calendar = NSETradingCalendar()

    saturday = date(2026, 1, 3)
    sunday = date(2026, 1, 4)

    assert not calendar.is_trading_day(saturday)
    assert not calendar.is_trading_day(sunday)
    assert calendar.get_session(saturday) is None
    assert calendar.get_session(sunday) is None


def test_nse_holiday_is_not_trading_day() -> None:
    calendar = NSETradingCalendar()

    assert not calendar.is_trading_day(date(2026, 1, 26))
    assert calendar.get_session(date(2026, 1, 26)) is None


@pytest.mark.parametrize(
    "holiday",
    [
        date(2026, 1, 26),
        date(2026, 3, 3),
        date(2026, 3, 26),
        date(2026, 3, 31),
        date(2026, 4, 3),
        date(2026, 4, 14),
        date(2026, 5, 1),
        date(2026, 5, 28),
        date(2026, 6, 26),
        date(2026, 9, 14),
        date(2026, 10, 2),
        date(2026, 10, 20),
        date(2026, 11, 10),
        date(2026, 11, 24),
        date(2026, 12, 25),
    ],
)
def test_nse_all_2026_regular_holidays_are_closed(
    holiday: date,
) -> None:
    calendar = NSETradingCalendar()

    assert not calendar.is_trading_day(holiday)
    assert calendar.get_session(holiday) is None
    assert calendar.expected_timestamps(
        holiday,
        timedelta(minutes=5),
    ) == ()


def test_nse_settlement_holiday_2026_08_26_remains_trading_day() -> None:
    calendar = NSETradingCalendar()

    session_date = date(2026, 8, 26)

    assert calendar.is_trading_day(session_date)

    session = calendar.get_session(session_date)

    assert session is not None
    assert session.open_time == NSE_REGULAR_OPEN
    assert session.close_time == NSE_REGULAR_CLOSE

    timestamps = calendar.expected_timestamps(
        session_date,
        timedelta(minutes=5),
    )

    assert len(timestamps) == 75
    assert timestamps[0] == datetime(
        2026,
        8,
        26,
        9,
        15,
        tzinfo=IST,
    )
    assert timestamps[-1] == datetime(
        2026,
        8,
        26,
        15,
        25,
        tzinfo=IST,
    )


def test_nse_before_open_is_outside_session() -> None:
    calendar = NSETradingCalendar()

    session = calendar.get_session(date(2026, 1, 2))

    assert session is not None
    assert not session.contains(
        datetime(2026, 1, 2, 9, 14, 59, tzinfo=IST)
    )


def test_nse_after_close_is_outside_session() -> None:
    calendar = NSETradingCalendar()

    session = calendar.get_session(date(2026, 1, 2))

    assert session is not None
    assert not session.contains(
        datetime(2026, 1, 2, 15, 30, 1, tzinfo=IST)
    )


def test_pending_special_session_has_no_guessed_session() -> None:
    calendar = NSETradingCalendar()

    pending_date = date(2026, 11, 8)

    assert calendar.is_trading_day(pending_date)
    assert calendar.get_session(pending_date) is None


def test_explicit_special_session_overrides_pending_date() -> None:
    special_date = date(2026, 11, 8)

    special_session = TradingSession(
        session_date=special_date,
        open_time=time(18, 0),
        close_time=time(19, 0),
    )

    calendar = NSETradingCalendar(
        special_sessions={
            special_date: special_session,
        }
    )

    assert calendar.is_trading_day(special_date)
    assert calendar.get_session(special_date) == special_session


def test_special_session_cannot_overlap_holiday() -> None:
    holiday = date(2026, 1, 26)

    session = TradingSession(
        session_date=holiday,
        open_time=time(9, 15),
        close_time=time(15, 30),
    )

    with pytest.raises(
        ValueError,
        match="cannot overlap an NSE holiday",
    ):
        NSETradingCalendar(
            special_sessions={holiday: session}
        )


def test_fixed_calendar_weekday_contract() -> None:
    calendar = FixedSessionCalendar(
        timezone=IST,
        open_time=time(9, 15),
        close_time=time(15, 30),
    )

    assert calendar.is_trading_day(date(2026, 1, 2))
    assert not calendar.is_trading_day(date(2026, 1, 3))

    session = calendar.get_session(date(2026, 1, 2))

    assert session is not None
    assert session.open_time == time(9, 15)
    assert session.close_time == time(15, 30)


def test_nse_five_minute_session_has_75_candle_starts() -> None:
    calendar = NSETradingCalendar()

    timestamps = calendar.expected_timestamps(
        date(2026, 1, 2),
        timedelta(minutes=5),
    )

    assert len(timestamps) == 75
    assert timestamps[0] == datetime(
        2026,
        1,
        2,
        9,
        15,
        tzinfo=IST,
    )
    assert timestamps[-1] == datetime(
        2026,
        1,
        2,
        15,
        25,
        tzinfo=IST,
    )


def test_nse_holiday_has_no_expected_candle_timestamps() -> None:
    calendar = NSETradingCalendar()

    timestamps = calendar.expected_timestamps(
        date(2026, 1, 26),
        timedelta(minutes=5),
    )

    assert timestamps == ()


def test_fixed_calendar_generates_expected_timestamps() -> None:
    calendar = FixedSessionCalendar(
        timezone=IST,
        open_time=time(9, 15),
        close_time=time(9, 30),
    )

    timestamps = calendar.expected_timestamps(
        date(2026, 1, 2),
        timedelta(minutes=5),
    )

    assert timestamps == (
        datetime(
            2026,
            1,
            2,
            9,
            15,
            tzinfo=IST,
        ),
        datetime(
            2026,
            1,
            2,
            9,
            20,
            tzinfo=IST,
        ),
        datetime(
            2026,
            1,
            2,
            9,
            25,
            tzinfo=IST,
        ),
    )


def test_nse_session_close_is_exclusive() -> None:
    calendar = NSETradingCalendar()

    session = calendar.get_session(date(2026, 1, 2))

    assert session is not None

    assert session.contains(
        datetime(
            2026,
            1,
            2,
            15,
            25,
            tzinfo=IST,
        )
    )

    assert not session.contains(
        datetime(
            2026,
            1,
            2,
            15,
            30,
            tzinfo=IST,
        )
    )
