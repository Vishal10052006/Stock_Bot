"""Tests for the canonical live-paper integration boundary."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from market.bot.contracts import MarketContext, MarketContextMetadata, MarketState
from market.bot.orchestrator import MarketBot, MarketBotConfig
from market.candles.models import Candle
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from trading.paper.canonical_live_orchestrator import (
    CanonicalLivePaperConfig,
    CanonicalLivePaperError,
    CanonicalLivePaperOrchestrator,
)
from trading.paper.live_loop import LivePaperEngine, LivePaperSessionConfig


def _fitted_components():
    """Build the same small fitted Phase-9 components used by adapter tests."""
    from tests.test_analysis_prediction_integration import _training_frame

    x_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    transformed = preprocessor.fit_transform(x_train)

    model = LogisticOutcomeModel()
    model.fit(transformed, y_train)
    return model, preprocessor


def _candle():
    """Return one valid completed 5-minute candle."""
    return Candle(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        timestamp=pd.Timestamp("2026-09-29T09:20:00Z").to_pydatetime(),
        open=100.0,
        high=101.0,
        low=99.5,
        close=100.5,
        volume=1000.0,
    )


def _market_context():
    """Create a minimal causal MarketContext for constructor validation."""
    ts = pd.Timestamp("2026-09-29T09:20:00Z").to_pydatetime()
    return MarketContext(
        timestamp=ts,
        benchmark="NIFTY",
        state=MarketState(
            timestamp=ts,
            benchmark="NIFTY",
        ),
        metadata=MarketContextMetadata(
            data_version="test-data",
            feature_version="v1.0",
        ),
    )


def _orchestrator():
    """Construct an orchestrator with test doubles for network dependencies."""
    model, preprocessor = _fitted_components()
    paper = LivePaperEngine(
        LivePaperSessionConfig(
            symbol="RELIANCE",
            target_trades=10,
        )
    )

    # Constructor only checks the concrete feed type; no connection is opened.
    market_data = RealtimeMarketDataPipeline.__new__(
        RealtimeMarketDataPipeline
    )

    return CanonicalLivePaperOrchestrator(
        market_data=market_data,
        market_bot=MarketBot(MarketBotConfig(benchmark="NIFTY")),
        model=model,
        preprocessor=preprocessor,
        paper_engine=paper,
        benchmark_history_provider=lambda _: pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    ["2026-09-29T09:20:00Z"]
                ),
                "close": [25_000.0],
                "market_return_3": [0.001],
                "market_return_12": [0.002],
                "market_volatility_20": [0.01],
            }
        ),
        benchmark_context_provider=lambda _, __: _market_context(),
        config=CanonicalLivePaperConfig(
            symbol="RELIANCE",
            target_trades=10,
        ),
    )


def test_canonical_orchestrator_builds_prediction():
    """Verify the real Market -> Analysis -> Prediction contract is connected."""
    prediction = _orchestrator().process_candle(_candle())

    assert prediction.symbol == "RELIANCE"
    assert prediction.timestamp == pd.Timestamp("2026-09-29T09:20:00Z")
    assert prediction.predicted_class in {
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    }
    assert abs(float(prediction.probabilities.iloc[0].sum()) - 1.0) < 1e-8


def test_future_market_context_is_rejected():
    """The live-paper boundary must reject a future MarketContext."""
    orchestrator = _orchestrator()

    original_provider = orchestrator.benchmark_context_provider
    object.__setattr__(
        orchestrator,
        "benchmark_context_provider",
        lambda _, __: MarketContext(
            timestamp=datetime(2026, 9, 29, 9, 25, tzinfo=timezone.utc),
            benchmark="NIFTY",
            state=MarketState(
                timestamp=datetime(
                    2026,
                    9,
                    29,
                    9,
                    25,
                    tzinfo=timezone.utc,
                ),
                benchmark="NIFTY",
            ),
            metadata=MarketContextMetadata(
                data_version="test-data",
                feature_version="v1.0",
            ),
        ),
    )

    with pytest.raises(
        CanonicalLivePaperError,
        match="newer than the candle",
    ):
        orchestrator.process_candle(_candle())

    object.__setattr__(
        orchestrator,
        "benchmark_context_provider",
        original_provider,
    )
