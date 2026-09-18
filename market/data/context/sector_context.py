"""Utilities for building a multi-index sector context frame."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import pandas as pd

from market.data.context.market_context import build_context_returns
from market.data.historical.models import HistoricalDataRequest
from market.data.historical.providers import HistoricalMarketDataProvider


def candles_to_context_frame(
    bars: Sequence[object],
) -> pd.DataFrame:
    """Convert canonical candle-like objects into sector context rows."""
    if not bars:
        raise ValueError("bars must not be empty")

    rows = []
    for bar in bars:
        rows.append(
            {
                "timestamp": bar.timestamp,
                "sector_index_symbol": str(bar.symbol).strip().upper(),
                "close": float(bar.close),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("bars produced an empty context frame")

    if not isinstance(frame["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("sector candle timestamps must be timezone-aware")

    return frame.sort_values(
        ["sector_index_symbol", "timestamp"],
        kind="stable",
    ).reset_index(drop=True)


def build_sector_context(
    provider: HistoricalMarketDataProvider,
    *,
    symbols: Sequence[str],
    timeframe_minutes: int,
    start: datetime | None = None,
    end: datetime | None = None,
) -> pd.DataFrame:
    """Fetch multiple sector indices and build causal context features.

    This function does not infer stock-to-sector membership. That mapping
    remains a separate point-in-time input to enrich_market_sector_context.
    """
    if not isinstance(provider, HistoricalMarketDataProvider):
        raise TypeError("provider must be a HistoricalMarketDataProvider")
    if not symbols:
        raise ValueError("symbols must not be empty")

    normalized = tuple(symbol.strip().upper() for symbol in symbols)
    if any(not symbol for symbol in normalized):
        raise ValueError("symbols must contain non-empty strings")
    if len(set(normalized)) != len(normalized):
        raise ValueError("symbols must be unique")
    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")

    frames: list[pd.DataFrame] = []
    for symbol in normalized:
        request = HistoricalDataRequest(
            symbol=symbol,
            exchange="NSE",
            timeframe_minutes=timeframe_minutes,
            start=start,
            end=end,
        )
        bars = provider.get_bars(request)
        frames.append(candles_to_context_frame(bars))

    combined = pd.concat(frames, ignore_index=True)
    return build_context_returns(
        combined,
        price_column="close",
        key_column="sector_index_symbol",
    )
