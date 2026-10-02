"""S06-S13 live Screen Intelligence smoke test.

Validates the full observation-only chain on a real Wayland/TradingView capture.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from screen_observer.analysis import build_screen_analysis_context
from screen_observer.candles import parse_candle_evidence
from screen_observer.confidence import calculate_screen_confidence
from screen_observer.contracts import CandleObservation, ScreenObservation, WindowObservation
from screen_observer.detection import TradingViewRegionDetector
from screen_observer.indicators import detect_indicator_evidence
from screen_observer.ocr import ocr_image
from screen_observer.pipewire_capture import PipeWireFrameCapture
from screen_observer.timeframe import detect_timeframe_evidence
from screen_observer.validation import validate_screen_observation\nfrom screen_observer.wayland_portal import WaylandScreenCastPortal


async def main() -> None:
    print("=" * 68)
    print("STOCK BOT - S06-S13 SCREEN INTELLIGENCE SMOKE TEST")
    print("=" * 68)

    portal = WaylandScreenCastPortal()
    capture = None

    try:
        print("\n[1/8] Connecting to ScreenCast portal...")
        await portal.connect()
        await portal.create_session()
        await portal.select_sources(source_types=2)
        result = await portal.start()
        stream = result.streams[0]
        fd = await portal.open_pipewire_remote()
        capture = PipeWireFrameCapture(fd, stream.node_id)
        capture.start()
        print(f"Capture: PLAYING (node={stream.node_id})")

        print("\n[2/8] Waiting for RGB frame...")
        frame = capture.read_frame(timeout_seconds=5.0)
        print(f"Frame: {frame.width}x{frame.height} {frame.format}")

        window = WindowObservation(
            title="Selected TradingView/browser window",
            application="wayland",
            left=0,
            top=0,
            width=frame.width,
            height=frame.height,
        )

        print("\n[3/8] S05 chart region...")
        ocr_result = ocr_image(frame.frame, observed_at=frame.observed_at)
        chart = TradingViewRegionDetector().detect(
            window, image=frame.frame, ocr_result=ocr_result
        )
        print(f"Chart: {chart.detected} confidence={chart.confidence:.4f}")

        if not chart.detected:
            raise RuntimeError("S05 chart detection failed")

        chart_region = (
            int(chart.left), int(chart.top),
            int(chart.width), int(chart.height)
        )

        print("\n[4/8] S06 candle evidence...")
        candles = parse_candle_evidence(frame.frame, chart_region=chart_region)
        print(
            f"Candles: bullish={candles.bullish} bearish={candles.bearish} "
            f"total={candles.total} confidence={candles.confidence:.4f}"
        )

        print("\n[5/8] S07 indicator evidence...")
        indicators = detect_indicator_evidence(ocr_result.tokens)
        print(
            "Indicators:",
            ", ".join(item.name for item in indicators) if indicators else "none",
        )

        print("\n[6/8] S08 timeframe evidence...")
        timeframe = detect_timeframe_evidence(ocr_result.tokens)
        print(
            f"Timeframe: {timeframe.value if timeframe else 'none'} "
            f"confidence={timeframe.confidence if timeframe else 0.0:.4f}"
        )

        from screen_observer.vision import detect_symbol
        symbol, symbol_conf = detect_symbol(ocr_result.lines)
        timeframe_value = timeframe.value if timeframe else None
        timeframe_conf = timeframe.confidence if timeframe else 0.0
        indicator_names = tuple(item.name for item in indicators)
        indicator_conf = max((item.confidence for item in indicators), default=0.0)
        candle_obs = CandleObservation(
            bullish=candles.bullish,
            bearish=candles.bearish,
            confidence=candles.confidence,
        )

        confidence = calculate_screen_confidence(
            chart=chart.confidence,
            ocr=ocr_result.confidence / 100.0 if ocr_result.available else 0.0,
            symbol=symbol_conf,
            timeframe=timeframe_conf,
            indicators=indicator_conf,
            candles=candles.confidence,
        )

        observation = ScreenObservation(
            observed_at=frame.observed_at,
            image=frame.frame,
            windows=(window,),
            target_window=window,
            chart=chart,
            ocr_text=ocr_result.lines,
            symbol=symbol,
            timeframe=timeframe_value,
            indicators=indicator_names,
            candles=candle_obs,
            confidence=confidence,
            ocr_result=ocr_result,
            candle_evidence=candles,
            indicator_evidence=indicators,
            timeframe_evidence=timeframe,
        )

        print("\n[7/9] S09 context + S10 reconciliation + S11 confidence...")
        decision_ts = frame.observed_at
        context = build_screen_analysis_context(
            observation,
            market_symbol=symbol or "UNKNOWN",
            market_timeframe=timeframe_value or "5m",
            decision_timestamp=decision_ts,
            max_age_seconds=30.0,
        )
        print(f"Confidence: {confidence.overall:.4f}")
        print(f"Reconciliation: {context.reconciliation_status}")
        print(f"Usable: {context.usable}")

        print("\n[8/9] S12 screen-aware analysis context...")
        print(f"Market symbol: {context.market_symbol}")
        print(f"Screen symbol: {context.screen_symbol}")
        print(f"Indicators: {context.indicators}")
        print(f"Authority: {context.provenance['authority']}")

        print(f"Validation: {\"PASS\" if context.usable else \"FAIL\"}")\n        if context.reconciliation_reasons:\n            print(f"Validation/reconciliation reasons: {context.reconciliation_reasons}")\n\n        if not context.reconciliation_status == "MATCH":
            raise RuntimeError(
                "S10 reconciliation did not match. "
                + ", ".join(context.reconciliation_reasons)
            )

        if not context.usable:\n            raise RuntimeError("S13 validation failed: " + ", ".join(context.reconciliation_reasons))\n\n        print("\nS06-S13 SCREEN INTELLIGENCE SMOKE TEST: SUCCESS")
    finally:
        if capture is not None:
            capture.stop()
        await portal.close()
        print("ScreenCast session closed.")


if __name__ == "__main__":
    asyncio.run(main())
