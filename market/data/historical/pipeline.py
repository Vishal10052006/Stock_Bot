"""Orchestration for historical market-data ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

from market.candles.models import Candle
from market.data.historical.calendar import MarketSessionCalendar
from market.data.historical.models import (
    HistoricalDataRequest,
    HistoricalDataset,
)
from market.data.historical.nse_calendar import NSETradingCalendar
from market.data.historical.providers import (
    HistoricalDataPurpose,
    HistoricalMarketDataProvider,
    HistoricalProviderRole,
)
from market.data.historical.storage import HistoricalDatasetStore
from market.data.historical.validation import (
    DatasetValidationResult,
    HistoricalDatasetValidator,
)


@dataclass(frozen=True, slots=True)
class HistoricalPipelineResult:
    """Result of a historical ingestion run."""

    dataset: HistoricalDataset
    validation: DatasetValidationResult


class HistoricalMarketDataPipeline:
    """Fetch, validate, construct, and optionally persist historical data."""

    def __init__(
        self,
        provider: HistoricalMarketDataProvider,
        validator: HistoricalDatasetValidator | None = None,
        store: HistoricalDatasetStore | None = None,
        calendar: MarketSessionCalendar | None = None,
        require_complete_sessions: bool = True,
        as_of: datetime | None = None,
        purpose: HistoricalDataPurpose = HistoricalDataPurpose.RESEARCH,
    ) -> None:
        self._provider = provider
        self._validator = (
            validator
            if validator is not None
            else HistoricalDatasetValidator()
        )
        self._store = store
        self._calendar = (
            calendar
            if calendar is not None
            else NSETradingCalendar()
        )
        self._require_complete_sessions = require_complete_sessions
        self._as_of = as_of
        self._purpose = purpose

    def ingest(
        self,
        request: HistoricalDataRequest,
        destination: str | Path | None = None,
    ) -> HistoricalPipelineResult:
        """
        Execute one historical-data ingestion.

        Validation always occurs before dataset construction and storage.
        Invalid data is never persisted.
        """

        if not isinstance(request, HistoricalDataRequest):
            raise TypeError(
                "request must be a HistoricalDataRequest"
            )

        if destination is not None and self._store is None:
            raise ValueError(
                "a storage implementation is required when "
                "destination is provided"
            )

        if (
            self._purpose == HistoricalDataPurpose.AUTHORITATIVE
            and self._provider.role != HistoricalProviderRole.AUTHORITATIVE
        ):
            raise ValueError(
                "authoritative historical ingestion requires "
                "an authoritative provider; "
                f"provider role is {self._provider.role.value}"
            )

        bars: Sequence[Candle] = self._provider.get_bars(request)

        if not isinstance(bars, Sequence):
            raise TypeError(
                "historical provider must return a Sequence of Candle objects"
            )

        validation = self._validator.validate(
            bars,
            expected_interval=timedelta(
                minutes=request.timeframe_minutes
            ),
            calendar=self._calendar,
            require_complete_sessions=self._require_complete_sessions,
            as_of=self._as_of,
        )

        if not validation.valid:
            raise ValueError(
                "historical dataset validation failed: "
                + "; ".join(validation.errors)
            )

        dataset = HistoricalDataset(
            symbol=request.symbol,
            exchange=request.exchange,
            timeframe_minutes=request.timeframe_minutes,
            bars=tuple(bars),
            metadata={
                "provider": type(self._provider).__name__,
                "pipeline_version": "1",
            },
        )

        if destination is not None:
            self._store.save(
                dataset,
                destination,
            )

        return HistoricalPipelineResult(
            dataset=dataset,
            validation=validation,
        )
