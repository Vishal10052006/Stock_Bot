"""M20 real-market Upstox shadow runtime.

This runtime intentionally stops at market-data ingestion and candle
formation. It never imports, constructs, or calls a broker execution adapter.
That separation is the primary M20 live-order safety boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator

from market.candles.aggregator import CandleAggregator
from market.candles.models import Candle
from market.data.ingestion.providers.upstox.config import UpstoxFeedConfig
from market.data.ingestion.providers.upstox.feed import UpstoxMarketFeed
from market.data.ingestion.providers.upstox.generated import MarketDataFeedV3_pb2
from market.data.ingestion.providers.upstox.instrument_mapper import (
    UpstoxInstrumentMapper,
)
from market.data.metrics import DataQualityMetrics
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from market.data.validation import MarketEventValidator

from .config import ShadowRuntimeConfig
from .health import ShadowHealth
from .mode import RuntimeSafety, load_runtime_safety
from .shadow_candles import ShadowCandleBuffer


@dataclass(slots=True)
class ShadowRuntime:
    """Compose the existing Upstox feed into the canonical data pipeline."""

    config: ShadowRuntimeConfig
    safety: RuntimeSafety
    feed: UpstoxMarketFeed
    pipeline: RealtimeMarketDataPipeline
    metrics: DataQualityMetrics
    health: ShadowHealth
    candle_buffer: ShadowCandleBuffer = field(default_factory=ShadowCandleBuffer)

    @classmethod
    def from_environment(
        cls,
        *,
        symbols: tuple[str, ...] | None = None,
    ) -> "ShadowRuntime":
        """Construct a fail-closed M20 runtime from environment settings."""
        safety = load_runtime_safety()

        mapper = UpstoxInstrumentMapper.from_env()
        configured_symbols = symbols or mapper.symbols()
        config = ShadowRuntimeConfig.from_env(configured_symbols)

        metrics = DataQualityMetrics()
        validator = MarketEventValidator(
            max_event_age_seconds=config.validator_max_event_age_seconds,
            max_future_skew_seconds=config.validator_max_future_skew_seconds,
        )
        aggregator = CandleAggregator(
            timeframe_minutes=config.timeframe_minutes,
        )

        feed = UpstoxMarketFeed(
            UpstoxFeedConfig.from_env(),
            mapper,
            protobuf_module=MarketDataFeedV3_pb2,
            # The provider adapter stays provider-specific; the canonical
            # pipeline owns validation and metrics for one authoritative pass.
            event_validator=None,
            metrics=None,
        )

        pipeline = RealtimeMarketDataPipeline(
            feed=feed,
            validator=validator,
            aggregator=aggregator,
            metrics=metrics,
        )

        return cls(
            config=config,
            safety=safety,
            feed=feed,
            pipeline=pipeline,
            metrics=metrics,
            health=ShadowHealth(
                started_at=datetime.now(timezone.utc),
            ),
            candle_buffer=ShadowCandleBuffer(),
        )

    def start(self) -> None:
        """Connect to Upstox and subscribe to configured instruments."""
        self.safety.assert_safe()
        self.pipeline.start(self.config.symbols)

    def candles(self) -> Iterator[Candle]:
        """Yield completed shadow candles."""
        self.safety.assert_safe()
        for candle in self.pipeline.run():
            self.health.record_candle()
            self.candle_buffer.append(candle)
            yield candle

    def stop(self) -> None:
        """Disconnect without invoking any order system."""
        self.pipeline.stop()

    def evidence(self) -> dict[str, object]:
        """Return current no-order operational evidence."""
        self.safety.assert_safe()
        return self.health.snapshot(self.metrics.snapshot())
