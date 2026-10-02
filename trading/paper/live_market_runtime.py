"""Real-market virtual-paper runtime composition.

This module wires the existing Upstox realtime feed into the canonical
Market -> Analysis -> Prediction -> Strategy -> Risk -> Safety -> Paper path.
It never submits broker orders.
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
from trading.paper.canonical_live_orchestrator import (
    CanonicalLivePaperConfig,
    CanonicalLivePaperOrchestrator,
)
from trading.paper.live_loop import LivePaperEngine, LivePaperSessionConfig
from trading.paper.upstox_history import UpstoxHistoryProvider
from paper.virtual_session import VirtualIntradaySession, VirtualIntradaySessionConfig
from research.live.runtime import LiveResearchCache, LiveResearchRuntime
from research.providers import pib_provider, rbi_provider, RssResearchProvider


def _load_runtime_instrument_mapper() -> UpstoxInstrumentMapper:
    """Merge trading and benchmark Upstox instrument maps from environment."""
    raw_mapping = os.getenv("UPSTOX_INSTRUMENT_MAP", "").strip()
    if not raw_mapping:
        raise ValueError(
            "UPSTOX_INSTRUMENT_MAP is required for the live market feed"
        )

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


def _load_live_research_providers() -> tuple:
    """Build explicit live research source adapters from configuration."""
    providers = [rbi_provider(), pib_provider()]

    raw_urls = os.getenv("STOCK_BOT_RESEARCH_RSS_URLS", "").strip()
    if raw_urls:
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
class LiveMarketPaperConfig:
    """Startup configuration for one real-market virtual session."""

    symbol: str
    benchmark_symbol: str
    model_artifact: Path
    model_sha256: str
    model_version: str
    data_version: str = "upstox-live-v1"
    feature_version: str = "v1.0"
    initial_equity: float = 100_000.0
    session_id: str = "VIRTUAL-INTRADAY-001"
    output_dir: Path = Path("paper/virtual_sessions")
    max_candles: int | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if not self.benchmark_symbol.strip():
            raise ValueError("benchmark_symbol must not be empty")
        if not self.model_artifact:
            raise ValueError("model_artifact must be supplied")
        if len(self.model_sha256) != 64:
            raise ValueError("model_sha256 must be a SHA-256 hex digest")
        if not self.model_version.strip():
            raise ValueError("model_version must not be empty")
        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if self.max_candles is not None and self.max_candles <= 0:
            raise ValueError("max_candles must be positive when supplied")


def build_live_market_paper_session(
    config: LiveMarketPaperConfig,
) -> VirtualIntradaySession:
    """Build the complete real-market paper stack without starting it."""
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
        raise ValueError(
            "model artifact version does not match runtime model_version"
        )
    if manifest.provenance.model_family != "logistic":
        raise ValueError("live paper runtime requires a logistic Phase-9 artifact")
    if not manifest.provenance.calibration_version:
        raise ValueError("live paper runtime requires a calibrated Phase-9 artifact")

    history = UpstoxHistoryProvider.from_env(mapper)

    def stock_history_provider(cutoff):
        return history.candles(config.symbol, cutoff)

    def benchmark_history_provider(cutoff):
        # Historical V3 supplies previous trading days while Intraday V3
        # supplies the current trading day. Combine both sources and retain
        # only candles available at the exact causal decision timestamp.
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

    paper_engine = LivePaperEngine(
        LivePaperSessionConfig(
            experiment_id=config.session_id,
            target_trades=1_000_000,
            symbol=config.symbol.strip().upper(),
            initial_equity=config.initial_equity,
            model_version=config.model_version,
            stop_on_target_trades=False,
        )
    )

    orchestrator = CanonicalLivePaperOrchestrator(
        market_data=pipeline,
        market_bot=market_bot,
        model=model,
        preprocessor=preprocessor,
        calibrator=calibrator,
        paper_engine=paper_engine,
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
            target_trades=1_000_000,
        ),
        research_context_provider=lambda cutoff: research_cache.build_analysis_context(
            symbol=config.symbol.strip().upper(),
            as_of=cutoff.to_pydatetime(),
        ),
        research_runtime=research_runtime,
    )

    return VirtualIntradaySession(
        orchestrator,
        config=VirtualIntradaySessionConfig(
            initial_equity=config.initial_equity,
            output_dir=config.output_dir,
            session_id=config.session_id,
        ),
    )


def run_live_market_paper_session(config: LiveMarketPaperConfig) -> int:
    """Start one real-market virtual session and validate its final state."""
    session = build_live_market_paper_session(config)

    print("=" * 72)
    print("STOCK BOT — REAL-MARKET VIRTUAL PAPER")
    print("=" * 72)
    print(f"Symbol              : {config.symbol}")
    print(f"Benchmark           : {config.benchmark_symbol}")
    print(f"Virtual capital     : ₹{config.initial_equity:,.2f}")
    print("Market data         : Upstox realtime")
    print("Execution           : PAPER ONLY")
    print("Broker orders       : 0")
    print("Session              : 09:15–15:30 IST")
    print("=" * 72)

    result = session.run(
        [config.symbol],
        max_candles=config.max_candles,
    )

    print("-" * 72)
    print(f"Completed trades    : {result.completed_trades}")
    print(f"Session fingerprint : {result.session_fingerprint}")
    print("Broker orders       : 0")
    print("=" * 72)
    return 0


__all__ = [
    "LiveMarketPaperConfig",
    "build_live_market_paper_session",
    "run_live_market_paper_session",
    "_load_runtime_instrument_mapper",
]
