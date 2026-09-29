"""Execute a controlled live-market paper trading experiment.

Connects market candles into the complete Strategy -> Risk -> Paper execution
pipeline, tracking open positions against subsequent candles until Target, Stop,
or Session Close, and automatically terminates once the specified target
completed trades (e.g. 10 trades) are reached.

Example:
    python scripts/trading/run_live_paper.py \
        --symbol RELIANCE \
        --target-trades 10 \
        --experiment-id PAPER-LIVE-001 \
        --output-dir paper/sessions
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd

from trading.paper.live_loop import (
    LivePaperEngine,
    LivePaperSessionConfig,
    LivePaperSessionResult,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a controlled live-market paper trading experiment."
    )
    parser.add_argument("--symbol", default="RELIANCE", help="Trading symbol (e.g. RELIANCE)")
    parser.add_argument(
        "--target-trades",
        type=int,
        default=10,
        help="Number of completed trades before session concludes (default: 10)",
    )
    parser.add_argument(
        "--experiment-id",
        default="PAPER-LIVE-001",
        help="Unique identifier for this empirical campaign",
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        help="Optional parquet/csv file containing historical 5m candles to replay",
    )
    parser.add_argument(
        "--initial-equity",
        type=float,
        default=100_000.0,
        help="Simulated starting capital in INR (default: 100,000.0)",
    )
    parser.add_argument(
        "--output-dir",
        default="paper/sessions",
        help="Directory where immutable evidence bundle is saved",
    )
    parser.add_argument(
        "--stop-loss-pct",
        type=float,
        default=0.010,
        help="Stop loss distance fraction (default: 0.010 = 1.0%%)",
    )
    parser.add_argument(
        "--take-profit-pct",
        type=float,
        default=0.020,
        help="Take profit distance fraction (default: 0.020 = 2.0%%)",
    )
    return parser


def generate_synthetic_stream(symbol: str, count: int = 150) -> list[dict]:
    """Generate realistic 5-minute intraday candles for testing and validation."""
    candles = []
    base_price = 100.0
    start_ts = pd.Timestamp("2026-09-29 09:15:00+05:30")
    for i in range(count):
        ts = start_ts + pd.Timedelta(minutes=5 * i)
        # Oscillate price to trigger multiple entries and exits
        wave = 1.5 * ((i % 12) - 6) / 6.0
        open_p = round(base_price + wave, 2)
        high_p = round(open_p + 1.20, 2)
        low_p = round(open_p - 1.20, 2)
        close_p = round(open_p + (0.50 if i % 2 == 0 else -0.50), 2)
        vol = 5000.0 + (i * 200.0)
        candles.append({
            "timestamp": ts,
            "symbol": symbol,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": vol,
        })
    return candles


def run_experiment(args: argparse.Namespace) -> LivePaperSessionResult:
    config = LivePaperSessionConfig(
        experiment_id=args.experiment_id,
        target_trades=args.target_trades,
        symbol=args.symbol.strip().upper(),
        initial_equity=args.initial_equity,
        output_dir=Path(args.output_dir),
        stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=args.take_profit_pct,
    )

    engine = LivePaperEngine(config)

    print("=" * 64)
    print("STOCK_BOT — LIVE-MARKET PAPER EXPERIMENT")
    print("=" * 64)
    print(f"Experiment ID    : {config.experiment_id}")
    print(f"Symbol           : {config.symbol}")
    print(f"Target Trades    : {config.target_trades}")
    print(f"Initial Equity   : ₹{config.initial_equity:,.2f}")
    print(f"Broker Orders    : DISABLED (FAIL-CLOSED)")
    print("=" * 64)

    if args.input_path:
        input_path = Path(args.input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Replay input file does not exist: {input_path}")
        print(f"[REPLAY] Loading candles from {input_path}...")
        df = pd.read_parquet(input_path) if input_path.suffix == ".parquet" else pd.read_csv(input_path)
        candles = df.to_dict(orient="records")
    else:
        print("[STREAM] Initializing candle sequence for experiment validation...")
        candles = generate_synthetic_stream(config.symbol, count=150)

    print(f"[STREAM] Feeding {len(candles)} candles to LivePaperEngine...")
    result = engine.run_candles(candles)

    print("\n" + result.report_text + "\n")
    print(f"Session Evidence Fingerprint: {result.session_fingerprint}")
    if result.output_path:
        print(f"Evidence Bundle Saved At    : {result.output_path}")
    print("=" * 64)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        run_experiment(args)
        return 0
    except Exception as exc:
        print(f"[ERROR] Live paper experiment failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
