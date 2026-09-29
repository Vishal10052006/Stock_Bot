"""CLI for real-market, model-only inference.

The command consumes Upstox historical data for causal warmup and then the
Upstox WebSocket for completed 5-minute candles. It never places orders.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ml.prediction.live_runtime import LiveModelRuntime, LiveModelRuntimeConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="STOCK_BOT live model inference")
    parser.add_argument("--symbol", default="RELIANCE")
    parser.add_argument("--benchmark", default="NIFTY50")
    parser.add_argument("--max-predictions", type=int, default=1)
    parser.add_argument(
        "--model-artifact",
        type=Path,
        default=Path("data/models/live_prediction_bundle.pkl"),
    )
    parser.add_argument(
        "--instrument-master",
        type=Path,
        default=Path("data/reference/upstox/NSE.json.gz"),
    )
    parser.add_argument(
        "--prediction-store",
        type=Path,
        default=Path("paper/live_predictions.jsonl"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = LiveModelRuntimeConfig(
        symbol=args.symbol.strip().upper(),
        benchmark=args.benchmark.strip().upper(),
        max_predictions=args.max_predictions,
        model_artifact=args.model_artifact,
        instrument_master=args.instrument_master,
        prediction_store=args.prediction_store,
    )

    runtime = LiveModelRuntime.from_env(config)

    print("=" * 72)
    print("STOCK_BOT — LIVE MODEL INFERENCE")
    print("=" * 72)
    print(f"Symbol              : {config.symbol}")
    print(f"Benchmark           : {config.benchmark}")
    print("Timeframe           : 5 minutes")
    print(f"Model artifact      : {config.model_artifact}")
    print(f"Model version       : {runtime.bundle.provenance.model_version}")
    print(f"Feature version     : {runtime.bundle.provenance.feature_version}")
    print("Market source       : Upstox historical warmup + WebSocket")
    print("Broker orders       : DISABLED")
    print("Trading authority   : NONE")
    print("=" * 72)

    predictions = runtime.run()
    snapshot = runtime.dashboard()

    for prediction in predictions:
        row = prediction.probabilities.iloc[0].to_dict()
        print(
            f"[PREDICTION] {prediction.symbol} "
            f"{prediction.timestamp.isoformat()} "
            f"class={prediction.predicted_class} "
            f"p_long={row['LONG_SUCCESS']:.4f} "
            f"p_short={row['SHORT_SUCCESS']:.4f} "
            f"p_no_edge={row['NO_EDGE']:.4f}"
        )

    print("-" * 72)
    print(json.dumps(snapshot, indent=2, default=str))
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
