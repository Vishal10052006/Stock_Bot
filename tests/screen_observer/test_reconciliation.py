import pandas as pd

from screen_observer.contracts import CandleObservation, ScreenConfidence, VisualContext
from screen_observer.reconciliation import reconcile


def context(
    symbol="RELIANCE.NS",
    timeframe="5m",
    observed="2026-10-02T09:30:00+05:30",
):
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
    assert result.symbol_match is True
    assert result.timeframe_match is True


def test_matching_context_normalizes_timeframe():
    result = reconcile(
        context(timeframe="5M"),
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:30:10+05:30"),
    )
    assert result.status == "MATCH"


def test_symbol_mismatch_is_explicit():
    result = reconcile(
        context(symbol="TCS.NS"),
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:30:10+05:30"),
    )
    assert result.status == "MISMATCH"
    assert result.symbol_match is False
    assert "SCREEN_SYMBOL_MISMATCH" in result.reasons


def test_timeframe_mismatch_is_explicit():
    result = reconcile(
        context(timeframe="15m"),
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:30:10+05:30"),
    )
    assert result.status == "MISMATCH"
    assert result.timeframe_match is False
    assert "SCREEN_TIMEFRAME_MISMATCH" in result.reasons


def test_future_observation_is_rejected():
    result = reconcile(
        context(),
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:29:00+05:30"),
    )
    assert result.status == "MISMATCH"
    assert "SCREEN_OBSERVATION_FROM_FUTURE" in result.reasons


def test_stale_observation_is_rejected():
    result = reconcile(
        context(),
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:31:00+05:30"),
        max_age_seconds=30,
    )
    assert result.status == "MISMATCH"
    assert result.age_seconds == 60.0
    assert "SCREEN_OBSERVATION_STALE" in result.reasons


def test_freshness_boundary_is_inclusive():
    result = reconcile(
        context(),
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:30:30+05:30"),
        max_age_seconds=30,
    )
    assert result.status == "MATCH"
    assert result.age_seconds == 30.0


def test_missing_screen_identity_fails_closed():
    result = reconcile(
        context(symbol=None, timeframe=None),
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:30:10+05:30"),
    )
    assert result.status == "MISMATCH"
    assert "SCREEN_SYMBOL_MISSING" in result.reasons
    assert "SCREEN_TIMEFRAME_MISSING" in result.reasons


def test_invalid_market_timeframe_fails_closed():
    result = reconcile(
        context(),
        market_symbol="RELIANCE.NS",
        market_timeframe="garbage",
        decision_timestamp=pd.Timestamp("2026-10-02T09:30:10+05:30"),
    )
    assert result.status == "MISMATCH"
    assert "MARKET_TIMEFRAME_INVALID" in result.reasons


def test_negative_max_age_is_rejected():
    try:
        reconcile(
            context(),
            market_symbol="RELIANCE.NS",
            market_timeframe="5m",
            decision_timestamp=pd.Timestamp("2026-10-02T09:30:10+05:30"),
            max_age_seconds=-1,
        )
    except ValueError as exc:
        assert "max_age_seconds" in str(exc)
    else:
        raise AssertionError("negative max_age_seconds must raise")
