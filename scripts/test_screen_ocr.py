#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from screen_observer.ocr import ocr_image
from screen_observer.pipewire_capture import PipeWireFrameCapture
from screen_observer.wayland_portal import WaylandScreenCastPortal


async def main() -> None:
    print("=" * 64)
    print("STOCK BOT - S04 WAYLAND SCREEN OCR SMOKE TEST")
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
        await portal.select_sources(source_types=2, multiple=False, persist_mode=2)
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
        deadline = time.monotonic() + 10.0
        frame = None
        while time.monotonic() < deadline:
            frame = capture.read_frame(timeout_seconds=0.5)
            if frame is not None:
                break
        if frame is None:
            raise RuntimeError("No frame received within 10 seconds")

        print(f"Frame: {frame.width}x{frame.height} {frame.format}")

        print("\n[6/6] Running structured Tesseract OCR...")
        result = ocr_image(
            frame.frame,
            observed_at=frame.observed_at,
        )

        print(f"OCR status      : {result.status}")
        print(f"OCR confidence  : {result.confidence:.2f}")
        print(f"OCR token count : {len(result.tokens)}")
        print(f"OCR lines       : {len(result.lines)}")
        for line in result.lines[:20]:
            print(f"  {line}")

        if result.status != "ok":
            raise RuntimeError(result.error or "OCR failed")
        if not result.tokens:
            raise RuntimeError(
                "Tesseract returned no OCR tokens. Keep visible TradingView "
                "text in the selected window and rerun."
            )

        print("\nS04 OCR SMOKE TEST: SUCCESS")

    finally:
        if capture is not None:
            capture.stop()
        await portal.close()
        print("ScreenCast session closed.")


if __name__ == "__main__":
    asyncio.run(main())
