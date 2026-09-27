"""Command-line runtime boundary for STOCK_BOT modes.

This module gives the repository a real mode-aware entry point while preserving
the existing trading authorities.

Modes:
    CEO demo  - legacy orchestration demo.
    shadow    - real Upstox market-feed -> validation -> 5-minute candle path.
    paper     - authoritative Strategy -> Risk -> Paper execution on an explicit
                frozen strategy-ready dataset.
    readiness - fail-closed structural live-readiness report.
    live      - explicitly refuses live broker activation while repository
                live execution remains locked.

The runtime never fabricates model artifacts, readiness evidence, or broker
authorization.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pandas as pd

from execution.readiness import LiveReadinessGate, LiveReadinessInput
from execution.safety import IndependentSafetyGate, SafetyState
from market.candles.aggregator import CandleAggregator
from market.data.ingestion.providers.upstox.config import UpstoxFeedConfig
from market.data.ingestion.providers.upstox.feed import UpstoxMarketFeed
from market.data.ingestion.providers.upstox.generated import MarketDataFeedV3_pb2
from market.data.ingestion.providers.upstox.instrument_mapper import UpstoxInstrumentMapper
from market.data.metrics import DataQualityMetrics
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from market.data.validation import MarketEventValidator
from trading.paper.decision_loop import PaperDecisionLoop


class RuntimeMode(str, Enum):
    """Supported STOCK_BOT runtime modes."""

    CEO_DEMO = "ceo-demo"
    SHADOW = "shadow"
    PAPER = "paper"
    READINESS = "readiness"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Validated configuration for one CLI invocation."""

    mode: RuntimeMode
    symbol: str = "RELIANCE"
    candles: int = 1
    input_path: Path | None = None
    quantity: float = 1.0
    price_column: str = "close"
    confirm_live: bool = False

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.candles <= 0:
            raise ValueError("candles must be a positive integer")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if not self.price_column.strip():
            raise ValueError("price_column must not be empty")


def build_parser() -> argparse.ArgumentParser:
    """Build the public STOCK_BOT command-line interface."""
    parser = argparse.ArgumentParser(description="STOCK_BOT runtime entry point.")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in RuntimeMode],
        default=RuntimeMode.CEO_DEMO.value,
        help="Runtime mode. Default preserves the legacy CEO demo.",
    )
    parser.add_argument("--symbol", default="RELIANCE")
    parser.add_argument(
        "--candles",
        type=int,
        default=1,
        help="Completed 5-minute candles before shadow mode exits.",
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        help="Frozen strategy-ready parquet for paper mode.",
    )
    parser.add_argument("--quantity", type=float, default=1.0)
    parser.add_argument("--price-column", default="close")
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Request live mode; repository lock still applies.",
    )
    return parser


def _config_from_args(args: argparse.Namespace) -> RuntimeConfig:
    """Translate argparse output into immutable runtime configuration."""
    return RuntimeConfig(
        mode=RuntimeMode(args.mode),
        symbol=args.symbol.strip().upper(),
        candles=args.candles,
        input_path=Path(args.input_path) if args.input_path else None,
        quantity=args.quantity,
        price_column=args.price_column,
        confirm_live=args.confirm_live,
    )


def run_ceo_demo() -> int:
    """Preserve the historical CEO demo behind an explicit runtime mode."""
    import asyncio
    from core.ceo import CEO

    async def _run() -> None:
        ceo = CEO()
        for index in range(3):
            print(f"\nRUN {index + 1}")
            await ceo.act("analyze stock: RELIANCE")

    asyncio.run(_run())
    return 0


def run_shadow(config: RuntimeConfig) -> int:
    """Run Upstox feed -> validation -> 5-minute aggregation without orders."""
    feed_config = UpstoxFeedConfig.from_env()
    mapper = UpstoxInstrumentMapper.from_env()
    feed = UpstoxMarketFeed(
        feed_config,
        mapper,
        protobuf_module=MarketDataFeedV3_pb2,
    )
    pipeline = RealtimeMarketDataPipeline(
        feed=feed,
        validator=MarketEventValidator(),
        aggregator=CandleAggregator(timeframe_minutes=5),
        metrics=DataQualityMetrics(),
    )
    produced = 0
    try:
        print("=" * 72)
        print("STOCK BOT — SHADOW MODE")
        print("=" * 72)
        print(f"Symbol              : {config.symbol}")
        print("Timeframe            : 5 minutes")
        print("Broker orders        : DISABLED")
        print("Purpose              : live market-data observation")
        print("=" * 72)
        pipeline.start([config.symbol])
        for candle in pipeline.run():
            produced += 1
            print(
                f"[SHADOW] {candle.symbol} {candle.timestamp.isoformat()} "
                f"O={candle.open} H={candle.high} L={candle.low} "
                f"C={candle.close} V={candle.volume}"
            )
            if produced >= config.candles:
                break
        snapshot = pipeline.metrics.snapshot()
        print("-" * 72)
        print(f"Completed candles   : {produced}")
        print(f"Events received     : {snapshot.events_received}")
        print(f"Events accepted     : {snapshot.events_accepted}")
        print(f"Events rejected     : {snapshot.events_rejected}")
        print(f"Connection failures : {snapshot.connection_failures}")
        print(f"Reconnect attempts  : {snapshot.reconnect_attempts}")
        print(f"Missing-data gaps   : {snapshot.missing_data_gaps}")
        print("-" * 72)
        return 0 if produced >= config.candles else 1
    finally:
        pipeline.stop()


def _load_paper_rows(config: RuntimeConfig) -> pd.DataFrame:
    """Load an explicit frozen strategy-ready paper dataset."""
    if config.input_path is None:
        raise ValueError(
            "paper mode requires --input pointing to a frozen strategy-ready parquet"
        )
    if not config.input_path.exists():
        raise FileNotFoundError(
            f"paper input does not exist: {config.input_path}"
        )
    rows = pd.read_parquet(config.input_path)
    required = {
        "timestamp",
        "symbol",
        "close",
        "regime",
        "regime_probability",
        "vwap_distance_pct",
        "rvol_20",
        "higher_high",
        "higher_low",
        "lower_low",
        "lower_high",
    }
    missing = sorted(required - set(rows.columns))
    if missing:
        raise ValueError(
            f"paper input is missing required strategy columns: {missing}"
        )
    if rows.empty:
        raise ValueError("paper input is empty")
    rows = rows.copy()
    rows["timestamp"] = pd.to_datetime(
        rows["timestamp"], utc=True, errors="raise"
    )
    rows["symbol"] = rows["symbol"].astype(str).str.strip().str.upper()
    if rows.duplicated(["timestamp", "symbol"]).any():
        raise ValueError(
            "paper input contains duplicate timestamp/symbol observations"
        )
    if not rows["timestamp"].is_monotonic_increasing:
        raise ValueError(
            "paper input must already be chronological; refusing to reorder"
        )
    return rows


def run_paper(config: RuntimeConfig) -> int:
    """Run Strategy -> Risk -> PaperTradingRuntime on explicit rows."""
    rows = _load_paper_rows(config)
    result = PaperDecisionLoop().run(
        rows,
        price_column=config.price_column,
        quantity=config.quantity,
    )
    orders = result.orders
    filled = sum(order.status.value == "FILLED" for order in orders)
    print("=" * 72)
    print("STOCK BOT — PAPER MODE")
    print("=" * 72)
    print(f"Input rows          : {len(rows):,}")
    print(f"Decision steps      : {len(result.steps):,}")
    print(f"Paper orders        : {len(orders):,}")
    print(f"Filled paper orders : {filled:,}")
    print(f"Run ID              : {result.run_id}")
    print("Broker orders       : DISABLED")
    print("=" * 72)
    return 0


def run_readiness() -> int:
    """Print the current fail-closed live-readiness state."""
    gates = LiveReadinessInput(
        historical_data_validated=False,
        indicators_validated=False,
        features_leakage_safe=False,
        labels_validated=False,
        baseline_validated=False,
        model_validated=False,
        realistic_backtest_validated=False,
        leakage_audit_passed=False,
        oos_validated=False,
        walk_forward_validated=False,
        paper_evidence_validated=False,
        risk_controls_validated=False,
        monitoring_validated=False,
        kill_switch_validated=False,
        broker_integration_validated=False,
        reconciliation_validated=False,
        compliance_verified_current=False,
    )
    report = LiveReadinessGate().evaluate(gates)
    safety = IndependentSafetyGate().evaluate(
        SafetyState(live_execution_enabled=False)
    )
    print("=" * 72)
    print("STOCK BOT — LIVE READINESS")
    print("=" * 72)
    print(f"READY                : {report.ready}")
    print(f"SAFETY BLOCK         : {safety.block.value}")
    print(f"FAILED GATES         : {len(report.failed_gates)}")
    for gate in report.failed_gates:
        print(f"  - {gate}")
    print("-" * 72)
    print("Live broker execution: LOCKED")
    print("=" * 72)
    return 0 if report.ready and safety.allowed else 2


def run_live(config: RuntimeConfig) -> int:
    """Enter live mode without bypassing the repository lock."""
    if not config.confirm_live:
        print("[LIVE] BLOCKED: live mode requires explicit --confirm-live.")
        return 2
    print("=" * 72)
    print("STOCK BOT — LIVE MODE")
    print("=" * 72)
    print("LIVE ORDER SUBMISSION: LOCKED")
    print("Reason: current repository keeps live broker execution fail-closed.")
    print("Run `python main.py --mode readiness` to inspect blocked gates.")
    print("=" * 72)
    return 3


def dispatch(config: RuntimeConfig) -> int:
    """Dispatch exactly one runtime mode."""
    if config.mode is RuntimeMode.CEO_DEMO:
        return run_ceo_demo()
    if config.mode is RuntimeMode.SHADOW:
        return run_shadow(config)
    if config.mode is RuntimeMode.PAPER:
        return run_paper(config)
    if config.mode is RuntimeMode.READINESS:
        return run_readiness()
    if config.mode is RuntimeMode.LIVE:
        return run_live(config)
    raise ValueError(f"unsupported runtime mode: {config.mode.value}")


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and execute one runtime mode."""
    args = build_parser().parse_args(argv)
    return dispatch(_config_from_args(args))


__all__ = [
    "RuntimeConfig",
    "RuntimeMode",
    "build_parser",
    "dispatch",
    "main",
    "run_ceo_demo",
    "run_live",
    "run_paper",
    "run_readiness",
    "run_shadow",
]
