import pandas as pd

from screen_observer.contracts import CandleObservation, ScreenConfidence, VisualContext
from screen_observer.reconciliation import reconcile


def context(symbol="RELIANCE.NS", timeframe="5m", observed="2026-10-02T09:30:00+05:30"):
    return VisualContext(
        observed_at=pd.Timestamp(observed),
        symbol=symbol,
        timeframe=timeframe,
        indicators=(),
        chart_detected=True,
        candle_observation=CandleObservation(),
        confidence=ScreenConfidence(overall=0.5),
    )


def test_matching_context():
    result = reconcile(
        context(),
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:30:10+05:30"),
    )
    assert result.status == "MATCH"
    assert result.reasons == ()


def test_symbol_mismatch_is_explicit():
    result = reconcile(
        context(symbol="TCS.NS"),
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:30:10+05:30"),
    )
    assert result.status == "MISMATCH"
    assert "SCREEN_SYMBOL_MISMATCH" in result.reasons


def test_future_observation_is_rejected():
    result = reconcile(
        context(),
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:29:00+05:30"),
    )
    assert result.status == "MISMATCH"
    assert "SCREEN_OBSERVATION_FROM_FUTURE" in result.reasons
