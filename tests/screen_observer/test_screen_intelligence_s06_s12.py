import numpy as np
import pandas as pd

from screen_observer.candles import parse_candle_evidence
from screen_observer.confidence import calculate_screen_confidence, screen_is_usable
from screen_observer.contracts import CandleObservation, ChartObservation, ScreenConfidence, ScreenObservation, VisualContext, WindowObservation
from screen_observer.evidence import IndicatorEvidence, TimeframeEvidence
from screen_observer.indicators import detect_indicator_evidence
from screen_observer.ocr import OCRToken
from screen_observer.reconciliation import reconcile
from screen_observer.timeframe import detect_timeframe_evidence


def test_s06_blank_image_fails_closed():
    image = np.full((400, 800, 3), 255, dtype=np.uint8)
    evidence = parse_candle_evidence(image)
    assert evidence.total == 0
    assert evidence.confidence == 0.0


def test_s07_indicator_evidence_deduplicates():
    tokens = (
        OCRToken("EMA", 95, 10, 10, 50, 20),
        OCRToken("EMA", 80, 20, 40, 50, 20),
        OCRToken("RSI", 90, 30, 70, 40, 20),
    )
    result = detect_indicator_evidence(tokens)
    assert [item.name for item in result] == ["EMA", "RSI"]
    assert result[0].confidence == 0.95


def test_s08_timeframe_evidence_normalizes():
    token = OCRToken("5m", 92, 10, 10, 30, 20)
    result = detect_timeframe_evidence((token,))
    assert result is not None
    assert result.value == "5m"
    assert result.confidence == 0.92


def test_s10_reconciliation_rejects_future_and_stale():
    context = VisualContext(
        observed_at=pd.Timestamp("2026-10-02T09:30:00+05:30"),
        symbol="RELIANCE.NS",
        timeframe="5m",
        indicators=(),
        chart_detected=True,
        candle_observation=CandleObservation(),
        confidence=ScreenConfidence(overall=0.8, chart=0.8),
    )
    future = reconcile(
        context,
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:29:00+05:30"),
    )
    assert "SCREEN_OBSERVATION_FROM_FUTURE" in future.reasons

    stale = reconcile(
        context,
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:31:00+05:30"),
        max_age_seconds=30,
    )
    assert "SCREEN_OBSERVATION_STALE" in stale.reasons


def test_s11_confidence_gate():
    confidence = calculate_screen_confidence(
        chart=0.9, ocr=0.8, symbol=0.8, timeframe=0.8, indicators=0.6, candles=0.7
    )
    assert confidence.overall > 0.7
    assert screen_is_usable(confidence)

from screen_observer.analysis import build_screen_analysis_context


def test_s12_analysis_context_is_observation_only_and_usable():
    observation = ScreenObservation(
        observed_at=pd.Timestamp("2026-10-02T09:30:00+05:30"),
        image=None,
        windows=(),
        target_window=None,
        chart=ChartObservation(
            detected=True, left=0, top=100, width=1000, height=600, confidence=0.9
        ),
        symbol="RELIANCE.NS",
        timeframe="5m",
        indicators=("EMA",),
        candles=CandleObservation(bullish=5, bearish=4, confidence=0.8),
        confidence=ScreenConfidence(
            overall=0.82, chart=0.9, symbol=0.9, timeframe=0.9,
            indicators=0.8, candles=0.8, ocr=0.8
        ),
    )
    result = build_screen_analysis_context(
        observation,
        market_symbol="RELIANCE.NS",
        market_timeframe="5m",
        decision_timestamp=pd.Timestamp("2026-10-02T09:30:05+05:30"),
    )
    assert result.usable
    assert result.reconciliation_status == "MATCH"
    assert result.provenance["authority"] == "OBSERVATION_ONLY"
    assert "signal" not in result.as_dict()
