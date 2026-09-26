"""M20 runtime configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _positive_float(name: str, default: str) -> float:
    """Read a positive floating-point environment setting."""
    raw = os.getenv(name, default).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def _positive_int(name: str, default: str) -> int:
    """Read a positive integer environment setting."""
    raw = os.getenv(name, default).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


@dataclass(frozen=True, slots=True)
class ShadowRuntimeConfig:
    """Configuration for a real-market, no-order shadow session."""

    symbols: tuple[str, ...]
    validator_max_event_age_seconds: float = 5.0
    validator_max_future_skew_seconds: float = 2.0
    timeframe_minutes: int = 5

    @classmethod
    def from_env(cls, symbols: tuple[str, ...]) -> "ShadowRuntimeConfig":
        """Build validated runtime settings from environment variables."""
        normalized = tuple(
            sorted(
                {
                    symbol.strip().upper()
                    for symbol in symbols
                    if symbol.strip()
                }
            )
        )
        if not normalized:
            raise ValueError("at least one shadow symbol is required")

        return cls(
            symbols=normalized,
            validator_max_event_age_seconds=_positive_float(
                "STOCK_BOT_EVENT_MAX_AGE_SECONDS",
                "5",
            ),
            validator_max_future_skew_seconds=_positive_float(
                "STOCK_BOT_EVENT_MAX_FUTURE_SKEW_SECONDS",
                "2",
            ),
            timeframe_minutes=_positive_int(
                "STOCK_BOT_CANDLE_TIMEFRAME_MINUTES",
                "5",
            ),
        )
