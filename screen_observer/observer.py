"""Screen Observer orchestration for S00-S12."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from .capture import CaptureBackend, MSSCaptureBackend
from .candles import parse_candle_evidence
from .confidence import calculate_screen_confidence
from .contracts import ScreenObservation, VisualContext, WindowObservation
from .context import build_visual_context
from .detection import TradingViewRegionDetector, WindowDetector
from .indicators import detect_indicator_evidence
from .ocr import ocr_image
from .reconciliation import ReconciliationResult
from .timeframe import detect_timeframe_evidence
from .vision import detect_indicators, detect_symbol, detect_timeframe


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
        capture_region = (
            (target.left, target.top, target.width, target.height)
            if target is not None else None
        )
        image = self.capture_backend.capture(capture_region)

        ocr_result = ocr_image(image, observed_at=ts)
        text_lines = ocr_result.lines

        chart = self.region_detector.detect(
            target,
            image=image,
            ocr_result=ocr_result,
        )

        symbol, symbol_conf = detect_symbol(text_lines)
        timeframe, timeframe_conf = detect_timeframe(text_lines)
        indicators, indicator_conf = detect_indicators(text_lines)

        timeframe_evidence = detect_timeframe_evidence(ocr_result.tokens)
        if timeframe_evidence is not None:
            timeframe = timeframe_evidence.value
            timeframe_conf = timeframe_evidence.confidence

        indicator_evidence = detect_indicator_evidence(ocr_result.tokens)
        if indicator_evidence:
            indicators = tuple(item.name for item in indicator_evidence)
            indicator_conf = max(item.confidence for item in indicator_evidence)

        chart_region_local = None
        if chart.detected and target is not None:
            chart_region_local = (
                max(0, int(chart.left) - target.left),
                max(0, int(chart.top) - target.top),
                int(chart.width),
                int(chart.height),
            )

        candle_evidence = parse_candle_evidence(
            image,
            chart_region=chart_region_local,
        )
        from .contracts import CandleObservation
        candles = CandleObservation(
            bullish=candle_evidence.bullish,
            bearish=candle_evidence.bearish,
            confidence=candle_evidence.confidence,
        )

        ocr_conf = ocr_result.confidence / 100.0 if ocr_result.available else 0.0
        chart_conf = chart.confidence
        confidence = calculate_screen_confidence(
            chart=chart_conf,
            ocr=ocr_conf,
            symbol=symbol_conf,
            timeframe=timeframe_conf,
            indicators=indicator_conf,
            candles=candles.confidence,
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
            ocr_result=ocr_result,
            candle_evidence=candle_evidence,
            indicator_evidence=indicator_evidence,
            timeframe_evidence=timeframe_evidence,
        )

    @staticmethod
    def to_visual_context(observation: ScreenObservation) -> VisualContext:
        return build_visual_context(observation)
