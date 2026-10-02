import numpy as np
import pandas as pd

from screen_observer.contracts import CandleObservation, ChartObservation, ScreenConfidence, ScreenObservation
from screen_observer.evidence import CandleVisualEvidence, TimeframeEvidence
from screen_observer.validation import validate_screen_observation


def _observation(**overrides):
    values = dict(
        observed_at=pd.Timestamp("2026-10-02T09:30:00+05:30"),
        image=np.zeros((600, 1000, 3), dtype=np.uint8),
        chart=ChartObservation(detected=True, left=0, top=0, width=1000, height=600, confidence=0.9),
        symbol="RELIANCE.NS",
        timeframe="5m",
        candles=CandleObservation(bullish=10, bearish=8, confidence=0.8),
        confidence=ScreenConfidence(overall=0.82, symbol=0.9, timeframe=0.9, chart=0.9, candles=0.8, indicators=0.8, ocr=0.8),
    )
    values.update(overrides)
    return ScreenObservation(**values)


def test_s13_valid_observation_passes():
    result = validate_screen_observation(_observation(), require_symbol=True, require_timeframe=True)
    assert result.valid
    assert result.usable


def test_s13_rejects_missing_chart():
    result = validate_screen_observation(_observation(chart=ChartObservation(False)))
    assert not result.valid
    assert "SCREEN_CHART_NOT_DETECTED" in result.reasons


def test_s13_rejects_low_chart_and_overall_confidence():
    result = validate_screen_observation(_observation(
        chart=ChartObservation(detected=True, left=0, top=0, width=1000, height=600, confidence=0.2),
        confidence=ScreenConfidence(overall=0.3, chart=0.2),
    ))
    assert not result.valid
    assert "SCREEN_CHART_CONFIDENCE_LOW" in result.reasons
    assert "SCREEN_OVERALL_CONFIDENCE_LOW" in result.reasons


def test_s13_rejects_invalid_timeframe_when_required():
    result = validate_screen_observation(_observation(timeframe="garbage"), require_timeframe=True)
    assert not result.valid
    assert "SCREEN_TIMEFRAME_INVALID" in result.reasons


def test_s13_rejects_implausible_candle_density():
    result = validate_screen_observation(_observation(
        chart=ChartObservation(detected=True, left=0, top=0, width=100, height=600, confidence=0.9),
        candles=CandleObservation(bullish=80, bearish=40, confidence=0.8),
    ))
    assert not result.valid
    assert "SCREEN_CANDLE_DENSITY_IMPLAUSIBLE" in result.reasons


def test_s13_rejects_inconsistent_candle_evidence():
    result = validate_screen_observation(_observation(
        candle_evidence=CandleVisualEvidence(bullish=4, bearish=4, total=8, confidence=0.8)
    ))
    assert not result.valid
    assert "SCREEN_CANDLE_EVIDENCE_INCONSISTENT" in result.reasons


def test_s13_rejects_noncanonical_timeframe_evidence():
    result = validate_screen_observation(_observation(
        timeframe_evidence=TimeframeEvidence(value="5M", confidence=0.9)
    ))
    assert not result.valid
    assert "SCREEN_TIMEFRAME_EVIDENCE_NONCANONICAL" in result.reasons