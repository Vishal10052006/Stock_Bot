"""Exchange-independent trading-session calendar contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class TradingSession:
    """Represents one valid exchange trading session."""

    session_date: date
    open_time: time
    close_time: time

    def __post_init__(self) -> None:
        """Validate session boundaries."""

        if self.close_time <= self.open_time:
            raise ValueError(
                "session close_time must be after open_time"
            )

    def contains(self, timestamp: datetime) -> bool:
        """Return whether a timestamp falls inside this session."""

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError(
                "timestamp must be timezone-aware"
            )

        if timestamp.date() != self.session_date:
            return False

        current_time = timestamp.timetz().replace(tzinfo=None)

        return self.open_time <= current_time < self.close_time


@runtime_checkable
class MarketSessionCalendar(Protocol):
    """Contract for exchange-specific trading-session calendars."""

    timezone: tzinfo

    def is_trading_day(self, session_date: date) -> bool:
        """Return whether the exchange trades on a date."""
        ...

    def get_session(
        self,
        session_date: date,
    ) -> TradingSession | None:
        """Return the trading session for a date."""
        ...

    def expected_timestamps(
        self,
        session_date: date,
        interval: timedelta,
    ) -> tuple[datetime, ...]:
        """
        Return expected candle-start timestamps for one session.

        The implementation owns exchange-specific timezone and session
        semantics.
        """
        ...


@dataclass(frozen=True, slots=True)
class FixedSessionCalendar:
    """
    Deterministic weekday-based calendar for contract testing.

    This calendar deliberately does not contain exchange holidays.
    """

    timezone: tzinfo
    open_time: time
    close_time: time

    def __post_init__(self) -> None:
        if self.close_time <= self.open_time:
            raise ValueError(
                "close_time must be after open_time"
            )

    def is_trading_day(self, session_date: date) -> bool:
        """Return True for Monday-Friday."""

        return session_date.weekday() < 5

    def get_session(
        self,
        session_date: date,
    ) -> TradingSession | None:
        """Return the regular weekday session."""

        if not self.is_trading_day(session_date):
            return None

        return TradingSession(
            session_date=session_date,
            open_time=self.open_time,
            close_time=self.close_time,
        )

    def expected_timestamps(
        self,
        session_date: date,
        interval: timedelta,
    ) -> tuple[datetime, ...]:
        """Return expected candle-start timestamps for a session."""

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
