#!/usr/bin/env python3
"""Run the continuous STOCK_BOT Screen Observer.

This is an observation-only desktop process. It never creates trading orders.
"""

from __future__ import annotations

import argparse
import json
import signal
import threading
from datetime import timedelta

from screen_observer import ScreenEvent, ScreenObserverRuntime


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live Screen Observer")
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="seconds between observations (default: 1.0)",
    )
    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval must be positive")

    stopped = threading.Event()

    def on_event(event: ScreenEvent) -> None:
        context = event.context
        print(
            json.dumps(
                {
                    "event": event.event_type,
                    "observed_at": event.observed_at.isoformat(),
                    "symbol": context.symbol,
                    "timeframe": context.timeframe,
                    "indicators": list(context.indicators),
                    "chart_detected": context.chart_detected,
                    "bullish_candles": context.candle_observation.bullish,
                    "bearish_candles": context.candle_observation.bearish,
                    "confidence": context.confidence.overall,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    runtime = ScreenObserverRuntime(
        interval=timedelta(seconds=args.interval),
        on_event=on_event,
    )

    def shutdown(_signum, _frame) -> None:
        stopped.set()
        runtime.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(
        f"Screen Observer started: interval={args.interval:.2f}s "
        "authority=OBSERVATION_ONLY",
        flush=True,
    )
    runtime.start()

    try:
        while runtime.running and not stopped.wait(0.5):
            pass
    finally:
        runtime.stop()

    print("Screen Observer stopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
