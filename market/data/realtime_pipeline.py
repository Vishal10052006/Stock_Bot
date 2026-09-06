"""Provider-neutral real-time market-data orchestration pipeline.

The pipeline forms the controlled boundary:

    MarketFeed
        -> MarketEventValidator
        -> DataQualityMetrics
        -> CandleAggregator
        -> completed Candle

Provider-specific feeds must already normalize their native payloads into
canonical ``MarketEvent`` instances before entering this pipeline.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from market.candles.aggregator import CandleAggregator
from market.candles.models import Candle
from market.data.events import MarketEvent
from market.data.ingestion import MarketFeed
from market.data.metrics import DataQualityMetrics
from market.data.validation import MarketEventValidator


class RealtimeMarketDataPipeline:
    """Coordinate live feed validation, metrics, and candle aggregation."""

    def __init__(
        self,
        *,
        feed: MarketFeed,
        validator: MarketEventValidator,
        aggregator: CandleAggregator,
        metrics: DataQualityMetrics | None = None,
    ) -> None:
        """Create a real-time pipeline from provider-neutral components."""
        if not isinstance(feed, MarketFeed):
            raise TypeError("feed must be a MarketFeed")

        if not isinstance(validator, MarketEventValidator):
            raise TypeError(
                "validator must be a MarketEventValidator"
            )

        if not isinstance(aggregator, CandleAggregator):
            raise TypeError(
                "aggregator must be a CandleAggregator"
            )

        if metrics is not None and not isinstance(
            metrics,
            DataQualityMetrics,
        ):
            raise TypeError(
                "metrics must be a DataQualityMetrics or None"
            )

        self.feed = feed
        self.validator = validator
        self.aggregator = aggregator
        self.metrics = metrics or DataQualityMetrics()

        self._started = False

    def start(self, symbols: Iterable[str]) -> None:
        """Connect the feed and subscribe to the requested symbols."""
        if self._started:
            raise RuntimeError("pipeline is already started")

        self.feed.connect()
        try:
            self.feed.subscribe(symbols)
        except Exception:
            self.feed.disconnect()
            raise

        self._started = True

    def run(self, *, now=None) -> Iterator[Candle]:
        """Consume live events and yield completed candles.

        ``now`` is optional and exists primarily for deterministic replay and
        testing. When omitted, ``MarketEventValidator`` uses the real current
        UTC clock.

        Only events accepted by ``MarketEventValidator`` are passed to the
        candle aggregator.
        """
        if not self._started:
            raise RuntimeError("pipeline is not started")

        for event in self.feed.events():
            if not isinstance(event, MarketEvent):
                raise TypeError(
                    "market feed yielded a non-MarketEvent"
                )

            result = self.validator.validate(event, now=now)
            self.metrics.record_validation(result)

            if not result.valid:
                continue

            candle = self.aggregator.update(event)

            if candle is not None:
                yield candle

    def flush(self) -> list[Candle]:
        """Emit all currently forming candles."""
        return self.aggregator.flush()

    def stop(self) -> None:
        """Disconnect the feed and mark the pipeline stopped."""
        if not self._started:
            return

        try:
            self.feed.disconnect()
        finally:
            self._started = False

    def reset(self) -> None:
        """Reset pipeline state without reconnecting the provider."""
        self.validator.reset()
        self.aggregator.reset()
        self.metrics.reset()
