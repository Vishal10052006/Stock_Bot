"""Boot the STOCK_BOT M20 real-market SHADOW runtime.

The process consumes real Upstox market data but has no live broker-order
submission path. Stop with Ctrl-C after collecting the required evidence.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from runtime.shadow_runtime import ShadowRuntime


def _symbols_from_environment() -> tuple[str, ...] | None:
    """Return an optional restricted symbol set from the environment."""
    raw = os.getenv("STOCK_BOT_SYMBOLS", "").strip()
    if not raw:
        return None
    return tuple(
        symbol.strip().upper()
        for symbol in raw.split(",")
        if symbol.strip()
    )


def _build_parser() -> argparse.ArgumentParser:
    """Create the M20 command-line interface."""
    parser = argparse.ArgumentParser(
        description="STOCK_BOT real-market SHADOW feed runtime",
    )
    parser.add_argument(
        "--max-candles",
        type=int,
        default=int(os.getenv("STOCK_BOT_MAX_CANDLES", "0")),
        help="stop after this many completed candles; 0 means Ctrl-C",
    )
    return parser


def main() -> int:
    """Run one fail-closed shadow session."""
    args = _build_parser().parse_args()

    if args.max_candles < 0:
        print("--max-candles must be >= 0", file=sys.stderr)
        return 2

    try:
        runtime = ShadowRuntime.from_environment(
            symbols=_symbols_from_environment(),
        )
    except Exception as exc:
        print(f"[M20][BOOT][FAIL] {exc}", file=sys.stderr)
        return 2

    print("=" * 68)
    print("STOCK_BOT — M20.1 + M20.2 REAL-MARKET SHADOW RUNTIME")
    print("=" * 68)
    print(f"mode                         : {runtime.safety.mode}")
    print(
        "live broker order submission : "
        f"{runtime.safety.live_broker_order_submission}"
    )
    print(f"symbols                      : {', '.join(runtime.config.symbols)}")
    print(f"candle timeframe             : {runtime.config.timeframe_minutes} min")
    print(f"started                      : {datetime.now(timezone.utc).isoformat()}")
    print("=" * 68)

    try:
        runtime.start()
        print("[M20][FEED] Upstox connected and subscription active.")

        for candle in runtime.candles():
            print(
                "[M20][CANDLE] "
                f"{candle.timestamp.isoformat()} "
                f"{candle.symbol} "
                f"O={candle.open:.2f} "
                f"H={candle.high:.2f} "
                f"L={candle.low:.2f} "
                f"C={candle.close:.2f} "
                f"V={candle.volume:.0f}"
            )

            if (
                args.max_candles
                and runtime.health.candles_completed >= args.max_candles
            ):
                break

    except KeyboardInterrupt:
        print("\n[M20][STOP] Keyboard interrupt received.")
    except Exception as exc:
        print(f"[M20][RUNTIME][FAIL] {exc}", file=sys.stderr)
        return 1
    finally:
        runtime.stop()

    print("[M20][EVIDENCE]")
    for key, value in runtime.evidence().items():
        print(f"  {key}: {value}")

    print("[M20][SAFETY] live broker order submission = FALSE")
    print("[M20][STATUS] SHADOW SESSION COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
