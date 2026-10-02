from __future__ import annotations
import pandas as pd
import pytest
from multi_stock.decision_explanation import build_decision_explanation

def test_explanation_preserves_pipeline_reasons_and_order():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    result = build_decision_explanation(ts, "RELIANCE.NS", strategy={"timestamp": ts, "direction": "NO_TRADE", "rationale": "Regime filter failed."}, risk={"timestamp": ts, "status": "REJECTED", "reason": "Risk gate blocked execution."})
    assert result.outcome == "NO_TRADE"
    assert [item.stage for item in result.items] == ["Strategy", "Risk"]
    assert result.items[0].reason == "Regime filter failed."
    assert result.authority == "OBSERVATION_ONLY"

def test_future_explanation_evidence_fails_closed():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    with pytest.raises(ValueError, match="future explanation evidence rejected"):
        build_decision_explanation(ts, "RELIANCE.NS", strategy={"timestamp": ts + pd.Timedelta(seconds=1), "direction": "LONG", "rationale": "candidate"})

def test_full_pipeline_layers_are_preserved():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    result = build_decision_explanation(
        ts, "RELIANCE.NS",
        market={"timestamp": ts, "symbol": "RELIANCE.NS", "status": "OBSERVED", "reason": "Market context available."},
        analysis={"timestamp": ts, "symbol": "RELIANCE.NS", "status": "OBSERVED", "reason": "Analysis context available."},
        prediction={"timestamp": ts, "symbol": "RELIANCE.NS", "status": "VALID", "reason": "Prediction evidence available."},
    )
    assert [item.stage for item in result.items] == ["Market", "Analysis", "Prediction"]
    assert result.outcome == "OBSERVATION_ONLY"


def test_symbol_mismatch_fails_closed():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    with pytest.raises(ValueError, match="explanation symbol mismatch"):
        build_decision_explanation(ts, "RELIANCE.NS", prediction={"timestamp": ts, "symbol": "TCS.NS", "reason": "evidence"})


def test_missing_reason_is_not_fabricated():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    result = build_decision_explanation(ts, "RELIANCE.NS", strategy={"timestamp": ts, "direction": "LONG"})
    assert result.items == ()


@pytest.mark.parametrize(
    ("execution_status", "expected"),
    [
        ("BLOCKED", "EXECUTION_BLOCKED"),
        ("REJECTED_BROKER", "EXECUTION_REJECTED"),
        ("FILLED", "EXECUTION_FILLED"),
        ("PARTIALLY_FILLED", "EXECUTION_PENDING"),
        ("OPEN", "EXECUTION_PENDING"),
        ("ACKNOWLEDGED", "EXECUTION_PENDING"),
    ],
)
def test_execution_lifecycle_outcomes_are_explicit(execution_status, expected):
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    result = build_decision_explanation(
        ts,
        "RELIANCE.NS",
        strategy={"timestamp": ts, "symbol": "RELIANCE.NS", "direction": "LONG", "reason": "candidate"},
        execution={"timestamp": ts, "symbol": "RELIANCE.NS", "status": execution_status, "reason": "observed execution state"},
    )
    assert result.outcome == expected


def test_authorized_execution_is_not_reported_as_filled():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    result = build_decision_explanation(
        ts,
        "RELIANCE.NS",
        strategy={"timestamp": ts, "symbol": "RELIANCE.NS", "direction": "LONG", "reason": "candidate"},
        execution={"timestamp": ts, "symbol": "RELIANCE.NS", "status": "AUTHORIZED", "reason": "risk-approved authorization"},
    )
    assert result.outcome == "LONG"


def test_risk_rejection_remains_authoritative_over_blocked_execution():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    result = build_decision_explanation(
        ts,
        "RELIANCE.NS",
        strategy={"timestamp": ts, "symbol": "RELIANCE.NS", "direction": "LONG", "reason": "candidate"},
        risk={"timestamp": ts, "symbol": "RELIANCE.NS", "status": "REJECTED", "reason": "exposure limit"},
        execution={"timestamp": ts, "symbol": "RELIANCE.NS", "status": "BLOCKED", "reason": "risk rejected"},
    )
    assert result.outcome == "RISK_REJECTED"
