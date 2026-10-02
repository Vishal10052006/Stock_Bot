"""Real-screen validation harness for Screen Observer vision.

This module evaluates one supplied screenshot without making trading decisions.
It reports observable evidence from S04-S08 so thresholds can be tuned against
real TradingView screenshots.

The market feed remains authoritative; this is a diagnostic/validation tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .vision import (
    detect_indicators,
    detect_symbol,
    detect_timeframe,
    ocr,
    parse_candles,
    recognize_chart,
)


def validate_image(image: Any, *, source: str | None = None) -> dict[str, Any]:
    """Run S04-S08 vision checks and return a JSON-serializable report."""
    text_lines = ocr(image)
    symbol, symbol_confidence = detect_symbol(text_lines)
    timeframe, timeframe_confidence = detect_timeframe(text_lines)
    indicators, indicator_confidence = detect_indicators(text_lines)
    chart_detected, chart_confidence = recognize_chart(image)
    candles = parse_candles(image)

    try:
        width, height = image.size
    except AttributeError:
        height, width = image.shape[:2]

    return {
        "source": source,
        "image": {"width": int(width), "height": int(height)},
        "ocr": {
            "lines": list(text_lines),
            "line_count": len(text_lines),
        },
        "symbol": {
            "value": symbol,
            "confidence": symbol_confidence,
        },
        "timeframe": {
            "value": timeframe,
            "confidence": timeframe_confidence,
        },
        "indicators": {
            "values": list(indicators),
            "confidence": indicator_confidence,
        },
        "chart": {
            "detected": chart_detected,
            "confidence": chart_confidence,
        },
        "candles": {
            "bullish": candles.bullish,
            "bearish": candles.bearish,
            "total": candles.bullish + candles.bearish,
            "confidence": candles.confidence,
        },
    }


def validate_file(path: str | Path) -> dict[str, Any]:
    """Load a screenshot with Pillow and validate it."""
    from PIL import Image

    image_path = Path(path).expanduser().resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"image not found: {image_path}")

    with Image.open(image_path) as image:
        return validate_image(image, source=str(image_path))


# S13 evidence-quality validation

from dataclasses import dataclass

from .contracts import ScreenObservation
from .timeframe import normalize_timeframe


@dataclass(frozen=True, slots=True)
class ScreenValidationResult:
    """Deterministic quality result for one screen observation."""

    valid: bool
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        return self.valid


def validate_screen_observation(
    observation: ScreenObservation,
    *,
    minimum_chart_confidence: float = 0.45,
    minimum_overall_confidence: float = 0.55,
    require_chart: bool = True,
    require_timeframe: bool = False,
    require_symbol: bool = False,
) -> ScreenValidationResult:
    """Validate evidence without correcting or inventing observations."""

    if not 0.0 <= minimum_chart_confidence <= 1.0:
        raise ValueError("minimum_chart_confidence must be in [0, 1]")
    if not 0.0 <= minimum_overall_confidence <= 1.0:
        raise ValueError("minimum_overall_confidence must be in [0, 1]")

    reasons: list[str] = []
    warnings: list[str] = []

    chart = observation.chart
    if require_chart and not chart.detected:
        reasons.append("SCREEN_CHART_NOT_DETECTED")
    if chart.detected:
        if chart.width is None or chart.height is None or chart.width <= 0 or chart.height <= 0:
            reasons.append("SCREEN_CHART_REGION_INVALID")
        if chart.confidence < minimum_chart_confidence:
            reasons.append("SCREEN_CHART_CONFIDENCE_LOW")

    confidence = observation.confidence
    if confidence.overall < minimum_overall_confidence:
        reasons.append("SCREEN_OVERALL_CONFIDENCE_LOW")
    if require_chart and confidence.chart < minimum_chart_confidence:
        reasons.append("SCREEN_CONFIDENCE_CHART_LOW")

    if require_symbol and not observation.symbol:
        reasons.append("SCREEN_SYMBOL_MISSING")
    if observation.symbol is not None:
        symbol = observation.symbol.strip().upper()
        if not symbol or len(symbol) > 24:
            reasons.append("SCREEN_SYMBOL_INVALID")

    if require_timeframe and not observation.timeframe:
        reasons.append("SCREEN_TIMEFRAME_MISSING")
    if observation.timeframe is not None:
        normalized = normalize_timeframe(observation.timeframe)
        if normalized is None:
            reasons.append("SCREEN_TIMEFRAME_INVALID")
        elif observation.timeframe != normalized:
            warnings.append("SCREEN_TIMEFRAME_NOT_CANONICAL")

    candle = observation.candles
    total = candle.bullish + candle.bearish
    if candle.bullish < 0 or candle.bearish < 0:
        reasons.append("SCREEN_CANDLE_COUNT_INVALID")

    if chart.detected and chart.width is not None and total > max(1, chart.width // 2):
        reasons.append("SCREEN_CANDLE_DENSITY_IMPLAUSIBLE")

    if observation.candle_evidence is not None:
        evidence = observation.candle_evidence
        if evidence.total != total:
            reasons.append("SCREEN_CANDLE_EVIDENCE_INCONSISTENT")

    if observation.timeframe_evidence is not None:
        evidence = observation.timeframe_evidence
        normalized = normalize_timeframe(evidence.value)
        if normalized is None:
            reasons.append("SCREEN_TIMEFRAME_EVIDENCE_INVALID")
        elif normalized != evidence.value:
            reasons.append("SCREEN_TIMEFRAME_EVIDENCE_NONCANONICAL")

    if observation.ocr_result is not None:
        status = observation.ocr_result.status
        if status not in {"ok", "unavailable", "failed"}:
            reasons.append("SCREEN_OCR_STATUS_INVALID")
        if status in {"failed", "unavailable"}:
            warnings.append(f"SCREEN_OCR_{status.upper()}")

    return ScreenValidationResult(
        valid=not reasons,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
    )
