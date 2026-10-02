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
