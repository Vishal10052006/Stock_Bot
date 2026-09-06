"""Provider contracts for historical market data."""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable

from market.candles.models import Candle
from market.data.historical.models import HistoricalDataRequest
from market.data.historical.security_lineage import (
    SecurityLineage,
    SecurityLineageObservation,
)


class HistoricalProviderRole(str, Enum):
    """Operational trust role of a historical-data provider."""

    TEST = "test"
    RESEARCH = "research"
    CANONICAL = "canonical"


class HistoricalDataPurpose(str, Enum):
    """Intended operational use of a historical dataset."""

    RESEARCH = "research"
    CANONICAL = "canonical"


@runtime_checkable
class HistoricalProviderProvenance(Protocol):
    """Provider-neutral provenance information for a historical request."""

    def provenance(
        self,
        request: HistoricalDataRequest,
    ) -> Mapping[str, str]:
        """Return deterministic source-identification metadata."""
        ...


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


@runtime_checkable
class InstrumentLifecycleProvider(Protocol):
    """Provider-neutral source of historical instrument lifecycle data."""

    def get_status_timeline(
        self,
        symbol: str,
    ) -> "InstrumentStatusTimeline":
        """Return the point-in-time status timeline for an instrument."""
        ...


@runtime_checkable
class InstrumentUniverseProvider(Protocol):
    """Provider-neutral source of historical instrument universe membership."""

    def get_membership_timeline(
        self,
        symbol: str,
        exchange: str,
    ) -> "UniverseMembershipTimeline":
        """Return point-in-time universe membership for an instrument."""
        ...


@runtime_checkable
class InstrumentSymbolHistoryProvider(Protocol):
    """Provider-neutral source of historical exchange-symbol mappings."""

    def get_symbol_timeline(
        self,
        isin: str,
        exchange: str,
    ) -> "InstrumentSymbolTimeline":
        """Return the point-in-time symbol history for a security."""
        ...

@runtime_checkable
class SecurityLineageProvider(Protocol):
    """Provider-neutral source of verified security lineage."""

    def get_security_lineage(
        self,
        observation: "SecurityLineageObservation",
    ) -> "SecurityLineage":
        """Return the verified lineage containing an instrument observation."""
        ...
