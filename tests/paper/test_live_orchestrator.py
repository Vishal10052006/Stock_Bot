"""Regression tests for the fail-closed live-paper orchestration seam."""

import pandas as pd
import pytest

from market.candles.models import Candle
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from market.bot.contracts import MarketContext, MarketContextMetadata, MarketState
from market.bot.orchestrator import MarketBot, MarketBotConfig
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from trading.paper.live_loop import LivePaperEngine, LivePaperSessionConfig
from trading.paper.live_orchestrator import (
    LivePaperOrchestrator,
    LivePaperOrchestratorConfig,
    LivePaperOrchestratorError,
)


def _fitted_model_and_preprocessor():
    from tests.test_analysis_prediction_integration import _training_frame

    X_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    model = LogisticOutcomeModel()
    model.fit(preprocessor.fit_transform(X_train), y_train)
    return model, preprocessor


def _paper_engine():
    return LivePaperEngine(
        LivePaperSessionConfig(symbol='RELIANCE', target_trades=10)
    )


def _candle():
    return Candle(
        symbol='RELIANCE',
        exchange='NSE',
        timeframe_minutes=5,
        timestamp=pd.Timestamp('2026-09-29T09:20:00Z').to_pydatetime(),
        open=100.0,
        high=101.0,
        low=99.5,
        close=100.5,
        volume=1000.0,
    )


def test_orchestrator_rejects_unfitted_model():
    model = LogisticOutcomeModel()
    preprocessor = FeaturePreprocessor()
    with pytest.raises(LivePaperOrchestratorError, match='model must be fitted'):
        LivePaperOrchestrator(
            market_data=RealtimeMarketDataPipeline.__new__(RealtimeMarketDataPipeline),
            market_bot=MarketBot(MarketBotConfig(benchmark='NIFTY')),
            model=model,
            preprocessor=preprocessor,
            paper_engine=_paper_engine(),
            benchmark_history_provider=lambda _: pd.DataFrame(),
            benchmark_context_provider=lambda _, __: None,
        )


def test_orchestrator_rejects_legacy_fallback():
    model, preprocessor = _fitted_model_and_preprocessor()
    paper = _paper_engine()
    market_data = RealtimeMarketDataPipeline.__new__(RealtimeMarketDataPipeline)
    runtime = LivePaperOrchestrator(
        market_data=market_data,
        market_bot=MarketBot(MarketBotConfig(benchmark='NIFTY')),
        model=model,
        preprocessor=preprocessor,
        paper_engine=paper,
        benchmark_history_provider=lambda _: pd.DataFrame({
            'timestamp': pd.to_datetime(['2026-09-29T09:20:00Z']),
            'close': [25000.0],
        }),
        benchmark_context_provider=lambda _, __: MarketContext(
            timestamp=pd.Timestamp('2026-09-29T09:20:00Z').to_pydatetime(),
            benchmark='NIFTY',
            state=MarketState(
                timestamp=pd.Timestamp('2026-09-29T09:20:00Z').to_pydatetime(),
                benchmark='NIFTY',
            ),
            metadata=MarketContextMetadata(
                data_version='test',
                feature_version='v1.0',
            ),
        ),
        config=LivePaperOrchestratorConfig(symbol='RELIANCE', target_trades=10),
    )

    with pytest.raises(LivePaperOrchestratorError, match='canonical Analysis/Prediction|rejected candle'):
        runtime.process_candle(_candle())
