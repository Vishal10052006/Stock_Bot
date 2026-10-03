from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from monitoring.operator_snapshot import OperatorSnapshotWriter


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
    strategy = SimpleNamespace(
        direction=SimpleNamespace(value="LONG"),
        rationale="Canonical strategy observation.",
        strategy_version="baseline-v1",
    )
    return SimpleNamespace(
        prediction=prediction,
        strategy=strategy,
        risk_status="APPROVED",
        risk_reason="Risk limits satisfied.",
        paper_order_status="FILLED",
        trade_id="TR-001",
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
    assert payload["mode"] == "live_market_paper"
    assert payload["authority"] == "OBSERVATION_ONLY"
    assert payload["market"]["status"] == "WAITING_FOR_MARKET"
    assert payload["execution"]["broker_orders"] == 0
    assert payload["performance"]["total_return"] == 0.0
    assert payload["fingerprint"]


def test_operator_snapshot_contains_only_observed_paper_state(tmp_path):
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
    assert payload["market"]["status"] == "LIVE_PAPER_OBSERVED"
    assert payload["market"]["price"] == 2505.0
    assert payload["prediction"]["predicted_class"] == "LONG_SUCCESS"
    assert payload["prediction"]["probabilities"]["LONG_SUCCESS"] == 0.62
    assert payload["strategy"]["status"] == "LONG"
    assert payload["risk"]["status"] == "APPROVED"
    assert payload["execution"]["paper_order_status"] == "FILLED"
    assert payload["execution"]["broker_orders"] == 0
    assert payload["performance"]["equity"] == 100250.0
    assert payload["performance"]["total_return"] == 0.0025
    assert payload["metrics"]["model.prediction_count"] == 1
    assert payload["metrics"]["execution.fill_count"] == 1
    assert payload["health"][2]["status"] == "ENFORCED"
    assert payload["events"]
    assert payload["fingerprint"]
