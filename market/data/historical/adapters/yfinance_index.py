"""Yahoo Finance adapter for historical NSE index market data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from math import isfinite
from typing import Any

import yfinance as yf

from market.candles.models import Candle
from market.data.context.sector_registry import DEFAULT_YFINANCE_INDEX_SYMBOLS
from market.data.historical.models import HistoricalDataRequest
from market.data.historical.providers import (
    HistoricalMarketDataProvider,
    HistoricalProviderRole,
)


class YFinanceHistoricalIndexMarketDataProvider(
    HistoricalMarketDataProvider
):
    """Retrieve historical NSE index OHLCV data from Yahoo Finance."""

    role = HistoricalProviderRole.RESEARCH

    REQUIRED_COLUMNS = (
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    )

    DEFAULT_PROVIDER_SYMBOLS: Mapping[str, str] = (
        DEFAULT_YFINANCE_INDEX_SYMBOLS
    )

    def __init__(
        self,
        *,
        period: str = "5d",
        auto_adjust: bool = False,
        provider_symbols: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(period, str) or not period.strip():
            raise ValueError("period must be a non-empty string")

        if not isinstance(auto_adjust, bool):
            raise TypeError("auto_adjust must be a bool")

        if provider_symbols is None:
            provider_symbols = self.DEFAULT_PROVIDER_SYMBOLS

        if not isinstance(provider_symbols, Mapping):
            raise TypeError("provider_symbols must be a mapping")

        normalized_symbols: dict[str, str] = {}

        for canonical, provider_symbol in provider_symbols.items():
            if (
                not isinstance(canonical, str)
                or not canonical.strip()
            ):
                raise ValueError(
                    "provider_symbols keys must be non-empty strings"
                )

            if (
                not isinstance(provider_symbol, str)
                or not provider_symbol.strip()
            ):
                raise ValueError(
                    "provider_symbols values must be non-empty strings"
                )

            normalized_symbols[
                canonical.strip().upper()
            ] = provider_symbol.strip()

        if not normalized_symbols:
            raise ValueError(
                "provider_symbols must not be empty"
            )

        self.period = period
        self.auto_adjust = auto_adjust
        self.provider_symbols = normalized_symbols

    def _provider_symbol(
        self,
        request: HistoricalDataRequest,
    ) -> str:
        """Map canonical NSE index symbol to Yahoo Finance symbol."""

        if request.exchange.upper() != "NSE":
            raise ValueError(
                "YFinance index adapter currently supports NSE only"
            )

        symbol = request.symbol.strip().upper()

        try:
            return self.provider_symbols[symbol]
        except KeyError as exc:
            raise ValueError(
                "unsupported NSE index symbol for YFinance: "
                f"{symbol}"
            ) from exc

    @staticmethod
    def _interval(timeframe_minutes: int) -> str:
        """Map canonical timeframe to Yahoo Finance interval."""

        intervals = {
            1: "1m",
            2: "2m",
            5: "5m",
            15: "15m",
            30: "30m",
            60: "60m",
            90: "90m",
            1440: "1d",
            10080: "1wk",
            43200: "1mo",
            129600: "3mo",
        }

        try:
            return intervals[timeframe_minutes]
        except KeyError as exc:
            raise ValueError(
                "unsupported YFinance timeframe: "
                f"{timeframe_minutes} minutes"
            ) from exc

    @staticmethod
    def _validate_timestamp(timestamp: Any) -> datetime:
        """Convert a provider timestamp and require timezone awareness."""

        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()

        if not isinstance(timestamp, datetime):
            raise ValueError(
                "Yahoo Finance returned a non-datetime timestamp"
            )

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError(
                "Yahoo Finance returned a naive timestamp"
            )

        return timestamp

    def provenance(
        self,
        request: HistoricalDataRequest,
    ) -> dict[str, str]:
        """Return deterministic Yahoo Finance source metadata."""

        if not isinstance(request, HistoricalDataRequest):
            raise TypeError(
                "request must be a HistoricalDataRequest"
            )

        return {
            "provider": "yfinance",
            "provider_symbol": self._provider_symbol(request),
            "instrument_type": "index",
            "adjustment_policy": (
                "adjusted"
                if self.auto_adjust
                else "unadjusted"
            ),
        }

    def get_bars(
        self,
        request: HistoricalDataRequest,
    ) -> Sequence[Candle]:
        """Retrieve and normalize Yahoo Finance index OHLCV data."""

        if not isinstance(request, HistoricalDataRequest):
            raise TypeError(
                "request must be a HistoricalDataRequest"
            )

        provider_symbol = self._provider_symbol(request)
        interval = self._interval(request.timeframe_minutes)

        try:
            ticker = yf.Ticker(provider_symbol)

            kwargs: dict[str, Any] = {
                "interval": interval,
                "auto_adjust": self.auto_adjust,
            }

            if request.start is not None:
                kwargs["start"] = request.start
                kwargs["end"] = request.end
            else:
                kwargs["period"] = self.period

            history = ticker.history(**kwargs)

        except Exception as exc:
            raise RuntimeError(
                "Yahoo Finance historical index request failed for "
                f"{provider_symbol}"
            ) from exc

        if history is None or history.empty:
            raise ValueError(
                "Yahoo Finance returned no historical data for "
                f"{provider_symbol}"
            )

        missing_columns = [
            column
            for column in self.REQUIRED_COLUMNS
            if column not in history.columns
        ]

        if missing_columns:
            raise ValueError(
                "Yahoo Finance returned missing required index OHLCV "
                f"columns: {missing_columns}"
            )

        bars: list[Candle] = []

        for timestamp, row in history.iterrows():
            timestamp = self._validate_timestamp(timestamp)

            try:
                values = {
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                }

                if any(
                    not isfinite(value)
                    for value in values.values()
                ):
                    raise ValueError(
                        "Yahoo Finance returned non-finite index OHLCV data"
                    )

                if values["open"] <= 0:
                    raise ValueError("open must be positive")

                if values["high"] <= 0:
                    raise ValueError("high must be positive")

                if values["low"] <= 0:
                    raise ValueError("low must be positive")

                if values["close"] <= 0:
                    raise ValueError("close must be positive")

                if values["volume"] < 0:
                    raise ValueError("volume must be non-negative")

                bars.append(
                    Candle(
                        symbol=request.symbol,
                        exchange=request.exchange,
                        timeframe_minutes=request.timeframe_minutes,
                        timestamp=timestamp,
                        **values,
                    )
                )

            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    "Yahoo Finance returned invalid index OHLCV data for "
                    f"{provider_symbol} at {timestamp}"
                ) from exc

        if not bars:
            raise ValueError(
                "Yahoo Finance returned no valid historical index bars for "
                f"{provider_symbol}"
            )

        return tuple(bars)
