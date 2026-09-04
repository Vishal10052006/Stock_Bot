"""Canonical contracts for historical market data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from market.candles.models import Candle


@dataclass(frozen=True, slots=True)
class HistoricalDataRequest:
    """Provider-independent request for historical OHLCV data."""

    symbol: str
    exchange: str = "NSE"
    timeframe_minutes: int = 5
    start: datetime | None = None
    end: datetime | None = None

    def __post_init__(self) -> None:
        """Validate the historical request contract."""

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        if not isinstance(self.exchange, str) or not self.exchange.strip():
            raise ValueError("exchange must be a non-empty string")

        if (
            not isinstance(self.timeframe_minutes, int)
            or isinstance(self.timeframe_minutes, bool)
            or self.timeframe_minutes <= 0
        ):
            raise ValueError(
                "timeframe_minutes must be a positive integer"
            )

        for name, timestamp in (
            ("start", self.start),
            ("end", self.end),
        ):
            if timestamp is None:
                continue

            if not isinstance(timestamp, datetime):
                raise TypeError(f"{name} must be a datetime or None")

            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError(
                    f"{name} must be timezone-aware"
                )

        if (
            self.start is not None
            and self.end is not None
            and self.end <= self.start
        ):
            raise ValueError("end must be after start")


@dataclass(frozen=True, slots=True)
class HistoricalDataset:
    """Validated historical candles for one instrument."""

    symbol: str
    exchange: str
    timeframe_minutes: int
    bars: tuple[Candle, ...]
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        """Validate and freeze the dataset contract."""

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        if not isinstance(self.exchange, str) or not self.exchange.strip():
            raise ValueError("exchange must be a non-empty string")

        if (
            not isinstance(self.timeframe_minutes, int)
            or isinstance(self.timeframe_minutes, bool)
            or self.timeframe_minutes <= 0
        ):
            raise ValueError(
                "timeframe_minutes must be a positive integer"
            )

        if not isinstance(self.bars, tuple):
            raise TypeError("bars must be a tuple of Candle objects")

        if not self.bars:
            raise ValueError(
                "historical dataset must contain at least one candle"
            )

        for index, bar in enumerate(self.bars):
            if not isinstance(bar, Candle):
                raise TypeError(
                    f"bars[{index}] must be a Candle"
                )

            if bar.symbol != self.symbol:
                raise ValueError(
                    "historical dataset contains a candle "
                    "for a different symbol"
                )

            if bar.exchange != self.exchange:
                raise ValueError(
                    "historical dataset contains a candle "
                    "for a different exchange"
                )

            if bar.timeframe_minutes != self.timeframe_minutes:
                raise ValueError(
                    "historical dataset contains a candle "
                    "with a different timeframe"
                )

        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")

        normalized_metadata: dict[str, str] = {}

        for key, value in self.metadata.items():
            if not isinstance(key, str):
                raise TypeError("metadata keys must be strings")

            if not isinstance(value, str):
                raise TypeError("metadata values must be strings")

            normalized_metadata[key] = value

        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(normalized_metadata),
        )
