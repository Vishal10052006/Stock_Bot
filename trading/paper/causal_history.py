"""Causal live-history accumulator for canonical paper integration.

Live Analysis needs enough prior candles to construct rolling indicators.
This helper keeps only information at or before the current decision time and
returns a stable DataFrame copy for the canonical Market -> Analysis path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from market.candles.models import Candle


@dataclass
class CausalCandleHistory:
    """Accumulate completed candles for one symbol without lookahead."""

    symbol: str
    _rows: list[dict[str, object]] = field(default_factory=list)

    def append(self, candle: Candle) -> None:
        """Append one completed candle after strict identity validation."""
        if not isinstance(candle, Candle):
            raise TypeError("candle must be a Candle")

        symbol = candle.symbol.strip().upper()
        expected = self.symbol.strip().upper()
        if symbol != expected:
            raise ValueError(
                f"history symbol mismatch: expected {expected}, received {symbol}"
            )

        timestamp = pd.Timestamp(candle.timestamp)
        if self._rows:
            previous = pd.Timestamp(self._rows[-1]["timestamp"])
            if timestamp <= previous:
                raise ValueError(
                    "candles must be appended in strictly increasing time order"
                )

        self._rows.append(
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "volume": float(candle.volume),
            }
        )

    def frame(self) -> pd.DataFrame:
        """Return a defensive, chronologically sorted history snapshot."""
        return pd.DataFrame(self._rows).copy()

    def snapshot_at(self, cutoff: pd.Timestamp) -> pd.DataFrame:
        """Return only observations available at the supplied cutoff."""
        cutoff = pd.Timestamp(cutoff)
        if cutoff.tzinfo is None:
            raise ValueError("cutoff must be timezone-aware")

        frame = self.frame()
        if frame.empty:
            return frame

        return frame.loc[
            pd.to_datetime(frame["timestamp"], utc=True) <= cutoff
        ].sort_values("timestamp", kind="stable").reset_index(drop=True)


__all__ = ["CausalCandleHistory"]
