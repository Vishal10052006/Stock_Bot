"""Fail-closed composition seam for real-market paper trading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import pandas as pd

from market.bot.orchestrator import MarketBot
from market.candles.models import Candle
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from trading.market_bot_pipeline import build_market_analysis_from_market_bot
from trading.paper.live_loop import LivePaperEngine, LivePaperSessionResult


class LivePaperOrchestratorError(RuntimeError):
    """Raised when the live-paper composition cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class LivePaperOrchestratorConfig:
    """Immutable configuration for one real-market paper session."""

    symbol: str = "RELIANCE"
    model_version: str = "phase9-logistic-v1"
    data_version: str = "upstox-live-v1"
    feature_version: str = "v1.0"
    target_trades: int = 10

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if not self.model_version.strip():
            raise ValueError("model_version must not be empty")
        if not self.data_version.strip():
            raise ValueError("data_version must not be empty")
        if not self.feature_version.strip():
            raise ValueError("feature_version must not be empty")
        if self.target_trades <= 0:
            raise ValueError("target_trades must be positive")


@dataclass(frozen=True, slots=True)
class LivePaperOrchestrator:
    """Compose live candles through Market/Analysis/Prediction before paper execution.

    This seam deliberately refuses to fall back to the legacy simplified
    feature builder in LivePaperEngine. Until canonical Analysis/Prediction
    output is accepted by that engine, a live-paper run fails closed.
    """

    market_data: RealtimeMarketDataPipeline
    market_bot: MarketBot
    model: LogisticOutcomeModel
    preprocessor: FeaturePreprocessor
    paper_engine: LivePaperEngine
    benchmark_history_provider: Callable[[pd.Timestamp], pd.DataFrame]
    benchmark_context_provider: Callable[[pd.Timestamp, pd.DataFrame], object]
    config: LivePaperOrchestratorConfig = LivePaperOrchestratorConfig()

    def __post_init__(self) -> None:
        if not isinstance(self.market_data, RealtimeMarketDataPipeline):
            raise TypeError("market_data must be RealtimeMarketDataPipeline")
        if not isinstance(self.market_bot, MarketBot):
            raise TypeError("market_bot must be MarketBot")
        if not isinstance(self.model, LogisticOutcomeModel):
            raise TypeError("model must be LogisticOutcomeModel")
        if not isinstance(self.preprocessor, FeaturePreprocessor):
            raise TypeError("preprocessor must be FeaturePreprocessor")
        if not isinstance(self.paper_engine, LivePaperEngine):
            raise TypeError("paper_engine must be LivePaperEngine")
        if not self.model.is_fitted:
            raise LivePaperOrchestratorError("model must be fitted before live-paper inference")
        if not self.preprocessor.is_fitted:
            raise LivePaperOrchestratorError("preprocessor must be fitted before live-paper inference")
        if self.model.feature_count != len(self.preprocessor.get_feature_names_out()):
            raise LivePaperOrchestratorError("model/preprocessor feature counts do not match")
        if self.paper_engine.config.symbol != self.config.symbol.strip().upper():
            raise LivePaperOrchestratorError("paper engine symbol must match orchestrator symbol")
        if self.paper_engine.config.target_trades != self.config.target_trades:
            raise LivePaperOrchestratorError("paper engine target_trades must match orchestrator target_trades")

    def process_candle(self, candle: Candle) -> None:
        """Run one completed candle through the canonical upstream path.

        The resulting Analysis/Prediction objects are intentionally not
        handed to the legacy LivePaperEngine yet. This prevents a false
        claim that the current engine is using model-backed inference.
        """
        if not isinstance(candle, Candle):
            raise TypeError("candle must be a Candle")
        symbol = candle.symbol.strip().upper()
        if symbol != self.config.symbol.strip().upper():
            return

        cutoff = pd.Timestamp(candle.timestamp)
        benchmark_history = self.benchmark_history_provider(cutoff)
        if not isinstance(benchmark_history, pd.DataFrame) or benchmark_history.empty:
            raise LivePaperOrchestratorError("benchmark history provider returned no causal benchmark data")

        market_context = self.benchmark_context_provider(cutoff, benchmark_history)
        if market_context is None:
            raise LivePaperOrchestratorError("benchmark context provider returned no MarketContext")

        candles = pd.DataFrame([candle.__dict__ if hasattr(candle, '__dict__') else {
            "timestamp": pd.Timestamp(candle.timestamp),
            "symbol": candle.symbol,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }])

        try:
            build_market_analysis_from_market_bot(
                candles,
                symbol=symbol,
                benchmark_history=benchmark_history,
                market_context=market_context,
                data_version=self.config.data_version,
                feature_version=self.config.feature_version,
            )
        except (ValueError, TypeError) as exc:
            raise LivePaperOrchestratorError(f"live-paper analysis pipeline rejected candle: {exc}") from exc

        raise LivePaperOrchestratorError(
            "canonical Analysis/Prediction injection into LivePaperEngine is not implemented yet; "
            "refusing to execute the legacy simplified feature path"
        )

    def run(self, symbols: Iterable[str]) -> LivePaperSessionResult:
        """Consume the real-time pipeline and always disconnect on exit."""
        requested = tuple(symbol.strip().upper() for symbol in symbols if symbol.strip())
        if requested != (self.config.symbol.strip().upper(),):
            raise LivePaperOrchestratorError("live-paper currently requires exactly one configured symbol")

        self.market_data.start(requested)
        try:
            for candle in self.market_data.run():
                self.process_candle(candle)
                if self.paper_engine.session_completed:
                    break
        finally:
            self.market_data.stop()

        return self.paper_engine.finalize_session()


__all__ = [
    "LivePaperOrchestrator",
    "LivePaperOrchestratorConfig",
    "LivePaperOrchestratorError",
]