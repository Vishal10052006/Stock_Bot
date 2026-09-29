"""Canonical real-market paper integration boundary.

This adapter replaces the legacy live-paper entry feature shortcut with the
existing Market Bot -> Analysis -> Prediction -> Strategy -> Risk contract
chain. The execution target remains the existing paper engine only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

import pandas as pd

from market.bot.contracts import MarketContext, MarketContextMetadata, MarketState
from market.bot.orchestrator import MarketBot
from market.candles.models import Candle
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from ml.integration.analysis_prediction import PredictionContext, predict_from_analysis
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from trading.market_bot_pipeline import build_market_analysis_from_market_bot
from trading.paper.live_loop import (
    LivePaperEngine,
    LivePaperSessionConfig,
    LivePaperSessionResult,
)
from trading.strategy.models import StrategyDirection, StrategyInput
from trading.risk.gate import evaluate_strategy_risk, RiskDecisionStatus
from execution.trading_execution import authorize_risk_decision, ExecutionAuthorizationStatus


class CanonicalLivePaperError(RuntimeError):
    """Raised when the causal live-paper composition cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class CanonicalLivePaperConfig:
    """Immutable configuration for one canonical live-paper session."""

    symbol: str = "RELIANCE"
    model_version: str = "phase9-logistic-v1"
    data_version: str = "upstox-live-v1"
    feature_version: str = "v1.0"
    target_trades: int = 10

    def __post_init__(self) -> None:
        """Validate configuration at construction time."""
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
class CanonicalLivePaperOrchestrator:
    """Connect completed candles to the authoritative paper-trading boundary.

    This class owns orchestration only. Market Bot, Analysis Bot, Prediction,
    Strategy, Risk, and Paper Execution remain the authorities for their jobs.
    """

    market_data: RealtimeMarketDataPipeline
    market_bot: MarketBot
    model: LogisticOutcomeModel
    preprocessor: FeaturePreprocessor
    paper_engine: LivePaperEngine
    benchmark_history_provider: Callable[[pd.Timestamp], pd.DataFrame]
    benchmark_context_provider: Callable[
        [pd.Timestamp, pd.DataFrame], MarketContext
    ]
    config: CanonicalLivePaperConfig = CanonicalLivePaperConfig()

    def __post_init__(self) -> None:
        """Reject incompatible dependencies before a session can start."""
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
            raise CanonicalLivePaperError("model must be fitted before paper inference")
        if not self.preprocessor.is_fitted:
            raise CanonicalLivePaperError(
                "preprocessor must be fitted before paper inference"
            )
        if self.model.feature_count != len(self.preprocessor.get_feature_names_out()):
            raise CanonicalLivePaperError(
                "model/preprocessor feature counts do not match"
            )
        expected_symbol = self.config.symbol.strip().upper()
        if self.paper_engine.config.symbol != expected_symbol:
            raise CanonicalLivePaperError("paper engine symbol must match orchestrator")
        if self.paper_engine.config.target_trades != self.config.target_trades:
            raise CanonicalLivePaperError(
                "paper engine target_trades must match orchestrator"
            )

    @staticmethod
    def _candle_frame(candle: Candle) -> pd.DataFrame:
        """Convert one canonical candle to the DataFrame boundary."""
        return pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp(candle.timestamp),
                    "symbol": candle.symbol.strip().upper(),
                    "open": float(candle.open),
                    "high": float(candle.high),
                    "low": float(candle.low),
                    "close": float(candle.close),
                    "volume": float(candle.volume),
                }
            ]
        )

    @staticmethod
    def _market_context_to_history(
        market_context: MarketContext,
    ) -> pd.DataFrame:
        """Create the minimal benchmark history accepted by AB-30.

        The exact market-state values are point-in-time observations already
        produced by Market Bot. Missing history is rejected rather than
        fabricated.
        """
        state = market_context.state
        timestamp = pd.Timestamp(market_context.timestamp)
        values = {
            "timestamp": timestamp,
            "close": float(getattr(state, "benchmark_close", 0.0) or 0.0),
            "market_return_3": getattr(state, "market_return_3", None),
            "market_return_12": getattr(state, "market_return_12", None),
            "market_volatility_20": getattr(
                state,
                "market_volatility_20",
                None,
            ),
        }
        if values["close"] <= 0.0:
            raise CanonicalLivePaperError(
                "benchmark context does not expose a usable causal benchmark price"
            )
        if any(values[key] is None for key in (
            "market_return_3",
            "market_return_12",
            "market_volatility_20",
        )):
            raise CanonicalLivePaperError(
                "benchmark history must provide causal market return/volatility fields"
            )
        return pd.DataFrame([values])

    def process_candle(self, candle: Candle) -> PredictionContext:
        """Run one candle through Market -> Analysis -> Prediction.

        Strategy/Risk/Paper execution is intentionally kept in the existing
        LivePaperEngine until its entry contract can consume the canonical
        PredictionContext directly. No simplified feature fallback is allowed.
        """
        if not isinstance(candle, Candle):
            raise TypeError("candle must be a Candle")

        symbol = candle.symbol.strip().upper()
        if symbol != self.config.symbol.strip().upper():
            raise CanonicalLivePaperError(
                f"unexpected symbol {symbol}; expected {self.config.symbol}"
            )

        cutoff = pd.Timestamp(candle.timestamp)
        if cutoff.tzinfo is None:
            raise CanonicalLivePaperError("candle timestamp must be timezone-aware")

        benchmark_history = self.benchmark_history_provider(cutoff)
        if (
            not isinstance(benchmark_history, pd.DataFrame)
            or benchmark_history.empty
        ):
            raise CanonicalLivePaperError(
                "benchmark history provider returned no causal benchmark history"
            )

        market_context = self.benchmark_context_provider(
            cutoff,
            benchmark_history,
        )
        if not isinstance(market_context, MarketContext):
            raise CanonicalLivePaperError(
                "benchmark context provider must return MarketContext"
            )
        if pd.Timestamp(market_context.timestamp) > cutoff:
            raise CanonicalLivePaperError(
                "MarketContext cannot be newer than the candle decision time"
            )

        candles = self._candle_frame(candle)
        result = build_market_analysis_from_market_bot(
            candles,
            symbol=symbol,
            benchmark_history=benchmark_history,
            market_context=market_context,
            data_version=self.config.data_version,
            feature_version=self.config.feature_version,
        )

        prediction = predict_from_analysis(
            result.analysis,
            model=self.model,
            preprocessor=self.preprocessor,
            model_version=self.config.model_version,
        )

        if pd.Timestamp(prediction.timestamp) != cutoff:
            raise CanonicalLivePaperError(
                "prediction timestamp must exactly match candle decision time"
            )

        if prediction.symbol != symbol:
            raise CanonicalLivePaperError(
                "prediction symbol must exactly match candle symbol"
            )

        return prediction

    def run(self, symbols: Iterable[str]) -> LivePaperSessionResult:
        """Consume the realtime feed and fail closed on composition errors."""
        requested = tuple(
            symbol.strip().upper()
            for symbol in symbols
            if symbol.strip()
        )
        expected = (self.config.symbol.strip().upper(),)
        if requested != expected:
            raise CanonicalLivePaperError(
                "canonical live-paper currently requires exactly one configured symbol"
            )

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
    "CanonicalLivePaperConfig",
    "CanonicalLivePaperError",
    "CanonicalLivePaperOrchestrator",
]
