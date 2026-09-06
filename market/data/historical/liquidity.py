"""Point-in-time liquidity measurements for historical OHLCV data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from statistics import mean
from typing import Sequence

from market.candles.models import Candle


@dataclass(frozen=True, slots=True)
class DailyLiquidity:
    """Liquidity measurement for one completed trading session."""

    session_date: date
    observation_count: int
    traded_value: float
    source: str

    def __post_init__(self) -> None:
        """Validate the daily liquidity observation."""
        if isinstance(self.session_date, datetime):
            raise TypeError("session_date must be a date")

        if not isinstance(self.session_date, date):
            raise TypeError("session_date must be a date")

        if self.observation_count <= 0:
            raise ValueError(
                "observation_count must be greater than zero"
            )

        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must not be empty")

        object.__setattr__(
            self,
            "source",
            self.source.strip(),
        )

        if not isfinite(self.traded_value):
            raise ValueError(
                "traded_value must be finite"
            )

        if self.traded_value < 0:
            raise ValueError(
                "traded_value must be non-negative"
            )


@dataclass(frozen=True, slots=True)
class LiquidityMeasurement:
    """Point-in-time rolling liquidity measurement."""

    as_of: date
    lookback_sessions: int
    completed_sessions: tuple[DailyLiquidity, ...]
    average_traded_value: float | None

    def __post_init__(self) -> None:
        """Validate the rolling liquidity measurement."""
        if isinstance(self.as_of, datetime):
            raise TypeError("as_of must be a date")

        if not isinstance(self.as_of, date):
            raise TypeError("as_of must be a date")

        if self.lookback_sessions <= 0:
            raise ValueError(
                "lookback_sessions must be greater than zero"
            )

        if len(self.completed_sessions) > self.lookback_sessions:
            raise ValueError(
                "completed_sessions cannot exceed lookback_sessions"
            )

        dates = tuple(
            session.session_date
            for session in self.completed_sessions
        )

        if dates != tuple(sorted(dates)):
            raise ValueError(
                "completed_sessions must be chronological"
            )

        if len(dates) != len(set(dates)):
            raise ValueError(
                "completed_sessions must not contain duplicate dates"
            )

        if any(session.session_date >= self.as_of for session in self.completed_sessions):
            raise ValueError(
                "completed_sessions must be before as_of"
            )

        if self.average_traded_value is not None:
            if not isfinite(self.average_traded_value):
                raise ValueError(
                    "average_traded_value must be finite"
                )

            if self.average_traded_value < 0:
                raise ValueError(
                    "average_traded_value must be non-negative"
                )


def daily_liquidity(
    candles: Sequence[Candle],
    *,
    session_date: date,
    expected_candles: int = 75,
) -> DailyLiquidity:
    """Calculate traded value for one complete session.

    The function rejects incomplete sessions, mixed instruments, duplicate
    timestamps, and invalid expected-candle counts. Upstream historical
    validation remains responsible for exchange-calendar completeness.
    """
    if isinstance(session_date, datetime):
        raise TypeError("session_date must be a date")

    if not isinstance(session_date, date):
        raise TypeError("session_date must be a date")

    if expected_candles <= 0:
        raise ValueError(
            "expected_candles must be greater than zero"
        )

    session_candles = [
        candle
        for candle in candles
        if candle.timestamp.date() == session_date
    ]

    if len(session_candles) != expected_candles:
        raise ValueError(
            "liquidity requires a complete session: "
            f"expected {expected_candles} candles, "
            f"received {len(session_candles)}"
        )

    identities = {
        (
            candle.symbol,
            candle.exchange,
            candle.timeframe_minutes,
        )
        for candle in session_candles
    }

    if len(identities) != 1:
        raise ValueError(
            "liquidity session must contain exactly one "
            "symbol, exchange, and timeframe"
        )

    timestamps = tuple(
        candle.timestamp
        for candle in session_candles
    )

    if len(timestamps) != len(set(timestamps)):
        raise ValueError(
            "liquidity session must not contain duplicate timestamps"
        )

    if timestamps != tuple(sorted(timestamps)):
        raise ValueError(
            "liquidity session must be chronological"
        )

    traded_value = 0.0

    for candle in session_candles:
        typical_price = (
            candle.high
            + candle.low
            + candle.close
        ) / 3.0

        traded_value += typical_price * candle.volume

    return DailyLiquidity(
        session_date=session_date,
        observation_count=len(session_candles),
        traded_value=traded_value,
        source="5m_ohlcv",
    )


def daily_liquidity_from_nse(
    bar: "NSESecurityDailyBar",
) -> DailyLiquidity:
    """Convert an NSE security-wise daily bar into session liquidity.

    NSE provides the exchange-reported traded value directly, so this
    function preserves that value rather than estimating it from OHLCV.
    """
    from market.data.historical.nse_security import NSESecurityDailyBar

    if not isinstance(bar, NSESecurityDailyBar):
        raise TypeError(
            "bar must be an NSESecurityDailyBar"
        )

    return DailyLiquidity(
        session_date=bar.session_date,
        observation_count=1,
        traded_value=bar.traded_value,
        source="nse_security_daily",
    )


def rolling_liquidity(
    sessions: Sequence[DailyLiquidity],
    *,
    as_of: date,
    lookback_sessions: int = 20,
) -> LiquidityMeasurement:
    """Calculate liquidity using only sessions before ``as_of``.

    The session on ``as_of`` is excluded deliberately. This prevents the
    liquidity decision from using information generated during the current
    decision date.
    """
    if isinstance(as_of, datetime):
        raise TypeError("as_of must be a date")

    if not isinstance(as_of, date):
        raise TypeError("as_of must be a date")

    if lookback_sessions <= 0:
        raise ValueError(
            "lookback_sessions must be greater than zero"
        )

    dates = tuple(
        session.session_date
        for session in sessions
    )

    if dates != tuple(sorted(dates)):
        raise ValueError(
            "sessions must be chronological"
        )

    if len(dates) != len(set(dates)):
        raise ValueError(
            "sessions must not contain duplicate dates"
        )

    eligible = tuple(
        session
        for session in sessions
        if session.session_date < as_of
    )

    selected = eligible[-lookback_sessions:]

    return LiquidityMeasurement(
        as_of=as_of,
        lookback_sessions=lookback_sessions,
        completed_sessions=selected,
        average_traded_value=(
            mean(
                session.traded_value
                for session in selected
            )
            if selected
            else None
        ),
    )


@dataclass(frozen=True, slots=True)
class LiquidityPolicy:
    """Versioned point-in-time liquidity eligibility policy."""

    version: str
    lookback_sessions: int
    minimum_completed_sessions: int
    minimum_average_traded_value: float

    def __post_init__(self) -> None:
        """Validate the liquidity-policy parameters."""
        if not self.version.strip():
            raise ValueError("version must not be empty")

        if self.lookback_sessions <= 0:
            raise ValueError(
                "lookback_sessions must be greater than zero"
            )

        if self.minimum_completed_sessions <= 0:
            raise ValueError(
                "minimum_completed_sessions must be greater than zero"
            )

        if self.minimum_completed_sessions > self.lookback_sessions:
            raise ValueError(
                "minimum_completed_sessions cannot exceed "
                "lookback_sessions"
            )

        if not isfinite(self.minimum_average_traded_value):
            raise ValueError(
                "minimum_average_traded_value must be finite"
            )

        if self.minimum_average_traded_value < 0:
            raise ValueError(
                "minimum_average_traded_value must be non-negative"
            )

        object.__setattr__(self, "version", self.version.strip())


def is_liquid(
    measurement: LiquidityMeasurement,
    policy: LiquidityPolicy,
) -> bool:
    """Return whether a point-in-time measurement satisfies the policy."""
    if measurement.lookback_sessions != policy.lookback_sessions:
        raise ValueError(
            "measurement lookback does not match liquidity policy"
        )

    if (
        len(measurement.completed_sessions)
        < policy.minimum_completed_sessions
    ):
        return False

    if measurement.average_traded_value is None:
        return False

    return (
        measurement.average_traded_value
        >= policy.minimum_average_traded_value
    )
