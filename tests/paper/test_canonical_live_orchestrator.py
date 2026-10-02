"""Tests for the canonical live-paper prediction integration seam."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from market.bot.contracts import MarketContext, MarketContextMetadata, MarketState
from market.bot.orchestrator import MarketBot, MarketBotConfig
from market.candles.models import Candle
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from trading.paper.causal_history import CausalCandleHistory
from trading.paper.canonical_live_orchestrator import (
    CanonicalLivePaperError,
    CanonicalLivePaperOrchestrator,
)
from trading.paper.live_loop import LivePaperEngine, LivePaperSessionConfig


IST = ZoneInfo("Asia/Kolkata")


def _fitted_components():
    """Build fitted Phase-9 components from the repository integration fixture."""
    from tests.test_analysis_prediction_integration import _training_frame

    x_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    transformed = preprocessor.fit_transform(x_train)

    model = LogisticOutcomeModel()
    model.fit(transformed, y_train)
    return model, preprocessor


def _candles(rows: int = 40) -> list[Candle]:
    """Create enough causal bars for the repository's rolling indicators."""
    base = datetime(2026, 9, 29, 9, 15, tzinfo=IST)
    prices = 100.0 * np.cumprod(1.0 + np.full(rows, 0.001))
    result: list[Candle] = []

    for index, close in enumerate(prices):
        timestamp = base + timedelta(minutes=5 * index)
        result.append(
            Candle(
                symbol="RELIANCE",
                exchange="NSE",
                timeframe_minutes=5,
                timestamp=timestamp,
                open=float(close),
                high=float(close + 0.20),
                low=float(close - 0.15),
                close=float(close),
                volume=float(1000 + index * 10),
            )
        )

    return result


def _market_context(cutoff: pd.Timestamp) -> MarketContext:
    """Return a causal MarketContext snapshot at the requested cutoff."""
    timestamp = pd.Timestamp(cutoff).to_pydatetime()
    return MarketContext(
        timestamp=timestamp,
        benchmark="NIFTY",
        state=MarketState(
            timestamp=timestamp,
            benchmark="NIFTY",
            trend_state="TRENDING",
            regime="TREND_UP",
            regime_probability=0.90,
            availability="AVAILABLE",
        ),
        metadata=MarketContextMetadata(
            data_version="test-data",
            feature_version="v1.0",
        ),
    )


def _benchmark_history(cutoff: pd.Timestamp) -> pd.DataFrame:
    """Return raw benchmark OHLCV ending exactly at the decision timestamp."""
    timestamps = pd.date_range(
        end=pd.Timestamp(cutoff),
        periods=40,
        freq="5min",
    )
    close = 25_000.0 * np.cumprod(
        1.0 + np.full(len(timestamps), 0.001)
    )
    return pd.DataFrame({"timestamp": timestamps, "close": close})


def _orchestrator(
    *,
    downstream_handler=None,
    candle_history: CausalCandleHistory | None = None,
    history_provider=None,
) -> CanonicalLivePaperOrchestrator:
    """Construct the seam without opening a network connection."""
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
        benchmark_history_provider=_benchmark_history,
        benchmark_context_provider=lambda cutoff, __: _market_context(cutoff),
        downstream_handler=downstream_handler,
        history_provider=history_provider,
        history=candle_history,
    )


def test_causal_history_is_strictly_ordered_and_cutoff_safe():
    history = CausalCandleHistory("RELIANCE")
    bars = _candles(3)

    history.append(bars[0])
    history.append(bars[1])

    snapshot = history.snapshot_at(pd.Timestamp(bars[1].timestamp))
    assert len(snapshot) == 2
    assert snapshot["timestamp"].iloc[-1] == pd.Timestamp(bars[1].timestamp)

    with pytest.raises(ValueError, match="strictly increasing"):
        history.append(bars[1])


def test_canonical_seam_produces_model_prediction():
    bars = _candles()
    history = CausalCandleHistory("RELIANCE")
    for bar in bars[:-1]:
        history.append(bar)

    prediction = _orchestrator(candle_history=history).process_candle(bars[-1])

    assert prediction.symbol == "RELIANCE"
    assert prediction.timestamp == pd.Timestamp(bars[-1].timestamp)
    assert prediction.predicted_class in {
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    }
    assert abs(float(prediction.probabilities.iloc[0].sum()) - 1.0) < 1e-8


def test_future_market_context_is_rejected():
    orchestrator = _orchestrator()
    candle = _candles()[-1]
    future = _market_context(
        pd.Timestamp(candle.timestamp) + pd.Timedelta(minutes=5)
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
        orchestrator.process_candle(candle)


def test_decision_observer_receives_canonical_decision():
    captured = {}

    def observer(decision, candle):
        captured["decision"] = decision
        captured["candle"] = candle

    bars = _candles()
    history = CausalCandleHistory("RELIANCE")
    for bar in bars[:-1]:
        history.append(bar)

    orchestrator = _orchestrator(candle_history=history)
    object.__setattr__(orchestrator, "decision_observer", observer)
    orchestrator.process_candle(bars[-1])

    assert captured["decision"].prediction.symbol == "RELIANCE"
    assert captured["decision"].strategy.symbol == "RELIANCE"
    assert captured["candle"] == bars[-1]


def test_downstream_callback_receives_canonical_prediction_and_result():
    captured = {}

    def downstream(prediction, result, candle, paper_engine):
        captured["prediction"] = prediction
        captured["result"] = result
        captured["candle"] = candle
        captured["paper_engine"] = paper_engine

    bars = _candles()
    history = CausalCandleHistory("RELIANCE")
    for bar in bars[:-1]:
        history.append(bar)

    prediction = _orchestrator(
        downstream_handler=downstream,
        candle_history=history,
    ).process_candle(bars[-1])

    assert captured["prediction"] == prediction
    assert captured["candle"] == bars[-1]
    assert captured["result"].analysis.symbol == "RELIANCE"
    assert isinstance(captured["result"].analysis.feature_vector, dict)
    assert not captured["result"].indicators.empty
    assert not captured["result"].regime.empty
    assert captured["paper_engine"].config.symbol == "RELIANCE"


def test_benchmark_history_must_reach_decision_timestamp():
    orchestrator = _orchestrator()
    candle = _candles()[-1]

    def stale_history(cutoff: pd.Timestamp) -> pd.DataFrame:
        return _benchmark_history(cutoff - pd.Timedelta(minutes=5))

    object.__setattr__(
        orchestrator,
        "benchmark_history_provider",
        stale_history,
    )

    with pytest.raises(CanonicalLivePaperError, match="endpoint"):
        orchestrator.process_candle(candle)


def test_history_provider_rejects_future_seed():
    future_bar = _candles()[-1]
    orchestrator = _orchestrator(
        history_provider=lambda _: (future_bar,),
    )

    with pytest.raises(CanonicalLivePaperError, match="at or after"):
        orchestrator.process_candle(_candles()[-2])
