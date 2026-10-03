"""Canonical real-market manual decision integration boundary.

Connects completed market candles to the existing Market Bot -> Analysis ->
Prediction chain. A downstream Strategy/Risk/manual-decision callback is injectable so
this layer coordinates existing authorities without duplicating them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

import pandas as pd

from market.bot.contracts import MarketContext
from market.bot.orchestrator import MarketBot
from market.candles.models import Candle
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from ml.integration.analysis_prediction import PredictionContext, predict_from_analysis
from ml.models.calibration import IsotonicProbabilityCalibrator
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from trading.ab30_pipeline import MarketAnalysisResult
from trading.market_bot_pipeline import build_market_analysis_from_market_bot
from trading.live.manual_decision import LiveManualRiskContext, build_live_money_decision
from trading.paper.causal_history import CausalCandleHistory
from trading.paper.live_loop import LivePaperEngine, LivePaperSessionResult
from trading.risk.engine import RiskEngine
from research.integration.analysis_contract import ResearchAnalysisContext
from research.live.runtime import LiveResearchRuntime


class CanonicalLivePaperError(RuntimeError):
    """Raised when the causal paper composition cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class CanonicalLivePaperConfig:
    """Immutable configuration for one canonical real-money decision session."""

    symbol: str = "RELIANCE"
    model_version: str = "phase9-logistic-v1"
    data_version: str = "upstox-live-v1"
    feature_version: str = "v1.0"
    target_version: str = "phase7-decision-label-v1"
    calibration_version: str | None = None
    target_trades: int = 10

    def __post_init__(self) -> None:
        """Validate the runtime configuration."""
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
    """Coordinate live candles through the canonical upstream pipeline.

    The downstream callback is intentionally dependency-injected. This keeps
    Strategy and Risk authority in their existing engines and prevents this
    orchestration module from inventing a second trading policy.
    """

    market_data: RealtimeMarketDataPipeline
    market_bot: MarketBot
    model: LogisticOutcomeModel
    preprocessor: FeaturePreprocessor
    paper_engine: LivePaperEngine | None
    benchmark_history_provider: Callable[[pd.Timestamp], pd.DataFrame]
    benchmark_context_provider: Callable[[pd.Timestamp, pd.DataFrame], MarketContext]
    calibrator: IsotonicProbabilityCalibrator | None = None
    downstream_handler: Callable[[PredictionContext, MarketAnalysisResult, Candle, LivePaperEngine], Any] | None = None
    decision_observer: Callable[[Any, Candle], None] | None = None
    history_provider: Callable[[pd.Timestamp], Iterable[Candle]] | None = None
    history: CausalCandleHistory | None = None
    config: CanonicalLivePaperConfig = CanonicalLivePaperConfig()
    research_context_provider: Callable[[pd.Timestamp], ResearchAnalysisContext] | None = None
    research_runtime: LiveResearchRuntime | None = None
    risk_context_provider: Callable[[pd.Timestamp, str], LiveManualRiskContext] | None = None
    risk_engine: RiskEngine | None = None

    def __post_init__(self) -> None:
        """Reject incompatible dependencies before any network activity."""
        if not isinstance(self.market_data, RealtimeMarketDataPipeline):
            raise TypeError("market_data must be RealtimeMarketDataPipeline")
        if not isinstance(self.market_bot, MarketBot):
            raise TypeError("market_bot must be MarketBot")
        if not isinstance(self.model, LogisticOutcomeModel):
            raise TypeError("model must be LogisticOutcomeModel")
        if not isinstance(self.preprocessor, FeaturePreprocessor):
            raise TypeError("preprocessor must be FeaturePreprocessor")
        if self.paper_engine is not None and not isinstance(self.paper_engine, LivePaperEngine):
            raise TypeError("paper_engine must be LivePaperEngine when supplied")
        if self.paper_engine is None and not isinstance(self.risk_engine, RiskEngine):
            raise TypeError("risk_engine is required when paper_engine is not supplied")
        if not self.model.is_fitted:
            raise CanonicalLivePaperError("model must be fitted before paper inference")
        if not self.preprocessor.is_fitted:
            raise CanonicalLivePaperError(
                "preprocessor must be fitted before paper inference"
            )
        if self.calibrator is not None and not isinstance(self.calibrator, IsotonicProbabilityCalibrator):
            raise TypeError("calibrator must be an IsotonicProbabilityCalibrator")
        if self.config.calibration_version is not None and self.calibrator is None:
            raise CanonicalLivePaperError("calibration_version requires a calibrator")
        if self.calibrator is not None and not self.calibrator.is_fitted:
            raise CanonicalLivePaperError("calibrator must be fitted before paper inference")
        if self.model.feature_count != len(self.preprocessor.get_feature_names_out()):
            raise CanonicalLivePaperError(
                "model/preprocessor feature counts do not match"
            )

        expected_symbol = self.config.symbol.strip().upper()
        if self.paper_engine is not None:
            if self.paper_engine.config.symbol != expected_symbol:
                raise CanonicalLivePaperError(
                    "paper engine symbol must match orchestrator"
                )
            if self.paper_engine.config.target_trades != self.config.target_trades:
                raise CanonicalLivePaperError(
                    "paper engine target_trades must match orchestrator"
                )
        if self.history is not None and self.history.symbol.strip().upper() != expected_symbol:
            raise CanonicalLivePaperError(
                "candle history symbol must match orchestrator"
            )
        if self.history is None:
            object.__setattr__(
                self,
                "history",
                CausalCandleHistory(expected_symbol),
            )

    @staticmethod
    def _candle_frame(candle: Candle) -> pd.DataFrame:
        """Convert one canonical candle into an OHLCV DataFrame."""
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

    def _ensure_causal_history(self, candle: Candle) -> pd.DataFrame:
        """Seed and append one live candle without admitting future bars."""
        if self.history is None:
            raise CanonicalLivePaperError("causal candle history is not initialized")

        cutoff = pd.Timestamp(candle.timestamp)
        current = self.history.frame()

        if current.empty and self.history_provider is not None:
            seeded = tuple(self.history_provider(cutoff))
            previous_timestamp: pd.Timestamp | None = None
            for bar in seeded:
                if not isinstance(bar, Candle):
                    raise CanonicalLivePaperError(
                        "history provider must return Candle objects"
                    )
                bar_timestamp = pd.Timestamp(bar.timestamp)
                if bar_timestamp >= cutoff:
                    raise CanonicalLivePaperError(
                        "history provider returned a candle at or after the live decision time"
                    )
                if previous_timestamp is not None and bar_timestamp <= previous_timestamp:
                    raise CanonicalLivePaperError(
                        "history provider returned non-chronological candles"
                    )
                previous_timestamp = bar_timestamp
                self.history.append(bar)

        current = self.history.frame()
        if current.empty:
            self.history.append(candle)
        else:
            last_timestamp = pd.Timestamp(current["timestamp"].iloc[-1])
            if last_timestamp < cutoff:
                self.history.append(candle)
            elif last_timestamp > cutoff:
                raise CanonicalLivePaperError(
                    "causal candle history is newer than the live decision time"
                )
            else:
                # A repeated delivery at the same decision timestamp is not
                # allowed to mutate the causal history a second time.
                expected = self._candle_frame(candle).iloc[0]
                existing = current.iloc[-1]
                for column in ("open", "high", "low", "close", "volume"):
                    if float(existing[column]) != float(expected[column]):
                        raise CanonicalLivePaperError(
                            "candle history conflicts with an existing decision timestamp"
                        )

        causal = self.history.snapshot_at(cutoff)
        if causal.empty:
            raise CanonicalLivePaperError("causal candle history is empty")
        return causal

    def build_prediction(self, candle: Candle) -> tuple[PredictionContext, MarketAnalysisResult]:
        """Build one causal Market -> Analysis -> Prediction result."""
        if not isinstance(candle, Candle):
            raise TypeError("candle must be a Candle")

        expected_symbol = self.config.symbol.strip().upper()
        if candle.symbol.strip().upper() != expected_symbol:
            raise CanonicalLivePaperError(
                f"unexpected symbol {candle.symbol}; expected {expected_symbol}"
            )

        cutoff = pd.Timestamp(candle.timestamp)
        if cutoff.tzinfo is None:
            raise CanonicalLivePaperError(
                "candle timestamp must be timezone-aware"
            )

        causal_candles = self._ensure_causal_history(candle)

        benchmark_history = self.benchmark_history_provider(cutoff)
        if not isinstance(benchmark_history, pd.DataFrame) or benchmark_history.empty:
            raise CanonicalLivePaperError(
                "benchmark history provider returned no causal benchmark history"
            )

        benchmark_timestamps = pd.to_datetime(
            benchmark_history["timestamp"],
            utc=True,
            errors="coerce",
        )
        if benchmark_timestamps.isna().any():
            raise CanonicalLivePaperError(
                "benchmark history contains invalid timestamps"
            )
        if benchmark_timestamps.max() != cutoff:
            raise CanonicalLivePaperError(
                "benchmark history endpoint does not match candle decision time"
            )

        market_context = self.benchmark_context_provider(
            cutoff,
            benchmark_history,
        )
        if not isinstance(market_context, MarketContext):
            raise CanonicalLivePaperError(
                "benchmark context provider must return MarketContext"
            )

        context_timestamp = pd.Timestamp(market_context.timestamp)
        if context_timestamp.tzinfo is None:
            raise CanonicalLivePaperError(
                "MarketContext timestamp must be timezone-aware"
            )
        if context_timestamp > cutoff:
            raise CanonicalLivePaperError(
                "MarketContext cannot be newer than the candle decision time"
            )

        research_context = None
        if self.research_context_provider is not None:
            research_context = self.research_context_provider(cutoff)
            if not isinstance(research_context, ResearchAnalysisContext):
                raise CanonicalLivePaperError(
                    "research context provider must return ResearchAnalysisContext"
                )
            if research_context.symbol.strip().upper() != expected_symbol:
                raise CanonicalLivePaperError(
                    "research context symbol must exactly match candle symbol"
                )
            if pd.Timestamp(research_context.as_of) > cutoff:
                raise CanonicalLivePaperError(
                    "research context cannot be newer than the candle decision time"
                )

        result = build_market_analysis_from_market_bot(
            causal_candles,
            symbol=expected_symbol,
            benchmark_history=benchmark_history,
            market_context=market_context,
            data_version=self.config.data_version,
            feature_version=self.config.feature_version,
            research_context=research_context,
        )

        prediction = predict_from_analysis(
            result.analysis,
            model=self.model,
            preprocessor=self.preprocessor,
            calibrator=self.calibrator,
            model_version=self.config.model_version,
            target_version=self.config.target_version,
            calibration_version=self.config.calibration_version,
        )

        if pd.Timestamp(prediction.timestamp) != cutoff:
            raise CanonicalLivePaperError(
                "prediction timestamp must exactly match candle decision time"
            )
        if prediction.symbol != expected_symbol:
            raise CanonicalLivePaperError(
                "prediction symbol must exactly match candle symbol"
            )

        return prediction, result

    def process_candle(self, candle: Candle) -> PredictionContext:
        """Run one completed candle through the canonical prediction boundary."""
        prediction, result = self.build_prediction(candle)

        # The callback is the only downstream handoff. No direct broker access
        # or alternate Strategy/Risk implementation exists in this module.
        handler = self.downstream_handler
        if handler is not None:
            callback_result = handler(
                prediction,
                result,
                candle,
                self.paper_engine,
            )
            # Legacy callbacks return None; only an explicit decision-like value
            # is forwarded to observers. This preserves the existing seam.
            decision = callback_result if callback_result is not None else None
        else:
            risk_context = None
            if self.risk_context_provider is not None:
                risk_context = self.risk_context_provider(
                    pd.Timestamp(prediction.timestamp),
                    prediction.symbol,
                )
                if not isinstance(risk_context, LiveManualRiskContext):
                    raise CanonicalLivePaperError(
                        "risk context provider must return LiveManualRiskContext"
                    )

            risk_engine = self.risk_engine
            if risk_engine is None and self.paper_engine is not None:
                risk_engine = self.paper_engine.risk_engine
            if risk_engine is None:
                raise CanonicalLivePaperError(
                    "risk engine is not configured for the canonical decision path"
                )
            decision = build_live_money_decision(
                prediction,
                result,
                candle,
                risk_engine,
                risk_context=risk_context,
            )

        if self.decision_observer is not None and decision is not None:
            self.decision_observer(decision, candle)

        return prediction

    def run_manual_review(
        self,
        symbols: Iterable[str],
        *,
        max_candles: int | None = None,
    ) -> int:
        """Run the real-market manual-review loop without a paper account."""
        if self.paper_engine is not None:
            raise CanonicalLivePaperError(
                "manual-review runtime must not attach a paper engine"
            )
        if max_candles is not None and max_candles <= 0:
            raise ValueError("max_candles must be positive when supplied")

        requested = tuple(
            symbol.strip().upper()
            for symbol in symbols
            if symbol.strip()
        )
        expected = (self.config.symbol.strip().upper(),)
        if requested != expected:
            raise CanonicalLivePaperError(
                "canonical manual-review runtime requires exactly one configured symbol"
            )

        if self.research_runtime is not None:
            self.research_runtime.start()
        self.market_data.start(requested)
        produced = 0
        try:
            for candle in self.market_data.run():
                self.process_candle(candle)
                produced += 1
                if max_candles is not None and produced >= max_candles:
                    break
        finally:
            self.market_data.stop()
            if self.research_runtime is not None:
                self.research_runtime.stop()
        return produced

    def run(self, symbols: Iterable[str]) -> LivePaperSessionResult:
        """Consume the realtime candle stream and finalize the paper session."""
        requested = tuple(
            symbol.strip().upper()
            for symbol in symbols
            if symbol.strip()
        )
        expected = (self.config.symbol.strip().upper(),)
        if requested != expected:
            raise CanonicalLivePaperError(
                "canonical live-paper requires exactly one configured symbol"
            )

        if self.research_runtime is not None:
            self.research_runtime.start()
        self.market_data.start(requested)
        try:
            for candle in self.market_data.run():
                self.process_candle(candle)
                if self.paper_engine.session_completed:
                    break
        finally:
            self.market_data.stop()
            if self.research_runtime is not None:
                self.research_runtime.stop()

        return self.paper_engine.finalize_session()


__all__ = [
    "CanonicalLivePaperConfig",
    "CanonicalLivePaperError",
    "CanonicalLivePaperOrchestrator",
]
