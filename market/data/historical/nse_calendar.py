"""NSE equity-segment trading calendar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, tzinfo
from types import MappingProxyType
from typing import Mapping
from zoneinfo import ZoneInfo

from market.data.historical.calendar import (
    MarketSessionCalendar,
    TradingSession,
)


NSE_REGULAR_OPEN = time(9, 15)
NSE_REGULAR_CLOSE = time(15, 30)


# NSE 2026 regular-session holidays represented by this calendar.
NSE_2026_TRADING_HOLIDAYS = frozenset(
    {
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
    }
)


# Special-session dates for which timings are not represented here.
# We deliberately do not fabricate their opening/closing times.
NSE_2026_PENDING_SPECIAL_SESSIONS = frozenset(
    {
        date(2026, 11, 8),
    }
)


@dataclass(frozen=True, slots=True)
class NSETradingCalendar(MarketSessionCalendar):
    """Trading calendar for the NSE equity segment."""

    timezone: tzinfo = field(
        default_factory=lambda: ZoneInfo("Asia/Kolkata")
    )

    special_sessions: Mapping[date, TradingSession] = field(
        default_factory=dict
    )

    holidays: frozenset[date] = field(
        default=NSE_2026_TRADING_HOLIDAYS
    )

    pending_special_sessions: frozenset[date] = field(
        default=NSE_2026_PENDING_SPECIAL_SESSIONS
    )

    def __post_init__(self) -> None:
        """Validate and freeze calendar configuration."""

        if self.timezone is None:
            raise ValueError(
                "NSE calendar timezone must not be None"
            )

        object.__setattr__(
            self,
            "special_sessions",
            MappingProxyType(dict(self.special_sessions)),
        )

        overlap = (
            set(self.special_sessions)
            & set(self.holidays)
        )

        if overlap:
            raise ValueError(
                "special session cannot overlap an NSE holiday: "
                f"{sorted(overlap)}"
            )

        normalized_pending = (
            set(self.pending_special_sessions)
            - set(self.special_sessions)
        )

        object.__setattr__(
            self,
            "pending_special_sessions",
            frozenset(normalized_pending),
        )

    def is_trading_day(self, session_date: date) -> bool:
        """Return whether the date is potentially tradable."""

        if session_date in self.special_sessions:
            return True

        if session_date in self.pending_special_sessions:
            return True

        if session_date in self.holidays:
            return False

        return session_date.weekday() < 5

    def get_session(
        self,
        session_date: date,
    ) -> TradingSession | None:
        """Return the session for an NSE trading date."""

        if session_date in self.special_sessions:
            return self.special_sessions[session_date]

        if session_date in self.pending_special_sessions:
            return None

        if not self.is_trading_day(session_date):
            return None

        return TradingSession(
            session_date=session_date,
            open_time=NSE_REGULAR_OPEN,
            close_time=NSE_REGULAR_CLOSE,
        )

    def expected_timestamps(
        self,
        session_date: date,
        interval: timedelta,
    ) -> tuple[datetime, ...]:
        """Return expected candle-start timestamps for an NSE session."""

        if interval <= timedelta(0):
            raise ValueError(
                "interval must be greater than zero"
            )

        session = self.get_session(session_date)

        if session is None:
            return ()

        current = datetime.combine(
            session_date,
            session.open_time,
            tzinfo=self.timezone,
        )

        close = datetime.combine(
            session_date,
            session.close_time,
            tzinfo=self.timezone,
        )

        timestamps: list[datetime] = []

        while current < close:
            timestamps.append(current)
            current += interval

        return tuple(timestamps)
