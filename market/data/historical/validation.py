"""Validation for historical market-data datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence

from market.candles.models import Candle
from market.data.historical.calendar import MarketSessionCalendar


@dataclass(frozen=True, slots=True)
class DatasetValidationResult:
    """Result of historical dataset validation."""

    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        """Ensure validation state is internally consistent."""

        if self.valid and self.errors:
            raise ValueError(
                "validation result cannot be valid when errors exist"
            )


class HistoricalDatasetValidator:
    """Validate a sequence of canonical historical candles."""

    def validate(
        self,
        bars: Sequence[Candle],
        expected_interval: timedelta | None = None,
        calendar: MarketSessionCalendar | None = None,
        require_complete_sessions: bool = False,
        as_of: datetime | None = None,
    ) -> DatasetValidationResult:
        """
        Validate historical candles without modifying them.

        Args:
            bars:
                Historical Candle observations.
            expected_interval:
                Expected candle interval, such as five minutes.
            calendar:
                Optional exchange trading-session calendar.
            require_complete_sessions:
                When True, every completed trading session represented
                by the dataset must contain every expected candle-start
                timestamp. This is intended for historical backfills.
            as_of:
                Optional timezone-aware reference timestamp used to
                determine whether the final represented session is
                currently open. If it falls inside a represented
                trading session, that session may be partial.
        """

        errors: list[str] = []
        warnings: list[str] = []

        if as_of is not None:
            if (
                as_of.tzinfo is None
                or as_of.utcoffset() is None
            ):
                return DatasetValidationResult(
                    valid=False,
                    errors=("as_of must be timezone-aware",),
                    warnings=tuple(warnings),
                )

            if calendar is not None:
                as_of = as_of.astimezone(
                    calendar.timezone
                )

        if not bars:
            return DatasetValidationResult(
                valid=False,
                errors=("dataset must contain at least one candle",),
                warnings=(),
            )

        # --------------------------------------------------------------
        # 1. Canonical object validation
        # --------------------------------------------------------------

        for index, bar in enumerate(bars):
            if not isinstance(bar, Candle):
                errors.append(
                    f"bar at index {index} is not a Candle"
                )

        if errors:
            return DatasetValidationResult(
                valid=False,
                errors=tuple(errors),
                warnings=tuple(warnings),
            )

        # --------------------------------------------------------------
        # 1A. as_of temporal boundary
        # --------------------------------------------------------------

        if as_of is not None:
            for index, bar in enumerate(bars):
                bar_timestamp = bar.timestamp

                if calendar is not None:
                    bar_timestamp = bar_timestamp.astimezone(
                        calendar.timezone
                    )

                if bar_timestamp > as_of:
                    errors.append(
                        f"bar at index {index} occurs after as_of: "
                        f"{bar.timestamp.isoformat()} > "
                        f"{as_of.isoformat()}"
                    )

        if errors:
            return DatasetValidationResult(
                valid=False,
                errors=tuple(errors),
                warnings=tuple(warnings),
            )

        # --------------------------------------------------------------
        # 2. Dataset identity
        # --------------------------------------------------------------

        symbols = {bar.symbol for bar in bars}

        if len(symbols) != 1:
            errors.append(
                "dataset contains multiple symbols"
            )

        exchanges = {bar.exchange for bar in bars}

        if len(exchanges) != 1:
            errors.append(
                "dataset contains multiple exchanges"
            )

        timeframes = {
            bar.timeframe_minutes
            for bar in bars
        }

        if len(timeframes) != 1:
            errors.append(
                "dataset contains multiple timeframes"
            )

        # --------------------------------------------------------------
        # 3. Timestamp validation
        # --------------------------------------------------------------

        timestamps = [
            bar.timestamp
            for bar in bars
        ]

        first_timestamp = timestamps[0]

        if (
            first_timestamp.tzinfo is None
            or first_timestamp.utcoffset() is None
        ):
            errors.append(
                "first timestamp must be timezone-aware"
            )

        for index, timestamp in enumerate(
            timestamps[1:],
            start=1,
        ):
            if (
                timestamp.tzinfo is None
                or timestamp.utcoffset() is None
            ):
                errors.append(
                    f"timestamp at index {index} "
                    "must be timezone-aware"
                )
                continue

            if timestamp.utcoffset() != first_timestamp.utcoffset():
                errors.append(
                    "dataset contains inconsistent timestamp "
                    f"offsets at index {index}"
                )

        # --------------------------------------------------------------
        # 4. Duplicate timestamps
        # --------------------------------------------------------------

        seen_timestamps: set = set()

        for index, timestamp in enumerate(timestamps):
            if timestamp in seen_timestamps:
                errors.append(
                    "duplicate timestamp at index "
                    f"{index}: {timestamp.isoformat()}"
                )
            else:
                seen_timestamps.add(timestamp)

        # --------------------------------------------------------------
        # 5. Chronological ordering
        # --------------------------------------------------------------

        for index in range(1, len(timestamps)):
            if timestamps[index] <= timestamps[index - 1]:
                errors.append(
                    "timestamps are not strictly increasing "
                    f"between indexes {index - 1} and {index}"
                )

        # --------------------------------------------------------------
        # 6. Expected interval configuration
        # --------------------------------------------------------------

        if expected_interval is not None:
            if expected_interval <= timedelta(0):
                errors.append(
                    "expected_interval must be greater than zero"
                )

        # --------------------------------------------------------------
        # 7. Exchange calendar validation
        # --------------------------------------------------------------

        local_timestamps = list(timestamps)

        if calendar is not None:
            local_timestamps = []

            for index, timestamp in enumerate(timestamps):
                if (
                    timestamp.tzinfo is None
                    or timestamp.utcoffset() is None
                ):
                    local_timestamps.append(timestamp)
                    continue

                local_timestamp = timestamp.astimezone(
                    calendar.timezone
                )

                local_timestamps.append(local_timestamp)

                session_date = local_timestamp.date()

                if not calendar.is_trading_day(session_date):
                    errors.append(
                        "timestamp falls on a non-trading day "
                        f"at index {index}: "
                        f"{local_timestamp.isoformat()}"
                    )
                    continue

                session = calendar.get_session(session_date)

                if session is None:
                    errors.append(
                        "trading calendar returned no session for "
                        f"trading date at index {index}: "
                        f"{session_date.isoformat()}"
                    )
                    continue

                if not session.contains(local_timestamp):
                    errors.append(
                        "timestamp falls outside trading session "
                        f"at index {index}: "
                        f"{local_timestamp.isoformat()}"
                    )

        # --------------------------------------------------------------
        # 8. Interval / missing-candle analysis
        # --------------------------------------------------------------

        if (
            expected_interval is not None
            and expected_interval > timedelta(0)
        ):
            for index in range(1, len(timestamps)):
                previous = local_timestamps[index - 1]
                current = local_timestamps[index]

                actual_interval = current - previous

                if actual_interval == expected_interval:
                    continue

                if calendar is not None:
                    previous_date = previous.date()
                    current_date = current.date()

                    if previous_date != current_date:
                        missing_trading_dates: list[date] = []

                        candidate_date = (
                            previous_date + timedelta(days=1)
                        )

                        while candidate_date < current_date:
                            if (
                                calendar.is_trading_day(
                                    candidate_date
                                )
                                and calendar.get_session(
                                    candidate_date
                                ) is not None
                            ):
                                missing_trading_dates.append(
                                    candidate_date
                                )

                            candidate_date += timedelta(days=1)

                        if missing_trading_dates:
                            warnings.append(
                                "missing trading-session data between "
                                f"indexes {index - 1} and {index}: "
                                f"{[d.isoformat() for d in missing_trading_dates]}"
                            )

                        continue

                warnings.append(
                    "unexpected timestamp interval between "
                    f"indexes {index - 1} and {index}: "
                    f"expected {expected_interval}, "
                    f"received {actual_interval}"
                )

        # --------------------------------------------------------------
        # 9. Complete-session validation
        # --------------------------------------------------------------

        if (
            require_complete_sessions
            and calendar is not None
            and expected_interval is not None
            and expected_interval > timedelta(0)
            and not errors
        ):
            session_dates = sorted(
                {
                    timestamp.astimezone(
                        calendar.timezone
                    ).date()
                    for timestamp in timestamps
                }
            )

            actual_by_date: dict[date, set] = {}

            for timestamp in local_timestamps:
                actual_by_date.setdefault(
                    timestamp.date(),
                    set(),
                ).add(timestamp)

            for session_date in session_dates:
                session = calendar.get_session(session_date)

                # Pending/undefined special sessions cannot safely
                # have completeness inferred.
                if session is None:
                    continue

                # When an explicit as_of timestamp falls inside this
                # represented session, the session is currently open.
                # Its tail is therefore allowed to be incomplete.
                if as_of is not None:
                    session_open = datetime.combine(
                        session_date,
                        session.open_time,
                        tzinfo=calendar.timezone,
                    )

                    session_close = datetime.combine(
                        session_date,
                        session.close_time,
                        tzinfo=calendar.timezone,
                    )

                    if session_open <= as_of < session_close:
                        continue

                expected = set(
                    calendar.expected_timestamps(
                        session_date,
                        expected_interval,
                    )
                )

                actual = actual_by_date.get(
                    session_date,
                    set(),
                )

                missing = sorted(expected - actual)

                if missing:
                    errors.append(
                        "incomplete trading session "
                        f"{session_date.isoformat()}; "
                        f"missing {len(missing)} expected candle(s): "
                        f"{[timestamp.isoformat() for timestamp in missing]}"
                    )

        return DatasetValidationResult(
            valid=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
