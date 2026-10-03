"""Real-market V1 manual-review runtime composition.

This runtime wires the Upstox realtime market feed into the canonical
Market -> Analysis -> Prediction -> Strategy -> Risk -> Human Review path.

It deliberately has no paper account, no virtual equity, and no broker order
submission authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from datetime import timedelta

import pandas as pd

from market.bot.orchestrator import MarketBot, MarketBotConfig
from market.candles.aggregator import CandleAggregator
from market.data.ingestion.providers.upstox.config import UpstoxFeedConfig
from market.data.ingestion.providers.upstox.feed import UpstoxMarketFeed
from market.data.ingestion.providers.upstox.generated import MarketDataFeedV3_pb2
from market.data.ingestion.providers.upstox.instrument_mapper import UpstoxInstrumentMapper
from market.data.metrics import DataQualityMetrics
from market.data.realtime_pipeline import RealtimeMarketDataPipeline
from market.data.validation import MarketEventValidator
from ml.prediction.artifacts import load_phase9_logistic_bundle
from multi_stock.scanner import StockScannerStore
from research.live.runtime import LiveResearchCache, LiveResearchRuntime
from research.providers import RssResearchProvider, pib_provider, rbi_provider
from trading.paper.canonical_live_orchestrator import (
    CanonicalLivePaperConfig,
    CanonicalLivePaperOrchestrator,
)
from trading.paper.upstox_history import UpstoxHistoryProvider
from monitoring.operator_snapshot import OperatorSnapshotWriter
from trading.risk.engine import RiskEngine

from .upstox_risk_context import UpstoxManualRiskContextProvider


def _load_runtime_instrument_mapper() -> UpstoxInstrumentMapper:
    """Load the required Upstox instrument map from runtime configuration."""
    raw_mapping = os.getenv("UPSTOX_INSTRUMENT_MAP", "").strip()
    if not raw_mapping:
        raise ValueError("UPSTOX_INSTRUMENT_MAP is required for live market review")
    try:
        mapping = json.loads(raw_mapping)
    except json.JSONDecodeError as exc:
        raise ValueError("UPSTOX_INSTRUMENT_MAP must contain valid JSON") from exc
    if not isinstance(mapping, dict):
        raise ValueError("UPSTOX_INSTRUMENT_MAP must decode to a JSON object")

    raw_context = os.getenv("UPSTOX_CONTEXT_INSTRUMENT_MAP", "").strip()
    if raw_context:
        try:
            context_mapping = json.loads(raw_context)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "UPSTOX_CONTEXT_INSTRUMENT_MAP must contain valid JSON"
            ) from exc
        if not isinstance(context_mapping, dict):
            raise ValueError(
                "UPSTOX_CONTEXT_INSTRUMENT_MAP must decode to a JSON object"
            )
        mapping.update(context_mapping)

    return UpstoxInstrumentMapper(mapping)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required for V1 manual review")
    return value


def _load_live_risk_context_provider() -> UpstoxManualRiskContextProvider:
    try:
        max_age_seconds = float(
            _required_env("STOCK_BOT_RISK_CONTEXT_MAX_AGE_SECONDS")
        )
        timeout_seconds = float(
            _required_env("STOCK_BOT_RISK_CONTEXT_TIMEOUT_SECONDS")
        )
    except ValueError as exc:
        raise ValueError(
            "STOCK_BOT_RISK_CONTEXT_MAX_AGE_SECONDS and "
            "STOCK_BOT_RISK_CONTEXT_TIMEOUT_SECONDS must be numeric"
        ) from exc

    return UpstoxManualRiskContextProvider.from_env(
        day_state_path=Path(_required_env("STOCK_BOT_RISK_DAY_STATE_PATH")),
        api_base_url=_required_env("STOCK_BOT_RISK_API_BASE_URL"),
        exchange=_required_env("STOCK_BOT_RISK_EXCHANGE"),
        segment=_required_env("STOCK_BOT_RISK_SEGMENT"),
        timezone_name=_required_env("STOCK_BOT_RISK_TIMEZONE"),
        max_age_seconds=max_age_seconds,
        source=_required_env("STOCK_BOT_RISK_CONTEXT_SOURCE"),
        timeout_seconds=timeout_seconds,
        access_token_env=_required_env("STOCK_BOT_RISK_ACCESS_TOKEN_ENV"),
    )


def _load_live_research_providers() -> tuple:
    providers = [rbi_provider(), pib_provider()]
    raw_urls = os.getenv("STOCK_BOT_RESEARCH_RSS_URLS", "").strip()
    if not raw_urls:
        return tuple(providers)

    try:
        configured = json.loads(raw_urls)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "STOCK_BOT_RESEARCH_RSS_URLS must contain valid JSON"
        ) from exc
    if not isinstance(configured, dict):
        raise ValueError(
            "STOCK_BOT_RESEARCH_RSS_URLS must decode to a JSON object"
        )

    for source_id, url in configured.items():
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("research RSS source IDs must be non-empty strings")
        if not isinstance(url, str) or not url.strip():
            raise ValueError(
                f"research RSS URL for {source_id!r} must be a non-empty string"
            )
        providers.append(RssResearchProvider(source_id.strip(), url.strip()))
    return tuple(providers)


@dataclass(frozen=True, slots=True)
class LiveManualReviewConfig:
    """Explicit startup configuration for one V1 manual-review runtime."""

    symbol: str
    benchmark_symbol: str
    model_artifact: Path
    model_sha256: str
    model_version: str
    data_version: str
    feature_version: str
    max_candles: int | None = None
    operator_snapshot_path: Path | None = None

    def __post_init__(self) -> None:
        for name in (
            "symbol",
            "benchmark_symbol",
            "model_version",
            "data_version",
            "feature_version",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")
        if not self.model_artifact:
            raise ValueError("model_artifact must be supplied")
        if len(self.model_sha256) != 64:
            raise ValueError("model_sha256 must be a SHA-256 hex digest")
        if self.max_candles is not None and self.max_candles <= 0:
            raise ValueError("max_candles must be positive when supplied")


def build_live_manual_review_runtime(
    config: LiveManualReviewConfig,
) -> CanonicalLivePaperOrchestrator:
    """Build the V1 real-market review runtime without a paper account."""
    mapper = _load_runtime_instrument_mapper()
    mapper.instrument_key(config.symbol)
    mapper.instrument_key(config.benchmark_symbol)

    feed_config = UpstoxFeedConfig.from_env()
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

    model, preprocessor, calibrator, manifest = load_phase9_logistic_bundle(
        config.model_artifact,
        expected_sha256=config.model_sha256,
    )
    if manifest.model_version != config.model_version:
        raise ValueError("model artifact version does not match runtime model_version")
    if manifest.provenance.model_family != "logistic":
        raise ValueError("V1 manual-review runtime requires a logistic Phase-9 artifact")
    if not manifest.provenance.calibration_version:
        raise ValueError(
            "V1 manual-review runtime requires a calibrated Phase-9 artifact"
        )

    history = UpstoxHistoryProvider.from_env(mapper)

    def stock_history_provider(cutoff):
        return history.candles(config.symbol, cutoff)

    def benchmark_history_provider(cutoff):
        historical = history.frame(
            config.benchmark_symbol,
            cutoff,
            include_cutoff=True,
        )
        intraday = history.intraday_frame(
            config.benchmark_symbol,
            target_timestamp=cutoff,
        )
        if intraday.empty:
            combined = historical
        else:
            cutoff_utc = pd.Timestamp(cutoff).tz_convert("UTC")
            intraday = intraday.loc[
                intraday["timestamp"] <= cutoff_utc
            ].copy()
            combined = pd.concat(
                [historical, intraday],
                ignore_index=True,
            )

        if combined.empty:
            return combined

        combined["timestamp"] = pd.to_datetime(
            combined["timestamp"],
            utc=True,
            errors="raise",
        )
        combined = combined.sort_values("timestamp", kind="stable")
        combined = combined.drop_duplicates(
            ["timestamp", "symbol"],
            keep="last",
        )
        return combined.reset_index(drop=True)

    market_bot = MarketBot(
        MarketBotConfig(
            benchmark=config.benchmark_symbol,
            data_version=config.data_version,
            feature_version=config.feature_version,
            require_live_account_context=True,
        )
    )

    research_cache = LiveResearchCache(
        providers=_load_live_research_providers(),
        retention=timedelta(days=7),
    )
    research_runtime = LiveResearchRuntime(
        cache=research_cache,
        symbols=(config.symbol.strip().upper(),),
        poll_interval=timedelta(seconds=30),
        lookback=timedelta(hours=24),
    )

    def benchmark_context_provider(cutoff, benchmark_frame):
        return market_bot.build(
            benchmark_data=benchmark_frame,
            provenance={"provider": "upstox-historical-v3+intraday-v3"},
        )

    risk_context_provider = _load_live_risk_context_provider()
    risk_engine = RiskEngine()
    scanner_store = StockScannerStore()
    operator_snapshot_path = config.operator_snapshot_path
    operator_writer = None
    if operator_snapshot_path is not None:
        operator_writer = OperatorSnapshotWriter(
            path=operator_snapshot_path,
            symbol=config.symbol,
            benchmark_symbol=config.benchmark_symbol,
            model_version=config.model_version,
            calibration_version=manifest.provenance.calibration_version,
            data_version=config.data_version,
            feature_version=config.feature_version,
            require_live_account_context=True,
        )
        operator_writer.write_initial()

    def observe_decision(decision, candle):
        scanner_store.observe(decision, price=float(candle.close))
        if operator_writer is not None:
            operator_writer.observe(decision, candle)

    return CanonicalLivePaperOrchestrator(
        decision_observer=observe_decision,
        market_data=pipeline,
        market_bot=market_bot,
        model=model,
        preprocessor=preprocessor,
        calibrator=calibrator,
        paper_engine=None,
        risk_engine=risk_engine,
        benchmark_history_provider=benchmark_history_provider,
        benchmark_context_provider=benchmark_context_provider,
        history_provider=stock_history_provider,
        config=CanonicalLivePaperConfig(
            symbol=config.symbol.strip().upper(),
            model_version=config.model_version,
            data_version=config.data_version,
            feature_version=config.feature_version,
            target_version=manifest.provenance.target_version,
            calibration_version=manifest.provenance.calibration_version,
            target_trades=1,
        ),
        research_context_provider=lambda cutoff: research_cache.build_analysis_context(
            symbol=config.symbol.strip().upper(),
            as_of=cutoff.to_pydatetime(),
        ),
        research_runtime=research_runtime,
        risk_context_provider=risk_context_provider,
    )


def run_live_manual_review(config: LiveManualReviewConfig) -> int:
    """Run V1 real-market candles until max_candles or stream termination."""
    runtime = build_live_manual_review_runtime(config)

    print("=" * 72)
    print("STOCK BOT — V1 REAL-MARKET MANUAL REVIEW")
    print("=" * 72)
    print(f"Symbol              : {config.symbol}")
    print(f"Benchmark           : {config.benchmark_symbol}")
    print("Market data         : Upstox realtime")
    print("Decision authority  : HUMAN REVIEW")
    print("Execution           : MANUAL BUY/SELL ONLY")
    print("Broker orders       : 0")
    print("=" * 72)

    produced = runtime.run_manual_review(
        [config.symbol],
        max_candles=config.max_candles,
    )

    print("-" * 72)
    print(f"Completed candles   : {produced}")
    print("Broker orders       : 0")
    print("=" * 72)
    return 0


__all__ = [
    "LiveManualReviewConfig",
    "build_live_manual_review_runtime",
    "run_live_manual_review",
]
