"""M20 real-market Upstox shadow runtime.

This runtime intentionally stops at market-data ingestion and candle
formation. It never imports, constructs, or calls a broker execution adapter.
That separation is the primary M20 live-order safety boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator
import os

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
from .shadow_session import ShadowSessionJournal


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
    session_journal: ShadowSessionJournal | None = None
    _session_started: bool = False
    _session_stopped: bool = False

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
            session_journal=(
                ShadowSessionJournal.open(
                    os.getenv("STOCK_BOT_SHADOW_JOURNAL", "data/shadow/m20_shadow.jsonl"),
                    session_id=os.getenv("STOCK_BOT_SHADOW_SESSION_ID") or None,
                )
                if os.getenv("STOCK_BOT_SHADOW_JOURNAL", "").strip()
                else None
            ),
        )

    def start(self) -> None:
        """Connect to Upstox and subscribe to configured instruments."""
        self.safety.assert_safe()
        if self.session_journal is not None and not self._session_started:
            self.session_journal.start(symbols=self.config.symbols)
            self._session_started = True
        self.pipeline.start(self.config.symbols)

    def candles(self) -> Iterator[Candle]:
        """Yield completed shadow candles."""
        self.safety.assert_safe()
        for candle in self.pipeline.run():
            self.health.record_candle()
            self.candle_buffer.append(candle)
            if self.session_journal is not None:
                self.session_journal.candle(
                    symbol=candle.symbol,
                    timestamp=candle.timestamp,
                )
            yield candle

    def stop(self) -> None:
        """Disconnect without invoking any order system."""
        self.pipeline.stop()
        if self.session_journal is not None and not self._session_stopped:
            self.session_journal.stop(evidence=self.evidence())
            self._session_stopped = True

    def evidence(self) -> dict[str, object]:
        """Return current no-order operational evidence."""
        self.safety.assert_safe()
        evidence = self.health.snapshot(self.metrics.snapshot())
        evidence["shadow_candle_buffer_symbols"] = list(self.candle_buffer.symbols())
        evidence["shadow_candle_buffer_counts"] = {
            symbol: self.candle_buffer.count(symbol)
            for symbol in self.candle_buffer.symbols()
        }
        if self.session_journal is not None:
            evidence["session_journal"] = self.session_journal.evidence()
        else:
            evidence["session_journal"] = None
        return evidence
