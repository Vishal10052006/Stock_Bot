import pytest

from screen_observer.confidence import (
    calculate_screen_confidence,
    screen_confidence_state,
    screen_is_usable,
    validate_screen_confidence,
)
from screen_observer.contracts import ScreenConfidence


def test_s15_rejects_out_of_range_component():
    with pytest.raises(ValueError):
        calculate_screen_confidence(
            chart=1.1, ocr=0.8, symbol=0.8, timeframe=0.8, indicators=0.6, candles=0.7
        )


def test_s15_calibration_is_deterministic():
    confidence = calculate_screen_confidence(
        chart=0.9, ocr=0.8, symbol=0.8, timeframe=0.8, indicators=0.6, candles=0.7
    )
    valid, reasons = validate_screen_confidence(confidence)
    assert valid
    assert reasons == ()
    assert screen_confidence_state(confidence) == "TRUSTED"


def test_s15_low_confidence_is_degraded():
    confidence = ScreenConfidence(
        overall=0.54, chart=0.60, ocr=0.5, symbol=0.5,
        timeframe=0.5, indicators=0.5, candles=0.5,
    )
    valid, reasons = validate_screen_confidence(confidence)
    assert not valid
    assert "SCREEN_CONFIDENCE_OVERALL_LOW" in reasons
    assert screen_confidence_state(confidence) == "DEGRADED"
    assert not screen_is_usable(confidence)


def test_s15_low_chart_is_degraded_even_with_high_overall():
    confidence = ScreenConfidence(
        overall=0.9, chart=0.4, ocr=1.0, symbol=1.0,
        timeframe=1.0, indicators=1.0, candles=1.0,
    )
    valid, reasons = validate_screen_confidence(confidence)
    assert not valid
    assert "SCREEN_CONFIDENCE_CHART_LOW" in reasons
    assert screen_confidence_state(confidence) == "DEGRADED"


def test_s15_boundary_is_trusted():
    confidence = ScreenConfidence(
        overall=0.55, chart=0.55, ocr=0.0, symbol=0.0,
        timeframe=0.0, indicators=0.0, candles=0.0,
    )
    valid, _ = validate_screen_confidence(confidence)
    assert valid
    assert screen_is_usable(confidence)


def test_s15_invalid_stored_component_is_rejected():
    confidence = ScreenConfidence(
        overall=0.8, chart=0.8, ocr=0.8, symbol=0.8,
        timeframe=0.8, indicators=0.8, candles=0.8,
    )
    object.__setattr__(confidence, "chart", 1.5)
    assert screen_confidence_state(confidence) == "REJECTED"
