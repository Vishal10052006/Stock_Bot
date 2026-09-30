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
from threading import Event

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
from ml.prediction.storage import PredictionRecord, PredictionStore
from trading.paper.live_loop import LivePaperEngine, LivePaperSessionConfig
from monitoring.runtime import MonitoringRuntime
from trading.runtime_pipeline import TradingResearchRuntime


@dataclass(frozen=True, slots=True)
class LiveModelRuntimeConfig:
    """Runtime configuration for model-only live inference."""

    symbol: str = "RELIANCE"
    benchmark: str = "NIFTY50"
    timeframe_minutes: int = 5
    warmup_days: int = 15
    target_trades: int = 10
    max_predictions: int = 500
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
        if self.target_trades < 1:
            raise ValueError("target_trades must be positive")


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
        paper_engine: LivePaperEngine,
    ) -> None:
        self.config = config
        self.bundle = bundle
        self.feed = feed
        self.historical = historical
        self.market_bot = market_bot
        self.runtime = runtime
        self.store = store
        self.paper_engine = paper_engine
        self.target_history = pd.DataFrame()
        self.benchmark_history = pd.DataFrame()
        self.predictions = 0
        self.last_prediction = None
        self.paper_result = None
        self._pause_event = Event()
        self._pause_event.set()
        self._stop_requested = Event()
        self._kill_requested = Event()
        self.lifecycle_state = "CREATED"
        self.lifecycle_error: str | None = None
        self.benchmark_candles = 0
        self.target_candles = 0

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
        paper_engine = LivePaperEngine(
            LivePaperSessionConfig(
                symbol=config.symbol,
                target_trades=config.target_trades,
                model_version=bundle.provenance.model_version,
                output_dir=Path('paper/sessions'),
            )
        )
        return cls(
            config=config,
            bundle=bundle,
            feed=pipeline,
            historical=historical,
            market_bot=market_bot,
            runtime=runtime,
            store=store,
            paper_engine=paper_engine,
        )

    @staticmethod
    def _frame(bars: tuple[Candle, ...] | list[Candle]) -> pd.DataFrame:
        frame = pd.DataFrame(
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
        if not frame.empty:
            # Historical and live candles can carry different timezone
            # objects (for example IST and UTC). Pandas may otherwise infer
            # object dtype for the mixed column, which violates the canonical
            # timezone-aware timestamp contract downstream. Converting the
            # complete column to UTC preserves each instant and guarantees a
            # single timezone-aware datetime dtype.
            frame["timestamp"] = pd.to_datetime(
                frame["timestamp"],
                utc=True,
                errors="raise",
            )
        return frame

    def warmup(self) -> None:
        """Fetch causal historical candles before subscribing to live data."""
        self.lifecycle_state = "WARMUP_STARTED"
        self.lifecycle_error = None
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
        self.lifecycle_state = "WARMUP_COMPLETED"

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
        analysis_result, prediction = self.runtime.market_analysis_and_prediction(
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
        self.last_prediction = prediction

        if self.store is not None:
            probabilities = prediction.probabilities.iloc[0]
            self.store.append(
                PredictionRecord(
                    timestamp=prediction.timestamp,
                    symbol=prediction.symbol,
                    model_version=prediction.model_version,
                    dataset_version=analysis_result.analysis.data_version,
                    feature_version=prediction.feature_version,
                    generated_at=pd.Timestamp.now(tz="UTC"),
                    prediction_type="phase9",
                    payload={
                        "predicted_class": prediction.predicted_class,
                        "LONG_SUCCESS": float(probabilities["LONG_SUCCESS"]),
                        "SHORT_SUCCESS": float(probabilities["SHORT_SUCCESS"]),
                        "NO_EDGE": float(probabilities["NO_EDGE"]),
                    },
                )
            )

        regime_row = analysis_result.regime.iloc[-1]
        self.paper_engine.on_candle_with_context(
            candle,
            analysis=analysis_result.analysis,
            prediction=prediction,
            regime=str(regime_row["regime"]),
            regime_probability=float(regime_row["regime_probability"]),
        )
        return prediction

    def pause(self) -> None:
        """Pause prediction processing without authorizing or submitting orders."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume prediction processing."""
        self._pause_event.set()

    def request_stop(self) -> None:
        """Request a controlled stop and interrupt the market feed."""
        self._stop_requested.set()
        self._pause_event.set()
        self.feed.stop()

    def request_kill(self) -> None:
        """Emergency-stop the paper session and keep broker authority at NONE."""
        self._kill_requested.set()
        self._stop_requested.set()
        self._pause_event.set()
        self.feed.stop()

    @property
    def kill_requested(self) -> bool:
        return self._kill_requested.is_set()

    def run(self) -> tuple[object, ...]:
        """Run until target completion, operator stop, or prediction safety cap."""
        predictions = []
        try:
            self.warmup()
            self.feed.start([self.config.symbol, self.config.benchmark])
            self.lifecycle_state = "FEED_STARTED"
            saw_target_candle = False
            self.lifecycle_state = "WAITING_FOR_CANDLE"
            for candle in self.feed.run():
                if self._stop_requested.is_set():
                    break

                if candle.symbol == self.config.benchmark:
                    self.benchmark_candles += 1
                    self.benchmark_history = self._append(self.benchmark_history, candle)
                    if self.lifecycle_state == "WAITING_FOR_CANDLE":
                        self.lifecycle_state = "BENCHMARK_CANDLE_RECEIVED"
                    continue

                saw_target_candle = True
                self.target_candles += 1
                self._pause_event.wait()
                if self._stop_requested.is_set():
                    break

                if self.predictions == 0:
                    self.lifecycle_state = "FIRST_TARGET_CANDLE"
                prediction = self._predict(candle)
                if prediction is not None:
                    if self.predictions == 1:
                        self.lifecycle_state = "FIRST_PREDICTION"
                    predictions.append(prediction)
                    if self.paper_engine.session_completed:
                        break
                    if self.predictions >= self.config.max_predictions:
                        break

            if (
                not saw_target_candle
                and not self._stop_requested.is_set()
                and not self._kill_requested.is_set()
            ):
                self.lifecycle_error = "FEED_ENDED_BEFORE_FIRST_TARGET_CANDLE"
                raise RuntimeError(self.lifecycle_error)
        except Exception as exc:
            if self.lifecycle_error is None:
                self.lifecycle_error = f"{type(exc).__name__}: {exc}"
            self.lifecycle_state = "FAILED"
            raise
        finally:
            self.feed.stop()

        self.paper_result = self.paper_engine.finalize_session()
        self.lifecycle_state = "STOP_REQUESTED" if self._stop_requested.is_set() else "COMPLETED"
        return tuple(predictions)

    def dashboard(self) -> dict:
        """Return monitoring plus the latest model-only prediction."""
        snapshot = dict(self.runtime.report())
        snapshot["live_runtime"] = {
            "lifecycle_state": self.lifecycle_state,
            "lifecycle_error": self.lifecycle_error,
            "benchmark_candles": self.benchmark_candles,
            "target_candles": self.target_candles,
            "predictions_generated": self.predictions,
        }
        if self.last_prediction is not None:
            probabilities = self.last_prediction.probabilities.iloc[0].to_dict()
            snapshot["live_model"] = {
                "symbol": self.last_prediction.symbol,
                "timestamp": self.last_prediction.timestamp,
                "predicted_class": self.last_prediction.predicted_class,
                "model_version": self.last_prediction.model_version,
                "feature_version": self.last_prediction.feature_version,
                "p_long": float(probabilities["LONG_SUCCESS"]),
                "p_short": float(probabilities["SHORT_SUCCESS"]),
                "p_no_edge": float(probabilities["NO_EDGE"]),
                "predictions_generated": self.predictions,
                "paper_trades": self.paper_engine.completed_count,
                "paper_target_trades": self.paper_engine.config.target_trades,
                "paper_target_reached": self.paper_engine.completed_count >= self.paper_engine.config.target_trades,
                "paper_net_pnl": float(self.paper_result.metrics.net_pnl) if self.paper_result is not None else None,
                "paper_session_fingerprint": self.paper_result.session_fingerprint if self.paper_result is not None else None,
                "decision_diagnostics": self.paper_engine.last_diagnostics,
                "broker_orders": 0,
                "trading_authority": "NONE",
            }
        else:
            snapshot["live_model"] = {
                "predictions_generated": self.predictions,
                "broker_orders": 0,
                "trading_authority": "NONE",
                "status": "WARMUP_OR_WAITING_FOR_COMPLETED_CANDLE",
            }
        return snapshot


__all__ = ["LiveModelRuntime", "LiveModelRuntimeConfig"]
