"""S09 visual-context builder."""

from __future__ import annotations

from .contracts import ScreenObservation, VisualContext


VISUAL_CONTEXT_VERSION = "1"


def build_visual_context(observation: ScreenObservation) -> VisualContext:
    return VisualContext(
        observed_at=observation.observed_at,
        symbol=observation.symbol,
        timeframe=observation.timeframe,
        indicators=observation.indicators,
        chart_detected=observation.chart.detected,
        candle_observation=observation.candles,
        confidence=observation.confidence,
        provenance={
            "source": "desktop_screen",
            "authority": "OBSERVATION_ONLY",
            "module": "screen_observer",
            "context_version": VISUAL_CONTEXT_VERSION,
        },
    )
