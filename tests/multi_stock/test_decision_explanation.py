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

def test_missing_reason_is_not_fabricated():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    result = build_decision_explanation(ts, "RELIANCE.NS", strategy={"timestamp": ts, "direction": "LONG"})
    assert result.items == ()
