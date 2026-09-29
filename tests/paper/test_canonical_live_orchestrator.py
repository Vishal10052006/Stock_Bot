"""Tests for the canonical live-paper prediction integration seam."""

import pandas as pd
import pytest

from market.bot.contracts import MarketContext, MarketContextMetadata, MarketState
from market.bot.orchestrator import MarketBot, MarketBotConfig
from market.candles.models import Candle
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from trading.paper.canonical_live_orchestrator import (
    CanonicalLivePaperError,
    CanonicalLivePaperOrchestrator,
)
from trading.paper.live_loop import LivePaperEngine, LivePaperSessionConfig


def _fitted_components():
    """Build small fitted Phase-9 components for integration testing."""
    from tests.test_analysis_prediction_integration import _training_frame

    x_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    transformed = preprocessor.fit_transform(x_train)

    model = LogisticOutcomeModel()
    model.fit(transformed, y_train)
    return model, preprocessor


def _candle() -> Candle:
    """Return a valid completed 5-minute candle."""
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


def _market_context() -> MarketContext:
    """Return a causal MarketContext for the integration fixture."""
    timestamp = pd.Timestamp("2026-09-29T09:20:00Z").to_pydatetime()
    return MarketContext(
        timestamp=timestamp,
        benchmark="NIFTY",
        state=MarketState(
            timestamp=timestamp,
            benchmark="NIFTY",
        ),
        metadata=MarketContextMetadata(
            data_version="test-data",
            feature_version="v1.0",
        ),
    )


def _orchestrator(
    downstream_handler=None,
) -> CanonicalLivePaperOrchestrator:
    """Construct the seam without opening any network connection."""
    model, preprocessor = _fitted_components()
    paper_engine = LivePaperEngine(
        LivePaperSessionConfig(
            symbol="RELIANCE",
            target_trades=10,
        )
    )

    market_data = RealtimeMarketDataPipeline.__new__(
        RealtimeMarketDataPipeline
    )

    return CanonicalLivePaperOrchestrator(
        market_data=market_data,
        market_bot=MarketBot(MarketBotConfig(benchmark="NIFTY")),
        model=model,
        preprocessor=preprocessor,
        paper_engine=paper_engine,
        benchmark_history_provider=lambda _: pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-09-29T09:20:00Z"]),
                "close": [25_000.0],
                "market_return_3": [0.001],
                "market_return_12": [0.002],
                "market_volatility_20": [0.01],
            }
        ),
        benchmark_context_provider=lambda _, __: _market_context(),
        downstream_handler=downstream_handler,
    )


def test_canonical_seam_produces_model_prediction():
    """Verify completed candles reach canonical model inference."""
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
    """Future MarketContext must fail closed before prediction."""
    orchestrator = _orchestrator()
    future = MarketContext(
        timestamp=pd.Timestamp("2026-09-29T09:25:00Z").to_pydatetime(),
        benchmark="NIFTY",
        state=MarketState(
            timestamp=pd.Timestamp("2026-09-29T09:25:00Z").to_pydatetime(),
            benchmark="NIFTY",
        ),
        metadata=MarketContextMetadata(
            data_version="test-data",
            feature_version="v1.0",
        ),
    )

    object.__setattr__(
        orchestrator,
        "benchmark_context_provider",
        lambda _, __: future,
    )

    with pytest.raises(
        CanonicalLivePaperError,
        match="newer than the candle",
    ):
        orchestrator.process_candle(_candle())


def test_downstream_callback_receives_canonical_prediction():
    """The orchestrator exposes prediction/analysis without adding broker logic."""
    captured = {}

    def downstream(prediction, analysis, candle, paper_engine):
        captured["prediction"] = prediction
        captured["analysis"] = analysis
        captured["candle"] = candle
        captured["paper_engine"] = paper_engine

    prediction = _orchestrator(downstream_handler=downstream).process_candle(
        _candle()
    )

    assert captured["prediction"] == prediction
    assert captured["candle"] == _candle()
    assert isinstance(captured["analysis"].feature_vector, dict)
    assert captured["paper_engine"].config.symbol == "RELIANCE"
