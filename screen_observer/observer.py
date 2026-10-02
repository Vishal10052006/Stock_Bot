"""Screen Observer orchestration.

References:
- Screen Intelligence roadmap S00-S12.
- TRADING_SPECIFICATION.md causality rule.
"""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

from .capture import CaptureBackend, MSSCaptureBackend
from .contracts import ScreenConfidence, ScreenObservation, VisualContext, WindowObservation
from .detection import TradingViewRegionDetector, WindowDetector
from .vision import (
    build_confidence,
    detect_indicators,
    detect_symbol,
    detect_timeframe,
    ocr,
    parse_candles,
    recognize_chart,
)


class ScreenObserver:
    """Produce immutable visual context; never issue trading actions."""

    def __init__(
        self,
        *,
        capture_backend: CaptureBackend | None = None,
        window_detector: WindowDetector | None = None,
        region_detector: TradingViewRegionDetector | None = None,
    ) -> None:
        self.capture_backend = capture_backend or MSSCaptureBackend()
        self.window_detector = window_detector or WindowDetector()
        self.region_detector = region_detector or TradingViewRegionDetector()

    def observe(
        self,
        *,
        observed_at: pd.Timestamp,
        windows: Iterable[WindowObservation] = (),
    ) -> ScreenObservation:
        ts = pd.Timestamp(observed_at)
        if ts.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")

        windows_tuple = tuple(windows)
        target = self.window_detector.select(windows_tuple)
        chart = self.region_detector.detect(target)

        region = (
            (chart.left, chart.top, chart.width, chart.height)
            if chart.detected
            else None
        )
        image = self.capture_backend.capture(region)

        text_lines = ocr(image)
        symbol, symbol_conf = detect_symbol(text_lines)
        timeframe, timeframe_conf = detect_timeframe(text_lines)
        indicators, indicator_conf = detect_indicators(text_lines)
        chart_detected, chart_conf = recognize_chart(image)
        candles = parse_candles(image)

        ocr_conf = 0.75 if text_lines else 0.0
        overall = build_confidence(
            chart=max(chart.confidence, chart_conf if chart_detected else 0.0),
            ocr_confidence=ocr_conf,
            symbol=symbol_conf,
            timeframe=timeframe_conf,
            indicators=indicator_conf,
            candles=candles.confidence,
        )

        confidence = ScreenConfidence(
            overall=overall,
            symbol=symbol_conf,
            timeframe=timeframe_conf,
            chart=max(chart.confidence, chart_conf if chart_detected else 0.0),
            candles=candles.confidence,
            indicators=indicator_conf,
            ocr=ocr_conf,
        )

        return ScreenObservation(
            observed_at=ts,
            image=image,
            windows=windows_tuple,
            target_window=target,
            chart=chart,
            ocr_text=text_lines,
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicators,
            candles=candles,
            confidence=confidence,
        )

    @staticmethod
    def to_visual_context(observation: ScreenObservation) -> VisualContext:
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
            },
        )
