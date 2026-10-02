from datetime import timezone
import pandas as pd
import pytest

from screen_observer.contracts import (
    CandleObservation,
    ChartObservation,
    ScreenConfidence,
    VisualContext,
)


def ts():
    return pd.Timestamp("2026-10-02T09:30:00+05:30")


def test_visual_context_is_timezone_aware_and_serializable():
    context = VisualContext(
        observed_at=ts(),
        symbol="reliance.ns",
        timeframe="5m",
        indicators=("EMA", "VWAP"),
        chart_detected=True,
        candle_observation=CandleObservation(bullish=3, bearish=2, confidence=0.8),
        confidence=ScreenConfidence(
            overall=0.8,
            symbol=0.9,
            timeframe=0.9,
            chart=0.8,
            candles=0.8,
            indicators=0.7,
            ocr=0.9,
        ),
    )

    payload = context.as_dict()
    assert payload["symbol"] == "RELIANCE.NS"
    assert payload["observed_at"].endswith("+05:30")


def test_detected_chart_requires_region():
    with pytest.raises(ValueError):
        ChartObservation(detected=True, confidence=0.5)


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError):
        VisualContext(
            observed_at=pd.Timestamp("2026-10-02 09:30"),
            symbol=None,
            timeframe=None,
            indicators=(),
            chart_detected=False,
            candle_observation=CandleObservation(),
            confidence=ScreenConfidence(overall=0),
        )
