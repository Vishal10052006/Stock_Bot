"""Real-market model inference runtime.

This module consumes the existing Upstox live feed, warms the causal feature
pipeline with Upstox historical candles, and emits one Phase-9 prediction after
each completed target-symbol 5-minute candle. It never places or authorizes
orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from market.bot.orchestrator import MarketBot, MarketBotConfig
from market.candles.aggregator import CandleAggregator
from market.candles.models import Candle
from market.data.historical.adapters.upstox import UpstoxHistoricalMarketDataProvider
from market.data.historical.models import HistoricalDataRequest
from market.data.ingestion.providers.upstox.config import UpstoxFeedConfig
from market.data.ingestion.providers.upstox.feed import UpstoxMarketFeed
from market.data.ingestion.providers.upstox.generated import MarketDataFeedV3_pb2
from market.data.ingestion.providers.upstox.instrument_mapper import UpstoxInstrumentMapper
from market.data.metrics import DataQualityMetrics
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from market.data.validation import MarketEventValidator
from ml.prediction.live_bundle import LivePredictionBundle, load_live_prediction_bundle
from ml.prediction.storage import PredictionStore
from monitoring.runtime import MonitoringRuntime
from trading.runtime_pipeline import TradingResearchRuntime


@dataclass(frozen=True, slots=True)
class LiveModelRuntimeConfig:
    """Runtime configuration for model-only live inference."""

    symbol: str = "RELIANCE"
    benchmark: str = "NIFTY50"
    timeframe_minutes: int = 5
    warmup_days: int = 15
    max_predictions: int = 1
    model_artifact: Path = Path("data/models/live_prediction_bundle.pkl")
    instrument_master: Path = Path("data/reference/upstox/NSE.json.gz")
    prediction_store: Path = Path("paper/live_predictions.jsonl")
    model_version: str | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.timeframe_minutes != 5:
            raise ValueError("live model runtime currently requires 5-minute candles")
        if self.warmup_days < 1:
            raise ValueError("warmup_days must be positive")
        if self.max_predictions < 1:
            raise ValueError("max_predictions must be positive")


class LiveModelRuntime:
    """Warm, subscribe, analyze, and predict from the real market."""

    def __init__(
        self,
        *,
        config: LiveModelRuntimeConfig,
        bundle: LivePredictionBundle,
        feed: RealtimeMarketDataPipeline,
        historical: UpstoxHistoricalMarketDataProvider,
        market_bot: MarketBot,
        runtime: TradingResearchRuntime,
        store: PredictionStore | None,
    ) -> None:
        self.config = config
        self.bundle = bundle
        self.feed = feed
        self.historical = historical
        self.market_bot = market_bot
        self.runtime = runtime
        self.store = store
        self.target_history = pd.DataFrame()
        self.benchmark_history = pd.DataFrame()
        self.predictions = 0

    @classmethod
    def from_env(cls, config: LiveModelRuntimeConfig) -> "LiveModelRuntime":
        """Construct the real-market runtime from environment credentials/config."""
        import os

        token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
        if not token:
            raise RuntimeError("UPSTOX_ACCESS_TOKEN is required")

        bundle, _ = load_live_prediction_bundle(config.model_artifact)

        mapper = UpstoxInstrumentMapper.from_local_master(config.instrument_master)
        feed_config = UpstoxFeedConfig.from_env()
        feed = UpstoxMarketFeed(
            feed_config,
            mapper,
            protobuf_module=MarketDataFeedV3_pb2,
        )
        pipeline = RealtimeMarketDataPipeline(
            feed=feed,
            validator=MarketEventValidator(),
            aggregator=CandleAggregator(timeframe_minutes=config.timeframe_minutes),
            metrics=DataQualityMetrics(),
        )

        historical = UpstoxHistoricalMarketDataProvider(
            token,
            mapper,
            timeout_seconds=feed_config.timeout_seconds,
        )
        runtime = TradingResearchRuntime(monitoring=MonitoringRuntime())
        market_bot = MarketBot(
            MarketBotConfig(
                benchmark=config.benchmark,
                data_version="upstox-live",
                feature_version=bundle.provenance.feature_version,
            )
        )
        store = PredictionStore(config.prediction_store)
        return cls(
            config=config,
            bundle=bundle,
            feed=pipeline,
            historical=historical,
            market_bot=market_bot,
            runtime=runtime,
            store=store,
        )

    @staticmethod
    def _frame(bars: tuple[Candle, ...] | list[Candle]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp(bar.timestamp),
                    "symbol": bar.symbol,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                for bar in bars
            ]
        )

    def warmup(self) -> None:
        """Fetch causal historical candles before subscribing to live data."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=self.config.warmup_days)

        target = self.historical.get_bars(
            HistoricalDataRequest(
                symbol=self.config.symbol,
                exchange="NSE",
                timeframe_minutes=5,
                start=start,
                end=end,
            )
        )
        benchmark = self.historical.get_bars(
            HistoricalDataRequest(
                symbol=self.config.benchmark,
                exchange="NSE",
                timeframe_minutes=5,
                start=start,
                end=end,
            )
        )

        self.target_history = self._frame(tuple(target))
        self.benchmark_history = self._frame(tuple(benchmark))

        if len(self.target_history) < 60:
            raise RuntimeError(
                f"insufficient target warmup: {len(self.target_history)} bars; need at least 60"
            )
        if len(self.benchmark_history) < 60:
            raise RuntimeError(
                f"insufficient benchmark warmup: {len(self.benchmark_history)} bars; need at least 60"
            )

    def _append(self, frame: pd.DataFrame, candle: Candle) -> pd.DataFrame:
        row = self._frame([candle])
        combined = pd.concat([frame, row], ignore_index=True)
        combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
        return combined.sort_values("timestamp", kind="stable").reset_index(drop=True)

    def _predict(self, candle: Candle):
        self.target_history = self._append(self.target_history, candle)
        benchmark = self.benchmark_history.loc[
            self.benchmark_history["timestamp"] <= pd.Timestamp(candle.timestamp)
        ].copy()
        if benchmark.empty:
            return None

        market_context = self.market_bot.build(
            benchmark_data=benchmark[["timestamp", "close"]],
            provenance={"source": "upstox_live_market"},
            monitoring=self.runtime.monitoring,
        )
        _, prediction = self.runtime.market_analysis_and_prediction(
            self.target_history,
            symbol=self.config.symbol,
            benchmark_history=benchmark[["timestamp", "close"]],
            market_context=market_context,
            model=self.bundle.model,
            preprocessor=self.bundle.preprocessor,
            data_version="upstox-live",
            feature_version=self.bundle.provenance.feature_version,
            model_version=self.config.model_version or self.bundle.provenance.model_version,
        )
        self.predictions += 1
        return prediction

    def run(self) -> tuple[object, ...]:
        """Run until max_predictions are produced or the feed terminates."""
        self.warmup()
        predictions = []
        self.feed.start([self.config.symbol, self.config.benchmark])
        try:
            for candle in self.feed.run():
                if candle.symbol != self.config.benchmark:
                    prediction = self._predict(candle)
                    if prediction is not None:
                        predictions.append(prediction)
                        if self.predictions >= self.config.max_predictions:
                            break
        finally:
            self.feed.stop()

        return tuple(predictions)

    def dashboard(self) -> dict:
        """Return the shared monitoring snapshot for the dashboard."""
        return self.runtime.report()


__all__ = ["LiveModelRuntime", "LiveModelRuntimeConfig"]
