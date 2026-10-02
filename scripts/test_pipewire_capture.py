#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from screen_observer.pipewire_capture import PipeWireFrameCapture
from screen_observer.wayland_portal import WaylandScreenCastPortal


async def main() -> None:
    print("=" * 64)
    print("STOCK BOT - WAYLAND PIPEWIRE FRAME CAPTURE SMOKE TEST")
    print("=" * 64)

    portal = WaylandScreenCastPortal()

    try:
        print("\n[1/5] Connecting to XDG ScreenCast portal...")
        await portal.connect()
        print("Portal connection: OK")

        print("\n[2/5] Creating ScreenCast session...")
        session = await portal.create_session()
        print(f"Session: {session}")

        print("\n[3/5] Requesting WINDOW capture...")
        print("GNOME should now ask you to select")
        print("the window to share.")
        print("Select your TradingView/browser window.")
        await portal.select_sources(
            source_types=2,
            multiple=False,
            persist_mode=2,
        )
        print("Source selection: OK")

        print("\n[4/5] Starting ScreenCast...")
        result = await portal.start()
        if not result.streams:
            raise RuntimeError("ScreenCast returned no streams")

        stream = result.streams[0]
        print("ScreenCast: STARTED")
        print(f"  node_id : {stream.node_id}")
        print(f"  size    : {stream.properties.get('size')}")

        print("\n[5/5] Opening PipeWire remote and waiting for frames...")
        fd = await portal.open_pipewire_remote()
        capture = PipeWireFrameCapture(fd, stream.node_id)

        try:
            capture.start()
            print("GStreamer pipeline: PLAYING")

            deadline = time.monotonic() + 10.0
            first = None
            while time.monotonic() < deadline:
                first = capture.read_frame(timeout_seconds=0.5)
                if first is not None:
                    break

            if first is None:
                raise RuntimeError(
                    "No PipeWire video frame received within 10 seconds"
                )

            print("\nPIPEWIRE FRAME CAPTURE: SUCCESS")
            print(f"Frame shape : {first.frame.shape}")
            print(f"Frame dtype : {first.frame.dtype}")
            print(f"Frame format: {first.format}")
            print(f"Width       : {first.width}")
            print(f"Height      : {first.height}")
            print(f"PTS (ns)    : {first.pts_ns}")

            count = 1
            end = time.monotonic() + 5.0
            while time.monotonic() < end:
                frame = capture.read_frame(timeout_seconds=0.5)
                if frame is not None:
                    count += 1

            print(f"Frames received in validation window: {count}")
            if count < 2:
                raise RuntimeError("Frame stream did not advance")

        finally:
            capture.stop()

    finally:
        print("\nClosing ScreenCast session...")
        await portal.close()
        print("Session closed.")


if __name__ == "__main__":
    asyncio.run(main())
