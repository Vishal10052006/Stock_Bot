"""Aggregate validated market events into time-based OHLCV candles.

Reference:
    ROADMAP_STOCK-BOT.pdf — Phase 4, Indicator Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from market.candles.models import Candle
from market.data.events import MarketEvent, MarketEventType


IST = ZoneInfo("Asia/Kolkata")


@dataclass
class _CandleState:
    """Mutable internal state for one currently forming candle."""

    symbol: str
    exchange: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    last_event_timestamp: datetime

    def update(self, event: MarketEvent) -> None:
        """Update OHLCV values with a chronologically valid event."""
        if event.exchange_timestamp < self.last_event_timestamp:
            raise ValueError(
                "market events must be supplied in chronological order"
            )

        self.high = max(self.high, event.price)
        self.low = min(self.low, event.price)
        self.close = event.price
        self.volume += event.volume
        self.last_event_timestamp = event.exchange_timestamp

    def to_candle(self, timeframe_minutes: int) -> Candle:
        """Convert internal state into an immutable Candle."""
        return Candle(
            symbol=self.symbol,
            exchange=self.exchange,
            timeframe_minutes=timeframe_minutes,
            timestamp=self.timestamp,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )


class CandleAggregator:
    """Aggregate MarketEvent trade events into fixed-time OHLCV candles.

    The default configuration creates five-minute NSE equity candles
    aligned to the normal session beginning at 09:15 IST.

    The aggregator keeps one forming candle per symbol. A completed candle
    is returned when an event arrives in the next time bucket.

    The final in-progress candle can be emitted explicitly with ``flush``.
    """

    def __init__(
        self,
        *,
        timeframe_minutes: int = 5,
        session_start: time = time(9, 15),
        session_end: time = time(15, 30),
        timezone: ZoneInfo = IST,
    ) -> None:
        """Configure candle timeframe and exchange session."""
        if timeframe_minutes <= 0:
            raise ValueError(
                "timeframe_minutes must be greater than zero"
            )

        if session_start >= session_end:
            raise ValueError(
                "session_start must be earlier than session_end"
            )

        session_minutes = (
            datetime.combine(
                datetime.min.date(),
                session_end,
            )
            - datetime.combine(
                datetime.min.date(),
                session_start,
            )
        ).total_seconds() / 60

        if session_minutes % timeframe_minutes != 0:
            raise ValueError(
                "timeframe_minutes must divide the session duration exactly"
            )

        self.timeframe_minutes = timeframe_minutes
        self.session_start = session_start
        self.session_end = session_end
        self.timezone = timezone

        # One active candle per symbol.
        self._states: dict[str, _CandleState] = {}

    def _session_bounds(
        self,
        timestamp: datetime,
    ) -> tuple[datetime, datetime]:
        """Return the NSE session bounds for the event's local date."""
        local_timestamp = timestamp.astimezone(self.timezone)
        session_date = local_timestamp.date()

        start = datetime.combine(
            session_date,
            self.session_start,
            tzinfo=self.timezone,
        )

        end = datetime.combine(
            session_date,
            self.session_end,
            tzinfo=self.timezone,
        )

        return start, end

    def _bucket_start(self, timestamp: datetime) -> datetime | None:
        """Return the candle start for an exchange timestamp.

        Events outside the configured normal trading session are ignored.
        """
        local_timestamp = timestamp.astimezone(self.timezone)

        session_start, session_end = self._session_bounds(timestamp)

        if local_timestamp < session_start:
            return None

        if local_timestamp >= session_end:
            return None

        elapsed_seconds = (
            local_timestamp - session_start
        ).total_seconds()

        bucket_number = int(
            elapsed_seconds // (self.timeframe_minutes * 60)
        )

        return session_start + timedelta(
            minutes=bucket_number * self.timeframe_minutes
        )

    def _create_state(
        self,
        event: MarketEvent,
        bucket_start: datetime,
    ) -> _CandleState:
        """Create a new forming candle from the first event."""
        return _CandleState(
            symbol=event.symbol,
            exchange=event.exchange,
            timestamp=bucket_start,
            open=event.price,
            high=event.price,
            low=event.price,
            close=event.price,
            volume=event.volume,
            last_event_timestamp=event.exchange_timestamp,
        )

    def update(self, event: MarketEvent) -> Candle | None:
        """Process one MarketEvent.

        Returns:
            A completed Candle when this event starts a new bucket.
            ``None`` when the current candle remains in progress.

        Raises:
            TypeError:
                If ``event`` is not a MarketEvent.
            ValueError:
                If a non-trade event is supplied.
        """
        if not isinstance(event, MarketEvent):
            raise TypeError("event must be a MarketEvent")

        if event.event_type is not MarketEventType.TRADE:
            raise ValueError(
                "CandleAggregator currently accepts trade events only"
            )

        bucket_start = self._bucket_start(
            event.exchange_timestamp
        )

        # Ignore events outside the configured normal trading session.
        if bucket_start is None:
            return None

        symbol = event.symbol.strip().upper()

        current = self._states.get(symbol)

        if current is None:
            self._states[symbol] = self._create_state(
                event,
                bucket_start,
            )
            return None

        if event.exchange_timestamp < current.last_event_timestamp:
            raise ValueError(
                "market events must be supplied in chronological order"
            )

        if bucket_start == current.timestamp:
            current.update(event)
            return None

        if bucket_start < current.timestamp:
            raise ValueError(
                "market event belongs to an already completed candle"
            )

        completed = current.to_candle(
            self.timeframe_minutes
        )

        self._states[symbol] = self._create_state(
            event,
            bucket_start,
        )

        return completed

    def flush(
        self,
        symbol: str | None = None,
    ) -> list[Candle]:
        """Emit and clear currently forming candles.

        Args:
            symbol: Optional symbol to flush. If omitted, all symbols are
                flushed.

        Returns:
            Completed candles created from the current in-progress states.
        """
        if symbol is not None:
            normalized_symbol = symbol.strip().upper()

            state = self._states.pop(
                normalized_symbol,
                None,
            )

            if state is None:
                return []

            return [
                state.to_candle(self.timeframe_minutes)
            ]

        candles = [
            state.to_candle(self.timeframe_minutes)
            for state in self._states.values()
        ]

        self._states.clear()

        return candles

    def reset(self) -> None:
        """Discard all currently forming candles."""
        self._states.clear()
