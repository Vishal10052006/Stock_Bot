"""End-to-end validation of the V1 live manual-review handoff."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from market.bot.contracts import MarketContext, MarketContextMetadata, MarketState
from market.bot.orchestrator import MarketBot, MarketBotConfig
from market.candles.models import Candle
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from monitoring.operator_snapshot import OperatorSnapshotWriter
from trading.live.manual_decision import CanonicalLiveDecision
from trading.live.risk_context import LiveManualRiskContext
from trading.paper.causal_history import CausalCandleHistory
from trading.paper.canonical_live_orchestrator import CanonicalLivePaperOrchestrator
from trading.risk.engine import RiskEngine
from trading.strategy.models import StrategyDirection


IST = ZoneInfo("Asia/Kolkata")


def _components():
    from tests.test_analysis_prediction_integration import _training_frame

    x_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    transformed = preprocessor.fit_transform(x_train)
    model = LogisticOutcomeModel()
    model.fit(transformed, y_train)
    return model, preprocessor


def _bars(rows: int = 40) -> list[Candle]:
    base = datetime(2026, 9, 29, 9, 15, tzinfo=IST)
    prices = 100.0 * np.cumprod(1.0 + np.full(rows, 0.001))
    return [
        Candle(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=base + timedelta(minutes=5 * i),
            open=float(close),
            high=float(close + 0.20),
            low=float(close - 0.15),
            close=float(close),
            volume=float(1000 + i * 10),
        )
        for i, close in enumerate(prices)
    ]


def _market_context(cutoff: pd.Timestamp) -> MarketContext:
    timestamp = cutoff.to_pydatetime()
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


def _benchmark(cutoff: pd.Timestamp) -> pd.DataFrame:
    timestamps = pd.date_range(end=cutoff, periods=40, freq="5min")
    close = 25_000.0 * np.cumprod(1.0 + np.full(len(timestamps), 0.001))
    return pd.DataFrame({"timestamp": timestamps, "close": close})


def _risk_context() -> LiveManualRiskContext:
    now = pd.Timestamp.now(tz="UTC")
    return LiveManualRiskContext(
        as_of=now - pd.Timedelta(seconds=2),
        source="v1-e2e-test-live-account",
        available_equity=125000.0,
        day_start_equity=120000.0,
        available_cash=80000.0,
        peak_equity=126000.0,
        realized_pnl=1500.0,
        unrealized_pnl=3500.0,
        open_positions=0,
        trades_today=0,
        gross_exposure=0.0,
        symbol_already_open=False,
        position_context=None,
        liquidity_available=True,
        kill_switch_active=False,
        sector=None,
        symbol_exposure={},
        sector_exposure={},
        pairwise_correlation={},
        atr=None,
        high_volatility=False,
        market_data_valid=True,
        system_ready=True,
        kill_switch_state=None,
        max_age_seconds=30.0,
    )


def test_v1_live_manual_review_pipeline_handoff_is_end_to_end(monkeypatch, tmp_path: Path):
    import trading.paper.canonical_live_orchestrator as orchestrator_module

    model, preprocessor = _components()
    bars = _bars()
    history = CausalCandleHistory("RELIANCE")
    for bar in bars[:-1]:
        history.append(bar)

    risk_context = _risk_context()
    captured: dict[str, object] = {}

    def fake_decision(prediction, result, candle, risk_engine, *, risk_context):
        captured["risk_context"] = risk_context
        return CanonicalLiveDecision(
            prediction=prediction,
            strategy=SimpleNamespace(
                timestamp=prediction.timestamp,
                symbol=prediction.symbol,
                direction=StrategyDirection.NO_TRADE,
                prediction_probability=None,
                prediction_margin=None,
            ),
            risk_status="APPROVED",
            risk_reason="Test risk gate approved.",
            manual_execution_status="MANUAL_BUY_SELL_REQUIRED",
            trade_id=None,
            research_context=None,
            market_context=None,
            risk_context=risk_context,
        )

    monkeypatch.setattr(
        orchestrator_module,
        "build_live_money_decision",
        fake_decision,
    )

    snapshot_path = tmp_path / "operator_snapshot.json"
    writer = OperatorSnapshotWriter(
        path=snapshot_path,
        symbol="RELIANCE",
        benchmark_symbol="NIFTY",
        model_version="phase9-logistic-v1",
        calibration_version="calibration-v1",
        data_version="upstox-live-v1",
        feature_version="v1.0",
        require_live_account_context=True,
    )

    def observer(decision, candle):
        captured["decision"] = decision
        captured["candle"] = candle
        writer.observe(decision, candle)

    market_data = RealtimeMarketDataPipeline.__new__(RealtimeMarketDataPipeline)
    orchestrator = CanonicalLivePaperOrchestrator(
        market_data=market_data,
        market_bot=MarketBot(
            MarketBotConfig(
                benchmark="NIFTY",
                data_version="upstox-live-v1",
                feature_version="v1.0",
            )
        ),
        model=model,
        preprocessor=preprocessor,
        paper_engine=None,
        risk_engine=RiskEngine(),
        benchmark_history_provider=_benchmark,
        benchmark_context_provider=lambda cutoff, _: _market_context(cutoff),
        history_provider=None,
        history=history,
        decision_observer=observer,
        risk_context_provider=lambda _timestamp, _symbol: risk_context,
    )

    prediction = orchestrator.process_candle(bars[-1])

    assert prediction.symbol == "RELIANCE"
    assert captured["risk_context"] is risk_context
    assert captured["decision"].manual_execution_status == "MANUAL_BUY_SELL_REQUIRED"
    assert captured["decision"].trade_id is None
    assert captured["candle"] == bars[-1]

    import json

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "live_market_manual_review"
    assert payload["execution"]["mode"] == "REAL_MONEY_MANUAL_REVIEW"
    assert payload["performance"]["status"] == "LIVE_ACCOUNT_OBSERVED"
    assert payload["performance"]["available_equity"] == 125000.0
    assert payload["v1"]["manual_execution"] is True
    assert payload["v1"]["broker_execution"] is False
