from __future__ import annotations

import json

import pandas as pd
import pytest

from multi_stock.scanner import StockScannerStore


def _decision(
    ts: str,
    symbol: str,
    long_p: float,
    short_p: float,
    no_edge: float,
    direction: str = "NO_TRADE",
):
    """Build a duck-typed canonical decision fixture."""
    prediction = type("Prediction", (), {})()
    prediction.timestamp = pd.Timestamp(ts)
    prediction.symbol = symbol
    prediction.predicted_class = (
        "LONG_SUCCESS"
        if long_p >= max(short_p, no_edge)
        else "SHORT_SUCCESS"
        if short_p >= no_edge
        else "NO_EDGE"
    )
    prediction.model_version = "phase9-logistic-v1"
    prediction.calibration_version = "cal-v1"
    prediction.feature_version = "v1.0"
    prediction.provenance = {"source": "test"}
    prediction.probabilities = pd.DataFrame(
        [{
            "LONG_SUCCESS": long_p,
            "SHORT_SUCCESS": short_p,
            "NO_EDGE": no_edge,
        }]
    )

    strategy = type("Strategy", (), {})()
    strategy.symbol = symbol
    strategy.direction = direction
    strategy.regime = "TREND_UP"
    strategy.rationale = "test rationale"
    strategy.entry_reference = 100.0
    strategy.stop_reference = 99.0
    strategy.target_reference = 102.0

    decision = type("Decision", (), {})()
    decision.prediction = prediction
    decision.strategy = strategy
    decision.risk_status = "APPROVED"
    decision.risk_reason = "risk passed"
    decision.paper_order_status = (
        "FILLED" if direction != "NO_TRADE" else None
    )
    decision.trade_id = "TR-001" if direction != "NO_TRADE" else None
    return decision


def test_scanner_keeps_latest_symbol_and_sorts():
    """The scanner keeps one latest row per symbol."""
    store = StockScannerStore()
    store.observe(
        _decision("2026-10-02T10:00:00Z", "ITC", 0.60, 0.20, 0.20),
        price=500,
    )
    store.observe(
        _decision("2026-10-02T10:05:00Z", "RELIANCE", 0.70, 0.15, 0.15),
        price=2500,
    )
    store.observe(
        _decision(
            "2026-10-02T10:05:00Z",
            "ITC",
            0.20,
            0.65,
            0.15,
            "SHORT",
        ),
        price=505,
    )

    assert [row.symbol for row in store.rows] == ["RELIANCE", "ITC"]
    assert store.rows[0].long_success == 0.70


def test_scanner_rejects_time_reversal():
    """An older observation cannot overwrite a newer symbol state."""
    store = StockScannerStore()
    store.observe(
        _decision("2026-10-02T10:05:00Z", "ITC", 0.6, 0.2, 0.2)
    )
    with pytest.raises(ValueError, match="moved backwards"):
        store.observe(
            _decision("2026-10-02T10:00:00Z", "ITC", 0.6, 0.2, 0.2)
        )


def test_scanner_rejects_probability_sum_error():
    """Malformed probabilities fail closed."""
    with pytest.raises(ValueError, match="sum to 1"):
        StockScannerStore().observe(
            _decision("2026-10-02T10:05:00Z", "ITC", 0.6, 0.2, 0.3)
        )


def test_scanner_persists_observation_only_snapshot(tmp_path):
    """Snapshot persistence includes observation-only authority."""
    store = StockScannerStore()
    store.observe(
        _decision("2026-10-02T10:05:00Z", "ITC", 0.6, 0.2, 0.2)
    )
    path = tmp_path / "operator_snapshot.json"

    snapshot = store.write_json(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert snapshot.status == "READY"
    assert payload["authority"] == "OBSERVATION_ONLY"
    assert payload["views"]["scanner"]["rows"][0]["symbol"] == "ITC"
    assert len(payload["fingerprint"]) == 64
