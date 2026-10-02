"""Tests for live Research -> Analysis integration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from market.bot.orchestrator import MarketBot, MarketBotConfig
from research.contracts import ResearchDocument
from research.live.runtime import LiveResearchCache
from trading.market_bot_pipeline import build_market_analysis_from_market_bot


UTC = timezone.utc


class FakeProvider:
    source_id = "test-source"

    def __init__(self, documents):
        self.documents = tuple(documents)

    def fetch(self, *, symbols, start, end):
        return tuple(d for d in self.documents if d.available_at <= end)


def _benchmark(rows: int = 40) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-09-20 09:15:00+05:30",
        periods=rows,
        freq="5min",
    )
    close = 100.0 * np.cumprod(1.0 + np.full(rows, 0.001))
    return pd.DataFrame({"timestamp": timestamps, "close": close})


def _candles(rows: int = 40) -> pd.DataFrame:
    benchmark = _benchmark(rows)
    close = benchmark["close"].to_numpy()
    return pd.DataFrame({
        "timestamp": benchmark["timestamp"],
        "symbol": ["RELIANCE"] * rows,
        "open": close,
        "high": close + 0.20,
        "low": close - 0.15,
        "close": close,
        "volume": [1000 + (index * 10) for index in range(rows)],
    })


def test_research_context_reaches_analysis_without_changing_market_authority():
    candles = _candles()
    decision = pd.Timestamp(candles.iloc[-1]["timestamp"]).tz_convert("UTC").to_pydatetime()
    document_time = decision - timedelta(minutes=2)

    document = ResearchDocument(
        document_id="doc-research-1",
        source_id="test-source",
        external_id="research-1",
        title="RELIANCE announcement",
        content="RELIANCE announces a positive business update",
        published_at=document_time - timedelta(minutes=1),
        observed_at=document_time,
        processed_at=document_time,
        available_at=document_time,
        symbols=("RELIANCE",),
    )

    cache = LiveResearchCache(
        providers=(FakeProvider((document,)),),
        clock=lambda: decision,
    )
    cache.refresh(
        symbols=("RELIANCE",),
        start=decision - timedelta(hours=1),
        end=decision,
    )
    research = cache.build_analysis_context(
        symbol="RELIANCE",
        as_of=decision,
    )

    benchmark = _benchmark()
    market_context = MarketBot(
        MarketBotConfig(benchmark="NIFTY", data_version="market-test")
    ).build(benchmark_data=benchmark)

    result = build_market_analysis_from_market_bot(
        candles,
        symbol="RELIANCE",
        benchmark_history=benchmark,
        market_context=market_context,
        research_context=research,
    )

    assert result.analysis.research_context["available"] is True
    assert result.analysis.research_context["symbol"] == "RELIANCE"
    assert result.analysis.research_context["as_of"] == decision.isoformat()
    assert result.analysis.provenance["sources"]["research_context"] is True
    assert result.analysis.provenance["market_bot"]["market_version"] == market_context.metadata.market_version
