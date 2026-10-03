from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from monitoring.operator_snapshot import OperatorSnapshotWriter
from trading.strategy.models import StrategyDecision, StrategyDirection


def _decision() -> SimpleNamespace:
    prediction = SimpleNamespace(
        timestamp=pd.Timestamp("2026-10-05 09:20:00+05:30"),
        symbol="RELIANCE",
        predicted_class="LONG_SUCCESS",
        probabilities=pd.DataFrame(
            [{
                "LONG_SUCCESS": 0.62,
                "SHORT_SUCCESS": 0.18,
                "NO_EDGE": 0.20,
            }]
        ),
        model_version="phase9-logistic-v1",
        calibration_version="calibration-v1",
        feature_version="v1.0",
    )
    strategy = StrategyDecision(
        timestamp=prediction.timestamp,
        symbol="RELIANCE",
        direction=StrategyDirection.LONG,
        strategy_version="baseline-v1",
        rationale="Canonical strategy observation.",
        prediction_class="LONG_SUCCESS",
        prediction_probability=0.62,
        prediction_margin=0.44,
        regime="TREND_UP",
        regime_probability=0.80,
        entry_reference=2505.0,
        stop_reference=2480.0,
        target_reference=2555.0,
        prediction_model_version="phase9-logistic-v1",
        feature_version="v1.0",
        provenance={"data_version": "upstox-live-v1"},
        features={"rsi": 61.0},
    )
    return SimpleNamespace(
        prediction=prediction,
        strategy=strategy,
        risk_status="APPROVED",
        risk_reason="Risk limits satisfied.",
        manual_execution_status="MANUAL_BUY_SELL_REQUIRED",
        trade_id=None,
    )


def _paper_engine() -> SimpleNamespace:
    runtime = SimpleNamespace(
        account_snapshot=lambda prices: (
            100250.0,
            250.0,
            0.0,
            5000.0,
        )
    )
    return SimpleNamespace(runtime=runtime)


def test_operator_snapshot_starts_explicitly_waiting(tmp_path):
    path = tmp_path / "operator_snapshot.json"
    writer = OperatorSnapshotWriter(
        path=path,
        symbol="RELIANCE",
        benchmark_symbol="NIFTY50",
        model_version="phase9-logistic-v1",
        calibration_version="calibration-v1",
        data_version="upstox-live-v1",
        feature_version="v1.0",
        initial_equity=100000.0,
    )

    writer.write_initial()

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["mode"] == "live_market_manual_review"
    assert payload["authority"] == "OBSERVATION_ONLY"
    assert payload["market"]["status"] == "WAITING_FOR_MARKET"
    assert payload["execution"]["broker_orders"] == 0
    assert payload["performance"]["total_return"] == 0.0
    assert payload["fingerprint"]


def test_operator_snapshot_contains_only_observed_manual_review_state(tmp_path):
    path = tmp_path / "operator_snapshot.json"
    writer = OperatorSnapshotWriter(
        path=path,
        symbol="RELIANCE",
        benchmark_symbol="NIFTY50",
        model_version="phase9-logistic-v1",
        calibration_version="calibration-v1",
        data_version="upstox-live-v1",
        feature_version="v1.0",
        initial_equity=100000.0,
    )

    candle = SimpleNamespace(
        symbol="RELIANCE",
        close=2505.0,
    )
    writer.observe(_decision(), candle, _paper_engine())

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["market"]["status"] == "LIVE_MARKET_OBSERVED"
    assert payload["market"]["price"] == 2505.0
    assert payload["prediction"]["predicted_class"] == "LONG_SUCCESS"
    assert payload["prediction"]["probabilities"]["LONG_SUCCESS"] == 0.62
    assert payload["strategy"]["status"] == "LONG"
    assert payload["risk"]["status"] == "APPROVED"
    assert payload["execution"]["manual_execution_status"] == "PENDING_MANUAL_BUY_SELL"
    assert payload["execution"]["broker_orders"] == 0
    assert payload["performance"]["equity"] == 100000.0
    assert payload["performance"]["total_return"] == 0.0
    assert payload["metrics"]["model.prediction_count"] == 1
    assert payload["metrics"]["execution.manual_actions"] == 0
    assert payload["health"][2]["status"] == "ENFORCED"
    assert payload["events"]
    assert payload["fingerprint"]
