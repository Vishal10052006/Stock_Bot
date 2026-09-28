"""Bounded in-memory history for M20 shadow candles.

This component is deliberately provider- and strategy-neutral. It stores only
completed canonical Candle objects so later M20 stages can consume a causal
rolling window without inventing missing observations or touching broker
execution.
"""

from __future__ import annotations

from collections import deque

import pandas as pd

from market.candles.models import Candle


class ShadowCandleBuffer:
    """Keep a bounded chronological candle history per symbol."""

    def __init__(self, *, max_candles_per_symbol: int = 250) -> None:
        if max_candles_per_symbol <= 0:
            raise ValueError("max_candles_per_symbol must be positive")
        self.max_candles_per_symbol = max_candles_per_symbol
        self._buffers: dict[str, deque[Candle]] = {}

    def append(self, candle: Candle) -> None:
        """Append one completed candle while enforcing chronological order."""
        if not isinstance(candle, Candle):
            raise TypeError("candle must be a Candle")

        symbol = candle.symbol.strip().upper()
        buffer = self._buffers.setdefault(
            symbol,
            deque(maxlen=self.max_candles_per_symbol),
        )

        if buffer and candle.timestamp < buffer[-1].timestamp:
            raise ValueError("candle timestamps must be chronological")

        if buffer and candle.timestamp == buffer[-1].timestamp:
            raise ValueError("duplicate candle timestamp for symbol")

        buffer.append(candle)

    def frame(self, symbol: str) -> pd.DataFrame:
        """Return the causal OHLCV history for one symbol."""
        normalized = symbol.strip().upper()
        candles = list(self._buffers.get(normalized, ()))

        return pd.DataFrame(
            [
                {
                    "timestamp": candle.timestamp,
                    "symbol": candle.symbol,
                    "exchange": candle.exchange,
                    "timeframe_minutes": candle.timeframe_minutes,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                }
                for candle in candles
            ],
            columns=[
                "timestamp",
                "symbol",
                "exchange",
                "timeframe_minutes",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        )

    def count(self, symbol: str) -> int:
        """Return the number of retained candles for one symbol."""
        return len(self._buffers.get(symbol.strip().upper(), ()))

    def symbols(self) -> tuple[str, ...]:
        """Return symbols currently represented in the buffer."""
        return tuple(sorted(self._buffers))

    def reset(self) -> None:
        """Discard all retained shadow candle history."""
        self._buffers.clear()
