"""Tests for historical provider policy boundaries."""

import pytest

from market.data.historical.adapters.yfinance import (
    YFinanceHistoricalMarketDataProvider,
)
from market.data.historical.models import HistoricalDataRequest
from market.data.historical.pipeline import HistoricalMarketDataPipeline
from market.data.historical.providers import (
    HistoricalDataPurpose,
    HistoricalProviderRole,
    StaticHistoricalMarketDataProvider,
)


def test_yfinance_provider_is_research_only() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    assert provider.role is HistoricalProviderRole.RESEARCH
    assert provider.period == "5d"
    assert provider.auto_adjust is False


def test_yfinance_supports_canonical_five_minute_request() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    assert provider._interval(request.timeframe_minutes) == "5m"


def test_static_provider_is_test_only() -> None:
    assert (
        StaticHistoricalMarketDataProvider.role
        is HistoricalProviderRole.TEST
    )


def test_research_purpose_accepts_research_provider() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    pipeline = HistoricalMarketDataPipeline(
        provider=provider,
        require_complete_sessions=False,
        purpose=HistoricalDataPurpose.RESEARCH,
    )

    assert pipeline._purpose is HistoricalDataPurpose.RESEARCH


def test_authoritative_purpose_rejects_research_provider_before_fetch() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    pipeline = HistoricalMarketDataPipeline(
        provider=provider,
        purpose=HistoricalDataPurpose.CANONICAL,
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    with pytest.raises(
        ValueError,
        match="canonical historical ingestion requires a canonical provider",
    ):
        pipeline.ingest(request)


def test_authoritative_purpose_rejects_test_provider_before_fetch() -> None:
    provider = StaticHistoricalMarketDataProvider([])

    pipeline = HistoricalMarketDataPipeline(
        provider=provider,
        purpose=HistoricalDataPurpose.CANONICAL,
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    with pytest.raises(
        ValueError,
        match="canonical historical ingestion requires a canonical provider",
    ):
        pipeline.ingest(request)
