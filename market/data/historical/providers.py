"""Provider contracts for historical market data."""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import Protocol, runtime_checkable

from market.candles.models import Candle
from market.data.historical.models import HistoricalDataRequest


class HistoricalProviderRole(str, Enum):
    """Operational trust role of a historical-data provider."""

    TEST = "test"
    RESEARCH = "research"
    AUTHORITATIVE = "authoritative"


class HistoricalDataPurpose(str, Enum):
    """Intended operational use of a historical dataset."""

    RESEARCH = "research"
    AUTHORITATIVE = "authoritative"


@runtime_checkable
class HistoricalMarketDataProvider(Protocol):
    """Provider-independent contract for historical OHLCV data."""

    @property
    def role(self) -> HistoricalProviderRole:
        """Return the provider's operational trust role."""
        ...

    def get_bars(
        self,
        request: HistoricalDataRequest,
    ) -> Sequence[Candle]:
        """Retrieve historical candles for a request."""
        ...

class StaticHistoricalMarketDataProvider:
    """
    Deterministic historical provider for contract tests.

    This provider performs no network access and no dataset repair.
    """

    role = HistoricalProviderRole.TEST

    def __init__(self, bars: Sequence[Candle]) -> None:
        self._bars = tuple(bars)

    def get_bars(
        self,
        request: HistoricalDataRequest,
    ) -> Sequence[Candle]:
        """Return the configured candles."""

        if not isinstance(request, HistoricalDataRequest):
            raise TypeError(
                "request must be a HistoricalDataRequest"
            )

        for bar in self._bars:
            if bar.symbol != request.symbol:
                raise ValueError(
                    "configured candle belongs to a different symbol"
                )

            if bar.exchange != request.exchange:
                raise ValueError(
                    "configured candle belongs to a different exchange"
                )

            if bar.timeframe_minutes != request.timeframe_minutes:
                raise ValueError(
                    "configured candle has a different timeframe"
                )

        return self._bars
