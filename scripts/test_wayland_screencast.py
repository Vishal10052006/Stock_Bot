from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from screen_observer.wayland_portal import (
    WaylandScreenCastPortal,
)


async def main() -> None:
    print("=" * 64)
    print("STOCK BOT — WAYLAND SCREENCAST SMOKE TEST")
    print("=" * 64)

    portal = WaylandScreenCastPortal(
        persist_mode=2,
    )

    try:
        print()
        print("[1/4] Connecting to XDG ScreenCast portal...")
        await portal.connect()
        print("      Portal connection: OK")

        print()
        print("[2/4] Creating ScreenCast session...")
        session = await portal.create_session()
        print(f"      Session: {session}")

        print()
        print("[3/4] Requesting WINDOW capture...")
        print()
        print("      GNOME should now ask you to select")
        print("      the window to share.")
        print()
        print("      Select your TradingView/browser window.")
        print()

        await portal.select_sources(
            source_types=2,  # WINDOW
            multiple=False,
            persist_mode=2,
        )

        print("      Source selection: OK")

        print()
        print("[4/4] Starting ScreenCast...")
        result = await portal.start()

        print("      ScreenCast: STARTED")
        print()

        print("STREAMS")
        print("-" * 64)

        for index, stream in enumerate(result.streams, start=1):
            print(f"Stream #{index}")
            print(f"  node_id        : {stream.node_id}")
            print(f"  pipewire_serial: {stream.pipewire_serial}")
            print(f"  properties     : {stream.properties}")
            print()

        if result.restore_token:
            print(
                "Restore token received: YES"
            )
        else:
            print(
                "Restore token received: NO"
            )

        print()
        print("=" * 64)
        print("WAYLAND SCREENCAST PORTAL: SUCCESS")
        print("=" * 64)

        print()
        print("Keeping session alive for 10 seconds...")
        print("The next stage will attach GStreamer/PipeWire.")

        await asyncio.sleep(10)

    except KeyboardInterrupt:
        print()
        print("Interrupted.")

    finally:
        print()
        print("Closing ScreenCast session...")
        await portal.close()
        print("Session closed.")


if __name__ == "__main__":
    asyncio.run(main())
