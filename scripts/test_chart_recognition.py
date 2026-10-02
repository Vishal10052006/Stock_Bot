"""S05 live smoke test: PipeWire frame -> visual chart recognition."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from screen_observer.contracts import WindowObservation
from screen_observer.detection import TradingViewRegionDetector
from screen_observer.ocr import ocr_image
from screen_observer.pipewire_capture import PipeWireFrameCapture
from screen_observer.wayland_portal import WaylandScreenCastPortal


async def main() -> None:
    print("=" * 64)
    print("STOCK BOT - S05 WAYLAND CHART RECOGNITION SMOKE TEST")
    print("=" * 64)

    portal = WaylandScreenCastPortal()
    capture = None

    try:
        print("\n[1/6] Connecting to XDG ScreenCast portal...")
        await portal.connect()
        print("Portal connection: OK")

        print("\n[2/6] Creating ScreenCast session...")
        await portal.create_session()
        print("Session: OK")

        print("\n[3/6] Selecting TradingView/browser WINDOW...")
        print("Select the TradingView/browser window in GNOME.")
        await portal.select_sources(types=2)
        print("Source selection: OK")

        print("\n[4/6] Starting ScreenCast and PipeWire capture...")
        result = await portal.start()
        if not result.streams:
            raise RuntimeError("ScreenCast returned no streams")
        stream = result.streams[0]
        fd = await portal.open_pipewire_remote()
        capture = PipeWireFrameCapture(fd, stream.node_id)
        capture.start()
        print(f"Capture: PLAYING (node={stream.node_id})")

        print("\n[5/6] Waiting for one RGB frame...")
        frame = None
        deadline = asyncio.get_running_loop().time() + 10
        while frame is None and asyncio.get_running_loop().time() < deadline:
            try:
                frame = capture.read_frame(timeout_seconds=1.0)
            except Exception:
                pass
        if frame is None:
            raise RuntimeError("Timed out waiting for PipeWire frame")
        print(f"Frame: {frame.width}x{frame.height} {frame.format}")

        window = WindowObservation(
            title="Selected TradingView/browser window",
            application="wayland",
            left=0,
            top=0,
            width=frame.width,
            height=frame.height,
        )
        ocr_result = ocr_image(
            frame.frame,
            observed_at=frame.observed_at,
        )

        print("\n[6/6] Running S05 visual chart recognition...")
        chart = TradingViewRegionDetector().detect(
            window,
            image=frame.frame,
            ocr_result=ocr_result,
        )

        print(f"Chart detected : {chart.detected}")
        print(f"Chart region   : ({chart.left}, {chart.top}, {chart.width}, {chart.height})")
        print(f"Chart confidence: {chart.confidence:.4f}")
        print(f"OCR status     : {ocr_result.status}")
        print(f"OCR tokens     : {len(ocr_result.tokens)}")

        if not chart.detected:
            raise RuntimeError(
                "S05 did not detect a chart in the selected TradingView/browser window"
            )

        print("\nS05 CHART RECOGNITION SMOKE TEST: SUCCESS")
    finally:
        if capture is not None:
            capture.stop()
        await portal.close()
        print("ScreenCast session closed.")


if __name__ == "__main__":
    asyncio.run(main())
