from __future__ import annotations

import pandas as pd

from monitoring.screen_reviewer import ScreenReviewer
from screen_observer.contracts import (
    CandleObservation,
    ChartObservation,
    ScreenConfidence,
    VisualContext,
)


def _context(
    *,
    observed_at: str = "2026-10-03T09:20:00+05:30",
    symbol: str | None = "RELIANCE",
    timeframe: str | None = "5m",
    confidence: float = 0.92,
) -> VisualContext:
    return VisualContext(
        observed_at=pd.Timestamp(observed_at),
        symbol=symbol,
        timeframe=timeframe,
        indicators=("RSI", "MACD"),
        chart_detected=True,
        candle_observation=CandleObservation(bullish=4, bearish=1, confidence=0.90),
        confidence=ScreenConfidence(
            overall=confidence,
            symbol=confidence,
            timeframe=confidence,
            chart=confidence,
            candles=confidence,
            indicators=confidence,
            ocr=confidence,
        ),
        provenance={"source": "desktop_screen", "authority": "OBSERVATION_ONLY"},
    )


def test_reviewer_matches_fresh_identity_aligned_screen():
    review = ScreenReviewer().review(
        _context(),
        market_symbol="RELIANCE",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-03T09:20:20+05:30"),
    )

    assert review.status == "MATCH"
    assert review.severity == "INFO"
    assert review.usable is True
    assert review.reasons == ()
    assert review.authority == "OBSERVATION_ONLY"


def test_reviewer_degrades_stale_screen_without_granting_authority():
    review = ScreenReviewer(max_age_seconds=30).review(
        _context(observed_at="2026-10-03T09:19:00+05:30"),
        market_symbol="RELIANCE",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-03T09:20:00+05:30"),
    )

    assert review.status == "DEGRADED"
    assert review.severity == "WARNING"
    assert "SCREEN_OBSERVATION_STALE" in review.reasons
    assert review.usable is False


def test_reviewer_flags_symbol_mismatch_as_high_severity():
    review = ScreenReviewer().review(
        _context(symbol="TCS"),
        market_symbol="RELIANCE",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-03T09:20:20+05:30"),
    )

    assert review.status == "MISMATCH"
    assert review.severity == "HIGH"
    assert "SCREEN_SYMBOL_MISMATCH" in review.reasons


def test_reviewer_flags_low_confidence_without_inventing_a_cause():
    review = ScreenReviewer(min_confidence=0.80).review(
        _context(confidence=0.50),
        market_symbol="RELIANCE",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-03T09:20:20+05:30"),
    )

    assert review.status == "DEGRADED"
    assert review.severity == "WARNING"
    assert "SCREEN_CONFIDENCE_LOW" in review.reasons
    assert review.as_dict()["authority"] == "OBSERVATION_ONLY"
