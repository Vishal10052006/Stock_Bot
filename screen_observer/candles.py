"""S06 visual candle parser."""

from __future__ import annotations

from typing import Any

from .evidence import CandleVisualEvidence
from .vision import _as_rgb_array, _color_masks, _count_candle_candidates, recognize_chart


def parse_candle_evidence(
    image: Any,
    *,
    chart_region: tuple[int, int, int, int] | None = None,
) -> CandleVisualEvidence:
    try:
        if chart_region is not None:
            left, top, width, height = (int(v) for v in chart_region)
            if min(left, top) < 0 or width <= 0 or height <= 0:
                return CandleVisualEvidence(chart_region=chart_region)
            rgb = _as_rgb_array(image)
            rgb = rgb[top:top + height, left:left + width]
        else:
            rgb = _as_rgb_array(image)

        if rgb.size == 0:
            return CandleVisualEvidence(chart_region=chart_region)

        detected, _ = recognize_chart(rgb)
        if not detected:
            return CandleVisualEvidence(chart_region=chart_region)

        red_mask, green_mask = _color_masks(rgb)
        bearish = _count_candle_candidates(red_mask)
        bullish = _count_candle_candidates(green_mask)
        total = bullish + bearish
        if total == 0:
            return CandleVisualEvidence(chart_region=chart_region)

        density = min(1.0, total / 20.0)
        class_support = 1.0 if bullish and bearish else 0.65
        confidence = round(0.25 + 0.55 * density + 0.20 * class_support, 4)
        return CandleVisualEvidence(
            bullish=bullish,
            bearish=bearish,
            total=total,
            confidence=min(1.0, confidence),
            chart_region=chart_region,
        )
    except (ImportError, ValueError, TypeError):
        return CandleVisualEvidence(chart_region=chart_region)
